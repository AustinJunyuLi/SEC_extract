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
from pipeline.llm.adjudicate import adjudicate
from pipeline.llm.audit import (
    AUDIT_LATEST_SCHEMA_VERSION,
    AUDIT_RUN_SCHEMA_VERSION,
    RAW_RESPONSE_SCHEMA_VERSION,
    AuditWriter,
    TokenUsage,
    audit_run_dir,
    audit_slug_root,
)
from pipeline.llm.client import LLMClient, OpenAICompatibleClient
from pipeline.llm.contracts import repair_loop_contract_version
from pipeline.llm.extract import extract_deal, extractor_contract_version, run_repair_loop
from pipeline.llm.response_format import SCHEMA_R1, schema_hash
from pipeline.llm.retry import RetryConfig
from pipeline.llm.tools import tools_contract_version
from pipeline.llm.watchdog import WatchdogConfig


DONE_STATUSES = {"passed", "passed_clean", "verified"}
FINALIZED_STATUSES = {"validated", "passed", "passed_clean", "verified"}
REFERENCE_SLUGS = frozenset(core.REFERENCE_SLUGS)
VALID_FILTERS = {"pending", "reference", "failed", "all"}
AUDIT_ROOT = core.REPO_ROOT / "output" / "audit"
TARGET_GATE_PROOF = core.REPO_ROOT / "quality_reports" / "stability" / "target-release-proof.json"
DEFAULT_XHIGH_MAX_WORKERS = 5
DEFAULT_REASONING_EFFORT = "xhigh"
EXTRACT_TOOL_MODE = "none"
REPAIR_STRATEGY = "prompt_then_targeted_tools"
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
    audit_run_id: str | None = None
    release_targets: bool = False
    target_gate_proof: Path = TARGET_GATE_PROOF
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
    latest_path: Path | None = None


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
        return sum(1 for outcome in self.outcomes if outcome.status == "failed")


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
    if payload.get("schema_version") != "target_gate_proof_v1":
        return False, "stability proof schema_version is not target_gate_proof_v1"
    if payload.get("classification") != "STABLE_FOR_REFERENCE_REVIEW":
        return False, f"stability proof classification={payload.get('classification')!r}"
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
        eligible = result.get("eligible_archived_runs")
        if not isinstance(eligible, int) or eligible < requested_runs:
            return False, f"stability proof slug {slug} has insufficient eligible_archived_runs"
        selected = result.get("selected_runs")
        if not isinstance(selected, list) or len(selected) < requested_runs:
            return False, f"stability proof slug {slug} selected_runs must contain at least {requested_runs} runs"
        if not all(isinstance(run_id, str) and run_id for run_id in selected):
            return False, f"stability proof slug {slug} selected_runs contains invalid run IDs"
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
        if deals.get(slug, {}).get("status") == "verified":
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
            "all 9 reference deals must be status=verified; missing "
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


@dataclass(frozen=True)
class CacheCheck:
    parsed_json: dict[str, Any] | None
    reason: str
    raw_payload: dict[str, Any] | None = None
    source_run_id: str | None = None
    raw_response_path: Path | None = None

    @property
    def valid(self) -> bool:
        return self.parsed_json is not None


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


def _current_contract_values(current_rulebook_version: str) -> dict[str, str]:
    return {
        "rulebook_version": current_rulebook_version,
        "extractor_contract_version": extractor_contract_version(),
        "tools_contract_version": tools_contract_version(),
        "repair_loop_contract_version": repair_loop_contract_version(),
        "extract_tool_mode": EXTRACT_TOOL_MODE,
        "repair_strategy": REPAIR_STRATEGY,
    }


def _contract_mismatch_reason(
    payload: dict[str, Any],
    *,
    label: str,
    current_contracts: dict[str, str],
) -> str | None:
    for key, expected in current_contracts.items():
        if payload.get(key) != expected:
            return (
                f"{label} {key} does not match current contract; "
                "use --re-extract for a fresh SDK call"
            )
    return None


