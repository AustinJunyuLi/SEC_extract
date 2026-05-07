from __future__ import annotations

from pipeline.deal_graph import (
    ALEX_EVENT_LEDGER_FIELDS,
    canonicalize_claim_payload,
    project_alex_event_ledger,
)
from pipeline.deal_graph.orchestrate import _bind_provider_evidence


def _refs(quote: str) -> list[dict]:
    return [{"citation_unit_id": "page_1_paragraph_1", "quote_text": quote}]


def _graph(payload: dict, *, deal_slug: str = "sample", run_id: str = "run-1") -> dict:
    quotes = []
    for claims in payload.values():
        for claim in claims:
            for ref in claim.get("evidence_refs", []):
                if ref["quote_text"] not in quotes:
                    quotes.append(ref["quote_text"])
    pages = [{"number": 1, "content": " ".join(quotes)}]
    return canonicalize_claim_payload(
        payload,
        deal_slug=deal_slug,
        run_id=run_id,
        evidence_context=_bind_provider_evidence(payload, slug=deal_slug, run_id=run_id, pages=pages),
    )


def test_alex_event_ledger_projects_event_relation_and_count_rows_only() -> None:
    graph = _graph(
        {
            "actor_claims": [
                {
                    "claim_type": "actor",
                    "coverage_obligation_id": "actor_party_a",
                    "actor_label": "Party A",
                    "actor_kind": "organization",
                    "observability": "anonymous_handle",
                    "actor_class": "financial",
                    "confidence": "high",
                    "evidence_refs": _refs("Party A was one of the parties contacted"),
                }
            ],
            "event_claims": [
                {
                    "claim_type": "event",
                    "coverage_obligation_id": "event_nda",
                    "event_type": "process",
                    "event_subtype": "nda_signed",
                    "event_date": "2014-01-03",
                    "description": "Party A signed a confidentiality agreement.",
                    "actor_label": "Party A",
                    "actor_role": "potential bidder",
                    "confidence": "high",
                    "evidence_refs": _refs("Party A signed a confidentiality agreement"),
                },
                {
                    "claim_type": "event",
                    "coverage_obligation_id": "event_drop",
                    "event_type": "process",
                    "event_subtype": "withdrawn_by_bidder",
                    "event_date": "2014-02-10",
                    "description": "Party A withdrew because value was below its prior indication.",
                    "actor_label": "Party A",
                    "actor_role": "bidder",
                    "confidence": "medium",
                    "evidence_refs": _refs("Party A withdrew because value was below its prior indication"),
                },
            ],
            "bid_claims": [
                {
                    "claim_type": "bid",
                    "coverage_obligation_id": "bid_party_a",
                    "bidder_label": "Party A",
                    "bid_date": "2014-02-01",
                    "bid_value": None,
                    "bid_value_lower": 10.0,
                    "bid_value_upper": 12.0,
                    "bid_value_unit": "per_share",
                    "consideration_type": "cash",
                    "bid_stage": "initial",
                    "confidence": "high",
                    "evidence_refs": _refs("Party A submitted an indication of interest of $10 to $12 per share"),
                }
            ],
            "actor_relation_claims": [
                {
                    "claim_type": "actor_relation",
                    "coverage_obligation_id": "advisor",
                    "subject_label": "Banker",
                    "object_label": "Sample Target",
                    "relation_type": "advises",
                    "role_detail": "financial advisor",
                    "effective_date_first": "2014-01-01",
                    "confidence": "high",
                    "evidence_refs": _refs("Sample Target retained Banker as financial advisor"),
                },
                {
                    "claim_type": "actor_relation",
                    "coverage_obligation_id": "committee_membership",
                    "subject_label": "Director A",
                    "object_label": "strategic committee",
                    "relation_type": "member_of",
                    "confidence": "high",
                    "evidence_refs": _refs("Director A served on the strategic committee"),
                }
            ],
            "participation_count_claims": [
                {
                    "claim_type": "participation_count",
                    "coverage_obligation_id": "count_contacted",
                    "process_stage": "contacted",
                    "actor_class": "financial",
                    "count_min": 5,
                    "count_max": 5,
                    "count_qualifier": "exact",
                    "confidence": "high",
                    "evidence_refs": _refs("Five financial sponsors were contacted"),
                }
            ],
        }
    )

    rows = project_alex_event_ledger(
        graph,
        deal_metadata={
            "TargetName": "Sample Target",
            "Acquirer": "Sample Acquirer",
            "DateAnnounced": "2014-03-01",
        },
    )

    assert tuple(rows[0]) == ALEX_EVENT_LEDGER_FIELDS
    assert "bidder_class" in ALEX_EVENT_LEDGER_FIELDS
    assert "bid_value" in ALEX_EVENT_LEDGER_FIELDS
    assert "bid_value_unit" in ALEX_EVENT_LEDGER_FIELDS
    assert ALEX_EVENT_LEDGER_FIELDS[17:21] == (
        "bid_value",
        "bid_value_lower",
        "bid_value_upper",
        "bid_value_unit",
    )
    assert [row["event_order"] for row in rows] == [10, 20, 30, 40, 50]
    assert [row["event_code"] for row in rows] == [
        "advisor_retained",
        "nda_signed",
        "bid_submitted",
        "bidder_withdrew",
        "participation_count",
    ]
    assert {row["event_family"] for row in rows} == {"advisor", "process", "bid", "dropout"}
    assert all(row["party_name"] != "" for row in rows)
    assert "actor_party_a" not in {row["source_claim_ids"] for row in rows}
    bid = next(row for row in rows if row["event_family"] == "bid")
    assert bid["bidder_class"] == "financial"
    assert bid["formality"] == "informal"
    assert bid["bid_value_lower"] == 10.0
    assert bid["bid_value_upper"] == 12.0
    assert bid["bid_value_unit"] == "per_share"
    assert bid["consideration_type"] == "cash"
    assert bid["evidence_quote_full"] == "Party A submitted an indication of interest of $10 to $12 per share"
    dropout = next(row for row in rows if row["event_family"] == "dropout")
    assert dropout["dropout_side"] == "bidder"
    assert dropout["dropout_reason"] == "below_prior_bid"
    assert dropout["needs_human_attention"] == 0
    count = next(row for row in rows if row["row_unit"] == "cohort")
    assert count["bidder_class"] == "financial"
    assert count["party_name"] == "5 financial parties"
    assert count["stage"] == "contacted"
    assert count["consideration_type"] == "not_applicable"
    advisor = next(row for row in rows if row["event_family"] == "advisor")
    assert advisor["bidder_class"] == "not_applicable"
    assert advisor["consideration_type"] == "not_applicable"


