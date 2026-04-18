# Stage 3 Iteration 1 Handoff — Read This First

**Intended reader.** A fresh Claude (or Codex) session opening this repo after
a context clear. Read this file, then `CLAUDE.md`, then stop and confirm the
plan with Austin before writing code.

**Date:** 2026-04-18
**Prior handoff:** `2026-04-18_stage3-handoff.md` (Stage 3 kickoff — now historical).
**Prior state:** Stages 1 and 2 complete. Stage 3 open, one iteration banked.

---

## TL;DR

Stage 3 iteration 1 is complete. Medivation runs end-to-end through the
pipeline — clean Python validator (zero hard flags), diff against Alex's
reference down from 30 divergences at kickoff to 14 today, and every remaining
divergence is either a convention-pin awaiting Austin's decision or a case
where the AI is demonstrably more informed than Alex's legacy workbook. The
pipeline's LLM Extractor is a Claude Code subagent; the Validator is pure
Python in `pipeline.py`; the Adjudicator is a scoped subagent that only fires
on soft flags (didn't fire this iteration). No Anthropic SDK calls from
Python.

---

## What shipped this iteration

Eight atomic commits, Stage 3 first iteration (2026-04-18):

```
ec22cbb Patch §B3 rough-anchor: inferred dates now populate bid_date_rough
a0397e1 Medivation re-extract post-patches: diff collapses 30→8 divergences
4ff5843 Make IB emission explicit: trigger on 'financial advisor to [Side]'
a099d3a Propagate §C3: unify bid rows under bid_note='Bid' + bid_type
7c59c91 Add §Q5: atomize Medivation's aggregated 'Several parties' rows
c4ec361 Fix §P-S3 'phase_termination_missing' misfire on same-date clusters
8ba3716 Fix 5 build_reference serialization bugs to match rulebook
031c371 Start Stage 3: Python validator + subagent-driven Extractor MVP
```

One-line digest of each:
- `031c371` — First real Medivation run (19 events, 1 hard flag).
- `8ba3716` — `build_reference.py` serialization bugs (5 fixes): `bid_date_rough` mirror, `bid_value_unit` "dollar" → "USD_per_share", `bidder_type.public` parsed from note, point-bid `bid_value_lower/upper` null, `multiplier` null on plain-dollar.
- `c4ec361` — Validator §P-S3 bug fix: `max(dated, key=date)` was picking the FIRST same-date tie; switched to last-row-in-§A-order.
- `7c59c91` — New rule `rules/dates.md` §Q5: atomize Medivation's `"Several parties, including Sanofi"` NDA (xlsx 6065) + Drop (xlsx 6075) rows per §E1. Also fixed the post-sort registry to populate aliases for expansion-introduced canonical ids.
- `a099d3a` — §C3 migration across the stack: bid rows now carry `bid_note="Bid"` + `bid_type` everywhere. Removed legacy `"Inf"` / `"Formal Bid"` / `"Revised Bid"` from `EVENT_VOCABULARY`, `A3_RANK`, extractor prompts, and the converter.
- `4ff5843` — Made IB emission explicit. §J1 rewritten with trigger phrases; `prompts/extract.md` §2a; `pipeline.build_extractor_prompt()` non-negotiable bullet. AI now finds J.P. Morgan + Evercore (Medivation's advisors), Centerview + Guggenheim (Pfizer's). Also folds post-execution press release into `Executed` row per §R3 multi-quote.
- `a0397e1` — Second Medivation run (22 events, diff 30→8).
- `ec22cbb` — §B3 rough-anchor patch. Surfaced the "inference flag implies non-null `bid_date_rough`" rule in §6 of the extractor prompt, the orchestrator template's non-negotiables, and §J1. Third Medivation run: 26 events, **zero hard validator flags**.

---

## Current Medivation state (after `ec22cbb`)

```
Validator:  status=passed_clean  hard=0 soft=0 info=0
Events:     26  (Alex reference: 19 post-§Q5 expansion; was 16 raw)
Diff:
  matched rows:          18
  AI-only rows:           8   (all legit — see below)
  Alex-only rows:         1   (one Alex phantom — see below)
  deal-level diffs:       3   (TargetName case, Acquirer case, DateEffective)
  field disagreements:   13
    bidder_type=8  (convention — pin awaiting Austin)
    bid_date_rough=3  (AI populated anchor phrases; Alex null)
    bid_value_pershare=1, bid_value_unit=1  (Executed-row consideration — Austin's deferred list)
```

Every divergence is either convention-pin work or AI-is-more-informed. Zero
real AI defects remaining on Medivation. The extraction is research-grade.

---

## Remaining divergences (read before acting)

**Do NOT treat any of these as "bugs to fix" without checking this list first.**
Most of them are legitimate, and touching them will either make the diff worse
or require a rulebook change Austin hasn't signed off on.

### AI-only rows (8) — all legit
1. Pfizer Bidder Interest 2016-05-02 — real filing event (Giordano's first contact email).
2. Sanofi Bid Press Release 2016-04-28 — real public announcement.
3. Sanofi DropTarget 2016-04-29 — real board rejection.
4. Evercore IB 2016-05-11 — real Medivation advisor.
5. Centerview IB 2016-05-11 — real Pfizer advisor.
6. Guggenheim IB 2016-07-07 — real Pfizer advisor.
7. Final Round Ext Ann 2016-08-19 — "best and final" request per §K1.
8. Final Round Inf 2016-08-08, Final Round 2016-08-19, Final Round Ext 2016-08-20 — deadline events paired with the round announcements.

### Alex-only row (1) — Alex phantom
- `None · Final Round Inf · 2016-08-14` — Alex mislabeled the formal-round process-letter date as an informal-round deadline. AI correctly doesn't emit.

### Deal-level disagreements (3) — AI right, convention pin deferred
- TargetName: AI `"Medivation, Inc."` vs Alex `"MEDIVATION INC"`. Filing uses mixed case; Alex's ALL-CAPS is a COMPUSTAT join leftover.
- Acquirer: AI `"Pfizer Inc."` vs Alex `"PFIZER INC"`. Same pattern.
- DateEffective: AI `null` vs Alex `"2016-09-28"`. Filing predates closing; AI correct per §Scope-3. Alex fills from external data.

### bidder_type disagreements (8) — all same pattern
- AI: `{base, non_us, public: true}` (no `note`)
- Alex: `{base, non_us, public: true|null, note: "S" | "Non-US public S"}`
- Rulebook §F1 doesn't pin whether `note` is required. Both-defensible.

### bid_date_rough disagreements (3) — AI more informed
- AI populates short anchor phrases (`"first narration: 2016-05-11 contact"`, etc.) on inferred IB retentions and implicit drops; Alex's reference has `null`. The AI is rulebook-correct per §B3.

### bid_value_pershare / bid_value_unit disagreements (2) — Executed row convention
- AI emits `bid_value_pershare=81.5`, `bid_value_unit="USD_per_share"` on the Executed row; Alex has both null. Rulebook is silent on whether `Executed` rows carry consideration. On Austin's deferred decision list.

---

## Decision backlog (awaiting Austin's call)

From `scoring/results/medivation_adjudicated.md` and the ongoing iteration:

**Deferred rulebook pins:**
1. §B5 — date-anchor rule for "letter dated X received Y" (Sanofi 4/13 vs 4/15 case).
2. §K2 addendum — `Final Round Ann` tie-break when invitation date and process-letter date differ.
3. §D1 clarification — unsolicited-first-contact bids: fold `Bidder Sale` into bid row (AI's approach) vs separate row (Alex's).
4. §F1 pin — `bidder_type.note` convention. Recommend drop; `public: bool` supersedes.
5. §R1 or §N2 clarification — whether `Executed` rows carry `bid_value_pershare` / `bid_value_unit` / `cash_per_share`.
6. §Scope-3 clarification — `DateEffective` always null when filing predates closing (formalize what §Scope-3 already implies).
7. §Scope-3 clarification — `TargetName` / `Acquirer` case formatting (filing verbatim vs COMPUSTAT ALL-CAPS).
8. Unnamed-bidder placeholder count rule — when filing says "several," how many NDA / Drop placeholders? AI heuristic is N=2; rulebook silent. Pin.

**Deferred code work (non-rulebook):**
- Zep's `"Exclusivity 30 days"` row (xlsx 6405). §C1 deprecated this code and says re-encode as `exclusivity_days: int` attribute on the associated bid row. Converter doesn't yet. Surfaces as 1 `invalid_event_type` flag on Zep references.
- Petsmart / Penford / Mac Gray / Saks references still flag `phase_termination_missing` post-§P-S3 fix — the references' own last events aren't §P-S3 terminators. Separate investigation per deal.

---

## Logical next step (recommendation)

**Advance to Imprivata** (`CLAUDE.md` rollout order: Medivation →
**Imprivata** → Zep → Providence → Penford → Mac Gray → Petsmart → STec → Saks).

Reasoning:
- Medivation's remaining divergences are all convention-pin or AI-informed
  (nothing a re-run will improve without a rulebook decision).
- Imprivata exercises different archetypes — `Bidder Interest → Bidder Sale`
  transitions and `DropBelowInf` / `DropAtInf` codes — that will reveal
  whether the Stage 3 patches generalize before we bank decisions on Medivation.
- The 3-consecutive-unchanged-rulebook-run exit criterion can be satisfied
  in parallel: two more Medivation re-runs after the next rulebook change
  (whenever that lands) will close it out.

Concrete next actions:
1. Spawn a fresh Extractor subagent on `imprivata`. Use `pipeline.build_extractor_prompt('imprivata')` as the prompt template; supplement with Imprivata-specific hints from `CLAUDE.md` if needed.
2. Finalize via `python run.py --slug imprivata --raw-extraction /tmp/imprivata.raw.json --no-commit`.
3. Run `python scoring/diff.py --slug imprivata`.
4. Spawn the Adjudicator subagent on the diff — same contract as the Medivation pass (`scoring/results/medivation_adjudicated.md` is the template).
5. Separate the divergences into: (a) generalization defects new to Imprivata, (b) Medivation-known conventions recurring, (c) Imprivata-specific rulebook gaps.
6. Fix (a) atomically. Hand (b) and (c) back to Austin for decisions.

**Alternative:** if Austin has landed convention-pin decisions between sessions, start there instead — apply them, rebuild references, re-run Medivation (counts toward the 3-run exit criterion), then advance to Imprivata.

---

## Operating notes for the next Claude

1. **Architecture is Claude-Code-driven**, not autonomous Python. `run.py` is a
   CLI shim for finalization; the Extractor is a Claude Code subagent spawned
   via the Agent tool with a clean-slate context. See `SKILL.md` §Pipeline for
   the architecture diagram.

2. **Do NOT add Anthropic SDK calls to Python.** `pipeline.py` is deterministic
   Python only. Subagents are orchestrated by the conversation, not from
   Python. This was a course correction partway through the first iteration;
   if you see API-call machinery in old comments, ignore it.

3. **Ground truth is the filing, not Alex's reference.** See
   `CLAUDE.md` §Ground-truth epistemology. Every diff divergence gets one of
   four verdicts (ai-right / alex-right / both-defensible / both-wrong)
   adjudicated against the filing. Don't "fix" the AI to match Alex if Alex
   is wrong.

4. **Auto mode**: if the session hands you auto mode, execute atomic commits
   without pausing. If auto mode is OFF, treat anything beyond the explicit
   request as a suggestion to check back with Austin.

5. **Hook reminders lie.** The `READ-BEFORE-EDIT` hook will fire even after a
   successful `Write` in the same session. Trust the `Write`/`Edit` tool's own
   success/failure response, not the hook's warning.

6. **Rulebook changes need atomic commits.** Every `rules/*.md` change requires
   a propagation sweep: `scripts/build_reference.py` → rebuild references,
   `pipeline.py` → vocabulary constants, `prompts/extract.md` →
   procedure + self-check, `pipeline.build_extractor_prompt()` →
   non-negotiables. See commit `a099d3a` for the §C3 migration template.

7. **Convention differences surface as diffs.** If a diff shows a field
   difference that looks like "both sides are fine," it's almost certainly a
   missing rulebook pin. Don't silently resolve by changing one side; flag it
   for Austin.

8. **Never revert user or linter file modifications** without explicit
   instruction. The session will often open with `CLAUDE.md`, `SKILL.md`, or
   rule files freshly edited by Austin — treat those as authoritative.

9. **Stage 3 exit criterion**: 3 consecutive reference-set runs with no
   rulebook changes. This session banked iteration 1 of 3 for Medivation.
   Each rulebook change resets the clock on affected deals.

---

## Files to read before taking action

1. `CLAUDE.md` — project context, ground-truth epistemology, three-stage
   workflow, current status.
2. `SKILL.md` §Pipeline — Extractor subagent + Python Validator + Adjudicator
   architecture. Invocation contract, state contract, fail-loud rules.
3. `rules/*.md` — every rule is resolved (🟩 RESOLVED). Scan for the specific
   section referenced by any task you take on.
4. `pipeline.py` — Filing loader, Python Validator invariants (§P-R / §P-D /
   §P-S), writers, `build_extractor_prompt()`. Single flat module ~500 lines.
5. `scoring/diff.py` — AI-vs-Alex diff harness. Join key:
   `(normalized_bidder_alias, bid_note, bid_date_precise)`. Not a grader;
   a human-review aid.
6. `scoring/results/medivation_adjudicated.md` — the first-iteration
   adjudication pass from the clean-context Adjudicator subagent.
   Template for the Imprivata adjudication.

---

**Commit graph at handoff:**
```
ec22cbb Patch §B3 rough-anchor: inferred dates now populate bid_date_rough
a0397e1 Medivation re-extract post-patches: diff collapses 30→8 divergences
4ff5843 Make IB emission explicit: trigger on 'financial advisor to [Side]'
a099d3a Propagate §C3: unify bid rows under bid_note='Bid' + bid_type
7c59c91 Add §Q5: atomize Medivation's aggregated 'Several parties' rows
c4ec361 Fix §P-S3 'phase_termination_missing' misfire on same-date clusters
8ba3716 Fix 5 build_reference serialization bugs to match rulebook
031c371 Start Stage 3: Python validator + subagent-driven Extractor MVP
cbc6a0a Close Stage 2, hand off Stage 3, defer Workstream C indefinitely
0b0d4d7 Wire scoring/diff.py end-to-end on Medivation
9dda10a Polish reference converter: mojibake salvage + A3 rank gap
3241785 Kick off Stage 2: reference/alex answer key + converter
f57a2aa Complete Stage 1: resolve 54 rulebook questions, scaffold pipeline
```
