# Stage 3 Iter-6 Reference-Set Rerun — Handoff

**Status:** READY — TIER 2 + review fixes landed; rerunning 9 reference deals.
**Branch:** `claude/sharp-sutherland-8d60d7`
**HEAD:** `aa2de3f` (Iter-6 TIER 2 review fixes)
**Date:** 2026-04-19

---

## TL;DR

All of Iter-6 TIER 0/1/2 has landed (16 commits, −727 net lines). Rulebook
is stable. Time to rerun all 9 reference deals under the new invariants
(§P-D2 strict, §P-G2 bid-type evidence) and the simplified rulebook
(−601 deletion lines + −126 review-fix lines).

This run is the **first of 3 unchanged-rulebook runs** toward the exit
gate — IF it completes without requiring any rulebook change.

---

## State snapshot

**Reference deals (existing extractions, iter-5 generation):**
```
providence-worcester         passed_clean  flags=0
medivation                   passed_clean  flags=0
imprivata                    passed_clean  flags=0
zep                          passed_clean  flags=0
petsmart-inc                 passed_clean  flags=0
penford                      passed_clean  flags=0
mac-gray                     passed_clean  flags=0
saks                         passed_clean  flags=0
stec                         passed_clean  flags=0
```

**Caveat.** These extractions are from the iter-5 rulebook. Since then
TIER 1b added `_invariant_p_g2` (hard-fires on rows missing trigger +
inference_note). A dry-run against these stale extractions would
produce ~33 `bid_type_unsupported` hard flags across 8 of 9 deals.
**Existing output/extractions/*.json must be regenerated under the new
rulebook.**

---

## What the rerun is

For each of the 9 reference deals, in rollout order:

```
medivation → imprivata → zep → providence-worcester → penford →
mac-gray → petsmart-inc → stec → saks
```

Per deal:

1. **Spawn clean-slate extractor subagent** via `pipeline.build_extractor_prompt(slug)`
   - Subagent reads `prompts/extract.md` + `rules/*.md` + `data/filings/{slug}/pages.json`
   - Emits raw `{deal, events}` JSON to `output/extractions/{slug}.raw.json` (or stdout)
2. **Validate + finalize via `run.py`**:
   - `python3 run.py --slug {slug} --raw output/extractions/{slug}.raw.json`
   - This runs `pipeline.validate` → flags → `pipeline.finalize` → writes
     `output/extractions/{slug}.json` + `state/flags.jsonl` + updates
     `state/progress.json`
3. **Run diff vs reference:**
   - `python3 scoring/diff.py --slug {slug}`
   - Produces `scoring/results/{slug}_<timestamp>.md` with per-row
     matched/AI-only/Alex-only/field-disagreement sections
4. **Adjudicate (manual, Austin)**: read each divergence against filing
   text; mark verdict in the diff report. This step is OUT OF SCOPE for
   the automated rerun — the orchestrator just produces the reports.
5. **Commit extraction + diff**, then move to next deal.

---

## Expected flag counts

Per TIER 1b dry-run against iter-5 extractions, ~33 `bid_type_unsupported`
hard flags are expected across 8 of 9 deals. These are legitimate finds
(old extractions had bid_type without trigger/inference_note in
`source_quote`). Two resolutions per flag:
- **Add `bid_type_inference_note`** to the Bid row if the rationale is in
  filing language (extractor-side follow-up, not a rule change)
- **Expand §G1 trigger list** if a common phrase isn't yet there
  (rulebook change — would reset the exit clock)

Other flag classes expected at ≤ prior-run levels:
- `rough_date_mismatch_inference` (§P-D2 strict): 0 expected; any hit is
  an extractor bug
- `nda_promotion_failed` (§P-R5 / TIER 1c registry integrity): 0 expected
- `informal_vs_formal_ambiguous` (§G1 fallback): variable per deal
- `bidder_id_*`: 0 expected (reference JSONs use canonical IDs; AI should
  too)

---

## Orchestrator pattern

Same as TIER 2 sub-commit pattern:
- Orchestrator (me) spawns a clean-slate extractor subagent per deal
- Subagent emits raw JSON
- Orchestrator runs `run.py` + `scoring/diff.py`
- Orchestrator reports diff summary (matched / AI-only / Alex-only /
  field-disagreement counts) and commits per deal
- After all 9: aggregate report → decide whether any rule change is
  needed → if yes, clock stays 0/3; if no, clock ticks to 1/3

**Time budget:** 9 extractor runs. Each takes ~60-180s depending on
filing size. Total ~30-45 minutes wall-clock with parallelism across
deals (different subagents, different filings, no shared state).

Could spawn 3-4 extractors in parallel (same-deal extraction is
stateless; no cross-deal coupling in `pipeline.validate` or
`scoring/diff.py` since both are per-deal).

---

## Exit clock accounting

Current state: **0/3 unchanged-rulebook runs.**

This rerun is:
- **→ 1/3** if all 9 pass and no rule changes needed for adjudication
- **→ 0/3** if any adjudication requires a rule change

Historical context: TIER 0/1/2/review-fixes each reset the clock. Clock
has never been above 0/3 in iter-6.

---

## Known pre-existing follow-ups (NOT blocking this rerun)

From CLAUDE.md "Current Stage 3 follow-ups":
- Refresh `scoring/results/medivation_adjudicated.md` against new diff
- `bidder_type.public` inference in `scripts/build_reference.py`
- Re-encode Zep "Exclusivity 30 days" as `exclusivity_days` on bid row
- Adjudicate Medivation inferred-date rows (if still present post-TIER 2)

These are reference-side / adjudication-side concerns. They don't block
the rerun itself.

---

## Success criteria

- [ ] 9 extractions produced under current rulebook
- [ ] `state/progress.json` reflects all 9 at `validated` or `passed` or
  `passed_clean` (not `pending`, not `failed`)
- [ ] `state/flags.jsonl` appended with run's flags
- [ ] 9 diff reports produced in `scoring/results/`
- [ ] Aggregate summary written (counts + per-deal flag breakdown)
- [ ] 9 atomic commits (one per deal), or one bundled commit if lower-risk
- [ ] Exit-clock decision: clock state reported at end (0/3 or 1/3)

---

## Out of scope for this rerun

- TIER 3 (dead-code sweep) — will follow after rerun adjudication
- Target-deal extraction (gate stays closed: 3-consecutive-unchanged not met)
- Per-row manual adjudication (Austin's job; orchestrator produces the
  reports)
- Rule changes surfaced by adjudication (those need their own commits)

---

## First action for rerun

Spawn 3 extractor subagents in parallel for the first 3 simplest deals
(medivation, imprivata, zep — all <25 events). Wait for completion,
run `run.py` + `scoring/diff.py` for each, commit. Then next batch.
