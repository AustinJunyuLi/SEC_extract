"""scoring/diff.py — Diff reporter: AI extractions vs Alex's reference.

Compares `output/extractions/{slug}.json` against `reference/alex/{slug}.json`
and prints a human-review report by default. NOT a grader. Every divergence eventually
gets one of four verdicts from Austin (see `reference/alex/README.md`):

    1. AI right, Alex wrong       3. Both defensible
    2. AI wrong, Alex right       4. Both wrong

USAGE
-----
    python scoring/diff.py --slug medivation
    python scoring/diff.py --all-reference
    python scoring/diff.py --slug medivation --write
"""

from __future__ import annotations

import argparse
import datetime
import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
REFERENCE_DIR = REPO_ROOT / "reference" / "alex"
EXTRACTION_DIR = REPO_ROOT / "output" / "extractions"
ALEX_FLAGGED_ROWS = REFERENCE_DIR / "alex_flagged_rows.json"
RESULTS_DIR = REPO_ROOT / "scoring" / "results"

# Fields compared on matched rows. `bid_type` is starred because it's the
# research-critical formal-vs-informal call.
COMPARE_EVENT_FIELDS = [
    "bid_type",
    "bidder_type",
    "drop_initiator",
    "drop_reason_class",
    "final_round_announcement",
    "final_round_extension",
    "final_round_informal",
    "press_release_subject",
    "invited_to_formal_round",
    "submitted_formal_bid",
    "bid_value",
    "bid_value_pershare",
    "bid_value_lower",
    "bid_value_upper",
    "bid_value_unit",
    "bid_date_rough",
]

COMPARE_DEAL_FIELDS = [
    "TargetName", "Acquirer", "DateAnnounced",
    "DateEffective", "auction", "all_cash",
]

FORMAL_STAGE_STATUS_FIELDS: frozenset[str] = frozenset({
    "invited_to_formal_round",
    "submitted_formal_bid",
})
CURRENT_DROP_INITIATORS: frozenset[str] = frozenset({"bidder", "target"})

# AI-only fields whose absence on Alex's side is expected and should NOT
# appear as divergences.
AI_ONLY_EVENT_FIELDS = {
    "source_quote", "source_page", "process_phase", "role",
    "exclusivity_days", "consideration_components",
}

# Bid-notes emitted by the AI as inferred metadata that are not present
# in Alex's reference. Stripped from the AI side before comparison so they
# don't appear as spurious "AI-only row" mismatches.
#
# DropSilent: per rules/events.md §I1, the AI emits one DropSilent row only
# for true post-NDA filing silence. Alex's reference predates this policy and
# represents true silent signers as bare NDA rows, so those AI DropSilent rows
# have no Alex counterpart by design. If a filtered DropSilent matches an
# Alex-only explicit Drop for the same bidder, diff_deal records a diagnostic
# because the filing likely narrated a bidder-specific outcome.
AI_ONLY_BID_NOTES: frozenset[str] = frozenset({"DropSilent"})
BUYER_GROUP_ATOMIZATION_FLAG_CODES: frozenset[str] = frozenset({
    "buyer_group_constituent",
    "consortium_drop_split",
})


@dataclass
class DiffReport:
    slug: str
    matched_rows: int = 0
    ai_only_rows: list[dict[str, Any]] = field(default_factory=list)
    alex_only_rows: list[dict[str, Any]] = field(default_factory=list)
    cardinality_mismatches: list[dict[str, Any]] = field(default_factory=list)
    field_disagreements: dict[str, int] = field(default_factory=dict)
    deal_disagreements: list[dict[str, Any]] = field(default_factory=list)
    divergences: list[dict[str, Any]] = field(default_factory=list)
    alex_flagged_hits: list[dict[str, Any]] = field(default_factory=list)
    review_blockers: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Normalizers and join keys
# ---------------------------------------------------------------------------

def normalize_bidder(alias: str | None) -> str | None:
    """Lowercase + collapse whitespace, strip common suffixes.

    Per `rules/bidders.md` §E3, cross-row canonicalization is the AI's job.
    For diffing we match on `bidder_alias` (per-row verbatim label from the
    filing) rather than the canonical `bidder_NN`, because the AI and Alex
    may use different canonical mappings.
    """
    if alias is None:
        return None
    s = unicodedata.normalize("NFKC", alias).strip().lower()
    s = s.translate(str.maketrans({
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u201f": '"',
    }))
    suffixes = (
        " llc.", " corp.", " inc.", " ltd.", " plc.",
        " llc", " corp", " inc", " ltd", " plc", ",",
    )
    while True:
        for suffix in suffixes:
            if not s.endswith(suffix):
                continue
            s = s[:-len(suffix)].rstrip()
            break
        else:
            break
    return " ".join(s.split())


