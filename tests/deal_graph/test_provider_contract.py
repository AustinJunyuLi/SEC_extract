import json

import pytest

from pipeline.llm.response_format import (
    DEAL_GRAPH_CLAIM_SCHEMA,
    MalformedJSONError,
    call_json,
    json_schema_format,
)
from tests.llm.test_response_format import StubClient, _valid_payload


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


def test_provider_schema_top_level_is_claim_only():
    fmt = json_schema_format(DEAL_GRAPH_CLAIM_SCHEMA)

    assert fmt["name"] == "deal_graph_v1_claim_schema"
    assert list(DEAL_GRAPH_CLAIM_SCHEMA["properties"]) == EXPECTED_TOP_LEVEL_KEYS
    assert DEAL_GRAPH_CLAIM_SCHEMA["required"] == EXPECTED_TOP_LEVEL_KEYS
    assert DEAL_GRAPH_CLAIM_SCHEMA["additionalProperties"] is False


def test_provider_schema_is_strict_and_linkflow_safe():
    for node in _walk_schema(DEAL_GRAPH_CLAIM_SCHEMA):
        assert "oneOf" not in node
        assert not isinstance(node.get("additionalProperties"), dict)
        if node.get("type") == "object":
            assert node.get("additionalProperties") is False


def test_provider_schema_does_not_expose_retired_scalar_or_projection_fields():
    encoded = json.dumps(DEAL_GRAPH_CLAIM_SCHEMA)

    for retired in [
        "coverage_results",
        "BidderID",
        "bidder_registry",
        "bid_note",
        "bid_type",
        "bidder_type",
        "source_page",
        "source_start",
        "source_end",
        "actor_id",
        "event_id",
        "canonical",
        "projection",
    ]:
        assert retired not in encoded


@pytest.mark.parametrize(
    ("family", "field", "value"),
    [
        ("actor_claims", "actor_id", "actor_1"),
        ("event_claims", "BidderID", 1),
        ("event_claims", "canonical_event_id", "event_1"),
        ("bid_claims", "bid_type", "formal"),
        ("bid_claims", "source_start", 1),
        ("participation_count_claims", "coverage_results", []),
        ("actor_relation_claims", "source_offsets", [1, 2]),
    ],
)
def test_parser_rejects_retired_fields_inside_claims(family, field, value):
    payload = _valid_payload()
    payload[family][0][field] = value
    client = StubClient([json.dumps(payload)])

    with pytest.raises(MalformedJSONError, match=field):
        import asyncio

        asyncio.run(
            call_json(
                client,
                model="gpt-test",
                system="sys",
                user="usr",
            )
        )


def test_parser_rejects_retired_projection_payload_at_top_level():
    payload = _valid_payload()
    payload["projection_rows"] = []
    client = StubClient([json.dumps(payload)])

    with pytest.raises(MalformedJSONError, match="projection_rows"):
        import asyncio

        asyncio.run(
            call_json(
                client,
                model="gpt-test",
                system="sys",
                user="usr",
            )
        )
