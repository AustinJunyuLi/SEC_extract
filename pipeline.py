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
  5. for soft flag in result.row_flags + result.deal_flags (severity=="soft"):
         spawn Adjudicator subagent, annotate
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

# §G1 trigger phrases. Substring match, case-insensitive, on source_quote.
# MUST stay in sync with rules/bids.md §G1 formal/informal trigger tables.
FORMAL_TRIGGERS: tuple[str, ...] = (
    "binding offer", "binding proposal", "binding bid",
    "executed commitment letter", "financing commitment",
    "fully financed", "no financing contingency",
    "definitive agreement submitted", "draft merger agreement",
    "final bid", "best and final",
    "markup of the merger agreement",
    "process letter",
)
INFORMAL_TRIGGERS: tuple[str, ...] = (
    "non-binding indication", "preliminary indication",
    "expression of interest",
    "indicative offer", "indicative proposal",
    "subject to due diligence",
    "preliminary proposal",
)
ALL_G1_TRIGGERS: tuple[str, ...] = FORMAL_TRIGGERS + INFORMAL_TRIGGERS


def _row_flag_codes(ev: dict) -> set[str]:
    """Return the set of flag codes attached to a row, guarding against
    non-dict entries that may slip through LLM output."""
    return {f.get("code") for f in (ev.get("flags") or []) if isinstance(f, dict)}

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
    return Filing(slug=slug, pages=pages)


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

Everything in `prompts/extract.md` and `rules/*.md` is binding. Do not
paraphrase, override, or reinterpret — follow the rulebook as written. If
any rule is 🟥 OPEN, halt and emit the blocked form (see below).

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
    row_flags.extend(_invariant_p_d5(events))
    row_flags.extend(_invariant_p_d6(events))
    row_flags.extend(_invariant_p_g2(events))

    # §P-D3 returns a mix (structural are deal-level; ordering violations are
    # row-level). Route by presence of row_index.
    for f in _invariant_p_d3(events):
        (row_flags if "row_index" in f else deal_flags).append(f)

    row_flags.extend(_invariant_p_s1(events))

    # Deal-level semantic invariants.
    deal_flags.extend(_invariant_p_s2(deal, events))
    deal_flags.extend(_invariant_p_s3(deal, events))
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


