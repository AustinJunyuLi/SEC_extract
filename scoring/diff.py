"""scoring/diff.py — Diff reporter: AI extractions vs Alex's reference.

Compares `output/extractions/{slug}.json` against `reference/alex/{slug}.json`
and emits a human-review report. NOT a grader. Every divergence eventually
gets one of four verdicts from Austin (see `reference/alex/README.md`):

    1. AI right, Alex wrong       3. Both defensible
    2. AI wrong, Alex right       4. Both wrong

USAGE
-----
    python scoring/diff.py --slug medivation
    python scoring/diff.py --all-reference
    python scoring/diff.py --slug medivation --verbose
"""

from __future__ import annotations

import argparse
import datetime
import json
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
    "bid_value_pershare",
    "bid_value_lower",
    "bid_value_upper",
    "bid_value_unit",
    "bid_date_rough",
]

COMPARE_DEAL_FIELDS = [
    "TargetName", "Acquirer", "DateAnnounced", "DateEffective",
    "auction", "all_cash",
]

# AI-only fields whose absence on Alex's side is expected and should NOT
# appear as divergences.
AI_ONLY_EVENT_FIELDS = {
    "source_quote", "source_page", "process_phase", "role",
    "exclusivity_days", "financing_contingent", "highly_confident_letter",
    "process_conditions_note", "cash_per_share", "stock_per_share",
    "contingent_per_share", "consideration_components", "aggregate_basis",
}


@dataclass
class DiffReport:
    slug: str
    matched_rows: int = 0
    ai_only_rows: list[dict[str, Any]] = field(default_factory=list)
    alex_only_rows: list[dict[str, Any]] = field(default_factory=list)
    field_disagreements: dict[str, int] = field(default_factory=dict)
    deal_disagreements: list[dict[str, Any]] = field(default_factory=list)
    divergences: list[dict[str, Any]] = field(default_factory=list)
    alex_flagged_hits: list[dict[str, Any]] = field(default_factory=list)
    hard_invariant_violations: list[dict[str, Any]] = field(default_factory=list)
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
    s = alias.strip().lower()
    for suffix in (" inc.", " inc", " corp.", " corp", " ltd.", " ltd",
                   " llc", " plc", ","):
        s = s.rstrip(suffix)
    return " ".join(s.split())


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

    # Primary pass: exact join.
    for key, ai_bucket in ai_idx.items():
        alex_bucket = alex_idx.get(key, [])
        for ai_ev, alex_ev in zip(ai_bucket, alex_bucket):
            matched_ai_ids.add(id(ai_ev))
            matched_alex_ids.add(id(alex_ev))
            r.matched_rows += 1
            divs = []
            for fname in COMPARE_EVENT_FIELDS:
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
                })
                if flag_note:
                    r.alex_flagged_hits.append(r.divergences[-1])

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

    return r


def diff_deal_fields(ai_deal: dict[str, Any], alex_deal: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for fname in COMPARE_DEAL_FIELDS:
        d = compare_field(fname, ai_deal.get(fname), alex_deal.get(fname))
        if d is not None:
            out.append(d)
    return out


def diff_deal(slug: str, verbose: bool = False) -> DiffReport:
    reference_path = REFERENCE_DIR / f"{slug}.json"
    extraction_path = EXTRACTION_DIR / f"{slug}.json"

    if not reference_path.exists():
        return DiffReport(slug=slug, notes=[f"reference missing: {reference_path}"])
    if not extraction_path.exists():
        return DiffReport(slug=slug, notes=[f"extraction missing: {extraction_path}"])

    ref = json.loads(reference_path.read_text())
    ext = json.loads(extraction_path.read_text())

    r = diff_events(slug, ext.get("events", []), ref.get("events", []))
    r.deal_disagreements = diff_deal_fields(ext.get("deal", {}), ref.get("deal", {}))
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
    if r.deal_disagreements:
        L.append("## Deal-level disagreements")
        for fd in r.deal_disagreements:
            L.append(f"- **{fd['field']}** — ai=`{fd['ai']!r}` · alex=`{fd['alex']!r}`")
        L.append("")
    if r.divergences:
        L.append("## Matched-row divergences")
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
        f"  deal-level disagreements:    {len(r.deal_disagreements)}\n"
        f"  Alex-flagged rows in diff:   {len(r.alex_flagged_hits)}\n"
        f"  field disagreements:         {sum(r.field_disagreements.values())}"
        + (f"  [{', '.join(f'{k}={v}' for k,v in sorted(r.field_disagreements.items()))}]" if r.field_disagreements else "")
        + ("\n  " + "\n  ".join(f"NOTE: {n}" for n in r.notes) if r.notes else "")
    )


def write_results(r: DiffReport) -> tuple[Path, Path]:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    md = RESULTS_DIR / f"{r.slug}_{ts}.md"
    js = RESULTS_DIR / f"{r.slug}_{ts}.json"
    md.write_text(format_report_md(r))
    js.write_text(json.dumps({
        "slug": r.slug,
        "matched_rows": r.matched_rows,
        "ai_only_rows": r.ai_only_rows,
        "alex_only_rows": r.alex_only_rows,
        "field_disagreements": r.field_disagreements,
        "deal_disagreements": r.deal_disagreements,
        "divergences": r.divergences,
        "alex_flagged_hits": r.alex_flagged_hits,
        "hard_invariant_violations": r.hard_invariant_violations,
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", help="Single deal slug (e.g. medivation).")
    parser.add_argument("--all-reference", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--no-write", action="store_true",
                        help="Skip writing scoring/results/*; print to stdout only.")
    args = parser.parse_args()

    if args.all_reference:
        reports = diff_all_reference()
        if not reports:
            print("no reference deals found under reference/alex/")
            return
        for r in reports:
            print(format_report_txt(r))
            if not args.no_write and r.matched_rows + len(r.ai_only_rows) + len(r.alex_only_rows) > 0:
                md, js = write_results(r)
                print(f"  -> {md.relative_to(REPO_ROOT)}")
            print()
    elif args.slug:
        r = diff_deal(args.slug, verbose=args.verbose)
        print(format_report_txt(r))
        if not args.no_write and r.matched_rows + len(r.ai_only_rows) + len(r.alex_only_rows) > 0:
            md, js = write_results(r)
            print(f"wrote {md.relative_to(REPO_ROOT)}")
            print(f"wrote {js.relative_to(REPO_ROOT)}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
