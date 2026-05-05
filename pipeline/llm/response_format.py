from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from pipeline.llm.client import CompletionResult, LLMClient


class MalformedJSONError(ValueError):
    pass


def _path(parent: str, child: str) -> str:
    if parent == "$":
        return f"$.{child}"
    return f"{parent}.{child}"


def _array_path(parent: str, index: int) -> str:
    return f"{parent}[{index}]"


def _matches_json_type(value: Any, json_type: str) -> bool:
    if json_type == "null":
        return value is None
    if json_type == "boolean":
        return isinstance(value, bool)
    if json_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if json_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if json_type == "string":
        return isinstance(value, str)
    if json_type == "array":
        return isinstance(value, list)
    if json_type == "object":
        return isinstance(value, dict)
    raise MalformedJSONError(f"unsupported schema type {json_type!r}")


def _validate_type(schema: dict[str, Any], value: Any, path: str) -> None:
    expected = schema.get("type")
    if expected is None:
        return
    types = expected if isinstance(expected, list) else [expected]
    if not any(_matches_json_type(value, json_type) for json_type in types):
        names = "|".join(str(t) for t in types)
        raise MalformedJSONError(
            f"{path}: expected {names}; got {type(value).__name__}"
        )


def _validate_schema_value(schema: dict[str, Any], value: Any, path: str = "$") -> None:
    if "oneOf" in schema:
        failures: list[str] = []
        matched = 0
        for option in schema["oneOf"]:
            try:
                _validate_schema_value(option, value, path)
            except MalformedJSONError as exc:
                failures.append(str(exc))
            else:
                matched += 1
        if matched != 1:
            detail = "; ".join(failures[:2])
            raise MalformedJSONError(
                f"{path}: expected exactly one schema match; got {matched}"
                + (f" ({detail})" if detail else "")
            )
        return

    _validate_type(schema, value, path)

    if "enum" in schema and value not in schema["enum"]:
        raise MalformedJSONError(f"{path}: value {value!r} not in allowed enum")

    schema_type = schema.get("type")
    type_names = set(schema_type if isinstance(schema_type, list) else [schema_type])

    if isinstance(value, str) and "maxLength" in schema:
        limit = int(schema["maxLength"])
        if len(value) > limit:
            raise MalformedJSONError(
                f"{path}: string length {len(value)} exceeds maxLength {limit}"
            )

    if isinstance(value, dict) and (schema_type is None or "object" in type_names):
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        for name in required:
            if name not in value:
                raise MalformedJSONError(f"{_path(path, name)}: missing required field")
        additional = schema.get("additionalProperties", True)
        for name, child in value.items():
            if name in properties:
                _validate_schema_value(properties[name], child, _path(path, name))
            elif additional is False:
                raise MalformedJSONError(f"{_path(path, name)}: unexpected field {name}")
            elif isinstance(additional, dict):
                _validate_schema_value(additional, child, _path(path, name))
        return

    if isinstance(value, list) and (schema_type is None or "array" in type_names):
        if "minItems" in schema:
            minimum = int(schema["minItems"])
            if len(value) < minimum:
                raise MalformedJSONError(
                    f"{path}: array length {len(value)} below minItems {minimum}"
                )
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                _validate_schema_value(item_schema, item, _array_path(path, index))


CONFIDENCE_SCHEMA = {"type": "string", "enum": ["high", "medium", "low"]}
QUOTE_TEXT_SCHEMA = {"type": "string", "maxLength": 1500}
QUOTE_TEXTS_SCHEMA = {
    "type": ["array", "null"],
    "items": QUOTE_TEXT_SCHEMA,
    "minItems": 1,
}

ACTOR_CLAIM_SCHEMA = {
    "type": "object",
    "properties": {
        "claim_type": {"type": "string", "enum": ["actor"]},
        "coverage_obligation_id": {"type": "string"},
        "actor_label": {"type": "string"},
        "actor_kind": {
            "type": "string",
            "enum": ["organization", "person", "group", "vehicle", "cohort", "committee"],
        },
        "observability": {
            "type": "string",
            "enum": ["named", "anonymous_handle", "count_only"],
        },
        "confidence": CONFIDENCE_SCHEMA,
        "quote_text": QUOTE_TEXT_SCHEMA,
        "quote_texts": QUOTE_TEXTS_SCHEMA,
    },
    "required": [
        "claim_type",
        "coverage_obligation_id",
        "actor_label",
        "actor_kind",
        "observability",
        "confidence",
        "quote_text",
        "quote_texts",
    ],
    "additionalProperties": False,
}

