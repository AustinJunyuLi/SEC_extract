---
date: 2026-04-23
status: DRAFT_FOR_AUSTIN_REVIEW
owner: Austin + Codex
purpose: Decide what to fix next before any implementation work resumes.
related:
  - AGENTS.md
  - CLAUDE.md
  - SKILL.md
  - quality_reports/adjudication/2026-04-21_rerun/MASTER_RERUN.md
  - quality_reports/comparisons/2026-04-21_three-way/MASTER_REPORT.md
  - quality_reports/plans/2026-04-21_validator-hardening-prd.md
---

# Plan: Stabilize the Current Pipeline, Then Test Claims in Shadow Mode

## 0. Plain-English Summary

The current extraction system is worth keeping.

It already has:

- a rulebook,
- saved SEC filings,
- AI-produced event rows,
- a Python checker,
- comparison reports against Alex's reference files,
- tests.

The next move should **not** be a big rewrite.

The next move should be:

1. Make the current tool safer and easier to reproduce.
2. Clean obvious reference-file noise.
3. Fix the one hard-blocked reference deal, `penford`.
4. Fix repeated AI mistakes found in the 9-deal review.
5. Only then test a small "claim-first" idea on one deal, without replacing the current pipeline.

The external "Deal Truth Engine" suggestion has one good idea:

> The AI should propose small evidence-backed facts before those facts become final event rows.

But taken literally, it becomes too much too soon. We should adopt the idea carefully, in shadow mode, after the current system is stable.

## 1. Current Status

`state/progress.json` still reflects the pre-cleanup 2026-04-21 reference
outputs. Those rows are useful history, but they are not current enough to
serve as the next gate because the runner, prompt contract, reference
converter, and rulebook-version behavior have changed.

Pre-cleanup ledger state:

| Item | Status |
|---|---:|
| Total deals | 401 |
| Reference deals | 9 |
| Target deals still pending | 392 |
| Reference deals with current output | 9 |
| Reference deals with no hard checker flags | 8 |
| Reference deals with hard checker flags | 1 |
| Reference deals manually marked verified | 0 |

The pre-cleanup hard blocker was:

```text
penford
```

`penford` had hard `bid_type_unsupported` flags. In plain language: several
bid rows said "this is a formal/informal bid," but the row did not give the
required explanation or range evidence.

Current implication:

```text
After the cleanup, rerun all 9 reference deals before trusting status counts.
```

The target-deal gate remains closed. Do not run the 392 target deals yet.

## 2. Guiding Principle

Keep the system boring until the 9 reference deals are clean.

That means:

- keep the current final event JSON schema,
- keep the current Python validator,
- keep the current diff workflow,
- do not add a multi-agent debate system yet,
- do not add numeric confidence scores,
- do not rewrite the repo around an untested "truth engine."

The safe design direction is:

```text
AI proposes evidence-backed facts.
Python checks evidence and structure.
Python still produces the existing event rows.
Austin adjudicates only the remaining judgment calls.
```

## 2.1. Non-Negotiable Engineering Policies

These apply to both docs and code.

### No backward compatibility

When we change a schema, rule, prompt contract, state format, or output format, we do **not** keep legacy support around.

That means:

- no compatibility shims,
- no "old format or new format" readers,
- no automatic migration paths hidden inside validators,
- no deprecated code left in place,
- no docs that describe old and new behavior side by side as if both are supported.

The rule is:

```text
Change the contract.
Regenerate affected data.
Delete stale code and stale docs.
Use git history as the compatibility record.
```

### Fail loudly

If something fails, it should fail clearly.

Do not silently fall back to an older behavior. Do not guess. Do not auto-repair unless that repair is the explicit feature being implemented and is logged.

Examples:

- If a required field is missing, fail with a clear error or hard flag.
- If a saved extraction uses an old schema, fail and regenerate it.
- If a rule file and prompt disagree, fail the contract test.
- If the claim experiment cannot explain the current output, stop the experiment and report the mismatch.

### Do not mine old commits for solutions

