"""pipeline.py — Python plumbing for the M&A extraction skill.

The Extractor and Adjudicator agents run as **Claude Code subagents** with
clean-slate contexts, administered by the orchestrating conversation. Python
owns validation, canonicalization, and finalization. The LLM orchestrator owns
Extractor spawning, Adjudicator spawning, and any pre-finalize mutation of
`raw_extraction`. This module provides the deterministic, non-LLM pieces only:

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
import hashlib
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


def rulebook_version() -> str:
    """Stable content hash for the live rulebook.

    This is intentionally a content hash rather than a git lookup: it fails
    less mysteriously in uncommitted development states and changes whenever
    any current `rules/*.md` content changes. Git history is still the record
    for prior rulebooks; the live pipeline supports only the current schema.
    """
    h = hashlib.sha256()
    rule_files = sorted(RULES_DIR.glob("*.md"))
    if not rule_files:
        raise FileNotFoundError(f"no rule files found under {RULES_DIR}")
    for path in rule_files:
        h.update(path.name.encode("utf-8"))
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def _now_iso() -> str:
    """UTC ISO-8601 timestamp with Z suffix (pipeline-standard format).

    Centralized so finalize() can capture a single value once and use it
    for both `logged_at` on every appended flag and `last_run` in state.
    This makes the documented `logged_at == last_run` query an exact
    equality rather than a timestamp-ordering question.
    """
    return _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")


RULEBOOK_HISTORY_CAP = 10  # Per-deal rulebook_version_history tail length.

# ---------------------------------------------------------------------------
# Vocabularies — mirrors of rules/*.md
# ---------------------------------------------------------------------------
# These are the operational, machine-readable form of the rulebook
# vocabularies. The rulebook markdown is the source of truth; when those
# files change, update the mirrors here in the same commit.

# Mirror of rules/events.md §C1 — the taxonomy-redesign closed vocabulary.
# Bid rows all carry bid_note="Bid"; bid_type ("informal"/"formal") is the
# only bid-row formal/informal distinguisher. Final-round, drop, and press
# release subtypes live in structured columns, not cross-product event labels.
EVENT_VOCABULARY: frozenset[str] = frozenset({
    # Start-of-process
    "Bidder Interest", "Bidder Sale", "Target Sale",
    "Target Sale Public", "Activist Sale",
    # Publicity
    "Press Release",
    # Advisors
    "IB", "IB Terminated",
    # Counterparty events
    "NDA", "ConsortiumCA",
    "Drop", "DropSilent",
    # Bid rows — §C3 unified; bid_type disambiguates formal/informal
    "Bid",
    # Round structure (§K1)
    "Final Round", "Auction Closed",
    # Closing
    "Executed",
    # Prior-process
    "Terminated", "Restarted",
})

# Mirror of rules/bids.md §M3.
ROLE_VOCABULARY: frozenset[str] = frozenset({
    "bidder", "advisor_financial", "advisor_legal",
})

# Mirror of rules/bidders.md §F1 — scalar bidder_type after the 2026-04-27
# flatten dropped `mixed`, `non_us`, and `public`. Enforced by §P-R6.
BIDDER_TYPE_VOCABULARY: frozenset[str] = frozenset({"s", "f"})

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
    "Drop", "DropSilent",
    "Executed",
})

# Flag codes that legitimize a non-null bid_date_rough per §B2/§B3/§B4.
DATE_INFERENCE_FLAG_CODES: frozenset[str] = frozenset({
    "date_inferred_from_rough",
    "date_inferred_from_context",
    "date_range_collapsed",
})

def _row_flag_codes(ev: dict) -> set[str]:
    """Return the set of flag codes attached to a row, guarding against
    non-dict entries that may slip through LLM output."""
    return {f.get("code") for f in (ev.get("flags") or []) if isinstance(f, dict)}

# §A3 logical ordering rank table (lower rank = earlier within same date).
# Keys are bid_note values; for Bid rows specifically, informal bids rank 6
# and formal bids rank 7 — the comparator consults bid_type.
EVENT_RANK: dict[str, int] = {
    # Rank 1 — process announcements / public events
    "Press Release": 1,
    "Target Sale Public": 1,
    "Bidder Sale": 1,
    "Activist Sale": 1,
    # Rank 2 — process start / restart
    "Target Sale": 2,
    "Terminated": 2,
    "Restarted": 2,
    # Rank 3 — advisor / IB events
    "IB": 3,
    "IB Terminated": 3,
    # Rank 4 — bidder first-contact
    "Bidder Interest": 4,
    # Rank 5 — NDAs and consortium CAs (§I2 distinguishes Type A vs Type B)
    "NDA": 5,
    "ConsortiumCA": 5,
    # Rank 6/7 — bids (§C3 unified "Bid"; formal bumps to 7 via _rank())
    "Bid": 6,
    # Rank 8 — dropouts
    "Drop": 8,
    "DropSilent": 8,
    # Rank 9 — final-round deadlines / auction closed
    "Final Round": 9,
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
    {RULES_DIR}/events.md      (bid_note closed vocabulary §C1, 18 values)
    {RULES_DIR}/bidders.md     (canonical IDs §E3, bidder_type §F1)
    {RULES_DIR}/bids.md        (formal/informal §G1, skip rules §M)
    {RULES_DIR}/dates.md       (date mapping §B, BidderID sequence §A1–§A4)

  Filing (authoritative for every source_quote and source_page):
    {DATA_DIR}/{slug}/pages.json     (list of {{"number": int, "content": str, ...}})
    {DATA_DIR}/{slug}/manifest.json  (EDGAR metadata + deal-identity cross-check)

Everything in `prompts/extract.md` and the listed extractor rule files is
binding. Do not paraphrase, override, or reinterpret — follow the rulebook
as written. If any listed extractor rule is 🟥 OPEN, halt and emit the
blocked form (see below).

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

    deal_flags.extend(_invariant_p_r1(raw_extraction))
    if deal_flags:
        return ValidatorResult(row_flags=row_flags, deal_flags=deal_flags)

    deal = raw_extraction.get("deal") or {}
    events = raw_extraction.get("events") or []

    # Row-level invariants.
    row_flags.extend(_invariant_p_r2(events, filing))
    row_flags.extend(_invariant_p_r3(events))
    row_flags.extend(_invariant_p_r4(events))
    row_flags.extend(_invariant_p_r5(events, deal))
    row_flags.extend(_invariant_p_r6(events))
    row_flags.extend(_invariant_p_r7(events))
    row_flags.extend(_invariant_p_d1(events))
    row_flags.extend(_invariant_p_d2(events))
    row_flags.extend(_invariant_p_d5(events))
    row_flags.extend(_invariant_p_d6(events))
    row_flags.extend(_invariant_p_d7(events))
    row_flags.extend(_invariant_p_d8(events))
    row_flags.extend(_invariant_p_h5(events))
    row_flags.extend(_invariant_p_g2(events))
    row_flags.extend(_invariant_p_g3(events))

    # §P-D3 returns a mix (structural are deal-level; ordering violations are
    # row-level). Route by presence of row_index.
    for f in _invariant_p_d3(events):
        (row_flags if "row_index" in f else deal_flags).append(f)

    row_flags.extend(_invariant_p_s1(events))

    # Deal-level semantic invariants.
    deal_flags.extend(_invariant_p_l1(events))
    deal_flags.extend(_invariant_p_l2(events))
    deal_flags.extend(_invariant_p_s2(deal, events))
    deal_flags.extend(_invariant_p_s3(events))
    deal_flags.extend(_invariant_p_s4(events))

    return ValidatorResult(row_flags=row_flags, deal_flags=deal_flags)


def _nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s)


# PDF-extraction curly-quote folding for §P-R2 substring check. Only the
# four curly-quote codepoints need folding; NFKC (applied first on both
# sides of the substring check) already canonicalizes NBSP (U+00A0 →
# U+0020) and ellipsis (U+2026 → "..."), so those entries would be dead
# code. Case is NOT folded, whitespace is NOT collapsed, punctuation is
# NOT stripped — those would mask real extractor paraphrase errors.
_PDF_ARTIFACT_MAP = str.maketrans({
    "‘": "'",   # left single quotation mark
    "’": "'",   # right single quotation mark (apostrophe)
    "“": '"',   # left double quotation mark
    "”": '"',   # right double quotation mark
})


def _canonicalize_pdf_artifacts(s: str) -> str:
    """Fold PDF-extraction curly-quote variants to ASCII equivalents.

    Applied to both sides of the §P-R2 substring check so curly-vs-straight
    quote mismatches do not spuriously fail.
    """
    return s.translate(_PDF_ARTIFACT_MAP)


def _phase(ev: dict) -> int:
    """§L2 default: `process_phase` is 1 when absent or None.

    Centralizes the default so invariants that need "main-phase or default"
    semantics share one implementation. Invariants that test phase 0 explicitly
    (§P-L2's phase_0_dates, §P-S3's exemption guard) continue to use the raw
    `ev.get("process_phase")` — defaulting None to 1 would hide the
    distinction.
    """
    phase = ev.get("process_phase")
    return 1 if phase is None else phase


def _invariant_p_r1(raw_extraction: dict[str, Any]) -> list[dict]:
    """§P-R1 — top-level `events` exists, is a list, and is non-empty."""
    events = raw_extraction.get("events")
    if isinstance(events, list) and events:
        return []
    return [{
        "code": "empty_events_array",
        "severity": "hard",
        "reason": "events[] must exist as a non-empty list",
        "deal_level": True,
    }]


def _invariant_p_r2(events: list[dict], filing: Filing) -> list[dict]:
    """§P-R2 — every row has source_quote and source_page; quote is an
    NFKC-substring of pages[source_page-1].content, ≤ 1000 chars."""
    flags: list[dict[str, Any]] = []
    valid_pages = filing.page_numbers()
    # Canonicalize each cited page at most once; ~N_pages instead of N_rows.
    page_canon_cache: dict[int, str] = {}
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
            if not q.strip():
                flags.append({
                    "row_index": i, "code": "missing_evidence", "severity": "hard",
                    "reason": "source_quote element is empty after trimming whitespace",
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
            page_canon = page_canon_cache.get(p)
            if page_canon is None:
                page_canon = _canonicalize_pdf_artifacts(_nfkc(filing.page_content(p) or ""))
                page_canon_cache[p] = page_canon
            q_canon = _canonicalize_pdf_artifacts(_nfkc(q)).strip()
            if q_canon not in page_canon:
                excerpt = q[:120] + ("..." if len(q) > 120 else "")
                flags.append({
                    "row_index": i, "code": "source_quote_not_in_page", "severity": "hard",
                    "reason": f"NFKC+PDF-artifact-normalized source_quote not a substring of pages[{p}].content; excerpt: {excerpt!r}",
                })
    return flags


def _invariant_p_r3(events: list[dict]) -> list[dict]:
    """§P-R3 — bid_note ∈ §C1 closed vocabulary on every row."""
    flags: list[dict[str, Any]] = []
    for i, ev in enumerate(events):
        bn = ev.get("bid_note")
        if bn is None:
            flags.append({
                "row_index": i, "code": "bid_note_null", "severity": "hard",
                "reason": (
                    "§P-R3: bid_note is null; §C1/§C3 require a "
                    "closed-vocabulary value on every row (bid rows use 'Bid')."
                ),
            })
            continue
        if bn in EVENT_VOCABULARY:
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
    """§P-R5 — bidder registry keys, aliases, and resolved names align."""
    flags: list[dict[str, Any]] = []
    registry = (deal.get("bidder_registry") or {}) if deal else {}
    for i, ev in enumerate(events):
        name = ev.get("bidder_name")
        if name is None:
            continue
        if name not in registry:
            flags.append({
                "row_index": i, "code": "bidder_not_in_registry", "severity": "hard",
                "reason": f"§P-R5/§E4: bidder_name={name!r} not a key in bidder_registry",
            })
            continue
        entry = registry[name] or {}
        aliases = set(entry.get("aliases_observed", []) or [])
        alias = ev.get("bidder_alias")
        if alias is not None and alias not in aliases:
            flags.append({
                "row_index": i, "code": "bidder_alias_not_observed", "severity": "hard",
                "reason": (
                    f"§P-R5/§E4: bidder_alias={alias!r} for {name!r} not in "
                    f"aliases_observed={sorted(aliases)!r}"
                ),
            })
        resolved = entry.get("resolved_name")
        if resolved is not None and resolved not in aliases:
            flags.append({
                "row_index": i, "code": "resolved_name_not_observed", "severity": "soft",
                "reason": (
                    f"§P-R5/§E4: resolved_name={resolved!r} for {name!r} not in "
                    f"aliases_observed={sorted(aliases)!r}"
                ),
            })
    return flags


def _invariant_p_r6(events: list[dict]) -> list[dict]:
    """§P-R6 — `bidder_type`, when present, must be a scalar string in
    {"s", "f"} or null. Any non-scalar type or unknown string value fails
    hard."""
    flags: list[dict[str, Any]] = []
    for i, ev in enumerate(events):
        bt = ev.get("bidder_type")
        if bt is None:
            continue
        if isinstance(bt, str) and bt in BIDDER_TYPE_VOCABULARY:
            continue
        flags.append({
            "row_index": i,
            "code": "bidder_type_invalid_value",
            "severity": "hard",
            "reason": (
                f"§P-R6: bidder_type={bt!r} (type {type(bt).__name__!r}) is not a "
                f"scalar in {{\"s\", \"f\"}} or null."
            ),
        })
    return flags


def _invariant_p_r7(events: list[dict]) -> list[dict]:
    """§P-R7 — `ca_type_ambiguous` is a hard flag after the taxonomy redesign.

    The extractor may still attach the ambiguity flag while classifying a
    CA, but ambiguity over whether a CA is target-bidder, bidder-bidder, or
    rollover is no longer allowed to pass as soft noise.
    """
    flags: list[dict[str, Any]] = []
    for i, ev in enumerate(events):
        for flag in ev.get("flags") or []:
            if not isinstance(flag, dict):
                continue
            if flag.get("code") != "ca_type_ambiguous":
                continue
            if flag.get("severity") == "hard":
                continue
            flags.append({
                "row_index": i,
                "code": "ca_type_ambiguous",
                "severity": "hard",
                "reason": (
                    "§P-R7: ca_type_ambiguous is hard after the taxonomy "
                    "redesign; ambiguous CA type requires adjudication."
                ),
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
    """§P-D5 — every explicit `Drop` row's bidder has a prior engagement row
    (NDA, Bidder Interest, IB, or prior Drop) in the same process_phase.

    Closes the dangling-drop gap where an AI emits a Drop row for a bidder
    that was never shown engaging with the process (no NDA, no expression
    of interest, no IB kickoff). Matches the current §C1 Drop-family
    DropSilent is explicitly excluded: it is inferred from filing silence and
    is backed by the matching NDA row under §I1 / §P-S1, not by a narrated
    dropout agency event. Existence-only check via set membership over
    per-(phase, bidder) engagement rows: canonicalization (§A2/§A3) has
    already ordered events, so "earlier row" reduces to "any engagement row
    for this (name, phase)" in practice. The prior-Drop carve-out covers §I2
    re-engagement edge cases where an extractor emits Drop→Drop without an
    intervening NDA.

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
        phase = _phase(ev)
        if "unsolicited_first_contact" in _row_flag_codes(ev):
            unsolicited_keys.add((name, phase))
        note = ev.get("bid_note", "") or ""
        if note not in engagement_notes and note != "Drop":
            continue
        engagement_rows.setdefault((name, phase), set()).add(j)

    for i, ev in enumerate(events):
        note = ev.get("bid_note", "") or ""
        if note != "Drop":
            continue
        name = ev.get("bidder_name")
        if not name:
            continue  # unnamed placeholder — skip
        phase = _phase(ev)
        if phase == 0:
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
      - Rows carrying `unsolicited_first_contact` flag (§D1.a, Class B)
        — the bidder never signs an NDA in this deal; §D1 itself
        authorizes the NDA-less Bid row.

    No `pre_nda_informal_bid` exemption is needed. §P-D6 is existence-
    only, not ordering — §C4's pre-NDA informal-bid pattern has the
    bidder signing an NDA LATER in the same phase, so the NDA does
    exist. The §C4 flag remains (documents the pre-NDA timing), but no
    validator carve-out is needed.
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
        nda_keys.add((name, _phase(ev)))

    for i, ev in enumerate(events):
        if ev.get("bid_note") != "Bid":
            continue
        name = ev.get("bidder_name")
        if not name:
            continue  # unnamed §E3 placeholder — skip
        phase = _phase(ev)
        if phase == 0:
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


