import asyncio
import json
import re

import pytest

from pipeline.llm.client import CompletionResult
from pipeline.llm.response_format import (
    DEAL_GRAPH_CLAIM_SCHEMA,
    REPAIR_SCHEMA_R1,
    SCHEMA_R1,
    MalformedJSONError,
    call_json,
    json_schema_format,
    parse_json_text,
)


EXPECTED_TOP_LEVEL_KEYS = [
    "actor_claims",
    "event_claims",
    "bid_claims",
    "participation_count_claims",
    "actor_relation_claims",
]


def _walk_schema(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk_schema(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk_schema(value)


def test_schema_r1_aliases_deal_graph_claim_schema():
    fmt = json_schema_format()

    assert fmt["type"] == "json_schema"
    assert fmt["name"] == "deal_graph_v1_claim_schema"
    assert fmt["strict"] is True
    assert fmt["schema"] is SCHEMA_R1
    assert SCHEMA_R1 is DEAL_GRAPH_CLAIM_SCHEMA
    assert SCHEMA_R1["required"] == EXPECTED_TOP_LEVEL_KEYS
    assert list(SCHEMA_R1["properties"]) == EXPECTED_TOP_LEVEL_KEYS
    assert SCHEMA_R1["additionalProperties"] is False


def test_schema_is_provider_safe_without_oneof_or_dynamic_additional_properties():
    for node in _walk_schema(SCHEMA_R1):
        assert "oneOf" not in node
        additional = node.get("additionalProperties")
        assert not isinstance(additional, dict)


def test_claim_family_schemas_are_closed_and_claim_only():
    for family in EXPECTED_TOP_LEVEL_KEYS:
        item_schema = SCHEMA_R1["properties"][family]["items"]
        assert item_schema["additionalProperties"] is False
        assert "claim_type" in item_schema["required"]
        assert "coverage_obligation_id" in item_schema["required"]
        assert "confidence" in item_schema["required"]
        assert "quote_text" in item_schema["required"]
        assert "quote_texts" in item_schema["required"]


def test_repair_schema_is_claim_payload_plus_repair_assertions():
    fmt = json_schema_format(REPAIR_SCHEMA_R1)

    assert fmt["name"] == "deal_graph_v1_repair_claim_schema"
    assert REPAIR_SCHEMA_R1["required"] == [
        *EXPECTED_TOP_LEVEL_KEYS,
        "obligation_assertions",
    ]
    assert set(REPAIR_SCHEMA_R1["properties"]) == {
        *EXPECTED_TOP_LEVEL_KEYS,
        "obligation_assertions",
    }


def test_parse_json_text_rejects_fenced_json():
    with pytest.raises(ValueError):
        parse_json_text('```json\n{"actor_claims": []}\n```')


def test_parse_json_text_rejects_non_object_json():
    with pytest.raises(ValueError, match="JSON object"):
        parse_json_text("[1, 2, 3]")


class StubClient:
    def __init__(self, texts):
        self.texts = list(texts)
        self.calls = []

    async def complete(self, **kwargs):
        self.calls.append(kwargs)
        text = self.texts.pop(0)
        return CompletionResult(text=text, model=kwargs["model"], input_tokens=1, output_tokens=2)


def _valid_payload():
    return {
        "actor_claims": [
            {
                "claim_type": "actor",
                "coverage_obligation_id": "obl_actor_1",
                "actor_label": "CSC/Pamplona",
                "actor_kind": "group",
                "observability": "named",
                "confidence": "high",
                "quote_text": "CSC and Pamplona, who together we refer to as CSC/Pamplona",
                "quote_texts": None,
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
                "quote_text": "CSC/Pamplona entered into a confidentiality agreement with Mac-Gray",
                "quote_texts": None,
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
                "quote_text": "CSC/Pamplona submitted an indication of interest at $18.50 per share",
                "quote_texts": None,
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
                "quote_text": "20 potential bidders entered confidentiality agreements",
                "quote_texts": None,
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
                "quote_text": "CSC and Pamplona, who together we refer to as CSC/Pamplona",
                "quote_texts": None,
            }
        ],
    }


def test_call_json_returns_completion_result():
    client = StubClient([json.dumps(_valid_payload())])

    result = asyncio.run(
        call_json(
            client,
            model="gpt-test",
            system="sys",
            user="usr",
        )
    )

    assert result.parsed_json == _valid_payload()
    assert client.calls[0]["text_format"]["name"] == "deal_graph_v1_claim_schema"
    assert result.input_tokens == 1
    assert result.output_tokens == 2
    assert result.attempts == 1
    assert len(client.calls) == 1


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda p: p.update({"coverage_results": []}), "coverage_results"),
        (lambda p: p.update({"deal": {}, "events": []}), "deal"),
        (lambda p: p["event_claims"][0].update({"BidderID": 1}), "BidderID"),
        (lambda p: p["event_claims"][0].update({"T": 1}), "T"),
        (lambda p: p["event_claims"][0].update({"bI": 1}), "bI"),
        (lambda p: p["event_claims"][0].update({"bF": 0}), "bF"),
        (lambda p: p["actor_claims"][0].update({"actor_id": "actor_1"}), "actor_id"),
        (lambda p: p["event_claims"][0].update({"event_id": "event_1"}), "event_id"),
        (lambda p: p["bid_claims"][0].update({"source_start": 12}), "source_start"),
        (lambda p: p["bid_claims"][0].update({"source_end": 42}), "source_end"),
        (lambda p: p["bid_claims"][0].update({"source_page": 12}), "source_page"),
        (lambda p: p["bid_claims"][0].update({"bid_type": "formal"}), "bid_type"),
        (lambda p: p["bid_claims"][0].update({"bidder_row": {}}), "bidder_row"),
        (lambda p: p["event_claims"][0].pop("quote_text"), "quote_text"),
        (lambda p: p["event_claims"][0].update({"event_subtype": "NDA"}), "event_subtype"),
    ],
)
def test_call_json_rejects_retired_provider_fields(mutate, message):
    payload = _valid_payload()
    mutate(payload)
    client = StubClient([json.dumps(payload)])

    with pytest.raises(MalformedJSONError, match=re.escape(message)):
        asyncio.run(
            call_json(
                client,
                model="gpt-test",
                system="sys",
                user="usr",
            )
        )

    assert client.calls[0]["text_format"]["name"] == "deal_graph_v1_claim_schema"


