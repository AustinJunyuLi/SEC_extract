from __future__ import annotations

from pipeline.deal_graph import canonicalize_claim_payload
from pipeline.deal_graph.project_review import project_review_rows


def test_review_projection_renders_source_backed_event_rows() -> None:
    graph = canonicalize_claim_payload(
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
                    "quote_text": "Party A signed a confidentiality agreement with the Company",
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
                    "quote_text": "Party A submitted an initial proposal of $10.00 per share",
                }
            ],
        },
        deal_slug="sample",
        run_id="run-1",
    )

    rows = project_review_rows(graph)

    assert [row["event_subtype"] for row in rows] == ["nda_signed", "first_round_bid"]
    assert rows[0]["actor_label"] == "Party A"
    assert rows[0]["source_quote"] == "Party A signed a confidentiality agreement with the Company"
    assert rows[1]["bid_value"] == 10.0
    assert rows[1]["actor_role"] == "bid_submitter"


def test_review_projection_preserves_multi_span_source_lists() -> None:
    graph = canonicalize_claim_payload(
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
                    "quote_text": "Longview agreed to rollover",
                }
            ],
        },
        deal_slug="sample",
        run_id="run-1",
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

    rows = project_review_rows(graph)

    assert rows[0]["source_quote"] == [
        "Longview agreed to rollover",
        "remain outstanding as equity",
    ]
    assert rows[0]["source_page"] == [23, 24]
