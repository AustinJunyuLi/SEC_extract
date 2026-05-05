from __future__ import annotations

import json
import sys

import pytest

from pipeline.deal_graph import canonicalize_claim_payload
from pipeline.deal_graph import project as project_cli
from pipeline.deal_graph.orchestrate import _bind_provider_evidence
from pipeline.deal_graph.project_estimation import project_estimation_rows


def _refs(quote: str) -> list[dict]:
    return [{"citation_unit_id": "page_1_paragraph_1", "quote_text": quote}]


def _graph(payload: dict, *, deal_slug: str = "sample", run_id: str = "run-1") -> dict:
    quotes = [
        ref["quote_text"]
        for family in payload.values()
        if isinstance(family, list)
        for claim in family
        for ref in claim.get("evidence_refs", [])
    ]
    pages = [{"number": 1, "content": " ".join(dict.fromkeys(quotes))}]
    return canonicalize_claim_payload(
        payload,
        deal_slug=deal_slug,
        run_id=run_id,
        evidence_context=_bind_provider_evidence(payload, slug=deal_slug, run_id=run_id, pages=pages),
    )


def test_estimation_projection_derives_initial_final_and_unknown_type() -> None:
    graph = _graph(
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
                    "evidence_refs": _refs("Party B proposed a range of $15.00 to $16.00 per share"),
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
                    "evidence_refs": _refs("Party B submitted a final proposal of $17.00 per share"),
                },
            ]
        }
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


def test_estimation_projection_uses_split_final_marker_for_last_bid() -> None:
    graph = _graph(
        {
            "event_claims": [
                {
                    "claim_type": "event",
                    "coverage_obligation_id": "obl_final_marker",
                    "event_type": "bid",
                    "event_subtype": "final_round_bid",
                    "event_date": "2015-02-10",
                    "description": "Party B was prepared to offer a final price.",
                    "actor_label": "Party B",
                    "actor_role": "bidder",
                    "confidence": "high",
                    "evidence_refs": _refs("Party B was prepared to offer a final price"),
                }
            ],
            "bid_claims": [
                {
                    "claim_type": "bid",
                    "coverage_obligation_id": "obl_bid_initial",
                    "bidder_label": "Party B",
                    "bid_date": "2015-01-02",
                    "bid_value": 15.0,
                    "bid_value_lower": None,
                    "bid_value_upper": None,
                    "bid_value_unit": "per_share",
                    "consideration_type": "cash",
                    "bid_stage": "initial",
                    "confidence": "high",
                    "evidence_refs": _refs("Party B proposed $15.00 per share"),
                },
                {
                    "claim_type": "bid",
                    "coverage_obligation_id": "obl_bid_later",
                    "bidder_label": "Party B",
                    "bid_date": "2015-02-10",
                    "bid_value": 17.0,
                    "bid_value_lower": None,
                    "bid_value_upper": None,
                    "bid_value_unit": "per_share",
                    "consideration_type": "cash",
                    "bid_stage": "revised",
                    "confidence": "high",
                    "evidence_refs": _refs("Party B proposed $17.00 per share"),
                },
            ],
        }
    )

    rows = project_estimation_rows(graph)

    assert len(rows) == 1
    assert rows[0]["actor_label"] == "Party B"
    assert rows[0]["bI"] == 15.0
    assert rows[0]["bF"] == 17.0
    assert rows[0]["admitted"] is True
    assert rows[0]["formal_boundary"] is True


def test_estimation_projection_uses_executed_merger_marker_for_acquirer_last_bid() -> None:
    graph = _graph(
        {
            "event_claims": [
                {
                    "claim_type": "event",
                    "coverage_obligation_id": "obl_execution",
                    "event_type": "transaction",
                    "event_subtype": "merger_agreement_executed",
                    "event_date": "2015-02-12",
                    "description": "Party B and the company executed the merger agreement.",
                    "actor_label": "Party B",
                    "actor_role": "acquirer",
                    "confidence": "high",
                    "evidence_refs": _refs("Party B and the company executed the merger agreement"),
                }
            ],
            "bid_claims": [
                {
                    "claim_type": "bid",
                    "coverage_obligation_id": "obl_bid_initial",
                    "bidder_label": "Party B",
                    "bid_date": "2015-01-02",
                    "bid_value": 15.0,
                    "bid_value_lower": None,
                    "bid_value_upper": None,
                    "bid_value_unit": "per_share",
                    "consideration_type": "cash",
                    "bid_stage": "initial",
                    "confidence": "high",
                    "evidence_refs": _refs("Party B proposed $15.00 per share"),
                },
                {
                    "claim_type": "bid",
                    "coverage_obligation_id": "obl_bid_revised",
                    "bidder_label": "Party B",
                    "bid_date": "2015-02-10",
                    "bid_value": 17.0,
                    "bid_value_lower": None,
                    "bid_value_upper": None,
                    "bid_value_unit": "per_share",
                    "consideration_type": "cash",
                    "bid_stage": "revised",
                    "confidence": "high",
                    "evidence_refs": _refs("Party B proposed $17.00 per share"),
                },
            ],
        }
    )

    rows = project_estimation_rows(graph)

    assert len(rows) == 1
    assert rows[0]["actor_label"] == "Party B"
    assert rows[0]["bI"] == 15.0
    assert rows[0]["bF"] == 17.0
    assert rows[0]["admitted"] is True
    assert rows[0]["formal_boundary"] is True


def test_projection_cli_blocks_invalid_snapshot(tmp_path, monkeypatch, capsys) -> None:
    graph = _graph(
        {
            "bid_claims": [
                {
                    "claim_type": "bid",
                    "coverage_obligation_id": "obl_bid_initial",
                    "bidder_label": "Party B",
                    "bid_date": "2015-01-02",
                    "bid_value": 15.0,
                    "bid_value_lower": None,
                    "bid_value_upper": None,
                    "bid_value_unit": "per_share",
                    "consideration_type": "cash",
                    "bid_stage": "initial",
                    "confidence": "high",
                    "evidence_refs": _refs("Party B proposed $15.00 per share"),
                }
            ]
        }
    )
    graph["claim_evidence"] = []
    snapshot = tmp_path / "deal_graph_v1.json"
    snapshot.write_text(json.dumps(graph))
    monkeypatch.setattr(sys, "argv", ["project", str(snapshot), "--projection", "estimation"])

    with pytest.raises(SystemExit) as exc:
        project_cli.main()

    assert exc.value.code == 1
    assert "projection blocked" in capsys.readouterr().err
