# Session log — 2026-04-20 reference-set full rerun + CSV export

**Date:** 2026-04-20
**Branch:** `main`
**Goal:** Fresh end-to-end extraction of all 9 reference deals, then export
one CSV in Alex's xlsx workbook format.

---

## What ran

1. **9 parallel Extractor subagents** (one per reference deal), each spawned
   in a fresh context with instructions to read the full rulebook and
   filing and write raw JSON to `/tmp/rerun-20260420/{slug}.raw.json`.
2. **`run.py --slug X --raw-extraction {slug}.raw.json --no-commit`** for
   each deal → Python validator → `output/extractions/{slug}.json` +
   `state/progress.json` + `state/flags.jsonl` updated.
3. **`scripts/export_alex_csv.py`** (new) → single
   `output/ai_workbook_alex_format.csv` with 37 columns (35 matching
   Alex's xlsx header + 2 AI audit columns: `source_page`, `source_quote`).

Several of the subagents overstepped their per-deal scope during this
session and re-ran the finalize step on other deals or generated their
own CSV/xlsx workbooks. The per-deal raw JSONs in `/tmp/rerun-20260420/`
and the final `output/extractions/*.json` and
`output/ai_workbook_alex_format.csv` are authoritative. Rogue duplicates
were removed before commit.

---

## Final per-deal statuses (from `state/progress.json`)

| Deal                   | Status      | Hard | Soft | Info |
|------------------------|-------------|-----:|-----:|-----:|
| medivation             | passed      | 0    | 15   | 10   |
| imprivata              | passed      | 0    | 12   | 19   |
| zep                    | validated   | 6    | 63   | 29   |
| providence-worcester   | passed      | 0    | 47   | 38   |
| penford                | validated   | 1    | 17   | 12   |
| mac-gray               | validated   | 3    | 46   | 30   |
| petsmart-inc           | validated   | 21   | 26   | 46   |
| stec                   | validated   | 8    | 8    | 10   |
| saks                   | passed      | 0    | 16   | 25   |

**Passed (0 hard):** medivation, imprivata, saks, providence-worcester
**Validated (≥1 hard):** zep (6), penford (1), mac-gray (3),
petsmart-inc (21), stec (8)

Hard flag categories Austin needs to adjudicate:

- **`source_quote_not_in_page`** — dominant (majority of hard flags
  across zep, stec, mac-gray, petsmart-inc). Extractor paraphrased or
  truncated quotes so the NFKC-normalized `source_quote` isn't a pure
  substring of the cited page. Page cites likely correct; quote
  fidelity is the defect.
- **`phase_termination_missing`** — penford, mac-gray, stec. Phase 0
  stale-prior processes with no formal Terminated/Restart row. Often a
  legitimate extraction of reality ("discussions faded"), not a rule
  violation.
- **`stale_prior_too_recent`** (mac-gray) — §P-L2 180-day gap fails
  because the extractor placed BofA's Oct 2012 – May 2013 engagement
  in phase 0 against an Apr 2013 phase-1 start. Austin should decide
  whether to narrow the phase-0 scope.
- **`bid_without_preceding_nda`** (zep phase 2 rows) — extractor did
  not emit a phase-2 NDA row for a bidder who continued into the
  restarted auction. Either filing doesn't narrate the re-sign or
  rulebook should permit NDA carryover across phases.

These are extractor-output quality issues, not rulebook drift. No rule
changes shipped this session. Exit clock decision is Austin's.

---

## CSV export

- **Path:** `output/ai_workbook_alex_format.csv`
- **Script:** `scripts/export_alex_csv.py`
- **Shape:** 329 rows × 37 columns

Column layout: first 35 columns mirror Alex's
`deal_details_Alex_2026.xlsx` header in the same order
(`index, TargetName, gvkeyT, DealNumber, Acquirer, gvkeyA, DateAnnounced,
DateEffective, DateFiled, FormType, URL, Auction, BidderID, BidderName,
bidder_type_financial, bidder_type_strategic, bidder_type_mixed,
bidder_type_nonUS, bidder_type_note, bid_value, bid_value_pershare,
bid_value_lower, bid_value_upper, bid_value_unit, multiplier, bid_type,
bid_date_precise, bid_date_rough, bid_note, all_cash, additional_note,
cshoc, comments_1, comments_2, comments_3`). Two audit columns appended
at the end — `source_page`, `source_quote` — preserving the pipeline's
§R3 non-negotiable that every row cites the filing.

Conventions applied by the exporter:
- Bid rows: Alex's Case-2 xlsx form (`bid_note="NA"`,
  `bid_type="Informal"/"Formal"`), reversing the pipeline's §C3
  unified `bid_note="Bid"` emission.
- Deal-level Compustat fields (`gvkeyT`, `DealNumber`, `gvkeyA`,
  `DateFiled`, `FormType`) lifted from the first xlsx row of each
  deal's range in `reference/deal_details_Alex_2026.xlsx`.
- `URL` lifted from `state/progress.json`.
- Our nested `bidder_type` object (`{base, non_us, public}`) expanded
  to Alex's 5 xlsx columns; note synthesized as (e.g.) `"Non-US public S"`.
- `comments_1/2/3`: deal `comments` / `bid_type_inference_note` / flag
  summary respectively.
- `cshoc` and `multiplier` left as `NA` — not in the pipeline's schema.

Row counts per deal:

| Deal | Rows |
|---|---:|
| Medivation, Inc. | 20 |
| Imprivata, Inc. | 26 |
| Zep Inc. | 48 |
| Providence and Worcester Railroad Company | 63 |
| Penford Corporation | 26 |
| MAC-GRAY CORPORATION | 45 |
| PetSmart, Inc. | 41 |
| sTec, Inc. | 31 |
| Saks Incorporated | 29 |

---

## Files changed

- `output/extractions/{all 9 deals}.json` — overwritten with fresh extractions
- `state/progress.json`, `state/flags.jsonl` — updated
- `output/ai_workbook_alex_format.csv` — new, replayable via
  `python3 scripts/export_alex_csv.py`
- `scripts/export_alex_csv.py` — new
- `quality_reports/session_logs/2026-04-20_reference-rerun-e2e.md` — this file

Untracked/uncommitted diagnosis artifacts carried over from earlier
sessions (`diagnosis/gptpro/2026-04-20/round_2/`, `round_3/`,
`quality_reports/plans/2026-04-20_pipeline-comparison.md`) were left
untouched.

---

## Exit clock

With 4/9 passed (0 hard) and 5/9 validated (≥1 hard), the strict
reading is **0/3 unchanged-rulebook clean runs**. No rulebook changes
shipped in this rerun — the hard flags are extractor-quality issues,
not rulebook defects. Whether this run counts as 1/3 clean-on-
rulebook toward the exit gate is Austin's judgment call.

Suggested next actions:
1. Spot-check the `source_quote_not_in_page` flags — if the quotes are
   off by whitespace/Unicode only, a renormalization pass closes them.
   If they're paraphrased, the extractor prompt needs reinforcement on
   "verbatim substring" discipline.
2. Decide whether to accept phase-0 `phase_termination_missing` as a
   permitted shape (update §P-S3 to carve out phase 0) or re-extract.
3. Adjudicate zep's phase-2 `bid_without_preceding_nda` against the
   filing text.

---
**Context compaction (manual) at 12:51**
Check git log and quality_reports/plans/ for current state.
