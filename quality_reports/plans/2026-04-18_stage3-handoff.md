# Stage 3 Handoff — Read This First

**Intended reader.** A fresh Claude session opened to build Stage 3 of the M&A extraction pipeline. Read this file, then `CLAUDE.md`, then stop and confirm the plan with Austin before writing code.

**Date:** 2026-04-18
**Prior state:** Stages 1 + 2 complete. Stage 3 is open.

---

## TL;DR

The rulebook, the reference answer key, and the diff harness are all built. Your job is to make the pipeline **actually extract**: read the Medivation SEC filing text, emit events conforming to `rules/schema.md` §R1, and get a diff report green(ish) enough that Austin can manually adjudicate what's left.

---

## What is already done

- **Stage 1** (commit `f57a2aa`). All 54 rulebook questions resolved. See `rules/*.md`.
- **Stage 2** (commits `3241785`, `9dda10a`, `0b0d4d7`).
  - `scripts/build_reference.py` → `reference/alex/{slug}.json` for 9 deals.
  - `scoring/diff.py` end-to-end on Medivation with `scripts/synth_extraction.py`.
- SEC filings already fetched: `data/filings/{slug}/raw.md` + `pages.json` + `manifest.json` for all 9 reference deals. **Do not re-fetch.**

## What Stage 3 needs to build

1. **`run.py:run_pipeline(deal)`** (currently `NotImplementedError`).
   - Load `prompts/extract.md` + `rules/*.md` + `data/filings/{slug}/raw.md`.
   - Invoke Extractor agent (Claude Agent SDK) → candidate event rows with `source_quote` + `source_page`.
   - Load `prompts/validate.md` + `rules/invariants.md` + candidate rows + filing text.
   - Invoke Validator agent → final rows + flags.
   - Return `PipelineResult(status, flag_count, notes, rows, flags)`.
   - Write `output/extractions/{slug}.json`, append `state/flags.jsonl`, update `state/progress.json`.

2. **Run on Medivation first** (simplest archetype per `CLAUDE.md` rollout order).
   - `scoring/diff.py --slug medivation` reveals AI-vs-Alex divergences.
   - Austin reads `data/filings/medivation/raw.md` for every divergence and assigns one of four verdicts (see `reference/alex/README.md`).

3. **Iterate.** When Austin finds an AI error that traces to a rule gap, update the rule in `rules/*.md`, re-run, re-diff. When Austin finds an Alex error that traces to an AI correction, record it (optionally in `alex_flagged_rows.json`) and move on.

4. **Roll out** once Medivation is green: Imprivata → Zep → Providence → Penford → Mac Gray → Petsmart → STec → Saks.

5. **Stage 3 exit**: all 9 reference deals manually verified AND three consecutive full-reference-set runs produce identical output with no rule changes. Only then point the pipeline at the 392 target deals.

## Non-negotiables (from `SKILL.md`)

- Every row carries `source_quote` + `source_page`. No un-cited rows ship.
- Event vocabulary in `rules/events.md` is closed. Flag, don't invent.
- Alex's workbook is a reference guideline, not ground truth. The SEC filing is ground truth.
- Do not touch `run.py`'s Ralph-loop outer structure — only fill in `run_pipeline()`.

## Things explicitly deferred

- **Workstream C** (25-deal lawyer-language study). Reopen only if Stage 3 diffs reveal systematic §G1/§L2 confusion the per-row loop can't resolve.
- **Planner** and **Canonicalizer** agents. Two-agent MVP first; add these only when the data demands it.
- **Target-deal (392) extraction.** Gated behind the Stage 3 exit criteria above.

## Before you write code

1. Read `CLAUDE.md` top-to-bottom.
2. Read `SKILL.md` for the invocation contract.
3. Skim `rules/schema.md` §R1 to internalize the output shape.
4. Look at `reference/alex/medivation.json` to see what "good" looks like for the simplest deal.
5. Look at `output/extractions/medivation.json` (synthetic, from `scripts/synth_extraction.py`) to see the fixture the diff is currently exercising.
6. Look at a section of `data/filings/medivation/raw.md` to see what the Extractor's input actually looks like.

Then propose a plan (Claude Agent SDK invocation pattern, error-handling, how you'll smoke-test before going live) and get Austin's sign-off.

---

**Commit graph at handoff:**
```
0b0d4d7 Wire scoring/diff.py end-to-end on Medivation
9dda10a Polish reference converter: mojibake salvage + A3 rank gap
3241785 Kick off Stage 2: reference/alex answer key + converter
f57a2aa Complete Stage 1: resolve 54 rulebook questions, scaffold pipeline
424df02 Initial commit
```

**Open coordination items with Alex** (from `CLAUDE.md`, unchanged):
- Confirm `cshoc` is the COMPUSTAT shares-outstanding field.
- Confirm whether to fix self-flagged rows in `alex/*.json` (current behavior: fix per §Q1–§Q4, preserve provenance flags).
- Confirm the composite-consideration schema (cash + CVR, cash + earnout) — structured columns or free text?
- Confirm whether legal counsel becomes an event type or a deal-level field.
