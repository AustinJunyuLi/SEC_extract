"""scripts/export_alex_csv.py — Flatten output/extractions/*.json to a single
CSV matching Alex's xlsx workbook column layout.

USAGE
-----
    python scripts/export_alex_csv.py                                     # all 9 reference deals to default path
    python scripts/export_alex_csv.py --out /tmp/ai_workbook.csv          # custom output path
    python scripts/export_alex_csv.py --slug medivation,imprivata,zep     # subset of deals

COLUMN LAYOUT
-------------
The first 31 columns mirror Alex's `deal_details_Alex_2026.xlsx` schema
(post-flatten: the legacy four boolean `bidder_type` columns and one note
column were replaced by a single scalar `bidder_type` column per the
2026-04-27 §F1 change). Two audit-trail columns are appended at the end
(`source_page`, `source_quote`) because the pipeline's §R3 non-negotiable
is that every row carries filing evidence. Those two columns are absent from
Alex's original workbook; downstream consumers that want pure Alex-format
can ignore them.

For the five deal-level legacy columns that the pipeline's JSON schema never
carried (`gvkeyT`, `DealNumber`, `gvkeyA`, `DateFiled`, `FormType`), we pull
the value from the first row of the deal's range in Alex's xlsx so the
exported CSV sits cleanly next to Alex's original workbook. Target-deal
exports (when the pipeline extends past the 9 reference deals) will emit
`"NA"` for these columns unless the caller extends `_deal_meta_from_xlsx`
to look them up from Compustat or a seeds file.

Bid-row convention: the pipeline emits `bid_note="Bid"` + `bid_type` per
§C3; Alex's xlsx uses `bid_note="NA"` + `bid_type="Informal"/"Formal"`
(Case 2 of the §C3 migrator in `scripts/build_reference.py`). This
exporter reverses the migration so the CSV matches Alex's more recent
convention.
"""

from __future__ import annotations

import argparse
import csv
import datetime
import json
import sys
from pathlib import Path
from typing import Any

import openpyxl

REPO_ROOT = Path(__file__).resolve().parent.parent
EXTRACTIONS_DIR = REPO_ROOT / "output" / "extractions"
XLSX_PATH = REPO_ROOT / "reference" / "deal_details_Alex_2026.xlsx"
PROGRESS_PATH = REPO_ROOT / "state" / "progress.json"
DEFAULT_OUT = REPO_ROOT / "output" / "ai_workbook_alex_format.csv"
SHEET_NAME = "deal_details"

# Roll-out order from CLAUDE.md (simple → complex).
ROLLOUT_ORDER: list[str] = [
    "medivation",
    "imprivata",
    "zep",
    "providence-worcester",
    "penford",
    "mac-gray",
    "petsmart-inc",
    "stec",
    "saks",
]

# First xlsx row per deal — used to lift deal-level Compustat fields.
# Keep in sync with scripts/build_reference.DEAL_ROWS.
DEAL_FIRST_ROW: dict[str, int] = {
    "providence-worcester": 6024,
    "medivation":           6060,
    "imprivata":            6076,
    "zep":                  6385,
    "petsmart-inc":         6408,
    "penford":              6461,
    "mac-gray":             6927,
    "saks":                 6996,
    "stec":                 7144,
}

# Exact column order — the first 35 mirror Alex's xlsx header.
COLUMNS: list[str] = [
    "index",                    # 1
    "TargetName",               # 2
    "gvkeyT",                   # 3
    "DealNumber",               # 4
    "Acquirer",                 # 5
    "gvkeyA",                   # 6
    "DateAnnounced",            # 7
    "DateEffective",            # 8
    "DateFiled",                # 9
    "FormType",                 # 10
    "URL",                      # 11
    "Auction",                  # 12
    "BidderID",                 # 13
    "BidderName",               # 14
    "bidder_type",              # 15
    "bid_value",                # 16
    "bid_value_pershare",       # 17
    "bid_value_lower",          # 18
    "bid_value_upper",          # 19
    "bid_value_unit",           # 20
    "multiplier",               # 21
    "bid_type",                 # 22
    "bid_date_precise",         # 23
    "bid_date_rough",           # 24
    "bid_note",                 # 25
    "all_cash",                 # 26
    "additional_note",          # 27
    "cshoc",                    # 28
    "comments_1",               # 29
    "comments_2",               # 30
    "comments_3",               # 31
    # AI audit trail — not in Alex's xlsx.
    "source_page",              # 32
    "source_quote",             # 33
]


