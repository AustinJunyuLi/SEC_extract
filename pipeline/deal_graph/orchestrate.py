"""End-to-end deal_graph_v2 finalization for one extracted claim payload."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline import core

from .canonicalize import (
    canonicalize_claim_payload,
    claim_id_for_provider_claim,
    iter_provider_claims,
)
from .claims import parse_provider_payload
from .evidence import (
    QuoteBindingError,
    bind_quote_to_citation_unit,
    citation_unit_paragraphs,
    quote_candidate_units,
)
from .export import write_csv, write_jsonl, write_snapshot
from .ids import make_id
from .project_review import project_review_rows
from .store import DealGraphStore
from .validate import validate_graph_as_dicts


@dataclass(frozen=True)
class GraphRunResult:
    status: str
    flag_count: int
    notes: str
    output_path: Path
    snapshot_path: Path
    database_path: Path
    review_rows_path: Path
    review_csv_path: Path
    final_output: dict[str, Any]
    validation_flags: list[dict[str, Any]]


def finalize_claim_payload(
    *,
    slug: str,
    run_id: str,
    raw_payload: dict[str, Any],
    rulebook_version: str,
    audit_run_dir: Path,
) -> GraphRunResult:
    """Finalize one strict provider claim payload into graph outputs.

    This is the replacement for the retired row-event finalizer. The provider
    proposes typed claims only; Python owns quote binding, canonical rows,
    validation flags, projections, state updates, and artifact writes.
    """
    section_pages = _background_pages(slug)
    provider_payload = parse_provider_payload(raw_payload).model_dump(mode="json")
    evidence_context = _bind_provider_evidence(
        provider_payload,
        slug=slug,
        run_id=run_id,
        pages=section_pages,
    )
    graph = canonicalize_claim_payload(
        provider_payload,
        deal_slug=slug,
        run_id=run_id,
        evidence_context=evidence_context,
        target_name=_target_name(slug),
    )

    review_projection = project_review_rows(graph)
    _attach_projection_rows(
        graph,
        slug=slug,
        run_id=run_id,
        review_projection=review_projection,
    )

    # Validate after review projection so the audit manifest covers exactly the
    # graph and review rows written for this run.
    validation_flags = validate_graph_as_dicts(graph)
    hard_count = sum(1 for flag in validation_flags if flag.get("severity") == "hard")
    soft_count = sum(1 for flag in validation_flags if flag.get("severity") == "soft")
    info_count = sum(1 for flag in validation_flags if flag.get("severity") == "info")
    status = "validated" if hard_count else "passed" if soft_count or info_count else "passed_clean"
    flag_count = hard_count + soft_count + info_count
    notes = f"hard={hard_count} soft={soft_count} info={info_count}"

    last_run = core._now_iso()
    graph.update({
        "last_run": last_run,
        "rulebook_version": rulebook_version,
        "validation_flags": validation_flags,
    })
    final_output = {
        "schema_version": "deal_graph_v2",
        "deal_slug": slug,
        "run_id": run_id,
        "last_run": last_run,
        "rulebook_version": rulebook_version,
        "deal": {
            "deal_slug": slug,
            "deal_flags": validation_flags,
            "last_run": last_run,
            "last_run_id": run_id,
            "rulebook_version": rulebook_version,
            "status": status,
        },
        "graph": graph,
        "review_rows": review_projection,
    }

    output_path = core.write_output(slug, final_output)
    snapshot_path = audit_run_dir / "deal_graph_v2.json"
    database_path = audit_run_dir / "deal_graph.duckdb"
    review_rows_path = core.REPO_ROOT / "output" / "review_rows" / f"{slug}.jsonl"
    review_csv_path = core.REPO_ROOT / "output" / "review_csv" / f"{slug}.csv"

    write_snapshot(graph, snapshot_path)
    write_jsonl(review_projection, review_rows_path)
    write_csv(review_projection, review_csv_path)
    database_tmp_path = database_path.with_name(f".{database_path.name}.tmp.{os.getpid()}")
    if database_tmp_path.exists():
        database_tmp_path.unlink()
    with DealGraphStore(database_tmp_path) as store:
        store.init_schema()
        store.insert_snapshot(graph)
    os.replace(database_tmp_path, database_path)

    core.append_flags_log(slug, final_output, last_run, run_id)
    core.update_progress(
        slug,
        status,
        flag_count,
        notes,
        rulebook_version,
        last_run,
        run_id,
    )
    return GraphRunResult(
        status=status,
        flag_count=flag_count,
        notes=notes,
        output_path=output_path,
        snapshot_path=snapshot_path,
        database_path=database_path,
        review_rows_path=review_rows_path,
        review_csv_path=review_csv_path,
        final_output=final_output,
        validation_flags=validation_flags,
    )


def _background_pages(slug: str) -> list[dict[str, Any]]:
    from pipeline.llm.extract import _background_section_payload

    pages = json.loads((core.DATA_DIR / slug / "pages.json").read_text())
    section_pages, _bounds = _background_section_payload(pages)
    return section_pages


def _target_name(slug: str) -> str | None:
    manifest_path = core.DATA_DIR / slug / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    value = manifest.get("target_name")
    return value if isinstance(value, str) and value.strip() else None


def _bind_provider_evidence(
    provider_payload: dict[str, Any],
    *,
    slug: str,
    run_id: str,
    pages: list[dict[str, Any]],
) -> dict[str, Any]:
    filing_id = make_id("filing", slug, run_id)
    citation_units = citation_unit_paragraphs(pages=pages, filing_id=filing_id)
    claim_evidence_ids: dict[str, list[str]] = {}
    claim_failures: dict[str, dict[str, Any]] = {}
    bound_evidence: dict[str, dict[str, Any]] = {}
    review_flags: list[dict[str, Any]] = []
    for family, claim_type, index, sequence, claim in iter_provider_claims(provider_payload):
        claim_id = claim_id_for_provider_claim(
            deal_slug=slug,
            claim_type=claim_type,
            sequence=sequence,
            claim=claim,
        )
        evidence_refs = claim.get("evidence_refs") or []
        bindings = []
        failures: list[dict[str, Any]] = []
        if not evidence_refs:
            failures.append(_evidence_failure_payload(
                slug=slug,
                run_id=run_id,
                family=family,
                claim_type=claim_type,
                claim_index=index,
                claim_id=claim_id,
                claim=claim,
                evidence_ref={},
                evidence_ref_index=None,
                error=QuoteBindingError("claim has no evidence_refs"),
                citation_units=citation_units,
            ))
        for ref_index, evidence_ref in enumerate(evidence_refs):
            try:
                if not isinstance(evidence_ref, dict):
                    raise QuoteBindingError(f"evidence_refs[{ref_index}] is not an object")
                citation_unit_id = evidence_ref.get("citation_unit_id")
                quote = evidence_ref.get("quote_text")
                if not isinstance(citation_unit_id, str) or not citation_unit_id:
                    raise QuoteBindingError(f"evidence_refs[{ref_index}].citation_unit_id is missing")
                if not isinstance(quote, str) or not quote:
                    raise QuoteBindingError(f"evidence_refs[{ref_index}].quote_text is missing")
                bindings.append(
                    bind_quote_to_citation_unit(
                        quote_text=quote,
                        citation_unit_id=citation_unit_id,
                        filing_id=filing_id,
                        citation_units=citation_units,
                    )
                )
            except QuoteBindingError as exc:
                failures.append(_evidence_failure_payload(
                    slug=slug,
                    run_id=run_id,
                    family=family,
                    claim_type=claim_type,
                    claim_index=index,
                    claim_id=claim_id,
                    claim=claim,
                    evidence_ref=evidence_ref if isinstance(evidence_ref, dict) else {},
                    evidence_ref_index=ref_index,
                    error=exc,
                    citation_units=citation_units,
                ))
        if failures and not bindings:
            failure = failures[0]
            claim_failures[claim_id] = {
                "reason_code": "evidence_ref_binding_failed",
                "reason": failure["reason"],
            }
        for failure in failures:
            review_flags.append(_review_flag_for_evidence_failure(
                run_id=run_id,
                claim_id=claim_id,
                failure=failure,
                blocks_claim=not bindings,
            ))
        if not bindings:
            continue
        new_evidence_ids = []
        for binding in bindings:
            evidence = binding.evidence.model_dump(mode="json")
            evidence.update({
                "run_id": run_id,
                "deal_slug": slug,
                "source_page": binding.paragraph.page_hint,
            })
            bound_evidence[evidence["evidence_id"]] = evidence
            new_evidence_ids.append(evidence["evidence_id"])
        claim_evidence_ids[claim_id] = new_evidence_ids

    return {
        "filing_id": filing_id,
        "evidence": list(bound_evidence.values()),
        "claim_evidence_ids": claim_evidence_ids,
        "claim_failures": claim_failures,
        "review_flags": review_flags,
    }


def _review_flag_for_evidence_failure(
    *,
    run_id: str,
    claim_id: str,
    failure: dict[str, Any],
    blocks_claim: bool,
) -> dict[str, Any]:
    return {
        "flag_id": failure["flag_id"],
        "run_id": run_id,
        "deal_id": None,
        "severity": "blocking" if blocks_claim else "soft",
        "code": "evidence_ref_binding_failed",
        "reason": failure["reason"],
        "row_table": "claims",
        "row_id": claim_id,
        "status": "open",
        "current": True,
        "metadata": failure,
    }


def _evidence_failure_payload(
    *,
    slug: str,
    run_id: str,
    family: str,
    claim_type: str,
    claim_index: int,
    claim_id: str,
    claim: dict[str, Any],
    evidence_ref: dict[str, Any],
    evidence_ref_index: int | None,
    error: Exception,
    citation_units: dict[str, Any],
) -> dict[str, Any]:
    refs = claim.get("evidence_refs") if isinstance(claim, dict) else None
    supplied_refs = refs if isinstance(refs, list) else []
    quote = evidence_ref.get("quote_text") if isinstance(evidence_ref, dict) else None
    reason = f"{type(error).__name__}: {error}"
    return {
        "flag_id": make_id("flag", slug, run_id, claim_id, "evidence_ref_binding_failed", evidence_ref_index),
        "slug": slug,
        "run_id": run_id,
        "claim_family": family,
        "claim_type": claim_type,
        "claim_index": claim_index,
        "claim_id": claim_id,
        "claim_summary": _claim_summary(claim_type, claim),
        "evidence_ref_index": evidence_ref_index,
        "provided_citation_unit_id": evidence_ref.get("citation_unit_id") if isinstance(evidence_ref, dict) else None,
        "provided_quote_text": quote,
        "supplied_evidence_refs": supplied_refs,
        "reason_code": "evidence_ref_binding_failed",
        "reason": reason,
        "candidate_units": quote_candidate_units(str(quote or ""), citation_units),
        "suggested_action": "Choose the correct citation unit and exact quote, or reject the claim.",
    }


def _claim_summary(claim_type: str, claim: dict[str, Any]) -> dict[str, Any]:
    if claim_type == "actor":
        keys = ("actor_label", "actor_kind", "observability")
    elif claim_type == "actor_relation":
        keys = ("subject_label", "relation_type", "object_label", "effective_date_first")
    elif claim_type == "event":
        keys = ("event_type", "event_subtype", "event_date", "actor_label")
    elif claim_type == "bid":
        keys = ("bidder_label", "bid_date", "bid_value", "bid_value_lower", "bid_value_upper", "bid_value_unit")
    else:
        keys = ("process_stage", "actor_class", "count_min", "count_max", "count_qualifier")
    return {key: claim.get(key) for key in keys if key in claim}


def _attach_projection_rows(
    graph: dict[str, Any],
    *,
    slug: str,
    run_id: str,
    review_projection: list[dict[str, Any]],
) -> None:
    graph["review_rows"] = [
        {
            "review_row_id": make_id("review_row", slug, run_id, index, row),
            **row,
        }
        for index, row in enumerate(review_projection, start=1)
    ]
