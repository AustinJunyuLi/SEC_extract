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
from typing import Any, Iterator, Literal

from pipeline import core
from pipeline.llm.audit import (
    AUDIT_LATEST_SCHEMA_VERSION,
    AUDIT_RUN_SCHEMA_VERSION,
    AuditWriter,
    TokenUsage,
    audit_run_dir,
    audit_slug_root,
)
from pipeline.llm.client import ClaudeAgentSDKClient, LLMClient, OpenAIResponsesClient
from pipeline.llm.extract import extract_deal, extractor_contract_version
from pipeline.llm.response_format import DEAL_GRAPH_CLAIM_SCHEMA, schema_hash
from pipeline.llm.retry import RetryConfig
from pipeline.llm.watchdog import WatchdogConfig
from pipeline.deal_graph.orchestrate import finalize_claim_payload


DONE_STATUSES = set(core.TRUSTED_STATUSES)
FINALIZED_STATUSES = set(core.TRUSTED_STATUSES)
REFERENCE_SLUGS = frozenset(core.REFERENCE_SLUGS)
FAILURE_FILTERS = set(core.FAILURE_STATUSES)
VALID_FILTERS = {"pending", "reference", *FAILURE_FILTERS, "all"}
AUDIT_ROOT = core.REPO_ROOT / "output" / "audit"
TARGET_GATE_PROOF = core.REPO_ROOT / "quality_reports" / "stability" / "target-release-proof.json"
DEFAULT_LLM_BACKEND = "claude_agent_sdk"
DEFAULT_OPENAI_MODEL = "gpt-5.5"
DEFAULT_REASONING_EFFORT = "high"
TARGET_GATE_PROOF_SCHEMA_VERSION = "target_gate_proof_v3"
SUPPORTED_BACKENDS = {"claude_agent_sdk", "openai"}
CLAUDE_REASONING_EFFORTS = {None, "none", "low", "medium", "high", "xhigh"}
OPENAI_REASONING_EFFORTS = {None, "none", "minimal", "low", "medium", "high"}


@dataclass
class PoolConfig:
    slugs: tuple[str, ...] = ()
    filter: Literal["pending", "reference", "failed_system", "stale_after_failure", "all"] = "pending"
    workers: int = 1
    llm_backend: Literal["claude_agent_sdk", "openai"] = DEFAULT_LLM_BACKEND
    extract_model: str | None = None
    extract_reasoning_effort: str | None = DEFAULT_REASONING_EFFORT
    re_extract: bool = False
    release_targets: bool = False
    target_gate_proof: Path = TARGET_GATE_PROOF
    commit: bool = False
    dry_run: bool = False
    openai_api_key: str | None = None
    audit_root: Path = AUDIT_ROOT
    watchdog_cfg: WatchdogConfig = field(default_factory=WatchdogConfig)
    retry_cfg: RetryConfig = field(default_factory=RetryConfig)


@dataclass(frozen=True)
class SkipDecision:
    action: Literal["skip", "run", "blocked"]
    reason: str


@dataclass
class DealOutcome:
    slug: str
    status: str
    skipped: bool = False
    error: str | None = None
    flag_count: int | None = None
    notes: str = ""
    output_path: Path | None = None
    audit_path: Path | None = None
    latest_path: Path | None = None
    review_csv_path: Path | None = None
    review_rows_path: Path | None = None


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
            if outcome.status in DONE_STATUSES
        )

    @property
    def skipped(self) -> int:
        return sum(1 for outcome in self.outcomes if outcome.skipped)

    @property
    def failed(self) -> int:
        return sum(1 for outcome in self.outcomes if outcome.status in core.FAILURE_STATUSES)

    @property
    def status_counts(self) -> dict[str, int]:
        return {
            status: sum(1 for outcome in self.outcomes if outcome.status == status)
            for status in (
                "passed_clean",
                "needs_review",
                "high_burden",
                "failed_system",
                "stale_after_failure",
            )
        }


class TargetGateClosedError(RuntimeError):
    pass


