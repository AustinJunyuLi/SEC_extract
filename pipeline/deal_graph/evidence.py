"""Source paragraphing and exact quote binding for deal_graph_v1."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .ids import evidence_fingerprint, make_id, quote_hash
from .schema import ParagraphRow, SpanRow


PARSER_VERSION = "deal_graph_pages_v1"


class QuoteBindingError(ValueError):
    """Base class for quote binding failures."""


class MissingQuoteError(QuoteBindingError):
    """Raised when quote text is not an exact source substring."""


class AmbiguousQuoteError(QuoteBindingError):
    """Raised when quote text appears more than once in the binding window."""


@dataclass(frozen=True)
class QuoteBinding:
    evidence: SpanRow
    paragraph: ParagraphRow


def raw_text_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def pages_to_paragraphs(
    *,
    pages: list[dict],
    filing_id: str,
    section: str = "background",
) -> list[ParagraphRow]:
    paragraphs: list[ParagraphRow] = []
    global_offset = 0
    sequence = 0

    for page in pages:
        page_number = page.get("number")
        content = str(page.get("content") or "")
        for match in re.finditer(r"\S(?:.*?\S)?(?=\n\s*\n|\Z)", content, flags=re.DOTALL):
            paragraph_text = match.group(0)
            char_start = global_offset + match.start()
            char_end = global_offset + match.end()
            paragraph_id = make_id(
                "para",
                filing_id,
                page_number,
                sequence,
                char_start,
                char_end,
                paragraph_text,
            )
            paragraphs.append(
                ParagraphRow(
                    paragraph_id=paragraph_id,
                    filing_id=filing_id,
                    section=section,
                    page_hint=page_number,
                    char_start=char_start,
                    char_end=char_end,
                    paragraph_text=paragraph_text,
                    paragraph_hash=raw_text_sha256(paragraph_text),
                )
            )
            sequence += 1
        global_offset += len(content) + 1

    return paragraphs


def bind_exact_quote(
    *,
    quote_text: str,
    filing_id: str,
    paragraphs: list[ParagraphRow],
    span_basis: str = "provider_quote",
    span_kind: str = "claim_quote",
    created_by_stage: str = "claim_insertion",
    parent_evidence_id: str | None = None,
) -> QuoteBinding:
    if not quote_text or not quote_text.strip():
        raise MissingQuoteError("quote_text is blank")

    matches: list[tuple[ParagraphRow, int]] = []
    for paragraph in paragraphs:
        start = paragraph.paragraph_text.find(quote_text)
        while start != -1:
            matches.append((paragraph, start))
            start = paragraph.paragraph_text.find(quote_text, start + 1)

    if not matches:
        raise MissingQuoteError("quote_text is not an exact paragraph substring")
    if len(matches) > 1:
        raise AmbiguousQuoteError("quote_text is ambiguous within provided paragraphs")

    paragraph, local_start = matches[0]
    char_start = paragraph.char_start + local_start
    char_end = char_start + len(quote_text)
    q_hash = quote_hash(quote_text)
    fingerprint = evidence_fingerprint(filing_id, char_start, char_end, q_hash)
    evidence_id = make_id("ev", filing_id, char_start, char_end, q_hash)
    span = SpanRow(
        evidence_id=evidence_id,
        filing_id=filing_id,
        paragraph_id=paragraph.paragraph_id,
        span_basis=span_basis,
        span_kind=span_kind,
        parent_evidence_id=parent_evidence_id,
        created_by_stage=created_by_stage,
        char_start=char_start,
        char_end=char_end,
        quote_text=quote_text,
        quote_text_hash=q_hash,
        evidence_fingerprint=fingerprint,
    )
    return QuoteBinding(evidence=span, paragraph=paragraph)


def audit_run_dir(repo_root: Path, slug: str, run_id: str) -> Path:
    return repo_root / "output" / "audit" / slug / "runs" / run_id
