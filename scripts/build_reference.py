"""scripts/build_reference.py — Convert Alex's xlsx to reference/alex/{slug}.json.

One-time conversion. Reads deal row ranges from
`reference/deal_details_Alex_2026.xlsx` (sheet `deal_details`), applies the
resolved §Q1–§Q7 overrides, maps to the §R1 schema, emits one JSON per deal
conformant to `rules/schema.md`.

USAGE
-----
    python scripts/build_reference.py --slug medivation          # one deal
    python scripts/build_reference.py --all                      # all 9
    python scripts/build_reference.py --slug medivation --dump   # print, don't write

WHY THIS EXISTS
---------------
`reference/alex/{slug}.json` is the answer key that `scoring/diff.py` joins
against. It is **Alex's intent** as structured data, not the xlsx's literal
cells — so structural defects Alex flagged (duplicate BidderIDs,
bidders-in-one-row aggregations, rows he marked for deletion) are fixed
here rather than copied through. Every fix is preserved as a flag on the
resulting row (or as a `deal_flag`) so reviewers can trace provenance back
to the xlsx; the original rows are also kept verbatim in
`reference/alex/alex_flagged_rows.json`.

The AI extractor never sees these overrides — it reads filings directly.
The overrides only exist to make Alex's reference JSONs diffable.

§Q OVERRIDES APPLIED DURING CONVERSION
--------------------------------------

§Q1 — Saks rows 7013 and 7015 → deleted
    Alex's own comments on these two rows say "should be deleted": row
    7013 is an unsolicited letter with no NDA/price/follow-up, and row
    7015 is a sponsor row he flagged as "not a separate bid." We drop
    both when building `reference/alex/saks.json` so Alex's reference
    reflects his stated intent rather than his literal xlsx cells.
    The `applied_alex_deletion` deal_flag records the dropped rows.
    Both rows remain in `alex_flagged_rows.json` with verdict `delete`.

§Q2 — Zep row 6390 → expand into 5 atomized rows
    Row 6390 compresses 5 bidders into a single row; Alex's own note
    asks for expansion ("one bid 20, another 22, another three
    [20,22]?"). We atomize per `rules/bidders.md` §E1 into 5 rows
    (Party A..Party E) with bid values populated conservatively from
    Alex's ambiguous ranges. Each expanded row carries the
    `alex_row_expanded` flag plus `bid_value_ambiguous_per_alex` so the
    value interpretations are auditable.

§Q3 — Mac Gray `BidderID=21` duplicate → renumbered
    Xlsx row 6960 has `BidderID=21`, duplicating row 6957. The duplicate
    violates §A4 rule 3 (uniqueness), so the resulting JSON would fail
    validation. We reassign `BidderID = 1..N` chronologically per
    §A2/§A3, which dedupes by construction. The renumbered row carries
    a `bidder_id_renumbered_from_alex` info flag citing the original
    xlsx BidderID.

§Q4 — Medivation `BidderID=5` duplicate → renumbered
    Same failure mode as §Q3 on a different deal: rows 6066 and 6070
    both have `BidderID=5` (uniqueness violation); row 6067 has `ID=4`
    on 8/8 against row 6066's `ID=5` on 7/19 (date-order violation,
    §A4 rule 5). A single chronological renumber pass (shared with
    §Q3) fixes all three. Each affected row carries the
    `bidder_id_renumbered_from_alex` flag.

§Q5 — Medivation "Several parties" rows → atomized
    Two xlsx rows compress multiple entities: row 6065 is a 7/5 NDA
    labelled "Several parties, including Sanofi" (Sanofi + ≥2 unnamed);
    row 6075 is an 8/20 Drop labelled "Several parties" (the same ≥2
    unnamed parties). "Several" is ≥3 in standard English, so we
    atomize per the universal §E1 rule into: row 6065 → 3 rows (Sanofi reusing the
    canonical id from its 4/13 Bidder Sale, plus Party A and Party B
    with fresh canonical ids), row 6075 → 2 Drop rows (Party A + Party
    B reusing the ids from 6065; Sanofi already has its own 8/20 Drop).
    Placeholder count matches the `≥3 → Sanofi + 2 unnamed` lower
    bound; differing AI counts surface as legitimate diff signal, not
    noise. Each expanded row carries `alex_row_expanded`.

Without §Q5 atomization the AI's universally atomized output would diff as
several `ai_only` rows against the aggregated reference, drowning out
real extraction defects.

§Q6 — Acquirer rewrite for sponsor-backed deals
    Per Alex's 2026-04-27 directive, only the operating acquirer is
    recorded. Alex's xlsx Acquirer column has the operating name for
    some sponsor-backed deals and the consortium list or shell name for
    others. The converter rewrites the 4 sponsor-backed reference deals
    (petsmart-inc, mac-gray, zep, saks) to the operating-acquirer string
    and records `acquirer_normalized` as an info flag with the original
    xlsx value for provenance.

§Q7 — Executed-row atomization for consortium deals
    Per `rules/bidders.md` §E1 + §E2.b (rewritten 2026-04-27): when the
    merger-agreement counterparty is a consortium, one Executed row is
    emitted per explicitly identified operational/economic buyer member.
    Affects petsmart-inc (5 members: BC Partners, La Caisse, GIC Pte Ltd,
    StepStone Group, Longview Asset Management) and mac-gray (2 members:
    CSC ServiceWorks, Pamplona Capital Partners). When the xlsx lacks an
    Executed row entirely (petsmart-inc), a declarative repair in
    `Q7_MISSING_EXECUTED_REPAIRS` cites filing evidence for both the
    execution date and the member list; the converter fails loud if that
    evidence cannot be verified against the local filing pages. Each
    atomized row carries a `consortium_executed_atomized` provenance flag.

OTHER SUBSTANTIVE TRANSFORMS (NOT NUMBERED §Q*)
-----------------------------------------------

These transforms also shape the reference JSONs. They predate the §Q
numbering or fall outside the "specific row repair" pattern §Q* uses, but
are equally load-bearing for diffability.

* `_apply_taxonomy_redesign` — collapses Alex's 31-value workbook
  vocabulary into the current 18-value §C1 set (2026-04-27 redesign):
  retired Final Round labels, Drop labels, Press Release labels, and
  `Target Interest` map to current values plus structured modifier
  columns (drop_initiator, drop_reason_class, final_round_*,
  press_release_subject, etc.).
* `_convert_bid_note` — rewrites legacy `Inf` / `Formal Bid` /
  `Revised Bid` labels into the current `bid_note="Bid"` + `bid_type`
  unified-bid convention (§C3). `Revised Bid` provenance is preserved as
  a `"revised"` marker on `additional_note`.
* `apply_exclusivity_events` — collapses xlsx `Exclusivity N days` event
  rows into the structured `exclusivity_days` integer attribute on the
  preceding bid row (Zep 6405 → exclusivity_days=30 on the prior bid).
* `BLANK_BID_NOTE_REPAIRS` — narrowly hardcoded fix for xlsx rows where
  `bid_note` is simply blank in Alex's workbook but filing context
  identifies the event (Providence row 6028: G&W's 2016-04-13 NDA).
  Each repair attaches a `bid_note_repaired_blank` info flag for
  provenance.
* §G1+§G2 range-bid informal coercion — auto-coerces any `lower<upper`
  row whose `bid_type` was `"formal"` in Alex's workbook to `"informal"`
  per the 2026-04-27 unconditional-informal-on-range rule. Records a
  `bid_range_must_be_informal` info flag on the coerced row.

The AI extractor never reads these transforms; they only exist on the
Alex side to make the diff harness operational.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
from dataclasses import dataclass
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

# §Q6 — Acquirer rewrite for the 4 sponsor-backed reference deals.
# Per Alex 2026-04-27 directive, only the operating acquirer is recorded;
# the legal shell is NOT preserved as a separate field. Alex's xlsx
# Acquirer column for these 4 deals contains the consortium label or shell
# name; the converter overwrites it with the operating-acquirer string.
# Operational acquirer values are sourced from each filing's signature block.
Q6_ACQUIRER_REWRITE: dict[str, str] = {
    "petsmart-inc": "BC Partners, Inc.",
    "mac-gray":     "CSC ServiceWorks, Inc.",
    "zep":          "New Mountain Capital",
    "saks":         "Hudson's Bay Company",
}

# §Q7 — Executed-row atomization for the consortium reference deals.
# Per `rules/bidders.md` §E1 + §E2.b (rewritten 2026-04-27): when the
# merger-agreement counterparty is a consortium, emit one Executed row per
# explicitly identified operational/economic buyer member. If the xlsx lacks
# an Executed row, a repair must cite filing evidence for both the agreement
# execution date and the named member list; otherwise the converter fails loud.
Q7_EXECUTED_MEMBERS: dict[str, list[str]] = {
    "petsmart-inc": [
        "BC Partners, Inc.",
        "La Caisse",
        "GIC Pte Ltd",
        "StepStone Group",
        "Longview Asset Management",
    ],
    "mac-gray": [
        "CSC ServiceWorks, Inc.",
        "Pamplona Capital Partners",
    ],
    "zep":  ["New Mountain Capital"],
    "saks": ["Hudson's Bay Company"],
}

# Explicit missing-Executed repairs. These are not inference rules: each
# entry is a narrow, filing-cited patch for a known reference-converter
# defect. The template selector chooses the xlsx row to copy non-bidder
# context from; the filing evidence proves that an agreement was executed and
# that the listed operating/economic buyer members are identifiable.
Q7_MISSING_EXECUTED_REPAIRS: dict[str, dict[str, Any]] = {
    "petsmart-inc": {
        "template": {
            "bid_note": "Bid",
            "bidder_alias": "Buyer Group",
            "select": "latest",
        },
        "executed_date": "2014-12-14",
        "members": [
            "BC Partners, Inc.",
            "La Caisse",
            "GIC Pte Ltd",
            "StepStone Group",
            "Longview Asset Management",
        ],
        "execution_evidence": {
            "page": 2,
            "quote": (
                "Agreement and Plan of Merger (as it may be amended from time "
                "to time, the “merger agreement”), dated as of December 14, 2014"
            ),
        },
        "membership_evidence": {
            "page": 2,
            "quote": (
                "owned by a consortium including funds advised by BC Partners, "
                "Inc., La Caisse de dépôt et placement du Québec, affiliates "
                "of GIC Special Investments Pte Ltd, affiliates of StepStone "
                "Group LP and Longview Asset Management, LLC"
            ),
        },
    },
}

Q7_UNIDENTIFIABLE_MEMBER_RE = re.compile(
    r"\b("
    r"unknown|unidentified|unnamed|other|others|various|certain|several|"
    r"multiple|party\s+[a-z0-9]+|bidder\s+[a-z0-9]+|buyer\s+group|consortium"
    r")\b",
    re.IGNORECASE,
)


def apply_q6_acquirer_rewrite(slug: str, deal: dict[str, Any]) -> None:
    """§Q6 — overwrite deal['Acquirer'] with the operating acquirer for the
    4 sponsor-backed reference deals. Mutates `deal` in place. Records the
    original xlsx string in an `acquirer_normalized` info flag for audit.
    """
    new_value = Q6_ACQUIRER_REWRITE.get(slug)
    if new_value is None:
        return
    original = deal.get("Acquirer")
    if original == new_value:
        return
    deal["Acquirer"] = new_value
    deal["deal_flags"].append({
        "code": "acquirer_normalized",
        "severity": "info",
        "reason": (
            f"§Q6: xlsx Acquirer={original!r} normalized to operating "
            f"acquirer {new_value!r} per Alex 2026-04-27 directive."
        ),
    })


def _next_canonical_ids(events: list[dict[str, Any]], count: int) -> list[str]:
    used = {ev.get("bidder_name") for ev in events if ev.get("bidder_name")}
    out: list[str] = []
    n = 1
    while len(out) < count:
        cid = f"bidder_{n:02d}"
        if cid not in used:
            used.add(cid)
            out.append(cid)
        n += 1
    return out


def _canonical_ids_for_members(events: list[dict[str, Any]], members: list[str]) -> list[str]:
    by_alias = {
        ev.get("bidder_alias"): ev.get("bidder_name")
        for ev in events
        if ev.get("bidder_alias") and ev.get("bidder_name")
    }
    ids: list[str | None] = [by_alias.get(member) for member in members]
    missing = [i for i, cid in enumerate(ids) if cid is None]
    fresh = _next_canonical_ids(events, len(missing))
    for idx, cid in zip(missing, fresh):
        ids[idx] = cid
    return [cid for cid in ids if cid is not None]


def _filing_pages_by_number(slug: str) -> dict[int, str]:
    path = REPO_ROOT / "data" / "filings" / slug / "pages.json"
    if not path.exists():
        raise ValueError(f"§Q7: {slug} filing pages not found at {path.relative_to(REPO_ROOT)}")
    pages = json.loads(path.read_text())
    if not isinstance(pages, list):
        raise ValueError(f"§Q7: {slug} filing pages must be a list")
    out: dict[int, str] = {}
    for page in pages:
        if not isinstance(page, dict):
            continue
        number = page.get("number")
        content = page.get("content")
        if isinstance(number, int) and isinstance(content, str):
            out[number] = content
    return out


def _quote_in_page(content: str, quote: str) -> bool:
    if quote in content:
        return True
    return " ".join(quote.split()) in " ".join(content.split())


def _validate_q7_evidence(slug: str, repair: dict[str, Any], key: str) -> None:
    evidence = repair.get(key)
    if not isinstance(evidence, dict):
        raise ValueError(f"§Q7: {slug} {key} must be an evidence dict")
    page = evidence.get("page")
    quote = evidence.get("quote")
    if not isinstance(page, int) or not isinstance(quote, str) or not quote.strip():
        raise ValueError(f"§Q7: {slug} {key} must include integer page and non-empty quote")
    content = _filing_pages_by_number(slug).get(page)
    if content is None:
        raise ValueError(f"§Q7: {slug} {key} cites missing filing page {page}")
    if not _quote_in_page(content, quote):
        raise ValueError(f"§Q7: {slug} {key} quote not found on filing page {page}")


def validate_q7_missing_executed_repair(slug: str, repair: dict[str, Any]) -> None:
    """Validate a narrow, filing-cited repair for an xlsx missing Executed row.

    This deliberately does not infer missing Executed rows. It only accepts
    explicit repair specs whose template row and named consortium members are
    known, and whose execution/member evidence is present in the local filing.
    """
    template = repair.get("template")
    if not isinstance(template, dict):
        raise ValueError(f"§Q7: {slug} repair template must be a dict")
    if template.get("select") != "latest":
        raise ValueError(f"§Q7: {slug} repair template only supports select='latest'")
    for key in ("bid_note", "bidder_alias"):
        if not isinstance(template.get(key), str) or not template[key].strip():
            raise ValueError(f"§Q7: {slug} repair template must include {key}")

    executed_date = repair.get("executed_date")
    if not isinstance(executed_date, str):
        raise ValueError(f"§Q7: {slug} repair must include executed_date")
    try:
        datetime.date.fromisoformat(executed_date)
    except ValueError as exc:
        raise ValueError(f"§Q7: {slug} executed_date must be ISO YYYY-MM-DD") from exc

    members = repair.get("members")
    if not isinstance(members, list) or not members:
        raise ValueError(f"§Q7: {slug} repair must include non-empty members list")
    for member in members:
        if not isinstance(member, str) or not member.strip():
            raise ValueError(f"§Q7: {slug} repair has blank or non-string member")
        if Q7_UNIDENTIFIABLE_MEMBER_RE.search(member):
            raise ValueError(f"§Q7: {slug} repair has unidentifiable member {member!r}")

    _validate_q7_evidence(slug, repair, "execution_evidence")
    _validate_q7_evidence(slug, repair, "membership_evidence")


def _q7_missing_executed_template(
    slug: str,
    events: list[dict[str, Any]],
    repair: dict[str, Any],
) -> dict[str, Any]:
    template = repair["template"]
    candidates = [
        ev for ev in events
        if ev.get("bid_note") == template["bid_note"]
        and ev.get("bidder_alias") == template["bidder_alias"]
    ]
    if not candidates:
        raise RuntimeError(
            f"§Q7: {slug} missing-Executed repair found no template row "
            f"matching bid_note={template['bid_note']!r}, "
            f"bidder_alias={template['bidder_alias']!r}"
        )
    return max(
        candidates,
        key=lambda ev: (ev.get("bid_date_precise") or "", ev.get("_xlsx_row") or 0),
    )


def apply_q7_executed_atomization(
    slug: str, events: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """§Q7 — atomize Executed row(s) per consortium constituent.

    For consortium-signed mergers, the xlsx may contain a single Executed row
    whose `bidder_alias` is the consortium label or shell. The xlsx may also
    omit the Executed row entirely for a known reference-converter defect; in
    that case a `Q7_MISSING_EXECUTED_REPAIRS` entry must cite filing evidence.
    This function clones the Executed template row N times, one per named
    operational/economic buyer member, and emits an info flag
    `executed_atomized`.
    """
    members = Q7_EXECUTED_MEMBERS.get(slug)
    repair = Q7_MISSING_EXECUTED_REPAIRS.get(slug)
    if not members and not repair:
        return events

    executed_rows = [ev for ev in events if ev.get("bid_note") == "Executed"]
    synthesize = False
    if not executed_rows:
        if repair is None:
            raise RuntimeError(
                f"§Q7: {slug} has consortium Executed members but no xlsx "
                "Executed row and no Q7_MISSING_EXECUTED_REPAIRS entry"
            )
        validate_q7_missing_executed_repair(slug, repair)
        repair_members = list(repair["members"])
        if members is not None and members != repair_members:
            raise RuntimeError(
                f"§Q7: {slug} Q7_EXECUTED_MEMBERS does not match "
                "Q7_MISSING_EXECUTED_REPAIRS members"
            )
        members = repair_members
        template = _q7_missing_executed_template(slug, events, repair)
        synthetic = json.loads(json.dumps(template, default=str))
        synthetic["bid_note"] = "Executed"
        synthetic["bid_type"] = None
        synthetic["bid_date_precise"] = repair["executed_date"]
        synthetic["bid_date_rough"] = None
        for key in (
            "bid_value", "bid_value_pershare", "bid_value_lower", "bid_value_upper",
            "bid_value_unit", "exclusivity_days",
        ):
            synthetic[key] = None
        synthetic["additional_note"] = None
        synthetic["comments"] = None
        synthetic["_xlsx_row"] = (template.get("_xlsx_row") or 0) + 0.1
        synthetic["_alex_bidder_id"] = None
        synthetic["flags"] = list(template.get("flags") or []) + [{
            "code": "executed_synthesized_per_q7",
            "severity": "info",
            "reason": (
                f"§Q7: {slug} xlsx lacked an Executed row; synthesized from "
                "a filing-cited missing-Executed repair using template "
                f"bidder_alias={repair['template']['bidder_alias']!r} and "
                f"executed_date={repair['executed_date']}."
            ),
        }]
        executed_rows = [synthetic]
        synthesize = True

    if not members:
        raise RuntimeError(f"§Q7: {slug} has Executed repair but no member list")

    member_ids = _canonical_ids_for_members(events, members)
    out: list[dict[str, Any]] = []
    replaced = False
    for ev in events:
        if ev.get("bid_note") != "Executed":
            out.append(ev)
            continue

        replaced = True
        original_alias = ev.get("bidder_alias")
        for i, (member_name, cid) in enumerate(zip(members, member_ids), start=1):
            new_ev = json.loads(json.dumps(ev, default=str))
            new_ev["bidder_alias"] = member_name
            new_ev["bidder_name"] = cid
            new_ev["flags"] = list(ev.get("flags") or []) + [{
                "code": "executed_atomized",
                "severity": "info",
                "reason": (
                    f"§Q7 (per §E1+§E2.b 2026-04-27): xlsx Executed row "
                    f"alias={original_alias!r} atomized to member "
                    f"{i}/{len(members)} = {member_name!r}."
                ),
            }]
            out.append(new_ev)

    if synthesize and not replaced:
        original_alias = executed_rows[0].get("bidder_alias")
        for i, (member_name, cid) in enumerate(zip(members, member_ids), start=1):
            new_ev = json.loads(json.dumps(executed_rows[0], default=str))
            new_ev["bidder_alias"] = member_name
            new_ev["bidder_name"] = cid
            new_ev["flags"] = list(executed_rows[0].get("flags") or []) + [{
                "code": "executed_atomized",
                "severity": "info",
                "reason": (
                    f"§Q7 (per §E1+§E2.b 2026-04-27): synthesized Executed "
                    f"row alias={original_alias!r} atomized to member "
                    f"{i}/{len(members)} = {member_name!r}."
                ),
            }]
            out.append(new_ev)
    return out

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
    "Press Release": 1, "Target Sale Public": 1,
    "Bidder Sale": 1, "Activist Sale": 1,
    # Rank 2 — process start/restart
    "Target Sale": 2,
    "Terminated": 2, "Restarted": 2,
    # Rank 3 — advisor/IB changes
    "IB": 3, "IB Terminated": 3,
    # Rank 4 — bidder first-contact
    "Bidder Interest": 4,
    # Rank 5 — NDA + ConsortiumCA (Decision #4 — §I3 distinguishes Type A
    # vs Type B; converter does not synthesize ConsortiumCA from xlsx
    # NDA rows because Alex's coding doesn't preserve the CA-type
    # distinction. Vocabulary completeness only.)
    "NDA": 5,
    "ConsortiumCA": 5,
    # Rank 6 — informal bids (default for "Bid"; bumps to 7 for bid_type="formal")
    "Bid": 6,
    # Rank 8 — mid-round dropouts (DropSilent included for vocabulary
    # completeness; the converter does not synthesize DropSilent rows from
    # silent NDA signers — Alex's reference predates the §I1 policy and
    # stays as-is. The diff harness filters DropSilent from the AI side.)
    "Drop": 8, "DropSilent": 8,
    # Rank 9 — final-round deadlines
    "Final Round": 9,
    "Auction Closed": 9,
    # Rank 11 — signing
    "Executed": 11,
}

VALID_BID_NOTES = frozenset(A3_RANK)

BLANK_BID_NOTE_REPAIRS: dict[int, tuple[str, str]] = {
    6028: (
        "NDA",
        "xlsx row 6028 has a blank bid_note; the row identifies G&W's "
        "2016-04-13 confidentiality-agreement event",
    ),
}

EXCLUSIVITY_EVENT_RE = re.compile(r"^Exclusivity\s+(\d+)\s+days$", re.IGNORECASE)


def _a3_rank(ev: dict[str, Any]) -> int:
    """§A3 same-date rank. Bid rows (§C3) rank by bid_type:
    informal → 6, formal → 7."""
    bn = ev.get("bid_note") or ""
    if bn == "Final Round" and ev.get("final_round_announcement") is True:
        return 1
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
    "bidder_type_note": 19,
    "bid_value":        20,
    "bid_value_pershare": 21,
    "bid_value_lower":  22,
    "bid_value_upper":  23,
    "bid_value_unit":   24,
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
    all_cash       = _bool(pick("all_cash"))
    auction        = _bool(pick("Auction"))

    return {
        "TargetName":        pick("TargetName"),
        "Acquirer":          pick("Acquirer"),
        "DateAnnounced":     date_announced,
        "DateEffective":     date_effective,
        "auction":           auction,
        "all_cash":          all_cash,
        # Alex-absent fields (AI-only at extraction time).
        "target_legal_counsel":    None,
        "acquirer_legal_counsel":  None,
        # Populated below after bidder canonicalization.
        "bidder_registry": {},
        "deal_flags": [],
    }


# ---------------------------------------------------------------------------
# Bidder canonicalization (§E3)
# ---------------------------------------------------------------------------

def canonicalize_bidders(rows: list[RawRow]) -> tuple[dict[int, str], dict[str, Any]]:
    """Assign bidder_01, bidder_02, ... deterministically in first-appearance order.

    Returns:
      xlsx_row → canonical id ("" for rows with no bidder alias).
      registry: canonical id → {resolved_name, aliases_observed, first_appearance_row}
    """
    canonical: dict[int, str] = {}
    registry: dict[str, dict[str, Any]] = {}
    alias_to_id: dict[str, str] = {}
    next_idx = 1

    for r in rows:
        alias_raw = r.get("BidderName")
        if alias_raw is None:
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

def build_bidder_type(r: RawRow) -> str | None:
    """Return scalar bidder_type per `rules/bidders.md` §F1 (2026-04-27).

    Reads the three boolean columns from Alex's xlsx (bt_financial,
    bt_strategic, bt_mixed) plus the free-text `bidder_type_note`.
    Returns one of "s" / "f" / None.

    bt_nonUS is not loaded from the xlsx (removed from COL after the
    2026-04-27 bidder_type flatten). Geography and listing status are no
    longer recorded per Alex's 2026-04-27 directive; this function does
    not attempt to parse them from the note column.
    """
    fin   = _bool(r.get("bt_financial"))
    strat = _bool(r.get("bt_strategic"))
    mixed = _bool(r.get("bt_mixed"))
    note  = r.get("bidder_type_note")

    # Boolean-column path (Alex's 4-boolean schema).
    if mixed or (fin and strat):
        return None
    if fin:
        return "f"
    if strat:
        return "s"

    # Note-column fallback when boolean columns are blank but the note has
    # signal. Tokenize the note and match the F/S/mixed letters.
    if isinstance(note, str):
        normalized = re.sub(r"non[-\s]?us", "", note.strip().lower())
        tokens = re.findall(r"[a-z]+|\d+[a-z]+", normalized)
        has_financial = any(t in {"f", "financial"} or re.fullmatch(r"\d+f", t) for t in tokens)
        has_strategic = any(t in {"s", "strategic"} or re.fullmatch(r"\d+s", t) for t in tokens)
        has_mixed     = "mixed" in tokens
        if has_mixed or (has_financial and has_strategic):
            return None
        if has_financial:
            return "f"
        if has_strategic:
            return "s"

    return None


# ---------------------------------------------------------------------------
# Event-row assembly
# ---------------------------------------------------------------------------

def _convert_bid_note(r: RawRow) -> tuple[str | None, str | None, str | None]:
    """Map source-workbook bid-row labels to the current §C3 form.

    Returns `(bid_note, bid_type_inferred, source_label)`:

    - `bid_note`: the rulebook-canonical §C1 code. Bid rows always use `"Bid"`.
    - `bid_type_inferred`: `"informal"` / `"formal"` / `None` — the bid_type
      inferred from the source label (when the xlsx used one); `None` if the
      xlsx had a non-bid event code or a blank.
    - `source_label`: the original xlsx `bid_note` string when it contains
      bid-row meaning that must become `bid_type`; else `None`.

    Handles three cases:

    1. xlsx `bid_note` contains bid-row meaning → emit `"Bid"` + inferred
       `bid_type`, retaining the source label only inside this function.
    2. xlsx `bid_note` is blank / "NA" but xlsx `bid_type` is set (Alex's
       earlier convention) → emit `"Bid"` with the xlsx `bid_type`.
    3. xlsx `bid_note` is any other §C1 code (NDA, IB, etc.) → pass through.
    """
    note = r.get("bid_note")
    # Case 1: source-workbook bid-row label.
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
        if r.xlsx_row in BLANK_BID_NOTE_REPAIRS:
            repaired_note, _ = BLANK_BID_NOTE_REPAIRS[r.xlsx_row]
            return (repaired_note, None, None)
        return (None, None, None)

    # Case 3: non-bid §C1 event (NDA, IB, Drop, Executed, ...).
    return (note, None, None)


_DEFAULT_TAXONOMY_COLUMNS: dict[str, Any] = {
    "drop_initiator": None,
    "drop_reason_class": None,
    "final_round_announcement": None,
    "final_round_extension": None,
    "final_round_informal": None,
    "press_release_subject": None,
    "invited_to_formal_round": None,
    "submitted_formal_bid": None,
}

_SOURCE_TEXT_REPLACEMENTS = {
    "Final Round Ann": "final-round announcement",
    "Final Round Inf Ann": "informal final-round announcement",
    "Final Round Inf": "informal final-round event",
    "Final Round Ext Ann": "final-round extension announcement",
    "Final Round Ext": "final-round extension",
    "Bid Press Release": "bidder press release",
    "Sale Press Release": "sale press release",
    "DropBelowM": "target-initiated below-minimum drop",
    "DropBelowInf": "target-initiated never-advanced drop",
    "DropAtInf": "bidder-initiated drop",
    "DropTarget": "target-initiated drop",
    "Target Interest": "target-initiated bidder interest",
}


def _scrub_source_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    for old, new in _SOURCE_TEXT_REPLACEMENTS.items():
        value = value.replace(old, new)
    return value


def _apply_taxonomy_redesign(note: str | None) -> tuple[str | None, dict[str, Any], bool]:
    """Map source-workbook event labels into the current schema.

    Returns `(new_note, modifiers, target_initiated)`. The output JSON carries
    only the current `bid_note` plus structured modifiers.
    """
    modifiers = dict(_DEFAULT_TAXONOMY_COLUMNS)
    if note is None:
        return None, modifiers, False

    drop_map = {
        "Drop": ("unknown", None),
        "DropBelowM": ("target", "below_minimum"),
        "DropBelowInf": ("target", "never_advanced"),
        "DropAtInf": ("bidder", None),
        "DropTarget": ("target", "target_other"),
    }
    if note in drop_map:
        initiator, reason = drop_map[note]
        modifiers["drop_initiator"] = initiator
        modifiers["drop_reason_class"] = reason
        return "Drop", modifiers, False

    final_round_map = {
        "Final Round Ann": (True, False, False),
        "Final Round": (False, False, False),
        "Final Round Inf Ann": (True, False, True),
        "Final Round Inf": (False, False, True),
        "Final Round Ext Ann": (True, True, False),
        "Final Round Ext": (False, True, False),
        "Final Round Inf Ext Ann": (True, True, True),
        "Final Round Inf Ext": (False, True, True),
    }
    if note in final_round_map:
        announcement, extension, informal = final_round_map[note]
        modifiers["final_round_announcement"] = announcement
        modifiers["final_round_extension"] = extension
        modifiers["final_round_informal"] = informal
        return "Final Round", modifiers, False

    press_map = {
        "Bid Press Release": "bidder",
        "Sale Press Release": "sale",
    }
    if note in press_map:
        modifiers["press_release_subject"] = press_map[note]
        return "Press Release", modifiers, False

    if note == "Target Interest":
        return "Bidder Interest", modifiers, True

    return note, modifiers, False


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
    return _scrub_source_text(" | ".join(str(p) for p in parts)) if parts else None


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
    # §C3 reference conversion: normalize bid-row event type to "Bid" + bid_type.
    note, inferred_bid_type, source_label = _convert_bid_note(r)
    note, taxonomy_columns, target_initiated = _apply_taxonomy_redesign(note)
    bid_type = _bid_type_canon(r.get("bid_type")) or inferred_bid_type

    # §B2: bid_date_rough is populated IFF the date was inferred. When Alex's
    # xlsx gives an explicit ISO date in bid_date_precise, the workbook "rough"
    # mirror is a serialization artifact, not a semantic signal —
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

    flags: list[dict[str, Any]] = []

    # Per-row provenance: blank-bid_note repair (§Q-style narrow override
    # for xlsx rows where bid_note was simply blank in Alex's workbook).
    # Without this flag the repair would land silently — every other
    # converter override (Q1 delete, Q2 expand, Q3 renumber, ...) carries
    # a flag, this one shouldn't be the lone exception.
    if r.xlsx_row in BLANK_BID_NOTE_REPAIRS and r.get("bid_note") in (None, "", "nan"):
        _, repair_reason = BLANK_BID_NOTE_REPAIRS[r.xlsx_row]
        flags.append({
            "code": "bid_note_repaired_blank",
            "severity": "info",
            "reason": repair_reason,
        })

    # Revised-bid provenance: the xlsx distinguishes a bidder's subsequent
    # formal bid with a source label. In current §C3, both bids carry
    # bid_note='Bid' + bid_type='formal'; we annotate the revision so the
    # downstream can reconstruct ordering without a distinct bid_note.
    additional_note = _scrub_source_text(r.get("additional_note"))
    if target_initiated:
        marker = "target-initiated"
        if additional_note is None:
            additional_note = marker
        elif marker not in str(additional_note).lower():
            additional_note = f"{additional_note} | {marker}"
    if source_label == "Revised Bid":
        marker = "revised"
        if additional_note is None:
            additional_note = marker
        elif marker not in str(additional_note).lower():
            additional_note = f"{additional_note} | {marker}"

    row = {
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
        "consideration_components": None,
        **taxonomy_columns,
        "exclusivity_days":       None,
        "additional_note": additional_note,
        "comments":        _comments(r),
        "_xlsx_row":       r.xlsx_row,            # provenance only; strip at write
        "_alex_bidder_id": r.get("BidderID"),     # provenance only; strip at write
        "flags": flags,
    }
    # §G1+§G2 (2026-04-27): true range bids are unconditionally informal.
    # Auto-coerce source xlsx rows where Alex labeled a range "formal".
    lower = row.get("bid_value_lower")
    upper = row.get("bid_value_upper")
    try:
        lo_num = float(lower) if lower is not None else None
        hi_num = float(upper) if upper is not None else None
    except (TypeError, ValueError):
        lo_num = hi_num = None
    if (
        lo_num is not None and hi_num is not None and lo_num < hi_num
        and row.get("bid_type") not in (None, "informal")
    ):
        original = row["bid_type"]
        row["bid_type"] = "informal"
        row.setdefault("flags", []).append({
            "code": "range_forced_informal_per_g1",
            "severity": "info",
            "reason": (
                f"§G1+§G2 (2026-04-27): xlsx bid_type={original!r} on a true "
                f"range ({lower!r}..{upper!r}) forced to 'informal'."
            ),
        })
    return row


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
    """Apply §Q2 — expand Zep row 6390 into 5 atomized rows.

    Each of Party A..E is a structurally distinct bidder per §E1 (atomize
    aggregated rows). Without fresh canonical ids, all 5 inherit the
    template's `bidder_name` (e.g. `bidder_04`) and the bidder_registry
    treats them as one entity — this would cause the diff harness's
    NDA→Bid→Drop chain joins to false-positive on the 5-party slice. See
    module docstring §Q2 for rationale; matches the §Q5 medivation pattern
    and §Q7 petsmart/mac-gray atomization.
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
        # Allocate one fresh canonical id per atomized party. The set
        # of "already used" ids is the snapshot of the pre-expansion
        # event list — we must not collide with the template's id
        # either (since after the loop the template is dropped).
        fresh_cids = _next_canonical_ids(events, count=len(configs))
        for (alias, value_overrides), cid in zip(configs, fresh_cids):
            new_ev = json.loads(json.dumps(template, default=str))
            new_ev["bidder_alias"] = alias
            new_ev["bidder_name"] = cid
            for k, v in value_overrides.items():
                new_ev[k] = v
            new_ev["flags"] = list(template["flags"]) + [
                ZEP_ROW_6390_EXPANSION_FLAG,
                {"code": "bid_value_ambiguous_per_alex", "severity": "info",
                 "reason": f"{alias} bid value inferred from Alex's ambiguous note"},
            ]
            out.append(new_ev)
    return out


