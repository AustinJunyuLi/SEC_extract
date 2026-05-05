from __future__ import annotations

from pipeline.deal_graph import canonicalize_claim_payload
from pipeline.deal_graph.orchestrate import _bind_provider_evidence
from pipeline.deal_graph.project_estimation import project_estimation_rows


def _refs(quote: str) -> list[dict]:
    return [{"citation_unit_id": "page_1_paragraph_1", "quote_text": quote}]


def _graph(payload: dict, *, deal_slug: str) -> dict:
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
        run_id="run-1",
        evidence_context=_bind_provider_evidence(payload, slug=deal_slug, run_id="run-1", pages=pages),
    )


def test_mac_gray_projects_one_csc_pamplona_bidder_row_without_member_atomization() -> None:
    graph = _graph(_mac_gray_payload(), deal_slug="mac-gray")

    rows = project_estimation_rows(graph)

    assert [row["actor_label"] for row in rows] == ["CSC/Pamplona"]
    row = rows[0]
    assert row["bI"] == 18.5
    assert row["bF"] == 21.25
    assert row["T"] == "strategic"
    assert row["formal_boundary"] is True
    assert {actor["actor_label"] for actor in graph["actors"]} >= {"CSC", "Pamplona", "CSC/Pamplona"}


def test_petsmart_buyer_group_bid_not_atomized_to_longview() -> None:
    graph = _graph(_petsmart_payload(), deal_slug="petsmart-inc")

    rows = project_estimation_rows(graph)

    assert [row["actor_label"] for row in rows] == ["Buyer Group"]
    assert rows[0]["bF"] == 83.0
    assert rows[0]["T"] == "financial"
    longview = next(actor for actor in graph["actors"] if actor["actor_label"] == "Longview")
    assert longview["actor_kind"] == "organization"


def _mac_gray_payload() -> dict:
    return {
        "actor_claims": [
            {
                "claim_type": "actor",
                "coverage_obligation_id": "obl_actor_group",
                "actor_label": "CSC/Pamplona",
                "actor_kind": "group",
                "observability": "named",
                "confidence": "high",
                "evidence_refs": _refs("CSC and Pamplona, who together we refer to as CSC/Pamplona"),
            }
        ],
        "actor_relation_claims": [
            {
                "claim_type": "actor_relation",
                "coverage_obligation_id": "obl_relation_csc",
                "subject_label": "CSC",
                "object_label": "CSC/Pamplona",
                "relation_type": "member_of",
                "role_detail": "operating strategic buyer",
                "effective_date_first": "2013-08-01",
                "confidence": "high",
                "evidence_refs": _refs("CSC and Pamplona, who together we refer to as CSC/Pamplona"),
            },
            {
                "claim_type": "actor_relation",
                "coverage_obligation_id": "obl_relation_pamplona",
                "subject_label": "Pamplona",
                "object_label": "CSC/Pamplona",
                "relation_type": "finances",
                "role_detail": "financing capital provider",
                "effective_date_first": "2013-08-01",
                "confidence": "high",
                "evidence_refs": _refs("Pamplona would provide financing capital to CSC/Pamplona"),
            },
        ],
        "bid_claims": [
            {
                "claim_type": "bid",
                "coverage_obligation_id": "obl_bid_initial",
                "bidder_label": "CSC/Pamplona",
                "bid_date": "2013-09-15",
                "bid_value": 18.5,
                "bid_value_lower": None,
                "bid_value_upper": None,
                "bid_value_unit": "per_share",
                "consideration_type": "cash",
                "bid_stage": "initial",
                "confidence": "high",
                "evidence_refs": _refs("CSC/Pamplona submitted an indication of interest at $18.50 per share"),
            },
            {
                "claim_type": "bid",
                "coverage_obligation_id": "obl_bid_final",
                "bidder_label": "CSC/Pamplona",
                "bid_date": "2013-10-10",
                "bid_value": 21.25,
                "bid_value_lower": None,
                "bid_value_upper": None,
                "bid_value_unit": "per_share",
                "consideration_type": "cash",
                "bid_stage": "final",
                "confidence": "high",
                "evidence_refs": _refs("CSC/Pamplona submitted a final proposal of $21.25 per share"),
            },
        ],
    }


def _petsmart_payload() -> dict:
    return {
        "actor_claims": [
            {
                "claim_type": "actor",
                "coverage_obligation_id": "obl_actor_buyer_group",
                "actor_label": "Buyer Group",
                "actor_kind": "group",
                "observability": "named",
                "confidence": "high",
                "evidence_refs": _refs("BC Partners and its co-investors formed the Buyer Group"),
            }
        ],
        "actor_relation_claims": [
            {
                "claim_type": "actor_relation",
                "coverage_obligation_id": "obl_relation_longview",
                "subject_label": "Longview",
                "object_label": "Buyer Group",
                "relation_type": "joins_group",
                "role_detail": "rollover investor",
                "effective_date_first": "2014-12-13",
                "confidence": "high",
                "evidence_refs": _refs("Longview agreed to join the Buyer Group on December 13, 2014"),
            },
            {
                "claim_type": "actor_relation",
                "coverage_obligation_id": "obl_relation_sponsor",
                "subject_label": "BC Partners",
                "object_label": "Buyer Group",
                "relation_type": "member_of",
                "role_detail": "financial sponsor",
                "effective_date_first": "2014-12-01",
                "confidence": "high",
                "evidence_refs": _refs("BC Partners and its co-investors formed the Buyer Group"),
            },
        ],
        "bid_claims": [
            {
                "claim_type": "bid",
                "coverage_obligation_id": "obl_bid_final",
                "bidder_label": "Buyer Group",
                "bid_date": "2014-12-14",
                "bid_value": 83.0,
                "bid_value_lower": None,
                "bid_value_upper": None,
                "bid_value_unit": "per_share",
                "consideration_type": "cash",
                "bid_stage": "final",
                "confidence": "high",
                "evidence_refs": _refs("The Buyer Group submitted a final proposal of $83.00 per share"),
            }
        ],
    }
