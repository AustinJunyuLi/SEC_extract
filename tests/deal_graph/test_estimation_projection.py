from __future__ import annotations

from pipeline.deal_graph import canonicalize_claim_payload
from pipeline.deal_graph.project_estimation import project_estimation_rows


def test_estimation_projection_derives_initial_final_and_unknown_type() -> None:
    graph = canonicalize_claim_payload(
        {
            "bid_claims": [
                {
                    "claim_type": "bid",
                    "coverage_obligation_id": "obl_bid_initial",
                    "bidder_label": "Party B",
                    "bid_date": "2015-01-02",
                    "bid_value": None,
                    "bid_value_lower": 15.0,
                    "bid_value_upper": 16.0,
                    "bid_value_unit": "per_share",
                    "consideration_type": "cash",
                    "bid_stage": "initial",
                    "confidence": "high",
                    "quote_text": "Party B proposed a range of $15.00 to $16.00 per share",
                },
                {
                    "claim_type": "bid",
                    "coverage_obligation_id": "obl_bid_final",
                    "bidder_label": "Party B",
                    "bid_date": "2015-02-10",
                    "bid_value": 17.0,
                    "bid_value_lower": None,
                    "bid_value_upper": None,
                    "bid_value_unit": "per_share",
                    "consideration_type": "cash",
                    "bid_stage": "final",
                    "confidence": "high",
                    "quote_text": "Party B submitted a final proposal of $17.00 per share",
                },
            ]
        },
        deal_slug="sample",
        run_id="run-1",
    )

    rows = project_estimation_rows(graph)

    assert len(rows) == 1
    assert rows[0]["actor_label"] == "Party B"
    assert rows[0]["bI"] is None
    assert rows[0]["bI_lo"] == 15.0
    assert rows[0]["bI_hi"] == 16.0
    assert rows[0]["bF"] == 17.0
    assert rows[0]["admitted"] is True
    assert rows[0]["T"] == "unknown"
    assert rows[0]["projection_rule_version"] == "bidder_cycle_baseline_v1"