def apply_exclusivity_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop exclusivity event rows after moving days onto the bid row."""
    out: list[dict[str, Any]] = []
    for ev in events:
        note = ev.get("bid_note")
        match = EXCLUSIVITY_EVENT_RE.match(note) if isinstance(note, str) else None
        if match is None:
            out.append(ev)
            continue

        days = int(match.group(1))
        bidder_name = ev.get("bidder_name")
        bidder_alias = ev.get("bidder_alias")
        target = next(
            (
                prev
                for prev in reversed(out)
                if prev.get("bid_note") == "Bid"
                and (
                    (bidder_name is not None and prev.get("bidder_name") == bidder_name)
                    or (bidder_alias is not None and prev.get("bidder_alias") == bidder_alias)
                )
            ),
            None,
        )
        if target is None:
            raise ValueError(
                f"xlsx row {ev.get('_xlsx_row')}: cannot attach bid_note={note!r}; "
                "no preceding bid row for the same bidder"
            )

        existing = target.get("exclusivity_days")
        if existing is not None and existing != days:
            raise ValueError(
                f"xlsx row {ev.get('_xlsx_row')}: bid_note={note!r} conflicts with "
                f"existing exclusivity_days={existing!r} on xlsx row {target.get('_xlsx_row')}"
            )

        target["exclusivity_days"] = days
    return out


def validate_current_schema_events(events: list[dict[str, Any]]) -> None:
    """Fail loudly if stale event codes survived converter cleanup."""
    for ev in events:
        note = ev.get("bid_note")
        if note is None:
            raise ValueError(f"xlsx row {ev.get('_xlsx_row')}: bid_note is null after conversion")
        if note not in VALID_BID_NOTES:
            raise ValueError(
                f"xlsx row {ev.get('_xlsx_row')}: bid_note={note!r} is not in the "
                "current rules/events.md §C1 vocabulary"
            )


# §Q5 — Medivation: aggregated NDA row (xlsx 6065) + Drop row (xlsx 6075).
MEDIVATION_NDA_AGG_XLSX_ROW = 6065
MEDIVATION_DROP_AGG_XLSX_ROW = 6075
MEDIVATION_UNNAMED_PLACEHOLDER_ALIASES = ("Party A", "Party B")


def apply_q5_medivation(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply §Q5 — atomize Medivation's aggregated rows per universal §E1."""
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
    apply_q6_acquirer_rewrite(slug, deal)

    if slug == "saks":
        raw = apply_q1_saks(raw, deal)

    canonical, registry = canonicalize_bidders(raw)

    events = [build_event_row(r, canonical[r.xlsx_row]) for r in raw]

    if slug == "zep":
        events = apply_q2_zep(events)
    if slug == "medivation":
        events = apply_q5_medivation(events)
    events = apply_q7_executed_atomization(slug, events)
    events = apply_exclusivity_events(events)
    validate_current_schema_events(events)

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
                "first_appearance_row_index": ev["BidderID"],
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
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
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
