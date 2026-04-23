#!/usr/bin/env python3
"""Clean prior rerun packets and write final adjudication reports for the 9 reference deals."""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

STATE_PATH = REPO_ROOT / "state" / "progress.json"
EXTRACTIONS_DIR = REPO_ROOT / "output" / "extractions"
REFERENCE_DIR = REPO_ROOT / "reference" / "alex"
SCORING_RESULTS_DIR = REPO_ROOT / "scoring" / "results"
COMPARISON_DIR = REPO_ROOT / "quality_reports" / "comparisons" / "2026-04-21_three-way"
DEFAULT_OUT_DIR = REPO_ROOT / "quality_reports" / "adjudication" / "2026-04-21_rerun"


@dataclass
class Verdict:
    kind: str
    text: str
    rows: list[int] | None = None
    evidence: str | None = None


@dataclass
class DealSpec:
    title: str
    disposition: str
    disposition_label: str
    headline: str
    flag_analysis: str
    recommendations: list[str]
    verdicts: list[Verdict]


ADJUDICATIONS: dict[str, DealSpec] = {
    "medivation": DealSpec(
        title="Medivation",
        disposition="Ship-ready after reference refresh; no extraction blocker remains.",
        disposition_label="ship-ready / reference-refresh",
        headline="The live rerun is materially correct. The remaining divergence burden is driven mainly by Alex reference defects and one low-stakes round-extension inference choice.",
        flag_analysis="All current flags are soft/info only and are the expected mix of date anchoring, placeholder NDA atomization, and inferred round-structure flags. None of them indicate a missing or unsupported current row.",
        recommendations=[
            "Regenerate the reference side for the Sanofi receipt-date correction and Alex's known final-round date errors.",
            "Optional prompt cleanup: keep 2016-08-19/2016-08-20 `Final Round Ext*` rows explicitly low-confidence, since the filing frames them as a best-and-final reset rather than an explicit extension notice.",
        ],
        verdicts=[
            Verdict(
                kind="AI right, Alex wrong",
                rows=[1],
                text="Sanofi's first-contact bid belongs on 2016-04-15, the date Medivation received the letter, not on the letter's 2016-04-13 drafting date.",
            ),
            Verdict(
                kind="AI right, Alex wrong",
                rows=[3],
                text="Pfizer's 2016-05-02 approach is a real `Bidder Interest` row; the filing describes Giordano expressing Pfizer's interest before any NDA or priced bid.",
            ),
            Verdict(
                kind="AI right, Alex wrong",
                rows=[8, 9, 10],
                text="The July 5 disclosure that Medivation had entered into confidentiality agreements with 'several parties, including Sanofi' supports one Sanofi NDA plus two unnamed placeholders under the minimum-supported-count rule; Alex's undated Party A/Party B NDA rows are the older, less faithful encoding.",
            ),
            Verdict(
                kind="AI right, Alex wrong",
                rows=[12, 14, 15, 17, 18, 21],
                text="The rerun's current round-date cluster corrects Alex's mis-dated 2016-08-14 block. The filing supports 2016-07-19 (`Final Round Inf Ann`), 2016-08-08 (`Final Round Inf`), 2016-08-10 (`Final Round Ann`), 2016-08-19 / 2016-08-20 Pfizer bids, and 2016-08-20 execution.",
            ),
            Verdict(
                kind="Both defensible",
                rows=[16, 20],
                text="The added `Final Round Ext Ann` / `Final Round Ext` rows on 2016-08-19 and 2016-08-20 are plausible §K2 inferences from the advisors' 'best and final' reset, but Alex's omission of those extra extension rows is not a blocking error.",
            ),
        ],
    ),
    "imprivata": DealSpec(
        title="Imprivata",
        disposition="Fix and rerun. Two material filing-truth issues remain in the live rerun.",
        disposition_label="fix-and-rerun",
        headline="The rerun gets the broad process right, but the current saved output still misses one pre-process Thoma Bravo approach and regresses on the Sponsor A dropout code.",
        flag_analysis="The soft/info profile is otherwise healthy: date-range collapse on the NDA wave is expected, and the formal-trigger flags on the June 9 round are exactly the sort of borderline cases the rules anticipate.",
        recommendations=[
            "Add the missing June 2015 Thoma Bravo `Bidder Interest` row called out explicitly in the filing.",
            "Change Sponsor A on 2016-06-15 from `DropAtInf` to `DropBelowInf`; the decisive language is Barclays telling Sponsor A the Board would not be interested at essentially the same price.",
        ],
        verdicts=[
            Verdict(
                kind="AI right, Alex wrong",
                rows=[5],
                text="Barclays belongs on 2016-04-15, the date the Board engaged Barclays subject to final paperwork, not on 2016-03-09.",
            ),
            Verdict(
                kind="AI right, Alex wrong",
                rows=[6],
                text="A standalone `Target Sale` row on 2016-05-05 is supported by the Board's decision to launch the outreach process.",
            ),
            Verdict(
                kind="Both wrong",
                rows=[23],
                text="Sponsor A on 2016-06-15 should be `DropBelowInf`, not `DropAtInf`. The filing's deciding action is target-side: Barclays tells Sponsor A that the Board would not be interested at essentially the same valuation.",
            ),
            Verdict(
                kind="Both wrong",
                evidence="Filing p. 28: 'In early 2015, and again in June 2015, representatives of Thoma Bravo informally approached...'",
                text="The live rerun still compresses Thoma Bravo's early-2015 and June-2015 approaches into one pre-2016 row, and Alex does too. The filing narrates two separate pre-March-2016 meetings.",
            ),
            Verdict(
                kind="AI right, Alex wrong",
                rows=[24],
                text="June 24 is a `Final Round Ann`, not Alex's `Final Round Ext Ann` + `Final Round Ann` + `Final Round Ext` bundle. The filing treats the June 24 letters as the first formal-final announcement.",
            ),
            Verdict(
                kind="AI right, Alex wrong",
                rows=[13],
                text="The unnamed fourth financial sponsor NDA/drop pair is supported by the filing's 'four financial sponsors executed confidentiality agreements' language and the later note that one financial sponsor dropped shortly thereafter.",
            ),
        ],
    ),
    "zep": DealSpec(
        title="Zep",
        disposition="Fix and rerun. The current saved extraction still misses material round-structure and final-bid formality details.",
        disposition_label="fix-and-rerun",
        headline="The rerun is far better than the over-fabricated older pipeline, but the live output still under-encodes the phase-1 round structure and mishandles the NMC endgame formality.",
        flag_analysis="The large soft/info count is mostly expected atomization signal: 25 NDA placeholders, bidder-type ambiguity on unnamed buyers, date inference, and cohort-level NDA-without-follow-up flags. Those are not the main problem here.",
        recommendations=[
            "Add the missing 2014-03-27 `Final Round Inf Ann` and 2014-04-14 `Final Round Inf` rows for phase 1.",
            "Retime/reclassify the NMC endgame so the best-and-final formal bid sits on 2015-03-13 rather than on a later document-finalization date.",
        ],
        verdicts=[
            Verdict(
                kind="AI right, Alex wrong",
                rows=[45, 46],
                text="The restart date / first phase-2 bid sequence is correct as saved: NMC re-engages on 2015-02-10 and delivers the $19.25 indication on 2015-02-19. Alex's dating compresses those into the wrong order.",
            ),
            Verdict(
                kind="AI wrong, Alex right",
                evidence="Filing pp. 36-37: March 27 process letter; April 14 IOI deadline.",
                text="The live rerun still omits the phase-1 `Final Round Inf Ann` and `Final Round Inf` structure. Alex is directionally right that those round markers belong in the dataset.",
            ),
            Verdict(
                kind="AI right, Alex wrong",
                evidence="Filing p. 38: the May 7 step is data-room access and continued diligence, not a new final-round deadline.",
                text="Alex's extra 2014-05-07 `Final Round` row is over-coded; the live rerun is right not to create a second formal-round event there.",
            ),
            Verdict(
                kind="Both wrong",
                rows=[49, 50],
                text="The key final formal bid should attach to NMC's 2015-03-13 'best and final' communication. Alex places the formal bid too late, while the live rerun splits it into an informal 2015-03-13 row plus a later formal 2015-03-29 row tied to document finalization.",
            ),
            Verdict(
                kind="AI right, Alex wrong",
                evidence="Filing p. 37: 'twenty-five potential buyers executed confidentiality agreements'.",
                text="The filing's NDA count is 25, not Alex's reduced aggregate count. The live rerun's 25-party phase-1 NDA structure is correct.",
            ),
        ],
    ),
    "providence-worcester": DealSpec(
        title="Providence & Worcester",
        disposition="Ship-ready after reference refresh; the live rerun now matches the filing well.",
        disposition_label="ship-ready / reference-refresh",
        headline="The saved rerun fixed the prior live concerns: it now treats the August 12 G&W endgame as formal, adds `Auction Closed`, and preserves the Party C/26-NDA ambiguity explicitly.",
        flag_analysis="The large info count is almost entirely date-range collapse on the NDA and LOI waves plus routine bid-value-unspecified notes. Only two soft flags remain, both consistent with documented judgment-call territory.",
        recommendations=[
            "Refresh the reference side or document as a judgment call that the filing can support either 25 or 26 NDA rows depending on whether Party C is folded into the headline count.",
            "No extractor prompt change is required based on this rerun; the live output already fixes the earlier formality / auction-close miss.",
        ],
        verdicts=[
            Verdict(
                kind="Both defensible",
                rows=[42, 43],
                text="The current 26-NDA interpretation is defensible because Party C enters separately in early July, while the filing's headline summary elsewhere reports 25 parties. This is a real judgment call, not an error.",
            ),
            Verdict(
                kind="AI right, Alex wrong",
                rows=[63],
                text="`Auction Closed` on 2016-08-12 is the correct target-side closeout row before execution; Alex's side omits that closure event.",
            ),
            Verdict(
                kind="AI right, Alex wrong",
                rows=[61, 64],
                text="The August 12 G&W $25.00 row is correctly formal in the live rerun, and the same-day execution sequence is supported by the filing.",
            ),
            Verdict(
                kind="AI right, Alex wrong",
                rows=[39, 40],
                text="The two June 1 low-IOI exits are better represented as two placeholder rows than as Alex's single aggregated '2 parties' dropout row.",
            ),
            Verdict(
                kind="AI right, Alex wrong",
                rows=[42, 43],
                text="Keeping Party C as a late-entering NDA + bid sequence is faithful to the filing's separate narration of Party C's approach and July 12 IOI.",
            ),
        ],
    ),
    "penford": DealSpec(
        title="Penford",
        disposition="Blocked. Fix and rerun before treating this deal as adjudicated-good.",
        disposition_label="blocked / fix-and-rerun",
        headline="Penford remains the only hard-blocked deal. The live rerun contains real signal, but it still ships six §P-G2 hard failures and one unsupported Ingredion bid row.",
        flag_analysis="This is the one deal where validator hard findings are substantive, not bookkeeping noise. The missing `bid_type_inference_note` content and the unsupported 2014-10-08 bid row are real output problems.",
        recommendations=[
            "Delete the unsupported 2014-10-08 Ingredion bid row currently sitting at row 29.",
            "Populate actual `bid_type_inference_note` values for rows 9, 10, 25, 26 and 32 so the validator sees the evidence that the current reasoning already implies.",
        ],
        verdicts=[
            Verdict(
                kind="AI right, Alex wrong",
                rows=[1, 2, 3, 4],
                text="The 2007 and 2009 stale-prior NDA/drop history belongs in the dataset. Alex's generic unlabeled rows encode the same history less faithfully.",
            ),
            Verdict(
                kind="AI right, Alex wrong",
                rows=[18, 23],
                text="Party B's 2014-09-12 withdrawal and Party F's 2014-09-29 withdrawal are explicit in the filing and should remain in the row set.",
            ),
            Verdict(
                kind="Both wrong",
                rows=[29],
                text="The current 2014-10-08 Ingredion bid row is unsupported: the cited text is only Sidley Austin circulating a revised merger agreement draft. Alex is also wrong because the reference side effectively pulls execution too early.",
            ),
            Verdict(
                kind="AI right, Alex wrong",
                rows=[35],
                text="Execution belongs on 2014-10-14, not on Alex's earlier 2014-10-08 date.",
            ),
            Verdict(
                kind="Both defensible",
                rows=[32],
                text="Party A's 2014-10-14 $16 indication can stay informal despite the filing's 'formal letter' wording, because the content is still a non-binding indication of interest. The current problem is not the row's existence; it is the missing §P-G2 evidence note.",
            ),
        ],
    ),
    "mac-gray": DealSpec(
        title="Mac-Gray",
        disposition="Targeted extractor fix recommended, but the current rerun is otherwise directionally strong.",
        disposition_label="targeted-fix",
        headline="The live rerun is much closer to filing truth than the legacy reference, especially on the start-of-process structure and the treatment of the anonymous NDA cohort. One formality call still needs tightening.",
        flag_analysis="The soft flags are dominated by the 16 NDA-only financial placeholders, which is expected under the current no-synthetic-drop rule. The remaining soft flags are largely agency or contingency judgment calls, not unsupported rows.",
        recommendations=[
            "Reclassify Party B's 2013-09-18 $21.50 row as formal rather than informal.",
            "Keep the no-synthetic-drop treatment for the 16 anonymous NDA signers; that is the current rulebook's intended behavior.",
        ],
        verdicts=[
            Verdict(
                kind="AI right, Alex wrong",
                evidence="Filing pp. 34 / 47 identify the buyer-side entity as CSC ServiceWorks, Inc.",
                text="The deal-level acquirer should be 'CSC ServiceWorks, Inc.', not Alex's provenance string about Pamplona's earlier purchase of CSC.",
            ),
            Verdict(
                kind="AI right, Alex wrong",
                rows=[2, 3],
                text="The Party A start-of-process is better split into 2013-04-05 `Target Interest` and 2013-04-08 `Bidder Interest` than collapsed into Alex's older single-row treatment.",
            ),
            Verdict(
                kind="AI right, Alex wrong",
                evidence="The filing does not narrate 16 individualized 2013-07-25 drops for the anonymous financial NDA signers.",
                text="The current rerun is right not to fabricate per-placeholder drop rows for the 16 anonymous NDA signers. Alex's aggregated drop row is a legacy shorthand, not filing-ground truth.",
            ),
            Verdict(
                kind="AI wrong, Alex right",
                rows=[38],
                text="Party B's $21.50 indication on 2013-09-18 belongs in the formal round, not the informal round. The live rerun under-classifies that row.",
            ),
            Verdict(
                kind="Both defensible",
                rows=[43, 44],
                text="The 2013-09-23 `DropBelowInf` coding for Party A and Party B is defensible from the filing even if Alex or earlier runs used a different drop-family label.",
            ),
        ],
    ),
    "petsmart-inc": DealSpec(
        title="PetSmart",
        disposition="Ship-ready with a judgment-call note on unnamed-party dropout atomization.",
        disposition_label="ship-ready / judgment-call",
        headline="The live rerun closes the biggest gaps from the earlier snapshot: it now captures the Industry Participant prehistory, the public process opening, the 15-NDA wave, and the December final-round structure.",
        flag_analysis="Almost all current flags are expected cohort/placeholder metadata: rough-date inference, unnamed-party group membership, and ordinary bid-shape notes. There is no hard blocker and only one soft flag remains.",
        recommendations=[
            "Keep the current prehistory + round-marker shape; it is materially closer to the filing than the older snapshot.",
            "If Austin wants a stricter anti-synthesis rule for unnamed-party exits, document that as a rulebook choice; the current unnamed-party dropout rows are the main remaining judgment-call axis.",
        ],
        verdicts=[
            Verdict(
                kind="AI right, Alex wrong",
                rows=[1, 5, 6, 7, 8, 9],
                text="The current rerun correctly captures the Industry Participant prehistory and the August 2014 decision to open and publicly announce the sale exploration process.",
            ),
            Verdict(
                kind="AI right, Alex wrong",
                rows=list(range(10, 25)),
                text="The filing supports 15 first-week NDA rows. The live rerun's atomization is faithful to the stated count and better than the older aggregate treatments.",
            ),
            Verdict(
                kind="AI right, Alex wrong",
                rows=list(range(25, 58)),
                text="The current rerun now captures the six-IOI cohort, the November narrowing, the December final-round structure, and the Buyer Group / Bidder 2 endgame bids in a way the older snapshot did not.",
            ),
            Verdict(
                kind="Both defensible",
                rows=[33, 34, 35, 36, 37, 38, 39, 40, 41, 43, 44, 49, 50, 56],
                text="The unnamed-party dropout rows are the main live judgment call. The filing often narrates those exits at the cohort level rather than with individualized names, so the atomized current treatment is plausible but not uniquely compelled.",
            ),
        ],
    ),
    "stec": DealSpec(
        title="sTec",
        disposition="Targeted extractor fix recommended before calling the deal fully clean.",
        disposition_label="targeted-fix",
        headline="The live rerun is much stronger than the earlier snapshot: it now carries the activist rows and the round structure. One dropout-agency call regressed and should be fixed.",
        flag_analysis="The current flag mix is mostly healthy bid-shape and date-inference metadata. The substantive issue is not the validator profile; it is the regression on Company H's dropout agency.",
        recommendations=[
            "Change Company H on 2013-05-23 from `Drop` to `DropBelowInf`.",
            "Keep the current activist and round-structure rows; those changes moved the live rerun closer to the filing.",
        ],
        verdicts=[
            Verdict(
                kind="AI right, Alex wrong",
                rows=[2, 3, 36],
                text="The activist pressure should be split across Balch Hill and Potomac, not collapsed into Balch Hill alone or dropped.",
            ),
            Verdict(
                kind="AI right, Alex wrong",
                rows=[15, 21, 25, 28, 29, 30],
                text="The current rerun now emits the round-structure rows that the older snapshot missed: `Final Round Inf Ann`, `Final Round Inf`, `Final Round Ann`, `Final Round`, `Final Round Ext Ann`, and `Final Round Ext`.",
            ),
            Verdict(
                kind="Both wrong",
                rows=[26],
                text="Company H's 2013-05-23 exit should be target-initiated (`DropBelowInf`), not generic `Drop`. Alex made the same mistake; the filing says BofA told Company H its range was insufficient to move forward.",
            ),
            Verdict(
                kind="AI right, Alex wrong",
                rows=[16],
                text="The single-bound Company D $5.60+ indication is represented correctly as a lower-only informal bid rather than as a collapsed point bid.",
            ),
            Verdict(
                kind="Both defensible",
                rows=[36],
                text="The undated Potomac activist row is a defensible way to preserve the filing's statement that Potomac later joined Balch Hill, even though the exact Potomac join date is not narrated.",
            ),
        ],
    ),
    "saks": DealSpec(
        title="Saks",
        disposition="Hot-fix one row and rerun; otherwise the current row set is strong.",
        disposition_label="hot-fix",
        headline="The live rerun fixes several older issues, but it now emits one post-signing `Sale Press Release` row that should be folded into `Executed`.",
        flag_analysis="The remaining flags are all soft/info only. Most are ordinary range/date flags on the April–July bid sequence; the substantive live issue is the extra 2013-07-29 publicity row after signing.",
        recommendations=[
            "Delete the standalone 2013-07-29 `Sale Press Release` row and fold that publicity into the 2013-07-28 `Executed` row.",
            "Keep the current separation of the April 1 Hudson's Bay meeting from the later priced bid and keep the Company H 7/21 row.",
        ],
        verdicts=[
            Verdict(
                kind="AI right, Alex wrong",
                rows=[3, 7],
                text="The April 1 Hudson's Bay meeting belongs as a separate `Bidder Interest` event from the later week-of-April-15 priced indication. Alex's merged treatment loses that distinction.",
            ),
            Verdict(
                kind="AI right, Alex wrong",
                rows=[21],
                text="Company H's 2013-07-21 aggregate $2.6 billion approach should stay in the dataset under the current unsolicited-first-contact rule; Alex's delete note is stale relative to the live rulebook.",
            ),
            Verdict(
                kind="AI right, Alex wrong",
                rows=[17, 18],
                text="The July 11 joint sponsor bid is correctly encoded as Sponsor E + Sponsor G. Alex's Sponsor A/E label is filing-wrong.",
            ),
            Verdict(
                kind="AI wrong, Alex right",
                rows=[27],
                text="The standalone 2013-07-29 `Sale Press Release` row should not exist. Under the project convention, post-signing publicity is folded into `Executed` rather than emitted as a separate row.",
            ),
            Verdict(
                kind="AI right, Alex wrong",
                evidence="The current rerun omits the Sponsor C / Sponsor D financing-side NDA rows that older try snapshots emitted.",
                text="The live rerun is correct to keep Sponsor C / Sponsor D out of the Saks-side auction row set; those NDAs belong to the separate Saks→Company B financing context, not the inbound Saks sale process.",
            ),
        ],
    ),
}