TARGET_DROP_REASON_CLASSES = frozenset({
    "below_market",
    "below_minimum",
    "target_other",
    "never_advanced",
    "scope_mismatch",
})
BIDDER_DROP_REASON_CLASSES = frozenset({None, "no_response", "scope_mismatch"})
DROP_INITIATORS = frozenset({"bidder", "target", "unknown"})


def _invariant_p_d7(events: list[dict]) -> list[dict]:
    """§P-D7 — `Drop` rows use the redesigned initiator/reason matrix."""
    flags: list[dict[str, Any]] = []
    for i, ev in enumerate(events):
        if ev.get("bid_note") != "Drop":
            continue
        initiator = ev.get("drop_initiator")
        reason = ev.get("drop_reason_class")
        problem: str | None = None
        if initiator not in DROP_INITIATORS:
            problem = (
                f"drop_initiator={initiator!r} must be one of "
                "{'bidder', 'target', 'unknown'} on Drop rows"
            )
        elif initiator == "target" and reason not in TARGET_DROP_REASON_CLASSES:
            problem = (
                f"drop_initiator='target' requires drop_reason_class in "
                f"{sorted(TARGET_DROP_REASON_CLASSES)!r}; got {reason!r}"
            )
        elif initiator == "bidder" and reason not in BIDDER_DROP_REASON_CLASSES:
            problem = (
                "drop_initiator='bidder' permits only null, 'no_response', "
                f"or 'scope_mismatch'; got {reason!r}"
            )
        elif initiator == "unknown" and reason is not None:
            problem = (
                f"drop_initiator='unknown' requires drop_reason_class=null; "
                f"got {reason!r}"
            )
        if problem is None:
            continue
        flags.append({
            "row_index": i,
            "code": "drop_reason_class_inconsistent",
            "severity": "soft",
            "reason": f"§P-D7: {problem}",
        })
    return flags


