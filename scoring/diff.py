"""scoring/diff.py — Diff reporter for AI extractions vs Alex's reference workbook.

Compares a pipeline extraction (output/extractions/{slug}.json) against Alex
Gorbenko's hand-converted reference JSON (reference/alex/{slug}.json). Emits a
row-by-row diff report that Austin reads against the SEC filing itself before
assigning a verdict.

This is NOT a grader. Alex's workbook is a reference guideline, not ground
truth. A divergence is not a bug by default — it's a question for human review.
Every divergence eventually gets one of four verdicts (see reference/alex/README.md):

    1. AI right, Alex wrong
    2. AI wrong, Alex right
    3. Both defensible
    4. Both wrong

USAGE
-----
    python scoring/diff.py --slug medivation
    python scoring/diff.py --all-reference
    python scoring/diff.py --slug medivation --verbose

STATUS
------
Stub. Matching and field-comparison logic intentionally schematic until Stage 1
rulebook decisions are made (see rules/schema.md §R1). The dependencies below
are the shape of the finished diff reporter.

WHAT IT MUST DO (once rulebook is resolved)

    1. Join rows between extraction and Alex's reference on a normalized key:
         (bidder_normalized, event_type_bucket, date_bucket)
       where date_bucket is a window from rules/dates.md §B1 (e.g., ±7 days for
       rough dates, exact for precise).

    2. Per matched row, report each field's agreement / disagreement — NOT a
       numeric score. A mismatch is a question, not a point deduction. Fields
       to surface:
         - bid_note (event type)
         - bidder_name, bidder_type
         - event_date, date_is_approximate
         - bid value fields (point / range / bound)
         - bid_type (formal / informal) — highest-attention mismatch
         - source_quote / source_page from the AI (Alex has no source_quote)

    3. Per unmatched row:
         - In extraction but not Alex:  AI added a row. Check its source_quote;
                                        Alex may have missed it, or the AI may
                                        be hallucinating.
         - In Alex but not extraction:  AI missed a row Alex has. Re-read the
                                        filing to see which side is right.

    4. Flag rows listed in reference/alex/alex_flagged_rows.json with a note:
       "Alex flagged this row himself — expect the AI to diverge." Do NOT
       exclude them from the diff; they are the MOST informative rows to review.

    5. Emit a diff report to scoring/results/{slug}_{timestamp}.json and a
       human-readable markdown summary to scoring/results/{slug}_{timestamp}.md
       with one section per divergence and space for Austin's verdict.

    6. Hard-invariant violations from rules/invariants.md §P-D* are reported
       separately — those ARE objective bugs in the extraction (or bugs in the
       rulebook). They are not scored as a pass rate; they are listed by
       invariant with the offending rows.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
REFERENCE_DIR = REPO_ROOT / "reference" / "alex"
EXTRACTION_DIR = REPO_ROOT / "output" / "extractions"
ALEX_FLAGGED_ROWS = REFERENCE_DIR / "alex_flagged_rows.json"
RESULTS_DIR = REPO_ROOT / "scoring" / "results"


@dataclass
class DiffReport:
    slug: str
    matched_rows: int = 0
    ai_only_rows: int = 0
    alex_only_rows: int = 0
    field_disagreements: dict[str, int] = field(default_factory=dict)
    hard_invariant_violations: list[dict[str, Any]] = field(default_factory=list)
    alex_flagged_rows_in_diff: int = 0
    divergences: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def load_json(path: Path) -> dict[str, Any]:
    with path.open() as f:
        return json.load(f)


def normalize_bidder(name: str | None) -> str | None:
    """Bidder-name normalization for matching.

    TODO: rules/bidders.md §E3 resolution determines canonical form.
    """
    if name is None:
        return None
    return name.strip().lower().replace(" ", "_")


def date_bucket(event_date: str | None, is_approximate: bool) -> str:
    """Date bucketing for join key.

    TODO: rules/dates.md §B1 resolution defines bucket width (e.g., ±7 days
    for rough dates, exact for precise).
    """
    raise NotImplementedError("pending rules/dates.md §B1")


def compare_field(field_name: str, extracted: Any, alex: Any) -> dict[str, Any]:
    """Per-field agreement / disagreement report (NOT a numeric score).

    Returns a dict describing whether the values match, and if not, what the
    divergence looks like. Partial-match logic (e.g., "bid value within 0.5%")
    is for triage only — it tells Austin which divergences to look at first,
    not whether the AI "passed."

    TODO: field-comparison rules depend on rules/schema.md §R1 (final column
    set) and per-column semantics.
    """
    raise NotImplementedError("pending rules/schema.md §R1")


def diff_deal(slug: str, verbose: bool = False) -> DiffReport:
    """Run diff for one reference deal.

    Currently a stub — returns an empty report with a status note.
    """
    reference_path = REFERENCE_DIR / f"{slug}.json"
    extraction_path = EXTRACTION_DIR / f"{slug}.json"

    if not reference_path.exists():
        return DiffReport(
            slug=slug,
            notes=[f"reference file not found: {reference_path}"],
        )
    if not extraction_path.exists():
        return DiffReport(
            slug=slug,
            notes=[f"extraction file not found: {extraction_path}"],
        )

    reference = load_json(reference_path)  # noqa: F841 — used once diff is implemented
    extraction = load_json(extraction_path)  # noqa: F841
    flagged = load_json(ALEX_FLAGGED_ROWS) if ALEX_FLAGGED_ROWS.exists() else {"deals": {}}
    flagged_count = len(flagged.get("deals", {}).get(slug, []))

    return DiffReport(
        slug=slug,
        alex_flagged_rows_in_diff=flagged_count,
        notes=[
            "diff reporter not yet implemented — pending Stage 1 rulebook decisions",
            "required: rules/schema.md §R1, rules/dates.md §B1, rules/bidders.md §E3",
        ],
    )


def diff_all_reference() -> list[DiffReport]:
    reports = []
    if REFERENCE_DIR.exists():
        for ref_file in sorted(REFERENCE_DIR.glob("*.json")):
            if ref_file.stem.startswith("_") or ref_file.stem == "alex_flagged_rows":
                continue
            reports.append(diff_deal(ref_file.stem))
    return reports


def format_report(r: DiffReport) -> str:
    lines = [
        f"=== {r.slug} ===",
        f"  matched rows:               {r.matched_rows}",
        f"  AI-only rows:               {r.ai_only_rows}",
        f"  Alex-only rows:             {r.alex_only_rows}",
        f"  hard-invariant violations:  {len(r.hard_invariant_violations)}",
        f"  Alex-flagged rows in diff:  {r.alex_flagged_rows_in_diff}",
        f"  field disagreements:        {sum(r.field_disagreements.values())}",
    ]
    for note in r.notes:
        lines.append(f"  NOTE: {note}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diff pipeline extractions against Alex's reference workbook."
    )
    parser.add_argument("--slug", help="Single deal slug (e.g. medivation).")
    parser.add_argument(
        "--all-reference",
        action="store_true",
        help="Diff every reference deal.",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if args.all_reference:
        reports = diff_all_reference()
        if not reports:
            print("no reference deals found under reference/alex/")
            return
        for r in reports:
            print(format_report(r))
            print()
    elif args.slug:
        r = diff_deal(args.slug, verbose=args.verbose)
        print(format_report(r))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
