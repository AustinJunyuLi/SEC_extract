"""Schema models and SQL table contract for deal_graph_v2."""
from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator


SCHEMA_VERSION = "deal_graph_v2"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ActorKind(StrEnum):
    ORGANIZATION = "organization"
    PERSON = "person"
    GROUP = "group"
    VEHICLE = "vehicle"
    COHORT = "cohort"
    COMMITTEE = "committee"


class Observability(StrEnum):
    NAMED = "named"
    ANONYMOUS_HANDLE = "anonymous_handle"
    COUNT_ONLY = "count_only"


class EventType(StrEnum):
    PROCESS = "process"
    BID = "bid"
    TRANSACTION = "transaction"


class EventSubtype(StrEnum):
    CONTACT_INITIAL = "contact_initial"
    NDA_SIGNED = "nda_signed"
    CONSORTIUM_CA_SIGNED = "consortium_ca_signed"
    IOI_SUBMITTED = "ioi_submitted"
    FIRST_ROUND_BID = "first_round_bid"
    FINAL_ROUND_BID = "final_round_bid"
    EXCLUSIVITY_GRANT = "exclusivity_grant"
    MERGER_AGREEMENT_EXECUTED = "merger_agreement_executed"
    WITHDRAWN_BY_BIDDER = "withdrawn_by_bidder"
    EXCLUDED_BY_TARGET = "excluded_by_target"
    NON_RESPONSIVE = "non_responsive"
    COHORT_CLOSURE = "cohort_closure"
    ADVANCEMENT_ADMITTED = "advancement_admitted"
    ADVANCEMENT_DECLINED = "advancement_declined"
    ROLLOVER_EXECUTED = "rollover_executed"
    FINANCING_COMMITTED = "financing_committed"
    GO_SHOP_STARTED = "go_shop_started"
    GO_SHOP_ENDED = "go_shop_ended"


class BidStage(StrEnum):
    INITIAL = "initial"
    REVISED = "revised"
    FINAL = "final"
    UNSPECIFIED = "unspecified"


class BidValueUnit(StrEnum):
    PER_SHARE = "per_share"
    ENTERPRISE_VALUE = "enterprise_value"
    EQUITY_VALUE = "equity_value"
    UNSPECIFIED = "unspecified"


class ConsiderationType(StrEnum):
    CASH = "cash"
    STOCK = "stock"
    MIXED = "mixed"
    OTHER = "other"
    UNSPECIFIED = "unspecified"


class ProcessStage(StrEnum):
    CONTACTED = "contacted"
    NDA_SIGNED = "nda_signed"
    IOI_SUBMITTED = "ioi_submitted"
    FIRST_ROUND = "first_round"
    FINAL_ROUND = "final_round"
    EXCLUSIVITY = "exclusivity"


class ActorClass(StrEnum):
    FINANCIAL = "financial"
    STRATEGIC = "strategic"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class CountQualifier(StrEnum):
    EXACT = "exact"
    AT_LEAST = "at_least"
    AT_MOST = "at_most"
    RANGE = "range"
    APPROXIMATE = "approximate"


class RelationType(StrEnum):
    MEMBER_OF = "member_of"
    JOINS_GROUP = "joins_group"
    EXITS_GROUP = "exits_group"
    AFFILIATE_OF = "affiliate_of"
    CONTROLS = "controls"
    ACQUISITION_VEHICLE_OF = "acquisition_vehicle_of"
    ADVISES = "advises"
    FINANCES = "finances"
    SUPPORTS = "supports"
    VOTING_SUPPORT_FOR = "voting_support_for"
    ROLLOVER_HOLDER_FOR = "rollover_holder_for"


PROVIDER_FORBIDDEN_FIELDS = frozenset({
    "coverage_results",
    "BidderID",
    "T",
    "bI",
    "bF",
    "admitted",
    "dropout_outcome",
    "projection_rows",
    "canonical_id",
    "actor_id",
    "event_id",
    "relation_id",
    "source_offset",
    "char_start",
    "char_end",
    "bidder_class",
    "formal_boundary",
})


class EvidenceRef(StrictModel):
    citation_unit_id: str = Field(min_length=1)
    quote_text: str = Field(min_length=1, max_length=1500)

    @field_validator("quote_text")
    @classmethod
    def quote_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("evidence_refs.quote_text must not be blank")
        return value


class ClaimBase(StrictModel):
    claim_type: str
    coverage_obligation_id: str = Field(min_length=1)
    confidence: Confidence
    evidence_refs: list[EvidenceRef] = Field(min_length=1)


class ActorClaim(ClaimBase):
    claim_type: Literal["actor"]
    actor_label: str = Field(min_length=1)
    actor_kind: ActorKind
    observability: Observability