Do not go backward through commit history to resurrect old code as the answer.

Allowed:

- read current tracked files,
- read current quality reports,
- read current rule files,
- use current tests,
- use current documented decisions.

Not allowed unless Austin explicitly asks:

- checking out old commits,
- copying old code from prior commits,
- restoring deleted behavior because it once existed,
- treating old plans as authoritative after the live repo has moved on.

Old reports can explain **why** a decision happened. They do not override the current live contract.

## 3. What We Adopt From the External Suggestion

Adopt these ideas, but only after stabilizing the current pipeline:

- **Evidence spans:** stable IDs for exact filing text snippets.
- **Claim extraction in shadow mode:** have the AI output small facts for one deal, without replacing event extraction.
- **Issue packets:** make Austin's manual review easier by turning messy diffs into clear questions.

Do not adopt these yet:

- multiple competing extractor agents,
- aggressive/conservative/critic ensemble,
- numeric confidence scores,
- replacing the event schema,
- deleting most of the current code,
- building a full "truth engine" before `penford` and reference noise are fixed.

## 4. Workstream A — Make the Current Pipeline Safe

This work should happen first. It reduces accidental damage and makes future runs easier to trust.

### A1. Stop `run.py` from committing too broadly

Problem:

Before Workstream A, `run.py` committed by default and used `git add -A`,
which could accidentally include unrelated files.

Decision:

- [x] Remove the old `--no-commit` path instead of keeping two behaviors.
- [x] Make no-commit the default behavior.
- [x] Keep commit support only through an explicit `--commit` flag.
- [x] If commit support is used, only stage the files for the current deal, not the whole repo.

Acceptance checks:

- [x] Running `python run.py --slug X --raw-extraction path.json` writes output/state but does not commit.
- [x] Running with `--commit` stages only the intended files.
- [x] Tests cover no-commit default behavior.

### A2. Record failed runs as failed

Problem:

The docs say failures should be recorded in `state/progress.json`, but several failures currently just raise an error.

Decision:

- [x] Add a small helper that marks a deal `failed` with a short note.
- [x] Use it when filing artifacts are missing or finalization otherwise fails.
- [x] Use it when raw JSON is malformed.
- [x] Use it when finalization fails before output is complete.

Acceptance checks:

- [x] Missing filing/finalization errors mark the deal `failed`.
- [x] Bad raw JSON marks the deal `failed`.
- [x] The failure note is short and readable.
- [x] Tests cover both cases.

### A3. Record the rulebook version

Problem:

The exit rule requires 3 clean runs with an unchanged rulebook. Before
Workstream A, `state/progress.json` did not record the live rulebook content
hash needed to audit that clock.

Decision:

- [x] Store a stable content hash for the current `rules/*.md` files when a run is finalized.
- [x] Put that value in `state/progress.json`.
- [x] Also copy it into the output deal object.

Acceptance checks:

- [x] A progress update records a non-null rulebook version.
- [x] Re-running without rule changes produces the same rulebook version.
- [x] Changing a rule file changes the version.

### A4. Pin dependencies

Problem:

`sec2md` affects page numbers, and page numbers are part of the evidence trail. The repo has no dependency file.

Decision:

- [x] Add a minimal dependency file.
- [x] Pin `sec2md==0.1.22`, because current filing manifests record that version.
- [x] Pin the libraries actually used by tests and scripts: `pytest`, `openpyxl`, `matplotlib`, `numpy`.

Acceptance checks:

- [ ] A new environment can install dependencies from the file.
- [x] `pytest -q` passes.
- [x] The dependency file is intentionally small.

### A5. Fix blank evidence quotes

Problem:

A whitespace-only `source_quote` can accidentally pass the substring check.

Decision:

- [x] Treat `source_quote` as missing if it is empty after stripping whitespace.
- [x] Apply this to each item in multi-quote form too.

Acceptance checks:

- [x] A quote of `"   "` fails with `missing_evidence`.
- [x] A list containing `"   "` fails.
- [x] Existing tests still pass.

### A6. Align prompt and contract docs

Problem:

