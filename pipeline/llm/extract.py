"""Extractor SDK message construction and call path."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from pipeline import core

from .audit import AuditWriter, TokenBudget
from .client import CompletionResult, LLMClient
from .response_format import SCHEMA_R1, call_json


EXTRACTOR_RULE_FILES = ("schema.md", "events.md", "bidders.md", "bids.md", "dates.md")
MAX_BACKGROUND_SECTION_PAGES = 35
MIN_BACKGROUND_SECTION_CHARS = 1500

BACKGROUND_START_RE = re.compile(
    r"\bBackground\s+of\s+the\s+(?:Merger|Offer|Transaction)\b",
    re.IGNORECASE,
)
BACKGROUND_CROSS_REF_RE = re.compile(
    r"\b(?:see|under|entitled|beginning on page|described above|described below)\b",
    re.IGNORECASE,
)
BACKGROUND_NARRATIVE_CUE_RE = re.compile(
    r"following\s+chronology|chronology\s+summarizes|regularly\s+reviewed|"
    r"frequently\s+reviews|ongoing\s+evaluation|strategic\s+options|"
    r"last\s+few\s+years|material\s+key\s+events",
    re.IGNORECASE | re.DOTALL,
)
BACKGROUND_END_HEADING_RE = re.compile(
    r"""
    (?:^|[\r\n]|\s{2,})
    (?:
        \*{1,3}\s*
        (?:COMMAND=STYLE_ADDED,[^\r\n]*?\s+)?
        (?:
            Reasons\s+for\s+the\s+(?:Merger|Offer)
          | Recommendation\s+(?:of|and)
          | Reasons\s+and\s+Recommendation
          | Opinion\s+of
          | Purpose\s+of\s+the\s+Offer
          | The\s+Merger\s+Agreement
          | Certain\s+Effects\s+of
          | Interests\s+of
          | Financing
          | Projected\s+Financial\s+Information
          | [A-Za-z]+(?:'|’)?s\s+Reasons\s+for\s+the\s+Merger
        )
      |
        \d{1,2}\.\s*
        (?:
            The\s+Merger\s+Agreement
          | Purpose\s+of\s+the\s+Offer
          | Certain\s+Effects\s+of
          | Reasons\s+for\s+the\s+(?:Merger|Offer)
        )
      |
        (?:
            Reasons\s+for\s+the\s+(?:Merger|Offer)
          | Recommendation\s+(?:of|and)
          | Reasons\s+and\s+Recommendation
          | Opinion\s+of
          | Purpose\s+of\s+the\s+Offer
          | Certain\s+Effects\s+of
          | Interests\s+of
          | Financing
          | Projected\s+Financial\s+Information
          | [A-Za-z]+(?:'|’)?s\s+Reasons\s+for\s+the\s+Merger
        )
    )
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)


@dataclass
class ExtractResult:
    raw_extraction: dict[str, Any]
    completion: CompletionResult
    rulebook_version: str


@dataclass(frozen=True)
class BackgroundBounds:
    start_page: int
    start_index: int
    end_page: int
    end_index: int


def _page_number(page: dict[str, Any]) -> int:
    number = page.get("number")
    if not isinstance(number, int):
        raise ValueError(f"filing page has non-integer number: {number!r}")
    return number


def _score_background_start(page: dict[str, Any], match: re.Match[str]) -> int:
    number = _page_number(page)
    content = str(page.get("content", ""))
    before = content[max(0, match.start() - 120):match.start()]
    after = content[match.end():match.end() + 700]
    around = content[max(0, match.start() - 180):match.end() + 220]

    score = 0
    if number >= 15:
        score += 6
    if "**" in before[-24:] or "**" in after[:24]:
        score += 3
    if BACKGROUND_NARRATIVE_CUE_RE.search(after):
        score += 3
    if BACKGROUND_CROSS_REF_RE.search(before[-100:]):
        score -= 8
    if around.count("|") >= 4:
        score -= 8
    return score


def _find_background_start(pages: list[dict[str, Any]]) -> tuple[int, int]:
    candidates: list[tuple[int, int, int]] = []
    for index, page in enumerate(pages):
        content = str(page.get("content", ""))
        for match in BACKGROUND_START_RE.finditer(content):
            candidates.append((_score_background_start(page, match), index, match.start()))
    if not candidates:
        raise ValueError("Background section heading not found in filing pages")

    candidates.sort(key=lambda candidate: (-candidate[0], _page_number(pages[candidate[1]]), candidate[2]))
    score, page_index, start_index = candidates[0]
    if score < 5:
        raise ValueError("Background section heading candidates were only table-of-contents/cross-reference hits")
    return page_index, start_index


def _is_background_end_heading(content: str, match: re.Match[str], *, search_start: int) -> bool:
    before = content[max(search_start, match.start() - 140):match.start()]
    around = content[max(search_start, match.start() - 200):match.end() + 200]
    if BACKGROUND_CROSS_REF_RE.search(before[-120:]):
        return False
    if around.count("|") >= 4:
        return False
    return True


def _find_background_end(
    pages: list[dict[str, Any]],
    *,
    start_page_index: int,
    start_index: int,
) -> tuple[int, int]:
    for page_index in range(start_page_index, min(len(pages), start_page_index + MAX_BACKGROUND_SECTION_PAGES)):
        content = str(pages[page_index].get("content", ""))
        search_start = start_index + 1 if page_index == start_page_index else 0
        for match in BACKGROUND_END_HEADING_RE.finditer(content, search_start):
            if _is_background_end_heading(content, match, search_start=search_start):
                return page_index, match.start()
    raise ValueError(
        "Background section end heading not found within "
        f"{MAX_BACKGROUND_SECTION_PAGES} pages of start page {_page_number(pages[start_page_index])}"
    )


def _background_section_payload(pages: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], BackgroundBounds]:
    start_page_index, start_index = _find_background_start(pages)
    end_page_index, end_index = _find_background_end(
        pages,
        start_page_index=start_page_index,
        start_index=start_index,
    )
    if end_page_index < start_page_index:
        raise ValueError("Background section end precedes start")

    section_pages = [deepcopy(page) for page in pages[start_page_index:end_page_index + 1]]
    for offset, section_page in enumerate(section_pages):
        source_page_index = start_page_index + offset
        content = str(pages[source_page_index].get("content", ""))
        if source_page_index == start_page_index == end_page_index:
            content = content[start_index:end_index]
        elif source_page_index == start_page_index:
            content = content[start_index:]
        elif source_page_index == end_page_index:
            content = content[:end_index]
        section_page["content"] = content

    total_chars = sum(len(str(page.get("content", ""))) for page in section_pages)
    if total_chars < MIN_BACKGROUND_SECTION_CHARS:
        raise ValueError(
            "Background section extraction produced too little filing text: "
            f"{total_chars} chars from pages {_page_number(pages[start_page_index])}..{_page_number(pages[end_page_index])}"
        )

    bounds = BackgroundBounds(
        start_page=_page_number(pages[start_page_index]),
        start_index=start_index,
        end_page=_page_number(pages[end_page_index]),
        end_index=end_index,
    )
    return section_pages, bounds