def _invariant_p_d8(events: list[dict]) -> list[dict]:
    """§P-D8 — informal-bid formal-stage status matches same-phase rows."""
    flags: list[dict[str, Any]] = []
    formal_bid_keys = {
        (ev.get("bidder_name"), _phase(ev))
        for ev in events
        if ev.get("bid_note") == "Bid"
        and ev.get("bid_type") == "formal"
        and ev.get("bidder_name")
    }
    for i, ev in enumerate(events):
        note = ev.get("bid_note")
        if note == "Bid" and ev.get("bid_type") == "informal" and _phase(ev) >= 1:
            key = (ev.get("bidder_name"), _phase(ev))
            has_formal_bid = key in formal_bid_keys
            submitted = ev.get("submitted_formal_bid")
            if submitted is True and not has_formal_bid:
                flags.append({
                    "row_index": i,
                    "code": "formal_round_status_inconsistent",
                    "severity": "soft",
                    "reason": (
                        "§P-D8: submitted_formal_bid=true but no formal Bid "
                        "row exists for the same bidder and process_phase."
                    ),
                })
            elif submitted is False and has_formal_bid:
                flags.append({
                    "row_index": i,
                    "code": "formal_round_status_inconsistent",
                    "severity": "soft",
                    "reason": (
                        "§P-D8: submitted_formal_bid=false but a formal Bid "
                        "row exists for the same bidder and process_phase."
                    ),
                })
        if note == "Drop" and ev.get("drop_reason_class") == "never_advanced":
            if ev.get("invited_to_formal_round") is not False:
                flags.append({
                    "row_index": i,
                    "code": "formal_round_status_inconsistent",
                    "severity": "soft",
                    "reason": (
                        "§P-D8: Drop with drop_reason_class='never_advanced' "
                        "requires invited_to_formal_round=false."
                    ),
                })
    return flags


