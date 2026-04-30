import asyncio
import json
import re

import pytest

from pipeline import core
from pipeline.llm.client import CompletionResult
from pipeline.llm.response_format import (
    SCHEMA_R1,
    MalformedJSONError,
    call_json,
    json_schema_format,
    parse_json_text,
)


def test_schema_r1_is_strict_deal_events_shape():
    fmt = json_schema_format()

    assert fmt["type"] == "json_schema"
    assert fmt["name"] == "extraction_schema_r1"
    assert fmt["strict"] is True
    assert fmt["schema"] is SCHEMA_R1
    assert SCHEMA_R1["required"] == ["deal", "events"]
    assert SCHEMA_R1["additionalProperties"] is False


def test_schema_r1_requires_prompt_skeleton_event_fields():
    required = set(SCHEMA_R1["properties"]["events"]["items"]["required"])
    for field in [
        "BidderID",
        "process_phase",
        "role",
        "bid_note",
        "source_quote",
        "source_page",
        "flags",
    ]:
        assert field in required
    assert SCHEMA_R1["properties"]["events"]["items"]["additionalProperties"] is False


def test_schema_r1_nullability_matches_validator_contract():
    props = SCHEMA_R1["properties"]["events"]["items"]["properties"]

    assert props["process_phase"]["type"] == ["integer", "null"]
    assert props["role"]["type"] == "string"
    assert props["role"]["enum"] == ["bidder", "advisor_financial", "advisor_legal"]


def test_schema_r1_bid_note_enum_matches_core_vocabulary():
    bid_note = SCHEMA_R1["properties"]["events"]["items"]["properties"]["bid_note"]

    assert bid_note["enum"] == sorted(core.EVENT_VOCABULARY)


def test_schema_r1_requires_unnamed_nda_promotion_hint_slot():
    event_schema = SCHEMA_R1["properties"]["events"]["items"]
    promotion = event_schema["properties"]["unnamed_nda_promotion"]

    assert "unnamed_nda_promotion" in event_schema["required"]
    assert promotion["additionalProperties"] is False
    assert set(promotion["required"]) == {
        "target_bidder_id",
        "promote_to_bidder_alias",
        "promote_to_bidder_name",
        "reason",
    }


def test_parse_json_text_rejects_fenced_json():
    with pytest.raises(ValueError):
        parse_json_text('```json\n{"deal": {}, "events": []}\n```')


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
        "deal": {
            "TargetName": "Target Inc.",
            "Acquirer": "Buyer Inc.",
            "DateAnnounced": "2020-01-02",
            "DateEffective": None,
            "auction": True,
            "all_cash": True,
            "target_legal_counsel": None,
            "acquirer_legal_counsel": None,
            "bidder_registry": {},
            "deal_flags": [],
        },
        "events": [
            {
                "BidderID": 1,
                "process_phase": 1,
                "role": "bidder",
                "exclusivity_days": None,
                "bidder_name": None,
                "bidder_alias": "Target board",
                "bidder_type": None,
                "bid_note": "Target Sale",
                "bid_type": None,
                "bid_type_inference_note": None,
                "drop_initiator": None,
                "drop_reason_class": None,
                "final_round_announcement": None,
                "final_round_extension": None,
                "final_round_informal": None,
                "press_release_subject": None,
                "invited_to_formal_round": None,
                "submitted_formal_bid": None,
                "bid_date_precise": "2020-01-01",
                "bid_date_rough": None,
                "bid_value": None,
                "bid_value_pershare": None,
                "bid_value_lower": None,
                "bid_value_upper": None,
                "bid_value_unit": None,
                "consideration_components": None,
                "additional_note": None,
                "comments": None,
                "unnamed_nda_promotion": None,
                "source_quote": "The target board met to discuss strategic alternatives.",
                "source_page": 12,
                "flags": [],
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
    assert client.calls[0]["text_format"]["name"] == "extraction_schema_r1"
    assert result.input_tokens == 1
    assert result.output_tokens == 2
    assert result.attempts == 1
    assert len(client.calls) == 1


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda p: p.update({"bidder_registry": {}}), "unexpected field bidder_registry"),
        (lambda p: p["events"][0].pop("role"), "events[0].role"),
        (lambda p: p["events"][0].update({"legacy_bid_note": "Inf"}), "events[0].legacy_bid_note"),
        (lambda p: p["events"][0].update({"bid_type": "soft"}), "events[0].bid_type"),
        (
            lambda p: p["events"][0]["flags"].append({
                "code": "x",
                "severity": "info",
                "reason": "synthetic",
                "source_page": 12,
            }),
            "events[0].flags[0].source_page",
        ),
        (lambda p: p["events"][0].update({"source_quote": ["quote"], "source_page": 12}), "source_quote"),
    ],
)
def test_call_json_enforces_local_schema_after_provider_response(mutate, message):
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

    assert client.calls[0]["text_format"]["name"] == "extraction_schema_r1"


def test_call_json_enforces_max_length_locally():
    payload = _valid_payload()
    payload["events"][0]["bid_type"] = "informal"
    payload["events"][0]["bid_type_inference_note"] = "x" * 301
    client = StubClient([json.dumps(payload)])

    with pytest.raises(MalformedJSONError, match=r"maxLength 300"):
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