`SKILL.md`, `prompts/extract.md`, and the prompt builder do not say exactly the same thing about which rule files the extractor reads and whether it fetches filing text externally.

Decision:

- [x] Make all three say the same thing: the filing is already saved locally; the extractor reads local files.
- [x] Decide whether the extractor must read `rules/invariants.md`.
- [x] Do not include it in `pipeline.build_extractor_prompt()`.
- [x] Document why it is validator-facing only.

Acceptance checks:

- [x] `SKILL.md`, `prompts/extract.md`, and `pipeline.build_extractor_prompt()` agree.
- [x] A simple test checks that all intended rule files appear in the prompt.

## 5. Workstream B — Clean Reference and Diff Noise

This work should happen before Austin spends more time manually reviewing row-by-row differences.

### B1. Fix invalid reference event labels

Known problems:

- `reference/alex/providence-worcester.json` has one row with `bid_note: null`.
- `reference/alex/zep.json` has one row with `bid_note: "Exclusivity 30 days"`, which is not part of the current event vocabulary.

Decision:

- [x] Fix these in `scripts/build_reference.py`, not by hand-editing the generated JSON.
- [x] Regenerate the affected reference JSONs.

Acceptance checks:

- [x] No `reference/alex/*.json` row has `bid_note: null`.
- [x] No `reference/alex/*.json` row has an out-of-vocabulary `bid_note`.
- [x] `python scripts/build_reference.py --all --dump >/dev/null` passes.

### B2. Fix `bidder_type.public` conversion

Problem:

Alex's workbook sometimes carries public-company information, but the
converter previously did not preserve explicit `public` notes. The converter
also briefly overreached by treating plain `S` / `F` notes as proof of
`public: false`; that was too strong because `S` only means strategic and `F`
only means financial.

Decision:

- [x] Update `scripts/build_reference.py` so it preserves explicit public/private signals when the workbook supports them.
- [x] Keep `public: null` when the workbook only says plain `S`, `F`, `strategic`, or `financial`.
- [x] Set `public: false` only when the note explicitly says private / PE / sponsor.

Acceptance checks:

- [x] Penford / Ingredion workbook note `S` stays `public: null`; the converter no longer invents either `public: true` or `public: false`.
- [ ] Current `bidder_type` diff noise drops materially.
- [x] Tests or a small verification script cover the conversion rule.

### B3. Decide how to handle deal-level identity diffs

Problem:

The AI uses filing-verbatim names and often leaves `DateEffective = null`. Alex's workbook may use normalized names and populated effective dates. These create recurring diff noise.

Decision needed from Austin:

- [ ] Should `scoring/diff.py` keep showing `TargetName`, `Acquirer`, and `DateEffective` disagreements?
- [ ] Or should it suppress expected reference noise unless the filing itself supports Alex's value?

Recommended decision:

- [ ] Suppress or separate these as "deal identity noise" unless Austin wants to adjudicate them.

Acceptance checks:

- [ ] Diff reports clearly separate research-relevant event differences from deal-name/date noise.
- [ ] No event-level disagreements are hidden.

### B4. Apply already-confirmed Alex/reference corrections

The three-way review already found likely reference-side issues. These should not be mixed into prompt fixes.

Candidate corrections include:

- Medivation date corrections.
- Imprivata date/drop corrections.
- Zep bid/NDA count corrections.
- Mac Gray acquirer/date corrections.
- Saks joint-bid label correction.
- Penford public-bit correction.

Decision:

- [ ] Austin reviews the existing list and checks which corrections to apply.
- [ ] Apply approved corrections through `scripts/build_reference.py`.
- [ ] Regenerate reference JSONs.

Acceptance checks:

- [ ] Corrections are documented in the converter or reference README.
- [ ] Regenerated files are converter-synchronized.
- [ ] Diff noise falls without changing extraction rules unnecessarily.

## 6. Workstream C — Fix Current Extraction Issues on the 9 Reference Deals

This work should happen before any claim-first experiment becomes central.

### C1. Fix `penford`

Problem:

