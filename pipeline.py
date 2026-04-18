"""pipeline.py — Python plumbing for the M&A extraction skill.

The Extractor and Adjudicator agents run as **Claude Code subagents** with
clean-slate contexts, administered by the orchestrating conversation. This
module provides the deterministic, non-LLM pieces only:

  - Filing loader (data/filings/{slug}/pages.json + manifest.json)
  - Vocabularies mirrored from rules/*.md (source of truth stays in markdown)
  - Python Validator that runs every invariant in rules/invariants.md
  - Output writers, state updaters, status classification

Orchestration flow (Claude Code drives, not Python):
  1. prompt = build_extractor_prompt(slug); spawn Extractor subagent
  2. raw_extraction = parse the subagent's JSON
  3. filing = load_filing(slug)
  4. result = validate(raw_extraction, filing)
  5. for soft flag in result.soft_flags: spawn Adjudicator subagent, annotate
  6. final = merge_flags(raw_extraction, result.row_flags, result.deal_flags)
  7. write_output(slug, final); append_flags_log(...); update_progress(...)

No Anthropic SDK import. No API keys. Python stays deterministic.
"""

from __future__ import annotations

import copy
import datetime as _dt
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "data" / "filings"
RULES_DIR = REPO_ROOT / "rules"
PROMPTS_DIR = REPO_ROOT / "prompts"
EXTRACTIONS_DIR = REPO_ROOT / "output" / "extractions"
STATE_DIR = REPO_ROOT / "state"
PROGRESS_PATH = STATE_DIR / "progress.json"
FLAGS_PATH = STATE_DIR / "flags.jsonl"

# ---------------------------------------------------------------------------
# Vocabularies — mirrors of rules/*.md
# ---------------------------------------------------------------------------
# These are the operational, machine-readable form of the rulebook
# vocabularies. The rulebook markdown is the source of truth; when those
# files change, update the mirrors here in the same commit.

# Mirror of rules/events.md §C1 — the §C3-migrated closed vocabulary.
# Bid rows all carry bid_note="Bid"; bid_type ("informal"/"formal") is the
# only distinguisher. The legacy labels "Inf" / "Formal Bid" / "Revised Bid"
# are deprecated and should never appear on a properly-built reference or a
# current AI extraction. scripts/build_reference.py migrates xlsx labels on
# ingestion; the extractor prompt instructs the subagent to emit §C3.
EVENT_VOCABULARY: frozenset[str] = frozenset({
    # Start-of-process
    "Bidder Interest", "Bidder Sale", "Target Interest", "Target Sale",
    "Target Sale Public", "Activist Sale",
    # Publicity
    "Bid Press Release", "Sale Press Release",
    # Advisors
    "IB", "IB Terminated",
    # Counterparty events
    "NDA", "Drop", "DropBelowM", "DropBelowInf", "DropAtInf", "DropTarget",
    # Bid rows — §C3 unified; bid_type disambiguates formal/informal
    "Bid",
    # Round structure (§K1)
    "Final Round Ann", "Final Round",
    "Final Round Inf Ann", "Final Round Inf",
    "Final Round Ext Ann", "Final Round Ext",
    "Final Round Inf Ext Ann", "Final Round Inf Ext",
    "Auction Closed",
    # Closing
    "Executed",
    # Prior-process
    "Terminated", "Restarted",
})

# Mirror of rules/bids.md §M3.
ROLE_VOCABULARY: frozenset[str] = frozenset({
    "bidder", "advisor_financial", "advisor_legal",
})

# Mirror of rules/invariants.md §P-S3 — the only legitimate phase enders.
PHASE_TERMINATORS: frozenset[str] = frozenset({
    "Executed", "Terminated", "Auction Closed",
})

# §P-S1 follow-up vocabulary: bid_notes that discharge the NDA→follow-up
# obligation. Covers bid submissions (§C3 unified "Bid"), every dropout code,
# Executed, and final-round bid-submission codes. Final-round "Ann" codes
# (announcements) are NOT follow-ups — they don't record bidder-specific
# activity.
BID_NOTE_FOLLOWUPS: frozenset[str] = frozenset({
    "Bid",
    "Drop", "DropBelowM", "DropBelowInf", "DropAtInf", "DropTarget",
    "Executed",
    "Final Round", "Final Round Inf",
    "Final Round Ext", "Final Round Inf Ext",
})

