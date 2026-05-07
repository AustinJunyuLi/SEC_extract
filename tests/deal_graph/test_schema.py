from __future__ import annotations

import pytest
from pydantic import ValidationError

from pipeline.deal_graph import schema
from pipeline.deal_graph.ids import make_id
from pipeline.deal_graph.store import artifact_paths, init_store


def _evidence_refs(quote: str, unit_id: str = "page_1_paragraph_1") -> list[dict]:
    return [{"citation_unit_id": unit_id, "quote_text": quote}]


def _valid_payload() -> dict:
    return {
        "actor_claims": [
            {
                "claim_type": "actor",
                "coverage_obligation_id": "obl_actor_1",
                "actor_label": "CSC/Pamplona",
                "actor_kind": "group",
                "observability": "named",
                "actor_class": "mixed",
                "confidence": "high",
                "evidence_refs": _evidence_refs(
                    "CSC and Pamplona, who together we refer to as CSC/Pamplona"
                ),
            }
        ],
        "event_claims": [
            {
                "claim_type": "event",
                "coverage_obligation_id": "obl_event_1",
                "event_type": "process",
                "event_subtype": "nda_signed",
                "event_date": "2013-08-01",
                "description": "CSC/Pamplona entered into a confidentiality agreement.",
                "actor_label": "CSC/Pamplona",
                "actor_role": "potential_buyer",
                "confidence": "high",
                "evidence_refs": _evidence_refs(
                    "CSC/Pamplona entered into a confidentiality agreement",
                    "page_1_paragraph_2",
                ),
            }
        ],
        "bid_claims": [
            {
                "claim_type": "bid",
                "coverage_obligation_id": "obl_bid_1",
                "bidder_label": "CSC/Pamplona",
                "bid_date": "2013-09-15",
                "bid_value": 18.5,
                "bid_value_lower": None,
                "bid_value_upper": None,
                "bid_value_unit": "per_share",
                "consideration_type": "cash",
                "bid_stage": "initial",
                "confidence": "high",
                "evidence_refs": _evidence_refs(
                    "CSC/Pamplona submitted an indication of interest at $18.50 per share",
                    "page_1_paragraph_3",
                ),
            }
        ],
        "participation_count_claims": [
            {
                "claim_type": "participation_count",
                "coverage_obligation_id": "obl_count_1",
                "process_stage": "nda_signed",
                "actor_class": "mixed",
                "count_min": 20,
                "count_max": 20,
                "count_qualifier": "exact",
                "confidence": "high",
                "evidence_refs": _evidence_refs(
                    "20 potential bidders entered confidentiality agreements",
                    "page_1_paragraph_4",
                ),
            }
        ],
        "actor_relation_claims": [
            {
                "claim_type": "actor_relation",
                "coverage_obligation_id": "obl_relation_1",
                "subject_label": "Pamplona",
                "object_label": "CSC/Pamplona",
                "relation_type": "member_of",
                "role_detail": "financing sponsor",
                "effective_date_first": None,
                "confidence": "high",
                "evidence_refs": _evidence_refs(
                    "CSC and Pamplona, who together we refer to as CSC/Pamplona"
                ),
            }
        ],
    }


def test_provider_payload_accepts_claim_only_shape():
    payload = schema.ProviderPayload.model_validate(_valid_payload())

    assert payload.actor_claims[0].actor_kind == "group"
    assert payload.actor_claims[0].actor_class == "mixed"
    assert payload.bid_claims[0].bid_stage == "initial"
    assert payload.actor_relation_claims[0].relation_type == "member_of"


@pytest.mark.parametrize("actor_class", ["non_us", "public", "private"])
def test_provider_payload_rejects_non_core_actor_class_values(actor_class: str) -> None:
    payload = _valid_payload()
    payload["actor_claims"][0]["actor_class"] = actor_class

    with pytest.raises(ValidationError, match="actor_class"):
        schema.ProviderPayload.model_validate(payload)


def test_provider_payload_requires_actor_class_on_actor_claims() -> None:
    payload = _valid_payload()
    del payload["actor_claims"][0]["actor_class"]

    with pytest.raises(ValidationError, match="actor_class"):
        schema.ProviderPayload.model_validate(payload)


def test_provider_payload_accepts_separated_exact_evidence_refs():
    payload = _valid_payload()
    payload["actor_relation_claims"][0]["evidence_refs"] = [
        {"citation_unit_id": "page_23_paragraph_2", "quote_text": "Longview had informed the Company"},
        {"citation_unit_id": "page_24_paragraph_1", "quote_text": "remain outstanding as equity in PetSmart"},
    ]

    parsed = schema.ProviderPayload.model_validate(payload)

    assert [ref.citation_unit_id for ref in parsed.actor_relation_claims[0].evidence_refs] == [
        "page_23_paragraph_2",
        "page_24_paragraph_1",
    ]


def test_provider_payload_rejects_empty_evidence_refs():
    payload = _valid_payload()
    payload["actor_claims"][0]["evidence_refs"] = []

    with pytest.raises(ValidationError, match="evidence_refs"):
        schema.ProviderPayload.model_validate(payload)


def test_provider_payload_rejects_python_owned_fields():
    payload = _valid_payload()
    payload["coverage_results"] = []

    with pytest.raises(ValidationError, match="Python-owned fields"):
        schema.ProviderPayload.model_validate(payload)

    payload = _valid_payload()
    payload["bid_claims"][0]["BidderID"] = 4

    with pytest.raises(ValidationError, match="Python-owned fields"):
        schema.ProviderPayload.model_validate(payload)


def test_provider_payload_rejects_old_event_row_shape():
    with pytest.raises(ValidationError):
        schema.ProviderPayload.model_validate({
            "deal": {"TargetName": "Mac Gray"},
            "events": [{"BidderID": 1, "bid_note": "Bid"}],
        })


def test_provider_json_schema_is_claim_array_only_top_level():
    provider_schema = schema.provider_json_schema()

    assert set(provider_schema["properties"]) == {
        "actor_claims",
        "event_claims",
        "bid_claims",
        "participation_count_claims",
        "actor_relation_claims",
    }
    assert provider_schema["additionalProperties"] is False
    assert "coverage_results" not in provider_schema["properties"]


def test_store_init_creates_expected_tables_under_audit_run(tmp_path):
    paths = artifact_paths(tmp_path, "mac-gray", "run_001")
    store = init_store(tmp_path, "mac-gray", "run_001")
    try:
        assert paths.database_path == tmp_path / "output/audit/mac-gray/runs/run_001/deal_graph.duckdb"
        assert paths.snapshot_path == tmp_path / "output/audit/mac-gray/runs/run_001/deal_graph_v2.json"
        assert paths.database_path.exists()
        assert schema.EXPECTED_TABLES <= store.list_tables()
    finally:
        store.close()


def test_store_rejects_legacy_canonical_tables(tmp_path):
    store = init_store(tmp_path, "mac-gray", "run_002")
    try:
        store.execute("CREATE TABLE event_rows (BidderID INTEGER)")
        store.commit()
        with pytest.raises(RuntimeError, match="legacy row-per-event tables"):
            store.reject_legacy_canonical_tables()
    finally:
        store.close()


def test_deterministic_ids_are_stable_and_prefixed():
    first = make_id("actor", "mac-gray", "CSC/Pamplona")
    second = make_id("actor", "mac-gray", "CSC/Pamplona")
    different = make_id("actor", "mac-gray", "Pamplona")

    assert first == second
    assert first.startswith("actor_")
    assert first != different