@dataclass(frozen=True)
class TargetGateStatus:
    reference_total: int
    reference_verified: int
    missing_verified_references: tuple[str, ...]
    stability_proof_path: Path
    stability_proof_ok: bool
    stability_proof_reason: str

    @property
    def is_open(self) -> bool:
        return (
            self.reference_total == len(REFERENCE_SLUGS)
            and self.reference_verified == len(REFERENCE_SLUGS)
            and not self.missing_verified_references
            and self.stability_proof_ok
        )


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
    if cfg.filter == "pending":
        return [
            slug
            for slug, deal in deals.items()
            if not isinstance(deal, dict) or deal.get("status") in (None, "", "pending")
        ]
    return [slug for slug, deal in deals.items() if deal.get("status") == cfg.filter]


def _is_reference_deal(state: dict[str, Any], slug: str) -> bool:
    return state.get("deals", {}).get(slug, {}).get("is_reference") is True


def _stability_proof_status(path: Path, reference_slugs: set[str]) -> tuple[bool, str]:
    if not path.exists():
        return False, f"missing stability proof file: {path}"
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return False, f"stability proof is unreadable JSON: {type(exc).__name__}: {exc}"
    if not isinstance(payload, dict):
        return False, "stability proof top-level value is not an object"
    if payload.get("schema_version") != TARGET_GATE_PROOF_SCHEMA_VERSION:
        return False, f"stability proof schema_version is not {TARGET_GATE_PROOF_SCHEMA_VERSION}"
    if payload.get("classification") != "STABLE_FOR_REFERENCE_REVIEW":
        return False, f"stability proof classification={payload.get('classification')!r}"
    llm_variation = payload.get("llm_content_variation")
    if not isinstance(llm_variation, dict) or llm_variation.get("allowed") is not True:
        return False, "stability proof must explicitly allow LLM content variation"
    proof_refs = payload.get("reference_slugs")
    if not isinstance(proof_refs, list) or set(proof_refs) != reference_slugs:
        return False, "stability proof reference_slugs do not match the live 9-reference set"
    requested_runs = payload.get("requested_runs")
    if not isinstance(requested_runs, int) or requested_runs < 3:
        return False, "stability proof requested_runs must be at least 3"
    slug_results = payload.get("slug_results")
    if not isinstance(slug_results, list):
        return False, "stability proof slug_results must be a list"
    results_by_slug = {
        item.get("slug"): item
        for item in slug_results
        if isinstance(item, dict) and isinstance(item.get("slug"), str)
    }
    for slug in sorted(reference_slugs):
        result = results_by_slug.get(slug)
        if not isinstance(result, dict):
            return False, f"stability proof missing slug_results entry for {slug}"
        if result.get("classification") != "STABLE_FOR_REFERENCE_REVIEW":
            return False, f"stability proof slug {slug} classification={result.get('classification')!r}"
        if result.get("status") in core.FAILURE_STATUSES:
            return False, f"stability proof slug {slug} has blocking status {result.get('status')!r}"
        if result.get("status") not in core.TRUSTED_STATUSES:
            return False, f"stability proof slug {slug} status is not an eligible trusted outcome"
        eligible = result.get("eligible_archived_runs")
        if not isinstance(eligible, int) or eligible < requested_runs:
            return False, f"stability proof slug {slug} has insufficient eligible_archived_runs"
        selected = result.get("selected_runs")
        if not isinstance(selected, list) or len(selected) < requested_runs:
            return False, f"stability proof slug {slug} selected_runs must contain at least {requested_runs} runs"
        if not all(isinstance(run_id, str) and run_id for run_id in selected):
            return False, f"stability proof slug {slug} selected_runs contains invalid run IDs"
        repo_root = path.resolve().parents[2]
        selected_dirs = result.get("selected_run_dirs")
        if not isinstance(selected_dirs, list) or len(selected_dirs) < requested_runs:
            return False, f"stability proof slug {slug} selected_run_dirs must contain at least {requested_runs} paths"
        for run_dir_rel in selected_dirs:
            if not isinstance(run_dir_rel, str) or not run_dir_rel:
                return False, f"stability proof slug {slug} selected_run_dirs contains invalid path"
            run_dir = repo_root / run_dir_rel
            if not run_dir.is_dir():
                return False, f"stability proof slug {slug} selected run directory is missing: {run_dir}"
    return True, "stability proof accepted"