def _invariant_p_h5(events: list[dict]) -> list[dict]:
    """§P-H5 — multi-bid sequences should be date-sorted per bidder."""
    by_name: dict[str, list[tuple[int, str]]] = {}
    for i, ev in enumerate(events):
        if ev.get("bid_note") != "Bid":
            continue
        name = ev.get("bidder_name")
        date = ev.get("bid_date_precise")
        if not name or not date:
            continue
        by_name.setdefault(name, []).append((i, date))

    flags: list[dict[str, Any]] = []
    for name, rows in by_name.items():
        if len(rows) <= 1:
            continue
        dates = [date for _, date in rows]
        if dates == sorted(dates):
            continue
        flags.append({
            "row_index": rows[-1][0],
            "code": "bid_revision_out_of_order",
            "severity": "soft",
            "reason": (
                f"§P-H5: bidder {name!r} has {len(rows)} bids with dates not "
                f"in chronological order: {dates!r}"
            ),
        })
    return flags


def _invariant_p_d2(events: list[dict]) -> list[dict]:
    """§P-D2 — bid_date_rough ≠ null IFF the row carries a date-inference
    flag (date_inferred_from_rough / date_inferred_from_context /
    date_range_collapsed). Strict XOR; no fixture carve-out."""
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


def _event_date_leq(left: dict, right: dict) -> bool:
    """Return whether left's precise date is <= right's when both exist.

    If either date is missing, use row order elsewhere as the fallback rather
    than treating the missing date as disqualifying.
    """
    left_date = left.get("bid_date_precise")
    right_date = right.get("bid_date_precise")
    if left_date and right_date:
        return left_date <= right_date
    return True


