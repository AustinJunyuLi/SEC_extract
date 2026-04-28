"""Async SDK-backed deal-pool runner."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from pipeline import core
from pipeline.llm.adjudicate import adjudicate
from pipeline.llm.audit import AuditWriter, TokenBudget
from pipeline.llm.client import LLMClient, OpenAICompatibleClient
from pipeline.llm.extract import extract_deal
from pipeline.llm.response_format import supports_json_schema
from pipeline.llm.retry import RetryConfig
from pipeline.llm.watchdog import WatchdogConfig


DONE_STATUSES = {"validated", "passed", "passed_clean", "verified"}
VALID_FILTERS = {"pending", "reference", "failed", "all"}
AUDIT_ROOT = core.REPO_ROOT / "output" / "audit"


@dataclass
class PoolConfig:
    slugs: tuple[str, ...] = ()
    filter: Literal["pending", "reference", "failed", "all"] = "pending"
    workers: int = 1
    extract_model: str = "gpt-5.5"
    adjudicate_model: str = "gpt-5.5"
    max_tokens_per_deal: int = 200000
    re_validate: bool = False
    re_extract: bool = False
    force: bool = False
    commit: bool = False
    dry_run: bool = False
    api_key: str | None = None
    base_url: str | None = "https://www.linkflow.run/v1"
    audit_root: Path = AUDIT_ROOT
    watchdog_cfg: WatchdogConfig = field(default_factory=WatchdogConfig)
    retry_cfg: RetryConfig = field(default_factory=RetryConfig)


@dataclass(frozen=True)
class SkipDecision:
    action: Literal["skip", "run", "re_validate"]
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


def _cached_raw_response(slug: str, cfg: PoolConfig, current_rulebook_version: str) -> dict[str, Any] | None:
    path = _cached_raw_response_path(cfg, slug)
    if not path.exists():
        return None
    payload = json.loads(path.read_text())
    if payload.get("schema_version") != "v1":
        return None
    if payload.get("slug") != slug:
        return None
    if payload.get("rulebook_version") != current_rulebook_version:
        return None
    parsed = payload.get("parsed_json")
    if not isinstance(parsed, dict):
        return None
    if not isinstance(parsed.get("deal"), dict):
        return None
    if not isinstance(parsed.get("events"), list):
        return None
    return parsed


def decide_skip(
    slug: str,
    cfg: PoolConfig,
    current_rulebook_version: str,
    state: dict[str, Any] | None = None,
) -> SkipDecision:
    if cfg.force or cfg.re_extract:
        return SkipDecision("run", "forced fresh extraction")
    if cfg.re_validate:
        cached = _cached_raw_response(slug, cfg, current_rulebook_version)
        if cached is not None:
            return SkipDecision("re_validate", "valid cached raw_response.json")
        return SkipDecision("run", "no current cache for re-validate")
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
    audit = AuditWriter(config.audit_root, slug)
    started = time.monotonic()
    if decision.action == "skip":
        audit.write_manifest({
            "rulebook_version": rulebook_version,
            "models": {"extract": config.extract_model, "adjudicate": config.adjudicate_model},
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

    budget = TokenBudget(config.max_tokens_per_deal)
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
                token_budget=budget,
                rulebook_version=rulebook_version,
                schema_supported=schema_supported,
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
                token_budget=budget,
                schema_supported=schema_supported,
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
            "total_input_tokens": budget.input_used,
            "total_output_tokens": budget.output_used,
            "total_reasoning_tokens": budget.reasoning_used,
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
        await asyncio.to_thread(core.mark_failed, slug, note)
        audit.write_manifest({
            "rulebook_version": rulebook_version,
            "models": {"extract": config.extract_model, "adjudicate": config.adjudicate_model},
            "total_input_tokens": budget.input_used,
            "total_output_tokens": budget.output_used,
            "total_reasoning_tokens": budget.reasoning_used,
            "total_attempts": None,
            "total_seconds": time.monotonic() - started,
            "watchdog_warnings": _watchdog_warnings(audit),
            "outcome": "failed",
            "cache_used": cached,
            "error": note,
        })
        return DealOutcome(slug=slug, status="failed", cached=cached, error=note, audit_path=audit.root)


async def run_pool(config: PoolConfig, *, llm_client: LLMClient | None = None) -> PoolSummary:
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
    schema_supported = await supports_json_schema(client, model=config.extract_model)
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
    parser.add_argument("--max-tokens-per-deal", type=int, default=_int_env("MAX_TOKENS_PER_DEAL", 200000))
    rerun = parser.add_mutually_exclusive_group()
    rerun.add_argument("--re-validate", action="store_true")
    rerun.add_argument("--re-extract", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def config_from_args(args: argparse.Namespace) -> PoolConfig:
    if args.workers < 1:
        raise ValueError("--workers must be >= 1")
    slugs = tuple(slug.strip() for slug in (args.slugs or "").split(",") if slug.strip())
    return PoolConfig(
        slugs=slugs,
        filter=args.filter,
        workers=args.workers,
        extract_model=args.extract_model,
        adjudicate_model=args.adjudicate_model,
        max_tokens_per_deal=args.max_tokens_per_deal,
        re_validate=args.re_validate,
        re_extract=args.re_extract,
        force=args.force,
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


def main(argv: list[str] | None = None) -> int:
    load_dotenv_if_available()
    parser = build_parser()
    args = parser.parse_args(argv)
    cfg = config_from_args(args)
    if not cfg.dry_run and not cfg.api_key:
        parser.error("OPENAI_API_KEY is required unless --dry-run")
    summary = asyncio.run(run_pool(cfg))
    return 1 if summary.failed else 0


if __name__ == "__main__":
    sys.exit(main())
