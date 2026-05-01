"""Repair-time row conservation checks."""

from __future__ import annotations

import hashlib
import inspect
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class RowAnchor:
    anchor_index: int
    bid_note: str | None
    bid_date_precise: str | None
    bid_date_rough: str | None
    bidder_alias_norm: str | None
    bidder_name: str | None
    bid_value_pershare: Any
    bid_value_lower: Any
    bid_value_upper: Any
    bid_value_unit: Any
    source_pages: tuple[int, ...]
    quote_prefix_norm: str


def _norm(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _source_pages(value: Any) -> tuple[int, ...]:
    pages = value if isinstance(value, list) else [value]
    return tuple(
        page for page in pages
        if isinstance(page, int) and not isinstance(page, bool)
    )


def _quote_prefix(value: Any) -> str:
    if isinstance(value, list):
        value = " ".join(str(item) for item in value)
    return (_norm(str(value)) or "")[:80]


def _anchor_from_row(index: int, row: dict[str, Any]) -> RowAnchor:
    return RowAnchor(
        anchor_index=index,
        bid_note=row.get("bid_note"),
        bid_date_precise=row.get("bid_date_precise"),
        bid_date_rough=row.get("bid_date_rough"),
        bidder_alias_norm=_norm(row.get("bidder_alias")),
        bidder_name=row.get("bidder_name"),
        bid_value_pershare=row.get("bid_value_pershare"),
        bid_value_lower=row.get("bid_value_lower"),
        bid_value_upper=row.get("bid_value_upper"),
        bid_value_unit=row.get("bid_value_unit"),
        source_pages=_source_pages(row.get("source_page")),
        quote_prefix_norm=_quote_prefix(row.get("source_quote")),
    )


def protected_anchors(
    raw_extraction: dict[str, Any],
    *,
    hard_row_indexes: set[int],
    obligation_row_indexes: set[int],
) -> list[RowAnchor]:
    """Return anchors for rows repair is not authorized to delete."""
    skipped = hard_row_indexes | obligation_row_indexes
    anchors: list[RowAnchor] = []
    for index, row in enumerate(raw_extraction.get("events", []) or []):
        if index in skipped or not isinstance(row, dict):
            continue
        anchors.append(_anchor_from_row(index, row))
    return anchors


def _matches_anchor(anchor: RowAnchor, row: dict[str, Any]) -> bool:
    row_pages = set(_source_pages(row.get("source_page")))
    if anchor.bid_note != row.get("bid_note"):
        return False
    if anchor.bid_date_precise != row.get("bid_date_precise"):
        return False
    if anchor.bid_date_rough != row.get("bid_date_rough"):
        return False
    if anchor.bidder_alias_norm and anchor.bidder_alias_norm != _norm(row.get("bidder_alias")):
        return False
    if anchor.bidder_name and anchor.bidder_name != row.get("bidder_name"):
        return False
    for field in ("bid_value_pershare", "bid_value_lower", "bid_value_upper", "bid_value_unit"):
        if getattr(anchor, field) != row.get(field):
            return False
    if anchor.source_pages and not (set(anchor.source_pages) & row_pages):
        return False
    quote_prefix = _quote_prefix(row.get("source_quote"))
    return quote_prefix.startswith(anchor.quote_prefix_norm[:40])


def check_repair_conservation(
    anchors: list[RowAnchor],
    repaired_extraction: dict[str, Any],
) -> list[dict[str, Any]]:
    """Emit hard flags for protected pre-repair rows missing after repair."""
    repaired_rows = [
        row for row in repaired_extraction.get("events", []) or []
        if isinstance(row, dict)
    ]
    flags: list[dict[str, Any]] = []
    for anchor in anchors:
        if any(_matches_anchor(anchor, row) for row in repaired_rows):
            continue
        flags.append({
            "code": "repair_lost_unaffected_rows",
            "severity": "hard",
            "reason": (
                "Repair deleted or failed to preserve protected row anchor: "
                f"{anchor.bid_note} {anchor.bidder_alias_norm or anchor.bidder_name} "
                f"on {anchor.bid_date_precise or anchor.bid_date_rough} "
                f"page {anchor.source_pages[0] if anchor.source_pages else 'unknown'}."
            ),
            "deal_level": True,
            "anchor_index": anchor.anchor_index,
        })
    return flags


def anchors_payload(anchors: list[RowAnchor]) -> list[dict[str, Any]]:
    return [asdict(anchor) for anchor in anchors]


def conservation_contract_version() -> str:
    payload = inspect.getsource(protected_anchors) + inspect.getsource(check_repair_conservation)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
