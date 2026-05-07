"""Alex-facing event-ledger projection from deal_graph_v2 snapshots."""
from __future__ import annotations

import re
from typing import Any

from .project_review import project_review_rows


ALEX_EVENT_LEDGER_FIELDS: tuple[str, ...] = (
    "deal_slug",
    "TargetName",
    "Acquirer",
    "DateAnnounced",
    "event_order",
    "event_date",
    "date_precision",
    "row_unit",
    "party_name",
    "bidder_class",
    "initiated_by",
    "event_family",
    "event_code",
    "stage",
    "formality",
    "dropout_side",
    "dropout_reason",
    "bid_value",
    "bid_value_lower",
    "bid_value_upper",
    "bid_value_unit",
    "consideration_type",
    "review_label",
    "evidence_page",
    "evidence_quote_full",
    "confidence",
    "needs_human_attention",
    "source_claim_ids",
)

EVENT_SUBTYPE_MAP: dict[str, dict[str, str]] = {
    "contact_initial": {"family": "contact", "code": "initial_contact", "stage": "pre_bid"},
    "nda_signed": {"family": "process", "code": "nda_signed", "stage": "nda"},
    "consortium_ca_signed": {"family": "consortium", "code": "consortium_ca_signed", "stage": "nda"},
    "ioi_submitted": {"family": "bid", "code": "ioi_submitted", "stage": "initial", "formality": "informal"},
    "first_round_bid": {"family": "bid", "code": "bid_submitted", "stage": "initial", "formality": "informal"},
    "final_round_bid": {"family": "bid", "code": "bid_submitted", "stage": "final_round", "formality": "formal"},
    "exclusivity_grant": {"family": "agreement", "code": "exclusivity_granted", "stage": "exclusivity"},
    "merger_agreement_executed": {"family": "agreement", "code": "merger_agreement_executed", "stage": "execution"},
    "withdrawn_by_bidder": {
        "family": "dropout",
        "code": "bidder_withdrew",
        "stage": "dropout",
        "dropout_side": "bidder",
    },
    "excluded_by_target": {
        "family": "dropout",
        "code": "target_excluded",
        "stage": "dropout",
        "dropout_side": "target",
    },
    "non_responsive": {
        "family": "dropout",
        "code": "no_response",
        "stage": "dropout",
        "dropout_side": "no_response",
    },
    "cohort_closure": {
        "family": "dropout",
        "code": "cohort_closed",
        "stage": "dropout",
        "dropout_side": "mixed_or_unknown",
    },
    "advancement_admitted": {"family": "advancement", "code": "advanced", "stage": "advancement"},
    "advancement_declined": {"family": "advancement", "code": "not_advanced", "stage": "advancement"},
    "rollover_executed": {"family": "support", "code": "rollover_executed", "stage": "support"},
    "financing_committed": {"family": "financing", "code": "financing_committed", "stage": "financing"},
    "go_shop_started": {"family": "go_shop", "code": "go_shop_started", "stage": "go_shop"},
    "go_shop_ended": {"family": "go_shop", "code": "go_shop_ended", "stage": "go_shop"},
}

RELATION_TYPE_MAP: dict[str, dict[str, str]] = {
    "advises": {"family": "advisor", "code": "advisor_retained", "stage": "process_setup"},
    "finances": {"family": "financing", "code": "financing_relation", "stage": "financing"},
    "supports": {"family": "support", "code": "support_agreement", "stage": "support"},
    "voting_support_for": {"family": "support", "code": "voting_support", "stage": "support"},
    "rollover_holder_for": {"family": "support", "code": "rollover_support", "stage": "support"},
    "joins_group": {"family": "consortium", "code": "joined_group", "stage": "consortium"},
    "exits_group": {"family": "consortium", "code": "exited_group", "stage": "consortium"},
}

EVENT_PRIORITY: dict[str, int] = {
    "advisor_retained": 10,
    "initial_contact": 20,
    "nda_signed": 30,
    "ioi_submitted": 40,
    "bid_submitted": 50,
    "advanced": 60,
    "not_advanced": 65,
    "target_excluded": 70,
    "bidder_withdrew": 75,
    "no_response": 80,
    "exclusivity_granted": 90,
    "financing_committed": 100,
    "merger_agreement_executed": 120,
    "participation_count": 900,
}


