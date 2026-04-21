---
date: 2026-04-21
status: COMPLETE
owner: Claude (orchestrator) + 9 parallel general-purpose agents
related:
  - quality_reports/plans/2026-04-20_pipeline-comparison.md
  - quality_reports/session_logs/2026-04-20_pipeline-comparison-and-gptpro-bundle.md
---

# Three-way pipeline comparison: bids_pipeline vs bids_try vs Alex (2026-04-21)

## Goal

Adjudicate every meaningful divergence between three candidate extractions of the
9 reference deals against the SEC filing (ground truth) and Alex's instructions
(reference, not oracle). Identify which pipeline is closer to filing-truth on
which dimensions, where each pipeline is wrong, and what rule/prompt changes
follow.

## Sources

| Source | Path | Role |
|---|---|---|
| **Raw SEC filings** | `/Users/austinli/bids_try/data/filings/{slug}/raw.md` (+ `pages.json`, `manifest.json`, `raw.htm`) | **Ground truth** |
| **Alex's PDF rulebook** | `/Users/austinli/bids_try/reference/CollectionInstructions_Alex_2026.pdf` | Rule reference (Alex's red text = his additions, most important) |
| **Alex's hand-corrected workbook** | `/Users/austinli/bids_try/reference/deal_details_Alex_2026.xlsx` | Reference extraction, not oracle |
| **bids_pipeline output (older)** | `/Users/austinli/Projects/bids_pipeline/debug/2026-04-17/boundary-map-implementation/reference9_post_bundle/results_reference9_post_bundle.xlsx` | Candidate A |
| **bids_try output (current)** | `/Users/austinli/bids_try/output/ai_workbook_alex_format.csv` | Candidate B |
| **Local rulebook** | `/Users/austinli/bids_try/rules/*.md` (schema, events, bidders, bids, dates, invariants) | Codified rules |

Per-deal CSV slices already extracted to:
`/Users/austinli/bids_try/quality_reports/comparisons/2026-04-21_three-way/inputs/{slug}_{alex|bids_pipeline|bids_try}.csv`

## Per-deal row counts (sanity-check baseline)

| Deal | Alex | bids_pipeline | bids_try |
|---|---|---|---|
| medivation | 16 | 22 | 20 |
| imprivata | 29 | 34 | 26 |
| zep | 23 | 80 | 48 |
| providence-worcester | 36 | 64 | 63 |
| penford | 25 | 33 | 26 |
| mac-gray | 34 | 65 | 45 |
| petsmart-inc | 53 | 55 | 41 |
| stec | 28 | 42 | 31 |
| saks | 25 | 28 | 29 |

## Adjudication framework (per CLAUDE.md)

Each divergence is one of four verdicts:

1. **AI correct, Alex wrong** — record as AI-identified correction; do NOT change rulebook.
2. **AI wrong, Alex correct** — flag for prompt/rule update.
3. **Both correct, different interpretations** — judgment call; document so AI and Alex converge.
4. **Both wrong** — update rulebook against filing text.

(For three-way comparison we extend: "AI-A correct vs AI-B correct vs Alex correct" combinations are recorded with which source got it right against the filing.)

## Approach: 9 parallel deal-specific agents

Each agent (general-purpose, Opus) gets one deal and produces a structured comparison report. The prompt for each agent:

1. Reads `rules/*.md` (concise, ~7 files) to understand the schema and invariants.
2. Reads the raw filing (`data/filings/{slug}/raw.md`) and treats it as ground truth.
3. Reads the three extractions (`inputs/{slug}_{alex|bids_pipeline|bids_try}.csv`).
4. Reads Alex's reference JSON (`reference/alex/{slug}.json`) for cross-check.
5. Builds a deal-level comparison and an event-by-event timeline.
6. For every meaningful divergence, adjudicates against the filing.
7. Writes a structured markdown report to:
   `quality_reports/comparisons/2026-04-21_three-way/{slug}_report.md`

Agent isolation: each gets only its own deal. No cross-deal state. (Aligns with CLAUDE.md: reset context per deal.)

## Aggregation step

After all 9 agents return, the orchestrator (this session) writes a master report at:
`quality_reports/comparisons/2026-04-21_three-way/MASTER_REPORT.md`

The master report cross-cuts:
- Which pipeline is generally closer to filing-truth (per dimension: completeness, atomization, dates, bidder typing, bid values)
- Systemic issues per pipeline (e.g., Zep 80 rows in bids_pipeline = over-atomization?)
- Common rule gaps where both pipelines diverge from filing
- Specific prompt/rule fixes recommended

## Out of scope (this pass)

- Re-running either pipeline.
- Touching `rules/*.md` to incorporate findings (next session, after Austin reviews).
- Re-generating Alex reference JSONs.

## Success criteria

- 9 deal reports written, each with: row-level comparison, divergence table with verdicts, summary findings.
- Master report identifies the top-N systemic issues per pipeline.
- Austin can read the reports and decide which pipeline to ship and which rule changes to make.