`penford` is the only hard-blocked reference deal.

Decision:

- [ ] Fix the 6 `bid_type_unsupported` rows.
- [ ] Decide whether the fix is in the saved output, extractor prompt, or a rerun.
- [ ] Prefer rerun or prompt fix over manual JSON patching.

Acceptance checks:

- [ ] `penford` has 0 hard flags.
- [ ] `penford` status moves from `validated` to `passed` or `passed_clean`.
- [ ] No evidence quotes are weakened or removed.

### C2. Fix repeated AI mistakes found in the 9-deal review

Known repeated patterns:

- voluntary bidder exit vs target rejection,
- missed final-round markers,
- missed NDA renewal / NDA revival,
- formal-vs-informal bid mistakes,
- out-of-scope financing NDAs,
- missed pre-history counterparties,
- over-classifying `Bidder Interest` as `Bidder Sale`,
- underusing `Auction Closed`.

Decision:

- [ ] Add concrete examples to the prompt/rules for each repeated pattern.
- [ ] Keep changes small and tied to an observed mistake.
- [ ] Do not add broad new architecture for these prompt-level issues.

Acceptance checks:

- [ ] Affected deals are rerun.
- [ ] No new hard flags appear.
- [ ] The specific known mistakes improve.
- [ ] Any row-count changes are documented.

### C3. Rerun the 9 reference deals after fixes

Decision:

- [ ] Rerun all 9 reference deals only after Workstreams A, B, and C1/C2 are complete.

Acceptance checks:

- [ ] All 9 reference deals have current outputs.
- [ ] All 9 have 0 hard validator flags.
- [ ] New diff reports are generated.
- [ ] Austin can manually review a smaller, cleaner set of differences.

## 7. Workstream D — Claim-First Experiment in Shadow Mode

This is the only part of the external "truth engine" idea that should be tested now.

The rule:

> Shadow mode means the new claim system runs beside the current pipeline. It does not replace the current output.

### D1. Build evidence spans for one deal

Start with:

```text
medivation
```

Reason:

It is the simplest reference deal and already behaves relatively well.

Add:

```text
evidence.py
tests/test_evidence.py
data/sections/medivation.json
```

Output shape:

```json
{
  "slug": "medivation",
  "spans": [
    {
      "span_id": "p23.s001",
      "page": 23,
      "text": "Exact sentence or paragraph from pages.json",
      "hash": "short stable hash"
    }
  ]
}
```

Acceptance checks:

- [ ] Every span text is a verbatim substring of its page.
- [ ] Every page number exists in `pages.json`.
- [ ] Span IDs are stable across reruns.
- [ ] No LLM is involved.

### D2. Define a small claim schema

Add:

```text
rules/claims.md
claims.py
tests/test_claim_schema.py
```

Start with a small claim vocabulary:

```text
actor_mentioned
advisor_engaged
nda_signed
bidder_contacted
bid_submitted
price_indicated
round_started
process_letter_sent
bidder_dropped
process_terminated
process_restarted
agreement_executed
count_statement
```

Do not add every possible concept yet.

Acceptance checks:

- [ ] Unknown claim types fail validation.
- [ ] Claims without evidence span IDs fail validation.
- [ ] Bad date formats fail validation.
- [ ] Claim validation is pure Python.

### D3. Write a claim-extraction prompt for Medivation only

Add:

```text
prompts/extract_claims.md
output/claims/medivation.json
```

Decision:

- [ ] Run this only on Medivation first.
- [ ] Do not compile claims into final event rows yet.
- [ ] Do not compare claims to all 9 deals yet.

Acceptance checks:

- [ ] Every claim has at least one valid span ID.
- [ ] The claim output is understandable by a human.
- [ ] The claims explain the current Medivation event rows at a high level.

### D4. Decide whether claims are worth continuing

After Medivation:

- [ ] Did claims make review easier?
- [ ] Did claims expose any missed event or bad interpretation?
- [ ] Was the added complexity small enough?
- [ ] Could Austin explain the claim file without needing a new system manual?

