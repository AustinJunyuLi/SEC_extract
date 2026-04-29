"""Async SDK-backed deal-pool runner."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pipeline import core
from pipeline.llm.adjudicate import adjudicate
from pipeline.llm.audit import AuditWriter, TokenUsage
from pipeline.llm.client import LLMClient, OpenAICompatibleClient
from pipeline.llm.extract import extract_deal, extractor_contract_version
from pipeline.llm.retry import RetryConfig
from pipeline.llm.watchdog import WatchdogConfig


DONE_STATUSES = {"validated", "passed", "passed_clean", "verified"}
VALID_FILTERS = {"pending", "reference", "failed", "all"}
AUDIT_ROOT = core.REPO_ROOT / "output" / "audit"
DEFAULT_XHIGH_MAX_WORKERS = 5
DEFAULT_REASONING_EFFORT = "xhigh"
SEMANTIC_ADJUDICATION_SOFT_FLAGS: frozenset[str] = frozenset({
    "missing_nda_dropsilent",
})


@dataclass
class PoolConfig:
    slugs: tuple[str, ...] = ()
    filter: Literal["pending", "reference", "failed", "all"] = "pending"
    workers: int = 1
    extract_model: str = "gpt-5.5"
    adjudicate_model: str = "gpt-5.5"
    extract_reasoning_effort: str | None = DEFAULT_REASONING_EFFORT
    adjudicate_reasoning_effort: str | None = DEFAULT_REASONING_EFFORT
    re_validate: bool = False
    re_extract: bool = False
    commit: bool = False
    dry_run: bool = False
    api_key: str | None = None
    base_url: str | None = "https://www.linkflow.run/v1"
    audit_root: Path = AUDIT_ROOT
    watchdog_cfg: WatchdogConfig = field(default_factory=WatchdogConfig)
    retry_cfg: RetryConfig = field(default_factory=RetryConfig)


@dataclass(frozen=True)
class SkipDecision:
    action: Literal["skip", "run", "re_validate", "blocked"]
    reason: str


@dataclass
class DealOutcome:
    slug: str
    status: str
    skipped: bool = False
    cached: bool = False
    error: str | None = None
    flag_count: int | None = None
    notes: str = ""
    output_path: Path | None = None
    audit_path: Path | None = None


@dataclass
class PoolSummary:
    outcomes: list[DealOutcome] = field(default_factory=list)

    @property
    def selected(self) -> int:
        return len(self.outcomes)

    @property
    def succeeded(self) -> int:
        return sum(
            1 for outcome in self.outcomes
            if outcome.status in {"validated", "passed", "passed_clean", "verified"}
        )

    @property
    def skipped(self) -> int:
        return sum(1 for outcome in self.outcomes if outcome.skipped)

    @property
    def failed(self) -> int:
        return sum(1 for outcome in self.outcomes if outcome.status == "failed")


def _load_progress() -> dict[str, Any]:
    return json.loads(core.PROGRESS_PATH.read_text())


def resolve_selection(cfg: PoolConfig, state: dict[str, Any] | None = None) -> list[str]:
    state = state or _load_progress()
    deals = state.get("deals", {})
    if cfg.slugs:
        missing = [slug for slug in cfg.slugs if slug not in deals]
        if missing:
            raise KeyError(f"slug(s) not in state/progress.json: {', '.join(missing)}")
        return list(cfg.slugs)
    if cfg.filter == "all":
        return list(deals)
    if cfg.filter == "reference":
        return [slug for slug, deal in deals.items() if deal.get("is_reference") is True]
    return [slug for slug, deal in deals.items() if deal.get("status") == cfg.filter]


def audit_dir(cfg: PoolConfig, slug: str) -> Path:
    return cfg.audit_root / slug


def _cached_raw_response_path(cfg: PoolConfig, slug: str) -> Path:
    return audit_dir(cfg, slug) / "raw_response.json"


@dataclass(frozen=True)
class CacheCheck:
    parsed_json: dict[str, Any] | None
    reason: str

    @property
    def valid(self) -> bool:
        return self.parsed_json is not None


def _check_cached_raw_response(slug: str, cfg: PoolConfig, current_rulebook_version: str) -> CacheCheck:
    path = _cached_raw_response_path(cfg, slug)
    if not path.exists():
        return CacheCheck(None, "no cached raw_response.json for --re-validate")
    payload = json.loads(path.read_text())
    if payload.get("schema_version") != "v1":
        return CacheCheck(None, "cached raw_response.json schema_version is not v1")
    if payload.get("slug") != slug:
        return CacheCheck(None, f"cached raw_response.json slug={payload.get('slug')!r} does not match {slug!r}")
    if payload.get("rulebook_version") != current_rulebook_version:
        return CacheCheck(
            None,
            "cached raw_response.json rulebook_version does not match current rulebook; "
            "use --re-extract for a fresh SDK call",
        )
    if payload.get("extractor_contract_version") != extractor_contract_version():
        return CacheCheck(
            None,
            "cached raw_response.json extractor_contract_version does not match current prompt/schema; "
            "use --re-extract for a fresh SDK call",
        )
    parsed = payload.get("parsed_json")
    if not isinstance(parsed, dict):
        return CacheCheck(None, "cached raw_response.json parsed_json is not an object")
    if not isinstance(parsed.get("deal"), dict):
        return CacheCheck(None, "cached raw_response.json parsed_json.deal is not an object")
    if not isinstance(parsed.get("events"), list):
        return CacheCheck(None, "cached raw_response.json parsed_json.events is not a list")
    return CacheCheck(parsed, "valid cached raw_response.json")


def _cached_raw_response(slug: str, cfg: PoolConfig, current_rulebook_version: str) -> dict[str, Any] | None:
    return _check_cached_raw_response(slug, cfg, current_rulebook_version).parsed_json


def decide_skip(
    slug: str,
    cfg: PoolConfig,
    current_rulebook_version: str,
    state: dict[str, Any] | None = None,
) -> SkipDecision:
    if cfg.re_extract:
        return SkipDecision("run", "fresh SDK extraction requested")
    if cfg.re_validate:
        cached = _check_cached_raw_response(slug, cfg, current_rulebook_version)
        if cached.valid:
            return SkipDecision("re_validate", cached.reason)
        return SkipDecision("blocked", cached.reason)
    state = state or _load_progress()
    deal = state.get("deals", {}).get(slug, {})
    status = deal.get("status")
    if status in DONE_STATUSES and deal.get("rulebook_version") == current_rulebook_version:
        return SkipDecision("skip", f"status={status} rulebook unchanged")
    return SkipDecision("run", "pending, failed, or stale rulebook")


def _soft_flags(result: core.ValidatorResult) -> list[dict[str, Any]]:
    return [
        flag for flag in [*result.row_flags, *result.deal_flags]
        if flag.get("severity") == "soft"
        and flag.get("code") in SEMANTIC_ADJUDICATION_SOFT_FLAGS
    ]


def _watchdog_warnings(audit: AuditWriter) -> int:
    path = audit.root / "calls.jsonl"
    if not path.exists():
        return 0
    total = 0
    for line in path.read_text().splitlines():
        entry = json.loads(line)
        watchdog = entry.get("watchdog")
        if isinstance(watchdog, dict):
            total += int(watchdog.get("warnings") or 0)
    return total


def _xhigh_max_workers() -> int:
    return int(os.environ.get("LINKFLOW_XHIGH_MAX_WORKERS", str(DEFAULT_XHIGH_MAX_WORKERS)))


def _validate_config(config: PoolConfig) -> None:
    if config.workers < 1:
        raise ValueError("--workers must be >= 1")
    if "xhigh" in {config.extract_reasoning_effort, config.adjudicate_reasoning_effort}:
        cap = _xhigh_max_workers()
        if config.workers > cap:
            raise ValueError(
                f"Linkflow xhigh reasoning is capped at workers <= {cap}; "
                f"got workers={config.workers}"
            )


def _build_audit_writer(root: Path, slug: str, *, run_action: str) -> AuditWriter:
    audit_root = root / slug
    if run_action in {"run", "re_validate"}:
        with contextlib.suppress(FileNotFoundError):
            (audit_root / "calls.jsonl").unlink()
        shutil.rmtree(audit_root / "prompts", ignore_errors=True)
    if run_action == "run":
        with contextlib.suppress(FileNotFoundError):
            (audit_root / "raw_response.json").unlink()
    return AuditWriter(root, slug)


def _prior_status_is_success(slug: str) -> bool:
    try:
        state = _load_progress()
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    return state.get("deals", {}).get(slug, {}).get("status") in DONE_STATUSES


def _commit_paths(slug: str, paths: list[Path]) -> None:
    pathspecs: list[str] = []
    seen: set[str] = set()
    for path in paths:
        if not path.exists():
            continue
        rel = str(path.resolve().relative_to(core.REPO_ROOT.resolve()))
        if rel in seen:
            continue
        seen.add(rel)
        pathspecs.append(rel)
    if not pathspecs:
        return
    drift = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--", *pathspecs],
        cwd=core.REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    if drift:
        raise RuntimeError(f"staged content for {drift!r} differs from current-deal commit paths")
    subprocess.run(["git", "add", "--", *pathspecs], cwd=core.REPO_ROOT, check=True)
    subprocess.run(
        ["git", "commit", "--only", "-m", f"deal={slug} api-pool", "--", *pathspecs],
        cwd=core.REPO_ROOT,
        check=True,
    )


async def process_deal(
    slug: str,
    *,
    config: PoolConfig,
    llm_client: LLMClient,
    schema_supported: bool,
    rulebook_version: str,
    skip_decision: SkipDecision | None = None,
) -> DealOutcome:
    decision = skip_decision or decide_skip(slug, config, rulebook_version)
    audit = _build_audit_writer(config.audit_root, slug, run_action=decision.action)
    started = time.monotonic()
    if decision.action == "skip":
        audit.write_manifest({
            "rulebook_version": rulebook_version,
            "models": {"extract": config.extract_model, "adjudicate": config.adjudicate_model},
            "api_endpoint": getattr(llm_client, "endpoint", None),
            "reasoning_efforts": {
                "extract": config.extract_reasoning_effort,
                "adjudicate": config.adjudicate_reasoning_effort,
            },
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_reasoning_tokens": 0,
            "total_attempts": 0,
            "total_seconds": 0.0,
            "watchdog_warnings": 0,
            "outcome": "skipped",
            "reason": decision.reason,
        })
        return DealOutcome(slug=slug, status="skipped", skipped=True, notes=decision.reason, audit_path=audit.root)
    if decision.action == "blocked":
        audit.write_manifest({
            "rulebook_version": rulebook_version,
            "models": {"extract": config.extract_model, "adjudicate": config.adjudicate_model},
            "api_endpoint": getattr(llm_client, "endpoint", None),
            "reasoning_efforts": {
                "extract": config.extract_reasoning_effort,
                "adjudicate": config.adjudicate_reasoning_effort,
            },
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_reasoning_tokens": 0,
            "total_attempts": 0,
            "total_seconds": 0.0,
            "watchdog_warnings": 0,
            "outcome": "blocked",
            "reason": decision.reason,
        })
        return DealOutcome(slug=slug, status="skipped", skipped=True, notes=decision.reason, audit_path=audit.root)

    token_usage = TokenUsage()
    cached = False
    try:
        if decision.action == "re_validate":
            raw_extraction = _cached_raw_response(slug, config, rulebook_version)
            if raw_extraction is None:
                raise RuntimeError("cached raw_response.json disappeared or became stale")
            cached = True
        else:
            extract_result = await extract_deal(
                slug,
                llm_client=llm_client,
                extract_model=config.extract_model,
                audit=audit,
                token_usage=token_usage,
                rulebook_version=rulebook_version,
                schema_supported=schema_supported,
                reasoning_effort=config.extract_reasoning_effort,
            )
            raw_extraction = extract_result.raw_extraction

        filing = await asyncio.to_thread(core.load_filing, slug)
        prepared, filing, promotion_log = await asyncio.to_thread(
            core.prepare_for_validate,
            slug,
            raw_extraction,
            filing,
        )
        validation = await asyncio.to_thread(core.validate, prepared, filing)
        soft_flags = _soft_flags(validation)
        if soft_flags:
            await adjudicate(
                slug,
                prepared,
                soft_flags,
                filing,
                llm_client=llm_client,
                adjudicate_model=config.adjudicate_model,
                audit=audit,
                token_usage=token_usage,
                schema_supported=schema_supported,
                reasoning_effort=config.adjudicate_reasoning_effort,
            )
        result = await asyncio.to_thread(
            core.finalize_prepared,
            slug,
            prepared,
            filing,
            validation,
            promotion_log,
        )
        elapsed = time.monotonic() - started
        audit.write_manifest({
            "rulebook_version": rulebook_version,
            "models": {"extract": config.extract_model, "adjudicate": config.adjudicate_model},
            "api_endpoint": getattr(llm_client, "endpoint", None),
            "reasoning_efforts": {
                "extract": config.extract_reasoning_effort,
                "adjudicate": config.adjudicate_reasoning_effort,
            },
            "total_input_tokens": token_usage.input_used,
            "total_output_tokens": token_usage.output_used,
            "total_reasoning_tokens": token_usage.reasoning_used,
            "total_attempts": None,
            "total_seconds": elapsed,
            "watchdog_warnings": _watchdog_warnings(audit),
            "outcome": result.status,
            "cache_used": cached,
        })
        if config.commit:
            _commit_paths(
                slug,
                [
                    result.output_path,
                    core.PROGRESS_PATH,
                    core.FLAGS_PATH,
                    audit.root / "manifest.json",
                    audit.root / "raw_response.json",
                    audit.root / "calls.jsonl",
                    *list((audit.root / "prompts").glob("*.txt")),
                ],
            )
        return DealOutcome(
            slug=slug,
            status=result.status,
            cached=cached,
            flag_count=result.flag_count,
            notes=result.notes,
            output_path=result.output_path,
            audit_path=audit.root,
        )
    except Exception as exc:  # noqa: BLE001 - per-deal isolation is the pool contract.
        note = f"{type(exc).__name__}: {exc}"[:500]
        if not _prior_status_is_success(slug):
            await asyncio.to_thread(core.mark_failed, slug, note)
        audit.write_manifest({
            "rulebook_version": rulebook_version,
            "models": {"extract": config.extract_model, "adjudicate": config.adjudicate_model},
            "api_endpoint": getattr(llm_client, "endpoint", None),
            "reasoning_efforts": {
                "extract": config.extract_reasoning_effort,
                "adjudicate": config.adjudicate_reasoning_effort,
            },
            "total_input_tokens": token_usage.input_used,
            "total_output_tokens": token_usage.output_used,
            "total_reasoning_tokens": token_usage.reasoning_used,
            "total_attempts": None,
            "total_seconds": time.monotonic() - started,
            "watchdog_warnings": _watchdog_warnings(audit),
            "outcome": "failed",
            "cache_used": cached,
            "error": note,
        })
        return DealOutcome(slug=slug, status="failed", cached=cached, error=note, audit_path=audit.root)


async def run_pool(config: PoolConfig, *, llm_client: LLMClient | None = None) -> PoolSummary:
    _validate_config(config)
    state = _load_progress()
    slugs = resolve_selection(config, state)
    current = core.rulebook_version()
    plan = [(slug, decide_skip(slug, config, current, state)) for slug in slugs]
    if config.dry_run:
        print("DRY RUN selected deals:")
        outcomes = []
        for slug, decision in plan:
            print(f"  {slug}: {decision.action} ({decision.reason})")
            outcomes.append(DealOutcome(slug=slug, status="dry_run", notes=decision.reason))
        return PoolSummary(outcomes)

    client = llm_client or _build_client(config)
    schema_supported = bool(getattr(client, "supports_structured_output", False))
    sem = asyncio.Semaphore(config.workers)

    async def gated(slug: str, decision: SkipDecision) -> DealOutcome:
        async with sem:
            return await process_deal(
                slug,
                config=config,
                llm_client=client,
                schema_supported=schema_supported,
                rulebook_version=current,
                skip_decision=decision,
            )

    gathered = await asyncio.gather(
        *(gated(slug, decision) for slug, decision in plan),
        return_exceptions=True,
    )
    outcomes: list[DealOutcome] = []
    for (slug, _decision), item in zip(plan, gathered, strict=True):
        if isinstance(item, Exception):
            outcomes.append(DealOutcome(slug=slug, status="failed", error=f"{type(item).__name__}: {item}"))
        else:
            outcomes.append(item)
    summary = PoolSummary(outcomes)
    print(
        f"Pool summary: selected={summary.selected} succeeded={summary.succeeded} "
        f"skipped={summary.skipped} failed={summary.failed}"
    )
    return summary


def _float_env(name: str, default: float) -> float:
    value = os.environ.get(name)
    return default if value is None else float(value)


def _int_env(name: str, default: int) -> int:
    value = os.environ.get(name)
    return default if value is None else int(value)


def _build_client(config: PoolConfig) -> OpenAICompatibleClient:
    api_key = config.api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required unless --dry-run")
    base_url = config.base_url or os.environ.get("OPENAI_BASE_URL") or "https://www.linkflow.run/v1"
    return OpenAICompatibleClient(
        api_key=api_key,
        base_url=base_url,
        watchdog_cfg=config.watchdog_cfg,
        retry_cfg=config.retry_cfg,
    )


def load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--slugs", help="Comma-separated deal slugs.")
    selection.add_argument("--filter", choices=sorted(VALID_FILTERS), default="pending")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--extract-model", default=os.environ.get("EXTRACT_MODEL", "gpt-5.5"))
    parser.add_argument("--adjudicate-model", default=os.environ.get("ADJUDICATE_MODEL", "gpt-5.5"))
    parser.add_argument(
        "--extract-reasoning-effort",
        default=os.environ.get("EXTRACT_REASONING_EFFORT") or DEFAULT_REASONING_EFFORT,
        choices=["none", "minimal", "low", "medium", "high", "xhigh"],
        help=f"reasoning.effort for extractor calls (default: {DEFAULT_REASONING_EFFORT})",
    )
    parser.add_argument(
        "--adjudicate-reasoning-effort",
        default=os.environ.get("ADJUDICATE_REASONING_EFFORT") or DEFAULT_REASONING_EFFORT,
        choices=["none", "minimal", "low", "medium", "high", "xhigh"],
        help=f"reasoning.effort for adjudicator calls (default: {DEFAULT_REASONING_EFFORT})",
    )
    rerun = parser.add_mutually_exclusive_group()
    rerun.add_argument("--re-validate", action="store_true", help="Reuse only a current raw_response.json cache.")
    rerun.add_argument("--re-extract", action="store_true")
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def config_from_args(args: argparse.Namespace) -> PoolConfig:
    slugs = tuple(slug.strip() for slug in (args.slugs or "").split(",") if slug.strip())
    cfg = PoolConfig(
        slugs=slugs,
        filter=args.filter,
        workers=args.workers,
        extract_model=args.extract_model,
        adjudicate_model=args.adjudicate_model,
        extract_reasoning_effort=args.extract_reasoning_effort,
        adjudicate_reasoning_effort=args.adjudicate_reasoning_effort,
        re_validate=args.re_validate,
        re_extract=args.re_extract,
        commit=args.commit,
        dry_run=args.dry_run,
        api_key=os.environ.get("OPENAI_API_KEY"),
        base_url=os.environ.get("OPENAI_BASE_URL", "https://www.linkflow.run/v1"),
        watchdog_cfg=WatchdogConfig(
            heartbeat_seconds=_float_env("LLM_HEARTBEAT_SECONDS", 5.0),
            stale_warning_seconds=_float_env("LLM_STALE_WARNING_SECONDS", 90.0),
            stream_idle_seconds=_float_env("LLM_STREAM_IDLE_SECONDS", 120.0),
            total_call_seconds=_float_env("LLM_TOTAL_CALL_SECONDS", 600.0),
        ),
        retry_cfg=RetryConfig(
            max_attempts=_int_env("LLM_MAX_ATTEMPTS", 3),
            backoff_base_seconds=_float_env("LLM_BACKOFF_BASE_SECONDS", 5.0),
            backoff_factor=_float_env("LLM_BACKOFF_FACTOR", 3.0),
        ),
    )
    _validate_config(cfg)
    return cfg


def main(argv: list[str] | None = None) -> int:
    load_dotenv_if_available()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        cfg = config_from_args(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not cfg.dry_run and not cfg.api_key:
        parser.error("OPENAI_API_KEY is required unless --dry-run")
    summary = asyncio.run(run_pool(cfg))
    return 1 if summary.failed else 0


if __name__ == "__main__":
    sys.exit(main())