# Flag codes that legitimize a non-null bid_date_rough per §B2/§B3/§B4.
DATE_INFERENCE_FLAG_CODES: frozenset[str] = frozenset({
    "date_inferred_from_rough",
    "date_inferred_from_context",
    "date_range_collapsed",
})

# §A3 logical ordering rank table (lower rank = earlier within same date).
# Keys are bid_note values; for Bid rows specifically, informal bids rank 6
# and formal bids rank 7 — the comparator consults bid_type.
EVENT_RANK: dict[str, int] = {
    # Rank 1 — process announcements / public events
    "Bid Press Release": 1,
    "Sale Press Release": 1,
    "Target Sale Public": 1,
    "Final Round Ann": 1,
    "Final Round Inf Ann": 1,
    "Final Round Ext Ann": 1,
    "Final Round Inf Ext Ann": 1,
    "Bidder Sale": 1,
    "Activist Sale": 1,
    # Rank 2 — process start / restart
    "Target Sale": 2,
    "Target Interest": 2,
    "Terminated": 2,
    "Restarted": 2,
    # Rank 3 — advisor / IB events
    "IB": 3,
    "IB Terminated": 3,
    # Rank 4 — bidder first-contact
    "Bidder Interest": 4,
    # Rank 5 — NDAs
    "NDA": 5,
    # Rank 6/7 — bids (§C3 unified "Bid"; formal bumps to 7 via _rank())
    "Bid": 6,
    # Rank 8 — dropouts
    "Drop": 8,
    "DropBelowInf": 8,
    "DropAtInf": 8,
    "DropBelowM": 8,
    "DropTarget": 8,
    # Rank 9 — final-round deadlines / auction closed
    "Final Round": 9,
    "Final Round Inf": 9,
    "Final Round Ext": 9,
    "Final Round Inf Ext": 9,
    "Auction Closed": 9,
    # Rank 11 — closing
    "Executed": 11,
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Filing:
    slug: str
    pages: list[dict[str, Any]]
    manifest: dict[str, Any]

    @property
    def num_pages(self) -> int:
        return len(self.pages)

    def page_content(self, number: int) -> str | None:
        for p in self.pages:
            if p.get("number") == number:
                return p.get("content", "")
        return None

    def page_numbers(self) -> set[int]:
        return {p.get("number") for p in self.pages if "number" in p}


@dataclass
class ValidatorResult:
    row_flags: list[dict[str, Any]]
    deal_flags: list[dict[str, Any]]

    def _severity_counts(self) -> dict[str, int]:
        counts = {"hard": 0, "soft": 0, "info": 0}
        for f in self.row_flags + self.deal_flags:
            sev = f.get("severity", "hard")
            if sev in counts:
                counts[sev] += 1
        return counts

    @property
    def hard_count(self) -> int:
        return self._severity_counts()["hard"]

    @property
    def soft_count(self) -> int:
        return self._severity_counts()["soft"]

    @property
    def info_count(self) -> int:
        return self._severity_counts()["info"]

    @property
    def total_count(self) -> int:
        return len(self.row_flags) + len(self.deal_flags)

    def soft_flags(self) -> list[dict[str, Any]]:
        return [f for f in self.row_flags + self.deal_flags if f.get("severity") == "soft"]


# ---------------------------------------------------------------------------
# Filing loader
# ---------------------------------------------------------------------------


def load_filing(slug: str) -> Filing:
    deal_dir = DATA_DIR / slug
    if not deal_dir.exists():
        raise FileNotFoundError(f"no filing directory at {deal_dir}")
    pages_path = deal_dir / "pages.json"
    manifest_path = deal_dir / "manifest.json"
    for p in (pages_path, manifest_path):
        if not p.exists():
            raise FileNotFoundError(f"missing artifact: {p}")
    pages = json.loads(pages_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    return Filing(slug=slug, pages=pages, manifest=manifest)


# ---------------------------------------------------------------------------
# Extractor subagent prompt builder
# ---------------------------------------------------------------------------


def build_extractor_prompt(slug: str) -> str:
    """Return the prompt for a Claude Code Extractor subagent.

    The subagent is spawned in a fresh, clean-slate context with Read access.
    Instead of stuffing the filing into the prompt, we point it at the file
    paths — the subagent reads what it needs from disk, which keeps the
    parent conversation's context lean.
    """
    return f"""You are the Extractor in the M&A auction extraction pipeline. \
Run in a fresh context on a single deal and emit one JSON object conforming \
to rules/schema.md §R1. No prose outside the final JSON block.

Deal slug: **{slug}**

Read these files in full (absolute paths; use your Read tool):

  Operating procedure:
    {PROMPTS_DIR}/extract.md

  Rulebook (all resolved; if you see 🟥 OPEN anywhere, halt and emit the blocked form):
    {RULES_DIR}/schema.md      (output shape §R1, evidence §R3)
    {RULES_DIR}/events.md      (bid_note closed vocabulary §C1, 27 values)
    {RULES_DIR}/bidders.md     (canonical IDs §E3, bidder_type §F1)
    {RULES_DIR}/bids.md        (formal/informal §G1, skip rules §M)
    {RULES_DIR}/dates.md       (date mapping §B, BidderID sequence §A1–§A4)

  Filing (authoritative for every source_quote and source_page):
    {DATA_DIR}/{slug}/pages.json     (list of {{"number": int, "content": str, ...}})
    {DATA_DIR}/{slug}/manifest.json  (EDGAR metadata + deal-identity cross-check)

Non-negotiables:
  - Every event row MUST have source_quote (verbatim NFKC-substring of
    pages[source_page-1].content, ≤1000 chars) and source_page (integer
    matching the "number" field in pages.json). No un-cited rows ship.
  - bid_note ∈ the §C1 closed vocabulary. **Bid rows use §C3's unified
    convention**: bid_note="Bid" for every bid row (informal or formal),
    with bid_type="informal" or "formal" carrying the classification. Do
    NOT emit legacy labels "Inf" / "Formal Bid" / "Revised Bid" — those are
    deprecated by §C3 and will fail the validator's §P-R3 vocabulary check.
    For a bidder's second formal bid, emit a second row with bid_note="Bid"
    + bid_type="formal"; the BidderID chronology preserves the revision
    ordering. If an event truly doesn't fit any §C1 code, emit the closest
    match and attach flag {{"code": "unknown_bid_note", "severity": "hard",
    "reason": "..."}}.
  - bidder_name is the canonical bidder_NN (§E3). bidder_alias is the
    filing's verbatim label on this row. bidder_registry in the deal object
    maps every bidder_NN → {{resolved_name, aliases_observed,
    first_appearance_row_index}}.
  - BidderID is a strict 1..N sequence in the §A2/§A3 ordering (chronological
    primary; logical rank for same-date ties). No decimals, no gaps.
  - Informal-vs-formal (bid_type) follows §G1 triggers/fallbacks. Every
    non-null bid_type needs either a formal/informal trigger phrase in the
    source_quote OR a bid_type_inference_note per §G2. Ambiguous →
    bid_type: null + hard flag informal_vs_formal_ambiguous.
  - Apply the skip rules in §M1–§M4. Unsolicited letters with no NDA, no
    price, no bid intent are dropped. Legal-advisor NDAs get role =
    "advisor_legal" (not skipped, but not counted toward auction threshold).

Output contract:
  Your FINAL message (and nothing else outside it) is a single fenced block:

    ```json
    {{"deal": {{ ... }}, "events": [ ... ]}}
    ```

  If a rule is 🟥 OPEN, emit instead:

    ```json
    {{"status": "blocked_by_open_rule", "open_rules": ["rules/xxx.md §Y"]}}
    ```

  Do not wrap the JSON in explanation. Do not emit multiple JSON blocks.
"""


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


def validate(raw_extraction: dict[str, Any], filing: Filing) -> ValidatorResult:
    """Run every invariant in rules/invariants.md. Returns row-level and
    deal-level flags; caller merges them into the extraction and writes out.
    """
    row_flags: list[dict[str, Any]] = []
    deal_flags: list[dict[str, Any]] = []

    deal = raw_extraction.get("deal") or {}
    events = raw_extraction.get("events") or []

    # §P-R1 — events array non-empty
    if not events:
        deal_flags.append({
            "code": "empty_events_array",
            "severity": "hard",
            "reason": "events[] is empty; every in-scope deal has at least an Executed row",
            "deal_level": True,
        })
        return ValidatorResult(row_flags=row_flags, deal_flags=deal_flags)

    # Row-level invariants.
    row_flags.extend(_invariant_p_r2(events, filing))
    row_flags.extend(_invariant_p_r3(events))
    row_flags.extend(_invariant_p_r4(events))
    row_flags.extend(_invariant_p_r5(events, deal))
    row_flags.extend(_invariant_p_d1(events))
    row_flags.extend(_invariant_p_d2(events))

    # §P-D3 returns a mix (structural are deal-level; ordering violations are
    # row-level). Route by presence of row_index.
    for f in _invariant_p_d3(events):
        (row_flags if "row_index" in f else deal_flags).append(f)

    row_flags.extend(_invariant_p_s1(events))

    # Deal-level semantic invariants.
    deal_flags.extend(_invariant_p_s2(deal, events))
    deal_flags.extend(_invariant_p_s3(events))
    deal_flags.extend(_invariant_p_s4(events))

    return ValidatorResult(row_flags=row_flags, deal_flags=deal_flags)


def _nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s)


def _invariant_p_r2(events: list[dict], filing: Filing) -> list[dict]:
    """§P-R2 — every row has source_quote and source_page; quote is an
    NFKC-substring of pages[source_page-1].content, ≤ 1000 chars."""
    flags: list[dict[str, Any]] = []
    valid_pages = filing.page_numbers()
    for i, ev in enumerate(events):
        quote = ev.get("source_quote")
        page = ev.get("source_page")

        if quote in (None, "", []):
            flags.append({
                "row_index": i, "code": "missing_evidence", "severity": "hard",
                "reason": "source_quote absent or empty",
            })
            continue
        if page in (None, "", []):
            flags.append({
                "row_index": i, "code": "missing_evidence", "severity": "hard",
                "reason": "source_page absent or empty",
            })
            continue

        # Multi-quote form (§R3) — both lists, equal length.
        if isinstance(quote, list) or isinstance(page, list):
            if not (isinstance(quote, list) and isinstance(page, list)):
                flags.append({
                    "row_index": i, "code": "source_quote_page_mismatch", "severity": "hard",
                    "reason": "multi-quote form requires both source_quote and source_page as lists",
                })
                continue
            if len(quote) != len(page):
                flags.append({
                    "row_index": i, "code": "source_quote_page_mismatch", "severity": "hard",
                    "reason": f"list-length mismatch: {len(quote)} quotes vs {len(page)} pages",
                })
                continue
            pairs = list(zip(quote, page))
        else:
            pairs = [(quote, page)]

        for q, p in pairs:
            if not isinstance(q, str):
                flags.append({
                    "row_index": i, "code": "missing_evidence", "severity": "hard",
                    "reason": f"source_quote element must be str; got {type(q).__name__}",
                })
                continue
            if not isinstance(p, int):
                flags.append({
                    "row_index": i, "code": "missing_evidence", "severity": "hard",
                    "reason": f"source_page element must be int; got {type(p).__name__}",
                })
                continue
            if len(q) > 1000:
                flags.append({
                    "row_index": i, "code": "source_quote_too_long", "severity": "hard",
                    "reason": f"source_quote has {len(q)} chars; cap is 1000",
                })
            if p not in valid_pages:
                flags.append({
                    "row_index": i, "code": "source_quote_not_in_page", "severity": "hard",
                    "reason": f"source_page={p} is not a valid page number for {filing.slug} (range: {min(valid_pages)}..{max(valid_pages)})",
                })
                continue
            page_content = filing.page_content(p) or ""
            if _nfkc(q).strip() not in _nfkc(page_content):
                excerpt = q[:120] + ("..." if len(q) > 120 else "")
                flags.append({
                    "row_index": i, "code": "source_quote_not_in_page", "severity": "hard",
                    "reason": f"NFKC-normalized source_quote not a substring of pages[{p}].content; excerpt: {excerpt!r}",
                })
    return flags


def _invariant_p_r3(events: list[dict]) -> list[dict]:
    """§P-R3 — bid_note ∈ §C1 closed vocabulary (or null on bid rows)."""
    flags: list[dict[str, Any]] = []
    for i, ev in enumerate(events):
        bn = ev.get("bid_note")
        if bn is None or bn in EVENT_VOCABULARY:
            continue
        flags.append({
            "row_index": i, "code": "invalid_event_type", "severity": "hard",
            "reason": f"bid_note={bn!r} not in §C1 closed vocabulary",
        })
    return flags


def _invariant_p_r4(events: list[dict]) -> list[dict]:
    """§P-R4 — role ∈ {bidder, advisor_financial, advisor_legal}."""
    flags: list[dict[str, Any]] = []
    for i, ev in enumerate(events):
        role = ev.get("role", "bidder")
        if role in ROLE_VOCABULARY:
            continue
        flags.append({
            "row_index": i, "code": "invalid_role", "severity": "hard",
            "reason": f"role={role!r} not in {{bidder, advisor_financial, advisor_legal}}",
        })
    return flags


def _invariant_p_r5(events: list[dict], deal: dict) -> list[dict]:
    """§P-R5 — every non-null bidder_name resolves in deal.bidder_registry."""
    flags: list[dict[str, Any]] = []
    registry = (deal.get("bidder_registry") or {}) if deal else {}
    for i, ev in enumerate(events):
        name = ev.get("bidder_name")
        if name is None:
            continue
        if name not in registry:
            flags.append({
                "row_index": i, "code": "bidder_name_unregistered", "severity": "hard",
                "reason": f"bidder_name={name!r} not a key of deal.bidder_registry",
            })
    return flags


_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _invariant_p_d1(events: list[dict]) -> list[dict]:
    """§P-D1 — bid_date_precise is ISO YYYY-MM-DD or null."""
    flags: list[dict[str, Any]] = []
    for i, ev in enumerate(events):
        d = ev.get("bid_date_precise")
        if d is None:
            continue
        if not (isinstance(d, str) and _ISO_DATE.match(d)):
            flags.append({
                "row_index": i, "code": "invalid_date_format", "severity": "hard",
                "reason": f"bid_date_precise={d!r} not ISO YYYY-MM-DD",
            })
    return flags


def _invariant_p_d2(events: list[dict]) -> list[dict]:
    """§P-D2 — bid_date_rough ≠ null IFF the row carries a date-inference
    flag (date_inferred_from_rough / date_inferred_from_context /
    date_range_collapsed). Tolerates the legacy-fixture case where
    bid_date_rough redundantly mirrors bid_date_precise (e.g.,
    "2016-04-13 00:00:00") because that's what build_reference.py emits
    for Alex's workbook parity — not an AI defect."""
    flags: list[dict[str, Any]] = []
    for i, ev in enumerate(events):
        rough = ev.get("bid_date_rough")
        precise = ev.get("bid_date_precise")
        row_flag_codes = {f.get("code") for f in (ev.get("flags") or []) if isinstance(f, dict)}
        has_inference = bool(row_flag_codes & DATE_INFERENCE_FLAG_CODES)
        rough_present = rough not in (None, "", [])

        if rough_present and not has_inference:
            # Legacy-fixture tolerance: rough is a direct mirror of precise.
            if isinstance(rough, str) and isinstance(precise, str) and rough.startswith(precise):
                continue
            flags.append({
                "row_index": i, "code": "rough_date_mismatch_inference", "severity": "hard",
                "reason": f"bid_date_rough={rough!r} populated without a date-inference flag",
            })
        elif has_inference and not rough_present:
            found = sorted(row_flag_codes & DATE_INFERENCE_FLAG_CODES)
            flags.append({
                "row_index": i, "code": "rough_date_mismatch_inference", "severity": "hard",
                "reason": f"date-inference flag(s) {found} present but bid_date_rough is null",
            })
    return flags


def _rank(bid_note: str | None, bid_type: str | None = None) -> int:
    """§A3 same-date logical rank. Formal bids bump to 7."""
    if bid_note is None:
        return 99
    r = EVENT_RANK.get(bid_note, 99)
    if bid_note == "Bid" and bid_type == "formal":
        return 7
    return r


def _invariant_p_d3(events: list[dict]) -> list[dict]:
    """§P-D3 — BidderID structural + chronological integrity (§A4 six rules)."""
    flags: list[dict[str, Any]] = []
    if not events:
        return flags
    ids = [ev.get("BidderID") for ev in events]

    # Structural block: must be ints, start at 1, strict monotone, unique, gap-free.
    if not all(isinstance(x, int) for x in ids):
        flags.append({
            "code": "bidder_id_structural_error", "severity": "hard",
            "reason": f"BidderID values must all be ints; got types {[type(x).__name__ for x in ids]}",
            "deal_level": True,
        })
        # Can't run the numeric checks; return early.
        return flags
    if ids[0] != 1:
        flags.append({
            "code": "bidder_id_structural_error", "severity": "hard",
            "reason": f"BidderID must start at 1; first row has BidderID={ids[0]}",
            "deal_level": True,
        })
    if any(ids[k] >= ids[k + 1] for k in range(len(ids) - 1)):
        flags.append({
            "code": "bidder_id_structural_error", "severity": "hard",
            "reason": "BidderID not strictly increasing across rows",
            "deal_level": True,
        })
    if len(set(ids)) != len(ids):
        dupes = sorted(x for x in set(ids) if ids.count(x) > 1)
        flags.append({
            "code": "bidder_id_structural_error", "severity": "hard",
            "reason": f"BidderID duplicates: {dupes}",
            "deal_level": True,
        })
    if max(ids) != len(ids):
        flags.append({
            "code": "bidder_id_structural_error", "severity": "hard",
            "reason": f"BidderID has gaps: max={max(ids)} but len(events)={len(ids)}",
            "deal_level": True,
        })

    # Rule 5 — date monotonicity for non-null dates.
    dates = [ev.get("bid_date_precise") for ev in events]
    for k in range(len(events) - 1):
        d_a, d_b = dates[k], dates[k + 1]
        if d_a and d_b and d_a > d_b:
            flags.append({
                "row_index": k + 1, "code": "bidder_id_date_order_violation", "severity": "hard",
                "reason": f"row {k} date {d_a} precedes row {k + 1} date {d_b}",
            })

    # Rule 6 — same-date §A3 rank-monotonicity.
    for k in range(len(events) - 1):
        d_a, d_b = dates[k], dates[k + 1]
        if d_a and d_b and d_a == d_b:
            ev_a, ev_b = events[k], events[k + 1]
            rank_a = _rank(ev_a.get("bid_note"), ev_a.get("bid_type"))
            rank_b = _rank(ev_b.get("bid_note"), ev_b.get("bid_type"))
            if rank_a > rank_b:
                flags.append({
                    "row_index": k + 1, "code": "bidder_id_same_date_rank_violation", "severity": "hard",
                    "reason": (
                        f"same date {d_a}: row {k} rank {rank_a} "
                        f"(bid_note={ev_a.get('bid_note')}, bid_type={ev_a.get('bid_type')}) "
                        f"after row {k + 1} rank {rank_b} "
                        f"(bid_note={ev_b.get('bid_note')}, bid_type={ev_b.get('bid_type')})"
                    ),
                })

    return flags


def _invariant_p_s1(events: list[dict]) -> list[dict]:
    """§P-S1 (SOFT) — every NDA row (role=bidder, phase ≥ 1) has a later
    follow-up event (bid, drop, executed) for the same bidder_name."""
    flags: list[dict[str, Any]] = []
    by_name: dict[str, list[tuple[int, dict]]] = {}
    for i, ev in enumerate(events):
        name = ev.get("bidder_name")
        if name is not None:
            by_name.setdefault(name, []).append((i, ev))

    for i, ev in enumerate(events):
        if ev.get("bid_note") != "NDA":
            continue
        if ev.get("role", "bidder") != "bidder":
            continue
        phase = ev.get("process_phase")
        if phase is not None and phase < 1:
            continue  # stale prior NDA — excluded per §L1
        name = ev.get("bidder_name")
        if name is None:
            continue  # anonymous NDA — cannot trace follow-up
        later = [(j, e) for (j, e) in by_name.get(name, []) if j > i]
        has_followup = any(e.get("bid_note") in BID_NOTE_FOLLOWUPS for _, e in later)
        if not has_followup:
            flags.append({
                "row_index": i, "code": "nda_without_bid_or_drop", "severity": "soft",
                "reason": f"bidder_name={name!r} signed NDA at row {i} but no follow-up (bid/drop/executed) was extracted",
            })
    return flags


def _invariant_p_s2(deal: dict, events: list[dict]) -> list[dict]:
    """§P-S2 — deal.auction == (NDA count with role=bidder, phase≥1 ≥ 2)."""
    nda_count = sum(
        1 for ev in events
        if ev.get("bid_note") == "NDA"
        and ev.get("role", "bidder") == "bidder"
        and (ev.get("process_phase") is None or ev.get("process_phase") >= 1)
    )
    expected = nda_count >= 2
    actual = bool((deal or {}).get("auction"))
    if expected != actual:
        return [{
            "code": "auction_flag_inconsistent", "severity": "hard",
            "reason": f"deal.auction={actual} but classifier counts {nda_count} qualifying NDAs (expects {expected})",
            "deal_level": True,
        }]
    return []


def _invariant_p_s3(events: list[dict]) -> list[dict]:
    """§P-S3 — each process_phase's chronologically last event is in
    {Executed, Terminated, Auction Closed}.

    Events are assumed to already be sorted by (bid_date_precise, §A3 rank,
    narrative order) per §A2/§A3 — that's the BidderID sequence. Within a
    phase, the last row in that order IS the chronologically-latest event.
    Do NOT use `max(... key=bid_date_precise)` — Python's max returns the
    FIRST element tied on the max date, which misidentifies same-date
    blocks (e.g., Medivation's 8/20 cluster of Formal Bid → Drops → Executed:
    max-by-date returns Formal Bid; §A3 says Executed is last).
    """
    flags: list[dict[str, Any]] = []
    by_phase: dict[int, list[dict]] = {}
    for ev in events:
        phase = ev.get("process_phase")
        if phase is None:
            phase = 1  # §L2 default for deals with no prior/restart
        by_phase.setdefault(phase, []).append(ev)
    for phase, rows in by_phase.items():
        # Trust the caller's §A2/§A3 ordering; take the last row in that order.
        last_row = rows[-1]
        if last_row.get("bid_note") not in PHASE_TERMINATORS:
            flags.append({
                "code": "phase_termination_missing", "severity": "hard",
                "reason": f"process_phase={phase}: last event bid_note={last_row.get('bid_note')!r} not in {{Executed, Terminated, Auction Closed}}",
                "deal_level": True,
            })
    return flags


def _invariant_p_s4(events: list[dict]) -> list[dict]:
    """§P-S4 — exactly one Executed row, in the max phase."""
    flags: list[dict[str, Any]] = []
    executed = [(i, ev) for i, ev in enumerate(events) if ev.get("bid_note") == "Executed"]
    if not executed:
        flags.append({
            "code": "no_executed_row", "severity": "hard",
            "reason": "no bid_note=Executed row; every in-scope deal closed and must have one",
            "deal_level": True,
        })
        return flags
    if len(executed) > 1:
        flags.append({
            "code": "multiple_executed_rows", "severity": "hard",
            "reason": f"{len(executed)} Executed rows; exactly one required",
            "deal_level": True,
        })
        return flags
    _, ex_ev = executed[0]
    ex_phase = ex_ev.get("process_phase") if ex_ev.get("process_phase") is not None else 1
    max_phase = max(
        (ev.get("process_phase") if ev.get("process_phase") is not None else 1)
        for ev in events
    )
    if ex_phase != max_phase:
        flags.append({
            "code": "executed_wrong_phase", "severity": "hard",
            "reason": f"Executed in process_phase={ex_phase}, but max phase is {max_phase}",
            "deal_level": True,
        })
    return flags


# ---------------------------------------------------------------------------
# Flag merging, status classification, writers
# ---------------------------------------------------------------------------


def merge_flags(
    raw_extraction: dict[str, Any],
    row_flags: list[dict[str, Any]],
    deal_flags: list[dict[str, Any]],
) -> dict[str, Any]:
    """Stamp validator flags into a deep-copy of the raw extraction.

    Row-level flags land in events[row_index].flags. Deal-level flags land
    in deal.deal_flags. The row_index and deal_level routing keys are
    stripped before embedding (they're orchestration metadata, not schema).
    """
    final = copy.deepcopy(raw_extraction)
    events = final.setdefault("events", [])
    deal = final.setdefault("deal", {})

    for flag in row_flags:
        i = flag.get("row_index")
        if i is None or i < 0 or i >= len(events):
            # Misplaced row flag — demote to deal-level so it isn't silently dropped.
            deal.setdefault("deal_flags", []).append({
                **{k: v for k, v in flag.items() if k not in ("row_index", "deal_level")},
                "reason": f"[misplaced row_index={i}] {flag.get('reason', '')}",
            })
            continue
        event_flags = events[i].setdefault("flags", [])
        event_flags.append({
            k: v for k, v in flag.items() if k not in ("row_index", "deal_level")
        })

    deal_flag_list = deal.setdefault("deal_flags", [])
    for flag in deal_flags:
        deal_flag_list.append({
            k: v for k, v in flag.items() if k not in ("row_index", "deal_level")
        })

    return final


def summarize(result: ValidatorResult) -> tuple[str, int, str]:
    """Return (status, flag_count, notes) per the §Status taxonomy.

    hard > 0 → "validated" (blocks advancement, human review required)
    only soft/info → "passed"
    zero flags → "passed_clean"
    """
    hard = result.hard_count
    soft = result.soft_count
    info = result.info_count
    if hard > 0:
        status = "validated"
    elif soft > 0:
        status = "passed"
    else:
        status = "passed_clean"
    flag_count = result.total_count
    notes = f"hard={hard} soft={soft} info={info}"
    return status, flag_count, notes


def write_output(slug: str, final_extraction: dict[str, Any]) -> Path:
    EXTRACTIONS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EXTRACTIONS_DIR / f"{slug}.json"
    out_path.write_text(json.dumps(final_extraction, indent=2, default=str) + "\n")
    return out_path


def append_flags_log(
    slug: str,
    row_flags: list[dict[str, Any]],
    deal_flags: list[dict[str, Any]],
) -> int:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    now = _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")
    lines: list[str] = []
    for f in row_flags:
        entry = {"deal": slug, "logged_at": now, **f}
        lines.append(json.dumps(entry, default=str))
    for f in deal_flags:
        entry = {"deal": slug, "logged_at": now, **f}
        lines.append(json.dumps(entry, default=str))
    if lines:
        with FLAGS_PATH.open("a") as fh:
            fh.write("\n".join(lines) + "\n")
    return len(lines)


def update_progress(slug: str, status: str, flag_count: int, notes: str) -> None:
    if not PROGRESS_PATH.exists():
        raise FileNotFoundError(f"{PROGRESS_PATH} does not exist; run scripts/build_seeds.py first")
    state = json.loads(PROGRESS_PATH.read_text())
    deals = state.setdefault("deals", {})
    if slug not in deals:
        raise KeyError(f"slug={slug} not in state/progress.json")
    now = _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")
    deals[slug].update({
        "status": status,
        "flag_count": flag_count,
        "last_run": now,
        "notes": notes,
    })
    state["updated"] = now
    PROGRESS_PATH.write_text(json.dumps(state, indent=2, sort_keys=False) + "\n")


# ---------------------------------------------------------------------------
# Convenience: end-to-end finalize (used by run.py and the orchestrator).
# ---------------------------------------------------------------------------


@dataclass
class PipelineResult:
    status: str
    flag_count: int
    notes: str
    output_path: Path
    validator: ValidatorResult


def finalize(
    slug: str,
    raw_extraction: dict[str, Any],
    filing: Filing | None = None,
) -> PipelineResult:
    """Run Python validator + merge flags + write output + update state.

    Does NOT spawn adjudicator subagents — that's the orchestrator's job,
    performed BEFORE calling this function. If the caller has adjudicated
    soft flags, they should mutate raw_extraction['events'][i]['flags']
    and/or raw_extraction['deal']['deal_flags'] with adjudicator verdicts
    before passing raw_extraction in.
    """
    if filing is None:
        filing = load_filing(slug)
    result = validate(raw_extraction, filing)
    final = merge_flags(raw_extraction, result.row_flags, result.deal_flags)
    out_path = write_output(slug, final)
    append_flags_log(slug, result.row_flags, result.deal_flags)
    status, flag_count, notes = summarize(result)
    update_progress(slug, status, flag_count, notes)
    return PipelineResult(
        status=status,
        flag_count=flag_count,
        notes=notes,
        output_path=out_path,
        validator=result,
    )