def _invariant_p_d5(events: list[dict]) -> list[dict]:
    """§P-D5 — every Drop-family row's bidder has a prior engagement row
    (NDA, Bidder Interest, IB, or prior Drop) in the same process_phase.

    Closes the dangling-drop gap where an AI emits a Drop row for a bidder
    that was never shown engaging with the process (no NDA, no expression
    of interest, no IB kickoff). Matches the full Drop family via string
    prefix: `{Drop, DropTarget, DropBelowInf, DropAtInf, DropBelowFormal,
    DropAtFormal, Dropped}`. Existence-only check via set membership over
    per-(phase, bidder) engagement rows: canonicalization (§A2/§A3) has
    already ordered events, so "earlier row" reduces to "any engagement
    row for this (name, phase)" in practice. The prior-Drop carve-out
    covers §I2 re-engagement edge cases where an extractor emits Drop→Drop
    without an intervening NDA.

    Skips:
      - Unnamed (bidder_name=null) Drop rows — §E3 placeholders are not
        bidder-bound.
      - §M4 stale-prior phase 0 — Drop rows in aborted prior processes do
        not require a prior engagement row in this deal.
      - Any row for the same (bidder_name, phase) carries
        `unsolicited_first_contact` (§D1.a) — the bidder approached
        unsolicited, made a concrete bid, and withdrew without ever
        signing an NDA; the Drop row IS the withdrawal. Mirrors §P-D6's
        §D1.a exemption on the tail-end of the lifecycle.
    """
    flags: list[dict[str, Any]] = []
    # Build engagement index by (bidder_name, phase). Engagement = NDA,
    # Bidder Interest, IB, or any Drop (to cover §I2 re-engagement chains
    # where a second NDA is missing between two Drops). Track row index
    # so a Drop row cannot satisfy itself as the "engagement" witness.
    engagement_notes = {"NDA", "Bidder Interest", "IB"}
    # Map (name, phase) -> set of row indices contributing engagement.
    engagement_rows: dict[tuple[str, int], set[int]] = {}
    # Map (name, phase) -> True if any row carries unsolicited_first_contact,
    # so the §D1.a exemption propagates from the Bid row to the Drop row.
    unsolicited_keys: set[tuple[str, int]] = set()
    for j, ev in enumerate(events):
        name = ev.get("bidder_name")
        if not name:
            continue
        phase = ev.get("process_phase")
        if phase is None:
            phase = 1
        if "unsolicited_first_contact" in _row_flag_codes(ev):
            unsolicited_keys.add((name, phase))
        note = ev.get("bid_note", "") or ""
        if note not in engagement_notes and not note.startswith("Drop"):
            continue
        engagement_rows.setdefault((name, phase), set()).add(j)

    for i, ev in enumerate(events):
        note = ev.get("bid_note", "") or ""
        if not note.startswith("Drop"):
            continue
        name = ev.get("bidder_name")
        if not name:
            continue  # unnamed placeholder — skip
        phase = ev.get("process_phase")
        if phase is None:
            phase = 1
        if phase < 1:
            continue  # §M4 stale-prior phase 0 — skip
        if (name, phase) in unsolicited_keys:
            continue  # §D1.a — bidder approached unsolicited and withdrew
        witnesses = engagement_rows.get((name, phase), set()) - {i}
        if not witnesses:
            flags.append({
                "row_index": i, "code": "drop_without_prior_engagement", "severity": "hard",
                "reason": (
                    f"§P-D5: Drop row for bidder_name={name!r} in phase={phase} "
                    f"has no prior NDA/Bidder Interest/IB row. If this is an "
                    f"extractor error, rerun. If the filing genuinely shows a "
                    f"drop without prior engagement, investigate."
                ),
            })
    return flags


def _invariant_p_d6(events: list[dict]) -> list[dict]:
    """§P-D6 — every named-Bid row's bidder has an NDA row somewhere in the
    same process_phase.

    Closes the retroactive-naming gap where an AI emits unnamed NDA
    placeholders that are later not linked to named Bid rows (Providence
    Party D/E/F case). Existence-only check, not ordering: canonicalization
    (§A2/§A3) already enforces chronological order, and §D1 permits an
    unsolicited first-contact Bid to precede the same bidder's later NDA.

    Skips:
      - Unnamed (bidder_name=null) Bid rows — §E3 placeholders are
        count-bound, not NDA-bound.
      - §M4 stale-prior phase 0 — Bid rows emitted against aborted prior
        processes do not require an NDA.
      - Rows carrying `unsolicited_first_contact` flag (§D1.a, Class B,
        iter-4) — the bidder never signs an NDA in this deal; §D1 itself
        authorizes the NDA-less Bid row.

    Iter-5 removed the `pre_nda_informal_bid` exemption (Class D). §P-D6
    is existence-only, not ordering — §C4's pre-NDA informal-bid pattern
    has the bidder signing an NDA LATER in the same phase, so the NDA
    does exist. The §C4 flag remains (documents the pre-NDA timing), but
    no validator carve-out is needed.
    """
    flags: list[dict[str, Any]] = []
    # Build NDA index by (bidder_name, phase).
    nda_keys: set[tuple[str, int]] = set()
    for ev in events:
        if ev.get("bid_note") != "NDA":
            continue
        name = ev.get("bidder_name")
        if not name:
            continue
        phase = ev.get("process_phase")
        if phase is None:
            phase = 1
        nda_keys.add((name, phase))

    for i, ev in enumerate(events):
        if ev.get("bid_note") != "Bid":
            continue
        name = ev.get("bidder_name")
        if not name:
            continue  # unnamed §E3 placeholder — skip
        phase = ev.get("process_phase")
        if phase is None:
            phase = 1
        if phase < 1:
            continue  # §M4 stale-prior phase 0 — skip
        # Only §D1.a exempts from §P-D6; §C4 is documentation-only.
        if "unsolicited_first_contact" in _row_flag_codes(ev):
            continue
        if (name, phase) not in nda_keys:
            flags.append({
                "row_index": i, "code": "bid_without_preceding_nda", "severity": "hard",
                "reason": (
                    f"§P-D6: Bid row for bidder_name={name!r} in phase={phase} "
                    f"has no NDA row under the same bidder_name in that phase. "
                    f"If this bidder's NDA was emitted as an unnamed §E3 placeholder, "
                    f"the extractor should have attached `unnamed_nda_promotion` on this "
                    f"Bid row to promote the placeholder at pipeline-finalize time. "
                    f"If this is a §D1 unsolicited first-contact where the bidder never "
                    f"signs an NDA, attach the `unsolicited_first_contact` flag (§D1.a) "
                    f"to exempt this row."
                ),
            })
    return flags


