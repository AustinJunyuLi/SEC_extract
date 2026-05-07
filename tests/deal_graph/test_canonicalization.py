from __future__ import annotations

import pytest

from pipeline.deal_graph import canonicalize_claim_payload, validate_graph
from pipeline.deal_graph.ids import make_id
from pipeline.deal_graph.orchestrate import _bind_provider_evidence
from pipeline.deal_graph.project_review import project_review_rows
from pipeline.deal_graph.store import DealGraphStore


def _refs(quote: str) -> list[dict]:
    return [{"citation_unit_id": "page_1_paragraph_1", "quote_text": quote}]


def _graph(
    payload: dict,
    *,
    deal_slug: str = "mac-gray",
    run_id: str = "run-1",
    target_name: str | None = None,
) -> dict:
    quotes: list[str] = []
    for family in (
        "actor_claims",
        "actor_relation_claims",
        "event_claims",
        "bid_claims",
        "participation_count_claims",
    ):
        for claim in payload.get(family, []) or []:
            for ref in claim.get("evidence_refs", []) or []:
                quote = ref["quote_text"]
                if quote not in quotes:
                    quotes.append(quote)
    pages = [{"number": 1, "content": " ".join(quotes)}]
    return canonicalize_claim_payload(
        payload,
        deal_slug=deal_slug,
        run_id=run_id,
        target_name=target_name,
        evidence_context=_bind_provider_evidence(payload, slug=deal_slug, run_id=run_id, pages=pages),
    )


def test_canonicalization_builds_group_relation_event_and_evidence() -> None:
    graph = _graph(_mac_gray_payload())

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
                "actor_class": "unknown",
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
                "role_detail": None,
                "effective_date_first": None,
                "confidence": "high",
                "evidence_refs": _refs("CSC and Pamplona, who together we refer to as CSC/Pamplona"),
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
                "evidence_refs": _refs("CSC and Pamplona, who together we refer to as CSC/Pamplona"),
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
                "evidence_refs": _refs("acquisition of Mac-Gray by its portfolio company, CSC"),
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
                "evidence_refs": _refs("Pamplona was committed to provide 100% of the capital"),
            },
        ],
    }

    graph = _graph(payload)
    actors = {row["actor_label"]: row for row in graph["actors"]}

    assert actors["CSC"]["bidder_class"] == "strategic"
    assert actors["CSC/Pamplona"]["has_strategic_member"] is True
    assert actors["CSC/Pamplona"]["bidder_class"] == "strategic"


def test_actor_claim_class_is_primary_and_relation_role_text_cannot_overwrite_it() -> None:
    payload = {
        "actor_claims": [
            {
                "claim_type": "actor",
                "coverage_obligation_id": "obl_actor_strategic",
                "actor_label": "Party A",
                "actor_kind": "organization",
                "observability": "anonymous_handle",
                "actor_class": "strategic",
                "confidence": "high",
                "evidence_refs": _refs("Party A was a strategic bidder"),
            },
            {
                "claim_type": "actor",
                "coverage_obligation_id": "obl_actor_mixed",
                "actor_label": "Buyer Group",
                "actor_kind": "group",
                "observability": "named",
                "actor_class": "mixed",
                "confidence": "high",
                "evidence_refs": _refs("Buyer Group consisted of a strategic buyer and a financial sponsor"),
            },
        ],
        "actor_relation_claims": [
            {
                "claim_type": "actor_relation",
                "coverage_obligation_id": "obl_relation_financing_noise",
                "subject_label": "Party A",
                "object_label": "Buyer Group",
                "relation_type": "finances",
                "role_detail": "financial sponsor",
                "effective_date_first": None,
                "confidence": "high",
                "evidence_refs": _refs("Party A provided financing to Buyer Group"),
            },
            {
                "claim_type": "actor_relation",
                "coverage_obligation_id": "obl_relation_strategic_member",
                "subject_label": "Party A",
                "object_label": "Buyer Group",
                "relation_type": "member_of",
                "role_detail": "strategic buyer",
                "effective_date_first": None,
                "confidence": "high",
                "evidence_refs": _refs("Party A was a strategic member of Buyer Group"),
            },
        ],
    }

    graph = _graph(payload)
    actors = {row["actor_label"]: row for row in graph["actors"]}

    assert actors["Party A"]["bidder_class"] == "strategic"
    assert actors["Buyer Group"]["bidder_class"] == "mixed"


