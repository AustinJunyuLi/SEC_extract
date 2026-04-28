import asyncio

import pytest

from pipeline import core
from pipeline.llm.client import CompletionResult
from pipeline.llm.response_format import SCHEMA_R1, call_json, json_schema_format, parse_json_text


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


def test_schema_r1_bid_note_enum_matches_core_vocabulary():
    bid_note = SCHEMA_R1["properties"]["events"]["items"]["properties"]["bid_note"]

    assert bid_note["enum"] == sorted(core.EVENT_VOCABULARY)


def test_schema_r1_allows_optional_unnamed_nda_promotion_hint():
    event_schema = SCHEMA_R1["properties"]["events"]["items"]
    promotion = event_schema["properties"]["unnamed_nda_promotion"]

    assert "unnamed_nda_promotion" not in event_schema["required"]
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


def test_call_json_returns_completion_result():
    client = StubClient(['{"deal": {}, "events": []}'])

    result = asyncio.run(
        call_json(
            client,
            model="gpt-test",
            system="sys",
            user="usr",
            schema_supported=True,
        )
    )

    assert result.parsed_json == {"deal": {}, "events": []}
    assert client.calls[0]["text_format"]["name"] == "extraction_schema_r1"
    assert result.input_tokens == 1
    assert result.output_tokens == 2
    assert result.attempts == 1
    assert len(client.calls) == 1


def test_call_json_fails_loudly_without_repair_call():
    client = StubClient(["not json"])

    with pytest.raises(ValueError):
        asyncio.run(
            call_json(
                client,
                model="gpt-test",
                system="sys",
                user="usr",
                schema_supported=False,
            )
        )

    assert len(client.calls) == 1