If yes, continue to D5.

If no, stop. Keep the current event-first pipeline.

### D5. Optional next step: compile claims into event rows for Medivation

Only do this if D1-D4 are useful.

Add:

```text
compiler.py
tests/test_compiler.py
output/traces/medivation.json
```

Acceptance checks:

- [ ] Compiled Medivation events pass the existing `pipeline.validate()`.
- [ ] Every compiled event links back to at least one claim.
- [ ] Every linked claim links back to at least one evidence span.
- [ ] The compiled event output does not become the production output until Austin approves it.

## 8. Workstream E — Better Manual Review Packets

This can be useful even if the claim experiment stops.

Goal:

Turn messy row diffs into clear questions for Austin.

Add later:

```text
review/issues/{slug}.json
```

Example:

```json
{
  "issue_id": "penford_007",
  "issue_type": "bid_type_question",
  "severity": "hard",
  "question_for_austin": "Does this concrete price indication qualify as a formal bid?",
  "filing_evidence": ["page 42 quote ..."],
  "ai_position": "informal",
  "alex_position": "formal"
}
```

Acceptance checks:

- [ ] Each issue asks one clear question.
- [ ] Each issue cites filing evidence.
- [ ] Each issue says what decision Austin needs to make.
- [ ] Issues are generated from existing diffs and flags where possible.

## 9. Workstream F — Staleness Cleanse

After the main fixes land, do a deliberate cleanup pass across both code and docs.

Goal:

Make the repo describe exactly one current system, not a pile of old plans and old behaviors.

### F1. Delete finished plans

Policy:

If a plan is fully implemented and its important decisions have been moved into the live docs or code comments, delete the plan file.

Do not keep finished plans just because they are historically interesting.

Allowed exceptions:

- a plan still under Austin review,
- a plan that documents an active unresolved decision,
- a final report that is evidence for an adjudication result.

Acceptance checks:

- [x] Every remaining file in `quality_reports/plans/` is either active, pending Austin review, or explicitly marked as historical-but-still-needed.
- [x] Fully completed plans are deleted.
- [x] Important decisions from deleted plans are represented in live docs such as `AGENTS.md`, `CLAUDE.md`, `SKILL.md`, `rules/*.md`, or module docstrings.

### F2. Remove stale docs

Problem:

Several docs are snapshots. Some are less current than others.

Decision:

- [x] Make `AGENTS.md`, `CLAUDE.md`, and `SKILL.md` agree on the current architecture.
- [x] Remove or rewrite old statements that describe abandoned behavior found in this pass.
- [ ] Remove old "maybe" sections after Austin has made a decision.
- [x] Make sure live docs do not preserve legacy behavior for backward compatibility.

Acceptance checks:

- [x] A new reader can understand the current workflow from the top-level docs without reading old session logs.
- [x] `AGENTS.md` and `CLAUDE.md` do not contradict each other.
- [x] `SKILL.md` describes the live pipeline, not a future wish list.

### F3. Remove stale code paths

Policy:

When code is replaced, delete the replaced path in the same implementation sequence.

Acceptance checks:

- [ ] No unused helper functions remain from replaced behavior.
- [ ] No tests exist only to protect old behavior.
- [x] No CLI flags support old formats unless they are still part of the current contract.
- [x] No comments say "legacy", "deprecated", "for backward compatibility", or "old format" unless they are explaining why the old path was deliberately removed.

### F4. Clean generated-state policy

Problem:

Some generated files are tracked, some are ignored, and some old outputs may look current.

Decision:

- [ ] Decide which generated artifacts are source-of-truth enough to track.
- [x] Regenerate reference JSONs after converter changes instead of keeping stale generated outputs.
- [ ] Keep only current reference outputs, current filing artifacts, and reports that are still needed for active decisions.

Acceptance checks:

- [ ] `git status` is understandable after a clean run.
- [ ] Ignored paths and tracked generated paths are intentional.
- [ ] Old scoring reports are deleted if superseded and no longer needed.

## 10. Previous Plan Items to Pause or Reconsider

