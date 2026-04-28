from __future__ import annotations

import json
from typing import Any

from pipeline.core import EVENT_VOCABULARY
from pipeline.llm.client import CompletionResult, LLMClient


class MalformedJSONError(ValueError):
    pass


FLAG_SCHEMA = {
    "type": "object",
    "properties": {
        "code": {"type": "string"},
        "severity": {"type": "string", "enum": ["hard", "soft", "info"]},
        "reason": {"type": "string"},
    },
    "required": ["code", "severity", "reason"],
    "additionalProperties": False,
}

REGISTRY_ENTRY_SCHEMA = {
    "type": "object",
    "properties": {
        "resolved_name": {"type": ["string", "null"]},
        "aliases_observed": {"type": "array", "items": {"type": "string"}},
        "first_appearance_row_index": {"type": ["integer", "null"]},
    },
    "required": ["resolved_name", "aliases_observed", "first_appearance_row_index"],
    "additionalProperties": False,
}

SCHEMA_R1: dict[str, Any] = {
    "type": "object",
    "properties": {
        "deal": {
            "type": "object",
            "properties": {
                "TargetName": {"type": ["string", "null"]},
                "Acquirer": {"type": ["string", "null"]},
                "DateAnnounced": {"type": ["string", "null"]},
                "DateEffective": {"type": ["string", "null"]},
                "auction": {"type": "boolean"},
                "all_cash": {"type": ["boolean", "null"]},
                "target_legal_counsel": {"type": ["string", "null"]},
                "acquirer_legal_counsel": {"type": ["string", "null"]},
                "bidder_registry": {
                    "type": "object",
                    "additionalProperties": REGISTRY_ENTRY_SCHEMA,
                },
                "deal_flags": {"type": "array", "items": FLAG_SCHEMA},
            },
            "required": [
                "TargetName",
                "Acquirer",
                "DateAnnounced",
                "DateEffective",
                "auction",
                "all_cash",
                "target_legal_counsel",
                "acquirer_legal_counsel",
                "bidder_registry",
                "deal_flags",
            ],
            "additionalProperties": False,
        },
        "events": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "BidderID": {"type": "integer"},
                    "process_phase": {"type": "integer"},
                    "role": {"type": ["string", "null"], "enum": ["bidder", "advisor_financial", "advisor_legal", None]},
                    "exclusivity_days": {"type": ["integer", "null"]},
                    "bidder_name": {"type": ["string", "null"]},
                    "bidder_alias": {"type": ["string", "null"]},
                    "bidder_type": {"type": ["string", "null"], "enum": ["s", "f", None]},
                    "bid_note": {"type": "string", "enum": sorted(EVENT_VOCABULARY)},
                    "bid_type": {"type": ["string", "null"], "enum": ["formal", "informal", None]},
                    "bid_type_inference_note": {"type": ["string", "null"], "maxLength": 300},
                    "drop_initiator": {"type": ["string", "null"], "enum": ["bidder", "target", "unknown", None]},
                    "drop_reason_class": {
                        "type": ["string", "null"],
                        "enum": [
                            "below_market",
                            "below_minimum",
                            "target_other",
                            "no_response",
                            "never_advanced",
                            "scope_mismatch",
                            None,
                        ],
                    },
                    "final_round_announcement": {"type": ["boolean", "null"]},
                    "final_round_extension": {"type": ["boolean", "null"]},
                    "final_round_informal": {"type": ["boolean", "null"]},
                    "press_release_subject": {"type": ["string", "null"], "enum": ["bidder", "sale", "other", None]},
                    "invited_to_formal_round": {"type": ["boolean", "null"]},
                    "submitted_formal_bid": {"type": ["boolean", "null"]},
                    "bid_date_precise": {"type": ["string", "null"]},
                    "bid_date_rough": {"type": ["string", "null"]},
                    "bid_value": {"type": ["number", "null"]},
                    "bid_value_pershare": {"type": ["number", "null"]},
                    "bid_value_lower": {"type": ["number", "null"]},
                    "bid_value_upper": {"type": ["number", "null"]},
                    "bid_value_unit": {"type": ["string", "null"]},
                    "consideration_components": {"type": ["array", "null"], "items": {"type": "string"}},
                    "additional_note": {"type": ["string", "null"]},
                    "comments": {"type": ["string", "null"]},
                    "unnamed_nda_promotion": {
                        "type": ["object", "null"],
                        "properties": {
                            "target_bidder_id": {"type": "integer"},
                            "promote_to_bidder_alias": {"type": "string"},
                            "promote_to_bidder_name": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                        "required": [
                            "target_bidder_id",
                            "promote_to_bidder_alias",
                            "promote_to_bidder_name",
                            "reason",
                        ],
                        "additionalProperties": False,
                    },
                    "source_quote": {"oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]},
                    "source_page": {"oneOf": [{"type": "integer"}, {"type": "array", "items": {"type": "integer"}}]},
                    "flags": {"type": "array", "items": FLAG_SCHEMA},
                },
                "required": [
                    "BidderID",
                    "process_phase",
                    "role",
                    "exclusivity_days",
                    "bidder_name",
                    "bidder_alias",
                    "bidder_type",
                    "bid_note",
                    "bid_type",
                    "bid_type_inference_note",
                    "drop_initiator",
                    "drop_reason_class",
                    "final_round_announcement",
                    "final_round_extension",
                    "final_round_informal",
                    "press_release_subject",
                    "invited_to_formal_round",
                    "submitted_formal_bid",
                    "bid_date_precise",
                    "bid_date_rough",
                    "bid_value",
                    "bid_value_pershare",
                    "bid_value_lower",
                    "bid_value_upper",
                    "bid_value_unit",
                    "consideration_components",
                    "additional_note",
                    "comments",
                    "source_quote",
                    "source_page",
                    "flags",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["deal", "events"],
    "additionalProperties": False,
}


def json_schema_format(schema: dict[str, Any] = SCHEMA_R1) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "name": "extraction_schema_r1",
        "schema": schema,
        "strict": True,
    }


def parse_json_text(text: str) -> dict[str, Any]:
    candidate = text.strip()
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise MalformedJSONError(str(exc)) from exc
    if not isinstance(parsed, dict):
        raise MalformedJSONError("expected JSON object")
    return parsed


def _ensure_extraction_shape(parsed: dict[str, Any]) -> None:
    if "deal" not in parsed or "events" not in parsed:
        raise MalformedJSONError("expected object with deal and events")


async def call_json(
    client: LLMClient,
    *,
    system: str,
    user: str,
    model: str,
    schema_supported: bool,
    schema: dict[str, Any] = SCHEMA_R1,
    max_output_tokens: int | None = None,
    reasoning_effort: str | None = None,
) -> CompletionResult:
    result = await client.complete(
        system=system,
        user=user,
        model=model,
        text_format=json_schema_format(schema) if schema_supported else None,
        max_output_tokens=max_output_tokens,
        reasoning_effort=reasoning_effort,
    )
    parsed = parse_json_text(result.text)
    if schema is SCHEMA_R1:
        _ensure_extraction_shape(parsed)
    result.parsed_json = parsed
    return result