def _paired_final_round(
    events: list[dict],
    bid_index: int,
    *,
    require_non_announcement: bool = False,
    after_index: int | None = None,
) -> tuple[int, dict] | None:
    """Find the final-round row that supplies §G1 process-position context.

    Preference follows the taxonomy spec: most recent non-announcement
    Final Round in the same phase with date <= bid date; if none exists and
    `require_non_announcement` is false, fall back to the most recent
    applicable Final Round regardless of announcement status.
    """
    if bid_index < 0 or bid_index >= len(events):
        return None
    bid = events[bid_index]
    if bid.get("bid_note") != "Bid":
        return None
    phase = _phase(bid)

    def candidates(non_announcement_only: bool) -> list[tuple[int, dict]]:
        out: list[tuple[int, dict]] = []
        for i, ev in enumerate(events):
            if i >= bid_index:
                continue
            if after_index is not None and i <= after_index:
                continue
            if ev.get("bid_note") != "Final Round":
                continue
            if _phase(ev) != phase:
                continue
            if non_announcement_only and ev.get("final_round_announcement") is not False:
                continue
            if not _event_date_leq(ev, bid):
                continue
            out.append((i, ev))
        return out

    non_ann = candidates(non_announcement_only=True)
    if non_ann:
        return max(non_ann, key=lambda item: (item[1].get("bid_date_precise") or "", item[0]))
    if require_non_announcement:
        return None
    any_round = candidates(non_announcement_only=False)
    if any_round:
        return max(any_round, key=lambda item: (item[1].get("bid_date_precise") or "", item[0]))
    return None


def _invariant_p_g2(events: list[dict]) -> list[dict]:
    """§P-G2 — every row with non-null bid_type satisfies one of:
    (1) the row is a true range bid (both `bid_value_lower` and
    `bid_value_upper` numeric with `lower < upper`, a §G1 informal
    structural signal), or (2) the row carries a non-empty
    `bid_type_inference_note: str` of ≤300 chars. §G1 trigger tables are
    classification guidance for the extractor. The redesigned process-
    position fallback may also be evidenced by a paired/fallback
    `Final Round.final_round_informal` value.

    Additional hard rule (per Alex 2026-04-27): when (1) is true, the row
    MUST have `bid_type = "informal"`. A range with bid_type="formal" is
    a structural contradiction.

    Violations emit hard `bid_type_unsupported`, `bid_range_inverted`, or
    `bid_range_must_be_informal`."""
    flags: list[dict[str, Any]] = []
    for i, ev in enumerate(events):
        bid_type = ev.get("bid_type")
        if bid_type in (None, "", []):
            continue

        lower = ev.get("bid_value_lower")
        upper = ev.get("bid_value_upper")
        try:
            lo_num = float(lower) if lower not in (None, "", []) else None
            hi_num = float(upper) if upper not in (None, "", []) else None
        except (TypeError, ValueError):
            lo_num = hi_num = None
        if lo_num is not None and hi_num is not None:
            if lo_num >= hi_num:
                flags.append({
                    "row_index": i, "code": "bid_range_inverted", "severity": "hard",
                    "reason": (
                        f"§P-G2: bid_value_lower={lower!r} >= "
                        f"bid_value_upper={upper!r}; ranges require lower < upper."
                    ),
                })
                continue
            if bid_type != "informal":
                flags.append({
                    "row_index": i, "code": "bid_range_must_be_informal", "severity": "hard",
                    "reason": (
                        f"§P-G2 (2026-04-27): true range "
                        f"({lower!r}..{upper!r}) requires bid_type='informal'; "
                        f"got bid_type={bid_type!r}. Range bids are unconditionally informal."
                    ),
                })
            continue

        note = ev.get("bid_type_inference_note")
        if isinstance(note, str) and 0 < len(note.strip()) <= 300:
            continue

        paired_round = _paired_final_round(events, i)
        if paired_round is not None:
            _, final_round = paired_round
            final_round_informal = final_round.get("final_round_informal")
            expected = (
                "informal" if final_round_informal is True
                else "formal" if final_round_informal is False
                else None
            )
            if expected == bid_type:
                continue

        flags.append({
            "row_index": i, "code": "bid_type_unsupported", "severity": "hard",
            "reason": (
                f"§P-G2: bid_type={bid_type!r} lacks both a true range "
                f"(lower<upper), a non-empty ≤300-char "
                f"bid_type_inference_note, and matching paired/fallback "
                f"Final Round.final_round_informal evidence."
            ),
        })
    return flags


