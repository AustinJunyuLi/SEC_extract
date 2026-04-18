# Session Log — 2026-04-18 · Codebase Orientation

> Historical note: this is a start-of-day orientation snapshot from before
> Stage 2 and Stage 3 implementation landed. For current status, prefer
> `AGENTS.md` / `CLAUDE.md` / `SKILL.md` plus live artifacts in `state/`,
> `output/extractions/`, and `scoring/results/`.

**Status:** ACTIVE
**Session type:** Orientation / read-through (no code changes yet)

---

## Goal

User asked me to "read the codebase meticulously and let me know." Produce a precise snapshot of the project state so we can decide what to work on next.

## Approach

1. Read `CLAUDE.md` + `SKILL.md` — architecture, ground-truth epistemology, stage gates.
2. Read `skill_open_questions.md` — the Stage 1 tracker.
3. Read every `rules/*.md` — `schema`, `events`, `bidders`, `bids`, `dates`, `invariants`.
4. Read both prompts (`extract.md`, `validate.md`).
5. Read `run.py` and `scoring/diff.py` — confirm both are stubs.
6. Inspect `state/progress.json` (seeded, all 401 pending), `seeds.csv` (401 rows, 9 reference), `reference/alex/` (README + flagged_rows.json only; no `{deal}.json` yet), `output/extractions/` (empty).

## Key context captured

### What the project is
AI extraction pipeline over SEC merger filings (DEFM14A / PREM14A / SC-TO-T / S-4). Target output: row-per-event JSON matching Alex Gorbenko's M&A auction-research schema. 9 reference deals (hand-corrected by Alex) are the dev/calibration set; 392 target deals are processed once the rulebook is stable.

### Ground-truth epistemology (critical)
- **SEC filing = ground truth.**
- **Alex's workbook = reference guideline, not oracle.** Alex has flagged some of his own rows as wrong.
- Austin adjudicates every AI-vs-Alex divergence against the filing (4-verdict scheme in `reference/alex/README.md`).
- `scoring/diff.py` is a human-review aid, not a grader. No F1-vs-Alex number gates shipping.

### Architecture
- Per-deal Ralph loop in `run.py`; each deal in a fresh Claude session.
- Two-agent inner pipeline: Extractor → Validator. No Planner, no Canonicalizer at MVP.
- Every row must carry `source_quote` + `source_page`. Non-negotiable.
- Event vocabulary is closed (per `rules/events.md`).
- Skip rules in `rules/bids.md` §M are mandatory.

### Current state — **Stage 1 not yet started**
- **Rulebook:** 52 🟥 OPEN · 2 🟨 TENTATIVE · 0 🟩 RESOLVED.
- **Code:** `run.py run_pipeline()` and `scoring/diff.py` (`date_bucket`, `compare_field`, `diff_deal`) are `NotImplementedError` stubs.
- **State:** `state/progress.json` seeded with all 401 deals, all `pending`. No `state/flags.jsonl`. No extractions. No `reference/alex/{deal}.json` files yet.
- **Upstream artifacts present:** `reference/CollectionInstructions_Alex_2026.pdf`, `reference/deal_details_Alex_2026.xlsx` (9,336 rows × 35 cols).

### Three-stage roadmap
1. **Stage 1 — Resolve open questions** (current). Walk `skill_open_questions.md` top-down. Exit when all 🟥 → 🟩.
2. **Stage 2 — Build diff harness + Alex JSONs.** Convert 9 reference deals xlsx → JSON; wire up `scoring/diff.py`.
3. **Stage 3 — Build, iterate, verify.** Extractor + Validator; per-deal manual adjudication. Only run 392 targets after 3 consecutive unchanged-rulebook passes on all 9 references.

### The 9 reference deals (rollout order: simple → complex)
Medivation → Imprivata → Zep → Providence → Penford → Mac Gray → Petsmart → STec → Saks.
Each tests a different archetype (documented in `CLAUDE.md`).

### Who decides what
- **Alex required** for: §R1 final columns, §R3 evidence quote, §G1 informal-vs-formal, §H2 composite consideration, §J2 legal counsel placement, §L1 prior-process rule, §Q1–Q4, §N3 `cshoc`.
- **Austin (Claude proposes)** for: §Scope-2 filing types, §C1 vocabulary, §C2 capitalization, §E3 anonymous naming, §F1 bidder-type format, §B1 date table, §A1–A4 `BidderID` semantics.
- **Already deterministic** (can move to 🟩 immediately): §R3 (evidence quote is non-negotiable per SKILL.md), §G2 (same).

## Rationale / notes