The older validator-hardening PRD contains useful ideas, but some items should not be implemented blindly.

Pause or reconsider these until Austin explicitly approves:

- adding code-synthesized Drop rows to close NDA silence,
- relaxing evidence checks for code-synthesized rows,
- expanding aggregate NDA rows by code if doing so hides filing ambiguity,
- adding a required `source` field to every event before the current 9-deal set is stable.

Reason:

These may be useful later, but they change the meaning of the dataset. The current project rule is that rows should be grounded in filing evidence. Code-created rows need a separate explicit policy decision.

Keep or adopt now:

- saving raw extractor JSON before mutation,
- stronger evidence checks,
- dependency pinning,
- rulebook-version tracking,
- prompt/documentation alignment,
- reference converter cleanup.

When one of these older plan items is rejected or superseded, delete or rewrite the stale plan text. Do not keep a dead plan as a parallel instruction source.

## 11. Full Implementation Order

Recommended order:

1. [x] A1: Make `run.py` no-commit by default.
2. [x] A2: Record failed runs.
3. [x] A3: Record rulebook version.
4. [x] A4: Pin dependencies.
5. [x] A5: Fix whitespace-only evidence quote check.
6. [x] A6: Align prompt and contract docs.
7. [x] B1: Fix invalid reference event labels.
8. [x] B2: Fix `bidder_type.public` conversion.
9. [ ] B3: Decide deal-level diff-noise policy.
10. [ ] B4: Apply Austin-approved Alex/reference corrections.
11. [ ] C1: Fix `penford`.
12. [ ] C2: Fix repeated AI mistakes in prompt/rules.
13. [ ] C3: Rerun all 9 reference deals.
14. [ ] D1-D4: Run Medivation claim-first shadow experiment.
15. [ ] D5: Only if useful, compile Medivation claims into event rows.
16. [ ] E: Add issue packets if manual review is still too noisy.
17. [ ] F: Do a staleness cleanse across docs, code, generated outputs, and finished plans. Partial pass completed on 2026-04-23.

## 12. Definition of Done Before 392 Target Deals

Do not run the 392 target deals until all of these are true:

- [ ] All 9 reference deals have current outputs.
- [ ] All 9 reference deals have 0 hard validator flags.
- [ ] Austin has manually verified the 9 reference deals against filings.
- [ ] `state/progress.json` marks verified deals correctly.
- [ ] Rulebook version is recorded for each run.
- [ ] Dependencies are pinned.
- [ ] The diff reports are cleaner and mainly show real judgment calls.
- [ ] Stale docs, stale code paths, stale generated outputs, and finished plans have been removed.
- [ ] The rulebook/prompt/code remain unchanged across 3 consecutive clean full-reference runs.

## 13. Austin Approval Checklist

Before implementation, Austin should check or reject each major decision:

- [ ] Approve Workstream A: safety and reproducibility first.
- [ ] Approve Workstream B: reference/diff cleanup before more manual review.
- [ ] Approve Workstream C: fix `penford` and repeated extraction mistakes before target deals.
- [ ] Approve Workstream D: claim-first experiment only in shadow mode, starting with Medivation.
- [ ] Approve Workstream F: thorough staleness cleanse after fixes.
- [ ] Enforce no backward compatibility in docs and code.
- [ ] Enforce fail-loud behavior instead of fallback behavior.
- [ ] Do not go back in commits for implementation solutions unless Austin explicitly asks.
- [ ] Reject large multi-agent redesign for now.
- [ ] Reject numeric confidence scores for now.
- [ ] Reject changing the final event schema for now.
- [ ] Pause code-synthesized Drop rows / relaxed evidence policy until separately approved.

## 14. Final Recommendation

The right move is not:

```text
rewrite the pipeline as a truth engine
```

The right move is:

```text
make the current event pipeline safe and clean,
then test whether evidence-backed claims improve review on one deal.
```

If the Medivation shadow experiment proves useful, expand it carefully.

If it does not, keep the simpler event-first pipeline and proceed with the cleaned 9-reference workflow.