def _invariant_p_g3(events: list[dict]) -> list[dict]:
    """§P-G3 — Final Round announcements with subsequent bids need a paired
    non-announcement Final Round row in the same phase."""
    flags: list[dict[str, Any]] = []
    for i, ev in enumerate(events):
        if ev.get("bid_note") != "Final Round":
            continue
        if ev.get("final_round_announcement") is not True:
            continue
        phase = _phase(ev)
        subsequent_bid_indices = [
            j for j, later in enumerate(events)
            if j > i
            and later.get("bid_note") == "Bid"
            and _phase(later) == phase
            and _event_date_leq(ev, later)
        ]
        if not subsequent_bid_indices:
            continue
        has_non_announcement_pair = any(
            _paired_final_round(
                events,
                bid_index,
                require_non_announcement=True,
                after_index=i,
            ) is not None
            for bid_index in subsequent_bid_indices
        )
        if has_non_announcement_pair:
            continue
        flags.append({
            "row_index": i,
            "code": "final_round_missing_non_announcement_pair",
            "severity": "hard",
            "reason": (
                "§P-G3: Final Round announcement has subsequent bids "
                "but no paired non-announcement Final Round row — check "
                "for missing row."
            ),
        })
    return flags


def _rank(
    bid_note: str | None,
    bid_type: str | None = None,
    final_round_announcement: bool | None = None,
) -> int:
    """§A3 same-date logical rank. Formal bids bump to 7."""
    if bid_note is None:
        return 99
    if bid_note == "Final Round" and final_round_announcement is True:
        return 1
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
            rank_a = _rank(
                ev_a.get("bid_note"),
                ev_a.get("bid_type"),
                ev_a.get("final_round_announcement"),
            )
            rank_b = _rank(
                ev_b.get("bid_note"),
                ev_b.get("bid_type"),
                ev_b.get("final_round_announcement"),
            )
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
    """§P-S1 (SOFT) — safety net for the §I1 DropSilent contract.

    Per rules/events.md §I1, every NDA row (role=bidder, phase ≥ 1) for a
    silent signer must be followed by a `DropSilent` row from the same
    bidder. This invariant fires only when the extractor failed to emit
    that required DropSilent (or any other follow-up). It is a backstop,
    not an expected-noise channel."""
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
        if _phase(ev) == 0:
            continue  # stale prior NDA — excluded per §L1
        name = ev.get("bidder_name")
        if name is None:
            continue  # anonymous NDA — cannot trace follow-up
        later = [(j, e) for (j, e) in by_name.get(name, []) if j > i]
        has_followup = any(e.get("bid_note") in BID_NOTE_FOLLOWUPS for _, e in later)
        if not has_followup:
            flags.append({
                "row_index": i, "code": "missing_nda_dropsilent", "severity": "soft",
                "reason": f"bidder_name={name!r} signed NDA at row {i} but no DropSilent (or other follow-up) was emitted; per §I1 the extractor must emit DropSilent for silent signers",
            })
    return flags


def _invariant_p_l1(events: list[dict]) -> list[dict]:
    """§P-L1 — phase 2 requires phase-1 Terminated and phase-2 Restarted."""
    phase_values = {ev.get("process_phase") for ev in events}
    if 2 not in phase_values:
        return []
    phase_1_notes = {
        ev.get("bid_note")
        for ev in events
        if ev.get("process_phase") == 1
    }
    phase_2_notes = {
        ev.get("bid_note")
        for ev in events
        if ev.get("process_phase") == 2
    }
    missing: list[str] = []
    if "Terminated" not in phase_1_notes:
        missing.append("phase-1 Terminated")
    if "Restarted" not in phase_2_notes:
        missing.append("phase-2 Restarted")
    if not missing:
        return []
    return [{
        "code": "orphan_phase_2",
        "severity": "hard",
        "reason": (
            f"§P-L1: process_phase=2 events exist but the restart boundary is "
            f"missing {missing!r}"
        ),
        "deal_level": True,
    }]