- Do not start Stage 3 (or even Stage 2's conversion script) until Stage 1 is closed — this is an explicit gate in `CLAUDE.md`.
- Walkthrough order matters: schema first (constrains everything), invariants last (can only be written after the rest).
- Some questions are coupled bundles: §E1 + §E2 + §Q2 (aggregate vs atomize); §L1 + §M4 + §Q (prior-process handling).

## Open questions for Austin

- Where to start the Stage 1 walkthrough? Prescribed order begins at `rules/schema.md` §Scope-1 (auction-only vs every M&A).
- Should we knock off the "already deterministic" ones first (§R3, §G2 → 🟩) to get a clean win and reduce the tracker count?
- Is Alex reachable in this session for the Alex-required items, or do we surface those blockers and work around them?

## Next action

Awaiting user direction. Default suggestion: start with §Scope-1 per prescribed order; opportunistically close the two deterministic-already items (§R3, §G2) along the way.

---

## 2026-04-18 (late) — Stage 3 iter 2 · Imprivata

**Context.** Resumed from handoff doc `2026-04-18_stage3-iter1-handoff.md` (post-`e996e62`). Austin confirmed the rulebook is fixed (no more rule edits) and directed proceed to Imprivata per rollout order.

**Run.**
1. Built extractor prompt via `pipeline.build_extractor_prompt('imprivata')`; spawned general-purpose subagent with fresh context + disk-write contract (`/tmp/imprivata.raw.json`).
2. Extractor returned 28 events, 8 bidders, all internal self-checks clean.
3. `python run.py --slug imprivata --raw-extraction /tmp/imprivata.raw.json --no-commit` → `status=passed_clean`, 0/0/0.
4. `python scoring/diff.py --slug imprivata` → 25 matched / 3 AI-only / 4 Alex-only / 2 deal-level / 1 field (`bid_value_pershare` on Sponsor B).
5. Adjudicator subagent wrote `scoring/results/imprivata_adjudicated.md` (zero genuine AI defects).

**Key finding.** Every divergence is either (a) AI correctly applying a resolved rule (§B4 midpoint on the 5/6–6/9 NDA window; §K2 advancement-date anchor for `Final Round Ann` 6/12; §H1 range-bid discipline on Sponsor B 17-18; §D1 Bidder Interest 1/15 vs Bidder Sale 3/9; §R1 `Executed` = 7/13 per filing p.39) while Alex's legacy workbook predates or ignores it, or (b) a known convention-pin boundary case. **No Extractor patches needed.**

**Action items surfaced (for Austin, not Extractor):** see commit body.
1. `scripts/build_reference.py` — apply §H1 legacy-migration on Sponsor B 6/9 (`pershare=17` → `null`, `lower=17, upper=18`).
2. Reference converter — apply §B4 midpoint to 5/6–6/9 NDA window (5 NDAs null → 2016-05-22).
3. Log Alex's 7/9 Executed vs filing's 7/13 (p.39) in `alex_flagged_rows.json`.

**Commit.** `d9b3a2a Imprivata first-pass extraction: clean run, zero AI defects` — staged only `state/progress.json`. 18 uncommitted Austin edits (rules/, prompts/, references, pipeline.py, scripts/build_reference.py, CLAUDE.md, AGENTS.md) left untouched.

**3-run exit clock.** Medivation: 1/3 banked. Imprivata: 1/3 banked (since the rulebook didn't change during this run). The clock only resets on rulebook changes.

**Next.** Zep (`Terminated` → `Restarted` prior-process archetype). Awaiting go-ahead.

---

## 2026-04-18 (night) — Stage 3 iter 2 · Zep, Penford, Providence + prompt patch + linkflow pivot (reverted)

**Subagent runs completed.** Zep (73 events, `passed_clean`, 0 AI defects), Penford (24 events, 1 AI defect D1: same-day verbal+letter bid atomization), Providence-Worcester (76 events, 2 AI defects D2/D3: NDA/IOI count mismatches). Commits `7761c5c`, `9681776`, `1e192e4`.

**Prompt patch.** Commit `3af5ecf` added two non-negotiables to both `prompts/extract.md` and `pipeline.build_extractor_prompt()`: (1) numeric-count audit enforcing §E1/§E3/§P-D6; (2) same-date multi-communication atomization. Plus 3 new self-check items. Also landed Austin's pre-session prompt consolidations (deal-identity verbatim, §D1, §B5, §E3, §K2, §Press-Release fold).

**Linkflow pivot attempt (reverted).** Austin asked to switch extractor to linkflow OpenAI-compatible backend (`gpt-5.4`, reasoning=high, 5-parallel). Built `api_extractor.py` with `APIWatchdog` heartbeat + `runlog/{slug}.log` + `ThreadPoolExecutor`. Medivation (24 events, 521s) and Providence (76 events, 876s) worked. Imprivata (3 events, 199s), Zep (4 events, 206s), Penford (5 events, 170s) regressed hard — skeletal extractions with suspiciously short reasoning phase. Cause unclear (possibly parallelism-induced reasoning truncation). Decision: revert to Claude Code Opus 4.7 subagents; keep patched prompt; keep `api_extractor.py` on disk as dormant option.

**Handoff written** at `quality_reports/plans/2026-04-18_stage3-iter2-handoff.md` covering commit graph, 3 defects, prompt patch, linkflow regression pattern, revert rationale, next-session plan, accumulated reference-builder action items, and the 8 convention pins still deferred.

**Exit clock.** Reset on all deals by commit `3af5ecf` (extractor behavior changed). All 9 reference deals need 3 consecutive clean runs under the patched prompt + fixed rulebook to bank exit. Mac-gray / Petsmart / STec / Saks still pending.

**Next session action.** After context clear: read handoff + CLAUDE.md, re-run Medivation/Imprivata/Zep/Penford/Providence under the patched subagent prompt, verify D1/D2/D3 close, adjudicate, commit, then start Mac-gray.
