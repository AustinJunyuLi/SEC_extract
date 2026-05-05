"""End-to-end deal_graph_v1 finalization for one extracted claim payload."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline import core

from .canonicalize import canonicalize_claim_payload
from .claims import parse_provider_payload
from .evidence import QuoteBindingError, bind_exact_quote, pages_to_paragraphs
from .export import write_csv, write_jsonl, write_snapshot
from .ids import make_id
from .project_estimation import project_estimation_rows
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
    estimation_rows_path: Path
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
    provider_payload = parse_provider_payload(raw_payload).model_dump(mode="json")
    graph = canonicalize_claim_payload(provider_payload, deal_slug=slug, run_id=run_id)

    section_pages = _background_pages(slug)
    _bind_claim_quotes(graph, slug=slug, run_id=run_id, pages=section_pages)

    validation_flags = validate_graph_as_dicts(graph)
    hard_count = sum(1 for flag in validation_flags if flag.get("severity") == "hard")
    review_projection: list[dict[str, Any]] = []
    estimation_projection: list[dict[str, Any]] = []
    if hard_count == 0:
        review_projection = project_review_rows(graph)
        estimation_projection = project_estimation_rows(graph)
        _attach_projection_rows(
            graph,
            slug=slug,
            run_id=run_id,
            review_projection=review_projection,
            estimation_projection=estimation_projection,
        )

    # Re-run validation after projections so unresolved blocking flags cannot
    # coexist with derived outputs.
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
        "schema_version": "deal_graph_v1",
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
        "estimation_bidder_rows": estimation_projection,
    }

    output_path = core.write_output(slug, final_output)
    snapshot_path = audit_run_dir / "deal_graph_v1.json"
    database_path = audit_run_dir / "deal_graph.duckdb"
    review_rows_path = core.REPO_ROOT / "output" / "review_rows" / f"{slug}.jsonl"
    review_csv_path = core.REPO_ROOT / "output" / "review_csv" / f"{slug}.csv"
    estimation_rows_path = (
        core.REPO_ROOT / "output" / "projections" / "estimation_bidder_rows" / f"{slug}.jsonl"
    )

    write_snapshot(graph, snapshot_path)
    write_jsonl(review_projection, review_rows_path)
    write_csv(review_projection, review_csv_path)
    write_jsonl(estimation_projection, estimation_rows_path)
    with DealGraphStore(database_path) as store:
        store.init_schema()
        store.insert_snapshot(graph)

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
        estimation_rows_path=estimation_rows_path,
        final_output=final_output,
        validation_flags=validation_flags,
    )


def _background_pages(slug: str) -> list[dict[str, Any]]:
    from pipeline.llm.extract import _background_section_payload

    pages = json.loads((core.DATA_DIR / slug / "pages.json").read_text())
    section_pages, _bounds = _background_section_payload(pages)
    return section_pages


def _bind_claim_quotes(
    graph: dict[str, Any],
    *,
    slug: str,
    run_id: str,
    pages: list[dict[str, Any]],
) -> None:
    filing_id = make_id("filing", slug, run_id)
    paragraphs = pages_to_paragraphs(pages=pages, filing_id=filing_id)
    links_by_claim: dict[str, list[str]] = {}
    for link in graph.get("claim_evidence", []):
        links_by_claim.setdefault(link["claim_id"], []).append(link["evidence_id"])

    old_evidence_remap: dict[str, list[str]] = {}
    bound_ids_by_claim: dict[str, list[str]] = {}
    bound_evidence: dict[str, dict[str, Any]] = {}
    review_flags: list[dict[str, Any]] = []
    for claim in graph.get("claims", []):
        claim["filing_id"] = filing_id
        claim.setdefault("provider_source_stage", "extractor_claims")
        claim_id = claim["claim_id"]
        quotes = _claim_quote_texts(claim)
        bindings = []
        try:
            for quote in quotes:
                bindings.append(
                    bind_exact_quote(
                        quote_text=quote,
                        filing_id=filing_id,
                        paragraphs=paragraphs,
                    )
                )
        except QuoteBindingError as exc:
            review_flags.append({
                "flag_id": make_id("flag", slug, run_id, claim_id, "quote_binding_failed"),
                "run_id": run_id,
                "deal_id": graph.get("deals", [{}])[0].get("deal_id"),
                "severity": "blocking",
                "code": "quote_binding_failed",
                "reason": f"{type(exc).__name__}: {exc}",
                "row_table": "claims",
                "row_id": claim_id,
                "status": "open",
                "current": True,
            })
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
        bound_ids_by_claim[claim_id] = new_evidence_ids
        for old_evidence_id in links_by_claim.get(claim_id, []):
            old_evidence_remap[old_evidence_id] = new_evidence_ids

    graph["evidence"] = list(bound_evidence.values())
    graph["review_flags"].extend(review_flags)
    _rebuild_claim_evidence_links(graph.get("claim_evidence", []), bound_ids_by_claim)
    _remap_row_evidence_links(graph.get("row_evidence", []), old_evidence_remap)


def _claim_quote_texts(claim: dict[str, Any]) -> list[str]:
    raw_value = claim.get("raw_value")
    if isinstance(raw_value, str):
        try:
            raw_value = json.loads(raw_value)
        except json.JSONDecodeError:
            raw_value = {}
    if not isinstance(raw_value, dict):
        raw_value = {}

    quotes: list[str] = []
    primary = claim.get("quote_text")
    for quote in [primary, *(raw_value.get("quote_texts") or [])]:
        if not isinstance(quote, str):
            continue
        if quote and quote not in quotes:
            quotes.append(quote)
    return quotes


def _rebuild_claim_evidence_links(
    rows: list[dict[str, Any]],
    bound_ids_by_claim: dict[str, list[str]],
) -> None:
    rebuilt: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for claim_id, evidence_ids in bound_ids_by_claim.items():
        for ordinal, evidence_id in enumerate(evidence_ids, start=1):
            key = (claim_id, evidence_id)
            if key in seen:
                continue
            seen.add(key)
            rebuilt.append({
                "claim_id": claim_id,
                "evidence_id": evidence_id,
                "ordinal": ordinal,
            })
    rows[:] = rebuilt


def _remap_row_evidence_links(rows: list[dict[str, Any]], remap: dict[str, list[str]]) -> None:
    kept: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        evidence_ids = remap.get(row.get("evidence_id"))
        if not evidence_ids:
            continue
        for ordinal, evidence_id in enumerate(evidence_ids, start=1):
            new_row = dict(row)
            new_row["evidence_id"] = evidence_id
            new_row["ordinal"] = ordinal
            key = (new_row.get("row_table"), new_row.get("row_id"), evidence_id)
            if key in seen:
                continue
            seen.add(key)
            kept.append(new_row)
    rows[:] = kept


def _attach_projection_rows(
    graph: dict[str, Any],
    *,
    slug: str,
    run_id: str,
    review_projection: list[dict[str, Any]],
    estimation_projection: list[dict[str, Any]],
) -> None:
    graph["review_rows"] = [
        {
            "review_row_id": make_id("review_row", slug, run_id, index, row),
            "run_id": run_id,
            "deal_slug": slug,
            "payload_json": json.dumps(row, sort_keys=True),
        }
        for index, row in enumerate(review_projection, start=1)
    ]
    graph["estimation_bidder_rows"] = [
        {
            "estimation_row_id": make_id("estimation_row", slug, run_id, index, row),
            "run_id": run_id,
            **row,
        }
        for index, row in enumerate(estimation_projection, start=1)
    ]
