"""Human-review row projection from deal_graph_v1 snapshots."""
from __future__ import annotations

from typing import Any


def project_review_rows(graph: dict[str, Any]) -> list[dict[str, Any]]:
    actors = {row["actor_id"]: row for row in graph.get("actors", [])}
    evidence_by_row = _evidence_by_row(graph)
    links_by_event: dict[str, list[dict[str, Any]]] = {}
    for link in graph.get("event_actor_links", []):
        links_by_event.setdefault(link["event_id"], []).append(link)

    rows: list[dict[str, Any]] = []
    for event in sorted(graph.get("events", []), key=lambda row: (row.get("event_date") or "", row.get("event_id") or "")):
        for link in links_by_event.get(event["event_id"], []) or [None]:
            actor = actors.get(link.get("actor_id")) if link else None
            evidence = evidence_by_row.get(("events", event["event_id"]), [])
            rows.append({
                "deal_slug": graph.get("deal_slug"),
                "cycle_id": event.get("cycle_id"),
                "event_id": event.get("event_id"),
                "event_date": event.get("event_date"),
                "event_type": event.get("event_type"),
                "event_subtype": event.get("event_subtype"),
                "actor_id": actor.get("actor_id") if actor else None,
                "actor_label": actor.get("actor_label") if actor else None,
                "actor_kind": actor.get("actor_kind") if actor else None,
                "actor_role": link.get("role") if link else None,
                "bid_value": event.get("bid_value"),
                "bid_value_lower": event.get("bid_value_lower"),
                "bid_value_upper": event.get("bid_value_upper"),
                "bid_value_unit": event.get("bid_value_unit"),
                "consideration_type": event.get("consideration_type"),
                "source_quote": _source_value(evidence, "quote_text"),
                "source_page": _source_value(evidence, "source_page"),
            })
    return rows


def _evidence_by_row(graph: dict[str, Any]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    evidence = {row["evidence_id"]: row for row in graph.get("evidence", [])}
    result: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for link in graph.get("row_evidence", []):
        key = (link.get("row_table"), link.get("row_id"))
        if link.get("evidence_id") in evidence:
            result.setdefault(key, []).append(evidence[link["evidence_id"]])
    return result


def _source_value(evidence_rows: list[dict[str, Any]], key: str) -> Any:
    values = [row.get(key) for row in evidence_rows if row.get(key) is not None]
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return values