def target_gate_status(
    state: dict[str, Any],
    proof_path: Path | None = None,
) -> TargetGateStatus:
    deals = state.get("deals", {})
    reference_slugs = {slug for slug, deal in deals.items() if deal.get("is_reference") is True}
    verified_count = 0
    missing_verified: list[str] = []
    for slug in REFERENCE_SLUGS:
        deal = deals.get(slug, {})
        if (
            deal.get("verified") is True
            and isinstance(deal.get("verification_report"), str)
            and isinstance(deal.get("last_verified_run_id"), str)
        ):
            verified_count += 1
        else:
            missing_verified.append(slug)
    missing_expected = REFERENCE_SLUGS - reference_slugs
    if missing_expected:
        missing_verified = sorted(set(missing_verified) | missing_expected)
    else:
        missing_verified.sort()
    proof = proof_path or TARGET_GATE_PROOF
    proof_ok, proof_reason = _stability_proof_status(proof, REFERENCE_SLUGS)
    return TargetGateStatus(
        reference_total=len(reference_slugs),
        reference_verified=verified_count,
        missing_verified_references=tuple(missing_verified),
        stability_proof_path=proof,
        stability_proof_ok=proof_ok,
        stability_proof_reason=proof_reason,
    )


def enforce_target_gate(selected_slugs: list[str], state: dict[str, Any], cfg: PoolConfig) -> None:
    target_slugs = [slug for slug in selected_slugs if not _is_reference_deal(state, slug)]
    if not target_slugs:
        return
    reference_count = len(selected_slugs) - len(target_slugs)
    status = target_gate_status(state, cfg.target_gate_proof)
    blockers: list[str] = []
    if status.missing_verified_references:
        blockers.append(
            "all 9 reference deals must have verified=true reference metadata; missing "
            + ", ".join(status.missing_verified_references)
        )
    if not status.stability_proof_ok:
        blockers.append(status.stability_proof_reason)
    if not cfg.release_targets:
        blockers.append("operator must pass --release-targets")
    if cfg.release_targets and status.is_open:
        return
    target_preview = ", ".join(target_slugs[:10])
    if len(target_slugs) > 10:
        target_preview += f", ... (+{len(target_slugs) - 10} more)"
    raise TargetGateClosedError(
        "target gate closed: "
        f"reference deals selected={reference_count}; target deals selected={len(target_slugs)} "
        f"({target_preview}). "
        "Blocked before audit directories, SDK clients, or model calls. "
        "Conditions: " + "; ".join(blockers)
    )


def _json_file(path: Path, label: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text())
    except FileNotFoundError:
        return None, f"{label} does not exist: {path}"
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"{label} is corrupt or unreadable: {type(exc).__name__}: {exc}"
    if not isinstance(payload, dict):
        return None, f"{label} top-level value is not an object"
    return payload, None


