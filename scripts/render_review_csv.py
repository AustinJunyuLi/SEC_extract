"""Render finalized extraction JSON into Alex-facing review CSVs.

Pure projection only: this script does not repair, infer, or backfill
extraction data.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
EXTRACTIONS_DIR = REPO_ROOT / "output" / "extractions"
REVIEW_CSV_DIR = REPO_ROOT / "output" / "review_csv"

COLUMNS = [
    "slug",
    "BidderID",
    "bid_date_precise",
    "bid_date_rough",
    "bidder_display",
    "bidder_name",
    "bidder_alias",
    "process_phase",
    "role",
    "bid_note",
    "bid_type",
    "bid_value_pershare",
    "bid_value_lower",
    "bid_value_upper",
    "bid_value",
    "bid_value_unit",
    "consideration_components",
    "drop_initiator",
    "drop_reason_class",
    "final_round_announcement",
    "final_round_extension",
    "final_round_informal",
    "invited_to_formal_round",
    "submitted_formal_bid",
    "press_release_subject",
    "exclusivity_days",
    "source_page",
    "source_quote",
    "flags_codes",
    "flag_severities",
]

_PLACEHOLDER_RE = re.compile(r"^(Financial|Strategic)\s+(\d+)$", re.IGNORECASE)


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    return str(value)


def _source_quote(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return "\n".join(value)
    raise ValueError("source_quote must be string, list[str], or null")


def _flag_codes(ev: dict[str, Any]) -> list[str]:
    flags = ev.get("flags") or []
    if not isinstance(flags, list):
        raise ValueError("flags must be a list")
    codes: list[str] = []
    for flag in flags:
        if not isinstance(flag, dict):
            raise ValueError("flag entries must be objects")
        code = flag.get("code")
        if not isinstance(code, str) or not code:
            raise ValueError("flag code must be non-empty string")
        codes.append(code)
    return codes


def _flag_severities(ev: dict[str, Any]) -> str:
    counts = {"hard": 0, "soft": 0, "info": 0}
    for flag in ev.get("flags") or []:
        severity = flag.get("severity") if isinstance(flag, dict) else None
        if severity not in counts:
            raise ValueError(f"invalid flag severity: {severity!r}")
        counts[severity] += 1
    return f"H={counts['hard']};S={counts['soft']};I={counts['info']}"


def _placeholder_display(ev: dict[str, Any]) -> str:
    alias = ev.get("bidder_alias")
    bidder_type = ev.get("bidder_type")
    if isinstance(alias, str) and alias:
        match = _PLACEHOLDER_RE.match(alias)
        if match:
            kind, number = match.groups()
            label = "financial sponsor" if kind.lower() == "financial" else "strategic bidder"
            return f"Unnamed {label} {number}"
        return f"Unnamed {alias}"
    if bidder_type == "f":
        return "Unnamed financial sponsor"
    if bidder_type == "s":
        return "Unnamed strategic bidder"
    return "Unnamed party"


def _bidder_display(ev: dict[str, Any], registry: dict[str, Any]) -> str:
    bidder_name = ev.get("bidder_name")
    if bidder_name is None:
        display = _placeholder_display(ev)
    else:
        entry = registry.get(bidder_name)
        resolved = entry.get("resolved_name") if isinstance(entry, dict) else None
        display = resolved or ev.get("bidder_alias") or bidder_name
    if "nda_promoted_from_placeholder" in _flag_codes(ev):
        display = f"{display} - promoted from unnamed placeholder"
    if not display:
        raise ValueError("bidder_display cannot be empty")
    return str(display)


def render_rows(slug: str, extraction: dict[str, Any]) -> list[dict[str, str]]:
    deal = extraction.get("deal")
    events = extraction.get("events")
    if not isinstance(deal, dict):
        raise ValueError("extraction.deal must be an object")
    if not isinstance(events, list):
        raise ValueError("extraction.events must be a list")
    registry = deal.get("bidder_registry") or {}
    if not isinstance(registry, dict):
        raise ValueError("deal.bidder_registry must be an object")

    rows: list[dict[str, str]] = []
    for ev in events:
        if not isinstance(ev, dict):
            raise ValueError("events entries must be objects")
        row: dict[str, str] = {}
        for column in COLUMNS:
            if column == "slug":
                row[column] = slug
            elif column == "bidder_display":
                row[column] = _bidder_display(ev, registry)
            elif column == "consideration_components":
                row[column] = _stringify(ev.get(column))
            elif column == "source_page":
                row[column] = _stringify(ev.get(column))
            elif column == "source_quote":
                row[column] = _source_quote(ev.get(column))
            elif column == "flags_codes":
                row[column] = ";".join(_flag_codes(ev))
            elif column == "flag_severities":
                row[column] = _flag_severities(ev)
            else:
                row[column] = _stringify(ev.get(column))
        rows.append(row)
    return rows


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _load_extraction(slug: str) -> dict[str, Any]:
    path = EXTRACTIONS_DIR / f"{slug}.json"
    if not path.exists():
        raise FileNotFoundError(f"missing extraction input: {path}")
    payload = json.loads(path.read_text())
    if not isinstance(payload, dict):
        raise ValueError(f"extraction input is not an object: {path}")
    return payload


def _available_slugs() -> list[str]:
    if not EXTRACTIONS_DIR.exists():
        raise FileNotFoundError(f"missing extraction directory: {EXTRACTIONS_DIR}")
    return sorted(path.stem for path in EXTRACTIONS_DIR.glob("*.json"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--slug", help="Render one finalized extraction.")
    selection.add_argument("--all", action="store_true", help="Render every finalized extraction.")
    parser.add_argument("--dump", action="store_true", help="Print CSV to stdout instead of writing files.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    slugs = _available_slugs() if args.all else [args.slug]
    all_rows: list[dict[str, str]] = []
    per_slug: dict[str, list[dict[str, str]]] = {}
    for slug in slugs:
        rows = render_rows(slug, _load_extraction(slug))
        per_slug[slug] = rows
        all_rows.extend(rows)

    if args.dump:
        writer = csv.DictWriter(sys.stdout, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(all_rows)
        return 0

    for slug, rows in per_slug.items():
        _write_csv(REVIEW_CSV_DIR / f"{slug}.csv", rows)
    if args.all:
        _write_csv(REVIEW_CSV_DIR / "_combined.csv", all_rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
