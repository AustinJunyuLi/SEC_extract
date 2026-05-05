from __future__ import annotations

import pytest

from pipeline.deal_graph.claims import assert_relation_quote_support
from pipeline.deal_graph.evidence import (
    AmbiguousQuoteError,
    MissingQuoteError,
    bind_exact_quote,
    pages_to_paragraphs,
)
from pipeline.deal_graph.schema import ActorRelationClaim


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
        quote_text="CSC and Pamplona, who together we refer to as CSC/Pamplona",
    )

    assert_relation_quote_support(claim)

    unsupported = claim.model_copy(update={
        "quote_text": "CSC/Pamplona submitted an indication of interest."
    })
    with pytest.raises(ValueError, match="lacks support"):
        assert_relation_quote_support(unsupported)
