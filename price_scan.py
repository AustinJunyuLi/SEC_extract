"""Regex-based price scanner (§P-R6 dependency).

Ported from bids_pipeline/pipeline/preprocess.py as part of US-002 of the
2026-04-21 validator-hardening PRD. Extracts dollar-per-share price
mentions from filing text using an anchor-scan plus context-window
strategy:

  1. Find every "per [common] share" anchor in the text.
  2. For each anchor, examine a ~250-char window around it.
  3. Match one of the 9 ordered patterns (range, per-share, cash trailer).
  4. Reject matches whose left context is a threshold phrase
     ("at least $X", "minimum of $X", "no less than $X per share",
     "floor of $X") or whose right context is a mixed-consideration tail
     ("$X plus $Y in stock"). Both exclusions are imported from the
     2026-04-17 boundary-map sprint (Cluster 3).

Returns a list of dicts with keys {value, lower, upper, raw_match,
position, context}. A point price has value == lower == upper. A range
has value == None and lower != upper.
"""

import re

# Case-insensitive so defined terms like "Per Share", "PER SHARE",
# "Per Common Share", and hyphenated "per-Share" all match.
_PER_SHARE_FRAGMENT = r"per(?:[-\s]+common)?[-\s]+share"
_PRICE_ANCHOR = re.compile(rf"\b{_PER_SHARE_FRAGMENT}\b", re.IGNORECASE)
_CASH_PRICE_TRAILER = r"(?:\s+in\s+cash|\s+cash)?"

_LOCAL_PRICE_THRESHOLD_CONTEXT = re.compile(
    r"\b(?:at\s+least|minimum(?:\s+of)?|no\s+less\s+than|floor\s+of)\b",
    re.IGNORECASE,
)
_LOCAL_PRICE_COMPONENT_TAIL = re.compile(
    r"\b(?:plus|and)\s+\$\d+(?:\.\d+)?\s+(?:in\s+)?stock\b",
    re.IGNORECASE,
)

# Ordered: specific patterns first so they claim the match before the
# general "$X per share" pattern can shadow them.
_LOCAL_PRICE_PATTERNS = [
    re.compile(
        rf"\$(\d+(?:\.\d+)?)\s+to\s+\$(\d+(?:\.\d+)?)\s+{_PER_SHARE_FRAGMENT}",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\$(\d+(?:\.\d+)?)\s*[-–]\s*\$(\d+(?:\.\d+)?)\s+{_PER_SHARE_FRAGMENT}",
        re.IGNORECASE,
    ),
    re.compile(
        rf"between\s+\$(\d+(?:\.\d+)?)\s+and\s+\$(\d+(?:\.\d+)?)\s+{_PER_SHARE_FRAGMENT}",
        re.IGNORECASE,
    ),
    re.compile(
        rf"price\s+{_PER_SHARE_FRAGMENT}\s+(?:in\s+the\s+range\s+of|of)\s+"
        rf"\$(\d+(?:\.\d+)?)\s+to\s+\$(\d+(?:\.\d+)?){_CASH_PRICE_TRAILER}",
        re.IGNORECASE,
    ),
    re.compile(
        rf"(?:all[-\s]+cash\s+)?{_PER_SHARE_FRAGMENT}\s+"
        rf"(?:price|value|consideration|amount|offer\s+price)\s+"
        rf"(?:of\s+)?\$(\d+(?:\.\d+)?){_CASH_PRICE_TRAILER}",
        re.IGNORECASE,
    ),
    re.compile(
        rf"price\s+{_PER_SHARE_FRAGMENT}\s+(?:of|to)\s+"
        rf"\$(\d+(?:\.\d+)?){_CASH_PRICE_TRAILER}",
        re.IGNORECASE,
    ),
    re.compile(
        rf"price\s+of\s+\$(\d+(?:\.\d+)?){_CASH_PRICE_TRAILER}\s+{_PER_SHARE_FRAGMENT}",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\$(\d+(?:\.\d+)?)\s+in\s+cash\s+{_PER_SHARE_FRAGMENT}",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\$(\d+(?:\.\d+)?)\s+{_PER_SHARE_FRAGMENT}",
        re.IGNORECASE,
    ),
]

_CONTEXT_BEFORE = 200
_CONTEXT_AFTER = 50


def _reject_local_price_match(window: str, match: re.Match) -> bool:
    left_context = window[max(0, match.start() - 40):match.start()]
    right_context = window[match.end():match.end() + 80]
    threshold_context = f"{left_context}{match.group()}"
    if _LOCAL_PRICE_THRESHOLD_CONTEXT.search(threshold_context):
        return True
    if _LOCAL_PRICE_COMPONENT_TAIL.search(right_context):
        return True
    return False


def extract_prices_regex(text: str) -> list[dict]:
    """Return every dollar-per-share mention in `text` with value/lower/upper."""
    prices: list[dict] = []
    seen_raw: set[str] = set()
    consumed_spans: list[tuple[int, int]] = []

    def _overlaps_consumed(abs_start: int, abs_end: int) -> bool:
        for cs, ce in consumed_spans:
            if abs_start < ce and abs_end > cs:
                return True
        return False

    for anchor in _PRICE_ANCHOR.finditer(text):
        window_start = max(0, anchor.start() - _CONTEXT_BEFORE)
        window_end = min(len(text), anchor.end() + _CONTEXT_AFTER)
        window = text[window_start:window_end]

        for pattern in _LOCAL_PRICE_PATTERNS:
            for match in pattern.finditer(window):
                groups = match.groups()
                raw = match.group()
                abs_position = window_start + match.start()
                abs_end = abs_position + len(raw)

                if _reject_local_price_match(window, match):
                    continue
                if raw in seen_raw:
                    continue
                if _overlaps_consumed(abs_position, abs_end):
                    continue
                seen_raw.add(raw)
                consumed_spans.append((abs_position, abs_end))

                if len(groups) == 1:
                    val = float(groups[0])
                    prices.append({
                        "value": val,
                        "lower": val,
                        "upper": val,
                        "raw_match": raw,
                        "position": abs_position,
                        "context": text[max(0, abs_position - 80):abs_end + 80],
                    })
                elif len(groups) == 2:
                    lo, hi = float(groups[0]), float(groups[1])
                    prices.append({
                        "value": None,
                        "lower": lo,
                        "upper": hi,
                        "raw_match": raw,
                        "position": abs_position,
                        "context": text[max(0, abs_position - 80):abs_end + 80],
                    })

    prices.sort(key=lambda p: p["position"])
    unique_keys = set()
    deduped: list[dict] = []
    for price in prices:
        key = (price["lower"], price["upper"])
        if key not in unique_keys:
            unique_keys.add(key)
            deduped.append(price)
    return deduped


def filing_price_set(filing_pages: list[dict]) -> set[float]:
    """Return every distinct dollar-per-share value mentioned in the filing.

    Expands ranges into both endpoints. Used by §P-R6 to membership-check
    extracted per-share prices.
    """
    full_text = "\n".join(page.get("content", "") for page in filing_pages)
    prices = extract_prices_regex(full_text)
    out: set[float] = set()
    for p in prices:
        for key in ("value", "lower", "upper"):
            v = p.get(key)
            if isinstance(v, (int, float)):
                out.add(float(v))
    return out
