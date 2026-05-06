from __future__ import annotations

import pytest

from pipeline.deal_graph.claims import assert_relation_quote_support
from pipeline.deal_graph.canonicalize import canonicalize_claim_payload
from pipeline.deal_graph.evidence import (
    AmbiguousQuoteError,
    MissingQuoteError,
    bind_exact_quote,
    bind_quote_to_citation_unit,
    citation_unit_paragraphs,
    pages_to_paragraphs,
)
from pipeline.deal_graph.orchestrate import _bind_provider_evidence
from pipeline.deal_graph.project_review import project_review_rows
from pipeline.deal_graph.schema import ActorRelationClaim
from pipeline.deal_graph.validate import validate_graph_as_dicts


def _paragraphs():
    return pages_to_paragraphs(
        filing_id="filing_mac_gray",
        pages=[
            {
                "number": 42,
                "content": (
                    "CSC and Pamplona, who together we refer to as CSC/Pamplona, "
                    "entered into a confidentiality agreement.\n\n"
                    "CSC/Pamplona submitted an indication of interest at $18.50 per share."
                ),
            }
        ],
    )


def test_bind_exact_quote_returns_source_coordinates_and_fingerprint():
    quote = "CSC/Pamplona submitted an indication of interest at $18.50 per share"

    binding = bind_exact_quote(
        quote_text=quote,
        filing_id="filing_mac_gray",
        paragraphs=_paragraphs(),
    )

    assert binding.evidence.quote_text == quote
    assert binding.evidence.char_end - binding.evidence.char_start == len(quote)
    assert binding.evidence.paragraph_id == binding.paragraph.paragraph_id
    assert binding.evidence.evidence_fingerprint


def test_bind_exact_quote_rejects_missing_quote():
    with pytest.raises(MissingQuoteError, match="exact paragraph substring"):
        bind_exact_quote(
            quote_text="CSC/Pamplona made a non-existent proposal",
            filing_id="filing_mac_gray",
            paragraphs=_paragraphs(),
        )


def test_bind_exact_quote_rejects_ambiguous_quote():
    paragraphs = pages_to_paragraphs(
        filing_id="filing_repeat",
        pages=[{"number": 1, "content": "Party A signed an NDA.\n\nParty A signed an NDA."}],
    )

    with pytest.raises(AmbiguousQuoteError, match="ambiguous"):
        bind_exact_quote(
            quote_text="Party A signed an NDA.",
            filing_id="filing_repeat",
            paragraphs=paragraphs,
        )


def test_actor_relation_quote_requires_subject_object_and_relation_support():
    claim = ActorRelationClaim(
        claim_type="actor_relation",
        coverage_obligation_id="obl_relation_1",
        subject_label="Pamplona",
        object_label="CSC/Pamplona",
        relation_type="member_of",
        role_detail=None,
        effective_date_first=None,
        confidence="high",
        evidence_refs=[
            {
                "citation_unit_id": "page_42_paragraph_1",
                "quote_text": "CSC and Pamplona, who together we refer to as CSC/Pamplona",
            }
        ],
    )

    assert_relation_quote_support(claim)

    unsupported = claim.model_copy(update={
        "evidence_refs": [
            {
                "citation_unit_id": "page_42_paragraph_2",
                "quote_text": "CSC/Pamplona submitted an indication of interest.",
            }
        ]
    })
    with pytest.raises(ValueError, match="lacks support"):
        assert_relation_quote_support(unsupported)


def test_bind_quote_to_citation_unit_resolves_repeated_true_quote_by_address():
    pages = [
        {"number": 1, "content": "Party A signed an NDA.\n\nParty A signed an NDA."}
    ]
    units = citation_unit_paragraphs(pages=pages, filing_id="filing_repeat")

    binding = bind_quote_to_citation_unit(
        quote_text="Party A signed an NDA.",
        citation_unit_id="page_1_paragraph_2",
        filing_id="filing_repeat",
        citation_units=units,
    )

    assert binding.paragraph.page_hint == 1
    assert binding.paragraph.paragraph_text == "Party A signed an NDA."