def _invariant_p_l2(events: list[dict]) -> list[dict]:
    """§P-L2 — stale-prior phase 0 must be at least 180 days before main."""
    phase_0_dates = [
        ev.get("bid_date_precise")
        for ev in events
        if ev.get("process_phase") == 0 and ev.get("bid_date_precise")
    ]
    main_dates = [
        ev.get("bid_date_precise")
        for ev in events
        if _phase(ev) >= 1 and ev.get("bid_date_precise")
    ]
    if not phase_0_dates or not main_dates:
        return []

    def _parse(value: str | None) -> _dt.date | None:
        try:
            return _dt.date.fromisoformat(value) if value else None
        except (TypeError, ValueError):
            return None

    stale_dates = [date for date in (_parse(value) for value in phase_0_dates) if date]
    current_dates = [date for date in (_parse(value) for value in main_dates) if date]
    if not stale_dates or not current_dates:
        return []

    latest_stale = max(stale_dates)
    earliest_main = min(current_dates)
    delta_days = (earliest_main - latest_stale).days
    if delta_days >= 180:
        return []
    return [{
        "code": "stale_prior_too_recent",
        "severity": "hard",
        "reason": (
            f"§P-L2: latest phase-0 {latest_stale.isoformat()} is only "
            f"{delta_days} days before earliest phase≥1 "
            f"{earliest_main.isoformat()} (<180-day minimum)"
        ),
        "deal_level": True,
    }]