class EventClaim(ClaimBase):
    claim_type: Literal["event"]
    event_type: EventType
    event_subtype: EventSubtype
    event_date: str | None = None
    description: str = Field(min_length=1)
    actor_label: str | None = None
    actor_role: str | None = None


class BidClaim(ClaimBase):
    claim_type: Literal["bid"]
    bidder_label: str = Field(min_length=1)
    bid_date: str | None = None
    bid_value: float | None = None
    bid_value_lower: float | None = None
    bid_value_upper: float | None = None
    bid_value_unit: BidValueUnit | None = None
    consideration_type: ConsiderationType | None = None
    bid_stage: BidStage

    @model_validator(mode="after")
    def range_is_ordered(self) -> "BidClaim":
        if (
            self.bid_value_lower is not None
            and self.bid_value_upper is not None
            and self.bid_value_lower > self.bid_value_upper
        ):
            raise ValueError("bid_value_lower cannot exceed bid_value_upper")
        return self


class ParticipationCountClaim(ClaimBase):
    claim_type: Literal["participation_count"]
    process_stage: ProcessStage
    actor_class: ActorClass
    count_min: int = Field(ge=0)
    count_max: int | None = Field(default=None, ge=0)
    count_qualifier: CountQualifier

    @model_validator(mode="after")
    def count_range_is_ordered(self) -> "ParticipationCountClaim":
        if self.count_max is not None and self.count_min > self.count_max:
            raise ValueError("count_min cannot exceed count_max")
        return self


class ActorRelationClaim(ClaimBase):
    claim_type: Literal["actor_relation"]
    subject_label: str = Field(min_length=1)
    object_label: str = Field(min_length=1)
    relation_type: RelationType
    role_detail: str | None = None
    effective_date_first: str | None = None


