"""Canonicalize deal_graph_v2 claim payloads into graph snapshots.

This module intentionally works with plain dictionaries.  Store-backed workers
can persist the same tables elsewhere and then pass equivalent rows into the
validators and projectors.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any

SUPPORTED_DISPOSITIONS = {"supported", "merged_duplicate"}
CLAIM_FAMILY_ORDER: tuple[tuple[str, str], ...] = (
    ("actor_claims", "actor"),
    ("actor_relation_claims", "actor_relation"),
    ("event_claims", "event"),
    ("bid_claims", "bid"),
    ("participation_count_claims", "participation_count"),
)


def iter_provider_claims(payload: dict[str, Any]):
    sequence = 1
    for family, claim_type in CLAIM_FAMILY_ORDER:
        for index, claim in enumerate(payload.get(family, []) or []):
            yield family, claim_type, index, sequence, claim
            sequence += 1


def claim_id_for_provider_claim(
    *,
    deal_slug: str,
    claim_type: str,
    sequence: int,
    claim: dict[str, Any],
) -> str:
    return _stable_id("claim", deal_slug, claim_type, sequence, _provider_raw_value(claim))


@dataclass
class Canonicalizer:
    deal_slug: str
    run_id: str
    deal_id: str
    filing_id: str
    target_name: str | None = None
    evidence: list[dict[str, Any]] = field(default_factory=list)
    claims: list[dict[str, Any]] = field(default_factory=list)
    claim_evidence: list[dict[str, Any]] = field(default_factory=list)
    claim_dispositions: list[dict[str, Any]] = field(default_factory=list)
    claim_coverage_links: list[dict[str, Any]] = field(default_factory=list)
    coverage_results: list[dict[str, Any]] = field(default_factory=list)
    actors: list[dict[str, Any]] = field(default_factory=list)
    actor_relations: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    event_actor_links: list[dict[str, Any]] = field(default_factory=list)
    participation_counts: list[dict[str, Any]] = field(default_factory=list)
    row_evidence: list[dict[str, Any]] = field(default_factory=list)
    review_flags: list[dict[str, Any]] = field(default_factory=list)
    actor_index: dict[str, dict[str, Any]] = field(default_factory=dict)
    bound_evidence_ids_by_claim: dict[str, list[str]] = field(default_factory=dict)
    claim_failures: dict[str, dict[str, Any]] = field(default_factory=dict)

    def actor(
        self,
        label: str | None,
        *,
        actor_kind: str = "organization",
        observability: str = "named",
        bidder_class: str | None = None,
    ) -> dict[str, Any] | None:
        if not label:
            return None
        key = _norm_key(label)
        existing = self.actor_index.get(key)
        if existing:
            if existing["actor_kind"] == "organization" and actor_kind != "organization":
                existing["actor_kind"] = actor_kind
            if existing["observability"] == "named" and observability != "named":
                existing["observability"] = observability
            if bidder_class and existing["bidder_class"] in {None, "unknown"}:
                existing["bidder_class"] = bidder_class
            return existing
        actor_id = _stable_id("actor", self.deal_slug, label)
        row = {
            "actor_id": actor_id,
            "run_id": self.run_id,
            "deal_id": self.deal_id,
            "actor_label": label,
            "actor_kind": actor_kind,
            "observability": observability,
            "bidder_class": bidder_class or "unknown",
            "lead_arranger_label": None,
            "member_count_known": None,
            "has_strategic_member": False,
            "has_financial_member": False,
            "has_sovereign_wealth_member": False,
        }
        self.actor_index[key] = row
        self.actors.append(row)
        return row

    def add_claim(self, claim_type: str, claim: dict[str, Any], sequence: int) -> tuple[str, list[str]]:
        raw_value = _provider_raw_value(claim)
        claim_id = claim_id_for_provider_claim(
            deal_slug=self.deal_slug,
            claim_type=claim_type,
            sequence=sequence,
            claim=claim,
        )
        quote = _primary_quote(raw_value)
        evidence_ids = list(self.bound_evidence_ids_by_claim.get(claim_id, []))
        failure = self.claim_failures.get(claim_id)
        self.claims.append({
            "claim_id": claim_id,
            "run_id": self.run_id,
            "filing_id": self.filing_id,
            "deal_slug": self.deal_slug,
            "region_id": None,
            "provider_source_stage": "extractor_claims",
            "claim_type": claim_type,
            "confidence": claim.get("confidence", "unknown"),
            "raw_value": raw_value,
            "normalized_value": _normalized_claim_value(claim_type, claim),
            "quote_text": quote,
            "quote_text_hash": _hash_text(quote),
            "status": "current",
            "claim_sequence": sequence,
            "coverage_obligation_id": claim.get("coverage_obligation_id"),
        })
        for ordinal, evidence_id in enumerate(evidence_ids, start=1):
            self.claim_evidence.append({
                "claim_id": claim_id,
                "evidence_id": evidence_id,
                "ordinal": ordinal,
            })
        obligation_id = claim.get("coverage_obligation_id")
        if obligation_id and not failure:
            self.claim_coverage_links.append({
                "claim_id": claim_id,
                "obligation_id": obligation_id,
                "run_id": self.run_id,
                "deal_slug": self.deal_slug,
                "claim_type": claim_type,
                "current": True,
            })
            self.coverage_results.append({
                "coverage_result_id": _stable_id("coverage", self.run_id, obligation_id),
                "run_id": self.run_id,
                "obligation_id": obligation_id,
                "result": "claims_emitted",
                "reason_code": "claim_present",
                "reason": "At least one current claim is linked to this obligation.",
                "claim_count": 1,
                "current": True,
            })
        disposition = "rejected_unsupported" if failure else "supported"
        reason_code = failure.get("reason_code") if failure else "evidence_refs_bound"
        reason = failure.get("reason") if failure else "All evidence refs bound to citation units."
        self.claim_dispositions.append({
            "disposition_id": _stable_id("disposition", self.run_id, claim_id),
            "claim_id": claim_id,
            "run_id": self.run_id,
            "disposition": disposition,
            "current": True,
            "reason_code": reason_code,
            "reason": reason,
        })
        return claim_id, evidence_ids

    def link_row_evidence(self, row_table: str, row_id: str, evidence_ids: list[str]) -> None:
        for ordinal, evidence_id in enumerate(evidence_ids, start=1):
            self.row_evidence.append({
                "row_table": row_table,
                "row_id": row_id,
                "evidence_id": evidence_id,
                "ordinal": ordinal,
            })

    def canonicalize_actor_claim(self, claim: dict[str, Any], sequence: int) -> None:
        claim_id, evidence_ids = self.add_claim("actor", claim, sequence)
        if claim_id in self.claim_failures:
            return
        actor = self.actor(
            claim.get("actor_label"),
            actor_kind=claim.get("actor_kind") or "organization",
            observability=claim.get("observability") or "named",
            bidder_class=_normalize_bidder_class(claim.get("actor_class") or claim.get("bidder_class")),
        )
        if actor:
            self.link_row_evidence("actors", actor["actor_id"], evidence_ids)

    def canonicalize_actor_relation_claim(self, claim: dict[str, Any], sequence: int) -> None:
        claim_id, evidence_ids = self.add_claim("actor_relation", claim, sequence)
        if claim_id in self.claim_failures:
            return
        subject = self.actor(claim.get("subject_label"))
        object_actor = self.actor(
            claim.get("object_label"),
            actor_kind="group" if claim.get("relation_type") in {"member_of", "joins_group", "exits_group"} else "organization",
        )
        if not subject or not object_actor:
            return
        self.link_row_evidence("actors", subject["actor_id"], evidence_ids)
        self.link_row_evidence("actors", object_actor["actor_id"], evidence_ids)
        relation_id = _stable_id(
            "relation",
            self.deal_slug,
            subject["actor_id"],
            object_actor["actor_id"],
            claim.get("relation_type"),
            claim.get("effective_date_first"),
            claim.get("role_detail"),
        )
        relation = {
            "relation_id": relation_id,
            "run_id": self.run_id,
            "deal_id": self.deal_id,
            "subject_actor_id": subject["actor_id"],
            "object_actor_id": object_actor["actor_id"],
            "subject_actor_label": subject["actor_label"],
            "object_actor_label": object_actor["actor_label"],
            "relation_type": claim.get("relation_type"),
            "role_detail": claim.get("role_detail"),
            "cycle_id_first_observed": _cycle_id(self.deal_slug, 1),
            "cycle_id_last_observed": None,
            "effective_date_first": claim.get("effective_date_first"),
            "effective_date_last": claim.get("effective_date_last"),
            "confidence": claim.get("confidence", "unknown"),
        }
        self.actor_relations.append(relation)
        self.link_row_evidence("actor_relations", relation_id, evidence_ids)
        _apply_relation_class_signal(subject, object_actor, relation)

    def canonicalize_event_claim(self, claim: dict[str, Any], sequence: int) -> None:
        claim_id, evidence_ids = self.add_claim("event", claim, sequence)
        if claim_id in self.claim_failures:
            return
        actor = self.actor(claim.get("actor_label"))
        event_id = _stable_id("event", self.deal_slug, "event", sequence, claim)
        event = {
            "event_id": event_id,
            "run_id": self.run_id,
            "deal_id": self.deal_id,
            "cycle_id": _cycle_id(self.deal_slug, 1),
            "event_type": claim.get("event_type") or "process",
            "event_subtype": claim.get("event_subtype"),
            "event_date": claim.get("event_date"),
            "description": claim.get("description"),
            "bid_value": None,
            "bid_value_lower": None,
            "bid_value_upper": None,
            "bid_value_unit": None,
            "consideration_type": None,
            "bid_stage": None,
        }
        self.events.append(event)
        self.link_row_evidence("events", event_id, evidence_ids)
        if actor:
            self.link_row_evidence("actors", actor["actor_id"], evidence_ids)
            self.event_actor_links.append({
                "link_id": _stable_id("link", event_id, actor["actor_id"], claim.get("actor_role")),
                "run_id": self.run_id,
                "event_id": event_id,
                "actor_id": actor["actor_id"],
                "actor_label": actor["actor_label"],
                "role": claim.get("actor_role") or _default_role_for_event(event),
                "role_detail": claim.get("role_detail"),
            })

    def canonicalize_bid_claim(self, claim: dict[str, Any], sequence: int) -> None:
        claim_id, evidence_ids = self.add_claim("bid", claim, sequence)
        if claim_id in self.claim_failures:
            return
        actor = self.actor(claim.get("bidder_label"), actor_kind="group" if _looks_group(claim.get("bidder_label")) else "organization")
        subtype = "final_round_bid" if claim.get("bid_stage") == "final" else "first_round_bid"
        event_id = _stable_id("event", self.deal_slug, "bid", sequence, claim)
        event = {
            "event_id": event_id,
            "run_id": self.run_id,
            "deal_id": self.deal_id,
            "cycle_id": _cycle_id(self.deal_slug, 1),
            "event_type": "bid",
            "event_subtype": subtype,
            "event_date": claim.get("bid_date"),
            "description": claim.get("description") or f"Bid submitted by {claim.get('bidder_label')}",
            "bid_value": claim.get("bid_value"),
            "bid_value_lower": claim.get("bid_value_lower"),
            "bid_value_upper": claim.get("bid_value_upper"),
            "bid_value_unit": claim.get("bid_value_unit"),
            "consideration_type": claim.get("consideration_type"),
            "bid_stage": claim.get("bid_stage") or "unspecified",
        }
        self.events.append(event)
        self.link_row_evidence("events", event_id, evidence_ids)
        if actor:
            self.link_row_evidence("actors", actor["actor_id"], evidence_ids)
            self.event_actor_links.append({
                "link_id": _stable_id("link", event_id, actor["actor_id"], "bid_submitter"),
                "run_id": self.run_id,
                "event_id": event_id,
                "actor_id": actor["actor_id"],
                "actor_label": actor["actor_label"],
                "role": "bid_submitter",
                "role_detail": None,
            })

    def canonicalize_participation_count_claim(self, claim: dict[str, Any], sequence: int) -> None:
        claim_id, evidence_ids = self.add_claim("participation_count", claim, sequence)
        if claim_id in self.claim_failures:
            return
        count_id = _stable_id("participation_count", self.deal_slug, sequence, claim)
        row = {
            "participation_count_id": count_id,
            "run_id": self.run_id,
            "deal_id": self.deal_id,
            "cycle_id": _cycle_id(self.deal_slug, 1),
            "process_stage": claim.get("process_stage"),
            "actor_class": claim.get("actor_class") or "unknown",
            "count_min": claim.get("count_min"),
            "count_max": claim.get("count_max"),
            "count_qualifier": claim.get("count_qualifier"),
            "confidence": claim.get("confidence", "unknown"),
        }
        self.participation_counts.append(row)
        self.link_row_evidence("participation_counts", count_id, evidence_ids)

    def snapshot(self) -> dict[str, Any]:
        _propagate_member_class_signals(self.actors, self.actor_relations)
        _dedupe_coverage_results(self.coverage_results)
        return {
            "schema_version": "deal_graph_v2",
            "run_id": self.run_id,
            "deal_slug": self.deal_slug,
            "deals": [{
                "deal_id": self.deal_id,
                "run_id": self.run_id,
                "deal_slug": self.deal_slug,
                "target_actor_id": _stable_id("actor", self.deal_slug, self.target_name) if self.target_name else None,
                "target_name": self.target_name,
                "announcement_date": None,
                "effective_date": None,
                "all_cash": None,
            }],
            "process_cycles": [{
                "cycle_id": _cycle_id(self.deal_slug, 1),
                "run_id": self.run_id,
                "deal_id": self.deal_id,
                "cycle_sequence": 1,
                "cycle_label": "primary",
                "start_date": None,
                "end_date": None,
            }],
            "evidence": self.evidence,
            "claims": self.claims,
            "claim_evidence": self.claim_evidence,
            "claim_dispositions": self.claim_dispositions,
            "claim_coverage_links": self.claim_coverage_links,
            "coverage_results": self.coverage_results,
            "actors": self.actors,
            "actor_relations": self.actor_relations,
            "events": self.events,
            "event_actor_links": self.event_actor_links,
            "participation_counts": self.participation_counts,
            "row_evidence": self.row_evidence,
            "review_flags": self.review_flags,
        }


def canonicalize_claim_payload(
    payload: dict[str, Any],
    *,
    deal_slug: str,
    run_id: str = "local",
    evidence_context: dict[str, Any] | None = None,
    target_name: str | None = None,
) -> dict[str, Any]:
    """Convert a claim-only provider payload into a canonical graph snapshot."""
    if payload.get("schema_version") and payload.get("schema_version") != "deal_graph_claims_v1":
        raise ValueError("claim payload must not be an old canonical/output snapshot")
    rejected = {"coverage_results", "BidderID", "T", "bI", "bF", "projection_rows", "events"}
    found = rejected.intersection(payload)
    if found:
        raise ValueError(f"provider payload contains Python-owned fields: {sorted(found)}")

    evidence_context = evidence_context or {}
    canonicalizer = Canonicalizer(
        deal_slug=deal_slug,
        run_id=run_id,
        deal_id=_stable_id("deal", deal_slug),
        filing_id=str(evidence_context.get("filing_id") or _stable_id("filing", deal_slug, run_id)),
        target_name=target_name,
        evidence=list(evidence_context.get("evidence", [])),
        bound_evidence_ids_by_claim=dict(evidence_context.get("claim_evidence_ids", {})),
        claim_failures=dict(evidence_context.get("claim_failures", {})),
        review_flags=list(evidence_context.get("review_flags", [])),
    )
    for _family, claim_type, _index, sequence, claim in iter_provider_claims(payload):
        if claim_type == "actor":
            canonicalizer.canonicalize_actor_claim(claim, sequence)
        elif claim_type == "actor_relation":
            canonicalizer.canonicalize_actor_relation_claim(claim, sequence)
        elif claim_type == "event":
            canonicalizer.canonicalize_event_claim(claim, sequence)
        elif claim_type == "bid":
            canonicalizer.canonicalize_bid_claim(claim, sequence)
        elif claim_type == "participation_count":
            canonicalizer.canonicalize_participation_count_claim(claim, sequence)
    return canonicalizer.snapshot()


def _normalized_claim_value(claim_type: str, claim: dict[str, Any]) -> dict[str, Any]:
    if claim_type == "actor":
        return {"actor_label": claim.get("actor_label")}
    if claim_type == "actor_relation":
        return {
            "subject_label": claim.get("subject_label"),
            "object_label": claim.get("object_label"),
            "relation_type": claim.get("relation_type"),
        }
    if claim_type == "bid":
        return {
            "bidder_label": claim.get("bidder_label"),
            "bid_date": claim.get("bid_date"),
            "bid_value": claim.get("bid_value"),
            "bid_stage": claim.get("bid_stage"),
        }
    return dict(claim)


def _provider_raw_value(claim: dict[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value)
        for key, value in claim.items()
        if not str(key).startswith("_")
    }


def _primary_quote(claim: dict[str, Any]) -> str:
    refs = claim.get("evidence_refs") or []
    if isinstance(refs, list) and refs and isinstance(refs[0], dict):
        quote = refs[0].get("quote_text")
        if isinstance(quote, str):
            return quote
    return ""


def _apply_relation_class_signal(subject: dict[str, Any], object_actor: dict[str, Any], relation: dict[str, Any]) -> None:
    detail = " ".join(str(value or "") for value in (subject.get("actor_label"), relation.get("role_detail"))).lower()
    if any(token in detail for token in ("strategic", "operating", "corporate", "portfolio company")):
        subject["bidder_class"] = "strategic"
        object_actor["has_strategic_member"] = True
        if object_actor["bidder_class"] in {"unknown", None, "financial"}:
            object_actor["bidder_class"] = "strategic"
    if any(token in detail for token in ("financial", "sponsor", "private equity", "financing", "capital")):
        subject["bidder_class"] = "financial"
        object_actor["has_financial_member"] = True
        if object_actor["bidder_class"] in {"unknown", None}:
            object_actor["bidder_class"] = "financial"
        elif object_actor["bidder_class"] != "financial" and not object_actor["has_strategic_member"]:
            object_actor["bidder_class"] = "mixed"
    if object_actor["has_strategic_member"] and object_actor["has_financial_member"]:
        # Mixed groups with a source-backed strategic member remain strategic
        # for canonical bidder-class review.
        object_actor["bidder_class"] = "strategic"


def _propagate_member_class_signals(
    actors: list[dict[str, Any]],
    relations: list[dict[str, Any]],
) -> None:
    actors_by_id = {row["actor_id"]: row for row in actors}
    for relation in relations:
        if relation.get("relation_type") not in {"member_of", "joins_group"}:
            continue
        subject = actors_by_id.get(relation.get("subject_actor_id"))
        group = actors_by_id.get(relation.get("object_actor_id"))
        if not subject or not group:
            continue
        if subject.get("bidder_class") == "strategic":
            group["has_strategic_member"] = True
        if subject.get("bidder_class") == "financial":
            group["has_financial_member"] = True
        if group.get("has_strategic_member") and group.get("has_financial_member"):
            group["bidder_class"] = "strategic"
        elif group.get("has_strategic_member"):
            group["bidder_class"] = "strategic"
        elif group.get("has_financial_member") and group.get("bidder_class") in {None, "unknown"}:
            group["bidder_class"] = "financial"


def _dedupe_coverage_results(rows: list[dict[str, Any]]) -> None:
    by_obligation: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = row["obligation_id"]
        if key in by_obligation:
            by_obligation[key]["claim_count"] += 1
        else:
            by_obligation[key] = row
    rows[:] = list(by_obligation.values())


def _default_role_for_event(event: dict[str, Any]) -> str:
    return "bid_submitter" if event.get("event_type") == "bid" else "participant"


def _looks_group(label: str | None) -> bool:
    return bool(label and any(token in label.lower() for token in ("group", "/", "consortium", "club")))


def _normalize_bidder_class(value: str | None) -> str | None:
    if value in {"strategic", "financial", "mixed", "unknown"}:
        return value
    if value == "s":
        return "strategic"
    if value == "f":
        return "financial"
    return None


def _norm_key(value: str) -> str:
    return " ".join(value.casefold().split())


def _cycle_id(deal_slug: str, sequence: int) -> str:
    return _stable_id("cycle", deal_slug, sequence)


def _hash_text(value: Any) -> str | None:
    if value is None:
        return None
    return sha256(str(value).encode("utf-8")).hexdigest()


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(part) for part in parts)
    return f"{prefix}_{sha256(raw.encode('utf-8')).hexdigest()[:16]}"