def test_rejects_provider_owned_projection_and_old_fields() -> None:
    with pytest.raises(ValueError, match="Python-owned"):
        canonicalize_claim_payload(
            {"actor_claims": [], "coverage_results": [], "BidderID": 1},
            deal_slug="bad",
        )


def test_validation_flags_missing_disposition_evidence_and_coverage() -> None:
    graph = _graph(_mac_gray_payload())
    first_claim = graph["claims"][0]["claim_id"]
    graph["claim_dispositions"] = [row for row in graph["claim_dispositions"] if row["claim_id"] != first_claim]
    graph["claim_evidence"] = [row for row in graph["claim_evidence"] if row["claim_id"] != first_claim]
    graph["coverage_results"] = []

    codes = {flag.code for flag in validate_graph(graph)}
    assert "DG_CLAIM_DISPOSITION_MISSING" in codes
    assert "DG_CLAIM_EVIDENCE_MISSING" in codes
    assert "DG_COVERAGE_RESULT_MISSING" in codes


def test_deal_row_uses_python_owned_target_metadata() -> None:
    graph = _graph(_mac_gray_payload(), target_name="MAC GRAY CORP")

    deal = graph["deals"][0]
    assert deal["target_name"] == "MAC GRAY CORP"
    assert deal["target_actor_id"].startswith("actor_")


def test_relation_id_keeps_same_parties_with_different_role_details_distinct() -> None:
    payload = _mac_gray_payload()
    payload["actor_relation_claims"].append({
        **payload["actor_relation_claims"][0],
        "coverage_obligation_id": "obl_relation_csc_second_detail",
        "role_detail": "portfolio company",
    })

    graph = _graph(payload)
    csc_relations = [
        row for row in graph["actor_relations"]
        if row["subject_actor_label"] == "CSC" and row["object_actor_label"] == "CSC/Pamplona"
    ]

    assert len({row["relation_id"] for row in csc_relations}) == len(csc_relations)


def test_inactive_blocking_review_flags_do_not_block_validation() -> None:
    graph = _graph(_mac_gray_payload())
    graph["review_flags"].append({
        "flag_id": "flag_inactive",
        "run_id": "run-1",
        "deal_id": graph["deals"][0]["deal_id"],
        "severity": "blocking",
        "code": "inactive_blocker",
        "reason": "Inactive historical blocker.",
        "row_table": "claims",
        "row_id": graph["claims"][0]["claim_id"],
        "status": "open",
        "current": False,
    })

    assert not validate_graph(graph)


def test_duckdb_store_preserves_live_graph_fields(tmp_path) -> None:
    graph = _graph(_mac_gray_payload(), target_name="MAC GRAY CORP")
    graph["review_rows"] = [
        {"review_row_id": make_id("review_row", "mac-gray", "run-1", index, row), **row}
        for index, row in enumerate(project_review_rows(graph), start=1)
    ]
    database_path = tmp_path / "deal_graph.duckdb"

    with DealGraphStore(database_path) as store:
        store.init_schema()
        store.insert_snapshot(graph)
        actor_relation_columns = set(store.table_columns("actor_relations"))
        event_columns = set(store.table_columns("events"))
        event_link_columns = set(store.table_columns("event_actor_links"))
        deal_columns = set(store.table_columns("deals"))

        assert {"subject_actor_label", "object_actor_label"} <= actor_relation_columns
        assert "bid_stage" in event_columns
        assert "actor_label" in event_link_columns
        assert "target_name" in deal_columns
        assert store.execute("SELECT target_name FROM deals").fetchone()[0] == "MAC GRAY CORP"
        assert store.execute("SELECT COUNT(*) FROM review_rows").fetchone()[0] == len(graph["review_rows"])


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
            },
            {
                "claim_type": "actor",
                "coverage_obligation_id": "obl_actor_csc",
                "actor_label": "CSC",
                "actor_kind": "organization",
                "observability": "named",
                "actor_class": "strategic",
                "confidence": "high",
                "evidence_refs": _refs("CSC was an operating strategic buyer in the process"),
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
                "evidence_refs": _refs("CSC and Pamplona, who together we refer to as CSC/Pamplona"),
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
                "evidence_refs": _refs("CSC and Pamplona, who together we refer to as CSC/Pamplona"),
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
