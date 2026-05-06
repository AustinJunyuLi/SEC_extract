"""Human-review row projection from deal_graph_v2 snapshots."""
from __future__ import annotations

import json
from typing import Any


REVIEW_ROW_FIELDS: tuple[str, ...] = (
    "deal_slug",
    "run_id",
    "review_status",
    "event_id",
    "event_date",
    "event_type",
    "event_subtype",
    "actor_id",
    "actor_label",
    "actor_kind",
    "actor_role",
    "bid_value",
    "bid_value_lower",
    "bid_value_upper",
    "bid_value_unit",
    "consideration_type",
    "bid_stage",
    "cycle_id",
    "relation_id",
    "relation_type",
    "subject_actor_id",
    "subject_actor_label",
    "object_actor_id",
    "object_actor_label",
    "participation_count_id",
    "process_stage",
    "actor_class",
    "count_min",
    "count_max",
    "count_qualifier",
    "claim_id",
    "claim_type",
    "claim_summary",
    "confidence",
    "citation_unit_id",
    "supplied_quote",
    "bound_source_quote",
    "bound_source_page",
    "issue_codes",
    "issue_reasons",
    "suggested_action",
    "evidence_ref_index",
    "review_resolution",
    "reviewed_by",
    "reviewed_at",
    "resolution_reason",
    "corrected_citation_unit_id",
    "corrected_quote_text",
)

RESOLUTION_FIELDS: tuple[str, ...] = (
    "review_resolution",
    "reviewed_by",
    "reviewed_at",
    "resolution_reason",
    "corrected_citation_unit_id",
    "corrected_quote_text",
)

NUMERIC_REVIEW_ROW_FIELDS: tuple[str, ...] = (
    "bid_value",
    "bid_value_lower",
    "bid_value_upper",
    "count_min",
    "count_max",
)


def project_review_rows(graph: dict[str, Any]) -> list[dict[str, Any]]:
    """Project canonical rows and rejected claims into one review surface."""
    context = _ReviewContext(graph)
    rows: list[dict[str, Any]] = []
    rows.extend(_actor_rows(graph, context))
    rows.extend(_actor_relation_rows(graph, context))
    rows.extend(_event_rows(graph, context))
    rows.extend(_participation_count_rows(graph, context))
    rows.extend(_rejected_claim_rows(graph, context))
    return [_ordered(row) for row in rows]


class _ReviewContext:
    def __init__(self, graph: dict[str, Any]):
        self.graph = graph
        self.claims = {row["claim_id"]: row for row in graph.get("claims", []) if row.get("claim_id")}
        self.dispositions = {
            row.get("claim_id"): row
            for row in graph.get("claim_dispositions", [])
            if row.get("current", True) and row.get("claim_id")
        }
        self.evidence = {row["evidence_id"]: row for row in graph.get("evidence", []) if row.get("evidence_id")}
        self.claim_evidence_ids: dict[str, list[str]] = {}
        self.claims_by_evidence_id: dict[str, list[str]] = {}
        for row in sorted(graph.get("claim_evidence", []), key=lambda item: item.get("ordinal") or 0):
            claim_id = row.get("claim_id")
            evidence_id = row.get("evidence_id")
            if not claim_id or not evidence_id:
                continue
            self.claim_evidence_ids.setdefault(claim_id, []).append(evidence_id)
            self.claims_by_evidence_id.setdefault(evidence_id, []).append(claim_id)
        self.evidence_ids_by_row: dict[tuple[str, str], list[str]] = {}
        for row in sorted(graph.get("row_evidence", []), key=lambda item: item.get("ordinal") or 0):
            key = (row.get("row_table"), row.get("row_id"))
            evidence_id = row.get("evidence_id")
            if key[0] and key[1] and evidence_id:
                self.evidence_ids_by_row.setdefault(key, []).append(evidence_id)
        self.flags_by_row: dict[tuple[str | None, str | None], list[dict[str, Any]]] = {}
        for flag in graph.get("review_flags", []):
            if flag.get("current", True) is False or flag.get("status") == "resolved":
                continue
            key = (flag.get("row_table"), flag.get("row_id"))
            self.flags_by_row.setdefault(key, []).append(flag)

    def row_evidence(self, row_table: str, row_id: str) -> list[dict[str, Any]]:
        return [
            self.evidence[evidence_id]
            for evidence_id in self.evidence_ids_by_row.get((row_table, row_id), [])
            if evidence_id in self.evidence
        ]

    def claim_for_row(self, row_table: str, row_id: str) -> dict[str, Any] | None:
        claim_ids: list[str] = []
        for evidence_id in self.evidence_ids_by_row.get((row_table, row_id), []):
            claim_ids.extend(self.claims_by_evidence_id.get(evidence_id, []))
        claim_ids = sorted(
            dict.fromkeys(claim_ids),
            key=lambda claim_id: self.claims.get(claim_id, {}).get("claim_sequence") or 0,
        )
        for claim_id in claim_ids:
            disposition = self.dispositions.get(claim_id, {})
            if disposition.get("disposition") in {"supported", "merged_duplicate"}:
                return self.claims.get(claim_id)
        return self.claims.get(claim_ids[0]) if claim_ids else None

    def flags_for(self, row_table: str, row_id: str, claim_id: str | None) -> list[dict[str, Any]]:
        flags = list(self.flags_by_row.get((row_table, row_id), []))
        if claim_id:
            flags.extend(self.flags_by_row.get(("claims", claim_id), []))
        return flags


