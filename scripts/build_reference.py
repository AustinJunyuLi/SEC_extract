"""scripts/build_reference.py — Convert Alex's xlsx to reference/alex/{slug}.json.

One-time conversion. Reads deal row ranges from
`reference/deal_details_Alex_2026.xlsx` (sheet `deal_details`), applies the
resolved §Q1–§Q4 fixes, maps to the §R1 schema, emits one JSON per deal
conformant to `rules/schema.md`.

USAGE
-----
    python scripts/build_reference.py --slug medivation          # one deal
    python scripts/build_reference.py --all                      # all 9
    python scripts/build_reference.py --slug medivation --dump   # print, don't write

STATUS
------
First pass — Medivation-focused. Renumbering + deal-lift logic applies uniformly
to all 9 deals; §Q1 (Saks delete), §Q2 (Zep expand) are implemented as
deal-specific hooks. Audit the output of each deal by hand against the xlsx
before trusting it for diffing.

WHY THIS EXISTS
---------------
`reference/alex/{slug}.json` is the answer key that `scoring/diff.py` joins
against. It is **Alex's intent** as structured data, not the xlsx's literal
cells — see `rules/dates.md` §Q and `reference/alex/README.md`. Structural
defects Alex flagged (duplicate BidderIDs, 5-bidders-in-one-row) are fixed
here; all fixes are preserved as flags on the resulting rows so reviewers can
trace provenance.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import openpyxl

REPO_ROOT = Path(__file__).resolve().parent.parent
XLSX_PATH = REPO_ROOT / "reference" / "deal_details_Alex_2026.xlsx"
OUT_DIR = REPO_ROOT / "reference" / "alex"
FLAGGED_ROWS_PATH = OUT_DIR / "alex_flagged_rows.json"
SHEET_NAME = "deal_details"


# ---------------------------------------------------------------------------
# Configuration: row ranges and §Q overrides
# ---------------------------------------------------------------------------

DEAL_ROWS: dict[str, tuple[int, int]] = {
    "providence-worcester": (6024, 6059),
    "medivation":           (6060, 6075),
    "imprivata":            (6076, 6104),
    "zep":                  (6385, 6407),
    "petsmart-inc":         (6408, 6457),
    "penford":              (6461, 6485),
    "mac-gray":             (6927, 6960),
    "saks":                 (6996, 7020),
    "stec":                 (7144, 7171),
}

# §Q1 — Saks rows Alex said to delete.
SAKS_DELETE_ROWS = {7013, 7015}

def _load_flagged_xlsx_rows() -> dict[str, set[int]]:
    """Parse reference/alex/alex_flagged_rows.json → {slug: {xlsx_row, ...}}."""
    if not FLAGGED_ROWS_PATH.exists():
        return {}
    data = json.loads(FLAGGED_ROWS_PATH.read_text())
    return {
        slug: {item["xlsx_row"] for item in items}
        for slug, items in data.get("deals", {}).items()
    }


# §Q2 — Zep row 6390: one xlsx row → 5 atomized rows, per Alex's note.
ZEP_ROW_6390_EXPANSION_FLAG = {
    "code": "alex_row_expanded",
    "severity": "info",
    "reason": (
        "from xlsx row 6390; original Alex comment: "
        "'This field needs to be expanded to 5 bidders; one of them bid 20, "
        "another 22, another three [20,22]?'"
    ),
}

# §A3 — same-date tie-break rank by event class.
# Bid rows (bid_note="Bid") rank 6 or 7 per bid_type — see _a3_rank().
A3_RANK: dict[str, int] = {
    # Rank 1 — process announcements / public events
    "Bid Press Release": 1, "Sale Press Release": 1, "Target Sale Public": 1,
    "Final Round Ann": 1, "Final Round Inf Ann": 1,
    "Final Round Ext Ann": 1, "Final Round Inf Ext Ann": 1,
    "Bidder Sale": 1, "Activist Sale": 1,
    # Rank 2 — process start/restart
    "Target Sale": 2, "Target Interest": 2,
    "Target Initiated": 2, "Terminated": 2, "Restarted": 2,
    # Rank 3 — advisor/IB changes
    "IB": 3, "IB Terminated": 3,
    # Rank 4 — bidder first-contact
    "Bidder Interest": 4,
    # Rank 5 — NDA
    "NDA": 5,
    # Rank 6 — informal bids (default for "Bid"; bumps to 7 for bid_type="formal")
    "Bid": 6,
    # Rank 8 — mid-round dropouts
    "Drop": 8, "DropBelowInf": 8, "DropAtInf": 8, "DropBelowM": 8, "DropTarget": 8,
    "DropBelowFormal": 8, "DropAtFormal": 8,
    # Rank 9 — final-round deadlines
    "Final Round": 9, "Final Round Inf": 9,
    "Final Round Ext": 9, "Final Round Inf Ext": 9,
    "Final Round Formal": 9, "Auction Closed": 9,
    # Rank 10 — post-deadline
    "Late Bid": 10,
    # Rank 11 — signing
    "Executed": 11,
}


def _a3_rank(ev: dict[str, Any]) -> int:
    """§A3 same-date rank. Bid rows (§C3) rank by bid_type:
    informal → 6, formal → 7."""
    bn = ev.get("bid_note") or ""
    if bn == "Bid":
        return 7 if ev.get("bid_type") == "formal" else 6
    return A3_RANK.get(bn, 99)


# ---------------------------------------------------------------------------
# XLSX column layout
# ---------------------------------------------------------------------------

# 1-indexed. Col 1 is a blank/index column.
COL = {
    "TargetName":       2,
    "gvkeyT":           3,
    "DealNumber":       4,
    "Acquirer":         5,
    "gvkeyA":           6,
    "DateAnnounced":    7,
    "DateEffective":    8,
    "DateFiled":        9,
    "FormType":         10,
    "URL":              11,
    "Auction":          12,
    "BidderID":         13,
    "BidderName":       14,
    "bt_financial":     15,
    "bt_strategic":     16,
    "bt_mixed":         17,
    "bt_nonUS":         18,
    "bidder_type_note": 19,
    "bid_value":        20,
    "bid_value_pershare": 21,
    "bid_value_lower":  22,
    "bid_value_upper":  23,
    "bid_value_unit":   24,
    "multiplier":       25,
    "bid_type":         26,
    "bid_date_precise": 27,
    "bid_date_rough":   28,
    "bid_note":         29,
    "all_cash":         30,
    "additional_note":  31,
    "cshoc":            32,
    "comments_1":       33,
    "comments_2":       34,
    "comments_3":       35,
}


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

_MOJIBAKE_MARKERS = ("Ã", "Â", "â€", "Ä")


def _unmojibake(s: str) -> str:
    """Salvage UTF-8 bytes that were decoded as Latin-1.

    Common when an xlsx string is `dÃ©pÃ´t` (= UTF-8 for 'dépôt' but each
    byte was interpreted as Latin-1). Round-trip `encode('latin-1') →
    decode('utf-8')` recovers the original. Only applied when the string
    contains mojibake markers AND the round-trip succeeds — keeps clean
    strings untouched.
    """
    if not any(m in s for m in _MOJIBAKE_MARKERS):
        return s
    try:
        fixed = s.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return s
    # Guard: salvage must not re-introduce other replacement chars.
    if "\ufffd" in fixed:
        return s
    return fixed


def _clean(v: Any) -> Any:
    """Normalize xlsx missing-value encodings to None, salvage mojibake."""
    if v is None:
        return None
    if isinstance(v, str):
        s = _unmojibake(v.strip())
        if s.upper() in ("NA", "N/A", ""):
            return None
        return s
    return v


def _iso_date(v: Any) -> str | None:
    if v is None:
        return None
    if isinstance(v, datetime.datetime):
        return v.date().isoformat()
    if isinstance(v, datetime.date):
        return v.isoformat()
    if isinstance(v, str):
        # Rare: dates stored as strings; accept YYYY-MM-DD.
        m = re.match(r"(\d{4}-\d{2}-\d{2})", v)
        if m:
            return m.group(1)
    return None


def _bool(v: Any) -> bool | None:
    """1/0/TRUE/FALSE/blank → bool or None."""
    v = _clean(v)
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(int(v))
    if isinstance(v, str):
        s = v.strip().upper()
        if s in ("1", "TRUE", "YES", "Y"):
            return True
        if s in ("0", "FALSE", "NO", "N"):
            return False
    return None


def _num(v: Any) -> float | int | None:
    v = _clean(v)
    if v is None:
        return None
    if isinstance(v, (int, float)):
        # Keep int when integral and originally an int
        if isinstance(v, float) and v.is_integer():
            return int(v)
        return v
    if isinstance(v, str):
        try:
            f = float(v.replace(",", "").replace("$", ""))
            return int(f) if f.is_integer() else f
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# Raw row fetch
# ---------------------------------------------------------------------------

@dataclass
class RawRow:
    xlsx_row: int
    cells: dict[str, Any]  # column-name → cleaned value

    def get(self, name: str) -> Any:
        return _clean(self.cells.get(name))


def load_raw_rows(slug: str) -> list[RawRow]:
    lo, hi = DEAL_ROWS[slug]
    wb = openpyxl.load_workbook(XLSX_PATH, data_only=True, read_only=True)
    ws = wb[SHEET_NAME]
    rows: list[RawRow] = []
    for offset, tup in enumerate(ws.iter_rows(min_row=lo, max_row=hi, values_only=True)):
        cells = {name: tup[idx - 1] for name, idx in COL.items()}
        rows.append(RawRow(xlsx_row=lo + offset, cells=cells))
    wb.close()
    return rows


# ---------------------------------------------------------------------------
# Deal-level field lift (§N1)
# ---------------------------------------------------------------------------

def _majority_or_first(values: list[Any]) -> Any:
    """Most common non-null value; falls back to first non-null."""
    seen: dict[Any, int] = {}
    for v in values:
        if v is None:
            continue
        seen[v] = seen.get(v, 0) + 1
    if not seen:
        return None
    return max(seen.items(), key=lambda kv: kv[1])[0]


def build_deal_object(slug: str, rows: list[RawRow]) -> dict[str, Any]:
    """Lift deal-level fields once, per §N1/§R1."""
    def pick(col: str) -> Any:
        return _majority_or_first([r.get(col) for r in rows])

    date_announced = _iso_date(pick("DateAnnounced"))
    date_effective = _iso_date(pick("DateEffective"))
    date_filed     = _iso_date(pick("DateFiled"))
    all_cash       = _bool(pick("all_cash"))
    auction        = _bool(pick("Auction"))

    return {
        "slug": slug,
        "TargetName":        pick("TargetName"),
        "Acquirer":          pick("Acquirer"),
        "DateAnnounced":     date_announced,
        "DateEffective":     date_effective,
        "DateFiled":         date_filed,
        "FormType":          pick("FormType"),
        "URL":               pick("URL"),
        "auction":           auction,
        "all_cash":          all_cash,
        # Alex-absent fields (AI-only at extraction time).
        "target_legal_counsel":    None,
        "acquirer_legal_counsel":  None,
        "go_shop_days":            None,
        "termination_fee":         None,
        "termination_fee_pct":     None,
        "reverse_termination_fee": None,
        # Populated below after bidder canonicalization.
        "bidder_registry": {},
        "deal_flags": [],
    }


# ---------------------------------------------------------------------------
# Bidder canonicalization (§E3)
# ---------------------------------------------------------------------------

_EVENT_MARKER_NOTES = {
    "Bid Press Release", "Final Round Ann", "Final Round", "Final Round Inf",
    "Final Round Formal", "Final Round Inf Ann", "Target Initiated",
    "Terminated", "Restarted", "Auction Closed", "Bidder Sale", "Activist Sale",
}


def _is_event_marker_row(alias: str | None, note: str | None) -> bool:
    """Rows that describe the process itself (no bidder on the left-hand side)."""
    if alias is None and note in _EVENT_MARKER_NOTES:
        return True
    return False


def canonicalize_bidders(rows: list[RawRow]) -> tuple[dict[int, str], dict[str, Any]]:
    """Assign bidder_01, bidder_02, ... deterministically in first-appearance order.

    Returns:
      xlsx_row → canonical id ("" for event-marker rows with no bidder).
      registry: canonical id → {resolved_name, aliases_observed, first_appearance_row}
    """
    canonical: dict[int, str] = {}
    registry: dict[str, dict[str, Any]] = {}
    alias_to_id: dict[str, str] = {}
    next_idx = 1

    for r in rows:
        alias_raw = r.get("BidderName")
        note = r.get("bid_note")
        if alias_raw is None:
            if _is_event_marker_row(alias_raw, note):
                canonical[r.xlsx_row] = ""
            else:
                canonical[r.xlsx_row] = ""
            continue
        # Key on the alias string exactly as Alex wrote it (§E3 defers
        # cross-row canonicalization to the AI extractor; for the reference
        # JSON we treat alias-string-identity as entity-identity, which is
        # how Alex populated the workbook).
        key = alias_raw
        if key not in alias_to_id:
            cid = f"bidder_{next_idx:02d}"
            alias_to_id[key] = cid
            registry[cid] = {
                "resolved_name": alias_raw,
                "aliases_observed": [alias_raw],
                "first_appearance_row_index": r.xlsx_row,
            }
            next_idx += 1
        canonical[r.xlsx_row] = alias_to_id[key]
    return canonical, registry


# ---------------------------------------------------------------------------
# Bidder-type collapse (§F1)
# ---------------------------------------------------------------------------

def build_bidder_type(r: RawRow) -> dict[str, Any] | None:
    fin  = _bool(r.get("bt_financial"))
    strat = _bool(r.get("bt_strategic"))
    mixed = _bool(r.get("bt_mixed"))
    nonus = _bool(r.get("bt_nonUS"))
    note  = r.get("bidder_type_note")
    # If none set, no type.
    if not any([fin, strat, mixed]):
        if note is None and nonus is None:
            return None
    if mixed:
        base = "mixed"
    elif fin and strat:
        base = "mixed"
    elif fin:
        base = "f"
    elif strat:
        base = "s"
    else:
        base = None
    # §F1: parse legacy note substring to populate `public: bool`. Alex's
    # workbook uses strings like "S" (no signal), "public S", "Non-US public S",
    # "public financial". The word "public" in the note means public=true.
    # Absent that token we leave public=null (ambiguous; AI can disambiguate).
    public = None
    if note and isinstance(note, str) and "public" in note.lower():
        public = True
    return {
        "base": base,
        "non_us": bool(nonus) if nonus is not None else False,
        "public": public,
        "note": note,
    }


# ---------------------------------------------------------------------------
# Event-row assembly
# ---------------------------------------------------------------------------

def _migrate_bid_note(r: RawRow) -> tuple[str | None, str | None, str | None]:
    """Apply the §C3 bid-row migration.

    Returns `(bid_note, bid_type_inferred, legacy_label)`:

    - `bid_note`: the rulebook-canonical §C1 code. Bid rows always use `"Bid"`.
    - `bid_type_inferred`: `"informal"` / `"formal"` / `None` — the bid_type
      inferred from the legacy label (when the xlsx used one); `None` if the
      xlsx had a non-bid event code or a blank.
    - `legacy_label`: the original xlsx `bid_note` string when it was one of
      the deprecated bid-row labels (`"Inf"` / `"Formal Bid"` / `"Revised Bid"`),
      else `None`. Used for a `legacy_bid_note_migrated` provenance flag.

    Handles three cases:

    1. xlsx `bid_note` is one of the deprecated bid-row labels → migrate to
       `"Bid"` + inferred `bid_type`, record legacy label for provenance.
    2. xlsx `bid_note` is blank / "NA" but xlsx `bid_type` is set (Alex's
       earlier convention) → emit `"Bid"` with the xlsx `bid_type`.
    3. xlsx `bid_note` is any other §C1 code (NDA, IB, etc.) → pass through.
    """
    note = r.get("bid_note")
    legacy = None

    # Case 1: deprecated bid-row label.
    if isinstance(note, str):
        if note == "Inf":
            return ("Bid", "informal", note)
        if note == "Formal Bid":
            return ("Bid", "formal", note)
        if note == "Revised Bid":
            # Keep provenance that this was a revision; the downstream can
            # reconstruct revision-vs-first via BidderID ordering on same
            # bidder_name.
            return ("Bid", "formal", note)

    # Case 2: blank bid_note recovered from bid_type column.
    if note is None:
        bt = (r.get("bid_type") or "").lower() if isinstance(r.get("bid_type"), str) else None
        if bt == "informal":
            return ("Bid", "informal", None)
        if bt == "formal":
            return ("Bid", "formal", None)
        return (None, None, None)

    # Case 3: non-bid §C1 event (NDA, IB, Drop, Executed, ...).
    return (note, None, None)


def _bid_type_canon(v: Any) -> str | None:
    v = _clean(v)
    if v is None:
        return None
    s = str(v).strip().lower()
    if s == "informal":
        return "informal"
    if s == "formal":
        return "formal"
    return None


def _comments(r: RawRow) -> str | None:
    parts = [r.get(k) for k in ("comments_1", "comments_2", "comments_3")]
    parts = [p for p in parts if p]
    return " | ".join(str(p) for p in parts) if parts else None


def _map_bid_value_unit(v: Any) -> str | None:
    """§R1: canonical per-share unit is `"USD_per_share"`, aggregate is `"USD"`,
    other currencies use codes. Alex's legacy workbook uses `"dollar"` (a
    per-share stand-in). Map that to `"USD_per_share"`; pass through other
    values unchanged.
    """
    v = _clean(v)
    if v is None:
        return None
    s = str(v).strip()
    if s.lower() == "dollar":
        return "USD_per_share"
    return s


def build_event_row(r: RawRow, canonical_id: str) -> dict[str, Any]:
    # §C3 migration: normalize bid-row event type to "Bid" + bid_type.
    note, inferred_bid_type, legacy_label = _migrate_bid_note(r)
    bid_type = _bid_type_canon(r.get("bid_type")) or inferred_bid_type

    # §B2: bid_date_rough is populated IFF the date was inferred. When Alex's
    # xlsx gives an explicit ISO date in bid_date_precise, the legacy "rough"
    # mirror in the xlsx is a serialization artifact, not a semantic signal —
    # null it out.
    precise = _iso_date(r.get("bid_date_precise"))
    rough_raw = r.get("bid_date_rough")
    rough = rough_raw if precise is None else None

    # §H1: point bids have null `bid_value_lower` / `bid_value_upper`. Alex's
    # xlsx stores `lower == upper == pershare` on point bids as a workbook
    # convention; strip that so the reference JSON matches the rulebook.
    pershare = _num(r.get("bid_value_pershare"))
    lower = _num(r.get("bid_value_lower"))
    upper = _num(r.get("bid_value_upper"))
    if pershare is not None and lower == pershare and upper == pershare:
        lower = None
        upper = None

    # §R1: `multiplier` is only meaningful for non-dollar units (e.g.,
    # `"EBITDA 12x"`). Alex's xlsx stores `1` as a no-op default on
    # plain-dollar bids; strip that to null so the semantics are clear.
    multiplier = r.get("multiplier")
    if multiplier == 1 or multiplier == 1.0:
        multiplier = None

    flags: list[dict[str, Any]] = []
    if legacy_label is not None:
        flags.append({
            "code": "legacy_bid_note_migrated",
            "severity": "info",
            "reason": (
                f"xlsx bid_note={legacy_label!r} migrated to bid_note='Bid' + "
                f"bid_type={bid_type!r} per rules/events.md §C3"
            ),
        })

    # Revised Bid provenance: the xlsx distinguished a bidder's subsequent
    # formal bid with the label 'Revised Bid'. Post-§C3, both bids carry
    # bid_note='Bid' + bid_type='formal'; we annotate the revision so the
    # downstream can reconstruct ordering without a distinct bid_note.
    additional_note = r.get("additional_note")
    if legacy_label == "Revised Bid":
        marker = "revised"
        if additional_note is None:
            additional_note = marker
        elif marker not in str(additional_note).lower():
            additional_note = f"{additional_note} | {marker}"

    return {
        # BidderID is assigned later (post-sort).
        "BidderID": None,
        "process_phase": None,
        "role": "bidder",
        "bidder_name": canonical_id or None,
        "bidder_alias": r.get("BidderName"),
        "bidder_type": build_bidder_type(r),
        "bid_note": note,
        "bid_type": bid_type,
        "bid_date_precise": precise,
        "bid_date_rough":   rough,
        "bid_value":          _num(r.get("bid_value")),
        "bid_value_pershare": pershare,
        "bid_value_lower":    lower,
        "bid_value_upper":    upper,
        "bid_value_unit":     _map_bid_value_unit(r.get("bid_value_unit")),
        "multiplier":         multiplier,
        "cash_per_share":         None,
        "stock_per_share":        None,
        "contingent_per_share":   None,
        "consideration_components": None,
        "aggregate_basis":        None,
        "exclusivity_days":       None,
        "financing_contingent":   None,
        "highly_confident_letter": False,
        "process_conditions_note": None,
        "additional_note": additional_note,
        "comments":        _comments(r),
        "_xlsx_row":       r.xlsx_row,            # provenance only; strip at write
        "_alex_bidder_id": r.get("BidderID"),     # provenance only; strip at write
        "flags": flags,
    }


# ---------------------------------------------------------------------------
# Chronological renumber (§A2/§A3/§Q3/§Q4 — applied universally)
# ---------------------------------------------------------------------------

def renumber_chronologically(
    events: list[dict[str, Any]],
    flagged_xlsx_rows: set[int],
) -> list[dict[str, Any]]:
    """Apply §A2/§A3 clean 1..N BidderID. Flag only rows Alex himself flagged.

    Per §A1, all reference deals are renumbered from Alex's decimal-wedge
    (0.7, 1.3, 1.5, ...) → strict 1..N integers. Routine decimal cleanup is
    captured as a deal-level `deal_flag` by the caller; only rows in
    `alex_flagged_rows.json` (§Q3/§Q4 duplicates, out-of-sequence) carry a
    per-row `bidder_id_renumbered_from_alex` info flag with the specific
    invariant cited.
    """
    # Propagate a date anchor forward so undated rows cluster near prior dated row.
    anchor: str | None = None
    for ev in events:
        if ev.get("bid_date_precise") is not None:
            anchor = ev["bid_date_precise"]
        ev["_date_anchor"] = ev.get("bid_date_precise") or anchor or ""
    ordered = sorted(
        events,
        key=lambda e: (e["_date_anchor"], _a3_rank(e), e["_xlsx_row"]),
    )
    for new_id, ev in enumerate(ordered, start=1):
        old_id = ev.pop("_alex_bidder_id", None)
        if ev["_xlsx_row"] in flagged_xlsx_rows:
            ev["flags"].append({
                "code": "bidder_id_renumbered_from_alex",
                "severity": "info",
                "reason": (
                    f"xlsx row {ev['_xlsx_row']} flagged in alex_flagged_rows.json "
                    f"(original BidderID={old_id}); renumbered to {new_id}"
                ),
            })
        ev["BidderID"] = new_id
        ev.pop("_date_anchor", None)
    return ordered


# ---------------------------------------------------------------------------
# §Q hooks
# ---------------------------------------------------------------------------

def apply_q1_saks(rows: list[RawRow], deal: dict[str, Any]) -> list[RawRow]:
    kept, dropped = [], []
    for r in rows:
        if r.xlsx_row in SAKS_DELETE_ROWS:
            dropped.append(r.xlsx_row)
        else:
            kept.append(r)
    if dropped:
        deal["deal_flags"].append({
            "code": "applied_alex_deletion",
            "severity": "info",
            "reason": f"§Q1: dropped xlsx rows {dropped} per Alex's 'should be deleted' notes",
        })
    return kept


def apply_q2_zep(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expand xlsx row 6390 into 5 atomized event rows per §Q2.

    Alex's ambiguous note: 'one bid 20, another 22, another three [20,22]?'
    We emit 5 rows with `bidder_alias = 'Party A'..'Party E'`, bid values
    populated conservatively (20, 22, [20-22], [20-22], [20-22]), each
    carrying the `alex_row_expanded` + `bid_value_ambiguous_per_alex` flags.
    Austin re-reads Zep's filing in Stage 3 and adjudicates.
    """
    out = []
    for ev in events:
        if ev["_xlsx_row"] != 6390:
            out.append(ev)
            continue
        template = ev
        configs = [
            ("Party A", {"bid_value_pershare": 20, "bid_value_lower": None, "bid_value_upper": None}),
            ("Party B", {"bid_value_pershare": 22, "bid_value_lower": None, "bid_value_upper": None}),
            ("Party C", {"bid_value_pershare": None, "bid_value_lower": 20, "bid_value_upper": 22}),
            ("Party D", {"bid_value_pershare": None, "bid_value_lower": 20, "bid_value_upper": 22}),
            ("Party E", {"bid_value_pershare": None, "bid_value_lower": 20, "bid_value_upper": 22}),
        ]
        for alias, value_overrides in configs:
            new_ev = json.loads(json.dumps(template, default=str))
            new_ev["bidder_alias"] = alias
            for k, v in value_overrides.items():
                new_ev[k] = v
            new_ev["flags"] = list(template["flags"]) + [
                ZEP_ROW_6390_EXPANSION_FLAG,
                {"code": "bid_value_ambiguous_per_alex", "severity": "info",
                 "reason": f"{alias} bid value inferred from Alex's ambiguous note"},
            ]
            out.append(new_ev)
    return out