@dataclass
class DiffSummary:
    markdown_path: Path
    matched_rows: int
    ai_only_rows: int
    alex_only_rows: int
    cardinality_mismatches: int
    field_disagreements: int
    deal_disagreements: int


def rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def load_progress() -> dict[str, Any]:
    return json.loads(STATE_PATH.read_text())


def reference_slugs(progress: dict[str, Any]) -> list[str]:
    return [
        slug
        for slug, meta in progress["deals"].items()
        if meta.get("is_reference")
    ]


def extraction_path(slug: str) -> Path:
    return EXTRACTIONS_DIR / f"{slug}.json"


def reference_path(slug: str) -> Path:
    return REFERENCE_DIR / f"{slug}.json"


def pages_path(slug: str) -> Path:
    return REPO_ROOT / "data" / "filings" / slug / "pages.json"


def comparison_path(slug: str) -> Path:
    return COMPARISON_DIR / f"{slug}_report.md"


def ensure_current_diff(slug: str) -> DiffSummary:
    from scoring.diff import diff_deal, write_results

    extraction = extraction_path(slug)
    reference = reference_path(slug)
    latest_md = None
    latest_js = None

    if SCORING_RESULTS_DIR.exists():
        md_candidates = sorted(SCORING_RESULTS_DIR.glob(f"{slug}_*.md"))
        js_candidates = sorted(SCORING_RESULTS_DIR.glob(f"{slug}_*.json"))
        latest_md = md_candidates[-1] if md_candidates else None
        latest_js = js_candidates[-1] if js_candidates else None

    source_mtime = max(extraction.stat().st_mtime, reference.stat().st_mtime)
    report_data = None
    if latest_md and latest_js and latest_md.stat().st_mtime >= source_mtime and latest_js.stat().st_mtime >= source_mtime:
        report_data = json.loads(latest_js.read_text())
        md_path = latest_md
    else:
        report = diff_deal(slug)
        md_path, js_path = write_results(report)
        report_data = json.loads(js_path.read_text())

    return DiffSummary(
        markdown_path=md_path,
        matched_rows=report_data["matched_rows"],
        ai_only_rows=len(report_data["ai_only_rows"]),
        alex_only_rows=len(report_data["alex_only_rows"]),
        cardinality_mismatches=len(report_data["cardinality_mismatches"]),
        field_disagreements=sum(report_data["field_disagreements"].values()),
        deal_disagreements=len(report_data["deal_disagreements"]),
    )