def _base_row(graph: dict[str, Any]) -> dict[str, Any]:
    row = {field: "" for field in REVIEW_ROW_FIELDS}
    for field in NUMERIC_REVIEW_ROW_FIELDS:
        row[field] = None
    row["deal_slug"] = graph.get("deal_slug") or ""
    row["run_id"] = graph.get("run_id") or ""
    return row


def _actor_rows(graph: dict[str, Any], context: _ReviewContext) -> list[dict[str, Any]]:
    rows = []
    for actor in sorted(graph.get("actors", []), key=lambda row: (row.get("actor_label") or "", row.get("actor_id") or "")):
        actor_id = actor.get("actor_id")
        if not actor_id:
            continue
        claim = context.claim_for_row("actors", actor_id)
        row = _canonical_base(graph, context, "actors", actor_id, claim)
        row.update({
            "actor_id": actor_id,
            "actor_label": actor.get("actor_label") or "",
            "actor_kind": actor.get("actor_kind") or "",
            "actor_class": actor.get("bidder_class") or "",
        })
        rows.append(row)
    return rows


def _actor_relation_rows(graph: dict[str, Any], context: _ReviewContext) -> list[dict[str, Any]]:
    rows = []
    for relation in sorted(graph.get("actor_relations", []), key=lambda row: row.get("relation_id") or ""):
        relation_id = relation.get("relation_id")
        if not relation_id:
            continue
        claim = context.claim_for_row("actor_relations", relation_id)
        row = _canonical_base(graph, context, "actor_relations", relation_id, claim)
        row.update({
            "relation_id": relation_id,
            "relation_type": relation.get("relation_type") or "",
            "subject_actor_id": relation.get("subject_actor_id") or "",
            "subject_actor_label": relation.get("subject_actor_label") or "",
            "object_actor_id": relation.get("object_actor_id") or "",
            "object_actor_label": relation.get("object_actor_label") or "",
            "actor_id": relation.get("subject_actor_id") or "",
            "actor_label": relation.get("subject_actor_label") or "",
            "actor_role": relation.get("relation_type") or "",
            "cycle_id": relation.get("cycle_id_first_observed") or "",
        })
        rows.append(row)
    return rows


def _event_rows(graph: dict[str, Any], context: _ReviewContext) -> list[dict[str, Any]]:
    actors = {row["actor_id"]: row for row in graph.get("actors", []) if row.get("actor_id")}
    links_by_event: dict[str, list[dict[str, Any]]] = {}
    for link in graph.get("event_actor_links", []):
        links_by_event.setdefault(link["event_id"], []).append(link)

    rows = []
    for event in sorted(graph.get("events", []), key=_event_sort_key):
        event_id = event.get("event_id")
        if not event_id:
            continue
        claim = context.claim_for_row("events", event_id)
        for link in links_by_event.get(event_id, []) or [None]:
            actor = actors.get(link.get("actor_id")) if link else None
            row = _canonical_base(graph, context, "events", event_id, claim)
            row.update({
                "cycle_id": event.get("cycle_id") or "",
                "event_id": event_id,
                "event_date": event.get("event_date") or "",
                "event_type": event.get("event_type") or "",
                "event_subtype": event.get("event_subtype") or "",
                "actor_id": actor.get("actor_id") if actor else "",
                "actor_label": actor.get("actor_label") if actor else "",
                "actor_kind": actor.get("actor_kind") if actor else "",
                "actor_role": link.get("role") if link else "",
                "bid_value": _numeric_cell(event.get("bid_value")),
                "bid_value_lower": _numeric_cell(event.get("bid_value_lower")),
                "bid_value_upper": _numeric_cell(event.get("bid_value_upper")),
                "bid_value_unit": event.get("bid_value_unit") or "",
                "consideration_type": event.get("consideration_type") or "",
                "bid_stage": event.get("bid_stage") or "",
            })
            rows.append(row)
    return rows