def _row_flag_codes(ev: dict[str, Any]) -> set[str]:
    return {f.get("code") for f in (ev.get("flags") or []) if isinstance(f, dict)}


def _is_buyer_group_atomization(
    ai_bucket: list[dict[str, Any]],
    alex_bucket: list[dict[str, Any]],
) -> bool:
    if not ai_bucket or not alex_bucket or len(ai_bucket) <= len(alex_bucket):
        return False
    return any(
        _row_flag_codes(ev) & BUYER_GROUP_ATOMIZATION_FLAG_CODES
        for ev in ai_bucket
    )


def join_key(ev: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """Match key for AI ↔ Alex events.

    (normalized_alias, bid_note, bid_date_precise). None compares equal to
    None so undated rows join. Secondary loose matches are tried for rows
    that fail this key.
    """
    return (
        normalize_bidder(ev.get("bidder_alias")),
        ev.get("bid_note"),
        ev.get("bid_date_precise"),
    )


def loose_key(ev: dict[str, Any]) -> tuple[str | None, str | None]:
    """Fallback key when dates differ: (alias, bid_note)."""
    return (normalize_bidder(ev.get("bidder_alias")), ev.get("bid_note"))


def _diagnostic_bidder_labels(
    ev: dict[str, Any],
    registry: dict[str, Any] | None,
) -> set[str]:
    labels: set[str] = set()
    alias = normalize_bidder(ev.get("bidder_alias"))
    if alias is not None:
        labels.add(alias)

    bidder_name = ev.get("bidder_name")
    if not bidder_name or not registry:
        return labels

    entry = registry.get(bidder_name)
    if not isinstance(entry, dict):
        return labels

    resolved_name = normalize_bidder(entry.get("resolved_name"))
    if resolved_name is not None:
        labels.add(resolved_name)
    for observed_alias in entry.get("aliases_observed") or []:
        observed = normalize_bidder(observed_alias)
        if observed is not None:
            labels.add(observed)
    return labels


def _same_bidder_for_diagnostic(
    ai_ev: dict[str, Any],
    alex_ev: dict[str, Any],
    ai_registry: dict[str, Any] | None = None,
    alex_registry: dict[str, Any] | None = None,
) -> bool:
    ai_labels = _diagnostic_bidder_labels(ai_ev, ai_registry)
    alex_labels = _diagnostic_bidder_labels(alex_ev, alex_registry)
    return bool(ai_labels & alex_labels)


# ---------------------------------------------------------------------------
# Field comparison
# ---------------------------------------------------------------------------

def _values_equal(a: Any, b: Any) -> bool:
    if a == b:
        return True
    # Numeric fuzz: within 0.1% counts as equal.
    try:
        af, bf = float(a), float(b)
    except (TypeError, ValueError):
        return False
    if af == bf:
        return True
    denom = max(abs(af), abs(bf), 1e-9)
    return abs(af - bf) / denom < 1e-3


def compare_field(name: str, ai_val: Any, alex_val: Any) -> dict[str, Any] | None:
    """Return a divergence dict or None if values agree.

    Treats Alex's absence of AI-only structured fields as expected.
    """
    if name in AI_ONLY_EVENT_FIELDS and alex_val in (None, "", [], {}):
        return None
    if _values_equal(ai_val, alex_val):
        return None
    return {"field": name, "ai": ai_val, "alex": alex_val}


def _is_ai_only_formal_stage_enrichment(name: str, ai_val: Any, alex_val: Any) -> bool:
    # Intentional comparator policy: Alex-null means "source workbook lacks
    # this newer field." Validator checks, not the reference diff, enforce
    # whether the AI populated it only on proper informal Bid rows.
    return (
        name in FORMAL_STAGE_STATUS_FIELDS
        and ai_val in (True, False)
        and alex_val is None
    )


def _is_reference_drop_classification_underspecification(
    name: str,
    ai_val: Any,
    alex_val: Any,
) -> bool:
    if name == "drop_initiator":
        # Intentional: suppress only Alex's explicit "unknown" initiator.
        # A null initiator on a Drop row means the converted reference omitted
        # a required field and should stay visible in the diff.
        return ai_val in CURRENT_DROP_INITIATORS and alex_val == "unknown"
    if name == "drop_reason_class":
        return ai_val is not None and alex_val is None
    return False


def _is_reference_bid_value_placement_noise(
    name: str,
    ai_ev: dict[str, Any],
    alex_ev: dict[str, Any],
) -> bool:
    """Suppress old-workbook per-share placement noise.

    Alex's source workbook often stores a per-share bid value in the legacy
    aggregate `bid_value` column. Current output stores that value in
    `bid_value_pershare` with `bid_value_unit="USD_per_share"`. A true numeric
    mismatch stays visible on `bid_value`; this only removes the duplicate
    field noise caused by the old column placement.
    """
    if ai_ev.get("bid_note") != "Bid":
        return False

    ai_pershare = ai_ev.get("bid_value_pershare")
    alex_legacy_value = alex_ev.get("bid_value")
    if ai_pershare in (None, "") or alex_legacy_value in (None, ""):
        return False

    if name == "bid_value":
        return (
            ai_ev.get("bid_value") in (None, "")
            and _values_equal(ai_pershare, alex_legacy_value)
        )
    if name == "bid_value_pershare":
        return alex_ev.get("bid_value_pershare") in (None, "")
    if name == "bid_value_unit":
        return (
            ai_ev.get("bid_value_unit") == "USD_per_share"
            and alex_ev.get("bid_value_unit") in (None, "")
        )
    return False


# ---------------------------------------------------------------------------
# Diff core
# ---------------------------------------------------------------------------

def _load_flagged_rows() -> dict[str, list[dict[str, Any]]]:
    if not ALEX_FLAGGED_ROWS.exists():
        return {}
    data = json.loads(ALEX_FLAGGED_ROWS.read_text())
    return data.get("deals", {})


def _alex_flag_note_for(slug: str, xlsx_row: int | None,
                         flagged: dict[str, list[dict[str, Any]]]) -> str | None:
    if xlsx_row is None:
        return None
    for item in flagged.get(slug, []):
        if item["xlsx_row"] == xlsx_row:
            return f"Alex flagged this row himself: {item['reason']}"
    return None


def diff_events(slug: str, ai_events: list[dict[str, Any]],
                alex_events: list[dict[str, Any]]) -> DiffReport:
    r = DiffReport(slug=slug)
    flagged = _load_flagged_rows()

    def _record_cardinality_mismatch(
        *,
        scope: str,
        code: str = "cardinality_mismatch",
        bucket_key: dict[str, Any],
        ai_bucket: list[dict[str, Any]],
        alex_bucket: list[dict[str, Any]],
        matched_ai_ids: set[int],
        matched_alex_ids: set[int],
    ) -> None:
        matched_ai_ids.update(id(ev) for ev in ai_bucket)
        matched_alex_ids.update(id(ev) for ev in alex_bucket)
        mismatch = {
            "type": "cardinality_mismatch",
            "code": code,
            "match_scope": scope,
            "bucket_key": bucket_key,
            "ai_count": len(ai_bucket),
            "alex_count": len(alex_bucket),
            "ai_rows": ai_bucket,
            "alex_rows": alex_bucket,
        }
        r.cardinality_mismatches.append(mismatch)
        r.divergences.append(mismatch)

    # Build indexes. Allow duplicate keys by appending to a list.
    def _index(evs: list[dict[str, Any]]) -> dict[Any, list[dict[str, Any]]]:
        out: dict[Any, list[dict[str, Any]]] = {}
        for ev in evs:
            out.setdefault(join_key(ev), []).append(ev)
        return out

    ai_idx = _index(ai_events)
    alex_idx = _index(alex_events)

    matched_ai_ids: set[int] = set()
    matched_alex_ids: set[int] = set()
    formal_stage_enrichment_counts: dict[str, int] = {}
    drop_classification_underspecified_counts: dict[str, int] = {}
    bid_value_placement_counts: dict[str, int] = {}

    # Primary pass: exact join.
    for key, ai_bucket in ai_idx.items():
        alex_bucket = alex_idx.get(key, [])
        if ai_bucket and alex_bucket and len(ai_bucket) != len(alex_bucket):
            atomized_group = _is_buyer_group_atomization(ai_bucket, alex_bucket)
            _record_cardinality_mismatch(
                scope="buyer_group_atomization" if atomized_group else "exact_join_key",
                code="atomization_vs_aggregation" if atomized_group else "cardinality_mismatch",
                bucket_key={
                    "bidder_alias_normalized": key[0],
                    "bid_note": key[1],
                    "bid_date_precise": key[2],
                },
                ai_bucket=ai_bucket,
                alex_bucket=alex_bucket,
                matched_ai_ids=matched_ai_ids,
                matched_alex_ids=matched_alex_ids,
            )
            continue

        multi_match = len(ai_bucket) == len(alex_bucket) > 1
        for ai_ev, alex_ev in zip(ai_bucket, alex_bucket):
            matched_ai_ids.add(id(ai_ev))
            matched_alex_ids.add(id(alex_ev))
            r.matched_rows += 1
            divs = []
            for fname in COMPARE_EVENT_FIELDS:
                if _is_ai_only_formal_stage_enrichment(
                    fname,
                    ai_ev.get(fname),
                    alex_ev.get(fname),
                ):
                    formal_stage_enrichment_counts[fname] = (
                        formal_stage_enrichment_counts.get(fname, 0) + 1
                    )
                    continue
                if (
                    ai_ev.get("bid_note") == "Drop"
                    and _is_reference_drop_classification_underspecification(
                        fname,
                        ai_ev.get(fname),
                        alex_ev.get(fname),
                    )
                ):
                    drop_classification_underspecified_counts[fname] = (
                        drop_classification_underspecified_counts.get(fname, 0) + 1
                    )
                    continue
                if _is_reference_bid_value_placement_noise(fname, ai_ev, alex_ev):
                    bid_value_placement_counts[fname] = (
                        bid_value_placement_counts.get(fname, 0) + 1
                    )
                    continue
                d = compare_field(fname, ai_ev.get(fname), alex_ev.get(fname))
                if d is not None:
                    divs.append(d)
                    r.field_disagreements[fname] = r.field_disagreements.get(fname, 0) + 1
            flag_note = _alex_flag_note_for(slug, alex_ev.get("_xlsx_row"), flagged)
            if divs or flag_note:
                r.divergences.append({
                    "type": "field_mismatch",
                    "join_key": {
                        "bidder_alias_ai": ai_ev.get("bidder_alias"),
                        "bidder_alias_alex": alex_ev.get("bidder_alias"),
                        "bid_note": key[1],
                        "bid_date_precise": key[2],
                    },
                    "ai_BidderID": ai_ev.get("BidderID"),
                    "alex_BidderID": alex_ev.get("BidderID"),
                    "field_divergences": divs,
                    "alex_self_flag": flag_note,
                    "bucket_match_mode": "order_dependent_zip" if multi_match else "exact_single",
                })
                if flag_note:
                    r.alex_flagged_hits.append(r.divergences[-1])

    # Residual grouped mismatch: if unmatched rows remain on both sides for the
    # same event type and counts differ, emit a single bucket-level mismatch
    # before attempting looser alias-based recovery. This catches atomized-vs-
    # aggregated patterns where alias/date granularity differs too much for the
    # exact join to be meaningful.
    still_unmatched_ai = [e for e in ai_events if id(e) not in matched_ai_ids]
    still_unmatched_alex = [e for e in alex_events if id(e) not in matched_alex_ids]
    residual_ai_by_note: dict[str | None, list[dict[str, Any]]] = {}
    residual_alex_by_note: dict[str | None, list[dict[str, Any]]] = {}
    for ev in still_unmatched_ai:
        residual_ai_by_note.setdefault(ev.get("bid_note"), []).append(ev)
    for ev in still_unmatched_alex:
        residual_alex_by_note.setdefault(ev.get("bid_note"), []).append(ev)
    for bid_note, ai_bucket in residual_ai_by_note.items():
        alex_bucket = residual_alex_by_note.get(bid_note, [])
        if not ai_bucket or not alex_bucket:
            continue
        if len(ai_bucket) == len(alex_bucket):
            continue
        atomized_group = _is_buyer_group_atomization(ai_bucket, alex_bucket)
        _record_cardinality_mismatch(
            scope="buyer_group_atomization" if atomized_group else "residual_bid_note",
            code="atomization_vs_aggregation" if atomized_group else "cardinality_mismatch",
            bucket_key={
                "bid_note": bid_note,
                "ai_dates": sorted({ev.get("bid_date_precise") for ev in ai_bucket}, key=lambda v: (v is None, v or "")),
                "alex_dates": sorted({ev.get("bid_date_precise") for ev in alex_bucket}, key=lambda v: (v is None, v or "")),
            },
            ai_bucket=ai_bucket,
            alex_bucket=alex_bucket,
            matched_ai_ids=matched_ai_ids,
            matched_alex_ids=matched_alex_ids,
        )

    # Fallback: try loose (alias, note) match for still-unmatched rows.
    still_unmatched_ai = [e for e in ai_events if id(e) not in matched_ai_ids]
    still_unmatched_alex = [e for e in alex_events if id(e) not in matched_alex_ids]

    loose_alex: dict[Any, list[dict[str, Any]]] = {}
    for ev in still_unmatched_alex:
        loose_alex.setdefault(loose_key(ev), []).append(ev)

    for ai_ev in list(still_unmatched_ai):
        bucket = loose_alex.get(loose_key(ai_ev), [])
        if bucket:
            alex_ev = bucket.pop(0)
            matched_ai_ids.add(id(ai_ev))
            matched_alex_ids.add(id(alex_ev))
            r.matched_rows += 1
            r.divergences.append({
                "type": "loose_match_date_mismatch",
                "join_key_loose": {
                    "bidder_alias": ai_ev.get("bidder_alias"),
                    "bid_note": ai_ev.get("bid_note"),
                },
                "ai_date": ai_ev.get("bid_date_precise"),
                "alex_date": alex_ev.get("bid_date_precise"),
                "ai_BidderID": ai_ev.get("BidderID"),
                "alex_BidderID": alex_ev.get("BidderID"),
            })

    # Residual unmatched rows.
    r.ai_only_rows = [e for e in ai_events if id(e) not in matched_ai_ids]
    r.alex_only_rows = [e for e in alex_events if id(e) not in matched_alex_ids]

    # Record Alex-only rows that Alex himself flagged.
    for alex_ev in r.alex_only_rows:
        flag_note = _alex_flag_note_for(slug, alex_ev.get("_xlsx_row"), flagged)
        if flag_note:
            r.alex_flagged_hits.append({
                "type": "alex_only",
                "bidder_alias": alex_ev.get("bidder_alias"),
                "bid_note": alex_ev.get("bid_note"),
                "alex_self_flag": flag_note,
            })

    if formal_stage_enrichment_counts:
        detail = ", ".join(
            f"{field}={count}"
            for field, count in sorted(formal_stage_enrichment_counts.items())
        )
        r.notes.append(
            "Suppressed AI-only formal-stage status enrichment field(s) where "
            f"Alex is null: {detail}."
        )
    if drop_classification_underspecified_counts:
        detail = ", ".join(
            f"{field}={count}"
            for field, count in sorted(drop_classification_underspecified_counts.items())
        )
        r.notes.append(
            "Suppressed source-workbook drop classification underspecification "
            "where AI has current-schema detail and Alex has unknown initiator "
            f"or null reason class: {detail}."
        )
    if bid_value_placement_counts:
        detail = ", ".join(
            f"{field}={count}"
            for field, count in sorted(bid_value_placement_counts.items())
        )
        r.notes.append(
            "Suppressed source-workbook per-share bid value placement noise "
            f"from the legacy bid_value column: {detail}."
        )
    if r.matched_rows == 0 and r.cardinality_mismatches:
        r.review_blockers.append({
            "code": "zero_matched_rows_with_cardinality_mismatch",
            "severity": "review_blocker",
            "reason": (
                "Reference diff has zero matched rows and "
                f"{len(r.cardinality_mismatches)} cardinality mismatch bucket(s)."
            ),
        })

    return r


def diff_deal_fields(ai_deal: dict[str, Any], alex_deal: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for fname in COMPARE_DEAL_FIELDS:
        if (
            fname == "DateEffective"
            and ai_deal.get(fname) is None
            and alex_deal.get(fname) not in (None, "")
        ):
            continue
        d = compare_field(fname, ai_deal.get(fname), alex_deal.get(fname))
        if d is not None:
            out.append(d)
    return out


def _drop_silent_vs_explicit_drop_warnings(
    filtered_ai_events: list[dict[str, Any]],
    alex_only_rows: list[dict[str, Any]],
    ai_registry: dict[str, Any] | None = None,
    alex_registry: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    alex_drop_rows = [
        ev for ev in alex_only_rows
        if ev.get("bid_note") == "Drop"
    ]
    used_alex_indexes: set[int] = set()
    warnings = []

    for ai_ev in filtered_ai_events:
        if ai_ev.get("bid_note") != "DropSilent":
            continue
        for idx, alex_ev in enumerate(alex_drop_rows):
            if idx in used_alex_indexes:
                continue
            if not _same_bidder_for_diagnostic(
                ai_ev,
                alex_ev,
                ai_registry,
                alex_registry,
            ):
                continue
            used_alex_indexes.add(idx)
            warnings.append({
                "type": "drop_silent_vs_explicit_drop",
                "code": "drop_silent_vs_explicit_drop",
                "ai_BidderID": ai_ev.get("BidderID"),
                "alex_BidderID": alex_ev.get("BidderID"),
                "bidder_alias_ai": ai_ev.get("bidder_alias"),
                "bidder_alias_alex": alex_ev.get("bidder_alias"),
                "bidder_name_ai": ai_ev.get("bidder_name"),
                "bidder_name_alex": alex_ev.get("bidder_name"),
                "ai_row": ai_ev,
                "alex_row": alex_ev,
                "reason": (
                    "AI emitted DropSilent but Alex has explicit Drop for the "
                    "same bidder; review the filing for narrated bidder-specific "
                    "inactivity, withdrawal, rejection, or process exit."
                ),
            })
            break
    return warnings


def diff_deal(slug: str) -> DiffReport:
    reference_path = REFERENCE_DIR / f"{slug}.json"
    extraction_path = EXTRACTION_DIR / f"{slug}.json"

    if not reference_path.exists():
        return DiffReport(slug=slug, notes=[f"reference missing: {reference_path}"])
    if not extraction_path.exists():
        return DiffReport(slug=slug, notes=[f"extraction missing: {extraction_path}"])

    ref = json.loads(reference_path.read_text())
    ext = json.loads(extraction_path.read_text())

    ai_events_raw = ext.get("events", [])
    filtered_ai_events = [
        ev for ev in ai_events_raw
        if ev.get("bid_note") in AI_ONLY_BID_NOTES
    ]
    ai_events = [
        ev for ev in ai_events_raw
        if ev.get("bid_note") not in AI_ONLY_BID_NOTES
    ]

    r = diff_events(slug, ai_events, ref.get("events", []))
    r.deal_disagreements = diff_deal_fields(ext.get("deal", {}), ref.get("deal", {}))

    drop_silent_warnings = _drop_silent_vs_explicit_drop_warnings(
        filtered_ai_events,
        r.alex_only_rows,
        ext.get("deal", {}).get("bidder_registry"),
        ref.get("deal", {}).get("bidder_registry"),
    )
    if drop_silent_warnings:
        r.divergences.extend(drop_silent_warnings)
        r.notes.append(
            "DropSilent-vs-Drop warnings: "
            f"{len(drop_silent_warnings)} filtered AI DropSilent row(s) matched "
            "Alex explicit Drop rows for the same bidder. Review source text for "
            "a narrated outcome; narrated outcomes must be explicit Drop."
        )

    if filtered_ai_events:
        r.notes.append(
            f"Filtered {len(filtered_ai_events)} AI-side row(s) with bid_note in "
            f"{sorted(AI_ONLY_BID_NOTES)} per §I1 (inferred metadata not "
            f"present in Alex's reference)."
        )
    return r


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _format_divergence_md(div: dict[str, Any]) -> str:
    lines: list[str] = []
    dtype = div.get("type", "?")
    if dtype == "field_mismatch":
        jk = div["join_key"]
        lines.append(
            f"### Matched: `{jk['bidder_alias_alex']}` · `{jk['bid_note']}` · {jk['bid_date_precise']}"
        )
        lines.append(f"- AI BidderID {div['ai_BidderID']} · Alex BidderID {div['alex_BidderID']}")
        if div.get("bucket_match_mode") == "order_dependent_zip":
            lines.append("- Matching note: equal-cardinality multi-row bucket; field comparison is order-dependent.")
        if div.get("alex_self_flag"):
            lines.append(f"- ⚠️  {div['alex_self_flag']}")
        for fd in div.get("field_divergences", []):
            lines.append(f"  - **{fd['field']}** — ai=`{fd['ai']!r}` · alex=`{fd['alex']!r}`")
        lines.append("- Verdict: `[ ] ai-right  [ ] alex-right  [ ] both-defensible  [ ] both-wrong`")
    elif dtype == "loose_match_date_mismatch":
        jk = div["join_key_loose"]
        lines.append(f"### Date mismatch: `{jk['bidder_alias']}` · `{jk['bid_note']}`")
        lines.append(
            f"- AI date `{div['ai_date']}` · Alex date `{div['alex_date']}` "
            f"(AI id {div['ai_BidderID']}, Alex id {div['alex_BidderID']})"
        )
        lines.append("- Verdict: `[ ] ai-right  [ ] alex-right  [ ] both-defensible  [ ] both-wrong`")
    elif dtype == "drop_silent_vs_explicit_drop":
        lines.append(
            "### DropSilent-vs-Drop diagnostic: "
            f"`{div.get('bidder_alias_ai')}` · `{div.get('bidder_alias_alex')}`"
        )
        lines.append(
            f"- AI DropSilent BidderID {div.get('ai_BidderID')} · "
            f"Alex Drop BidderID {div.get('alex_BidderID')}"
        )
        lines.append(f"- Diagnostic: {div.get('reason')}")
        lines.append("- Verdict: `[ ] true-silence  [ ] narrated-drop  [ ] both-defensible  [ ] both-wrong`")
    elif dtype == "cardinality_mismatch":
        jk = div["bucket_key"]
        if div.get("match_scope") == "buyer_group_atomization":
            lines.append(f"### Atomization vs aggregation: `{jk['bid_note']}`")
            if "bid_date_precise" in jk:
                lines.append(f"- Date `{jk.get('bid_date_precise')}`")
            else:
                lines.append(f"- AI dates `{jk.get('ai_dates')}` · Alex dates `{jk.get('alex_dates')}`")
        elif div.get("match_scope") == "exact_join_key":
            lines.append(
                f"### Cardinality mismatch: `{jk['bidder_alias_normalized']}` · `{jk['bid_note']}` · {jk['bid_date_precise']}"
            )
        else:
            lines.append(f"### Cardinality mismatch: `{jk['bid_note']}` residual bucket")
            lines.append(f"- AI dates `{jk.get('ai_dates')}` · Alex dates `{jk.get('alex_dates')}`")
        lines.append(f"- AI rows `{div['ai_count']}` · Alex rows `{div['alex_count']}`")
        lines.append(
            f"- AI BidderIDs `{[ev.get('BidderID') for ev in div['ai_rows']]}`"
        )
        lines.append(
            f"- Alex BidderIDs `{[ev.get('BidderID') for ev in div['alex_rows']]}`"
        )
        if div.get("match_scope") == "buyer_group_atomization":
            lines.append("- Comparison note: AI atomized identifiable buyer-group constituents; Alex appears aggregated.")
        elif div.get("match_scope") == "exact_join_key":
            lines.append("- No field-level pairing attempted; counts differ within the exact bucket.")
        else:
            lines.append("- No field-level pairing attempted; counts differ within this residual event-type bucket.")
        lines.append("- Verdict: `[ ] ai-right  [ ] alex-right  [ ] both-defensible  [ ] both-wrong`")
    return "\n".join(lines)


def _format_unmatched_md(ev: dict[str, Any], side: str) -> str:
    label = "AI-only (added by AI)" if side == "ai" else "Alex-only (AI missed)"
    lines = [
        f"### {label}: `{ev.get('bidder_alias')}` · `{ev.get('bid_note')}` · {ev.get('bid_date_precise')}",
        f"- BidderID {ev.get('BidderID')} · bid_type `{ev.get('bid_type')}` · "
        f"per-share `{ev.get('bid_value_pershare')}`",
    ]
    if side == "ai" and ev.get("source_quote"):
        q = ev["source_quote"]
        q_short = (q[:200] + "…") if isinstance(q, str) and len(q) > 200 else q
        lines.append(f"- source_page `{ev.get('source_page')}`: {q_short!r}")
    lines.append("- Verdict: `[ ] ai-right  [ ] alex-right  [ ] both-defensible  [ ] both-wrong`")
    return "\n".join(lines)


def format_report_md(r: DiffReport) -> str:
    ts = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds") + "Z"
    L: list[str] = [
        f"# Diff report — {r.slug}",
        f"_Generated {ts}. This is a human-review aid, not a grade._",
        "",
        "## Summary",
        f"- matched rows: **{r.matched_rows}**",
        f"- AI-only rows: **{len(r.ai_only_rows)}**",
        f"- Alex-only rows: **{len(r.alex_only_rows)}**",
        f"- cardinality mismatches: **{len(r.cardinality_mismatches)}**",
        f"- deal-level disagreements: **{len(r.deal_disagreements)}**",
        f"- field disagreements: **{sum(r.field_disagreements.values())}** "
        f"({', '.join(f'{k}={v}' for k,v in sorted(r.field_disagreements.items())) or 'none'})",
        f"- Alex-self-flagged rows hit: **{len(r.alex_flagged_hits)}** "
        "(expected to diverge; see reference/alex/alex_flagged_rows.json)",
        "",
    ]
    if r.notes:
        L.append("## Notes")
        L.extend(f"- {n}" for n in r.notes)
        L.append("")
    if r.review_blockers:
        L.append("## Review blockers")
        L.extend(f"- **{item['code']}**: {item['reason']}" for item in r.review_blockers)
        L.append("")
    if r.deal_disagreements:
        L.append("## Deal-level disagreements")
        for fd in r.deal_disagreements:
            L.append(f"- **{fd['field']}** — ai=`{fd['ai']!r}` · alex=`{fd['alex']!r}`")
        L.append("")
    if r.divergences:
        L.append("## Divergences and diagnostics")
        for div in r.divergences:
            L.append(_format_divergence_md(div))
            L.append("")
    if r.ai_only_rows:
        L.append("## AI-only rows")
        for ev in r.ai_only_rows:
            L.append(_format_unmatched_md(ev, "ai"))
            L.append("")
    if r.alex_only_rows:
        L.append("## Alex-only rows")
        for ev in r.alex_only_rows:
            L.append(_format_unmatched_md(ev, "alex"))
            L.append("")
    return "\n".join(L).rstrip() + "\n"


def format_report_txt(r: DiffReport) -> str:
    return (
        f"=== {r.slug} ===\n"
        f"  matched rows:                {r.matched_rows}\n"
        f"  AI-only rows:                {len(r.ai_only_rows)}\n"
        f"  Alex-only rows:              {len(r.alex_only_rows)}\n"
        f"  cardinality mismatches:      {len(r.cardinality_mismatches)}\n"
        f"  review blockers:             {len(r.review_blockers)}\n"
        f"  deal-level disagreements:    {len(r.deal_disagreements)}\n"
        f"  Alex-flagged rows in diff:   {len(r.alex_flagged_hits)}\n"
        f"  field disagreements:         {sum(r.field_disagreements.values())}"
        + (f"  [{', '.join(f'{k}={v}' for k,v in sorted(r.field_disagreements.items()))}]" if r.field_disagreements else "")
        + ("\n  " + "\n  ".join(f"NOTE: {n}" for n in r.notes) if r.notes else "")
    )


def write_results(r: DiffReport) -> tuple[Path, Path]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    md = RESULTS_DIR / f"{r.slug}.md"
    js = RESULTS_DIR / f"{r.slug}.json"
    md.write_text(format_report_md(r))
    js.write_text(json.dumps({
        "slug": r.slug,
        "matched_rows": r.matched_rows,
        "ai_only_rows": r.ai_only_rows,
        "alex_only_rows": r.alex_only_rows,
        "cardinality_mismatches": r.cardinality_mismatches,
        "field_disagreements": r.field_disagreements,
        "deal_disagreements": r.deal_disagreements,
        "divergences": r.divergences,
        "alex_flagged_hits": r.alex_flagged_hits,
        "review_blockers": r.review_blockers,
        "notes": r.notes,
    }, indent=2, default=str))
    return md, js


def diff_all_reference() -> list[DiffReport]:
    reports = []
    if REFERENCE_DIR.exists():
        for ref_file in sorted(REFERENCE_DIR.glob("*.json")):
            if ref_file.stem.startswith("_") or ref_file.stem == "alex_flagged_rows":
                continue
            reports.append(diff_deal(ref_file.stem))
    return reports


def _has_content(r: DiffReport) -> bool:
    return bool(
        r.matched_rows
        or r.ai_only_rows
        or r.alex_only_rows
        or r.cardinality_mismatches
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", help="Single deal slug (e.g. medivation).")
    parser.add_argument("--all-reference", action="store_true")
    parser.add_argument("--write", action="store_true",
                        help="Also write markdown/json reports under scoring/results/.")
    args = parser.parse_args()

    if args.all_reference:
        reports = diff_all_reference()
        if not reports:
            print("no reference deals found under reference/alex/")
            return
        for r in reports:
            print(format_report_txt(r))
            if args.write and _has_content(r):
                md, js = write_results(r)
                print(f"  -> {md.relative_to(REPO_ROOT)}")
            print()
    elif args.slug:
        r = diff_deal(args.slug)
        print(format_report_txt(r))
        if args.write and _has_content(r):
            md, js = write_results(r)
            print(f"wrote {md.relative_to(REPO_ROOT)}")
            print(f"wrote {js.relative_to(REPO_ROOT)}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
