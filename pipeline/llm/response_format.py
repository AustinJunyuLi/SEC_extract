from __future__ import annotations

import hashlib
import json
from typing import Any

from pipeline.deal_graph.schema import (
    ActorClass,
    ActorKind,
    BidStage,
    BidValueUnit,
    Confidence,
    ConsiderationType,
    CountQualifier,
    EventSubtype,
    EventType,
    Observability,
    ProcessStage,
    RelationType,
)
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


def _enum_values(enum_cls: Any) -> list[str]:
    return [member.value for member in enum_cls]


def _nullable_enum_values(enum_cls: Any) -> list[str | None]:
    return [*_enum_values(enum_cls), None]


CONFIDENCE_SCHEMA = {"type": "string", "enum": _enum_values(Confidence)}
QUOTE_TEXT_SCHEMA = {"type": "string", "maxLength": 1500}
EVIDENCE_REF_SCHEMA = {
    "type": "object",
    "properties": {
        "citation_unit_id": {"type": "string"},
        "quote_text": QUOTE_TEXT_SCHEMA,
    },
    "required": ["citation_unit_id", "quote_text"],
    "additionalProperties": False,
}
EVIDENCE_REFS_SCHEMA = {
    "type": "array",
    "items": EVIDENCE_REF_SCHEMA,
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
            "enum": _enum_values(ActorKind),
        },
        "observability": {
            "type": "string",
            "enum": _enum_values(Observability),
        },
        "confidence": CONFIDENCE_SCHEMA,
        "evidence_refs": EVIDENCE_REFS_SCHEMA,
    },
    "required": [
        "claim_type",
        "coverage_obligation_id",
        "actor_label",
        "actor_kind",
        "observability",
        "confidence",
        "evidence_refs",
    ],
    "additionalProperties": False,
}

EVENT_CLAIM_SCHEMA = {
    "type": "object",
    "properties": {
        "claim_type": {"type": "string", "enum": ["event"]},
        "coverage_obligation_id": {"type": "string"},
        "event_type": {"type": "string", "enum": _enum_values(EventType)},
        "event_subtype": {
            "type": "string",
            "enum": _enum_values(EventSubtype),
        },
        "event_date": {"type": ["string", "null"]},
        "description": {"type": "string"},
        "actor_label": {"type": ["string", "null"]},
        "actor_role": {"type": ["string", "null"]},
        "confidence": CONFIDENCE_SCHEMA,
        "evidence_refs": EVIDENCE_REFS_SCHEMA,
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
        "evidence_refs",
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
            "enum": _nullable_enum_values(BidValueUnit),
        },
        "consideration_type": {
            "type": ["string", "null"],
            "enum": _nullable_enum_values(ConsiderationType),
        },
        "bid_stage": {
            "type": "string",
            "enum": _enum_values(BidStage),
        },
        "confidence": CONFIDENCE_SCHEMA,
        "evidence_refs": EVIDENCE_REFS_SCHEMA,
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
        "evidence_refs",
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
            "enum": _enum_values(ProcessStage),
        },
        "actor_class": {
            "type": "string",
            "enum": _enum_values(ActorClass),
        },
        "count_min": {"type": "integer"},
        "count_max": {"type": ["integer", "null"]},
        "count_qualifier": {"type": "string", "enum": _enum_values(CountQualifier)},
        "confidence": CONFIDENCE_SCHEMA,
        "evidence_refs": EVIDENCE_REFS_SCHEMA,
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
        "evidence_refs",
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
            "enum": _enum_values(RelationType),
        },
        "role_detail": {"type": ["string", "null"]},
        "effective_date_first": {"type": ["string", "null"]},
        "confidence": CONFIDENCE_SCHEMA,
        "evidence_refs": EVIDENCE_REFS_SCHEMA,
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
        "evidence_refs",
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

def json_schema_format(schema: dict[str, Any] = DEAL_GRAPH_CLAIM_SCHEMA) -> dict[str, Any]:
    if schema is not DEAL_GRAPH_CLAIM_SCHEMA:
        raise ValueError("only the live deal_graph_v2 claim schema is allowed")
    return {
        "type": "json_schema",
        "name": "deal_graph_v2_claim_schema",
        "schema": schema,
        "strict": True,
    }


def schema_hash(schema: dict[str, Any] = DEAL_GRAPH_CLAIM_SCHEMA) -> str:
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


def _ensure_extraction_shape(parsed: dict[str, Any], schema: dict[str, Any] = DEAL_GRAPH_CLAIM_SCHEMA) -> None:
    missing = [name for name in schema["required"] if name not in parsed]
    if missing:
        raise MalformedJSONError(
            "expected deal_graph_v2 claim object; missing " + ", ".join(missing)
        )
    _validate_schema_value(schema, parsed)


async def call_json(
    client: LLMClient,
    *,
    system: str,
    user: str,
    model: str,
    max_output_tokens: int | None = None,
    reasoning_effort: str | None = None,
) -> CompletionResult:
    result = await client.complete(
        system=system,
        user=user,
        model=model,
        text_format=json_schema_format(DEAL_GRAPH_CLAIM_SCHEMA),
        max_output_tokens=max_output_tokens,
        reasoning_effort=reasoning_effort,
    )
    parsed = parse_json_text(result.text)
    _ensure_extraction_shape(parsed)
    result.parsed_json = parsed
    return result