def _is_claim_payload(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    return all(isinstance(value.get(name), list) for name in DEAL_GRAPH_CLAIM_SCHEMA["required"])


def decide_skip(
    slug: str,
    cfg: PoolConfig,
    current_rulebook_version: str,
    state: dict[str, Any] | None = None,
) -> SkipDecision:
    if cfg.re_extract:
        return SkipDecision("run", "fresh SDK extraction requested")
    state = state or _load_progress()
    deal = state.get("deals", {}).get(slug, {})
    status = deal.get("status")
    if status not in core.ALL_RUN_STATUSES and status not in (None, "", "pending"):
        return SkipDecision(
            "blocked",
            f"retired or unknown stored status={status!r}; rerun with --re-extract",
        )
    if status in DONE_STATUSES and deal.get("rulebook_version") == current_rulebook_version:
        return SkipDecision("skip", f"status={status} rulebook unchanged")
    return SkipDecision("run", "pending, failure status, or stale rulebook")


def _iter_calls(audit: AuditWriter) -> Iterator[dict[str, Any]]:
    path = audit.root / "calls.jsonl"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def _calls_summary(audit: AuditWriter) -> tuple[dict[str, str], int, int]:
    hashes: dict[str, str] = {}
    total_attempts = 0
    watchdog_warnings = 0
    for entry in _iter_calls(audit):
        total_attempts += int(entry.get("attempts") or 0)
        watchdog = entry.get("watchdog")
        if isinstance(watchdog, dict):
            watchdog_warnings += int(watchdog.get("warnings") or 0)
        prompt_hash = entry.get("prompt_hash")
        if not isinstance(prompt_hash, str) or not prompt_hash:
            continue
        phase = entry.get("phase")
        if phase == "extract":
            hashes.setdefault("extract", prompt_hash)
    return hashes, total_attempts, watchdog_warnings


def _validate_config(config: PoolConfig) -> None:
    if config.workers < 1:
        raise ValueError("--workers must be >= 1")
    if config.llm_backend not in SUPPORTED_BACKENDS:
        raise ValueError(
            "--llm-backend must be one of "
            + ", ".join(sorted(SUPPORTED_BACKENDS))
            + f"; got {config.llm_backend!r}"
        )
    effort = config.extract_reasoning_effort
    if config.llm_backend == "claude_agent_sdk" and effort not in CLAUDE_REASONING_EFFORTS:
        raise ValueError(f"Claude Agent SDK backend does not support reasoning effort {effort!r}")
    if config.llm_backend == "openai":
        if effort not in OPENAI_REASONING_EFFORTS:
            raise ValueError(f"OpenAI backend does not support reasoning effort {effort!r}")
        if not config.extract_model:
            config.extract_model = DEFAULT_OPENAI_MODEL


def _build_audit_writer(root: Path, slug: str, *, run_id: str) -> AuditWriter:
    return AuditWriter(audit_run_dir(root, slug, run_id), slug=slug, run_id=run_id)


def _prior_status_is_success(slug: str) -> bool:
    try:
        state = _load_progress()
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    status = state.get("deals", {}).get(slug, {}).get("status")
    return status in FINALIZED_STATUSES


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


def _extractor_contract_version_or_unavailable() -> str:
    try:
        return extractor_contract_version()
    except (FileNotFoundError, OSError) as exc:
        return f"unavailable:{type(exc).__name__}"


def _manifest_payload(
    *,
    audit: AuditWriter,
    config: PoolConfig,
    llm_client: LLMClient,
    rulebook_version: str,
    token_usage: TokenUsage,
    started: float,
    outcome: str,
    action: str,
    error: str | None = None,
    stability_eligible: bool,
) -> dict[str, Any]:
    prompt_hashes, total_attempts, watchdog_warnings = _calls_summary(audit)
    return {
        "action": action,
        "rulebook_version": rulebook_version,
        "extractor_contract_version": _extractor_contract_version_or_unavailable(),
        "schema_hash": schema_hash(DEAL_GRAPH_CLAIM_SCHEMA),
        "prompt_hash": prompt_hashes.get("extract"),
        "prompt_hashes": prompt_hashes,
        "llm_backend": config.llm_backend,
        "models": {"extract": config.extract_model},
        "api_endpoint": getattr(llm_client, "endpoint", None),
        "reasoning_efforts": {
            "extract": config.extract_reasoning_effort,
        },
        "total_input_tokens": token_usage.input_used,
        "total_output_tokens": token_usage.output_used,
        "total_reasoning_tokens": token_usage.reasoning_used,
        "total_attempts": total_attempts,
        "total_seconds": time.monotonic() - started,
        "watchdog_warnings": watchdog_warnings,
        "outcome": outcome,
        "stability_eligible": stability_eligible,
        "error": error,
    }


async def process_deal(
    slug: str,
    *,
    config: PoolConfig,
    llm_client: LLMClient,
    rulebook_version: str,
    skip_decision: SkipDecision | None = None,
) -> DealOutcome:
    decision = skip_decision or decide_skip(slug, config, rulebook_version)
    if decision.action == "skip":
        return DealOutcome(slug=slug, status="skipped", skipped=True, notes=decision.reason)
    if decision.action == "blocked":
        return DealOutcome(slug=slug, status="failed_system", error=decision.reason, notes=decision.reason)

    run_id = core._new_run_id()
    audit = _build_audit_writer(config.audit_root, slug, run_id=run_id)
    started = time.monotonic()
    token_usage = TokenUsage()
    try:
        extract_result = await extract_deal(
            slug,
            llm_client=llm_client,
            extract_model=config.extract_model,
            audit=audit,
            token_usage=token_usage,
            rulebook_version=rulebook_version,
            reasoning_effort=config.extract_reasoning_effort,
        )
        raw_extraction = extract_result.raw_extraction
        if raw_extraction is None:
            raise RuntimeError("extractor yielded no parsed_json")

        result = await asyncio.to_thread(
            finalize_claim_payload,
            slug=slug,
            run_id=run_id,
            raw_payload=raw_extraction,
            rulebook_version=rulebook_version,
            audit_run_dir=audit.root,
        )
        audit.write_validation({
            "final_status": result.status,
            "flag_count": result.flag_count,
            "hard_count": sum(1 for flag in result.validation_flags if flag.get("severity") == "hard"),
            "soft_count": sum(1 for flag in result.validation_flags if flag.get("severity") == "soft"),
            "info_count": sum(1 for flag in result.validation_flags if flag.get("severity") == "info"),
            "validation_flags": result.validation_flags,
            "graph_snapshot_path": str(result.snapshot_path),
            "graph_database_path": str(result.database_path),
        })
        audit.write_manifest(_manifest_payload(
            audit=audit,
            config=config,
            llm_client=llm_client,
            rulebook_version=rulebook_version,
            token_usage=token_usage,
            started=started,
            outcome=result.status,
            action=decision.action,
            stability_eligible=True,
        ))
        audit.write_latest(outcome=result.status, stability_eligible=True)
        if config.commit:
            _commit_paths(
                slug,
                [
                    result.output_path,
                    core.PROGRESS_PATH,
                    core.FLAGS_PATH,
                    audit.root,
                    audit.latest_path,
                ],
            )
        return DealOutcome(
            slug=slug,
            status=result.status,
            flag_count=result.flag_count,
            notes=result.notes,
            output_path=result.output_path,
            audit_path=audit.root,
            latest_path=audit.latest_path,
            review_csv_path=result.review_csv_path,
            review_rows_path=result.review_rows_path,
        )
    except Exception as exc:  # noqa: BLE001 - per-deal isolation is the pool contract.
        note = f"{type(exc).__name__}: {exc}"[:500]
        failure_status = "stale_after_failure" if _prior_status_is_success(slug) else "failed_system"
        await asyncio.to_thread(
            core.update_progress,
            slug,
            failure_status,
            0,
            note,
            rulebook_version,
            core._now_iso(),
            run_id,
        )
        audit.write_manifest(_manifest_payload(
            audit=audit,
            config=config,
            llm_client=llm_client,
            rulebook_version=rulebook_version,
            token_usage=token_usage,
            started=started,
            outcome=failure_status,
            action=decision.action,
            error=note,
            stability_eligible=False,
        ))
        audit.write_latest(outcome=failure_status, stability_eligible=False)
        if config.commit:
            commit_paths = [core.PROGRESS_PATH, core.FLAGS_PATH, audit.root, audit.latest_path]
            prior_output_path = core.EXTRACTIONS_DIR / f"{slug}.json"
            if prior_output_path.exists():
                commit_paths.append(prior_output_path)
            _commit_paths(slug, commit_paths)
        return DealOutcome(slug=slug, status=failure_status, error=note, audit_path=audit.root, latest_path=audit.latest_path)


async def run_pool(config: PoolConfig, *, llm_client: LLMClient | None = None) -> PoolSummary:
    _validate_config(config)
    state = _load_progress()
    slugs = resolve_selection(config, state)
    enforce_target_gate(slugs, state, config)
    current = core.rulebook_version()
    plan = [(slug, decide_skip(slug, config, current, state)) for slug in slugs]
    if config.dry_run:
        print("DRY RUN selected deals:")
        target_count = sum(1 for slug in slugs if not _is_reference_deal(state, slug))
        gate = target_gate_status(state, config.target_gate_proof)
        print(
            "Target gate: "
            f"targets_selected={target_count} "
            f"gate_ready={gate.is_open} "
            f"release_requested={config.release_targets} "
            f"proof={gate.stability_proof_reason}"
        )
        outcomes = []
        for slug, decision in plan:
            print(f"  {slug}: {decision.action} ({decision.reason})")
            outcomes.append(DealOutcome(slug=slug, status="dry_run", notes=decision.reason))
        return PoolSummary(outcomes)

    client = llm_client or _build_client(config)
    sem = asyncio.Semaphore(config.workers)

    async def gated(slug: str, decision: SkipDecision) -> DealOutcome:
        async with sem:
            return await process_deal(
                slug,
                config=config,
                llm_client=client,
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
            outcomes.append(DealOutcome(slug=slug, status="failed_system", error=f"{type(item).__name__}: {item}"))
        else:
            outcomes.append(item)
    summary = PoolSummary(outcomes)
    counts = summary.status_counts
    print(
        f"Pool summary: selected={summary.selected} succeeded={summary.succeeded} "
        f"skipped={summary.skipped} failed={summary.failed} "
        f"passed_clean={counts['passed_clean']} needs_review={counts['needs_review']} "
        f"high_burden={counts['high_burden']} failed_system={counts['failed_system']} "
        f"stale_after_failure={counts['stale_after_failure']}"
    )
    for outcome in outcomes:
        if outcome.status in DONE_STATUSES:
            print(
                f"  {outcome.slug}: status={outcome.status} "
                f"review_items={outcome.flag_count or 0} review_csv={outcome.review_csv_path or '-'}"
            )
        elif outcome.status in core.FAILURE_STATUSES:
            print(f"  {outcome.slug}: status={outcome.status} error={outcome.error or outcome.notes}")
    return summary


def _float_env(name: str, default: float) -> float:
    value = os.environ.get(name)
    return default if value is None else float(value)


def _int_env(name: str, default: int) -> int:
    value = os.environ.get(name)
    return default if value is None else int(value)


def _build_client(config: PoolConfig) -> LLMClient:
    if config.llm_backend == "claude_agent_sdk":
        return ClaudeAgentSDKClient(
            watchdog_cfg=config.watchdog_cfg,
            retry_cfg=config.retry_cfg,
        )
    if config.llm_backend == "openai":
        api_key = config.openai_api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for --llm-backend openai unless --dry-run")
        retired_base_url_var = "OPENAI_" + "BASE_URL"
        if os.environ.get(retired_base_url_var):
            raise RuntimeError(f"{retired_base_url_var} is not supported by the direct OpenAI backend")
        return OpenAIResponsesClient(
            api_key=api_key,
            watchdog_cfg=config.watchdog_cfg,
            retry_cfg=config.retry_cfg,
        )
    raise ValueError(f"unsupported llm backend: {config.llm_backend!r}")


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
    parser.add_argument(
        "--llm-backend",
        choices=sorted(SUPPORTED_BACKENDS),
        default=os.environ.get("LLM_BACKEND") or DEFAULT_LLM_BACKEND,
        help=f"Extraction backend (default: {DEFAULT_LLM_BACKEND}).",
    )
    parser.add_argument("--extract-model", default=os.environ.get("EXTRACT_MODEL"))
    parser.add_argument(
        "--extract-reasoning-effort",
        default=os.environ.get("EXTRACT_REASONING_EFFORT") or DEFAULT_REASONING_EFFORT,
        choices=["none", "minimal", "low", "medium", "high", "xhigh"],
        help=f"reasoning.effort for extractor calls (default: {DEFAULT_REASONING_EFFORT})",
    )
    rerun = parser.add_mutually_exclusive_group()
    rerun.add_argument("--re-extract", action="store_true")
    parser.add_argument(
        "--release-targets",
        action="store_true",
        help="Explicitly allow target-deal selection when the reference/stability gate is open.",
    )
    parser.add_argument(
        "--target-gate-proof",
        type=Path,
        default=TARGET_GATE_PROOF,
        help="JSON target-release proof file produced after stable reference runs.",
    )
    parser.add_argument("--commit", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def config_from_args(args: argparse.Namespace) -> PoolConfig:
    slugs = tuple(slug.strip() for slug in (args.slugs or "").split(",") if slug.strip())
    extract_model = args.extract_model
    if args.llm_backend == "openai" and not extract_model:
        extract_model = DEFAULT_OPENAI_MODEL
    cfg = PoolConfig(
        slugs=slugs,
        filter=args.filter,
        workers=args.workers,
        llm_backend=args.llm_backend,
        extract_model=extract_model,
        extract_reasoning_effort=args.extract_reasoning_effort,
        re_extract=args.re_extract,
        release_targets=args.release_targets,
        target_gate_proof=args.target_gate_proof,
        commit=args.commit,
        dry_run=args.dry_run,
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
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
    if not cfg.dry_run and cfg.llm_backend == "openai" and not cfg.openai_api_key:
        parser.error("OPENAI_API_KEY is required for --llm-backend openai unless --dry-run")
    try:
        summary = asyncio.run(run_pool(cfg))
    except TargetGateClosedError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 1 if summary.failed else 0


if __name__ == "__main__":
    sys.exit(main())