def _participation_count_rows(graph: dict[str, Any], context: _ReviewContext) -> list[dict[str, Any]]:
    rows = []
    for count in sorted(graph.get("participation_counts", []), key=lambda row: row.get("participation_count_id") or ""):
        count_id = count.get("participation_count_id")
        if not count_id:
            continue
        claim = context.claim_for_row("participation_counts", count_id)
        row = _canonical_base(graph, context, "participation_counts", count_id, claim)
        row.update({
            "participation_count_id": count_id,
            "cycle_id": count.get("cycle_id") or "",
            "process_stage": count.get("process_stage") or "",
            "actor_class": count.get("actor_class") or "",
            "count_min": _numeric_cell(count.get("count_min")),
            "count_max": _numeric_cell(count.get("count_max")),
            "count_qualifier": count.get("count_qualifier") or "",
        })
        rows.append(row)
    return rows


def _canonical_base(
    graph: dict[str, Any],
    context: _ReviewContext,
    row_table: str,
    row_id: str,
    claim: dict[str, Any] | None,
) -> dict[str, Any]:
    row = _base_row(graph)
    claim_id = claim.get("claim_id") if claim else None
    flags = context.flags_for(row_table, row_id, claim_id)
    evidence_rows = context.row_evidence(row_table, row_id)
    row.update({
        "review_status": "needs_review" if flags else "clean",
        "claim_id": claim_id or "",
        "claim_type": _claim_type_label(claim.get("claim_type")) if claim else "",
        "claim_summary": _claim_summary(claim) if claim else "",
        "confidence": claim.get("confidence") if claim else "",
        "citation_unit_id": _source_ref_value(claim, "citation_unit_id"),
        "supplied_quote": _source_ref_value(claim, "quote_text"),
        "bound_source_quote": _joined(evidence_rows, "quote_text"),
        "bound_source_page": _joined(evidence_rows, "source_page"),
        **_issue_columns(flags),
    })
    return row


def _rejected_claim_rows(graph: dict[str, Any], context: _ReviewContext) -> list[dict[str, Any]]:
    rows = []
    for disposition in sorted(graph.get("claim_dispositions", []), key=lambda row: row.get("claim_id") or ""):
        if disposition.get("disposition") != "rejected_unsupported":
            continue
        claim_id = disposition.get("claim_id")
        claim = context.claims.get(claim_id)
        if not claim:
            continue
        flags = context.flags_for("claims", claim_id, claim_id)
        metadata = _first_metadata(flags)
        row = _base_row(graph)
        row.update({
            "review_status": "rejected_claim",
            "claim_id": claim_id,
            "claim_type": _claim_type_label(claim.get("claim_type")),
            "claim_summary": _claim_summary(claim),
            "confidence": claim.get("confidence") or "",
            "citation_unit_id": metadata.get("provided_citation_unit_id") or _source_ref_value(claim, "citation_unit_id"),
            "supplied_quote": metadata.get("provided_quote_text") or _source_ref_value(claim, "quote_text"),
            "bound_source_quote": "",
            "bound_source_page": "",
            "issue_codes": _join_unique([flag.get("code") for flag in flags] + [disposition.get("reason_code")]),
            "issue_reasons": _join_unique([flag.get("reason") for flag in flags] + [disposition.get("reason")]),
            "suggested_action": metadata.get("suggested_action") or "Review the supplied citation unit and quote, or reject the claim.",
            "evidence_ref_index": _cell(metadata.get("evidence_ref_index")),
        })
        rows.append(row)
    return rows


