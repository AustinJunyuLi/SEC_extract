# Session Log — 2026-04-18 · Codebase Orientation

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
