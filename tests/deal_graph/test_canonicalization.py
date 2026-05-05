from __future__ import annotations

import pytest

from pipeline.deal_graph import canonicalize_claim_payload, validate_graph


def test_canonicalization_builds_group_relation_event_and_evidence() -> None:
    graph = canonicalize_claim_payload(_mac_gray_payload(), deal_slug="mac-gray", run_id="run-1")

    actors = {row["actor_label"]: row for row in graph["actors"]}
    assert actors["CSC/Pamplona"]["actor_kind"] == "group"
    assert actors["CSC/Pamplona"]["has_strategic_member"] is True
    assert actors["CSC/Pamplona"]["has_financial_member"] is True

    relations = {
        (row["subject_actor_label"], row["object_actor_label"], row["relation_type"])
        for row in graph["actor_relations"]
    }
    assert ("CSC", "CSC/Pamplona", "member_of") in relations
    assert ("Pamplona", "CSC/Pamplona", "member_of") in relations
    assert ("Pamplona", "CSC/Pamplona", "finances") in relations

    bid_links = [
        row for row in graph["event_actor_links"]
        if row["role"] == "bid_submitter" and row["actor_label"] == "CSC/Pamplona"
    ]
    assert len(bid_links) == 2
    assert not validate_graph(graph)


def test_portfolio_company_member_signal_projects_group_as_strategic() -> None:
    payload = {
        "actor_claims": [
            {
                "claim_type": "actor",
                "coverage_obligation_id": "obl_actor_group",
                "actor_label": "CSC/Pamplona",
                "actor_kind": "group",
                "observability": "named",
                "confidence": "high",
                "quote_text": "CSC and Pamplona, who together we refer to as CSC/Pamplona",
            }
        ],
        "actor_relation_claims": [
            {
                "claim_type": "actor_relation",
                "coverage_obligation_id": "obl_relation_csc",
                "subject_label": "CSC",
                "object_label": "CSC/Pamplona",
                "relation_type": "member_of",
                "role_detail": None,
                "effective_date_first": None,
                "confidence": "high",
                "quote_text": "CSC and Pamplona, who together we refer to as CSC/Pamplona",
            },
            {
                "claim_type": "actor_relation",
                "coverage_obligation_id": "obl_relation_pamplona",
                "subject_label": "Pamplona",
                "object_label": "CSC/Pamplona",
                "relation_type": "member_of",
                "role_detail": None,
                "effective_date_first": None,
                "confidence": "high",
                "quote_text": "CSC and Pamplona, who together we refer to as CSC/Pamplona",
            },
            {
                "claim_type": "actor_relation",
                "coverage_obligation_id": "obl_relation_csc_portfolio_company",
                "subject_label": "CSC",
                "object_label": "Pamplona",
                "relation_type": "affiliate_of",
                "role_detail": "portfolio company",
                "effective_date_first": None,
                "confidence": "high",
                "quote_text": "acquisition of Mac-Gray by its portfolio company, CSC",
            },
            {
                "claim_type": "actor_relation",
                "coverage_obligation_id": "obl_relation_financing",
                "subject_label": "Pamplona",
                "object_label": "CSC/Pamplona",
                "relation_type": "finances",
                "role_detail": "committed financing capital",
                "effective_date_first": None,
                "confidence": "high",
                "quote_text": "Pamplona was committed to provide 100% of the capital",
            },
        ],
    }

    graph = canonicalize_claim_payload(payload, deal_slug="mac-gray", run_id="run-1")
    actors = {row["actor_label"]: row for row in graph["actors"]}

    assert actors["CSC"]["bidder_class"] == "strategic"
    assert actors["CSC/Pamplona"]["has_strategic_member"] is True
    assert actors["CSC/Pamplona"]["bidder_class"] == "strategic"


def test_rejects_provider_owned_projection_and_old_fields() -> None:
    with pytest.raises(ValueError, match="Python-owned"):
        canonicalize_claim_payload(
            {"actor_claims": [], "coverage_results": [], "BidderID": 1},
            deal_slug="bad",
        )


def test_validation_flags_missing_disposition_evidence_and_coverage() -> None:
    graph = canonicalize_claim_payload(_mac_gray_payload(), deal_slug="mac-gray", run_id="run-1")
    first_claim = graph["claims"][0]["claim_id"]
    graph["claim_dispositions"] = [row for row in graph["claim_dispositions"] if row["claim_id"] != first_claim]
    graph["claim_evidence"] = [row for row in graph["claim_evidence"] if row["claim_id"] != first_claim]
    graph["coverage_results"] = []

    codes = {flag.code for flag in validate_graph(graph)}
    assert "DG_CLAIM_DISPOSITION_MISSING" in codes
    assert "DG_CLAIM_EVIDENCE_MISSING" in codes
    assert "DG_COVERAGE_RESULT_MISSING" in codes


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
                "quote_text": "CSC and Pamplona, who together we refer to as CSC/Pamplona",
            },
            {
                "claim_type": "actor",
                "coverage_obligation_id": "obl_actor_csc",
                "actor_label": "CSC",
                "actor_kind": "organization",
                "observability": "named",
                "actor_class": "strategic",
                "confidence": "high",
                "quote_text": "CSC was an operating strategic buyer in the process",
            },
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
                "quote_text": "CSC and Pamplona, who together we refer to as CSC/Pamplona",
            },
            {
                "claim_type": "actor_relation",
                "coverage_obligation_id": "obl_relation_pamplona",
                "subject_label": "Pamplona",
                "object_label": "CSC/Pamplona",
                "relation_type": "member_of",
                "role_detail": "financial sponsor",
                "effective_date_first": "2013-08-01",
                "confidence": "high",
                "quote_text": "CSC and Pamplona, who together we refer to as CSC/Pamplona",
            },
            {
                "claim_type": "actor_relation",
                "coverage_obligation_id": "obl_relation_financing",
                "subject_label": "Pamplona",
                "object_label": "CSC/Pamplona",
                "relation_type": "finances",
                "role_detail": "financing capital provider",
                "effective_date_first": "2013-08-01",
                "confidence": "high",
                "quote_text": "Pamplona would provide financing capital to CSC/Pamplona",
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
                "quote_text": "CSC/Pamplona submitted an indication of interest at $18.50 per share",
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
                "quote_text": "CSC/Pamplona submitted a final proposal of $21.25 per share",
            },
        ],
    }