def _issue_columns(flags: list[dict[str, Any]]) -> dict[str, str]:
    metadata = _first_metadata(flags)
    return {
        "issue_codes": _join_unique(flag.get("code") for flag in flags),
        "issue_reasons": _join_unique(flag.get("reason") for flag in flags),
        "suggested_action": metadata.get("suggested_action") or ("" if not flags else "Review the source support and canonical row fields."),
        "evidence_ref_index": _cell(metadata.get("evidence_ref_index")),
    }


def _first_metadata(flags: list[dict[str, Any]]) -> dict[str, Any]:
    for flag in flags:
        metadata = flag.get("metadata")
        if isinstance(metadata, dict):
            return metadata
        if isinstance(metadata, str):
            try:
                parsed = json.loads(metadata)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
    return {}


def _source_ref_value(claim: dict[str, Any] | None, key: str) -> str:
    if not claim:
        return ""
    raw_value = claim.get("raw_value")
    if isinstance(raw_value, str):
        try:
            raw_value = json.loads(raw_value)
        except json.JSONDecodeError:
            raw_value = {}
    refs = raw_value.get("evidence_refs") if isinstance(raw_value, dict) else None
    if not isinstance(refs, list):
        return ""
    values = [str(ref.get(key)) for ref in refs if isinstance(ref, dict) and ref.get(key) not in (None, "")]
    return " | ".join(values)


def _claim_summary(claim: dict[str, Any] | None) -> str:
    if not claim:
        return ""
    raw_value = claim.get("raw_value")
    if isinstance(raw_value, str):
        try:
            raw_value = json.loads(raw_value)
        except json.JSONDecodeError:
            raw_value = {}
    if not isinstance(raw_value, dict):
        raw_value = {}
    claim_type = claim.get("claim_type")
    if claim_type == "actor":
        return f"actor {raw_value.get('actor_label') or ''} ({raw_value.get('actor_kind') or ''})".strip()
    if claim_type == "actor_relation":
        return " ".join(
            str(raw_value.get(key) or "")
            for key in ("subject_label", "relation_type", "object_label")
        ).strip()
    if claim_type == "bid":
        value = raw_value.get("bid_value")
        if value in (None, ""):
            lower = raw_value.get("bid_value_lower")
            upper = raw_value.get("bid_value_upper")
            value = f"{lower}-{upper}" if lower not in (None, "") or upper not in (None, "") else "value unspecified"
        return f"{raw_value.get('bidder_label') or ''} {raw_value.get('bid_stage') or ''} bid {value}".strip()
    if claim_type == "participation_count":
        return (
            f"{raw_value.get('process_stage') or ''} {raw_value.get('actor_class') or ''} "
            f"count {raw_value.get('count_min') or ''}-{raw_value.get('count_max') or ''}"
        ).strip()
    if claim_type == "event":
        return (
            f"{raw_value.get('event_date') or 'undated'} {raw_value.get('event_subtype') or ''} "
            f"{raw_value.get('actor_label') or ''}"
        ).strip()
    return json.dumps(raw_value, sort_keys=True)


def _claim_type_label(value: Any) -> str:
    if not value:
        return ""
    text = str(value)
    return text if text.endswith("_claim") else f"{text}_claim"


def _joined(evidence_rows: list[dict[str, Any]], key: str) -> str:
    return " | ".join(str(row.get(key)) for row in evidence_rows if row.get(key) not in (None, ""))


def _join_unique(values: Any) -> str:
    result = []
    for value in values:
        if value in (None, ""):
            continue
        text = str(value)
        if text not in result:
            result.append(text)
    return ",".join(result)


def _ordered(row: dict[str, Any]) -> dict[str, Any]:
    for field in RESOLUTION_FIELDS:
        row.setdefault(field, "")
    return {field: row.get(field, "") for field in REVIEW_ROW_FIELDS}


def _cell(value: Any) -> Any:
    return "" if value is None else value


def _numeric_cell(value: Any) -> Any:
    return None if value in (None, "") else value


def _event_sort_key(event: dict[str, Any]) -> tuple[bool, str, str]:
    event_date = event.get("event_date")
    return (event_date is None, event_date or "", event.get("event_id") or "")
