"""Native function-calling tools available to the extractor at draft time."""

from __future__ import annotations

import hashlib
import inspect
import json
import unicodedata
from typing import Any

from pipeline import core


CHECK_ROW_SCHEMA: dict[str, Any] = {
    "type": "function",
    "name": "check_row",
    "description": (
        "Validate a single proposed extraction event row against the row-local "
        "rulebook (P-R0/R2/R3/R4/R6/R7/R8/R9, P-D1/D2/D7, P-G2). "
        "Returns ok=true if the row passes all checks, otherwise ok=false "
        "with a violations list naming each broken rule. Registry-dependent "
        "P-R5 runs in the full validator. Call this before submitting any row."
    ),
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "row": {
                "type": "object",
                "additionalProperties": True,
                "description": "A single proposed event row matching SCHEMA_R1 event shape.",
            },
        },
        "required": ["row"],
    },
}

SEARCH_FILING_SCHEMA: dict[str, Any] = {
    "type": "function",
    "name": "search_filing",
    "description": (
        "Case-insensitive substring search over filing pages. Returns up to "
        "max_hits page+snippet pairs. Use plain words or phrases, not regex."
    ),
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "query": {
                "type": "string",
                "description": "Plain-text substring to search for.",
            },
            "page_range": {
                "type": ["array", "null"],
                "items": {"type": "integer"},
                "minItems": 2,
                "maxItems": 2,
                "description": "Inclusive [start_page, end_page] or null for whole filing.",
            },
            "max_hits": {"type": "integer", "minimum": 1, "maximum": 50},
        },
        "required": ["query", "page_range", "max_hits"],
    },
}

GET_PAGES_SCHEMA: dict[str, Any] = {
    "type": "function",
    "name": "get_pages",
    "description": (
        "Fetch the full text of a contiguous range of filing pages by page "
        "number. Use after search_filing or when you need surrounding context "
        "for a specific page. Maximum 10 pages per call."
    ),
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "start_page": {"type": "integer", "minimum": 1},
            "end_page": {"type": "integer", "minimum": 1},
        },
        "required": ["start_page", "end_page"],
    },
}

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    CHECK_ROW_SCHEMA,
    SEARCH_FILING_SCHEMA,
    GET_PAGES_SCHEMA,
]

GET_PAGES_MAX_RANGE = 10
SEARCH_SNIPPET_RADIUS = 200


def _nfkc(value: str) -> str:
    return unicodedata.normalize("NFKC", value)


def _filing_from_pages(filing_pages: list[dict[str, Any]]) -> core.Filing:
    return core.Filing(slug="tool_call", pages=filing_pages)


def _page_number(page: dict[str, Any]) -> int | None:
    number = page.get("number")
    if isinstance(number, int) and not isinstance(number, bool):
        return number
    return None


def _validate_page_range(page_range: list[int] | None) -> tuple[int, int] | None:
    if page_range is None:
        return None
    if (
        not isinstance(page_range, list)
        or len(page_range) != 2
        or not all(
            isinstance(value, int) and not isinstance(value, bool)
            for value in page_range
        )
    ):
        raise ValueError("page_range must be null or [start_page, end_page]")
    start_page, end_page = page_range
    if end_page < start_page:
        raise ValueError(f"page_range end_page {end_page} < start_page {start_page}")
    return start_page, end_page


def check_row(row: dict[str, Any], *, filing_pages: list[dict[str, Any]]) -> dict[str, Any]:
    """Run row-local validators on a single proposed row."""
    violations = core.validate_row_local(row, _filing_from_pages(filing_pages))
    return {"ok": len(violations) == 0, "violations": violations}


def search_filing(
    query: str,
    *,
    filing_pages: list[dict[str, Any]],
    page_range: list[int] | None = None,
    max_hits: int = 10,
) -> dict[str, Any]:
    """Case-insensitive plain substring search over filing pages."""
    if not isinstance(query, str) or not query:
        raise ValueError("query must be a non-empty string")
    if (
        not isinstance(max_hits, int)
        or isinstance(max_hits, bool)
        or not (1 <= max_hits <= 50)
    ):
        raise ValueError("max_hits must be an integer between 1 and 50")

    normalized_range = _validate_page_range(page_range)
    needle = _nfkc(query).casefold()
    hits: list[dict[str, Any]] = []
    for page in filing_pages:
        page_no = _page_number(page)
        if page_no is None:
            continue
        if normalized_range is not None:
            start_page, end_page = normalized_range
            if not (start_page <= page_no <= end_page):
                continue
        haystack = _nfkc(str(page.get("content", "")))
        idx = haystack.casefold().find(needle)
        if idx == -1:
            continue
        start = max(0, idx - SEARCH_SNIPPET_RADIUS)
        end = min(len(haystack), idx + len(query) + SEARCH_SNIPPET_RADIUS)
        hits.append({"page": page_no, "snippet": haystack[start:end]})
        if len(hits) >= max_hits:
            break
    return {"hits": hits}


def get_pages(
    *,
    start_page: int,
    end_page: int,
    filing_pages: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return full text for up to 10 filing pages in an inclusive range."""
    if not isinstance(start_page, int) or isinstance(start_page, bool):
        raise ValueError("start_page must be an integer")
    if not isinstance(end_page, int) or isinstance(end_page, bool):
        raise ValueError("end_page must be an integer")
    if end_page < start_page:
        raise ValueError(f"end_page {end_page} < start_page {start_page}")
    if end_page - start_page + 1 > GET_PAGES_MAX_RANGE:
        raise ValueError(
            f"page range too wide: {end_page - start_page + 1} > {GET_PAGES_MAX_RANGE}"
        )

    pages_by_number = {
        number: page
        for page in filing_pages
        if (number := _page_number(page)) is not None
    }
    pages = [
        {"page": number, "text": str(pages_by_number[number].get("content", ""))}
        for number in range(start_page, end_page + 1)
        if number in pages_by_number
    ]
    return {"pages": pages}


def tools_contract_version() -> str:
    """Return a stable hash for tool definitions and implementations."""
    payload = {
        "definitions": TOOL_DEFINITIONS,
        "impl_src": (
            inspect.getsource(check_row)
            + inspect.getsource(search_filing)
            + inspect.getsource(get_pages)
            + inspect.getsource(dispatch)
        ),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()[:16]


def dispatch(
    name: str,
    arguments: dict[str, Any],
    *,
    filing_pages: list[dict[str, Any]],
) -> dict[str, Any]:
    """Dispatch a Responses API function call to the local implementation."""
    if name == "check_row":
        row = arguments.get("row")
        if row is None:
            row = arguments
        return check_row(row, filing_pages=filing_pages)
    if name == "search_filing":
        return search_filing(
            arguments["query"],
            filing_pages=filing_pages,
            page_range=arguments.get("page_range"),
            max_hits=arguments.get("max_hits", 10),
        )
    if name == "get_pages":
        return get_pages(
            start_page=arguments["start_page"],
            end_page=arguments["end_page"],
            filing_pages=filing_pages,
        )
    raise ValueError(f"unknown tool: {name!r}")
