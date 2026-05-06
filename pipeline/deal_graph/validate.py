"""Validation for deal_graph_v2 graph snapshots."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ValidationFlag:
    code: str
    severity: str
    reason: str
    row_table: str | None = None
    row_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "reason": self.reason,
            "row_table": self.row_table,
            "row_id": self.row_id,
        }


CANONICAL_ROW_TABLES = {
    "actors": "actor_id",
    "actor_relations": "relation_id",
    "events": "event_id",
    "participation_counts": "participation_count_id",
}


def validate_graph(graph: dict[str, Any]) -> list[ValidationFlag]:
    """Return hard validation flags for missing graph proof/disposition data."""
    flags: list[ValidationFlag] = []
    if graph.get("schema_version") != "deal_graph_v2":
        flags.append(ValidationFlag(
            code="DG_SCHEMA_VERSION",
            severity="hard",
            reason="Canonical graph snapshot must declare schema_version=deal_graph_v2.",
        ))

    claims = {row["claim_id"]: row for row in graph.get("claims", []) if row.get("claim_id")}
    dispositions_by_claim = _current_by_key(graph.get("claim_dispositions", []), "claim_id")
    evidence_by_claim = _rows_by_key(graph.get("claim_evidence", []), "claim_id")
    coverage_by_claim = _rows_by_key(graph.get("claim_coverage_links", []), "claim_id")

    for claim_id, claim in claims.items():
        dispositions = dispositions_by_claim.get(claim_id, [])
        if len(dispositions) != 1:
            flags.append(ValidationFlag(
                code="DG_CLAIM_DISPOSITION_MISSING",
                severity="hard",
                reason="Every claim must have exactly one current disposition.",
                row_table="claims",
                row_id=claim_id,
            ))
            disposition = None
        else:
            disposition = dispositions[0].get("disposition")
        requires_support = disposition is None or disposition in {"supported", "merged_duplicate"}
        if requires_support and not evidence_by_claim.get(claim_id):
            flags.append(ValidationFlag(
                code="DG_CLAIM_EVIDENCE_MISSING",
                severity="hard",
                reason="Every claim must link to source evidence.",
                row_table="claims",
                row_id=claim_id,
            ))
        if requires_support and claim.get("coverage_obligation_id") and not coverage_by_claim.get(claim_id):
            flags.append(ValidationFlag(
                code="DG_CLAIM_COVERAGE_LINK_MISSING",
                severity="hard",
                reason="Claims emitted for an obligation must link back to that obligation.",
                row_table="claims",
                row_id=claim_id,
            ))

    coverage_results = _current_by_key(graph.get("coverage_results", []), "obligation_id")
    obligation_ids = {
        row.get("obligation_id")
        for row in graph.get("coverage_obligations", [])
        if row.get("current", True) and row.get("applicability", "applicable") == "applicable"
    }
    for claim_id, claim in claims.items():
        dispositions = dispositions_by_claim.get(claim_id, [])
        disposition = dispositions[0].get("disposition") if len(dispositions) == 1 else None
        if (
            disposition in {"supported", "merged_duplicate"}
            and claim.get("coverage_obligation_id")
        ):
            obligation_ids.add(claim.get("coverage_obligation_id"))
    for obligation_id in sorted(obligation_ids):
        if len(coverage_results.get(obligation_id, [])) != 1:
            flags.append(ValidationFlag(
                code="DG_COVERAGE_RESULT_MISSING",
                severity="hard",
                reason="Every current applicable obligation must have exactly one current coverage result.",
                row_table="coverage_obligations",
                row_id=obligation_id,
            ))

    row_evidence = {
        (row.get("row_table"), row.get("row_id"))
        for row in graph.get("row_evidence", [])
        if row.get("row_table") and row.get("row_id")
    }
    for table, id_field in CANONICAL_ROW_TABLES.items():
        for row in graph.get(table, []):
            row_id = row.get(id_field)
            if row_id and (table, row_id) not in row_evidence:
                flags.append(ValidationFlag(
                    code="DG_ROW_EVIDENCE_MISSING",
                    severity="hard",
                    reason=f"Canonical {table} row must link to source evidence.",
                    row_table=table,
                    row_id=row_id,
                ))

    event_ids = {row.get("event_id") for row in graph.get("events", [])}
    actor_ids = {row.get("actor_id") for row in graph.get("actors", [])}
    for link in graph.get("event_actor_links", []):
        if link.get("event_id") not in event_ids:
            flags.append(ValidationFlag("DG_EVENT_LINK_ORPHAN", "hard", "Event actor link references a missing event.", "event_actor_links", link.get("link_id")))
        if link.get("actor_id") not in actor_ids:
            flags.append(ValidationFlag("DG_EVENT_LINK_ORPHAN", "hard", "Event actor link references a missing actor.", "event_actor_links", link.get("link_id")))

    unresolved = [
        row for row in graph.get("review_flags", [])
        if (
            row.get("severity") == "blocking"
            and row.get("current", True) is not False
            and row.get("status", "open") != "resolved"
        )
    ]
    for row in unresolved:
        flags.append(ValidationFlag(
            code=row.get("code", "DG_BLOCKING_REVIEW_FLAG"),
            severity="hard",
            reason=row.get("reason", "Unresolved blocking graph review flag."),
            row_table=row.get("row_table"),
            row_id=row.get("row_id"),
        ))
    return flags


def validate_graph_as_dicts(graph: dict[str, Any]) -> list[dict[str, Any]]:
    return [flag.as_dict() for flag in validate_graph(graph)]


def _current_by_key(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if row.get("current", True):
            grouped.setdefault(row.get(key), []).append(row)
    return grouped


def _rows_by_key(rows: list[dict[str, Any]], key: str) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row.get(key), []).append(row)
    return grouped


def main() -> None:
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Validate a deal_graph_v2 snapshot.")
    parser.add_argument("snapshot", type=Path)
    args = parser.parse_args()
    flags = validate_graph_as_dicts(json.loads(args.snapshot.read_text()))
    print(json.dumps({"flags": flags, "hard_flag_count": len(flags)}, indent=2, sort_keys=True))
    raise SystemExit(1 if flags else 0)


if __name__ == "__main__":
    main()