def _cache_source_from_latest(
    cfg: PoolConfig,
    slug: str,
    current_contracts: dict[str, str],
) -> tuple[str | None, Path | None, str | None]:
    latest_path = audit_slug_root(cfg.audit_root, slug) / "latest.json"
    latest, error = _json_file(latest_path, "latest.json")
    if error:
        legacy_raw = audit_slug_root(cfg.audit_root, slug) / "raw_response.json"
        legacy_hint = "; legacy loose audit layout is not accepted" if legacy_raw.exists() else ""
        return None, None, error + legacy_hint
    if latest.get("schema_version") != AUDIT_LATEST_SCHEMA_VERSION:
        return None, None, "latest.json schema_version is not audit_v2"
    if latest.get("slug") != slug:
        return None, None, f"latest.json slug={latest.get('slug')!r} does not match {slug!r}"
    if latest.get("cache_eligible") is not True:
        return None, None, "latest archived run is not cache-eligible"
    run_id = latest.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        return None, None, "latest.json run_id is missing"
    manifest_run_id, _manifest_raw_path, manifest_error = _cache_source_from_run_id(
        cfg,
        slug,
        run_id,
        current_contracts=current_contracts,
    )
    if manifest_error or manifest_run_id != run_id:
        return None, None, manifest_error or "latest archived manifest does not match latest.json run_id"
    raw_rel = latest.get("raw_response_path")
    if raw_rel != f"runs/{run_id}/raw_response.json":
        return None, None, "latest.json raw_response_path must point under runs/{run_id}/raw_response.json"
    return run_id, audit_slug_root(cfg.audit_root, slug) / raw_rel, None


def _cache_source_from_run_id(
    cfg: PoolConfig,
    slug: str,
    run_id: str,
    *,
    current_contracts: dict[str, str] | None = None,
) -> tuple[str | None, Path | None, str | None]:
    run_dir = audit_run_dir(cfg.audit_root, slug, run_id)
    manifest, error = _json_file(run_dir / "manifest.json", "archived manifest.json")
    if error:
        return None, None, error
    if manifest.get("schema_version") != AUDIT_RUN_SCHEMA_VERSION:
        return None, None, "archived manifest.json schema_version is not audit_run_v2"
    if manifest.get("slug") != slug or manifest.get("run_id") != run_id:
        return None, None, "archived manifest.json slug/run_id does not match requested cache run"
    if manifest.get("cache_eligible") is not True:
        return None, None, "requested archived run is not cache-eligible"
    if current_contracts is not None:
        mismatch = _contract_mismatch_reason(
            manifest,
            label="archived manifest.json",
            current_contracts=current_contracts,
        )
        if mismatch:
            return None, None, mismatch
    return run_id, run_dir / "raw_response.json", None


def _check_cached_raw_response(slug: str, cfg: PoolConfig, current_rulebook_version: str) -> CacheCheck:
    current_contracts = _current_contract_values(current_rulebook_version)
    if cfg.audit_run_id:
        source_run_id, path, source_error = _cache_source_from_run_id(
            cfg,
            slug,
            cfg.audit_run_id,
            current_contracts=current_contracts,
        )
    else:
        source_run_id, path, source_error = _cache_source_from_latest(
            cfg,
            slug,
            current_contracts,
        )
    if source_error or path is None or source_run_id is None:
        return CacheCheck(None, source_error or "no cache source selected")
    payload, error = _json_file(path, "cached raw_response.json")
    if error:
        return CacheCheck(None, error)
    assert payload is not None
    if payload.get("schema_version") != RAW_RESPONSE_SCHEMA_VERSION:
        return CacheCheck(None, "cached raw_response.json schema_version is not raw_response_v2")
    if payload.get("run_id") != source_run_id:
        return CacheCheck(None, "cached raw_response.json run_id does not match selected audit run")
    if payload.get("slug") != slug:
        return CacheCheck(None, f"cached raw_response.json slug={payload.get('slug')!r} does not match {slug!r}")
    if payload.get("rulebook_version") != current_contracts["rulebook_version"]:
        return CacheCheck(
            None,
            "cached raw_response.json rulebook_version does not match current rulebook; "
            "use --re-extract for a fresh SDK call",
        )
    if payload.get("extractor_contract_version") != current_contracts["extractor_contract_version"]:
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
    return CacheCheck(parsed, "valid archived raw_response.json", payload, source_run_id, path)


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
        elif phase == "adjudicate":
            hashes.setdefault(f"adjudicate_{entry.get('flag_index')}", prompt_hash)
    return hashes, total_attempts, watchdog_warnings


def _xhigh_max_workers() -> int:
    return int(os.environ.get("LINKFLOW_XHIGH_MAX_WORKERS", str(DEFAULT_XHIGH_MAX_WORKERS)))


def _validate_config(config: PoolConfig) -> None:
    if config.workers < 1:
        raise ValueError("--workers must be >= 1")
    if config.audit_run_id and not config.re_validate:
        raise ValueError("--audit-run-id is only valid with --re-validate")
    if "xhigh" in {config.extract_reasoning_effort, config.adjudicate_reasoning_effort}:
        cap = _xhigh_max_workers()
        if config.workers > cap:
            raise ValueError(
                f"Linkflow xhigh reasoning is capped at workers <= {cap}; "
                f"got workers={config.workers}"
            )


