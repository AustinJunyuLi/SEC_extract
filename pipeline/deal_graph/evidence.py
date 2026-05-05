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


class UnknownCitationUnitError(QuoteBindingError):
    """Raised when a provider cites a citation unit that Python did not supply."""


@dataclass(frozen=True)
class QuoteBinding:
    evidence: SpanRow
    paragraph: ParagraphRow


@dataclass(frozen=True)
class CitationUnitParagraph:
    unit_id: str
    page_number: int
    paragraph_index: int
    paragraph: ParagraphRow

    @property
    def text(self) -> str:
        return self.paragraph.paragraph_text


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


def is_citation_boilerplate(text: str) -> bool:
    compact = " ".join(text.split())
    if not compact:
        return True
    if compact == "Table of Contents":
        return True
    if re.fullmatch(r"\d+", compact):
        return True
    if compact.startswith("ZEQ.="):
        return True
    if compact.startswith("COMMAND="):
        return True
    return False


def citation_units_from_pages(section_pages: list[dict]) -> list[dict]:
    units: list[dict] = []
    for page in section_pages:
        page_number = page.get("number")
        if not isinstance(page_number, int):
            raise ValueError(f"filing page has non-integer number: {page_number!r}")
        content = str(page.get("content") or "")
        paragraph_index = 0
        for match in re.finditer(r"\S(?:.*?\S)?(?=\n\s*\n|\Z)", content, flags=re.DOTALL):
            text = match.group(0).strip()
            if is_citation_boilerplate(text):
                continue
            paragraph_index += 1
            units.append({
                "unit_id": f"page_{page_number}_paragraph_{paragraph_index}",
                "page_number": page_number,
                "paragraph_index": paragraph_index,
                "text": text,
            })
    if not units:
        raise ValueError("Background section produced no citation units")
    return units


def citation_unit_paragraphs(
    *,
    pages: list[dict],
    filing_id: str,
    section: str = "background",
) -> dict[str, CitationUnitParagraph]:
    units: dict[str, CitationUnitParagraph] = {}
    global_offset = 0
    sequence = 0

    for page in pages:
        page_number = page.get("number")
        if not isinstance(page_number, int):
            raise ValueError(f"filing page has non-integer number: {page_number!r}")
        content = str(page.get("content") or "")
        paragraph_index = 0
        for match in re.finditer(r"\S(?:.*?\S)?(?=\n\s*\n|\Z)", content, flags=re.DOTALL):
            paragraph_text = match.group(0).strip()
            if is_citation_boilerplate(paragraph_text):
                continue
            paragraph_index += 1
            char_start = global_offset + match.start() + len(match.group(0)) - len(match.group(0).lstrip())
            char_end = char_start + len(paragraph_text)
            unit_id = f"page_{page_number}_paragraph_{paragraph_index}"
            paragraph_id = make_id(
                "para",
                filing_id,
                unit_id,
                sequence,
                char_start,
                char_end,
                paragraph_text,
            )
            paragraph = ParagraphRow(
                paragraph_id=paragraph_id,
                filing_id=filing_id,
                section=section,
                page_hint=page_number,
                char_start=char_start,
                char_end=char_end,
                paragraph_text=paragraph_text,
                paragraph_hash=raw_text_sha256(paragraph_text),
            )
            units[unit_id] = CitationUnitParagraph(
                unit_id=unit_id,
                page_number=page_number,
                paragraph_index=paragraph_index,
                paragraph=paragraph,
            )
            sequence += 1
        global_offset += len(content) + 1

    if not units:
        raise ValueError("Background section produced no citation-unit paragraphs")
    return units


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


def bind_quote_to_citation_unit(
    *,
    quote_text: str,
    citation_unit_id: str,
    filing_id: str,
    citation_units: dict[str, CitationUnitParagraph],
    span_basis: str = "provider_evidence_ref",
    span_kind: str = "claim_quote",
    created_by_stage: str = "evidence_ref_binding",
    parent_evidence_id: str | None = None,
) -> QuoteBinding:
    if not quote_text or not quote_text.strip():
        raise MissingQuoteError("quote_text is blank")
    unit = citation_units.get(citation_unit_id)
    if unit is None:
        raise UnknownCitationUnitError(f"unknown citation_unit_id {citation_unit_id!r}")

    starts: list[int] = []
    start = unit.text.find(quote_text)
    while start != -1:
        starts.append(start)
        start = unit.text.find(quote_text, start + 1)
    if not starts:
        raise MissingQuoteError(
            f"quote_text is not an exact substring of citation_unit_id {citation_unit_id!r}"
        )
    # The citation unit is the binding address. If identical text repeats within
    # the same paragraph, either occurrence supports the same provider receipt.
    local_start = starts[0]
    paragraph = unit.paragraph
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


def quote_candidate_units(
    quote_text: str,
    citation_units: dict[str, CitationUnitParagraph],
    *,
    limit: int = 8,
) -> list[dict]:
    if not quote_text:
        return []
    candidates: list[dict] = []
    for unit in citation_units.values():
        count = unit.text.count(quote_text)
        if count <= 0:
            continue
        candidates.append({
            "citation_unit_id": unit.unit_id,
            "page_number": unit.page_number,
            "paragraph_index": unit.paragraph_index,
            "match_count": count,
        })
    return candidates[:limit]


def audit_run_dir(repo_root: Path, slug: str, run_id: str) -> Path:
    return repo_root / "output" / "audit" / slug / "runs" / run_id