def test_bind_quote_to_citation_unit_allows_duplicate_text_inside_same_unit():
    pages = [
        {"number": 1, "content": "Party A signed an NDA and Party A signed an NDA."}
    ]
    units = citation_unit_paragraphs(pages=pages, filing_id="filing_repeat")

    binding = bind_quote_to_citation_unit(
        quote_text="Party A signed an NDA",
        citation_unit_id="page_1_paragraph_1",
        filing_id="filing_repeat",
        citation_units=units,
    )

    assert binding.paragraph.paragraph_text == "Party A signed an NDA and Party A signed an NDA."
    assert binding.evidence.char_start == binding.paragraph.char_start


def test_evidence_ref_binding_failure_creates_one_sharp_blocking_flag():
    payload = {
        "event_claims": [
            {
                "claim_type": "event",
                "coverage_obligation_id": "obl_nda",
                "event_type": "process",
                "event_subtype": "nda_signed",
                "event_date": "2014-01-03",
                "description": "Party A signed a confidentiality agreement.",
                "actor_label": "Party A",
                "actor_role": "potential_buyer",
                "confidence": "high",
                "evidence_refs": [
                    {
                        "citation_unit_id": "page_1_paragraph_1",
                        "quote_text": "Party A signed a confidentiality agreement.",
                    }
                ],
            }
        ]
    }
    evidence_context = _bind_provider_evidence(
        payload,
        run_id="run-1",
        slug="sample",
        pages=[{"number": 1, "content": "Party A entered into a confidentiality agreement."}],
    )
    graph = canonicalize_claim_payload(
        payload,
        deal_slug="sample",
        run_id="run-1",
        evidence_context=evidence_context,
    )

    claim_id = graph["claims"][0]["claim_id"]
    disposition = graph["claim_dispositions"][0]
    flags = validate_graph_as_dicts(graph)

    assert graph["claim_evidence"] == []
    assert graph["row_evidence"] == []
    assert disposition["claim_id"] == claim_id
    assert disposition["disposition"] == "rejected_unsupported"
    assert disposition["reason_code"] == "evidence_ref_binding_failed"
    assert graph["review_flags"][0]["code"] == "evidence_ref_binding_failed"
    assert graph["review_flags"][0]["metadata"]["provided_citation_unit_id"] == "page_1_paragraph_1"
    assert {
        (flag["code"], flag["row_table"], flag["row_id"])
        for flag in flags
    } == {("evidence_ref_binding_failed", "claims", claim_id)}

    review_rows = project_review_rows(graph)
    assert len(review_rows) == 1
    assert review_rows[0]["review_status"] == "rejected_claim"
    assert review_rows[0]["claim_id"] == claim_id
    assert review_rows[0]["claim_type"] == "event_claim"
    assert review_rows[0]["citation_unit_id"] == "page_1_paragraph_1"
    assert review_rows[0]["supplied_quote"] == "Party A signed a confidentiality agreement."
    assert review_rows[0]["bound_source_quote"] == ""
    assert review_rows[0]["issue_codes"] == "evidence_ref_binding_failed"


def test_multi_ref_binding_is_all_or_nothing_for_one_claim():
    payload = {
        "actor_relation_claims": [
            {
                "claim_type": "actor_relation",
                "coverage_obligation_id": "obl_relation",
                "subject_label": "Longview",
                "object_label": "Buyer Group",
                "relation_type": "supports",
                "role_detail": "rollover support",
                "effective_date_first": "2014-12-12",
                "confidence": "high",
                "evidence_refs": [
                    {
                        "citation_unit_id": "page_1_paragraph_1",
                        "quote_text": "Longview met with the Buyer Group.",
                    },
                    {
                        "citation_unit_id": "page_1_paragraph_2",
                        "quote_text": "Longview signed a cleaned-up receipt.",
                    },
                ],
            }
        ]
    }
    evidence_context = _bind_provider_evidence(
        payload,
        slug="sample",
        run_id="run-1",
        pages=[
            {
                "number": 1,
                "content": "Longview met with the Buyer Group.\n\nLongview signed a voting agreement.",
            }
        ],
    )
    graph = canonicalize_claim_payload(
        payload,
        deal_slug="sample",
        run_id="run-1",
        evidence_context=evidence_context,
    )

    claim_id = graph["claims"][0]["claim_id"]

    assert graph["evidence"] == []
    assert graph["claim_evidence"] == []
    assert graph["claim_dispositions"][0]["disposition"] == "rejected_unsupported"
    assert graph["review_flags"][0]["row_id"] == claim_id