def _build_audit_writer(root: Path, slug: str, *, run_id: str) -> AuditWriter:
    return AuditWriter(audit_run_dir(root, slug, run_id), slug=slug, run_id=run_id)


def _prior_status_is_success(slug: str) -> bool:
    try:
        state = _load_progress()
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    return state.get("deals", {}).get(slug, {}).get("status") in FINALIZED_STATUSES


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


def _validation_payload(
    *,
    status: str,
    flag_count: int,
    final_output: dict[str, Any] | None,
    validation: core.ValidatorResult | None,
    promotion_log: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    counts = core.count_flags(final_output or {"deal": {"deal_flags": []}, "events": []})
    return {
        "final_status": status,
        "flag_count": flag_count,
        "row_flag_count": len(validation.row_flags) if validation else 0,
        "deal_flag_count": len(validation.deal_flags) if validation else 0,
        "hard_count": counts["hard"],
        "soft_count": counts["soft"],
        "info_count": counts["info"],
        "promotion_log_count": len(promotion_log or []),
    }


def _extractor_contract_version_or_unavailable() -> str:
    try:
        return extractor_contract_version()
    except (FileNotFoundError, OSError) as exc:
        return f"unavailable:{type(exc).__name__}"


def _tools_contract_version_or_unavailable() -> str:
    try:
        return tools_contract_version()
    except (FileNotFoundError, OSError) as exc:
        return f"unavailable:{type(exc).__name__}"


def _repair_loop_contract_version_or_unavailable() -> str:
    try:
        return repair_loop_contract_version()
    except (FileNotFoundError, OSError) as exc:
        return f"unavailable:{type(exc).__name__}"


def _jsonl_count(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text().splitlines() if line.strip())


def _manifest_payload(
    *,
    audit: AuditWriter,
    config: PoolConfig,
    llm_client: LLMClient,
    rulebook_version: str,
    token_usage: TokenUsage,
    started: float,
    outcome: str,
    cache_used: bool,
    cache_eligible: bool,
    action: str,
    repair_turns_used: int,
    repair_loop_outcome: str,
    error: str | None = None,
    source_audit_run_id: str | None = None,
) -> dict[str, Any]:
    prompt_hashes, total_attempts, watchdog_warnings = _calls_summary(audit)
    return {
        "action": action,
        "rulebook_version": rulebook_version,
        "extractor_contract_version": _extractor_contract_version_or_unavailable(),
        "tools_contract_version": _tools_contract_version_or_unavailable(),
        "repair_loop_contract_version": _repair_loop_contract_version_or_unavailable(),
        "schema_hash": schema_hash(SCHEMA_R1),
        "prompt_hash": prompt_hashes.get("extract"),
        "prompt_hashes": prompt_hashes,
        "models": {"extract": config.extract_model, "adjudicate": config.adjudicate_model},
        "api_endpoint": getattr(llm_client, "endpoint", None),
        "extract_tool_mode": EXTRACT_TOOL_MODE,
        "repair_strategy": REPAIR_STRATEGY,
        "reasoning_efforts": {
            "extract": config.extract_reasoning_effort,
            "adjudicate": config.adjudicate_reasoning_effort,
        },
        "total_input_tokens": token_usage.input_used,
        "total_output_tokens": token_usage.output_used,
        "total_reasoning_tokens": token_usage.reasoning_used,
        "total_attempts": total_attempts,
        "total_seconds": time.monotonic() - started,
        "watchdog_warnings": watchdog_warnings,
        "repair_turns_used": repair_turns_used,
        "repair_loop_outcome": repair_loop_outcome,
        "tool_calls_count": _jsonl_count(audit.root / "tool_calls.jsonl"),
        "outcome": outcome,
        "cache_used": cache_used,
        "cache_eligible": cache_eligible,
        "source_audit_run_id": source_audit_run_id,
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
        return DealOutcome(slug=slug, status="failed", error=decision.reason, notes=decision.reason)

    run_id = core._new_run_id()
    audit = _build_audit_writer(config.audit_root, slug, run_id=run_id)
    started = time.monotonic()
    token_usage = TokenUsage()
    cached = False
    source_audit_run_id: str | None = None
    repair_outcome = "not_started"
    repair_turns_used = 0
    try:
        if decision.action == "re_validate":
            cache_check = _check_cached_raw_response(slug, config, rulebook_version)
            if not cache_check.valid or cache_check.raw_payload is None:
                raise RuntimeError("cached raw_response.json disappeared or became stale")
            audit.write_cached_raw_response(
                payload=cache_check.raw_payload,
                source_run_id=cache_check.source_run_id or "unknown",
            )
            raw_extraction = cache_check.parsed_json
            source_audit_run_id = cache_check.source_run_id
            cached = True
        else:
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
            raise RuntimeError("raw extraction cache yielded no parsed_json")

        filing = await asyncio.to_thread(core.load_filing, slug)
        prepared, filing, promotion_log = await asyncio.to_thread(
            core.prepare_for_validate,
            slug,
            raw_extraction,
            filing,
        )
        validation = await asyncio.to_thread(core.validate, prepared, filing)
        repair_outcome = "clean"
        repair_turns_used = 0
        if any(
            flag.get("severity") == "hard"
            for flag in [*validation.row_flags, *validation.deal_flags]
        ):
            (
                prepared,
                validation,
                promotion_log,
                repair_outcome,
                repair_turns_used,
            ) = await run_repair_loop(
                slug=slug,
                initial_draft=prepared,
                filing=filing,
                validation=validation,
                llm_client=llm_client,
                extract_model=config.extract_model,
                audit=audit,
                token_usage=token_usage,
                reasoning_effort=config.extract_reasoning_effort,
            )
            if repair_outcome == "exhausted":
                validation.deal_flags.append({
                    "code": "repair_loop_exhausted",
                    "severity": "hard",
                    "reason": "Hard validator flags remained after 2 repair turns.",
                    "deal_level": True,
                })
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
                reasoning_effort=config.adjudicate_reasoning_effort,
            )
        result = await asyncio.to_thread(
            core.finalize_prepared,
            slug,
            prepared,
            filing,
            validation,
            promotion_log,
            run_id=run_id,
        )
        final_output = json.loads(result.output_path.read_text())
        audit.write_validation(
            _validation_payload(
                status=result.status,
                flag_count=result.flag_count,
                final_output=final_output,
                validation=validation,
                promotion_log=promotion_log,
            )
        )
        audit.write_final_output(final_output)
        audit.write_manifest(_manifest_payload(
            audit=audit,
            config=config,
            llm_client=llm_client,
            rulebook_version=rulebook_version,
            token_usage=token_usage,
            started=started,
            outcome=result.status,
            cache_used=cached,
            cache_eligible=True,
            action=decision.action,
            repair_turns_used=repair_turns_used,
            repair_loop_outcome=repair_outcome,
            source_audit_run_id=source_audit_run_id,
        ))
        audit.write_latest(outcome=result.status, cache_eligible=True)
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
            cached=cached,
            flag_count=result.flag_count,
            notes=result.notes,
            output_path=result.output_path,
            audit_path=audit.root,
            latest_path=audit.latest_path,
        )
    except Exception as exc:  # noqa: BLE001 - per-deal isolation is the pool contract.
        note = f"{type(exc).__name__}: {exc}"[:500]
        if not _prior_status_is_success(slug):
            await asyncio.to_thread(
                core.update_progress,
                slug,
                "failed",
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
            outcome="failed",
            cache_used=cached,
            cache_eligible=False,
            action=decision.action,
            repair_turns_used=repair_turns_used,
            repair_loop_outcome=repair_outcome,
            error=note,
            source_audit_run_id=source_audit_run_id,
        ))
        audit.write_latest(outcome="failed", cache_eligible=False)
        if config.commit:
            commit_paths = [core.PROGRESS_PATH, core.FLAGS_PATH, audit.root, audit.latest_path]
            prior_output_path = core.EXTRACTIONS_DIR / f"{slug}.json"
            if prior_output_path.exists():
                commit_paths.append(prior_output_path)
            _commit_paths(slug, commit_paths)
        return DealOutcome(slug=slug, status="failed", cached=cached, error=note, audit_path=audit.root, latest_path=audit.latest_path)


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
    rerun.add_argument("--re-validate", action="store_true", help="Reuse only a cache-eligible archived audit v2 run.")
    rerun.add_argument("--re-extract", action="store_true")
    parser.add_argument("--audit-run-id", help="Archived audit run ID to reuse with --re-validate.")
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
        audit_run_id=args.audit_run_id,
        release_targets=args.release_targets,
        target_gate_proof=args.target_gate_proof,
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
    try:
        summary = asyncio.run(run_pool(cfg))
    except TargetGateClosedError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 1 if summary.failed else 0


if __name__ == "__main__":
    sys.exit(main())