def test_alex_event_ledger_marks_low_confidence_and_review_rows_for_attention() -> None:
    graph = _graph(
        {
            "event_claims": [
                {
                    "claim_type": "event",
                    "coverage_obligation_id": "event_nonresponsive",
                    "event_type": "process",
                    "event_subtype": "non_responsive",
                    "event_date": None,
                    "description": "Party B did not respond.",
                    "actor_label": "Party B",
                    "actor_role": "potential bidder",
                    "confidence": "low",
                    "evidence_refs": _refs("Party B did not respond"),
                }
            ],
        }
    )

    rows = project_alex_event_ledger(graph)

    assert rows[0]["event_order"] == 10
    assert rows[0]["event_code"] == "no_response"
    assert rows[0]["dropout_side"] == "no_response"
    assert rows[0]["confidence"] == "low"
    assert rows[0]["needs_human_attention"] == 1
    assert rows[0]["date_precision"] == "unknown"


def test_alex_event_ledger_derives_contact_initiator_from_evidence_text() -> None:
    graph = _graph(
        {
            "event_claims": [
                {
                    "claim_type": "event",
                    "coverage_obligation_id": "event_target_contact",
                    "event_type": "process",
                    "event_subtype": "contact_initial",
                    "event_date": "2016-03-24",
                    "description": "The transaction committee authorized outreach to Party A.",
                    "actor_label": "Party A",
                    "actor_role": "potential bidder",
                    "confidence": "high",
                    "evidence_refs": _refs(
                        "The Transaction Committee authorized GHF to contact Party A as well as other potential buyers"
                    ),
                },
                {
                    "claim_type": "event",
                    "coverage_obligation_id": "event_bidder_contact",
                    "event_type": "process",
                    "event_subtype": "contact_initial",
                    "event_date": "2016-04-02",
                    "description": "Party B approached the Company.",
                    "actor_label": "Party B",
                    "actor_role": "potential bidder",
                    "confidence": "high",
                    "evidence_refs": _refs("Party B approached the Company regarding a possible transaction"),
                },
            ],
        }
    )

    rows = project_alex_event_ledger(graph)

    assert [row["initiated_by"] for row in rows] == ["target", "bidder"]


def test_alex_event_ledger_projects_enterprise_value_unit_and_unspecified_consideration() -> None:
    graph = _graph(
        {
            "actor_claims": [
                {
                    "claim_type": "actor",
                    "coverage_obligation_id": "actor_altus",
                    "actor_label": "Altus",
                    "actor_kind": "organization",
                    "observability": "named",
                    "actor_class": "financial",
                    "confidence": "high",
                    "evidence_refs": _refs("Altus manages and makes investments in middle market businesses"),
                }
            ],
            "bid_claims": [
                {
                    "claim_type": "bid",
                    "coverage_obligation_id": "bid_altus_revised",
                    "bidder_label": "Altus",
                    "bid_date": "2017-09-21",
                    "bid_value": 44000000.0,
                    "bid_value_lower": None,
                    "bid_value_upper": None,
                    "bid_value_unit": "enterprise_value",
                    "consideration_type": None,
                    "bid_stage": "revised",
                    "confidence": "high",
                    "evidence_refs": _refs(
                        "Altus increased its proposed valuation of the Company to $44,000,000 on a cash-free, debt-free basis"
                    ),
                }
            ],
        }
    )

    rows = project_alex_event_ledger(graph)

    assert len(rows) == 1
    assert rows[0]["event_family"] == "bid"
    assert rows[0]["bid_value"] == 44000000.0
    assert rows[0]["bid_value_lower"] is None
    assert rows[0]["bid_value_upper"] is None
    assert rows[0]["bid_value_unit"] == "enterprise_value"
    assert rows[0]["consideration_type"] == "unspecified"