# §Q5 — Medivation: aggregated NDA row (xlsx 6065) + Drop row (xlsx 6075).
MEDIVATION_NDA_AGG_XLSX_ROW = 6065
MEDIVATION_DROP_AGG_XLSX_ROW = 6075
MEDIVATION_UNNAMED_PLACEHOLDER_ALIASES = ("Party A", "Party B")


def apply_q5_medivation(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expand Medivation's aggregated NDA + Drop rows into atomic rows per §E1.

    Two xlsx rows compress multiple entities:
      - 6065: `"Several parties, including Sanofi"` NDA on 7/5 (≥3 entities)
      - 6075: `"Several parties"` Drop on 8/20 (≥2 unnamed entities)

    Expansion:
      - 6065 → 3 rows: Sanofi (reuses her existing canonical id from her 4/13
        Bidder Sale row) + Party A + Party B (new canonical ids).
      - 6075 → 2 rows: Party A + Party B Drops, reusing the Party A/B canonical
        ids from 6065. Sanofi has her own 8/20 Drop row already.

    "Several" is ≥ 3 in standard English → ≥ 2 unnamed parties beyond Sanofi.
    We emit exactly 2 placeholders to match that lower bound; if the AI
    extraction infers a different count, that surfaces in the diff as a
    legitimate both-defensible judgment call per the adjudication pass.
    """
    # Locate the aggregated rows.
    nda_idx = next(
        (i for i, ev in enumerate(events) if ev.get("_xlsx_row") == MEDIVATION_NDA_AGG_XLSX_ROW),
        None,
    )
    drop_idx = next(
        (i for i, ev in enumerate(events) if ev.get("_xlsx_row") == MEDIVATION_DROP_AGG_XLSX_ROW),
        None,
    )
    if nda_idx is None:
        return events  # nothing to expand; xlsx doesn't match the expected shape

    # Pull Sanofi's canonical id and bidder_type from her earliest non-aggregated row.
    sanofi_cid = None
    sanofi_type = None
    for ev in events:
        if ev.get("bidder_alias") == "Sanofi" and ev.get("bidder_name"):
            sanofi_cid = ev["bidder_name"]
            sanofi_type = ev.get("bidder_type")
            break
    if sanofi_cid is None:
        # Shouldn't happen — Sanofi has a 4/13 Bidder Sale row in the xlsx.
        # Failing loud beats silently skipping the expansion.
        raise RuntimeError(
            "apply_q5_medivation: Sanofi canonical id not found among events; "
            "xlsx 6065 expansion aborted"
        )

    # Allocate two fresh canonical ids for Party A / Party B. Must not
    # collide with anything already in the event set.
    existing_cids = {ev.get("bidder_name") for ev in events if ev.get("bidder_name")}

    def _next_cid(used: set[str]) -> str:
        n = 1
        while f"bidder_{n:02d}" in used:
            n += 1
        cid = f"bidder_{n:02d}"
        used.add(cid)
        return cid

    party_a_cid = _next_cid(existing_cids)
    party_b_cid = _next_cid(existing_cids)

    def _clone(template: dict[str, Any], overrides: dict[str, Any], reason: str) -> dict[str, Any]:
        new_ev = json.loads(json.dumps(template, default=str))
        for k, v in overrides.items():
            new_ev[k] = v
        new_ev["flags"] = list(template.get("flags", [])) + [{
            "code": "alex_row_expanded",
            "severity": "info",
            "reason": reason,
        }]
        return new_ev

    out: list[dict[str, Any]] = []
    for i, ev in enumerate(events):
        if i == nda_idx:
            reason = (
                f"§Q5: from xlsx row {MEDIVATION_NDA_AGG_XLSX_ROW} "
                f"('Several parties, including Sanofi'); atomized per §E1 — "
                "the xlsx compressed ≥3 NDA signers into one row"
            )
            out.append(_clone(ev, {
                "bidder_name": sanofi_cid,
                "bidder_alias": "Sanofi",
                "bidder_type": sanofi_type,
            }, reason))
            for alias, cid in zip(MEDIVATION_UNNAMED_PLACEHOLDER_ALIASES, (party_a_cid, party_b_cid)):
                out.append(_clone(ev, {
                    "bidder_name": cid,
                    "bidder_alias": alias,
                    "bidder_type": None,
                }, reason))
        elif i == drop_idx:
            reason = (
                f"§Q5: from xlsx row {MEDIVATION_DROP_AGG_XLSX_ROW} "
                f"('Several parties'); atomized per §E1 — companion to "
                f"xlsx {MEDIVATION_NDA_AGG_XLSX_ROW}'s unnamed-party NDAs"
            )
            for alias, cid in zip(MEDIVATION_UNNAMED_PLACEHOLDER_ALIASES, (party_a_cid, party_b_cid)):
                out.append(_clone(ev, {
                    "bidder_name": cid,
                    "bidder_alias": alias,
                    "bidder_type": None,
                }, reason))
        else:
            out.append(ev)
    return out


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def build_deal(slug: str) -> dict[str, Any]:
    raw = load_raw_rows(slug)
    deal = build_deal_object(slug, raw)

    if slug == "saks":
        raw = apply_q1_saks(raw, deal)

    canonical, registry = canonicalize_bidders(raw)

    events = [build_event_row(r, canonical[r.xlsx_row]) for r in raw]

    if slug == "zep":
        events = apply_q2_zep(events)
    if slug == "medivation":
        events = apply_q5_medivation(events)

    flagged_rows = _load_flagged_xlsx_rows().get(slug, set())
    events = renumber_chronologically(events, flagged_rows)

    # Deal-level note: reference JSONs always redefine BidderID per §A1.
    deal["deal_flags"].append({
        "code": "bidder_ids_renumbered_per_a1",
        "severity": "info",
        "reason": (
            "BidderIDs reassigned to strict 1..N per §A1; Alex's decimal-wedge "
            "convention (0.3, 1.5, ...) is not preserved in reference JSONs. "
            "Per-row provenance flags appear only for rows in "
            "alex_flagged_rows.json (§Q3/§Q4)."
        ),
    })

    # Rebuild registry in first-appearance-by-new-order for stable output.
    # For canonical ids that pre-exist in the initial canonicalize pass, lift
    # the aliases_observed list from there. For canonical ids introduced by
    # §Q expansions (apply_q5_medivation's Party A / Party B), seed the
    # registry from the first expanded row's bidder_alias so the entry isn't
    # aliases-empty.
    new_registry: dict[str, dict[str, Any]] = {}
    for ev in events:
        cid = ev.get("bidder_name")
        alias = ev.get("bidder_alias")
        if not cid:
            continue
        if cid not in new_registry:
            info = registry.get(cid, {})
            aliases = list(info.get("aliases_observed") or [])
            if alias and alias not in aliases:
                aliases.append(alias)
            new_registry[cid] = {
                "resolved_name": info.get("resolved_name") or alias,
                "aliases_observed": aliases,
                "first_appearance_BidderID": ev["BidderID"],
            }
        else:
            # Accumulate additional aliases on subsequent rows (e.g., if a
            # split bidder appears with multiple spellings).
            if alias and alias not in new_registry[cid]["aliases_observed"]:
                new_registry[cid]["aliases_observed"].append(alias)
    deal["bidder_registry"] = new_registry

    # Strip provenance helpers before writing.
    for ev in events:
        ev.pop("_xlsx_row", None)

    return {"deal": deal, "events": events}


def write_deal(slug: str, payload: dict[str, Any]) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{slug}.json"
    with path.open("w") as f:
        json.dump(payload, f, indent=2, default=str)
    return path


def _summary(slug: str, payload: dict[str, Any]) -> str:
    d = payload["deal"]
    e = payload["events"]
    renumbered = sum(1 for ev in e for f in ev["flags"] if f["code"] == "bidder_id_renumbered_from_alex")
    expanded   = sum(1 for ev in e for f in ev["flags"] if f["code"] == "alex_row_expanded")
    deleted    = sum(f.get("reason", "").count("§Q1") for f in d.get("deal_flags", []))
    return (
        f"{slug:24s} target={d['TargetName']!r} acquirer={d['Acquirer']!r} "
        f"n_events={len(e)} auction={d['auction']} all_cash={d['all_cash']} "
        f"renumbered={renumbered} expanded={expanded} deleted={deleted}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", help=f"One of {list(DEAL_ROWS)}")
    parser.add_argument("--all", action="store_true", help="Build all 9 reference deals.")
    parser.add_argument("--dump", action="store_true", help="Print JSON to stdout instead of writing.")
    args = parser.parse_args()

    slugs: list[str] = []
    if args.all:
        slugs = list(DEAL_ROWS)
    elif args.slug:
        if args.slug not in DEAL_ROWS:
            parser.error(f"unknown slug; expected one of {list(DEAL_ROWS)}")
        slugs = [args.slug]
    else:
        parser.error("specify --slug or --all")

    for slug in slugs:
        payload = build_deal(slug)
        if args.dump:
            print(json.dumps(payload, indent=2, default=str))
        else:
            path = write_deal(slug, payload)
            print(_summary(slug, payload))
            print(f"  -> {path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