def summarize_flags(extraction: dict[str, Any]) -> tuple[collections.Counter[str], collections.Counter[str]]:
    severity_counts: collections.Counter[str] = collections.Counter()
    code_counts: collections.Counter[str] = collections.Counter()

    for event in extraction.get("events", []):
        for flag in event.get("flags", []):
            severity_counts[flag.get("severity", "unknown")] += 1
            code_counts[flag.get("code", "unknown")] += 1

    for flag in extraction.get("deal", {}).get("deal_flags", []):
        severity_counts[flag.get("severity", "unknown")] += 1
        code_counts[flag.get("code", "unknown")] += 1

    return severity_counts, code_counts


def format_pages(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def row_descriptor(extraction: dict[str, Any], row_index: int) -> str:
    event = extraction["events"][row_index - 1]
    alias = event.get("bidder_alias")
    note = event.get("bid_note")
    date = event.get("bid_date_precise")
    page = format_pages(event.get("source_page"))
    return f"row {row_index} (`{alias}` · `{note}` · `{date}` · p.{page})"


def render_verdict(extraction: dict[str, Any], verdict: Verdict) -> str:
    parts = [f"- **{verdict.kind}** — "]
    if verdict.rows:
        desc = ", ".join(row_descriptor(extraction, row) for row in verdict.rows)
        parts.append(f"{desc}: {verdict.text}")
    elif verdict.evidence:
        parts.append(f"{verdict.evidence} {verdict.text}")
    else:
        parts.append(verdict.text)
    return "".join(parts)


def common_non_issue_line(slug: str) -> str:
    if slug == "mac-gray":
        return "Capitalization-only `TargetName` noise and `DateEffective=null` are not treated as extraction defects here; the substantive deal-level issue is the acquirer-name correction."
    return "Most deal-level diff noise here is non-substantive: filing-verbatim casing, Alex-side `DateEffective` population, and reference-side naming conventions. Those are not extraction defects unless called out below."


def build_report(slug: str, progress_meta: dict[str, Any], extraction: dict[str, Any], diff: DiffSummary, severity_counts: collections.Counter[str], code_counts: collections.Counter[str], spec: DealSpec) -> str:
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    lines: list[str] = [
        "---",
        f"date: {now[:10]}",
        "status: COMPLETE — adjudicated against filing",
        "owner: Codex",
        f"slug: {slug}",
        f"extraction: {rel(extraction_path(slug))}",
        f"reference: {rel(reference_path(slug))}",
        f"filing_pages: {rel(pages_path(slug))}",
        f"diff_markdown: {rel(diff.markdown_path)}",
        f"prior_comparison: {rel(comparison_path(slug))}" if comparison_path(slug).exists() else "prior_comparison: none",
        "---",
        "",
        f"# {spec.title} — rerun adjudication",
        "",
        "## TL;DR",
        f"- **Disposition:** {spec.disposition}",
        f"- **Current rerun verdict:** {spec.headline}",
        "",
        "## Current rerun snapshot",
        f"- `state/progress.json`: status=`{progress_meta['status']}` · flag_count=`{progress_meta['flag_count']}` · last_run=`{progress_meta['last_run']}`",
        f"- Rows: `{len(extraction['events'])}` · hard=`{severity_counts.get('hard', 0)}` · soft=`{severity_counts.get('soft', 0)}` · info=`{severity_counts.get('info', 0)}`",
        f"- Diff burden vs Alex: matched=`{diff.matched_rows}` · AI-only=`{diff.ai_only_rows}` · Alex-only=`{diff.alex_only_rows}` · cardinality mismatches=`{diff.cardinality_mismatches}` · field disagreements=`{diff.field_disagreements}` · deal-level disagreements=`{diff.deal_disagreements}`",
        f"- Top current flag codes: {', '.join(f'`{code}` × {count}' for code, count in code_counts.most_common(6)) or 'none'}",
        f"- Non-issue note: {common_non_issue_line(slug)}",
        "",
        "## Adjudicated rerun divergences",
    ]
    lines.extend(render_verdict(extraction, verdict) for verdict in spec.verdicts)
    lines.extend(
        [
            "",
            "## Flag Analysis",
            f"- {spec.flag_analysis}",
            "",
            "## Recommendation",
        ]
    )
    lines.extend(f"- {item}" for item in spec.recommendations)
    lines.append("")
    return "\n".join(lines)


def clean_old_materials(out_dir: Path) -> None:
    if not out_dir.exists():
        return
    for path in out_dir.glob("*.md"):
        if path.name == "CUTOFF_REPORT.md":
            continue
        path.unlink()


def write_reports(out_dir: Path) -> None:
    progress = load_progress()
    out_dir.mkdir(parents=True, exist_ok=True)
    clean_old_materials(out_dir)

    packets: list[tuple[str, dict[str, Any], dict[str, Any], DiffSummary, collections.Counter[str], collections.Counter[str], DealSpec]] = []
    for slug in reference_slugs(progress):
        extraction = json.loads(extraction_path(slug).read_text())
        diff = ensure_current_diff(slug)
        severity_counts, code_counts = summarize_flags(extraction)
        spec = ADJUDICATIONS[slug]
        packets.append((slug, progress["deals"][slug], extraction, diff, severity_counts, code_counts, spec))

    for slug, meta, extraction, diff, severity_counts, code_counts, spec in packets:
        (out_dir / f"{slug}.md").write_text(
            build_report(slug, meta, extraction, diff, severity_counts, code_counts, spec)
        )

    master_lines = [
        "---",
        f"date: {dt.datetime.now(dt.timezone.utc).date().isoformat()}",
        "status: COMPLETE — all 9 reference deals adjudicated",
        "owner: Codex",
        f"source_cutoff: {rel(out_dir / 'CUTOFF_REPORT.md')}",
        "---",
        "",
        "# MASTER_RERUN — final rerun adjudication",
        "",
        "## Cleanup",
        "- The previous temporary restart packets in this folder were removed and replaced with completed adjudication reports.",
        "- `CUTOFF_REPORT.md` was kept as historical context only.",
        "",
        "## Per-deal dispositions",
        "| Deal | Disposition | Current status | Hard | Soft | Info | Notes |",
        "|---|---|---|---|---|---|---|",
    ]

    ordered = []
    for slug, meta, extraction, diff, severity_counts, code_counts, spec in packets:
        ordered.append((slug, spec, meta, severity_counts))
        note = spec.disposition
        master_lines.append(
            f"| {slug} | {spec.disposition_label} | {meta['status']} | {severity_counts.get('hard', 0)} | {severity_counts.get('soft', 0)} | {severity_counts.get('info', 0)} | {note} |"
        )

    master_lines.extend(
        [
            "",
            "## System-wide adjudication findings",
            "- `TargetName`/`Acquirer` casing differences and Alex-side `DateEffective` population are mostly reference/converter noise, not extraction defects.",
            "- The live rerun materially improved the earlier snapshot on `providence-worcester`, `petsmart-inc`, and `stec` by adding missing process structure and prehistory.",
            "- The live rerun still needs extraction-side fixes on `imprivata`, `zep`, `penford`, `mac-gray`, `stec`, and `saks` before the reference set can be called stable.",
            "- `penford` is still the only hard-blocked deal; its blocker is real and not just diff noise.",
            "",
            "## Next actions",
            "1. Fix the extraction-side issues called out in `imprivata`, `zep`, `penford`, `mac-gray`, `stec`, and `saks`.",
            "2. Refresh the reference side for the confirmed Alex/converter defects in `medivation`, `providence-worcester`, `mac-gray`, `petsmart-inc`, and `saks`.",
            "3. Re-run the 9-reference set only after those fixes land; that is the earliest point where the 3-clean-run stability clock can restart honestly.",
            "",
            "## Report set",
        ]
    )
    master_lines.extend(
        f"- `{rel(out_dir / f'{slug}.md')}` — {spec.disposition_label}"
        for slug, spec, meta, severity_counts in ordered
    )
    master_lines.append("")

    (out_dir / "MASTER_RERUN.md").write_text("\n".join(master_lines))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        default=str(DEFAULT_OUT_DIR),
        help="Directory where adjudication reports should be written.",
    )
    args = parser.parse_args()
    out_dir = Path(args.out_dir)
    write_reports(out_dir)
    print(f"wrote final adjudication reports to {out_dir}")


if __name__ == "__main__":
    main()
