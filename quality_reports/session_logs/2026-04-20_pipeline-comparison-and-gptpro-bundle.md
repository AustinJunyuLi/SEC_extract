# Session Log — 2026-04-20

## Goal

Cross-pipeline architecture comparison between this repo (`bids_try`) and a
sibling pipeline at `~/Projects/bids_pipeline`, followed by packaging both
pipelines as a GPT Pro review bundle so an external model can design an
ideal merged architecture independently.

## Key context

- Both pipelines target the same research problem: extract row-per-event
  M&A takeover-auction tables from SEC merger filings at research-grade
  quality, for 9 reference deals + 392 target deals.
- `bids_try` uses Claude Code subagent orchestration + Python-only
  validator (flag-only, never mutates) + mandatory `source_quote` /
  `source_page` on every row.
- `bids_pipeline` uses direct Anthropic/OpenAI SDK + two-pass LLM
  (extract + conditional evidence-repair) + auto-repairing validator
  (cohort expansion, NDA gap-fill, code-owned formality classification).
- Neither pipeline is authoritative; they're independent attempts at the
  same problem.

## Work done

### 1. Systematic comparison

- Deployed two Explore subagents in parallel, each with identical
  14-section structured report template.
- Synthesized findings into `quality_reports/plans/2026-04-20_pipeline-comparison.md`.
- Dimension-by-dimension table + deep dive on the fundamental
  architectural bet (flag-only vs auto-repair) + recommendation sketch
  for merged v2.

### 2. GPT Pro review bundle

- Built round_2 bundle at `diagnosis/gptpro/2026-04-20/round_2/`.
- 172 files, 566 KB zipped.
- Both pipelines included verbatim, side by side.
- Large artifacts excluded: raw EDGAR filings (21 MB + 310 MB),
  scoring/results adjudication archive (12 MB), legacy xlsx.
- Both CLAUDE.md files excluded (operator instructions dominate;
  salvageable content superseded by rules/, prompt templates, and
  new `PROJECT_CONTEXT.md`).
- My comparison memo deliberately withheld to avoid framing the
  external reviewer's design.

### 3. Prompt design

- `PROMPT.md` explicitly frees GPT Pro from any obligation to reconcile
  the two pipelines, preserve components, or defer to project-owner
  preferences. Design task stated only in terms of target properties
  (reliability, efficiency, robustness) and output requirements
  (walkthrough, architecture, critique, risks, roadmap).

## Artifacts

- `quality_reports/plans/2026-04-20_pipeline-comparison.md` — internal
  comparison memo (not shared with GPT Pro).
- `diagnosis/gptpro/2026-04-20/round_2/codebase.zip` — bundle.
- `diagnosis/gptpro/2026-04-20/round_2/PROMPT.md` — upload prompt.
- `diagnosis/gptpro/2026-04-20/round_2/staging/` — (remaining staging dir
  can be removed; zip and prompt are the deliverables).

## Open questions / next steps

- Await GPT Pro reply; save to
  `diagnosis/gptpro/2026-04-20/round_2_reply.md` and produce meeting
  notes.
- Decide whether to adopt any of the four cross-pipeline grafts
  proposed in the comparison memo (§10): Phase A authority rule,
  cohort expansion + gap-fill as Python transforms, regex price
  cross-check as §P-R6, raw-extraction save-before-canonicalize.
- Stage 3 follow-ups from CLAUDE.md (unchanged): providence soft-flag
  policy, NDA atomization-vs-aggregation, `bidder_type.public` inference
  in `build_reference.py`.