# ---------------------------------------------------------------------------
# Deal-level legacy-field lookup from xlsx
# ---------------------------------------------------------------------------


_LEGACY_FIELDS = ("gvkeyT", "DealNumber", "gvkeyA", "DateFiled", "FormType")
_LEGACY_XLSX_COL = {
    "gvkeyT":     3,
    "DealNumber": 4,
    "gvkeyA":     6,
    "DateFiled":  9,
    "FormType":   10,
}


def _deal_meta_from_xlsx() -> dict[str, dict[str, Any]]:
    """Lift the 5 deal-level legacy fields from the first row of each deal's
    range in Alex's xlsx. Falls back to all-NA if the xlsx is missing
    (target deals we haven't ingested, or environments without the file)."""
    meta: dict[str, dict[str, Any]] = {slug: {k: "NA" for k in _LEGACY_FIELDS} for slug in DEAL_FIRST_ROW}
    if not XLSX_PATH.exists():
        return meta
    wb = openpyxl.load_workbook(XLSX_PATH, data_only=True, read_only=True)
    try:
        ws = wb[SHEET_NAME]
        for slug, row_num in DEAL_FIRST_ROW.items():
            for field, col in _LEGACY_XLSX_COL.items():
                v = ws.cell(row=row_num, column=col).value
                meta[slug][field] = v
    finally:
        wb.close()
    return meta


def _filing_url_by_slug() -> dict[str, str]:
    """Lift `filing_url` from state/progress.json for each deal slug. The
    pipeline's output JSON doesn't carry the URL; state/progress.json does."""
    if not PROGRESS_PATH.exists():
        return {}
    data = json.loads(PROGRESS_PATH.read_text())
    return {
        slug: (entry.get("filing_url") or "")
        for slug, entry in (data.get("deals") or {}).items()
    }


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _na(v: Any) -> Any:
    """Render None / empty as 'NA' to match Alex's xlsx convention."""
    if v is None:
        return "NA"
    if isinstance(v, str) and v == "":
        return "NA"
    if isinstance(v, list) and not v:
        return "NA"
    return v


def _bool_to_10(v: Any) -> Any:
    """Render bool → 1/0; None → 'NA'; pass other scalars through."""
    if v is None:
        return "NA"
    if isinstance(v, bool):
        return 1 if v else 0
    return v


def _iso_date(v: Any) -> Any:
    """Render ISO date strings and datetime objects to 'YYYY-MM-DD'."""
    if v is None or v == "":
        return "NA"
    if isinstance(v, datetime.datetime):
        return v.date().isoformat()
    if isinstance(v, datetime.date):
        return v.isoformat()
    # Already a string — assume ISO. Pass through.
    return v


def _bidder_type_scalar(bt: str | None) -> str:
    """Emit bidder_type for CSV export. Per `rules/bidders.md` §F1
    (2026-04-27) bidder_type is a scalar string in {"s", "f", "mixed"} or
    null. CSV represents null as "NA".
    """
    if bt is None:
        return "NA"
    return bt


def _reverse_c3_bid_note(bid_note: Any, bid_type: Any) -> tuple[Any, Any]:
    """Reverse §C3 unified-bid migration for Alex's convention.

    Pipeline JSON: bid_note="Bid" + bid_type="informal"/"formal"
    Alex's xlsx (recent form, Case 2 of the migrator):
        bid_note="NA" + bid_type="Informal"/"Formal"

    Returns (xlsx_bid_note, xlsx_bid_type). Non-bid rows pass through
    (bid_note preserved, bid_type → "NA" since it shouldn't be set).
    """
    if bid_note == "Bid" and bid_type in ("informal", "formal"):
        return ("NA", bid_type.capitalize())
    return (_na(bid_note), _na(bid_type).capitalize() if isinstance(_na(bid_type), str) and _na(bid_type) != "NA" else "NA")


