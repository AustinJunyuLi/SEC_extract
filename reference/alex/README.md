# reference/alex/

**Purpose.** Alex Gorbenko's hand-corrected extractions of 9 deals, converted from `deal_details_Alex_2026.xlsx` into the pipeline's output JSON schema, plus Alex's own annotations on rows he flagged as problematic.

**Frame.** Alex's workbook is a **reference guideline** for the pipeline — not ground truth. The SEC filing is ground truth. Alex is an expert with decades of context, and his rulebook + corrections are the single best source we have for *how* to extract these filings, but he is human, makes judgment calls, and has flagged some of his own rows as wrong. During development, Austin manually re-reads the filing for every AI-vs-Alex divergence and adjudicates on the merits.

## What this folder contains

- `{deal-slug}.json` — one file per reference deal, Alex's rows reshaped to conform to `rules/schema.md`.
- `alex_flagged_rows.json` — rows Alex himself flagged as wrong or that violate a basic structural invariant. Used to contextualize diffs, not to exclude rows from comparison.
- `README.md` — this file.

Deal slugs (match `seeds.csv`):
- `medivation`
- `imprivata`
- `providence-worcester`
- `zep`
- `penford`
- `mac-gray`
- `petsmart-inc`
- `stec`
- `saks`

## How the JSON files are produced

A one-time conversion script (to be written in Stage 2) reads the relevant row ranges from `../deal_details_Alex_2026.xlsx`, maps legacy columns to the resolved pipeline schema, and writes JSON here. The conversion is **faithful to Alex's rows as-is** by default — we don't silently "fix" rows in the conversion. Decisions about which flagged rows to rewrite (vs. copy as-is and let the diff surface the issue) live in `rules/dates.md` §Q.

## Blocking dependencies

The conversion script cannot be written until:

- `rules/schema.md` §R1 is resolved (final column set).
- `rules/schema.md` §N1 is resolved (deal-level vs event-level split).
- `rules/bidders.md` §E3 is resolved (bidder-name canonicalization).
- `rules/dates.md` §A is resolved (BidderID convention).
- `rules/dates.md` §Q is resolved (how to handle Alex-flagged rows in the conversion).

When all five are 🟩, write `scripts/build_reference.py`, run it once, and commit the resulting JSONs.

## Diff contract — NOT a scoring contract

`scoring/diff.py` reads every file in this folder that matches a deal slug and joins against `../../output/extractions/{slug}.json`. Its output is a **diff report for human review**, not a pass/fail grade. Every divergence gets a verdict from Austin after re-reading the filing:

1. **AI right, Alex wrong** — update `alex_flagged_rows.json` with the corrected rule (optional) and move on.
2. **AI wrong, Alex right** — strengthen the relevant rule in `rules/` and re-run the Extractor.
3. **Both defensible** — judgment call; flag in `alex_flagged_rows.json` and ensure the rulebook picks one convention explicitly.
4. **Both wrong** — re-read the filing, decide the right answer, and update both the rule and Alex's row.

The pipeline never sets a `verified` status on its own — only the manual adjudication workflow does.