def test_call_json_enforces_max_length_locally():
    payload = _valid_payload()
    payload["actor_claims"][0]["quote_text"] = "x" * 1501
    client = StubClient([json.dumps(payload)])

    with pytest.raises(MalformedJSONError, match=r"maxLength 1500"):
        asyncio.run(
            call_json(
                client,
                model="gpt-test",
                system="sys",
                user="usr",
            )
        )


def test_call_json_validates_custom_schema():
    client = StubClient([json.dumps({"reason": "too long"})])

    with pytest.raises(MalformedJSONError, match=r"reason.*maxLength 3"):
        asyncio.run(
            call_json(
                client,
                model="gpt-test",
                system="sys",
                user="usr",
                schema={
                    "type": "object",
                    "properties": {"reason": {"type": "string", "maxLength": 3}},
                    "required": ["reason"],
                    "additionalProperties": False,
                },
            )
        )


def test_call_json_validates_custom_schema_min_items():
    client = StubClient([json.dumps({"items": []})])

    with pytest.raises(MalformedJSONError, match=r"items.*minItems 1"):
        asyncio.run(
            call_json(
                client,
                model="gpt-test",
                system="sys",
                user="usr",
                schema={
                    "type": "object",
                    "properties": {"items": {"type": "array", "minItems": 1}},
                    "required": ["items"],
                    "additionalProperties": False,
                },
            )
        )


def test_parse_repair_response_accepts_obligation_assertions_and_strips_them():
    from pipeline.llm.response_format import parse_repair_json_text

    parsed, assertions = parse_repair_json_text(
        json.dumps({
            **_valid_payload(),
            "obligation_assertions": [
                {
                    "obligation_id": "obl-001",
                    "status": "satisfied",
                    "claim_indexes": [1],
                    "reason": "Claims satisfy the obligation.",
                }
            ],
        })
    )

    assert parsed == _valid_payload()
    assert assertions == [
        {
            "obligation_id": "obl-001",
            "status": "satisfied",
            "claim_indexes": [1],
            "reason": "Claims satisfy the obligation.",
        }
    ]


def test_call_json_fails_loudly_without_repair_call():
    client = StubClient(["not json"])

    with pytest.raises(ValueError):
        asyncio.run(
            call_json(
                client,
                model="gpt-test",
                system="sys",
                user="usr",
            )
        )

    assert len(client.calls) == 1