def build_messages(slug: str) -> tuple[str, str]:
    prompt = (core.PROMPTS_DIR / "extract.md").read_text()
    rule_chunks = []
    for name in EXTRACTOR_RULE_FILES:
        path = core.RULES_DIR / name
        rule_chunks.append(f"\n\n# rules/{path.name}\n\n{path.read_text()}")
    manifest = json.loads((core.DATA_DIR / slug / "manifest.json").read_text())
    pages = json.loads((core.DATA_DIR / slug / "pages.json").read_text())
    section_pages, section_bounds = _background_section_payload(pages)
    system = prompt + "\n\n" + "\n".join(rule_chunks)
    user = json.dumps(
        {
            "slug": slug,
            "manifest": manifest,
            "section": {
                "name": "Background",
                "start_page": section_bounds.start_page,
                "end_page": section_bounds.end_page,
                "source": "verbatim slices from the source filing pages",
            },
            "pages": section_pages,
        },
        indent=2,
        sort_keys=True,
    )
    return system, user


async def extract_deal(
    slug: str,
    *,
    llm_client: LLMClient,
    extract_model: str,
    audit: AuditWriter,
    token_budget: TokenBudget,
    rulebook_version: str,
    schema_supported: bool,
    max_output_tokens: int | None = None,
    reasoning_effort: str | None = None,
) -> ExtractResult:
    system, user = build_messages(slug)
    prompt_digest = audit.write_prompt(phase="extractor", system=system, user=user)
    completion = await call_json(
        llm_client,
        system=system,
        user=user,
        model=extract_model,
        schema_supported=schema_supported,
        schema=SCHEMA_R1,
        max_output_tokens=max_output_tokens,
        reasoning_effort=reasoning_effort,
    )
    token_budget.consume(completion)
    parsed = completion.parsed_json or {}
    audit.write_raw_response(
        result=completion,
        parsed_json=parsed,
        rulebook_version=rulebook_version,
    )
    audit.append_call({
        "ts": core._now_iso(),
        "phase": "extract",
        "flag_index": None,
        "model": completion.model,
        "reasoning_effort": reasoning_effort,
        "prompt_hash": prompt_digest,
        "json_schema_used": schema_supported,
        "input_tokens": completion.input_tokens,
        "output_tokens": completion.output_tokens,
        "reasoning_tokens": completion.reasoning_tokens,
        "latency_seconds": completion.latency_seconds,
        "attempts": completion.attempts,
        "finish_reason": completion.finish_reason,
        "watchdog": {
            "warnings": completion.watchdog.warnings,
            "max_idle_seconds": completion.watchdog.max_idle_seconds,
        },
        "outcome": "ok",
        "error": None,
    })
    return ExtractResult(
        raw_extraction=parsed,
        completion=completion,
        rulebook_version=rulebook_version,
    )
