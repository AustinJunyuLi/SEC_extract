"""Read-only reconciliation for progress, outputs, flags, and audit v3."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal

from pipeline import core
from pipeline.llm.audit import (
    AUDIT_LATEST_SCHEMA_VERSION,
    AUDIT_RUN_SCHEMA_VERSION,
    LEGACY_AUDIT_NAMES,
    RAW_RESPONSE_SCHEMA_VERSION,
    VALIDATION_SCHEMA_VERSION,
)
from pipeline.llm.response_format import DEAL_GRAPH_CLAIM_SCHEMA


REFERENCE_SLUGS: tuple[str, ...] = core.REFERENCE_SLUGS
TRUSTED_OUTPUT_STATUSES = set(core.TRUSTED_STATUSES)
STALE_OUTPUT_STATUSES = {"stale_after_failure"}
TERMINAL_WITH_AUDIT_STATUSES = set(core.ALL_RUN_STATUSES)
EXPECTED_PROGRESS_SCHEMA = "v1"
RETIRED_PROVIDER_FALLBACK_FIELD = "json_" + "schema_used"


@dataclass(frozen=True)
class Issue:
    severity: Literal["error", "warning"]
    code: str
    message: str
    slug: str | None = None
    path: str | None = None
    line: int | None = None


@dataclass
class Report:
    repo_root: str
    scope: str
    checked_slugs: list[str] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == "warning")

    @property
    def ok(self) -> bool:
        return self.error_count == 0

    def add(
        self,
        severity: Literal["error", "warning"],
        code: str,
        message: str,
        *,
        slug: str | None = None,
        path: str | None = None,
        line: int | None = None,
    ) -> None:
        self.issues.append(
            Issue(
                severity=severity,
                code=code,
                message=message,
                slug=slug,
                path=path,
                line=line,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "repo_root": self.repo_root,
            "scope": self.scope,
            "checked_slugs": self.checked_slugs,
            "issues": [asdict(issue) for issue in self.issues],
        }


def _rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text())
    except FileNotFoundError:
        return None, "missing"
    except json.JSONDecodeError as exc:
        return None, f"bad_json: line {exc.lineno}: {exc.msg}"
    except OSError as exc:
        return None, f"unreadable: {exc}"
    if not isinstance(payload, dict):
        return None, "top-level JSON value is not an object"
    return payload, None


def _read_progress(root: Path, report: Report) -> dict[str, Any] | None:
    path = root / "state" / "progress.json"
    state, error = _load_json(path)
    if error:
        report.add("error", "progress_unreadable", error, path=_rel(root, path))
        return None
    assert state is not None
    if state.get("schema_version") != EXPECTED_PROGRESS_SCHEMA:
        report.add(
            "error",
            "progress_schema",
            "state/progress.json schema_version must be v1",
            path=_rel(root, path),
        )
    if "rulebook_version" in state:
        report.add(
            "error",
            "progress_stale_rulebook_pin",
            "state/progress.json must not contain a top-level rulebook_version",
            path=_rel(root, path),
        )
    if not isinstance(state.get("deals"), dict):
        report.add(
            "error",
            "progress_deals_missing",
            "state/progress.json deals must be an object",
            path=_rel(root, path),
        )
        return None
    return state


def _load_flags(root: Path, report: Report) -> list[dict[str, Any]]:
    path = root / "state" / "flags.jsonl"
    try:
        lines = path.read_text().splitlines()
    except FileNotFoundError:
        return []
    except OSError as exc:
        report.add("error", "flags_unreadable", str(exc), path=_rel(root, path))
        return []

    entries: list[dict[str, Any]] = []
    for line_no, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            report.add(
                "error",
                "bad_flags_jsonl",
                f"state/flags.jsonl line {line_no} is not valid JSON: {exc.msg}",
                path=_rel(root, path),
                line=line_no,
            )
            continue
        if not isinstance(entry, dict):
            report.add(
                "error",
                "bad_flags_jsonl",
                f"state/flags.jsonl line {line_no} is not a JSON object",
                path=_rel(root, path),
                line=line_no,
            )
            continue
        entries.append(entry)
    return entries


def _output_flags(final_output: dict[str, Any]) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    deal = final_output.get("deal") or {}
    for flag in deal.get("deal_flags") or []:
        if isinstance(flag, dict):
            flags.append({"deal_level": True, **flag})
    graph = final_output.get("graph")
    if isinstance(graph, dict):
        for flag in graph.get("review_flags") or []:
            if isinstance(flag, dict):
                flags.append(dict(flag))
    return flags


def _normalize_flag(flag: dict[str, Any]) -> dict[str, Any]:
    ignored = {"deal", "run_id", "logged_at"}
    return {key: value for key, value in flag.items() if key not in ignored}


def _expected_status(final_output: dict[str, Any]) -> tuple[str, int, dict[str, int]]:
    status, flag_count, _notes = core.summarize(final_output)
    return status, flag_count, core.count_flags(final_output)


def _check_reference_membership(deals: dict[str, Any], report: Report) -> None:
    for slug in REFERENCE_SLUGS:
        deal = deals.get(slug)
        if not isinstance(deal, dict):
            report.add(
                "error",
                "missing_reference_slug",
                f"reference slug {slug} is missing from state/progress.json",
                slug=slug,
                path="state/progress.json",
            )
            continue
        if deal.get("is_reference") is not True:
            report.add(
                "error",
                "reference_not_marked",
                f"reference slug {slug} is not marked is_reference=true",
                slug=slug,
                path="state/progress.json",
            )


def _check_targets_not_verified(deals: dict[str, Any], report: Report) -> None:
    for slug, deal in deals.items():
        if not isinstance(deal, dict):
            continue
        if deal.get("is_reference") is not True and deal.get("verified") is True:
            report.add(
                "error",
                "target_verified",
                "target deals must not carry verified reference metadata",
                slug=slug,
                path="state/progress.json",
            )


def _check_status_taxonomy(deals: dict[str, Any], report: Report) -> None:
    for slug, deal in deals.items():
        if not isinstance(deal, dict):
            continue
        status = deal.get("status")
        if status not in core.ALL_RUN_STATUSES and status not in (None, ""):
            report.add(
                "error",
                "status_taxonomy",
                f"stored status {status!r} is not in the live extraction taxonomy",
                slug=slug,
                path="state/progress.json",
            )


def _selected_slugs(
    deals: dict[str, Any],
    *,
    scope: Literal["reference", "all"],
    slugs: Iterable[str] | None,
    report: Report,
) -> list[str]:
    if slugs is not None:
        selected = [slug for slug in slugs if slug]
        for slug in selected:
            if slug not in deals:
                report.add(
                    "error",
                    "slug_missing",
                    f"slug {slug} is not present in state/progress.json",
                    slug=slug,
                    path="state/progress.json",
                )
        return selected
    if scope == "reference":
        return list(REFERENCE_SLUGS)
    return sorted(deals)


def _legacy_loose_files(slug_root: Path) -> list[Path]:
    if not slug_root.exists():
        return []
    return [
        child for child in slug_root.iterdir()
        if child.name in LEGACY_AUDIT_NAMES
    ]


def _path_under_run(expected_run_id: str, rel_path: Any, filename: str) -> bool:
    return rel_path == f"runs/{expected_run_id}/{filename}"


def _is_claim_payload(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    return all(isinstance(value.get(name), list) for name in DEAL_GRAPH_CLAIM_SCHEMA["required"])


def _run_pointer(slug: str, run_id: str, *, cache_eligible: bool = True) -> dict[str, Any]:
    return {
        "schema_version": AUDIT_LATEST_SCHEMA_VERSION,
        "slug": slug,
        "run_id": run_id,
        "outcome": "archived",
        "cache_eligible": cache_eligible,
        "manifest_path": f"runs/{run_id}/manifest.json",
        "raw_response_path": f"runs/{run_id}/raw_response.json",
        "validation_path": f"runs/{run_id}/validation.json",
        "final_output_path": f"runs/{run_id}/final_output.json",
    }


def _check_referenced_audit_file(
    *,
    root: Path,
    report: Report,
    slug: str,
    slug_root: Path,
    latest: dict[str, Any],
    key: str,
    filename: str,
    schema_key: str | None,
    expected_schema: str | None,
    run_id: str,
    check_identity: bool = True,
) -> dict[str, Any] | None:
    rel_path = latest.get(key)
    if rel_path is None:
        return None
    if not _path_under_run(run_id, rel_path, filename):
        report.add(
            "error",
            "audit_path_not_archived",
            f"latest.json {key} must be runs/{run_id}/{filename}",
            slug=slug,
            path=_rel(root, slug_root / "latest.json"),
        )
        return None
    path = slug_root / rel_path
    payload, error = _load_json(path)
    if error:
        report.add(
            "error",
            "audit_referenced_file_missing",
            f"{key} points to unreadable file: {error}",
            slug=slug,
            path=_rel(root, path),
        )
        return None
    assert payload is not None
    if check_identity and (payload.get("slug") != slug or payload.get("run_id") != run_id):
        report.add(
            "error",
            "audit_file_identity_mismatch",
            f"{rel_path} slug/run_id does not match latest.json",
            slug=slug,
            path=_rel(root, path),
        )
    if schema_key and expected_schema and payload.get(schema_key) != expected_schema:
        report.add(
            "error",
            "audit_file_schema",
            f"{rel_path} {schema_key} must be {expected_schema}",
            slug=slug,
            path=_rel(root, path),
        )
    return payload


def _check_manifest_contract_fields(
    *,
    root: Path,
    report: Report,
    slug: str,
    manifest: dict[str, Any],
    manifest_path: Path,
) -> None:
    if RETIRED_PROVIDER_FALLBACK_FIELD in manifest:
        report.add(
            "error",
            "audit_manifest_stale_field",
            "audit manifest must not contain retired structured-output fallback fields",
            slug=slug,
            path=_rel(root, manifest_path),
        )
    required = (
        "extractor_contract_version",
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
            report.add(
                "error",
                "audit_manifest_retired_field",
                f"audit manifest must not contain retired {key}",
                slug=slug,
                path=_rel(root, manifest_path),
            )
    for nested_key in ("models", "reasoning_efforts"):
        nested = manifest.get(nested_key)
        if isinstance(nested, dict) and "adjudicate" in nested:
            report.add(
                "error",
                "audit_manifest_retired_field",
                f"audit manifest {nested_key} must not contain retired adjudicate entry",
                slug=slug,
                path=_rel(root, manifest_path),
            )
    for key in required:
        if key not in manifest or manifest.get(key) in (None, ""):
            report.add(
                "error",
                "audit_manifest_contract_missing",
                f"audit manifest missing required {key}",
                slug=slug,
                path=_rel(root, manifest_path),
            )


def _check_audit(
    *,
    root: Path,
    report: Report,
    slug: str,
    progress_deal: dict[str, Any],
    output: dict[str, Any] | None,
) -> None:
    status = progress_deal.get("status")
    if status not in TERMINAL_WITH_AUDIT_STATUSES:
        return

    slug_root = root / "output" / "audit" / slug
    for loose_file in _legacy_loose_files(slug_root):
        report.add(
            "error",
            "legacy_loose_audit_file",
            "loose legacy audit files are not live audit data",
            slug=slug,
            path=_rel(root, loose_file),
        )

    latest_path = slug_root / "latest.json"
    latest, error = _load_json(latest_path)
    if error:
        report.add(
            "error",
            "missing_latest_audit",
            f"latest audit pointer is missing or unreadable: {error}",
            slug=slug,
            path=_rel(root, latest_path),
        )
        return
    assert latest is not None
    if latest.get("schema_version") != AUDIT_LATEST_SCHEMA_VERSION:
        report.add(
            "error",
            "audit_latest_schema",
            f"latest.json schema_version must be {AUDIT_LATEST_SCHEMA_VERSION}",
            slug=slug,
            path=_rel(root, latest_path),
        )
    if latest.get("slug") != slug:
        report.add(
            "error",
            "audit_latest_slug_mismatch",
            "latest.json slug does not match audit directory",
            slug=slug,
            path=_rel(root, latest_path),
        )
    run_id = latest.get("run_id")
    progress_run_id = progress_deal.get("last_run_id")
    output_run_id = (output.get("deal") or {}).get("last_run_id") if output else None
    if run_id != progress_run_id:
        report.add(
            "error",
            "audit_run_id_mismatch",
            "latest audit run_id must match progress last_run_id",
            slug=slug,
            path=_rel(root, latest_path),
        )
    if status in TRUSTED_OUTPUT_STATUSES and output is not None and run_id != output_run_id:
        report.add(
            "error",
            "audit_run_id_mismatch",
            "trusted latest audit run_id must match output deal.last_run_id",
            slug=slug,
            path=_rel(root, latest_path),
        )
    if status == "stale_after_failure" and output_run_id == progress_run_id:
        report.add(
            "error",
            "reference_artifact_stale",
            "stale_after_failure must leave a prior trusted output in place, not refresh it",
            slug=slug,
            path=_rel(root, latest_path),
        )
    if not isinstance(run_id, str) or not run_id:
        return
    if latest.get("outcome") != status:
        report.add(
            "error",
            "audit_outcome_mismatch",
            f"latest.json outcome={latest.get('outcome')!r} must match progress status={status!r}",
            slug=slug,
            path=_rel(root, latest_path),
        )
    if status in core.FAILURE_STATUSES and latest.get("cache_eligible") is not False:
        report.add(
            "error",
            "failed_cache_eligible",
            "failure runs must have cache_eligible=false",
            slug=slug,
            path=_rel(root, latest_path),
        )
    if status in TRUSTED_OUTPUT_STATUSES and latest.get("cache_eligible") is not True:
        report.add(
            "error",
            "trusted_cache_ineligible",
            "trusted extraction runs must have cache_eligible=true",
            slug=slug,
            path=_rel(root, latest_path),
        )

    manifest = _check_referenced_audit_file(
        root=root,
        report=report,
        slug=slug,
        slug_root=slug_root,
        latest=latest,
        key="manifest_path",
        filename="manifest.json",
        schema_key="schema_version",
        expected_schema=AUDIT_RUN_SCHEMA_VERSION,
        run_id=run_id,
    )
    if latest.get("manifest_path") is None or manifest is None:
        report.add(
            "error",
            "audit_manifest_missing",
            "latest.json must reference runs/{run_id}/manifest.json",
            slug=slug,
            path=_rel(root, latest_path),
        )
    raw = None
    validation = None
    final_output = None
    if latest.get("raw_response_path") is not None:
        raw = _check_referenced_audit_file(
            root=root,
            report=report,
            slug=slug,
            slug_root=slug_root,
            latest=latest,
            key="raw_response_path",
            filename="raw_response.json",
            schema_key="schema_version",
            expected_schema=RAW_RESPONSE_SCHEMA_VERSION,
            run_id=run_id,
        )
    if latest.get("validation_path") is not None:
        validation = _check_referenced_audit_file(
            root=root,
            report=report,
            slug=slug,
            slug_root=slug_root,
            latest=latest,
            key="validation_path",
            filename="validation.json",
            schema_key="schema_version",
            expected_schema=VALIDATION_SCHEMA_VERSION,
            run_id=run_id,
        )
    if latest.get("final_output_path") is not None:
        final_output = _check_referenced_audit_file(
            root=root,
            report=report,
            slug=slug,
            slug_root=slug_root,
            latest=latest,
            key="final_output_path",
            filename="final_output.json",
            schema_key=None,
            expected_schema=None,
            run_id=run_id,
            check_identity=False,
        )

    if status in TRUSTED_OUTPUT_STATUSES:
        for key, payload in (
            ("raw_response_path", raw),
            ("validation_path", validation),
            ("final_output_path", final_output),
        ):
            if latest.get(key) is None or payload is None:
                report.add(
                    "error",
                    "audit_required_file_missing",
                    f"finalized run latest.json must reference {key}",
                    slug=slug,
                    path=_rel(root, latest_path),
                )
        run_dir = slug_root / "runs" / run_id
        for artifact_name, code in (
            ("deal_graph_v2.json", "graph_snapshot_missing"),
            ("deal_graph.duckdb", "graph_database_missing"),
        ):
            artifact_path = run_dir / artifact_name
            if not artifact_path.exists():
                report.add(
                    "error",
                    code,
                    f"trusted run must contain {artifact_name}",
                    slug=slug,
                    path=_rel(root, artifact_path),
                )
        graph_snapshot_path = run_dir / "deal_graph_v2.json"
        if graph_snapshot_path.exists():
            graph_snapshot, graph_error = _load_json(graph_snapshot_path)
            if graph_error:
                report.add(
                    "error",
                    "graph_snapshot_unreadable",
                    f"deal_graph_v2.json is unreadable: {graph_error}",
                    slug=slug,
                    path=_rel(root, graph_snapshot_path),
                )
            elif graph_snapshot and graph_snapshot.get("schema_version") != "deal_graph_v2":
                report.add(
                    "error",
                    "graph_snapshot_schema",
                    "deal_graph_v2.json schema_version must be deal_graph_v2",
                    slug=slug,
                    path=_rel(root, graph_snapshot_path),
                )
    elif latest.get("final_output_path") is not None:
        report.add(
            "error",
            "failure_final_output_written",
            "failure runs must not refresh trusted final_output artifacts",
            slug=slug,
            path=_rel(root, latest_path),
        )
    if manifest:
        manifest_path = slug_root / latest["manifest_path"]
        _check_manifest_contract_fields(
            root=root,
            report=report,
            slug=slug,
            manifest=manifest,
            manifest_path=manifest_path,
        )
        if manifest.get("cache_eligible") != latest.get("cache_eligible"):
            report.add(
                "error",
                "audit_cache_eligible_mismatch",
                "manifest cache_eligible must match latest.json",
                slug=slug,
                path=_rel(root, manifest_path),
            )
        expected_rulebook = progress_deal.get("rulebook_version")
        if expected_rulebook and manifest.get("rulebook_version") != expected_rulebook:
            report.add(
                "error",
                "rulebook_version_mismatch",
                "audit manifest rulebook_version must match progress",
                slug=slug,
                path=_rel(root, manifest_path),
            )
    if raw:
        expected_rulebook = progress_deal.get("rulebook_version")
        if not _is_claim_payload(raw.get("parsed_json")):
            report.add(
                "error",
                "raw_response_shape",
                "raw_response parsed_json must use the live claim-only provider payload",
                slug=slug,
                path=_rel(root, slug_root / latest["raw_response_path"]),
            )
        if expected_rulebook and raw.get("rulebook_version") != expected_rulebook:
            report.add(
                "error",
                "rulebook_version_mismatch",
                "raw_response rulebook_version must match progress",
                slug=slug,
                path=_rel(root, slug_root / latest["raw_response_path"]),
            )
        if manifest and raw.get("extractor_contract_version") != manifest.get("extractor_contract_version"):
            report.add(
                "error",
                "extractor_contract_version_mismatch",
                "raw_response extractor_contract_version must match audit manifest",
                slug=slug,
                path=_rel(root, slug_root / latest["raw_response_path"]),
            )


def _check_output_and_flags(
    *,
    root: Path,
    report: Report,
    slug: str,
    progress_deal: dict[str, Any],
    flags_entries: list[dict[str, Any]],
) -> dict[str, Any] | None:
    status = progress_deal.get("status")
    output_path = root / "output" / "extractions" / f"{slug}.json"
    if status == "failed_system":
        if output_path.exists():
            report.add(
                "error",
                "failure_output_present",
                "failed_system must not leave a trusted latest extraction output",
                slug=slug,
                path=_rel(root, output_path),
            )
        return None
    output, error = _load_json(output_path)
    if error:
        report.add(
            "error",
            "missing_output",
            f"latest output is missing or unreadable for status={status}: {error}",
            slug=slug,
            path=_rel(root, output_path),
        )
        return None
    assert output is not None
    deal = output.get("deal")
    if not isinstance(deal, dict):
        report.add(
            "error",
            "output_deal_missing",
            "output deal object is missing",
            slug=slug,
            path=_rel(root, output_path),
        )
        return output

    progress_run_id = progress_deal.get("last_run_id")
    if output.get("schema_version") != "deal_graph_v2":
        report.add(
            "error",
            "output_schema",
            "latest output schema_version must be deal_graph_v2",
            slug=slug,
            path=_rel(root, output_path),
        )
    if "estimation_bidder_rows" in output:
        report.add(
            "error",
            "estimator_output_present",
            "trusted extraction output must not contain estimation_bidder_rows",
            slug=slug,
            path=_rel(root, output_path),
        )
    if not isinstance(output.get("review_rows"), list):
        report.add(
            "error",
            "review_rows_missing",
            "latest output must contain review_rows",
            slug=slug,
            path=_rel(root, output_path),
        )

    if status == "stale_after_failure":
        if deal.get("last_run_id") == progress_run_id:
            report.add(
                "error",
                "reference_artifact_stale",
                "stale_after_failure must point progress at the failed run while output remains from a prior trusted run",
                slug=slug,
                path=_rel(root, output_path),
            )
        else:
            report.add(
                "warning",
                "reference_artifact_stale",
                "latest trusted output is stale because the newest run failed",
                slug=slug,
                path=_rel(root, output_path),
            )
        return output

    if deal.get("last_run_id") != progress_run_id:
        report.add(
            "error",
            "run_id_mismatch",
            "output deal.last_run_id must match progress last_run_id",
            slug=slug,
            path=_rel(root, output_path),
        )
    if deal.get("last_run") != progress_deal.get("last_run"):
        report.add(
            "error",
            "last_run_mismatch",
            "output deal.last_run must match progress last_run",
            slug=slug,
            path=_rel(root, output_path),
        )
    if deal.get("rulebook_version") != progress_deal.get("rulebook_version"):
        report.add(
            "error",
            "rulebook_version_mismatch",
            "output rulebook_version must match progress",
            slug=slug,
            path=_rel(root, output_path),
        )

    expected_status, flag_count, counts = _expected_status(output)
    if progress_deal.get("flag_count") != flag_count:
        report.add(
            "error",
            "flag_count_mismatch",
            f"progress flag_count={progress_deal.get('flag_count')} but output has {flag_count}",
            slug=slug,
            path=_rel(root, output_path),
        )
    if status != expected_status:
        report.add(
            "error",
            "status_mismatch",
            f"progress status={status!r} but output flags imply {expected_status!r}",
            slug=slug,
            path=_rel(root, output_path),
        )
    for artifact_root, filename, code in (
        ("output/review_rows", f"{slug}.jsonl", "review_jsonl_missing"),
        ("output/review_csv", f"{slug}.csv", "review_csv_missing"),
    ):
        artifact_path = root / artifact_root / filename
        if not artifact_path.exists():
            report.add(
                "error",
                code,
                f"trusted status={status} requires {artifact_root}/{filename}",
                slug=slug,
                path=_rel(root, artifact_path),
            )

    output_norm = sorted(
        (_normalize_flag(flag) for flag in _output_flags(output)),
        key=lambda item: json.dumps(item, sort_keys=True),
    )
    current_entries = [
        entry for entry in flags_entries
        if entry.get("deal") == slug
        and entry.get("run_id") == progress_run_id
        and entry.get("logged_at") == progress_deal.get("last_run")
    ]
    jsonl_norm = sorted(
        (_normalize_flag(entry) for entry in current_entries),
        key=lambda item: json.dumps(item, sort_keys=True),
    )
    if output_norm != jsonl_norm:
        report.add(
            "error",
            "flags_jsonl_mismatch",
            "state/flags.jsonl latest run entries must match output flags",
            slug=slug,
            path="state/flags.jsonl",
        )
    return output


def reconcile_repo(
    repo_root: str | Path,
    *,
    scope: Literal["reference", "all"] = "reference",
    slugs: Iterable[str] | None = None,
) -> Report:
    root = Path(repo_root).resolve()
    report = Report(repo_root=str(root), scope="slugs" if slugs is not None else scope)
    state = _read_progress(root, report)
    if state is None:
        return report
    deals = state["deals"]
    _check_reference_membership(deals, report)
    _check_targets_not_verified(deals, report)
    _check_status_taxonomy(deals, report)
    flags_entries = _load_flags(root, report)

    selected = _selected_slugs(deals, scope=scope, slugs=slugs, report=report)
    report.checked_slugs = selected
    for slug in selected:
        progress_deal = deals.get(slug)
        if not isinstance(progress_deal, dict):
            continue
        output = _check_output_and_flags(
            root=root,
            report=report,
            slug=slug,
            progress_deal=progress_deal,
            flags_entries=flags_entries,
        )
        _check_audit(
            root=root,
            report=report,
            slug=slug,
            progress_deal=progress_deal,
            output=output,
        )
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scope",
        choices=("reference", "all"),
        default="reference",
        help="Which progress entries to reconcile when --slugs is omitted.",
    )
    parser.add_argument(
        "--slugs",
        help="Comma-separated explicit slugs to reconcile instead of --scope selection.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=core.REPO_ROOT,
        help="Repository root containing state/ and output/.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON report.",
    )
    return parser


def _print_text_report(report: Report) -> None:
    status = "OK" if report.ok else "FAILED"
    print(
        f"reconcile {status}: checked={len(report.checked_slugs)} "
        f"errors={report.error_count} warnings={report.warning_count}"
    )
    for issue in report.issues:
        location = issue.path or ""
        if issue.line is not None:
            location = f"{location}:{issue.line}"
        slug = f" [{issue.slug}]" if issue.slug else ""
        where = f" {location}" if location else ""
        print(f"{issue.severity.upper()} {issue.code}{slug}{where}: {issue.message}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    slugs = None
    if args.slugs:
        slugs = [slug.strip() for slug in args.slugs.split(",") if slug.strip()]
    report = reconcile_repo(
        args.repo_root,
        scope=args.scope,
        slugs=slugs,
    )
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        _print_text_report(report)
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