EVENT_CLAIM_SCHEMA = {
    "type": "object",
    "properties": {
        "claim_type": {"type": "string", "enum": ["event"]},
        "coverage_obligation_id": {"type": "string"},
        "event_type": {"type": "string", "enum": ["process", "bid", "transaction"]},
        "event_subtype": {
            "type": "string",
            "enum": [
                "contact_initial",
                "nda_signed",
                "consortium_ca_signed",
                "ioi_submitted",
                "first_round_bid",
                "final_round_bid",
                "exclusivity_grant",
                "merger_agreement_executed",
                "withdrawn_by_bidder",
                "excluded_by_target",
                "non_responsive",
                "cohort_closure",
                "advancement_admitted",
                "advancement_declined",
                "rollover_executed",
                "financing_committed",
                "go_shop_started",
                "go_shop_ended",
            ],
        },
        "event_date": {"type": ["string", "null"]},
        "description": {"type": "string"},
        "actor_label": {"type": ["string", "null"]},
        "actor_role": {"type": ["string", "null"]},
        "confidence": CONFIDENCE_SCHEMA,
        "quote_text": QUOTE_TEXT_SCHEMA,
        "quote_texts": QUOTE_TEXTS_SCHEMA,
    },
    "required": [
        "claim_type",
        "coverage_obligation_id",
        "event_type",
        "event_subtype",
        "event_date",
        "description",
        "actor_label",
        "actor_role",
        "confidence",
        "quote_text",
        "quote_texts",
    ],
    "additionalProperties": False,
}

BID_CLAIM_SCHEMA = {
    "type": "object",
    "properties": {
        "claim_type": {"type": "string", "enum": ["bid"]},
        "coverage_obligation_id": {"type": "string"},
        "bidder_label": {"type": "string"},
        "bid_date": {"type": ["string", "null"]},
        "bid_value": {"type": ["number", "null"]},
        "bid_value_lower": {"type": ["number", "null"]},
        "bid_value_upper": {"type": ["number", "null"]},
        "bid_value_unit": {
            "type": ["string", "null"],
            "enum": ["per_share", "enterprise_value", "equity_value", "other", None],
        },
        "consideration_type": {
            "type": ["string", "null"],
            "enum": ["cash", "stock", "mixed", "other", None],
        },
        "bid_stage": {
            "type": "string",
            "enum": ["initial", "revised", "final", "unspecified"],
        },
        "confidence": CONFIDENCE_SCHEMA,
        "quote_text": QUOTE_TEXT_SCHEMA,
        "quote_texts": QUOTE_TEXTS_SCHEMA,
    },
    "required": [
        "claim_type",
        "coverage_obligation_id",
        "bidder_label",
        "bid_date",
        "bid_value",
        "bid_value_lower",
        "bid_value_upper",
        "bid_value_unit",
        "consideration_type",
        "bid_stage",
        "confidence",
        "quote_text",
        "quote_texts",
    ],
    "additionalProperties": False,
}

PARTICIPATION_COUNT_CLAIM_SCHEMA = {
    "type": "object",
    "properties": {
        "claim_type": {"type": "string", "enum": ["participation_count"]},
        "coverage_obligation_id": {"type": "string"},
        "process_stage": {
            "type": "string",
            "enum": ["contacted", "nda_signed", "ioi_submitted", "first_round", "final_round", "exclusivity"],
        },
        "actor_class": {
            "type": "string",
            "enum": ["financial", "strategic", "mixed", "unknown"],
        },
        "count_min": {"type": "integer"},
        "count_max": {"type": ["integer", "null"]},
        "count_qualifier": {"type": "string", "enum": ["exact", "at_least", "at_most", "range", "approximate"]},
        "confidence": CONFIDENCE_SCHEMA,
        "quote_text": QUOTE_TEXT_SCHEMA,
        "quote_texts": QUOTE_TEXTS_SCHEMA,
    },
    "required": [
        "claim_type",
        "coverage_obligation_id",
        "process_stage",
        "actor_class",
        "count_min",
        "count_max",
        "count_qualifier",
        "confidence",
        "quote_text",
        "quote_texts",
    ],
    "additionalProperties": False,
}

ACTOR_RELATION_CLAIM_SCHEMA = {
    "type": "object",
    "properties": {
        "claim_type": {"type": "string", "enum": ["actor_relation"]},
        "coverage_obligation_id": {"type": "string"},
        "subject_label": {"type": "string"},
        "object_label": {"type": "string"},
        "relation_type": {
            "type": "string",
            "enum": [
                "member_of",
                "joins_group",
                "exits_group",
                "affiliate_of",
                "controls",
                "acquisition_vehicle_of",
                "advises",
                "finances",
                "supports",
                "voting_support_for",
                "rollover_holder_for",
            ],
        },
        "role_detail": {"type": ["string", "null"]},
        "effective_date_first": {"type": ["string", "null"]},
        "confidence": CONFIDENCE_SCHEMA,
        "quote_text": QUOTE_TEXT_SCHEMA,
        "quote_texts": QUOTE_TEXTS_SCHEMA,
    },
    "required": [
        "claim_type",
        "coverage_obligation_id",
        "subject_label",
        "object_label",
        "relation_type",
        "role_detail",
        "effective_date_first",
        "confidence",
        "quote_text",
        "quote_texts",
    ],
    "additionalProperties": False,
}

