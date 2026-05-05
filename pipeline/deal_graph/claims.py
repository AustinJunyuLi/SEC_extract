"""Provider claim parsing and local row preparation."""
from __future__ import annotations

from typing import Iterable

from pydantic import BaseModel

from .ids import make_id, quote_hash, stable_json
from .schema import (
    ActorClaim,
    ActorRelationClaim,
    BidClaim,
    ClaimBase,
    ClaimRow,
    EventClaim,
    ParticipationCountClaim,
    ProviderPayload,
)


def parse_provider_payload(payload: dict) -> ProviderPayload:
    return ProviderPayload.model_validate(payload)


def iter_claims(payload: ProviderPayload) -> Iterable[ClaimBase]:
    yield from payload.actor_claims
    yield from payload.event_claims
    yield from payload.bid_claims
    yield from payload.participation_count_claims
    yield from payload.actor_relation_claims


def claim_row(
    *,
    claim: ClaimBase,
    run_id: str,
    filing_id: str,
    deal_slug: str,
    claim_sequence: int,
    region_id: str | None = None,
    provider_source_stage: str = "extractor_claims",
    status: str = "pending_quote_binding",
) -> ClaimRow:
    raw_value = claim.model_dump(mode="json")
    claim_id = make_id(
        "claim",
        run_id,
        deal_slug,
        claim.claim_type,
        claim_sequence,
        raw_value,
    )
    return ClaimRow(
        claim_id=claim_id,
        run_id=run_id,
        filing_id=filing_id,
        deal_slug=deal_slug,
        region_id=region_id,
        provider_source_stage=provider_source_stage,
        claim_type=claim.claim_type,
        confidence=claim.confidence,
        raw_value=stable_json(raw_value),
        normalized_value=None,
        quote_text=claim.quote_text,
        quote_text_hash=quote_hash(claim.quote_text),
        status=status,
        claim_sequence=claim_sequence,
    )


def typed_claim_values(claim_id: str, claim: ClaimBase) -> tuple[str, tuple]:
    if isinstance(claim, ActorClaim):
        return (
            "actor_claims",
            (claim_id, claim.actor_label, claim.actor_kind, claim.observability),
        )
    if isinstance(claim, EventClaim):
        return (
            "event_claims",
            (
                claim_id,
                claim.event_type,
                claim.event_subtype,
                claim.event_date,
                claim.description,
                claim.actor_label,
                claim.actor_role,
            ),
        )
    if isinstance(claim, BidClaim):
        return (
            "bid_claims",
            (
                claim_id,
                claim.bidder_label,
                claim.bid_date,
                claim.bid_value,
                claim.bid_value_lower,
                claim.bid_value_upper,
                claim.bid_value_unit,
                claim.consideration_type,
                claim.bid_stage,
            ),
        )
    if isinstance(claim, ParticipationCountClaim):
        return (
            "participation_count_claims",
            (
                claim_id,
                claim.process_stage,
                claim.actor_class,
                claim.count_min,
                claim.count_max,
                claim.count_qualifier,
            ),
        )
    if isinstance(claim, ActorRelationClaim):
        return (
            "actor_relation_claims",
            (
                claim_id,
                claim.subject_label,
                claim.object_label,
                claim.relation_type,
                claim.role_detail,
                claim.effective_date_first,
            ),
        )
    raise TypeError(f"unsupported claim model: {type(claim).__name__}")


def assert_relation_quote_support(claim: ActorRelationClaim) -> None:
    quote_lower = claim.quote_text.lower()
    missing = [
        label
        for label in (claim.subject_label, claim.object_label)
        if label.lower() not in quote_lower
    ]
    relation_markers = {
        "member_of": ("member", "together", "refer to as", "part of"),
        "joins_group": ("join", "joined", "became part", "together"),
        "exits_group": ("exit", "withdrew", "left"),
        "affiliate_of": ("affiliate", "affiliated"),
        "controls": ("control", "controls", "controlled"),
        "acquisition_vehicle_of": ("vehicle", "acquisition vehicle"),
        "advises": ("advise", "advisor", "advised"),
        "finances": ("finance", "financing", "capital"),
        "supports": ("support", "supported"),
        "voting_support_for": ("voting support", "support agreement", "vote"),
        "rollover_holder_for": ("rollover", "rolled", "contribute", "retain"),
    }[claim.relation_type]
    if not any(marker in quote_lower for marker in relation_markers):
        missing.append(claim.relation_type)
    if missing:
        raise ValueError(f"actor relation quote lacks support for: {missing}")


def model_to_params(model: BaseModel) -> tuple:
    return tuple(model.model_dump(mode="json").values())