def _row_from_event(
    slug: str,
    running_index: int,
    deal: dict[str, Any],
    legacy: dict[str, Any],
    ev: dict[str, Any],
) -> list[Any]:
    """Build one CSV row for one event."""
    bidder_type = _bidder_type_scalar(ev.get("bidder_type"))
    xlsx_bid_note, xlsx_bid_type = _reverse_c3_bid_note(ev.get("bid_note"), ev.get("bid_type"))

    # comments_1/2/3: pack our comments / bid_type_inference_note / additional_note
    # context without clobbering each other. Alex's cshoc column isn't in our
    # schema; leave as NA.
    comments_1 = _na(ev.get("comments"))
    comments_2 = _na(ev.get("bid_type_inference_note"))
    # Fold any row-level flags into comments_3 as a compact string so
    # adjudication context isn't lost. Empty → NA.
    flags = ev.get("flags") or []
    if flags:
        comments_3 = " | ".join(
            f"[{f.get('severity','?')}:{f.get('code','?')}] {f.get('reason','')}"
            for f in flags if isinstance(f, dict)
        )
    else:
        comments_3 = "NA"

    # source_quote may be a list (multi-quote §R3 form); join with " || ".
    sq = ev.get("source_quote")
    sp = ev.get("source_page")
    if isinstance(sq, list):
        sq = " || ".join(str(x) for x in sq)
    if isinstance(sp, list):
        sp = " / ".join(str(x) for x in sp)

    return [
        running_index,                                    # 1. index (sequential, no decimal-wedge)
        _na(deal.get("TargetName")),                      # 2
        _na(legacy.get("gvkeyT")),                        # 3
        _na(legacy.get("DealNumber")),                    # 4
        _na(deal.get("Acquirer")),                        # 5
        _na(legacy.get("gvkeyA")),                        # 6
        _iso_date(deal.get("DateAnnounced")),             # 7
        _iso_date(deal.get("DateEffective")),             # 8
        _iso_date(legacy.get("DateFiled")),               # 9
        _na(legacy.get("FormType")),                      # 10
        _na(deal.get("URL")),                             # 11
        _bool_to_10(deal.get("auction")),                 # 12
        _na(ev.get("BidderID")),                          # 13
        _na(ev.get("bidder_alias")),                      # 14
        bidder_type,                                      # 15
        _na(ev.get("bid_value")),                         # 16
        _na(ev.get("bid_value_pershare")),                # 17
        _na(ev.get("bid_value_lower")),                   # 18
        _na(ev.get("bid_value_upper")),                   # 19
        _na(ev.get("bid_value_unit")),                    # 20
        "NA",                                             # 21 multiplier (not in our schema)
        xlsx_bid_type,                                    # 22
        _iso_date(ev.get("bid_date_precise")),            # 23
        _iso_date(ev.get("bid_date_rough")),              # 24
        xlsx_bid_note,                                    # 25
        _bool_to_10(deal.get("all_cash")),                # 26
        _na(ev.get("additional_note")),                   # 27
        "NA",                                             # 28 cshoc (not in our schema)
        comments_1,                                       # 29
        comments_2,                                       # 30
        comments_3,                                       # 31
        _na(sp),                                          # 32 source_page
        _na(sq),                                          # 33 source_quote
    ]


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def export_csv(slugs: list[str], out_path: Path) -> tuple[int, int]:
    """Write one CSV containing every event for every requested slug.

    Returns (deal_count, row_count)."""
    legacy_by_slug = _deal_meta_from_xlsx()
    url_by_slug = _filing_url_by_slug()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    running_index = 1
    n_rows = 0
    with out_path.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(COLUMNS)
        for slug in slugs:
            path = EXTRACTIONS_DIR / f"{slug}.json"
            if not path.exists():
                print(f"[skip] {slug}: {path} not found", file=sys.stderr)
                continue
            payload = json.loads(path.read_text())
            deal = payload.get("deal") or {}
            # Deal-level JSON doesn't carry URL; lift from state/progress.json.
            if not deal.get("URL"):
                deal = {**deal, "URL": url_by_slug.get(slug) or None}
            events = payload.get("events") or []
            legacy = legacy_by_slug.get(slug, {k: "NA" for k in _LEGACY_FIELDS})
            for ev in events:
                writer.writerow(_row_from_event(slug, running_index, deal, legacy, ev))
                running_index += 1
                n_rows += 1
    return (sum(1 for s in slugs if (EXTRACTIONS_DIR / f"{s}.json").exists()), n_rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--slug",
        help="Comma-separated deal slugs (default: all 9 reference deals in rollout order).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output CSV path (default: {DEFAULT_OUT.relative_to(REPO_ROOT)}).",
    )
    args = parser.parse_args()

    if args.slug:
        slugs = [s.strip() for s in args.slug.split(",") if s.strip()]
    else:
        slugs = list(ROLLOUT_ORDER)

    deal_count, row_count = export_csv(slugs, args.out)
    rel = args.out.relative_to(REPO_ROOT) if args.out.is_relative_to(REPO_ROOT) else args.out
    print(f"wrote {row_count} rows across {deal_count} deals -> {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
