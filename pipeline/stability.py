"""Read-only stability harness for immutable audit v3 archives."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from pipeline import core
from pipeline.core import REFERENCE_SLUGS
from pipeline.llm.audit import (
    AUDIT_RUN_SCHEMA_VERSION,
    LEGACY_AUDIT_NAMES,
    RAW_RESPONSE_SCHEMA_VERSION,
)
from pipeline.llm.response_format import DEAL_GRAPH_CLAIM_SCHEMA


ELIGIBLE_OUTCOMES = frozenset({"validated", "passed", "passed_clean"})
STRUCTURAL_INFO_CODES = frozenset({
    "date_phrase_unmapped",
    "rough_date_mismatch",
    "source_quote_page_mismatch",
    "source_quote_not_substring",
    "source_quote_missing",
})
LIFECYCLE_NOTES = ("NDA", "Bid", "Drop", "DropSilent", "Executed")
FINAL_CLASSIFICATIONS = (
    "STABLE_FOR_REFERENCE_REVIEW",
    "UNSTABLE_RULE_OR_VALIDATOR_FIX_NEEDED",
    "UNSTABLE_ARCHITECTURE_ESCALATION_CANDIDATE",
    "INSUFFICIENT_ARCHIVED_RUNS",
)
RETIRED_PROVIDER_FALLBACK_FIELD = "json_" + "schema_used"


class StabilityError(RuntimeError):
    """Raised for strict-mode archive contract failures."""


@dataclass(frozen=True)
class ArchivedRun:
    slug: str
    run_id: str
    run_dir: Path
    manifest: dict[str, Any]
    final_output: dict[str, Any]
    validation: dict[str, Any]


@dataclass(frozen=True)
class RunMetrics:
    slug: str
    run_id: str
    finished_at: str
    outcome: str
    model: str
    reasoning_effort: str
    provider: str
    prompt_hash: str
    schema_hash: str
    rulebook_hash: str
    extractor_contract_version: str
    row_count: int
    row_fingerprints: tuple[str, ...]
    bid_note_counts: tuple[tuple[str, int], ...]
    flag_counts: tuple[tuple[tuple[str, str], int], ...]
    hard_flag_identities: tuple[str, ...]
    auction_value: str
    lifecycle_counts: tuple[tuple[str, int], ...]
    anonymous_placeholder_count: int
    cohort_like_placeholder_count: int
    final_round_metrics: tuple[tuple[str, int], ...]
    date_diagnostics: tuple[tuple[str, int], ...]
    bid_value_representation: tuple[tuple[str, int], ...]
    quote_diagnostics: tuple[tuple[str, int], ...]

    @property
    def config_identity(self) -> tuple[str, str, str, str, str, str, str]:
        return (
            self.model,
            self.reasoning_effort,
            self.provider,
            self.prompt_hash,
            self.schema_hash,
            self.rulebook_hash,
            self.extractor_contract_version,
        )

    @property
    def substantive_identity(self) -> tuple[Any, ...]:
        return (
            self.row_count,
            self.row_fingerprints,
            self.bid_note_counts,
            self.hard_flag_identities,
            self.auction_value,
            self.lifecycle_counts,
            self.anonymous_placeholder_count,
            self.cohort_like_placeholder_count,
            self.final_round_metrics,
            self.date_diagnostics,
            self.bid_value_representation,
            self.quote_diagnostics,
            _structural_flag_counts(self.flag_counts),
        )


@dataclass(frozen=True)
class SlugAnalysis:
    slug: str
    selected_runs: tuple[RunMetrics, ...] = ()
    eligible_run_count: int = 0
    required_run_count: int = 3
    classification: str = "INSUFFICIENT_ARCHIVED_RUNS"
    reasons: tuple[str, ...] = ()
    info_only_flag_volume_changed: bool = False


@dataclass(frozen=True)
class StabilityAnalysis:
    slugs: tuple[str, ...]
    requested_runs: int
    slug_results: tuple[SlugAnalysis, ...]
    classification: str
    reasons: tuple[str, ...]




def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise StabilityError(f"cannot read JSON archive artifact {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise StabilityError(f"archive artifact is not a JSON object: {path}")
    return payload


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value))
    return re.sub(r"\s+", " ", text).strip().lower()


def _quote_text(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(str(item) for item in value if item is not None)
    return "" if value is None else str(value)


def _page_text(value: Any) -> str:
    if isinstance(value, list):
        return ",".join(str(item) for item in value)
    return "" if value is None else str(value)


def _number_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (int, float)):
        return f"{value:g}"
    return str(value)


def _auction_repr(deal: dict[str, Any]) -> str:
    if "auction" not in deal:
        return "missing"
    value = deal["auction"]
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return f"non_bool:{value!r}"


def _row_fingerprint(slug: str, row: dict[str, Any]) -> str:
    quote_prefix = _normalize_text(_quote_text(row.get("source_quote")))[:180]
    parts = [
        slug,
        _normalize_text(row.get("process_phase")),
        _normalize_text(row.get("bid_note")),
        _normalize_text(row.get("bid_date_precise")),
        _normalize_text(row.get("bid_date_rough")),
        _normalize_text(row.get("bidder_alias") or row.get("bidder_name")),
        _normalize_text(row.get("bidder_type")),
        _number_text(row.get("bid_value_lower")),
        _number_text(row.get("bid_value_upper")),
        _page_text(row.get("source_page")),
        quote_prefix,
    ]
    return " | ".join(parts)


def _stable_items(counter: Counter) -> tuple[tuple[str, int], ...]:
    return tuple(sorted((str(key), int(value)) for key, value in counter.items()))


def _stable_nested_items(counter: Counter) -> tuple[tuple[tuple[str, str], int], ...]:
    return tuple(sorted(((str(sev), str(code)), int(value)) for (sev, code), value in counter.items()))


def _manifest_value(manifest: dict[str, Any], key: str) -> str:
    value = manifest.get(key)
    return "" if value in (None, "") else str(value)


def _manifest_nested_value(manifest: dict[str, Any], key: str, subkey: str) -> str:
    value = manifest.get(key)
    if not isinstance(value, dict):
        return ""
    nested = value.get(subkey)
    return "" if nested in (None, "") else str(nested)


def _is_claim_payload(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    return all(isinstance(value.get(name), list) for name in DEAL_GRAPH_CLAIM_SCHEMA["required"])


def _require_manifest_value(manifest: dict[str, Any], path: tuple[str, ...], manifest_path: Path) -> None:
    value: Any = manifest
    for part in path:
        if not isinstance(value, dict) or part not in value:
            dotted = ".".join(path)
            raise StabilityError(f"archived run manifest missing required {dotted}: {manifest_path}")
        value = value[part]
    if value in (None, ""):
        dotted = ".".join(path)
        raise StabilityError(f"archived run manifest has empty required {dotted}: {manifest_path}")


def _validate_manifest(manifest: dict[str, Any], manifest_path: Path) -> None:
    if manifest.get("schema_version") != AUDIT_RUN_SCHEMA_VERSION:
        raise StabilityError(f"archived run manifest schema_version is not {AUDIT_RUN_SCHEMA_VERSION}: {manifest_path}")
    required_paths = (
        ("slug",),
        ("run_id",),
        ("outcome",),
        ("cache_eligible",),
        ("cache_used",),
        ("finished_at",),
        ("models", "extract"),
        ("reasoning_efforts", "extract"),
        ("api_endpoint",),
        ("prompt_hash",),
        ("schema_hash",),
        ("rulebook_version",),
        ("extractor_contract_version",),
    )
    for path in required_paths:
        _require_manifest_value(manifest, path, manifest_path)
    if RETIRED_PROVIDER_FALLBACK_FIELD in manifest:
        raise StabilityError(
            f"archived run manifest contains a retired structured-output fallback field: {manifest_path}"
        )
    retired = (
        "tools_contract_version",
        "repair_loop_contract_version",
        "obligation_contract_version",
        "repair_turns_used",
        "repair_loop_outcome",
        "tool_calls_count",
    )
    for key in retired:
        if key in manifest:
            raise StabilityError(f"archived run manifest contains retired {key}: {manifest_path}")
    for nested_key in ("models", "reasoning_efforts"):
        nested = manifest.get(nested_key)
        if isinstance(nested, dict) and "adjudicate" in nested:
            raise StabilityError(
                f"archived run manifest {nested_key} contains retired adjudicate entry: {manifest_path}"
            )


def _all_flags(final_output: dict[str, Any], validation: dict[str, Any]) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    for key in ("row_flags", "deal_flags", "flags"):
        value = validation.get(key)
        if isinstance(value, list):
            flags.extend(flag for flag in value if isinstance(flag, dict))
    deal = final_output.get("deal")
    if isinstance(deal, dict):
        deal_flags = deal.get("deal_flags")
        if isinstance(deal_flags, list):
            flags.extend(flag for flag in deal_flags if isinstance(flag, dict))
    events = final_output.get("events")
    if isinstance(events, list):
        for idx, row in enumerate(events):
            if not isinstance(row, dict):
                continue
            for flag in row.get("flags") or []:
                if isinstance(flag, dict):
                    enriched = {"row_index": idx, **flag}
                    flags.append(enriched)
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for flag in flags:
        key = json.dumps(flag, sort_keys=True, default=str)
        if key not in seen:
            seen.add(key)
            unique.append(flag)
    return unique


def _flag_counts(flags: Iterable[dict[str, Any]]) -> Counter:
    counter: Counter = Counter()
    for flag in flags:
        severity = str(flag.get("severity") or "unknown")
        code = str(flag.get("code") or "unknown")
        counter[(severity, code)] += 1
    return counter


def _hard_flag_identities(flags: Iterable[dict[str, Any]]) -> tuple[str, ...]:
    identities = []
    for flag in flags:
        if flag.get("severity") != "hard":
            continue
        code = str(flag.get("code") or "unknown")
        if "row_index" in flag:
            location = f"row:{flag.get('row_index')}"
        else:
            location = "deal"
        identities.append(f"{location}:{code}")
    return tuple(sorted(identities))


def _structural_flag_counts(flag_counts: tuple[tuple[tuple[str, str], int], ...]) -> tuple[tuple[tuple[str, str], int], ...]:
    kept = []
    for (severity, code), count in flag_counts:
        if severity in {"hard", "soft"} or code in STRUCTURAL_INFO_CODES:
            kept.append(((severity, code), count))
    return tuple(kept)


def _info_flag_counts(flag_counts: tuple[tuple[tuple[str, str], int], ...]) -> tuple[tuple[tuple[str, str], int], ...]:
    return tuple(((sev_code, count)) for sev_code, count in flag_counts if sev_code[0] == "info")


def _is_anonymous_alias(alias: str) -> bool:
    normalized = _normalize_text(alias)
    if not normalized:
        return False
    patterns = (
        r"^party [a-z0-9]+$",
        r"^bidder [a-z0-9]+$",
        r"^financial sponsor [a-z0-9]+$",
        r"^strategic party [a-z0-9]+$",
        r"^unnamed\b",
        r"^anonymous\b",
    )
    return any(re.search(pattern, normalized) for pattern in patterns)


def _is_cohort_like_alias(alias: str) -> bool:
    normalized = _normalize_text(alias)
    return bool(re.search(r"\b(?:party|bidder|sponsor|strategic party|financial sponsor)\s+[a-z0-9]+\b", normalized))


def _date_diagnostics(events: list[dict[str, Any]], flags: list[dict[str, Any]]) -> Counter:
    counter: Counter = Counter()
    for row in events:
        precise = row.get("bid_date_precise")
        rough = row.get("bid_date_rough")
        if precise not in (None, ""):
            counter["precise"] += 1
        elif rough not in (None, ""):
            counter["rough_only"] += 1
        else:
            counter["null"] += 1
    for flag in flags:
        code = str(flag.get("code") or "")
        if code == "date_phrase_unmapped":
            counter["accepted_date_inference_flags"] += 1
        if "rough" in code and "date" in code:
            counter["rough_date_mismatch_flags"] += 1
    return counter


def _bid_value_representation(events: list[dict[str, Any]]) -> Counter:
    counter: Counter = Counter()
    for row in events:
        lower = row.get("bid_value_lower")
        upper = row.get("bid_value_upper")
        bid_type = row.get("bid_type")
        lower_state = "lower" if lower not in (None, "") else "no_lower"
        upper_state = "upper" if upper not in (None, "") else "no_upper"
        type_state = f"type:{bid_type}" if bid_type not in (None, "") else "type:null"
        counter[f"{lower_state}/{upper_state}/{type_state}"] += 1
    return counter


def _quote_diagnostics(events: list[dict[str, Any]], flags: list[dict[str, Any]]) -> Counter:
    counter: Counter = Counter()
    for row in events:
        quote = row.get("source_quote")
        page = row.get("source_page")
        quote_values = quote if isinstance(quote, list) else [quote]
        if quote in (None, "") or any(item in (None, "") for item in quote_values):
            counter["missing_quote"] += 1
        if any(len(str(item)) > 1500 for item in quote_values if item is not None):
            counter["overlength_quote"] += 1
        if page in (None, ""):
            counter["missing_page"] += 1
    for flag in flags:
        code = str(flag.get("code") or "")
        if "page" in code and "quote" in code:
            counter["page_mismatch"] += 1
        if "substring" in code or "verbatim" in code:
            counter["substring_failure"] += 1
    return counter


def _final_round_metrics(events: list[dict[str, Any]], flags: list[dict[str, Any]]) -> Counter:
    counter: Counter = Counter()
    dates_with_bids = {
        row.get("bid_date_precise")
        for row in events
        if row.get("bid_note") == "Bid" and row.get("bid_date_precise")
    }
    for row in events:
        if row.get("bid_note") != "Final Round":
            continue
        if row.get("final_round_announcement") is True:
            counter["announcement_rows"] += 1
        else:
            counter["non_announcement_rows"] += 1
        if row.get("bid_date_precise") in dates_with_bids:
            counter["same_day_bid_milestone_pairs"] += 1
    for flag in flags:
        code = str(flag.get("code") or "")
        if (
            code.startswith("P-G2")
            or code.startswith("P-G3")
            or code in {
                "P-G2",
                "P-G3",
                "bid_type_unsupported",
                "bid_range_inverted",
                "bid_range_must_be_informal",
                "final_round_missing_non_announcement_pair",
            }
        ):
            counter[f"{code}_flags"] += 1
    return counter


def metrics_for_run(archived: ArchivedRun) -> RunMetrics:
    final_output = archived.final_output
    events_value = final_output.get("events")
    events = [row for row in events_value if isinstance(row, dict)] if isinstance(events_value, list) else []
    flags = _all_flags(final_output, archived.validation)
    bid_notes = Counter(str(row.get("bid_note") or "null") for row in events)
    lifecycle = Counter({note: 0 for note in LIFECYCLE_NOTES})
    lifecycle.update(str(row.get("bid_note") or "null") for row in events if row.get("bid_note") in LIFECYCLE_NOTES)
    aliases = [str(row.get("bidder_alias") or row.get("bidder_name") or "") for row in events]
    deal = final_output.get("deal") if isinstance(final_output.get("deal"), dict) else {}
    flag_count_values = _stable_nested_items(_flag_counts(flags))
    return RunMetrics(
        slug=archived.slug,
        run_id=archived.run_id,
        finished_at=_manifest_value(archived.manifest, "finished_at"),
        outcome=_manifest_value(archived.manifest, "outcome"),
        model=_manifest_nested_value(archived.manifest, "models", "extract"),
        reasoning_effort=_manifest_nested_value(archived.manifest, "reasoning_efforts", "extract"),
        provider=_manifest_value(archived.manifest, "api_endpoint"),
        prompt_hash=_manifest_value(archived.manifest, "prompt_hash"),
        schema_hash=_manifest_value(archived.manifest, "schema_hash"),
        rulebook_hash=_manifest_value(archived.manifest, "rulebook_version"),
        extractor_contract_version=_manifest_value(archived.manifest, "extractor_contract_version"),
        row_count=len(events),
        row_fingerprints=tuple(sorted(_row_fingerprint(archived.slug, row) for row in events)),
        bid_note_counts=_stable_items(bid_notes),
        flag_counts=flag_count_values,
        hard_flag_identities=_hard_flag_identities(flags),
        auction_value=_auction_repr(deal),
        lifecycle_counts=_stable_items(lifecycle),
        anonymous_placeholder_count=sum(1 for alias in aliases if _is_anonymous_alias(alias)),
        cohort_like_placeholder_count=sum(1 for alias in aliases if _is_cohort_like_alias(alias)),
        final_round_metrics=_stable_items(_final_round_metrics(events, flags)),
        date_diagnostics=_stable_items(_date_diagnostics(events, flags)),
        bid_value_representation=_stable_items(_bid_value_representation(events)),
        quote_diagnostics=_stable_items(_quote_diagnostics(events, flags)),
    )


def _reject_legacy_singletons(slug_root: Path) -> None:
    for name in sorted(LEGACY_AUDIT_NAMES):
        path = slug_root / name
        if path.exists():
            raise StabilityError(f"legacy singleton audit file rejected: {path}")


def _validate_run_artifacts(run_dir: Path) -> None:
    required = ("manifest.json", "final_output.json", "validation.json", "raw_response.json", "calls.jsonl", "prompts")
    missing = [name for name in required if not (run_dir / name).exists()]
    if missing:
        raise StabilityError(f"archived run missing required artifact(s) {', '.join(missing)}: {run_dir}")
    if not (run_dir / "prompts").is_dir():
        raise StabilityError(f"archived run prompts artifact is not a directory: {run_dir / 'prompts'}")


def load_archived_runs(repo_root: Path, slug: str) -> list[ArchivedRun]:
    slug_root = repo_root / "output" / "audit" / slug
    if slug_root.exists():
        _reject_legacy_singletons(slug_root)
    runs_root = slug_root / "runs"
    if not runs_root.exists():
        return []
    archived: list[ArchivedRun] = []
    for run_dir in sorted(path for path in runs_root.iterdir() if path.is_dir()):
        manifest_path = run_dir / "manifest.json"
        if not manifest_path.exists():
            raise StabilityError(f"archived run missing manifest.json: {run_dir}")
        manifest = _read_json(manifest_path)
        if manifest.get("schema_version") != AUDIT_RUN_SCHEMA_VERSION:
            raise StabilityError(f"archived run manifest schema_version is not {AUDIT_RUN_SCHEMA_VERSION}: {manifest_path}")
        for required_path in (("slug",), ("run_id",), ("outcome",), ("cache_eligible",)):
            _require_manifest_value(manifest, required_path, manifest_path)
        if (
            manifest.get("outcome") not in ELIGIBLE_OUTCOMES
            or manifest.get("cache_eligible") is not True
            or manifest.get("cache_used") is True
        ):
            continue
        _validate_manifest(manifest, manifest_path)
        _validate_run_artifacts(run_dir)
        raw_response = _read_json(run_dir / "raw_response.json")
        if raw_response.get("schema_version") != RAW_RESPONSE_SCHEMA_VERSION:
            raise StabilityError(
                f"archived run raw_response schema_version is not {RAW_RESPONSE_SCHEMA_VERSION}: {run_dir / 'raw_response.json'}"
            )
        if not _is_claim_payload(raw_response.get("parsed_json")):
            raise StabilityError(
                f"archived run raw_response parsed_json is not the live claim-only provider payload: {run_dir / 'raw_response.json'}"
            )
        final_output = _read_json(run_dir / "final_output.json")
        validation = _read_json(run_dir / "validation.json")
        run_id = str(manifest.get("run_id") or run_dir.name)
        archived.append(ArchivedRun(slug=slug, run_id=run_id, run_dir=run_dir, manifest=manifest, final_output=final_output, validation=validation))
    archived.sort(key=lambda run: (_manifest_value(run.manifest, "finished_at"), run.run_id))
    return archived


def select_latest_runs(runs: list[ArchivedRun], count: int) -> tuple[ArchivedRun, ...]:
    return tuple(runs[-count:])


def _classify_slug(slug: str, runs: tuple[RunMetrics, ...], eligible_count: int, required: int) -> SlugAnalysis:
    if eligible_count < required:
        return SlugAnalysis(
            slug=slug,
            eligible_run_count=eligible_count,
            required_run_count=required,
            classification="INSUFFICIENT_ARCHIVED_RUNS",
            reasons=(f"{slug} has {eligible_count} eligible archived runs; need {required}",),
        )
    reasons: list[str] = []
    config_ids = {run.config_identity for run in runs}
    if len(config_ids) > 1:
        reasons.append("model/reasoning/provider or prompt/schema/rulebook/extractor contract changed")
        return SlugAnalysis(
            slug=slug,
            selected_runs=runs,
            eligible_run_count=eligible_count,
            required_run_count=required,
            classification="UNSTABLE_RULE_OR_VALIDATOR_FIX_NEEDED",
            reasons=tuple(reasons),
        )
    hard_flag_sets = {run.hard_flag_identities for run in runs}
    if any(run.hard_flag_identities for run in runs):
        reasons.append("hard flags present in selected archived runs")
        if len(hard_flag_sets) > 1:
            reasons.append("hard flag identities changed")
            return SlugAnalysis(
                slug=slug,
                selected_runs=runs,
                eligible_run_count=eligible_count,
                required_run_count=required,
                classification="UNSTABLE_ARCHITECTURE_ESCALATION_CANDIDATE",
                reasons=tuple(reasons),
            )
        return SlugAnalysis(
            slug=slug,
            selected_runs=runs,
            eligible_run_count=eligible_count,
            required_run_count=required,
            classification="UNSTABLE_RULE_OR_VALIDATOR_FIX_NEEDED",
            reasons=tuple(reasons),
        )
    if len({run.row_fingerprints for run in runs}) > 1:
        reasons.append("row fingerprints changed")
    elif len({run.row_count for run in runs}) > 1:
        reasons.append("row counts changed")
    compared_attrs = (
        ("auction values changed", lambda run: run.auction_value),
        ("bid_note counts changed", lambda run: run.bid_note_counts),
        ("lifecycle counts changed", lambda run: run.lifecycle_counts),
        ("anonymous placeholder counts changed", lambda run: run.anonymous_placeholder_count),
        ("cohort-like placeholder counts changed", lambda run: run.cohort_like_placeholder_count),
        ("final-round metrics changed", lambda run: run.final_round_metrics),
        ("date diagnostics changed", lambda run: run.date_diagnostics),
        ("bid-value representation changed", lambda run: run.bid_value_representation),
        ("quote diagnostics changed", lambda run: run.quote_diagnostics),
        ("structural flag counts changed", lambda run: _structural_flag_counts(run.flag_counts)),
    )
    for reason, getter in compared_attrs:
        if len({getter(run) for run in runs}) > 1:
            reasons.append(reason)
    info_only_changed = len({_info_flag_counts(run.flag_counts) for run in runs}) > 1
    if reasons:
        return SlugAnalysis(
            slug=slug,
            selected_runs=runs,
            eligible_run_count=eligible_count,
            required_run_count=required,
            classification="UNSTABLE_ARCHITECTURE_ESCALATION_CANDIDATE",
            reasons=tuple(dict.fromkeys(reasons)),
            info_only_flag_volume_changed=info_only_changed,
        )
    if info_only_changed:
        reasons.append("info-only flag volume changed but substantive metrics were stable")
    else:
        reasons.append("selected archived runs have stable hashes, row fingerprints, and substantive metrics")
    return SlugAnalysis(
        slug=slug,
        selected_runs=runs,
        eligible_run_count=eligible_count,
        required_run_count=required,
        classification="STABLE_FOR_REFERENCE_REVIEW",
        reasons=tuple(reasons),
        info_only_flag_volume_changed=info_only_changed,
    )


def analyze(
    *,
    repo_root: Path,
    slugs: list[str],
    runs: int,
) -> StabilityAnalysis:
    slug_results: list[SlugAnalysis] = []
    for slug in slugs:
        archived = load_archived_runs(repo_root, slug)
        selected = select_latest_runs(archived, runs) if len(archived) >= runs else ()
        metrics = tuple(metrics_for_run(run) for run in selected)
        slug_results.append(_classify_slug(slug, metrics, len(archived), runs))
    classifications = [result.classification for result in slug_results]
    if "INSUFFICIENT_ARCHIVED_RUNS" in classifications:
        classification = "INSUFFICIENT_ARCHIVED_RUNS"
    elif "UNSTABLE_RULE_OR_VALIDATOR_FIX_NEEDED" in classifications:
        classification = "UNSTABLE_RULE_OR_VALIDATOR_FIX_NEEDED"
    elif "UNSTABLE_ARCHITECTURE_ESCALATION_CANDIDATE" in classifications:
        classification = "UNSTABLE_ARCHITECTURE_ESCALATION_CANDIDATE"
    else:
        classification = "STABLE_FOR_REFERENCE_REVIEW"
    reasons = tuple(
        f"{result.slug}: {reason}"
        for result in slug_results
        for reason in result.reasons
    )
    return StabilityAnalysis(
        slugs=tuple(slugs),
        requested_runs=runs,
        slug_results=tuple(slug_results),
        classification=classification,
        reasons=reasons,
    )


def _format_pairs(items: tuple[tuple[str, int], ...]) -> str:
    if not items:
        return "-"
    return ", ".join(f"{key}={value}" for key, value in items)


def _format_nested_pairs(items: tuple[tuple[tuple[str, str], int], ...]) -> str:
    if not items:
        return "-"
    return ", ".join(f"{severity}:{code}={value}" for (severity, code), value in items)


def _digest(values: Iterable[str]) -> str:
    joined = "\n".join(values)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:12]


def build_report(analysis: StabilityAnalysis) -> str:
    lines: list[str] = [
        "# Stability Report",
        "",
        f"- scope_slugs: {', '.join(analysis.slugs) if analysis.slugs else '-'}",
        f"- requested_runs: {analysis.requested_runs}",
        "",
        "## Run Manifest",
        "",
        "| slug | run_id | outcome | finished_at | model | reasoning | provider | prompt_hash | schema_hash | rulebook_hash | extractor_contract |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for result in analysis.slug_results:
        for run in result.selected_runs:
            lines.append(
                "| "
                + " | ".join([
                    result.slug,
                    run.run_id,
                    run.outcome,
                    run.finished_at,
                    run.model,
                    run.reasoning_effort,
                    run.provider,
                    run.prompt_hash,
                    run.schema_hash,
                    run.rulebook_hash,
                    run.extractor_contract_version,
                ])
                + " |"
            )
    lines.extend(["", "## Metrics", ""])
    for result in analysis.slug_results:
        lines.extend([
            f"### {result.slug}",
            "",
            f"- classification: {result.classification}",
            f"- eligible_archived_runs: {result.eligible_run_count}",
            f"- reasons: {'; '.join(result.reasons) if result.reasons else '-'}",
        ])
        for run in result.selected_runs:
            lines.extend([
                f"- run {run.run_id}: rows={run.row_count}; fingerprints={_digest(run.row_fingerprints)}; auction={run.auction_value}",
                f"- run {run.run_id} bid_note_counts: {_format_pairs(run.bid_note_counts)}",
                f"- run {run.run_id} flag_matrix: {_format_nested_pairs(run.flag_counts)}",
                f"- run {run.run_id} hard_flags: {', '.join(run.hard_flag_identities) if run.hard_flag_identities else '-'}",
                f"- run {run.run_id} lifecycle_counts: {_format_pairs(run.lifecycle_counts)}",
                f"- run {run.run_id} anonymous_placeholders: {run.anonymous_placeholder_count}; cohort_like_placeholders: {run.cohort_like_placeholder_count}",
                f"- run {run.run_id} final_round_metrics: {_format_pairs(run.final_round_metrics)}",
                f"- run {run.run_id} date_diagnostics: {_format_pairs(run.date_diagnostics)}",
                f"- run {run.run_id} bid_value_representation: {_format_pairs(run.bid_value_representation)}",
                f"- run {run.run_id} quote_diagnostics: {_format_pairs(run.quote_diagnostics)}",
            ])
        lines.append("")
    lines.extend([
        "## Classification",
        "",
        analysis.classification,
        "",
        "Reasons:",
    ])
    if analysis.reasons:
        lines.extend(f"- {reason}" for reason in analysis.reasons)
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"


def build_json_summary(analysis: StabilityAnalysis) -> str:
    payload = {
        "schema_version": "target_gate_proof_v1",
        "classification": analysis.classification,
        "reference_slugs": list(analysis.slugs),
        "requested_runs": analysis.requested_runs,
        "slugs": list(analysis.slugs),
        "reasons": list(analysis.reasons),
        "slug_results": [
            {
                "slug": result.slug,
                "classification": result.classification,
                "eligible_archived_runs": result.eligible_run_count,
                "required_archived_runs": result.required_run_count,
                "reasons": list(result.reasons),
                "selected_runs": [run.run_id for run in result.selected_runs],
            }
            for result in analysis.slug_results
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _reference_slugs_from_seeds(repo_root: Path) -> list[str]:
    seeds_path = repo_root / "seeds.csv"
    if not seeds_path.exists():
        return list(REFERENCE_SLUGS)
    with seeds_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        slugs = [
            row["deal_slug"]
            for row in reader
            if str(row.get("is_reference", "")).strip().lower() == "true"
        ]
    return slugs or list(REFERENCE_SLUGS)


def resolve_slugs(repo_root: Path, scope: str, slugs_arg: str | None) -> list[str]:
    if slugs_arg:
        slugs = [slug.strip() for slug in slugs_arg.split(",") if slug.strip()]
        if not slugs:
            raise StabilityError("--slugs did not contain any non-empty slug")
        return slugs
    if scope == "reference":
        return _reference_slugs_from_seeds(repo_root)
    raise StabilityError(f"unsupported scope: {scope}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=["reference"], default="reference")
    parser.add_argument("--slugs", help="Comma-separated slug list. Overrides --scope selection.")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--repo-root", type=Path, default=core.REPO_ROOT)
    parser.add_argument("--write", type=Path, help="Explicit report path to write. This is the only file the command writes.")
    parser.add_argument("--json", action="store_true", help="Emit JSON summary instead of markdown.")
    return parser


def _write_report(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.runs <= 0:
        parser.error("--runs must be positive")
    repo_root = args.repo_root.resolve()
    try:
        slugs = resolve_slugs(repo_root, args.scope, args.slugs)
        analysis = analyze(
            repo_root=repo_root,
            slugs=slugs,
            runs=args.runs,
        )
    except StabilityError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    report = build_json_summary(analysis) if args.json else build_report(analysis)
    if args.write:
        write_path = args.write if args.write.is_absolute() else repo_root / args.write
        write_path = write_path.resolve()
        try:
            write_path.relative_to(repo_root)
        except ValueError:
            print(
                f"--write path must live under repo root {repo_root}: {write_path}",
                file=sys.stderr,
            )
            return 2
        _write_report(write_path, report)
    print(report, end="")
    return 0 if analysis.classification == "STABLE_FOR_REFERENCE_REVIEW" else 1


if __name__ == "__main__":
    raise SystemExit(main())
