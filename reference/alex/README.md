# reference/alex/

**Purpose.** Alex Gorbenko's hand-corrected extractions of 9 deals, converted from `deal_details_Alex_2026.xlsx` into the current comparison-reference JSON shape, plus Alex's own annotations on rows he flagged as problematic.

**Frame.** Alex's workbook is a **reference guideline** for the pipeline — not ground truth. The SEC filing is ground truth. Alex is an expert with decades of context, and his rulebook + corrections are the single best source we have for *how* to extract these filings, but he is human, makes judgment calls, and has flagged some of his own rows as wrong. During development, Austin manually re-reads the filing for every AI-vs-Alex divergence and adjudicates on the merits.

## What this folder contains

- `{deal-slug}.json` — one file per reference deal, Alex's rows reshaped for
  AI-vs-Alex comparison. These are not full live extractor outputs: Alex's
  workbook does not contain filing `source_quote` / `source_page` evidence, and
  the comparator treats them as a reference projection.
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

`scripts/build_reference.py` reads the relevant row ranges from
`../deal_details_Alex_2026.xlsx`, maps source workbook columns to the resolved
comparison-reference schema, and writes JSON here.

Current behavior:
- applies the §Q overrides defined in the `scripts/build_reference.py`
  module docstring (Saks deletions, Zep expansion, Mac-Gray / Medivation
  renumbering, Medivation atomization of aggregated "Several parties"
  rows, Acquirer rewrites for sponsor-backed deals, and Executed-row
  atomization for consortium deals);
- converts bid rows to the §C3 form (`bid_note="Bid"` + `bid_type`);
- reassigns `BidderID` per the resolved `§A1`–`§A3` sequencing rules;
- preserves provenance by attaching info flags where Alex's workbook had a
  self-flagged or structurally repaired row.

The conversion is therefore **Alex's structured reference intent after the
resolved normalizations**, not a literal dump of the workbook cells.

## When to regenerate

Re-run the converter whenever:
- `scripts/build_reference.py` changes;
- a rules change affects reference-side serialization;
- a newly adjudicated Alex error should be reflected in the generated
  reference JSONs rather than left as workbook noise.

Typical commands:

```bash
python scripts/build_reference.py --all
python scripts/build_reference.py --slug medivation --dump
```

## Diff contract — NOT a scoring contract

`scoring/diff.py` reads every file in this folder that matches a deal slug and joins against `../../output/extractions/{slug}.json`. Its output is a **diff for human review**, not a pass/fail grade. The default mode prints to stdout; use `--write` only when a temporary markdown/JSON artifact is explicitly needed. Every divergence gets a verdict from Austin after re-reading the filing:

1. **AI right, Alex wrong** — update `alex_flagged_rows.json` with the corrected rule (optional) and move on.
2. **AI wrong, Alex right** — strengthen the relevant rule in `rules/` and re-run the Extractor.
3. **Both defensible** — judgment call; flag in `alex_flagged_rows.json` and ensure the rulebook picks one convention explicitly.
4. **Both wrong** — re-read the filing, decide the right answer, and update both the rule and Alex's row.

The pipeline never sets a `verified` status on its own — only the manual adjudication workflow does.
