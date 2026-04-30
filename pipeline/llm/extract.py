"""Extractor SDK message construction and call path."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from pipeline import core

from .audit import AuditWriter, TokenUsage
from .client import CompletionResult, LLMClient
from .contracts import MAX_REPAIR_TURNS
from .response_format import (
    SCHEMA_R1,
    _ensure_extraction_shape,
    json_schema_format,
    parse_json_text,
    schema_hash,
)
from .tools import TOOL_DEFINITIONS, dispatch


EXTRACTOR_RULE_FILES = ("schema.md", "events.md", "bidders.md", "bids.md", "dates.md")
MAX_BACKGROUND_SECTION_PAGES = 35
MIN_BACKGROUND_SECTION_CHARS = 1500
MAX_TOOL_TURNS = 8


def extractor_contract_version() -> str:
    """Hash the static extractor prompt plus local response schema mirror.

    `rulebook_version()` covers `rules/*.md`. This hash covers the two other
    inputs that make a cached raw response stale even when the rules do not
    change: `prompts/extract.md` and the Python schema mirror used for local
    Linkflow validation.
    """
    h = hashlib.sha256()
    h.update((core.REPO_ROOT / "prompts" / "extract.md").read_bytes())
    h.update(b"\n---SCHEMA_R1---\n")
    h.update(schema_hash(SCHEMA_R1).encode("ascii"))
    return h.hexdigest()

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
    tool_calls_count: int = 0


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


def _load_tool_pages(slug: str) -> list[dict[str, Any]]:
    return json.loads((core.DATA_DIR / slug / "pages.json").read_text())


def _json_dumps_tool_output(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


async def _call_with_tools(
    *,
    llm_client: LLMClient,
    model: str,
    system: str,
    user: str,
    filing_pages: list[dict[str, Any]],
    max_output_tokens: int | None,
    reasoning_effort: str | None,
) -> tuple[dict[str, Any], CompletionResult, list[CompletionResult], int]:
    input_items: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    completions: list[CompletionResult] = []
    tool_calls_count = 0

    for _turn in range(1, MAX_TOOL_TURNS + 1):
        completion = await llm_client.complete(
            model=model,
            input_items=input_items,
            text_format=json_schema_format(SCHEMA_R1),
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
            max_output_tokens=max_output_tokens,
            reasoning_effort=reasoning_effort,
            stream=True,
        )
        completions.append(completion)

        if completion.tool_calls:
            input_items.extend(completion.output_items or completion.tool_calls)
            for tool_call in completion.tool_calls:
                try:
                    arguments = json.loads(tool_call.get("arguments") or "{}")
                    result = dispatch(
                        name=str(tool_call.get("name")),
                        arguments=arguments,
                        filing_pages=filing_pages,
                    )
                    output = _json_dumps_tool_output(result)
                except Exception as exc:  # noqa: BLE001 - return tool errors to model
                    output = _json_dumps_tool_output({"error": str(exc)})
                tool_calls_count += 1
                input_items.append({
                    "type": "function_call_output",
                    "call_id": tool_call["call_id"],
                    "output": output,
                })
            continue

        parsed = parse_json_text(completion.text)
        _ensure_extraction_shape(parsed)
        completion.parsed_json = parsed
        return parsed, completion, completions, tool_calls_count

    input_items.append({
        "role": "user",
        "content": (
            f"Tool-call turn limit ({MAX_TOOL_TURNS}) reached. Emit the final "
            "{deal, events} JSON now. Do not call tools. Any remaining issues "
            "will be handled by Python validation and repair."
        ),
    })
    completion = await llm_client.complete(
        model=model,
        input_items=input_items,
        text_format=json_schema_format(SCHEMA_R1),
        max_output_tokens=max_output_tokens,
        reasoning_effort=reasoning_effort,
        stream=True,
    )
    completions.append(completion)
    parsed = parse_json_text(completion.text)
    _ensure_extraction_shape(parsed)
    completion.parsed_json = parsed
    return parsed, completion, completions, tool_calls_count


def _hard_flags(validation: core.ValidatorResult) -> list[dict[str, Any]]:
    return [
        flag for flag in [*validation.row_flags, *validation.deal_flags]
        if flag.get("severity") == "hard"
    ]


def _affected_rows(draft: dict[str, Any], row_flags: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events = draft.get("events") or []
    rows: list[dict[str, Any]] = []
    seen: set[int] = set()
    for flag in row_flags:
        if flag.get("severity") != "hard":
            continue
        index = flag.get("row_index")
        if not isinstance(index, int) or index in seen:
            continue
        if 0 <= index < len(events) and isinstance(events[index], dict):
            rows.append({"row_index": index, "row": events[index]})
            seen.add(index)
    return rows


def _filing_snippets(rows: list[dict[str, Any]], filing: core.Filing) -> list[dict[str, Any]]:
    snippets: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    for item in rows:
        row_index = item.get("row_index")
        row = item.get("row") or {}
        pages = row.get("source_page")
        page_numbers = pages if isinstance(pages, list) else [pages]
        for page_number in page_numbers:
            if not isinstance(page_number, int):
                continue
            key = (int(row_index), page_number)
            if key in seen:
                continue
            seen.add(key)
            text = filing.page_content(page_number) or ""
            snippets.append({
                "row_index": row_index,
                "page": page_number,
                "text": text[:2500],
            })
    return snippets


def _repair_prompt_template() -> str:
    return (core.PROMPTS_DIR / "repair.md").read_text()


async def run_repair_loop(
    *,
    slug: str,
    initial_draft: dict[str, Any],
    filing: core.Filing,
    validation: core.ValidatorResult,
    llm_client: LLMClient,
    extract_model: str,
    audit: AuditWriter,
    token_usage: TokenUsage,
    reasoning_effort: str | None = None,
    max_output_tokens: int | None = None,
) -> tuple[dict[str, Any], core.ValidatorResult, list[dict[str, Any]], str, int]:
    """Run up to MAX_REPAIR_TURNS complete-revision repair turns."""
    if not _hard_flags(validation):
        return initial_draft, validation, [], "clean", 0

    system, _original_user = build_messages(slug)
    filing_pages = _load_tool_pages(slug)
    draft = initial_draft
    current_validation = validation
    promotion_log: list[dict[str, Any]] = []
    template = _repair_prompt_template()

    for turn in range(1, MAX_REPAIR_TURNS + 1):
        report = core.compact_validator_report(
            current_validation.row_flags,
            current_validation.deal_flags,
        )
        affected = _affected_rows(draft, current_validation.row_flags)
        repair_user = template.format(
            validator_report=json.dumps(report, indent=2, default=str),
            affected_rows=json.dumps(affected, indent=2, default=str),
            filing_snippets=json.dumps(_filing_snippets(affected, filing), indent=2),
        )
        audit.write_prompt(
            phase=f"repair_{turn}",
            system=system,
            user=repair_user,
        )
        revised, _completion, completions, _tool_calls_count = await _call_with_tools(
            llm_client=llm_client,
            model=extract_model,
            system=system,
            user=repair_user,
            filing_pages=filing_pages,
            max_output_tokens=max_output_tokens,
            reasoning_effort=reasoning_effort,
        )
        for completion in completions:
            token_usage.consume(completion)
        prepared, filing, promotion_log = core.prepare_for_validate(slug, revised, filing)
        current_validation = core.validate(prepared, filing)
        draft = prepared
        hard_after = len(_hard_flags(current_validation))
        if hasattr(audit, "write_repair_turn"):
            audit.write_repair_turn({
                "turn": turn,
                "validator_report_summary": report,
                "hard_flags_before": report["hard_count"],
                "hard_flags_after": hard_after,
            })
        if hard_after == 0:
            return draft, current_validation, promotion_log, "fixed", turn

    return draft, current_validation, promotion_log, "exhausted", MAX_REPAIR_TURNS


async def extract_deal(
    slug: str,
    *,
    llm_client: LLMClient,
    extract_model: str,
    audit: AuditWriter,
    token_usage: TokenUsage,
    rulebook_version: str,
    max_output_tokens: int | None = None,
    reasoning_effort: str | None = None,
) -> ExtractResult:
    system, user = build_messages(slug)
    filing_pages = _load_tool_pages(slug)
    prompt_digest = audit.write_prompt(phase="extractor", system=system, user=user)
    try:
        parsed, completion, completions, tool_calls_count = await _call_with_tools(
            llm_client=llm_client,
            filing_pages=filing_pages,
            system=system,
            user=user,
            model=extract_model,
            max_output_tokens=max_output_tokens,
            reasoning_effort=reasoning_effort,
        )
    except Exception as exc:
        audit.append_call({
            "ts": core._now_iso(),
            "phase": "extract",
            "flag_index": None,
            "model": extract_model,
            "reasoning_effort": reasoning_effort,
            "prompt_hash": prompt_digest,
            "attempts": int(getattr(exc, "attempts", 1) or 1),
            "outcome": "failed",
            "error": {"type": type(exc).__name__, "message": str(exc)[:500]},
        })
        raise
    for turn_completion in completions:
        token_usage.consume(turn_completion)
    audit.write_raw_response(
        result=completion,
        parsed_json=parsed,
        rulebook_version=rulebook_version,
        extractor_contract_version=extractor_contract_version(),
    )
    audit.append_call({
        "ts": core._now_iso(),
        "phase": "extract",
        "flag_index": None,
        "model": completion.model,
        "reasoning_effort": reasoning_effort,
        "prompt_hash": prompt_digest,
        "input_tokens": completion.input_tokens,
        "output_tokens": completion.output_tokens,
        "reasoning_tokens": completion.reasoning_tokens,
        "latency_seconds": completion.latency_seconds,
        "attempts": completion.attempts,
        "turns": len(completions),
        "tool_calls_count": tool_calls_count,
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
        tool_calls_count=tool_calls_count,
    )