def _invariant_p_d2(events: list[dict]) -> list[dict]:
    """§P-D2 — bid_date_rough ≠ null IFF the row carries a date-inference
    flag (date_inferred_from_rough / date_inferred_from_context /
    date_range_collapsed). Strict XOR; no legacy-fixture carve-out."""
    flags: list[dict[str, Any]] = []
    for i, ev in enumerate(events):
        rough = ev.get("bid_date_rough")
        row_flag_codes = _row_flag_codes(ev)
        has_inference = bool(row_flag_codes & DATE_INFERENCE_FLAG_CODES)
        rough_present = rough not in (None, "", [])

        if rough_present and not has_inference:
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


def _invariant_p_g2(events: list[dict]) -> list[dict]:
    """§P-G2 — every row with non-null bid_type satisfies one of:
    (1) source_quote contains a §G1 trigger phrase (case-insensitive
    substring), (2) the row is a true range bid
    (`bid_value_lower < bid_value_upper`), or (3) the row carries a
    ≤200-char `bid_type_inference_note`. Violations emit the hard flag
    `bid_type_unsupported`."""
    flags: list[dict[str, Any]] = []
    for i, ev in enumerate(events):
        bid_type = ev.get("bid_type")
        if bid_type in (None, "", []):
            continue

        note = ev.get("bid_type_inference_note")
        if isinstance(note, str) and 0 < len(note.strip()) <= 200:
            continue

        lower = ev.get("bid_value_lower")
        upper = ev.get("bid_value_upper")
        if (
            lower not in (None, "", [])
            and upper not in (None, "", [])
            and lower != upper
        ):
            continue  # true range-bid signal per §G1 (lower < upper)

        raw_quote = ev.get("source_quote")
        if isinstance(raw_quote, list):
            quote_text = " ".join(q for q in raw_quote if isinstance(q, str))
        elif isinstance(raw_quote, str):
            quote_text = raw_quote
        else:
            quote_text = ""
        # §G2 is existence-only: any §G1 trigger (formal or informal) suffices.
        # §G1 governs which classification the trigger maps to.
        if any(t in quote_text.lower() for t in ALL_G1_TRIGGERS):
            continue

        flags.append({
            "row_index": i, "code": "bid_type_unsupported", "severity": "hard",
            "reason": (
                f"§P-G2: bid_type={bid_type!r} has no §G1 trigger in "
                f"source_quote, no range-bid structure, and no "
                f"bid_type_inference_note. Attach one."
            ),
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


def _invariant_p_s3(deal: dict, events: list[dict]) -> list[dict]:
    """§P-S3 — each process_phase contains a terminator event in
    {Executed, Terminated, Auction Closed}.

    Iter-5 simplification. The previous iter-4 form checked the LITERAL
    LAST ROW after §A2/§A3 canonical sort. That interpretation was too
    strict in three distinct cases:

    1. **Go-shop trailing activity.** Post-Executed go-shop rows (new
       NDAs, IOIs, Drops during the go-shop window) trail the Executed
       row and pushed "last row" past the terminator. Iter-4 added a
       narrow `deal.go_shop_days > 0` carve-out.

    2. **§A3 rank inversions on stale priors.** §A3 places Terminated
       at rank 2 (Process start/restart) and Drop at rank 8 (Dropouts).
       In a same-date cluster with both a Drop and a Terminated, the
       Drop sorts last. Penford's 2007/2009 stale-prior phases hit this.

    3. **Null-dated §E3 placeholder rows.** Count-audit placeholders
       (e.g., mac-gray's 16 unnamed financial NDAs + 16 implicit Drops
       emitted from "over the next two months, 20 bidders signed NDAs")
       sort AFTER all dated rows, trailing the Executed row. Even with
       dated placeholders via §B4 range-collapse, they often still
       land after Executed in narrative order.

    All three are cases where the phase DOES contain a terminator; the
    "literal last row" interpretation was conflating "last row" with
    "phase terminator" unnecessarily. The relaxed rule ("any terminator
    in phase") captures the actual invariant: every phase's process
    must close, but rows representing activity tangential to that
    close (go-shop, undated placeholders, §A3 same-date clusters) are
    allowed to trail the terminator in the canonical sequence.

    Hard-invariant coverage is preserved: a phase with NO terminator
    still fires the flag. §P-S4 (exactly one Executed row, in the max
    phase) continues to enforce the deal-level close invariant
    independently.
    """
    flags: list[dict[str, Any]] = []
    by_phase: dict[int, list[dict]] = {}
    for ev in events:
        phase = ev.get("process_phase")
        if phase is None:
            phase = 1  # §L2 default for deals with no prior/restart
        by_phase.setdefault(phase, []).append(ev)
    for phase, rows in by_phase.items():
        has_terminator = any(
            r.get("bid_note") in PHASE_TERMINATORS for r in rows
        )
        if has_terminator:
            continue
        last_row = rows[-1]
        flags.append({
            "code": "phase_termination_missing", "severity": "hard",
            "reason": (
                f"process_phase={phase}: phase contains no terminator event "
                f"(no row with bid_note in {{Executed, Terminated, Auction Closed}}); "
                f"last row is bid_note={last_row.get('bid_note')!r}"
            ),
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


def count_flags(final_extraction: dict[str, Any]) -> dict[str, int]:
    """Count combined extractor + validator flags from the finalized output."""
    counts = {"hard": 0, "soft": 0, "info": 0}
    deal_flags = (final_extraction.get("deal") or {}).get("deal_flags") or []
    event_lists = [
        ev.get("flags") or []
        for ev in (final_extraction.get("events") or [])
    ]
    for flag in deal_flags:
        severity = flag.get("severity", "hard")
        if severity not in counts:
            severity = "hard"
        counts[severity] += 1
    for flags in event_lists:
        for flag in flags:
            severity = flag.get("severity", "hard")
            if severity not in counts:
                severity = "hard"
            counts[severity] += 1
    return counts


def summarize(final_extraction: dict[str, Any]) -> tuple[str, int, str]:
    """Return (status, flag_count, notes) per the §Status taxonomy.

    hard > 0 → "validated" (blocks advancement, human review required)
    any soft/info but zero hard → "passed"
    zero combined flags → "passed_clean"
    """
    counts = count_flags(final_extraction)
    hard = counts["hard"]
    soft = counts["soft"]
    info = counts["info"]
    if hard > 0:
        status = "validated"
    elif soft > 0 or info > 0:
        status = "passed"
    else:
        status = "passed_clean"
    flag_count = hard + soft + info
    notes = f"hard={hard} soft={soft} info={info}"
    return status, flag_count, notes


def write_output(slug: str, final_extraction: dict[str, Any]) -> Path:
    EXTRACTIONS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EXTRACTIONS_DIR / f"{slug}.json"
    out_path.write_text(json.dumps(final_extraction, indent=2, default=str) + "\n")
    return out_path


def append_flags_log(
    slug: str,
    final_extraction: dict[str, Any],
) -> int:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    now = _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")
    lines: list[str] = []
    deal = final_extraction.get("deal") or {}
    events = final_extraction.get("events") or []
    for f in deal.get("deal_flags") or []:
        entry = {"deal": slug, "logged_at": now, "deal_level": True, **f}
        lines.append(json.dumps(entry, default=str))
    for i, ev in enumerate(events):
        for f in ev.get("flags") or []:
            entry = {"deal": slug, "logged_at": now, "row_index": i, **f}
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


def _apply_unnamed_nda_promotions(
    raw_extraction: dict[str, Any],
) -> list[dict[str, Any]]:
    """Consume `unnamed_nda_promotion` hints on Bid rows.

    The extractor emits NDA rows in narrative order. When the filing later
    names a bidder whose NDA was emitted as an unnamed §E3 placeholder
    ("Strategic 5"), the AI attaches an `unnamed_nda_promotion` hint on the
    named Bid row pointing to the placeholder's BidderID. Python applies the
    hint deterministically: the target NDA row's bidder_alias / bidder_name
    are rewritten to the promoted values, and the hint field is stripped.

    Hint schema:
      {
        "unnamed_nda_promotion": {
          "target_bidder_id": 12,            // narrative-order BidderID of placeholder NDA row
          "promote_to_bidder_alias": "Party E",
          "promote_to_bidder_name": "bidder_07",  // must exist in bidder_registry
          "reason": "<filing citation>"
        }
      }

    Returns a log of {row_index, status, from, to, reason} entries for audit.
    Mutates raw_extraction in place.
    """
    events = raw_extraction.get("events") or []
    deal = raw_extraction.setdefault("deal", {})
    bidder_registry = deal.setdefault("bidder_registry", {})
    by_bidder_id: dict[int, dict] = {
        ev["BidderID"]: ev for ev in events if isinstance(ev.get("BidderID"), int)
    }

    log: list[dict[str, Any]] = []
    for i, ev in enumerate(events):
        promo = ev.get("unnamed_nda_promotion")
        if not promo:
            continue

        def fail(reason: str) -> None:
            # Hint remains on the row as audit trail; finalize() emits the
            # corresponding hard flag post-canonicalize so row indices are
            # stable for downstream consumers.
            log.append({
                "row_index": i, "status": "failed",
                "reason": reason, "hint": promo,
            })

        target_id = promo.get("target_bidder_id")
        target = by_bidder_id.get(target_id)
        if target is None:
            fail(f"target_bidder_id={target_id} not found in events")
            continue
        if target.get("bid_note") != "NDA":
            fail(f"target row {target_id} has bid_note={target.get('bid_note')!r}, expected 'NDA'")
            continue
        old_alias = target.get("bidder_alias")
        old_name = target.get("bidder_name")
        new_alias = promo.get("promote_to_bidder_alias")
        new_name = promo.get("promote_to_bidder_name")
        if new_name and new_name not in bidder_registry:
            fail(
                f"promote_to_bidder_name={new_name!r} not present in "
                f"bidder_registry — promotion would leave a dangling "
                f"bidder_name on target row {target_id}"
            )
            continue
        if old_name is not None and new_name and old_name != new_name:
            fail(
                f"target row {target_id} already has bidder_name={old_name!r}; "
                f"promotion would overwrite a named bidder (only unnamed §E3 "
                f"placeholders are promotable)"
            )
            continue
        # Success — apply mutations and pop the hint so it doesn't ship.
        if new_alias:
            target["bidder_alias"] = new_alias
        if new_name:
            target["bidder_name"] = new_name
            aliases = bidder_registry[new_name].setdefault("aliases_observed", [])
            if old_alias and old_alias not in aliases:
                aliases.append(old_alias)
        ev.pop("unnamed_nda_promotion", None)
        log.append({
            "row_index": i,
            "target_bidder_id": target_id,
            "status": "applied",
            "from": {"bidder_alias": old_alias, "bidder_name": old_name},
            "to": {"bidder_alias": new_alias, "bidder_name": new_name},
            "reason": promo.get("reason"),
        })
    return log


def _canonicalize_order(raw_extraction: dict[str, Any]) -> None:
    """Python-enforced §A2/§A3 ordering (Fix 1).

    Sort events by (bid_date_precise, §A3 rank, narrative index). Reassign
    BidderID = 1..N strictly monotone. Null-dated rows sort to the end
    preserving narrative order among themselves.

    This removes mechanical ordering from the LLM's responsibility. The AI
    may emit rows in narrative order; Python fixes §A2 date-monotone and
    §A3 same-date rank violations deterministically.

    Also updates `bidder_registry[*].first_appearance_row_index` to the new
    BidderID of each bidder's first appearance.

    Mutates raw_extraction in place.
    """
    events = raw_extraction.get("events") or []
    if not events:
        return
    for idx, ev in enumerate(events):
        ev["_narrative_index"] = idx

    def sort_key(ev: dict) -> tuple:
        date = ev.get("bid_date_precise") or "9999-12-31"
        rank = _rank(ev.get("bid_note"), ev.get("bid_type"))
        return (date, rank, ev["_narrative_index"])

    events.sort(key=sort_key)
    for new_id, ev in enumerate(events, start=1):
        ev["BidderID"] = new_id
        ev.pop("_narrative_index", None)
    raw_extraction["events"] = events

    # Recompute first_appearance_row_index for each bidder_name.
    registry = raw_extraction.get("deal", {}).get("bidder_registry") or {}
    first_seen: dict[str, int] = {}
    for ev in events:
        name = ev.get("bidder_name")
        if name and name not in first_seen:
            first_seen[name] = ev["BidderID"]
    for name, reg_entry in registry.items():
        if not isinstance(reg_entry, dict):
            continue
        if name in first_seen:
            reg_entry["first_appearance_row_index"] = first_seen[name]


def finalize(
    slug: str,
    raw_extraction: dict[str, Any],
    filing: Filing | None = None,
) -> PipelineResult:
    """Run Python validator + merge flags + write output + update state.

    Pre-validate transforms:
      1. Apply `unnamed_nda_promotion` hints (Fix 2C)
      2. Canonicalize row order and BidderIDs (Fix 1 — §A2/§A3 sort)

    Does NOT spawn adjudicator subagents — that's the orchestrator's job,
    performed BEFORE calling this function. If the caller has adjudicated
    soft flags, they should mutate raw_extraction['events'][i]['flags']
    and/or raw_extraction['deal']['deal_flags'] with adjudicator verdicts
    before passing raw_extraction in.
    """
    if filing is None:
        filing = load_filing(slug)
    # Promote unnamed NDA placeholders to named bidders before sort.
    # Failed promotions leave their hint on the source row; flagging
    # happens post-canonicalize so row indices are stable.
    promotion_log = _apply_unnamed_nda_promotions(raw_extraction)
    # Deterministic §A2/§A3 sort + BidderID reassignment.
    _canonicalize_order(raw_extraction)
    # Locate failed-promotion source rows via residual-hint identity
    # (success path pops the hint; failure path leaves it).
    failed_reasons_by_hint_id = {
        id(entry["hint"]): entry["reason"]
        for entry in promotion_log if entry.get("status") == "failed"
    }
    for ev in raw_extraction.get("events", []):
        promo = ev.get("unnamed_nda_promotion")
        if not promo or id(promo) not in failed_reasons_by_hint_id:
            continue
        ev.setdefault("flags", []).append({
            "code": "nda_promotion_failed", "severity": "hard",
            "reason": failed_reasons_by_hint_id[id(promo)],
        })
    result = validate(raw_extraction, filing)
    final = merge_flags(raw_extraction, result.row_flags, result.deal_flags)
    # Attach promotion log to deal object for audit (pipeline-internal field).
    if promotion_log:
        final.setdefault("deal", {})["_unnamed_nda_promotions"] = promotion_log
    status, flag_count, notes = summarize(final)
    out_path = write_output(slug, final)
    append_flags_log(slug, final)
    update_progress(slug, status, flag_count, notes)
    return PipelineResult(
        status=status,
        flag_count=flag_count,
        notes=notes,
        output_path=out_path,
    )
