from __future__ import annotations

from pipeline.deal_graph import canonicalize_claim_payload
from pipeline.deal_graph.orchestrate import _bind_provider_evidence
from pipeline.deal_graph.project_review import project_review_rows


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


def test_review_projection_renders_source_backed_event_rows() -> None:
    graph = _graph(
        {
            "event_claims": [
                {
                    "claim_type": "event",
                    "coverage_obligation_id": "obl_nda",
                    "event_type": "process",
                    "event_subtype": "nda_signed",
                    "event_date": "2014-01-03",
                    "description": "Party A signed a confidentiality agreement.",
                    "actor_label": "Party A",
                    "actor_role": "potential_buyer",
                    "confidence": "high",
                    "evidence_refs": _refs("Party A signed a confidentiality agreement with the Company"),
                }
            ],
            "bid_claims": [
                {
                    "claim_type": "bid",
                    "coverage_obligation_id": "obl_bid",
                    "bidder_label": "Party A",
                    "bid_date": "2014-02-01",
                    "bid_value": 10.0,
                    "bid_value_lower": None,
                    "bid_value_upper": None,
                    "bid_value_unit": "per_share",
                    "consideration_type": "cash",
                    "bid_stage": "initial",
                    "confidence": "high",
                    "evidence_refs": _refs("Party A submitted an initial proposal of $10.00 per share"),
                }
            ],
        }
    )

    rows = [row for row in project_review_rows(graph) if row["event_id"]]

    assert [row["event_subtype"] for row in rows] == ["nda_signed", "first_round_bid"]
    assert rows[0]["actor_label"] == "Party A"
    assert rows[0]["review_status"] == "clean"
    assert rows[0]["claim_type"] == "event_claim"
    assert rows[0]["bound_source_quote"] == "Party A signed a confidentiality agreement with the Company"
    assert rows[1]["bid_value"] == 10.0
    assert rows[1]["actor_role"] == "bid_submitter"


def test_review_projection_preserves_multi_span_source_lists() -> None:
    graph = _graph(
        {
            "event_claims": [
                {
                    "claim_type": "event",
                    "coverage_obligation_id": "obl_rollover",
                    "event_type": "process",
                    "event_subtype": "rollover_executed",
                    "event_date": "2014-12-14",
                    "description": "Longview rollover support was executed.",
                    "actor_label": "Longview",
                    "actor_role": "rollover_holder",
                    "confidence": "high",
                    "evidence_refs": _refs("Longview agreed to rollover"),
                }
            ],
        }
    )
    event_id = graph["events"][0]["event_id"]
    graph["evidence"] = [
        {"evidence_id": "ev_1", "quote_text": "Longview agreed to rollover", "source_page": 23},
        {"evidence_id": "ev_2", "quote_text": "remain outstanding as equity", "source_page": 24},
    ]
    graph["row_evidence"] = [
        {"row_table": "events", "row_id": event_id, "evidence_id": "ev_1", "ordinal": 1},
        {"row_table": "events", "row_id": event_id, "evidence_id": "ev_2", "ordinal": 2},
    ]

    rows = [row for row in project_review_rows(graph) if row["event_id"]]

    assert rows[0]["bound_source_quote"] == "Longview agreed to rollover | remain outstanding as equity"
    assert rows[0]["bound_source_page"] == "23 | 24"


def test_review_projection_includes_binding_diagnostic_subcode() -> None:
    graph = _graph(
        {
            "event_claims": [
                {
                    "claim_type": "event",
                    "coverage_obligation_id": "obl_nda",
                    "event_type": "process",
                    "event_subtype": "nda_signed",
                    "event_date": "2014-01-03",
                    "description": "Party A signed a confidentiality agreement.",
                    "actor_label": "Party A",
                    "actor_role": "potential_buyer",
                    "confidence": "high",
                    "evidence_refs": _refs("Party A signed a confidentiality agreement"),
                }
            ],
        }
    )
    event_id = graph["events"][0]["event_id"]
    graph["review_flags"] = [
        {
            "flag_id": "flag_1",
            "run_id": "run-1",
            "deal_id": None,
            "severity": "soft",
            "code": "evidence_ref_binding_failed",
            "reason": "MissingQuoteError: quote_text is not an exact substring",
            "row_table": "events",
            "row_id": event_id,
            "status": "open",
            "current": True,
            "metadata": {
                "diagnostic_subcode": "cross_unit_quote_stitching",
                "suggested_action": "Split the quote into exact per-unit evidence refs.",
                "evidence_ref_index": 0,
            },
        }
    ]

    rows = [row for row in project_review_rows(graph) if row["event_id"]]

    assert rows[0]["review_status"] == "needs_review"
    assert rows[0]["issue_codes"] == "evidence_ref_binding_failed; cross_unit_quote_stitching"
    assert rows[0]["suggested_action"] == "Split the quote into exact per-unit evidence refs."