def project_alex_event_ledger(
    graph: dict[str, Any],
    *,
    deal_metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Project one graph snapshot into Alex's human-review event ledger."""
    metadata = _deal_metadata(graph, deal_metadata)
    review_rows = project_review_rows(graph)
    actors = {row.get("actor_id"): row for row in graph.get("actors", []) if row.get("actor_id")}
    relations = {row.get("relation_id"): row for row in graph.get("actor_relations", []) if row.get("relation_id")}
    projected: list[dict[str, Any]] = []

    for row in review_rows:
        if row.get("event_id"):
            projected.append(_project_event_row(row, metadata, actors))
        elif row.get("relation_id") and row.get("relation_type") in RELATION_TYPE_MAP:
            projected.append(_project_relation_row(row, metadata, actors, relations))
        elif row.get("participation_count_id"):
            projected.append(_project_count_row(row, metadata))

    projected.sort(key=_ledger_sort_key)
    for index, row in enumerate(projected, start=1):
        row["event_order"] = index * 10
    return [_ordered(row) for row in projected]


def _deal_metadata(graph: dict[str, Any], override: dict[str, Any] | None) -> dict[str, str]:
    deal = {}
    if isinstance(graph.get("deals"), list) and graph["deals"]:
        deal = graph["deals"][0] or {}
    metadata = {
        "deal_slug": graph.get("deal_slug") or deal.get("deal_slug") or "",
        "TargetName": deal.get("target_name") or "",
        "Acquirer": "",
        "DateAnnounced": _cell(deal.get("announcement_date")),
    }
    for key, value in (override or {}).items():
        if key in metadata or key in {"deal_slug"}:
            metadata[key] = _cell(value)
    return metadata


def _project_event_row(row: dict[str, Any], metadata: dict[str, str], actors: dict[str, dict[str, Any]]) -> dict[str, Any]:
    subtype = row.get("event_subtype") or ""
    spec = EVENT_SUBTYPE_MAP.get(subtype, {"family": "process", "code": subtype or "event", "stage": "unknown"})
    actor = actors.get(row.get("actor_id")) or {}
    family = spec["family"]
    code = spec["code"]
    formality = _formality(row, spec)
    evidence_text = row.get("bound_source_quote") or row.get("supplied_quote") or ""
    dropout_side = spec.get("dropout_side") or "not_applicable"
    party_name = row.get("actor_label") or metadata.get("TargetName") or "Deal process"
    return _base(
        metadata,
        row,
        row_unit=_row_unit_for_event(row),
        party_name=party_name,
        bidder_class=_bidder_class_for_row(row, actor),
        initiated_by=_initiated_by(row, family, evidence_text),
        event_family=family,
        event_code=code,
        stage=_stage(row, spec),
        formality=formality,
        dropout_side=dropout_side,
        dropout_reason=_dropout_reason(evidence_text, dropout_side),
        review_label=_review_label(code, party_name, row),
    )


def _project_relation_row(
    row: dict[str, Any],
    metadata: dict[str, str],
    actors: dict[str, dict[str, Any]],
    relations: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    relation_type = row.get("relation_type") or ""
    spec = RELATION_TYPE_MAP[relation_type]
    relation = relations.get(row.get("relation_id")) or {}
    actor = actors.get(row.get("subject_actor_id")) or actors.get(row.get("actor_id")) or {}
    subject = row.get("subject_actor_label") or row.get("actor_label") or "Related party"
    target = row.get("object_actor_label") or metadata.get("TargetName") or "deal party"
    projected = _base(
        metadata,
        row,
        event_date=_cell(relation.get("effective_date_first")),
        row_unit="cohort" if relation_type in {"joins_group", "exits_group"} else "bidder",
        party_name=subject,
        bidder_class=_bidder_class_for_relation(relation_type, actor),
        initiated_by="not_applicable",
        event_family=spec["family"],
        event_code=spec["code"],
        stage=spec["stage"],
        formality="not_applicable",
        dropout_side="not_applicable",
        dropout_reason="not_applicable",
        review_label=f"{_humanize(spec['code'])}: {subject} / {target}",
    )
    return projected


def _project_count_row(row: dict[str, Any], metadata: dict[str, str]) -> dict[str, Any]:
    actor_class = row.get("actor_class") or "unknown"
    party_name = _count_party_name(row)
    return _base(
        metadata,
        row,
        row_unit="cohort",
        party_name=party_name,
        bidder_class=actor_class,
        initiated_by="not_applicable",
        event_family="process",
        event_code="participation_count",
        stage=row.get("process_stage") or "unknown",
        formality="not_applicable",
        dropout_side="not_applicable",
        dropout_reason="not_applicable",
        review_label=f"{_humanize(row.get('process_stage') or 'process')} count: {party_name}",
    )


def _base(
    metadata: dict[str, str],
    source: dict[str, Any],
    *,
    row_unit: str,
    party_name: str,
    bidder_class: str,
    initiated_by: str,
    event_family: str,
    event_code: str,
    stage: str,
    formality: str,
    dropout_side: str,
    dropout_reason: str,
    review_label: str,
    event_date: str | None = None,
) -> dict[str, Any]:
    date = _cell(event_date if event_date is not None else source.get("event_date"))
    confidence = source.get("confidence") or ""
    return {
        "deal_slug": metadata.get("deal_slug") or source.get("deal_slug") or "",
        "TargetName": metadata.get("TargetName") or "",
        "Acquirer": metadata.get("Acquirer") or "",
        "DateAnnounced": metadata.get("DateAnnounced") or "",
        "event_order": 0,
        "event_date": date,
        "date_precision": _date_precision(date),
        "row_unit": row_unit,
        "party_name": party_name,
        "bidder_class": bidder_class,
        "initiated_by": initiated_by,
        "event_family": event_family,
        "event_code": event_code,
        "stage": stage,
        "formality": formality,
        "dropout_side": dropout_side,
        "dropout_reason": dropout_reason,
        "bid_value": source.get("bid_value"),
        "bid_value_lower": source.get("bid_value_lower"),
        "bid_value_upper": source.get("bid_value_upper"),
        "bid_value_unit": _bid_value_unit(source, event_family),
        "consideration_type": _consideration_type(source, event_family),
        "review_label": review_label,
        "evidence_page": source.get("bound_source_page") or "",
        "evidence_quote_full": source.get("bound_source_quote") or source.get("supplied_quote") or "",
        "confidence": confidence,
        "needs_human_attention": _needs_human_attention(source, confidence),
        "source_claim_ids": source.get("claim_id") or "",
    }


def _ordered(row: dict[str, Any]) -> dict[str, Any]:
    return {field: row.get(field, "") for field in ALEX_EVENT_LEDGER_FIELDS}


def _cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _date_precision(value: str) -> str:
    if not value:
        return "unknown"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return "exact"
    if re.fullmatch(r"\d{4}-\d{2}", value):
        return "month"
    if re.fullmatch(r"\d{4}", value):
        return "year"
    return "rough"


def _bid_value_unit(source: dict[str, Any], event_family: str) -> str:
    if event_family != "bid" or not _has_bid_value(source):
        return "not_applicable"
    return source.get("bid_value_unit") or "unspecified"


def _consideration_type(source: dict[str, Any], event_family: str) -> str:
    if event_family != "bid":
        return "not_applicable"
    return source.get("consideration_type") or "unspecified"


def _has_bid_value(source: dict[str, Any]) -> bool:
    return any(source.get(field) not in (None, "") for field in ("bid_value", "bid_value_lower", "bid_value_upper"))


def _row_unit_for_event(row: dict[str, Any]) -> str:
    if row.get("actor_kind") == "cohort" or _looks_cohort(row.get("actor_label")):
        return "cohort"
    if row.get("actor_label"):
        return "bidder"
    return "deal"


def _bidder_class_for_row(row: dict[str, Any], actor: dict[str, Any]) -> str:
    if _row_unit_for_event(row) not in {"bidder", "cohort"}:
        return "not_applicable"
    return _bidder_class(actor.get("bidder_class"))


def _bidder_class_for_relation(relation_type: str, actor: dict[str, Any]) -> str:
    if relation_type in {"advises"}:
        return "not_applicable"
    return _bidder_class(actor.get("bidder_class"))


def _bidder_class(value: Any) -> str:
    if value in {"financial", "strategic", "mixed", "unknown"}:
        return str(value)
    return "unknown"


def _stage(row: dict[str, Any], spec: dict[str, str]) -> str:
    if row.get("bid_stage") == "final":
        return "final_round"
    return row.get("bid_stage") or spec.get("stage") or "unknown"


def _formality(row: dict[str, Any], spec: dict[str, str]) -> str:
    if spec.get("formality"):
        if row.get("event_subtype") == "first_round_bid" and _is_range_bid(row):
            return "informal"
        return spec["formality"]
    if row.get("bid_stage") == "final":
        return "formal"
    return "not_applicable"


def _is_range_bid(row: dict[str, Any]) -> bool:
    lower = row.get("bid_value_lower")
    upper = row.get("bid_value_upper")
    return lower not in (None, "") and upper not in (None, "") and lower != upper


def _initiated_by(row: dict[str, Any], family: str, evidence_text: str) -> str:
    text = evidence_text.lower()
    if "activist" in text:
        return "activist_shareholder"
    if family == "bid":
        bidder_verbs = (
            "unsolicited",
            "submitted",
            "delivered",
            "made a proposal",
            "made an offer",
            "offered",
        )
        return "bidder" if any(term in text for term in bidder_verbs) else "unknown"
    if row.get("event_subtype") == "contact_initial":
        if "approached" in text or "unsolicited" in text:
            return "bidder"
        if "contacted the company" in text or "contacted representatives of the company" in text:
            return "bidder"
        if any(term in text for term in ("authorized", "instructed", "directed")) and any(
            term in text for term in ("contact", "solicit")
        ):
            return "target"
        target_contact_phrases = (
            "the company contacted",
            "company contacted",
            "the board contacted",
            "board contacted",
            "committee contacted",
            "management contacted",
            "representatives of the company contacted",
            "reached out to",
        )
        if any(term in text for term in target_contact_phrases):
            return "target"
        if "contacted" in text and "representatives" in text:
            return "advisor"
        return "unknown"
    return "not_applicable"


def _dropout_reason(evidence_text: str, dropout_side: str) -> str:
    if dropout_side == "not_applicable":
        return "not_applicable"
    text = evidence_text.lower()
    if "below" in text and ("prior" in text or "earlier" in text or "indication" in text):
        return "below_prior_bid"
    if "market value" in text or "market price" in text:
        return "below_market"
    if "strategic fit" in text:
        return "strategic_fit"
    if "financ" in text:
        return "financing"
    if "valuation" in text or "price" in text or "premium" in text:
        return "valuation"
    if "confidential" in text or "leak" in text:
        return "confidentiality"
    return "unknown"


def _review_label(code: str, party_name: str, row: dict[str, Any]) -> str:
    if code == "bid_submitted":
        value = _bid_value_label(row)
        return f"{party_name} submitted {row.get('bid_stage') or 'unspecified'} bid{value}"
    if code == "ioi_submitted":
        return f"{party_name} submitted indication of interest"
    if code == "nda_signed":
        return f"{party_name} signed NDA"
    if code == "bidder_withdrew":
        return f"{party_name} withdrew from process"
    if code == "target_excluded":
        return f"Target excluded {party_name}"
    if code == "no_response":
        return f"{party_name} did not respond or proceed"
    return f"{_humanize(code)}: {party_name}"


def _bid_value_label(row: dict[str, Any]) -> str:
    value = row.get("bid_value")
    lower = row.get("bid_value_lower")
    upper = row.get("bid_value_upper")
    if value not in (None, ""):
        return f" ({value})"
    if lower not in (None, "") or upper not in (None, ""):
        return f" ({lower or ''}-{upper or ''})"
    return ""


def _count_party_name(row: dict[str, Any]) -> str:
    count_min = row.get("count_min")
    count_max = row.get("count_max")
    actor_class = row.get("actor_class") or "unknown"
    if count_min not in (None, "") and count_min == count_max:
        count = str(int(count_min)) if isinstance(count_min, float) and count_min.is_integer() else str(count_min)
    elif count_min not in (None, "") or count_max not in (None, ""):
        count = f"{count_min or ''}-{count_max or ''}"
    else:
        count = "unknown number of"
    return f"{count} {actor_class} parties"


def _needs_human_attention(row: dict[str, Any], confidence: Any) -> int:
    if row.get("review_status") not in ("", "clean"):
        return 1
    if confidence == "low":
        return 1
    if not row.get("bound_source_quote") and not row.get("supplied_quote"):
        return 1
    return 0


def _ledger_sort_key(row: dict[str, Any]) -> tuple[bool, str, int, str, str]:
    date = row.get("event_date") or ""
    return (
        not bool(date),
        date,
        EVENT_PRIORITY.get(row.get("event_code") or "", 500),
        row.get("party_name") or "",
        row.get("source_claim_ids") or "",
    )


def _humanize(value: str) -> str:
    return value.replace("_", " ").strip().title()


def _looks_cohort(label: Any) -> bool:
    text = str(label or "").lower()
    cohort_words = ("parties", "bidders", "buyers", "sponsors", "companies", "remaining")
    return any(word in text for word in cohort_words)