class ProviderPayload(StrictModel):
    actor_claims: list[ActorClaim] = Field(default_factory=list)
    event_claims: list[EventClaim] = Field(default_factory=list)
    bid_claims: list[BidClaim] = Field(default_factory=list)
    participation_count_claims: list[ParticipationCountClaim] = Field(default_factory=list)
    actor_relation_claims: list[ActorRelationClaim] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def reject_provider_owned_fields(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        forbidden = sorted(PROVIDER_FORBIDDEN_FIELDS.intersection(data))
        if forbidden:
            raise ValueError(f"provider payload includes Python-owned fields: {forbidden}")
        for family, claims in data.items():
            if not isinstance(claims, list):
                continue
            for index, claim in enumerate(claims):
                if isinstance(claim, dict):
                    nested = sorted(PROVIDER_FORBIDDEN_FIELDS.intersection(claim))
                    if nested:
                        raise ValueError(
                            f"{family}[{index}] includes Python-owned fields: {nested}"
                        )
        return data

    @field_validator(
        "actor_claims",
        "event_claims",
        "bid_claims",
        "participation_count_claims",
        "actor_relation_claims",
    )
    @classmethod
    def claim_family_matches_field(cls, value: list[ClaimBase], info: ValidationInfo) -> list[ClaimBase]:
        expected = {
            "actor_claims": "actor",
            "event_claims": "event",
            "bid_claims": "bid",
            "participation_count_claims": "participation_count",
            "actor_relation_claims": "actor_relation",
        }[info.field_name]
        for claim in value:
            if claim.claim_type != expected:
                raise ValueError(f"{info.field_name} can only contain {expected} claims")
        return value


class FilingRow(StrictModel):
    filing_id: str
    run_id: str
    deal_slug: str
    source_path: str
    raw_sha256: str
    parser_version: str
    page_count: int
    section_count: int
    process_scope: str


class ParagraphRow(StrictModel):
    paragraph_id: str
    filing_id: str
    section: str
    page_hint: int | None
    char_start: int
    char_end: int
    paragraph_text: str
    paragraph_hash: str


class SpanRow(StrictModel):
    evidence_id: str
    filing_id: str
    paragraph_id: str
    span_basis: str
    span_kind: str
    parent_evidence_id: str | None = None
    created_by_stage: str
    char_start: int
    char_end: int
    quote_text: str
    quote_text_hash: str
    evidence_fingerprint: str


class ClaimRow(StrictModel):
    claim_id: str
    run_id: str
    filing_id: str
    deal_slug: str
    region_id: str | None = None
    provider_source_stage: str
    claim_type: str
    confidence: str
    raw_value: str
    normalized_value: str | None = None
    quote_text: str
    quote_text_hash: str
    status: str
    claim_sequence: int


class ActorRow(StrictModel):
    actor_id: str
    run_id: str
    deal_id: str
    actor_label: str
    actor_kind: ActorKind
    observability: Observability
    bidder_class: ActorClass
    lead_arranger_label: str | None = None
    member_count_known: int | None = None
    has_strategic_member: bool | None = None
    has_financial_member: bool | None = None
    has_sovereign_wealth_member: bool | None = None


EXPECTED_TABLES = frozenset({
    "filings",
    "paragraphs",
    "spans",
    "evidence_regions",
    "coverage_obligations",
    "coverage_results",
    "claims",
    "claim_coverage_links",
    "actor_claims",
    "event_claims",
    "bid_claims",
    "participation_count_claims",
    "actor_relation_claims",
    "claim_evidence",
    "claim_dispositions",
    "deals",
    "process_cycles",
    "actors",
    "actor_relations",
    "events",
    "event_actor_links",
    "participation_counts",
    "row_evidence",
    "judgments",
    "review_flags",
    "projection_units",
    "projection_judgments",
    "review_rows",
})


DDL: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS filings (
      filing_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, deal_slug TEXT NOT NULL,
      source_path TEXT NOT NULL, raw_sha256 TEXT NOT NULL, parser_version TEXT NOT NULL,
      page_count INTEGER NOT NULL, section_count INTEGER NOT NULL, process_scope TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS paragraphs (
      paragraph_id TEXT PRIMARY KEY, filing_id TEXT NOT NULL, section TEXT NOT NULL,
      page_hint INTEGER, char_start INTEGER NOT NULL, char_end INTEGER NOT NULL,
      paragraph_text TEXT NOT NULL, paragraph_hash TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS spans (
      evidence_id TEXT PRIMARY KEY, filing_id TEXT NOT NULL, paragraph_id TEXT NOT NULL,
      span_basis TEXT NOT NULL, span_kind TEXT NOT NULL, parent_evidence_id TEXT,
      created_by_stage TEXT NOT NULL, char_start INTEGER NOT NULL, char_end INTEGER NOT NULL,
      quote_text TEXT NOT NULL, quote_text_hash TEXT NOT NULL, evidence_fingerprint TEXT NOT NULL,
      run_id TEXT, deal_slug TEXT, source_page INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS evidence_regions (
      region_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, filing_id TEXT NOT NULL,
      deal_slug TEXT NOT NULL, region_kind TEXT NOT NULL, priority INTEGER NOT NULL,
      start_paragraph_id TEXT NOT NULL, end_paragraph_id TEXT NOT NULL,
      paragraph_ids_json TEXT NOT NULL, trigger_phrases_json TEXT NOT NULL,
      expected_claim_types_json TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS coverage_obligations (
      obligation_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, region_id TEXT NOT NULL,
      filing_id TEXT NOT NULL, deal_slug TEXT NOT NULL, expected_claim_type TEXT NOT NULL,
      obligation_kind TEXT NOT NULL, obligation_label TEXT NOT NULL, importance TEXT NOT NULL,
      applicability TEXT NOT NULL, applicability_reason_code TEXT,
      applicability_basis_json TEXT NOT NULL, current INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS coverage_results (
      coverage_result_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, obligation_id TEXT NOT NULL,
      result TEXT NOT NULL, reason_code TEXT NOT NULL, reason TEXT NOT NULL,
      claim_count INTEGER NOT NULL, current INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS claims (
      claim_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, filing_id TEXT NOT NULL,
      deal_slug TEXT NOT NULL, region_id TEXT, provider_source_stage TEXT NOT NULL,
      claim_type TEXT NOT NULL, confidence TEXT NOT NULL, raw_value TEXT NOT NULL,
      normalized_value TEXT, quote_text TEXT NOT NULL, quote_text_hash TEXT NOT NULL,
      status TEXT NOT NULL, claim_sequence INTEGER NOT NULL, coverage_obligation_id TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS claim_coverage_links (
      claim_id TEXT NOT NULL, obligation_id TEXT NOT NULL, run_id TEXT NOT NULL,
      deal_slug TEXT NOT NULL, claim_type TEXT NOT NULL, current INTEGER NOT NULL,
      PRIMARY KEY (claim_id, obligation_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS actor_claims (
      claim_id TEXT PRIMARY KEY, actor_label TEXT NOT NULL, actor_kind TEXT NOT NULL,
      observability TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS event_claims (
      claim_id TEXT PRIMARY KEY, event_type TEXT NOT NULL, event_subtype TEXT NOT NULL,
      event_date TEXT, description TEXT NOT NULL, actor_label TEXT, actor_role TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS bid_claims (
      claim_id TEXT PRIMARY KEY, bidder_label TEXT NOT NULL, bid_date TEXT,
      bid_value REAL, bid_value_lower REAL, bid_value_upper REAL, bid_value_unit TEXT,
      consideration_type TEXT, bid_stage TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS participation_count_claims (
      claim_id TEXT PRIMARY KEY, process_stage TEXT NOT NULL, actor_class TEXT NOT NULL,
      count_min INTEGER NOT NULL, count_max INTEGER, count_qualifier TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS actor_relation_claims (
      claim_id TEXT PRIMARY KEY, subject_label TEXT NOT NULL, object_label TEXT NOT NULL,
      relation_type TEXT NOT NULL, role_detail TEXT, effective_date_first TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS claim_evidence (
      claim_id TEXT NOT NULL, evidence_id TEXT NOT NULL, ordinal INTEGER NOT NULL,
      PRIMARY KEY (claim_id, evidence_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS claim_dispositions (
      disposition_id TEXT PRIMARY KEY, claim_id TEXT NOT NULL, run_id TEXT NOT NULL,
      disposition TEXT NOT NULL, reason_code TEXT NOT NULL, reason TEXT NOT NULL,
      current INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS deals (
      deal_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, deal_slug TEXT NOT NULL,
      target_actor_id TEXT, target_name TEXT, announcement_date TEXT, effective_date TEXT, all_cash INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS process_cycles (
      cycle_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, deal_id TEXT NOT NULL,
      cycle_sequence INTEGER NOT NULL, cycle_label TEXT NOT NULL, start_date TEXT, end_date TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS actors (
      actor_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, deal_id TEXT NOT NULL,
      actor_label TEXT NOT NULL, actor_kind TEXT NOT NULL, observability TEXT NOT NULL,
      bidder_class TEXT NOT NULL, lead_arranger_label TEXT, member_count_known INTEGER,
      has_strategic_member INTEGER, has_financial_member INTEGER,
      has_sovereign_wealth_member INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS actor_relations (
      relation_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, deal_id TEXT NOT NULL,
      subject_actor_id TEXT NOT NULL, object_actor_id TEXT NOT NULL, relation_type TEXT NOT NULL,
      subject_actor_label TEXT NOT NULL, object_actor_label TEXT NOT NULL,
      role_detail TEXT, cycle_id_first_observed TEXT, cycle_id_last_observed TEXT,
      effective_date_first TEXT, effective_date_last TEXT, confidence TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS events (
      event_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, deal_id TEXT NOT NULL,
      cycle_id TEXT, event_type TEXT NOT NULL, event_subtype TEXT NOT NULL, event_date TEXT,
      description TEXT NOT NULL, bid_value REAL, bid_value_lower REAL, bid_value_upper REAL,
      bid_value_unit TEXT, consideration_type TEXT, bid_stage TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS event_actor_links (
      link_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, event_id TEXT NOT NULL,
      actor_id TEXT NOT NULL, actor_label TEXT NOT NULL, role TEXT NOT NULL, role_detail TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS participation_counts (
      participation_count_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, deal_id TEXT NOT NULL,
      cycle_id TEXT, process_stage TEXT NOT NULL, actor_class TEXT NOT NULL,
      count_min INTEGER NOT NULL, count_max INTEGER, count_qualifier TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS row_evidence (
      row_table TEXT NOT NULL, row_id TEXT NOT NULL, evidence_id TEXT NOT NULL,
      ordinal INTEGER NOT NULL, PRIMARY KEY (row_table, row_id, evidence_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS judgments (
      judgment_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, deal_id TEXT NOT NULL,
      subject_table TEXT NOT NULL, subject_id TEXT NOT NULL, judgment_type TEXT NOT NULL,
      value TEXT NOT NULL, reason TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS review_flags (
      flag_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, deal_id TEXT,
      severity TEXT NOT NULL, code TEXT NOT NULL, reason TEXT NOT NULL,
      row_table TEXT, row_id TEXT, status TEXT, metadata TEXT, current INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS projection_units (
      projection_unit_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, projection_name TEXT NOT NULL,
      deal_id TEXT NOT NULL, cycle_id TEXT, actor_id TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS projection_judgments (
      projection_judgment_id TEXT PRIMARY KEY, run_id TEXT NOT NULL,
      projection_unit_id TEXT NOT NULL, rule_id TEXT NOT NULL, included INTEGER NOT NULL,
      reason TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS review_rows (
      review_row_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, deal_slug TEXT NOT NULL,
      payload_json TEXT NOT NULL
    )
    """,
)


def provider_json_schema() -> dict[str, Any]:
    """Return strict, provider-safe JSON schema for claim-only payloads."""
    schema = ProviderPayload.model_json_schema()
    schema["additionalProperties"] = False
    return schema