def _invariant_p_s2(deal: dict, events: list[dict]) -> list[dict]:
    """§P-S2 — deal.auction == (NDA count with role=bidder, phase≥1 ≥ 2)."""
    nda_count = sum(
        1 for ev in events
        if ev.get("bid_note") == "NDA"
        and ev.get("role", "bidder") == "bidder"
        and _phase(ev) >= 1
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
    """§P-S3 — each process_phase contains a terminator event in
    {Executed, Terminated, Auction Closed}.

    The relaxed form (this implementation) accepts any terminator in
    the phase, not the literal last row. The strict "literal last row"
    interpretation was too narrow in three cases:

    1. **Go-shop trailing activity.** Post-Executed go-shop rows (new
       NDAs, IOIs, Drops during the go-shop window) trail the Executed
       row and push "last row" past the terminator.

    2. **§A3 rank inversions on stale priors.** §A3 places Terminated
       at rank 2 (Process start/restart) and Drop at rank 8 (Dropouts).
       In a same-date cluster with both a Drop and a Terminated, the
       Drop sorts last. Penford's 2007/2009 stale-prior phases hit this.

    3. **Null-dated §E3 placeholder rows.** Count-audit placeholders
       (e.g., mac-gray's 16 unnamed financial NDAs + 16 implicit Drops
       emitted from "over the next two months, 20 bidders signed NDAs")
       sort AFTER all dated rows, trailing the Executed row. Dated
       placeholders via §B4 range-collapse often still land after
       Executed in narrative order.

    All three are cases where the phase DOES contain a terminator; the
    "literal last row" interpretation was conflating "last row" with
    "phase terminator" unnecessarily. The relaxed rule ("any terminator
    in phase") captures the actual invariant: every phase's process
    must close, but rows representing activity tangential to that
    close (go-shop, undated placeholders, §A3 same-date clusters) are
    allowed to trail the terminator in the canonical sequence.

    Hard-invariant coverage is preserved: a phase with NO terminator
    still fires the flag. §P-S4 (Executed row(s) in the max phase)
    continues to enforce the deal-level close invariant
    independently.

    §M4 stale-prior phase 0 is exempted: those rows narrate a prior
    abandoned process that the filing references for context and that
    §P-L2 already separates by ≥180 days. Requiring a terminator in
    phase 0 penalized deals whose filings summarized the stale prior
    without re-narrating its close (penford, stec, mac-gray).
    """
    flags: list[dict[str, Any]] = []
    by_phase: dict[int, list[dict]] = {}
    for ev in events:
        by_phase.setdefault(_phase(ev), []).append(ev)
    for phase, rows in by_phase.items():
        if phase == 0:
            # §M4 stale-prior phase 0 is a narrative record of a prior
            # abandoned process; it is not required to carry an in-scope
            # terminator event. §P-L2 enforces the ≥180-day gap between
            # phase-0 and phase≥1, which is the real coherence check on
            # stale priors.
            continue
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
    """§P-S4 — at least one Executed row, all in the max phase."""
    flags: list[dict[str, Any]] = []
    executed = [(i, ev) for i, ev in enumerate(events) if ev.get("bid_note") == "Executed"]
    if not executed:
        flags.append({
            "code": "no_executed_row", "severity": "hard",
            "reason": "no bid_note=Executed row; every in-scope deal closed and must have one",
            "deal_level": True,
        })
        return flags
    max_phase = max(_phase(ev) for ev in events)
    wrong_phases = sorted({_phase(ev) for _, ev in executed if _phase(ev) != max_phase})
    if wrong_phases:
        flags.append({
            "code": "executed_wrong_phase", "severity": "hard",
            "reason": f"Executed row(s) in process_phase={wrong_phases}, but max phase is {max_phase}",
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
    run_ts: str,
) -> int:
    """Append this run's flags to state/flags.jsonl.

    `run_ts` is stamped onto every line's `logged_at`. The caller
    (`finalize()`) captures it once at the start of the run and passes the
    same value to `update_progress()` so the documented query
    `logged_at == last_run` returns exactly this run's flags.
    """
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    deal = final_extraction.get("deal") or {}
    events = final_extraction.get("events") or []
    for f in deal.get("deal_flags") or []:
        entry = {"deal": slug, "logged_at": run_ts, "deal_level": True, **f}
        lines.append(json.dumps(entry, default=str))
    for i, ev in enumerate(events):
        for f in ev.get("flags") or []:
            entry = {"deal": slug, "logged_at": run_ts, "row_index": i, **f}
            lines.append(json.dumps(entry, default=str))
    if lines:
        with FLAGS_PATH.open("a") as fh:
            fh.write("\n".join(lines) + "\n")
    return len(lines)


def update_progress(
    slug: str,
    status: str,
    flag_count: int,
    notes: str,
    current_rulebook_version: str,
    last_run: str,
) -> None:
    """Write this run's status + flag_count + rulebook pin to state/progress.json.

    Auto-creates a minimal deal entry if `slug` was never seeded. Append-only
    on `rulebook_version_history` (capped at `RULEBOOK_HISTORY_CAP`) so the
    "3 consecutive unchanged-rulebook clean runs" gate can be audited per-deal.
    No top-level `rulebook_version`; that key raced between concurrent deal
    finalizes and had no history. Stale state fails loudly instead of being
    cleaned in-place.
    """
    if not PROGRESS_PATH.exists():
        raise FileNotFoundError(f"{PROGRESS_PATH} does not exist; run scripts/build_seeds.py first")
    state = json.loads(PROGRESS_PATH.read_text())
    if "rulebook_version" in state:
        raise ValueError(
            "state/progress.json contains stale top-level rulebook_version; "
            "regenerate state/progress.json under the current schema"
        )
    deals = state.setdefault("deals", {})
    if slug not in deals:
        deals[slug] = {
            "is_reference": False,
            "status": "pending",
            "flag_count": 0,
            "last_run": None,
            "last_verified_by": None,
            "last_verified_at": None,
            "notes": f"auto-created at {last_run} by update_progress; was not in seeds",
        }
    history = deals[slug].setdefault("rulebook_version_history", [])
    history.append({"ts": last_run, "version": current_rulebook_version})
    if len(history) > RULEBOOK_HISTORY_CAP:
        deals[slug]["rulebook_version_history"] = history[-RULEBOOK_HISTORY_CAP:]
    deals[slug].update({
        "status": status,
        "flag_count": flag_count,
        "last_run": last_run,
        "notes": notes,
        "rulebook_version": current_rulebook_version,
    })
    state["updated"] = last_run
    PROGRESS_PATH.write_text(json.dumps(state, indent=2, sort_keys=False) + "\n")


def mark_failed(slug: str, notes: str) -> None:
    """Record a failed deal run.

    This is for pipeline/runtime failures before a valid output can be written.
    Uses `update_progress()`, which auto-creates the deal entry if the slug
    is not in seeds — this is explicit so that failure-recording for
    never-seeded slugs still lands rather than crashing. If the rules
    directory is empty, records `rulebook_version="unavailable"` instead
    of propagating the FileNotFoundError. Other exceptions (missing
    progress.json, disk errors) still propagate — the caller needs to know
    the recorder itself failed.
    """
    if not notes.strip():
        raise ValueError("failure notes must be non-empty")
    try:
        current_version = rulebook_version()
    except FileNotFoundError:
        current_version = "unavailable"
    update_progress(
        slug=slug,
        status="failed",
        flag_count=0,
        notes=notes,
        current_rulebook_version=current_version,
        last_run=_now_iso(),
    )


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
        rank = _rank(
            ev.get("bid_note"),
            ev.get("bid_type"),
            ev.get("final_round_announcement"),
        )
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


def prepare_for_validate(
    slug: str,
    raw_extraction: dict[str, Any],
    filing: Filing | None = None,
) -> tuple[dict[str, Any], Filing, list[dict[str, Any]]]:
    """Apply every pre-validate transform without writing output."""
    if filing is None:
        filing = load_filing(slug)
    promotion_log = _apply_unnamed_nda_promotions(raw_extraction)
    _canonicalize_order(raw_extraction)
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
    return raw_extraction, filing, promotion_log


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
    run_ts = _now_iso()
    raw_extraction, filing, promotion_log = prepare_for_validate(
        slug, raw_extraction, filing=filing
    )
    result = validate(raw_extraction, filing)
    final = merge_flags(raw_extraction, result.row_flags, result.deal_flags)
    current_rulebook_version = rulebook_version()
    deal_obj = final.setdefault("deal", {})
    deal_obj["rulebook_version"] = current_rulebook_version
    deal_obj["last_run"] = run_ts
    # Attach promotion log to deal object for audit (pipeline-internal field).
    if promotion_log:
        deal_obj["_unnamed_nda_promotions"] = promotion_log
    status, flag_count, notes = summarize(final)
    out_path = write_output(slug, final)
    append_flags_log(slug, final, run_ts=run_ts)
    update_progress(
        slug,
        status,
        flag_count,
        notes,
        current_rulebook_version,
        last_run=run_ts,
    )
    return PipelineResult(
        status=status,
        flag_count=flag_count,
        notes=notes,
        output_path=out_path,
    )
