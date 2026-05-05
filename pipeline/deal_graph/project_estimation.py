"""Estimator bidder-row projection from deal_graph_v1 snapshots."""
from __future__ import annotations

from typing import Any

PROJECTION_RULE_VERSION = "bidder_cycle_baseline_v1"


def project_estimation_rows(graph: dict[str, Any]) -> list[dict[str, Any]]:
    actors = {row["actor_id"]: row for row in graph.get("actors", [])}
    events = {row["event_id"]: row for row in graph.get("events", [])}
    links_by_actor: dict[str, list[dict[str, Any]]] = {}
    for link in graph.get("event_actor_links", []):
        if link.get("role") == "bid_submitter":
            links_by_actor.setdefault(link["actor_id"], []).append(link)

    rows: list[dict[str, Any]] = []
    for actor_id, links in sorted(links_by_actor.items(), key=lambda item: actors[item[0]]["actor_label"]):
        bid_events = sorted(
            (events[link["event_id"]] for link in links if link.get("event_id") in events),
            key=lambda event: (event.get("event_date") or "", event.get("event_id") or ""),
        )
        if not bid_events:
            continue
        initial = _first_nonfinal_bid(bid_events)
        final = _last_final_bid(bid_events)
        boundary = final or bid_events[-1]
        actor = actors[actor_id]
        rows.append({
            "deal_slug": graph.get("deal_slug"),
            "cycle_id": boundary.get("cycle_id"),
            "actor_id": actor_id,
            "actor_label": actor.get("actor_label"),
            "bI": _bid_point(initial),
            "bI_lo": _bid_low(initial),
            "bI_hi": _bid_high(initial),
            "bF": _bid_point(final),
            "admitted": bool(final),
            "T": _project_type(actor),
            "bid_value_unit": boundary.get("bid_value_unit"),
            "consideration_type": boundary.get("consideration_type"),
            "boundary_event_id": boundary.get("event_id"),
            "formal_boundary": boundary.get("event_subtype") == "final_round_bid",
            "dropout_mechanism": _dropout_mechanism(actor_id, graph),
            "confidence_min": _confidence_min(actor_id, graph),
            "projection_rule_version": PROJECTION_RULE_VERSION,
        })
    return rows


def _first_nonfinal_bid(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for event in events:
        if event.get("event_subtype") != "final_round_bid":
            return event
    return events[0] if events else None


def _last_final_bid(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    finals = [event for event in events if event.get("event_subtype") == "final_round_bid"]
    return finals[-1] if finals else None


def _bid_point(event: dict[str, Any] | None) -> Any:
    if not event:
        return None
    return event.get("bid_value")


def _bid_low(event: dict[str, Any] | None) -> Any:
    if not event:
        return None
    return event.get("bid_value_lower") if event.get("bid_value_lower") is not None else event.get("bid_value")


def _bid_high(event: dict[str, Any] | None) -> Any:
    if not event:
        return None
    return event.get("bid_value_upper") if event.get("bid_value_upper") is not None else event.get("bid_value")


def _project_type(actor: dict[str, Any]) -> str:
    bidder_class = actor.get("bidder_class")
    if bidder_class in {"strategic", "financial", "mixed"}:
        return bidder_class
    if actor.get("has_strategic_member"):
        return "strategic"
    if actor.get("has_financial_member"):
        return "financial"
    return "unknown"


def _dropout_mechanism(actor_id: str, graph: dict[str, Any]) -> str | None:
    events = {row["event_id"]: row for row in graph.get("events", [])}
    for link in graph.get("event_actor_links", []):
        if link.get("actor_id") != actor_id:
            continue
        event = events.get(link.get("event_id"))
        if not event:
            continue
        if event.get("event_subtype") in {"withdrawn_by_bidder", "excluded_by_target", "non_responsive"}:
            return event.get("event_subtype")
    return None


def _confidence_min(actor_id: str, graph: dict[str, Any]) -> str:
    evidence_event_ids = {
        link.get("event_id")
        for link in graph.get("event_actor_links", [])
        if link.get("actor_id") == actor_id and link.get("role") == "bid_submitter"
    }
    if not evidence_event_ids:
        return "unknown"
    return "high"