DEAL_GRAPH_CLAIM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "actor_claims": {"type": "array", "items": ACTOR_CLAIM_SCHEMA},
        "event_claims": {"type": "array", "items": EVENT_CLAIM_SCHEMA},
        "bid_claims": {"type": "array", "items": BID_CLAIM_SCHEMA},
        "participation_count_claims": {
            "type": "array",
            "items": PARTICIPATION_COUNT_CLAIM_SCHEMA,
        },
        "actor_relation_claims": {"type": "array", "items": ACTOR_RELATION_CLAIM_SCHEMA},
    },
    "required": [
        "actor_claims",
        "event_claims",
        "bid_claims",
        "participation_count_claims",
        "actor_relation_claims",
    ],
    "additionalProperties": False,
}

# Compatibility name for existing callers during the deal_graph_v1 provider
# contract slice. The schema itself is no longer the retired row/event format.
SCHEMA_R1: dict[str, Any] = DEAL_GRAPH_CLAIM_SCHEMA


REPAIR_SCHEMA_R1: dict[str, Any] = deepcopy(SCHEMA_R1)
REPAIR_SCHEMA_R1["properties"]["obligation_assertions"] = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "obligation_id": {"type": "string"},
            "status": {
                "type": "string",
                "enum": ["satisfied", "unmet", "not_applicable"],
            },
            "claim_indexes": {"type": "array", "items": {"type": "integer"}},
            "reason": {"type": "string"},
        },
        "required": ["obligation_id", "status", "claim_indexes", "reason"],
        "additionalProperties": False,
    },
}
REPAIR_SCHEMA_R1["required"] = [*SCHEMA_R1["required"], "obligation_assertions"]


def json_schema_format(schema: dict[str, Any] = SCHEMA_R1) -> dict[str, Any]:
    if schema is REPAIR_SCHEMA_R1:
        name = "deal_graph_v1_repair_claim_schema"
    elif schema is SCHEMA_R1:
        name = "deal_graph_v1_claim_schema"
    else:
        name = "custom_json_schema"
    return {
        "type": "json_schema",
        "name": name,
        "schema": schema,
        "strict": True,
    }


def schema_hash(schema: dict[str, Any] = SCHEMA_R1) -> str:
    encoded = json.dumps(schema, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def parse_json_text(text: str) -> dict[str, Any]:
    candidate = text.strip()
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise MalformedJSONError(str(exc)) from exc
    if not isinstance(parsed, dict):
        raise MalformedJSONError("expected JSON object")
    return parsed


def parse_repair_json_text(text: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    parsed = parse_json_text(text)
    _validate_schema_value(REPAIR_SCHEMA_R1, parsed)
    obligation_assertions = parsed.pop("obligation_assertions")
    _ensure_extraction_shape(parsed)
    return parsed, obligation_assertions


def _ensure_source_quote_page_pairing(parsed: dict[str, Any]) -> None:
    for index, event in enumerate(parsed.get("events") or []):
        if not isinstance(event, dict):
            continue
        quote = event.get("source_quote")
        page = event.get("source_page")
        quote_is_list = isinstance(quote, list)
        page_is_list = isinstance(page, list)
        if quote_is_list != page_is_list:
            raise MalformedJSONError(
                f"$.events[{index}].source_quote/source_page: multi-quote form "
                "requires both fields to be lists"
            )
        if quote_is_list and len(quote) != len(page):
            raise MalformedJSONError(
                f"$.events[{index}].source_quote/source_page: list lengths differ"
            )


def _ensure_extraction_shape(parsed: dict[str, Any], schema: dict[str, Any] = SCHEMA_R1) -> None:
    missing = [name for name in schema["required"] if name not in parsed]
    if missing:
        raise MalformedJSONError(
            "expected deal_graph_v1 claim object; missing " + ", ".join(missing)
        )
    _validate_schema_value(schema, parsed)


async def call_json(
    client: LLMClient,
    *,
    system: str,
    user: str,
    model: str,
    schema: dict[str, Any] = SCHEMA_R1,
    max_output_tokens: int | None = None,
    reasoning_effort: str | None = None,
) -> CompletionResult:
    result = await client.complete(
        system=system,
        user=user,
        model=model,
        text_format=json_schema_format(schema),
        max_output_tokens=max_output_tokens,
        reasoning_effort=reasoning_effort,
    )
    parsed = parse_json_text(result.text)
    if schema is SCHEMA_R1:
        _ensure_extraction_shape(parsed)
    else:
        _validate_schema_value(schema, parsed)
    result.parsed_json = parsed
    return result
