import asyncio

import pytest

from pipeline.llm.client import CompletionResult
from pipeline.llm.response_format import SCHEMA_R1, call_json, json_schema_format, parse_json_text, supports_json_schema


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


def test_parse_json_text_accepts_fenced_json():
    parsed = parse_json_text('Before\n```json\n{"deal": {}, "events": []}\n```\nAfter')

    assert parsed == {"deal": {}, "events": []}


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


def test_supports_json_schema_probes_client_with_model():
    client = StubClient(['{"ok": true}'])

    assert asyncio.run(supports_json_schema(client, model="gpt-test")) is True
    assert client.calls[0]["text_format"]["name"] == "probe"


def test_call_json_returns_completion_result_and_repairs_once():
    client = StubClient(["not json", '{"deal": {}, "events": []}'])

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
    assert "Re-emit valid JSON only" in client.calls[1]["user"]
    assert result.input_tokens == 2
    assert result.output_tokens == 4
    assert result.attempts == 2
    assert len(client.calls) == 2
