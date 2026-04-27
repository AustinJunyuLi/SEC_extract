# Six-Policy Update — Alex 2026-04-27 Directive

**Status:** DRAFT (awaiting user review)
**Date:** 2026-04-27
**Author:** Austin (with Claude assist)
**Supersedes:** `quality_reports/decisions/2026-04-26_six-policy-decisions.md` decisions #2, #3, #6 — *to be deleted, not annotated, per §0 below*

---

## §0 — Guiding principle (non-negotiable)

**No backward compatibility. No compromise. No going back.**

This batch deletes stale rules, deletes stale code, deletes stale data, and deletes stale documentation. There are no shims, no migration helpers, no "deprecated" markers, no annotated-supersede notes, no preserved-for-forensics directories, no old-format readers, no fallback paths. Git history is the compatibility record. If a future contributor wants to know what the rules used to say, they `git log` it.

Every commit in this batch leaves the repo in a state where the *only* truth is the new truth.

---

## §1 — Background

Alex transmitted six policy updates on 2026-04-27. They materially change schema, rules, validator, prompt, reference data, and the active decisions record:

1. **Drop `non_us` and `public`** from `bidder_type`. Keep `base ∈ {"s","f","mixed"}` only. `bidder_type` flattens from object to scalar.
2. **Operating acquirer only.** No legal-shell sidecar. `Acquirer_legal` deleted everywhere.
3. **Universal atomization.** Bidders never aggregate. Including the `Executed` row — petsmart's consortium produces 5 Executed rows, mac-gray's produces 2.
4. **180-day phase separator.** Confirms the existing §L2 / §P-L2 design; tightens "6 months" wording to "180 calendar days" so language matches the validator constant.
5. **Range bids unconditionally informal.** Both endpoints recorded. `bid_type = "informal"` whenever `bid_value_lower < bid_value_upper`. Hard validator + soft conflict flag.
6. **Reference book regenerated** under all of the above.

---

## §2 — Scope

**In scope (this spec, this batch):**
- Rule files: `rules/*.md`, `prompts/extract.md`, `SKILL.md`, `skill_open_questions.md`
- Code: `pipeline.py`, `scripts/build_reference.py`, `scoring/diff.py`, `scripts/export_alex_csv.py`, `tests/`
- Reference data: `reference/alex/*.json` (regenerated from updated converter)
- Stale-data deletion: `state/flags.jsonl`, `output/extractions/*.json`, `quality_reports/decisions/2026-04-26_six-policy-decisions.md`
- Handoff doc bundled into C6

**Out of scope (deferred or explicitly rejected):**
- Live AI re-extraction on the 9 reference deals (deferred to a separate C7 workstream that runs per-deal under Austin's adjudication clock)
- Live AI extraction on the 392 target deals (gated behind verification cycle; not unblocked by this batch)
- Backward-compatibility shims (rejected per §0)
- Annotation of superseded docs (rejected per §0; full delete instead)
- Preservation of stale `output/extractions/*.json` for forensics (rejected per §0)

---

## §3 — Requirements

### MUST

| ID | Requirement | Clarity |
|---|---|---|
| M1 | `bidder_type.non_us` removed from schema, rules, prompt, code, tests, and all 9 reference JSONs | CLEAR |
| M2 | `bidder_type.public` removed from schema, rules, prompt, code, tests, and all 9 reference JSONs | CLEAR |
| M3 | `bidder_type` flattened from object `{base, non_us, public}` to scalar `"s" \| "f" \| "mixed" \| None` | CLEAR |
| M4 | `Acquirer_legal` field deleted from schema, rules (§N4 deleted entirely), prompt, code, diff comparator, tests, and all 9 reference JSONs | CLEAR |
| M5 | `Acquirer` records the operating entity only; for the 4 sponsor-backed reference deals (`petsmart-inc`, `mac-gray`, `zep`, `saks`), the converter rewrites Alex's xlsx `Acquirer` to the operational name and emits info flag `acquirer_normalized` | CLEAR |
| M6 | `rules/bidders.md` §E2.a (Executed-row joint-bidder collapse) deleted entirely | CLEAR |
| M7 | `rules/bidders.md` §E2.b table collapsed: filing narrates a multi-bidder event → one row per identifiable signer; numeric count without names → count-many placeholder rows per §E5 | CLEAR |
| M8 | New `Q7_EXECUTED_MEMBERS` static dict in `scripts/build_reference.py` with hardcoded constituent lists for the 4 sponsor-backed deals | CLEAR |
| M9 | New `apply_q7_executed_atomization()` function clones the `Executed` row N times per `Q7_EXECUTED_MEMBERS[slug]`, emitting info flag `executed_atomized` and removing `joint_bidder_members` from each row | CLEAR |
| M10 | Range bids unconditionally classified `bid_type = "informal"` whenever `bid_value_lower` and `bid_value_upper` are both numeric and `lower < upper` | CLEAR |
| M11 | New hard validator `bid_range_must_be_informal` in `pipeline.py` `_invariant_p_g2`: range present + `bid_type != "informal"` → fail | CLEAR |
| M12 | New soft flag `range_with_formal_trigger_override` emitted by extractor when a formal trigger phrase coexists with a range structural signal (range still wins; flag preserves audit trail) | CLEAR |
| M13 | Converter `_migrate_bid_note()` auto-coerces legacy xlsx rows where `range present + bid_type = "formal"` → `bid_type = "informal"` with info flag `range_forced_informal_per_g1` | CLEAR |
| M14 | `rules/events.md` §L2 wording: "6 months" → "180 calendar days" (three places). No semantic change | CLEAR |
| M15 | All 9 `reference/alex/*.json` files regenerated from updated converter under the rules from M1–M14 | CLEAR |
| M16 | `state/flags.jsonl` deleted (clean slate; pipeline recreates on first append) | CLEAR |
| M17 | All 9 `output/extractions/*.json` deleted (clean slate; deferred C7 workstream regenerates per deal) | CLEAR |
| M18 | `quality_reports/decisions/2026-04-26_six-policy-decisions.md` deleted (no annotation, full delete per §0) | CLEAR |
| M19 | Legacy tests asserting `non_us`, `public`, `Acquirer_legal` behavior deleted from `tests/` (not converted to negative tests) | CLEAR |
| M20 | `SKILL.md` and `skill_open_questions.md` updated in lockstep with each concept's commit (no bulk catch-up commit) | CLEAR |
| M21 | Each commit in C1–C5 ships rule + prompt + code + tests aligned. No commit leaves the repo internally inconsistent | CLEAR |
| M22 | C6 ships regenerated reference JSONs + handoff doc together | CLEAR |
| M23 | All commits in this batch land in 6+1 sequence per §4 below; no out-of-order merges | CLEAR |

### SHOULD

| ID | Requirement | Clarity |
|---|---|---|
| S1 | New tests covering petsmart 5-row Executed expansion (BC Partners + Caisse + GIC + StepStone + Longview) | CLEAR |
| S2 | New tests covering mac-gray 2-row Executed expansion (CSC + Pamplona) | CLEAR |
| S3 | Q5 Medivation docstring updated to reflect that atomization is universal (not a special case protecting against §E2.b's deleted carve-out) | CLEAR |
| S4 | Each commit's message names the concept and references this spec | CLEAR |
| S5 | `pre-reextract-2026-04-27` git tag placed before C6 to enable `git diff` against pre-regeneration state during verification | CLEAR |

### MAY

| ID | Requirement | Clarity |
|---|---|---|
| Y1 | New defensive validator `executed_member_no_nda` (soft) flagging Executed-row members who lack an upstream NDA in the same phase | CLEAR (optional; defer to implementation plan) |

---

## §4 — Architecture & commit sequence

Three layers move in lockstep. Each commit pairs the rule change with its code implementation; reference-JSON regeneration is deferred to a single mechanical commit at the end.

```
Layer A: Rules + prompt   rules/*.md, prompts/extract.md, SKILL.md, skill_open_questions.md
Layer B: Code             pipeline.py, scripts/build_reference.py, scoring/diff.py,
                          scripts/export_alex_csv.py, tests/*
Layer C: Reference data   reference/alex/*.json (9 files)
Layer D: Live extractions output/extractions/*.json + state/  ← deferred to C7 workstream
```

| # | Concept | Layers | Touches |
|---|---|---|---|
| C1 | Drop `non_us` + `public`, flatten `bidder_type` to scalar | A + B | rules/bidders.md §F1+§F2; rules/schema.md §R1; prompts/extract.md; build_reference.py `_bidder_type_note_signals` + `build_bidder_type`; pipeline.py canonicalization; scoring/diff.py; export_alex_csv.py; tests/test_reference_converter.py + tests/test_diff.py; SKILL.md; skill_open_questions.md |
| C2 | Drop legal acquirer | A + B | rules/schema.md §N4 deleted + §R1 entry; prompts/extract.md; build_reference.py `Q6_ACQUIRER_OVERRIDES` (delete sidecar half, keep operating rewrite as new `Q6_ACQUIRER_REWRITE`); scoring/diff.py `COMPARE_DEAL_FIELDS`; tests/; SKILL.md |
| C3 | Universal atomization | A + B | rules/bidders.md §E2.a deleted + §E2.b rewritten; rules/events.md §I1 (no change but verify); prompts/extract.md (CA-classification para, numeric-count para); build_reference.py new `Q7_EXECUTED_MEMBERS` + `apply_q7_executed_atomization()`; tests/; SKILL.md; skill_open_questions.md |
| C4 | Range bids → informal + soft override flag | A + B | rules/bids.md §G1 + §G2 + §H1; rules/invariants.md §P-G2; prompts/extract.md; pipeline.py `_invariant_p_g2` (new sub-check `bid_range_must_be_informal`, hard); build_reference.py `_migrate_bid_note` (auto-coerce); tests/test_invariants.py |
| C5 | §L2 wording tighten "6 months" → "180 calendar days" | A only | rules/events.md §L2 (three places); no code change |
| C6 | Regenerate reference data + write handoff doc | C | reference/alex/*.json (9 files) regenerated mechanically from updated converter; quality_reports/handoffs/2026-04-27_six-policy-update.md created. Stale-file deletion ALSO happens here: `state/flags.jsonl`, `output/extractions/*.json`, `quality_reports/decisions/2026-04-26_six-policy-decisions.md`. |
| C7 | Re-run pipeline on 9 reference deals | D | **DEFERRED**. Per-deal Claude session. Validator runs new invariants. `scoring/diff.py` produces Austin-readable diff against the freshly-regenerated reference JSON. Austin manually adjudicates each disagreement against the SEC filing per the four-verdict framework (CLAUDE.md). Marks `state/progress.json` `verified` on clean. Not part of this batch. |

---

## §5 — Per-concept rule deltas (Layer A)

### C1 — Drop `non_us` + `public`, flatten `bidder_type`

**`rules/bidders.md`**
- §F1: collapse `{base, non_us, public}` → scalar `base ∈ {"s","f","mixed","null"}`. Rewrite "Why structured object" rationale to "Why scalar."
- §F2: deleted entirely (lines 234–314 of current file). The decision table, "silent → null" subsection, "why strict-filing-only" rationale, and PE-sponsor tri-state subsection all go.

**`rules/schema.md`**
- §R1 entry for `bidder_type`: rewrites to `string OR null, one of {"s","f","mixed"}`. Cross-reference to §F2 removed.

**`prompts/extract.md`**
- Lines 73–76 (the `bidder_type.public` paragraph) deleted.
- Self-check items in lines 145–146 referencing public/non_us deleted.

**`SKILL.md`** and **`skill_open_questions.md`**: any reference to §F2's tri-state logic, public/non_us scoring, or bidder-type tri-state evaluation deleted.

### C2 — Drop legal acquirer

**`rules/schema.md`**
- §N4 deleted entirely (lines 399–477).
- §R1 entry for `Acquirer`: rewrites to "the entity that actually negotiated and will own the target's assets. For consortia, the lead sponsor named in the primary position; fall back to filing's verbatim consortium label only when no lead is identifiable. Skip Delaware shells and merger-vehicle entities."
- §R1 entry for `Acquirer_legal`: deleted.
- Cross-reference table updated.

**`prompts/extract.md`**
- Lines 78–79: rewrites to one paragraph dropping the `Acquirer_legal` half. Lead-sponsor heuristic preserved. "Skip Delaware shells / merger-vehicle entities" preserved.

**`SKILL.md`**: any reference to §N4 sidecar mechanic, dual-acquirer recording, or `Acquirer_legal` field deleted.

### C3 — Universal atomization

**`rules/bidders.md`**
- §E1: rewritten with stronger language. Atomization is unconditional. No exceptions. Add explicit clause: "This applies to every event type — NDA, Bid, Drop*, Restarted, Terminated, **and Executed**. The Executed row is no exception."
- §E2.a (Executed-row joint-bidder collapse): deleted entirely.
- §E2.b table: collapsed to single row. Filing narrates a multi-bidder event → one row per identifiable signer; numeric count without names → count-many placeholder rows per §E5.

**`rules/events.md`**
- §I1: no changes (DropSilent and consortium-drop atomization already conformant). Verify during implementation.

**`prompts/extract.md`**
- Lines 49–50 (CA classification): keep three CA types. Drop any reference to consortium-collapse exemption.
- Lines 82–95 (numeric-count rule): no change; already enforces atomization.
- Add new explicit instruction: "For the Executed row, atomize per signer named in the merger agreement's signature block. If the filing narrates the agreement as signed by 'Buyer Group' and the constituent firms are identifiable elsewhere in the filing, emit one Executed row per constituent."

**`SKILL.md`** and **`skill_open_questions.md`**: any reference to §E2.a or to the deleted §E2.b carve-out deleted. Atomization stance updated to "universal."

### C4 — Range bids → informal

**`rules/bids.md`**
- §G1: keep range as a structural signal of informality. Rewrite the "if a range coexists with a formal trigger, the formal trigger wins" carve-out to: **"Range always wins. Whenever `bid_value_lower` and `bid_value_upper` are both populated and numeric with `lower < upper`, `bid_type = 'informal'`, regardless of any formal trigger phrase the filing uses. Emit soft flag `range_with_formal_trigger_override` when a formal trigger coexists, to preserve audit trail."**
- §G2: range satisfier path stays; extend hard requirement: range present → `bid_type` MUST equal `"informal"`.
- §H1: tighten "SHOULD" → "MUST" wherever `bid_value_lower` / `bid_value_upper` requirements are stated. Both endpoints required when bid is shaped as a range.

**`rules/invariants.md`**
- §P-G2: existing `bid_range_inverted` check stays. New sub-check `bid_range_must_be_informal` (hard): if `bid_value_lower < bid_value_upper` and `bid_type != "informal"` → fail.

**`prompts/extract.md`**
- Lines 60–61: range exemption from `bid_type_inference_note` requirement stays. Add: range additionally locks `bid_type = "informal"`.
- Self-check at lines 145–146: same.

### C5 — §L2 wording tighten

**`rules/events.md`**
- §L2: "6 months or more apart" → "180 calendar days or more apart" (three places).
- No semantic change. Validator at `pipeline.py:1008` already coded to 180.

---

## §6 — Per-concept code changes (Layer B)

### C1 — Drop `non_us` + `public`, flatten `bidder_type`

**`scripts/build_reference.py`**
- Delete `_bidder_type_note_signals()` entirely (lines 540–595).
- Rewrite `build_bidder_type()` (lines ~600–635) to return scalar `"s" | "f" | "mixed" | None` directly. Logic: parse `bidder_type_strategic` / `_financial` / `_mixed` columns from xlsx, return one of three strings (or None if all blank).
- Update every callsite that unpacks `bt["base"]` → `bt` directly.

**`pipeline.py`**
- Comparator changes from dict-equality to string-equality at canonicalization and conflict-detection sites.
- `_invariant_p_g2` and other validators: no change (none read `non_us` / `public`).

**`scoring/diff.py`**
- `COMPARE_EVENT_FIELDS`: `bidder_type` stays; comparator logic simplifies to scalar compare.

**`scripts/export_alex_csv.py`**
- Lines 220–240 (the `non_us_val` / "Non-US" label / "public" label CSV-emission block) deleted.
- CSV emits `bidder_type` as a single scalar column.

**`tests/`**
- `test_reference_converter.py` lines 55, 66, 77, 101: rewrite assertions to `assert sanofi_bid["bidder_type"] == "s"`.
- `test_diff.py` lines 46, 59, 74, 88: same.
- `test_bidder_type_pe_token_keeps_public_null` and any sibling tri-state tests: deleted entirely.

### C2 — Drop legal acquirer

**`scripts/build_reference.py`**
- Delete `Q6_ACQUIRER_OVERRIDES` dict entirely (lines 140–180).
- Delete `apply_q6_acquirer_override()` function entirely (lines 186–207).
- Delete its call at line 1074.
- Delete `Acquirer_legal` from deal-init schema (line 482).
- Add new `Q6_ACQUIRER_REWRITE: dict[str, str]` mapping slug → operational acquirer string, for petsmart, mac-gray, zep, saks. (Same data as today's `Q6_ACQUIRER_OVERRIDES["operating"]`, just stripped of the `legal` half.)
- Add `apply_q6_acquirer_rewrite()` that overwrites `deal["Acquirer"]` and emits info flag `acquirer_normalized`.

**`pipeline.py`**
- No change. Validator never reads `Acquirer_legal`.

**`scoring/diff.py`**
- Line 44: remove `"Acquirer_legal"` from `COMPARE_DEAL_FIELDS`.

**`scripts/export_alex_csv.py`**
- No change. Already emits only `Acquirer`.

**`tests/`**
- Any test asserting `Acquirer_legal` presence or value: deleted.

### C3 — Universal atomization

**`scripts/build_reference.py`**
- §Q2 (Zep row 6390 expansion): kept; docstring updated to note that atomization is universal.
- §Q5 (Medivation "Several parties"): kept; docstring updated similarly (S3).
- New §Q7 — Executed-row atomization:
  - `Q7_EXECUTED_MEMBERS: dict[str, list[str]]` with hardcoded lists for petsmart-inc (5 members), mac-gray (2 members), zep (1 member, no expansion needed), saks (1 member, no expansion needed). Member names sourced from each filing's signature block.
  - `apply_q7_executed_atomization(slug, events)` clones the Executed row `len(Q7_EXECUTED_MEMBERS[slug])` times if applicable, sets `bidder_alias` and `bidder_name` per member, removes `joint_bidder_members` (no longer needed), emits info flag `executed_atomized` per row.
  - Called in the build pipeline alongside §Q2 and §Q5.

**`pipeline.py`**
- `_invariant_p_d5` and `_invariant_p_d6` (per-phase engagement): no change; iterate per row and atomization-friendly.
- §P-S1 (DropSilent enforcement): no change.
- BidderID sequence-number assignment: no change (atomized rows are still events, sequence stays 1..N).
- Optional Y1 — new soft check `executed_member_no_nda`: for every Executed row, ensure same-phase NDA exists for that bidder. Defer to implementation plan.

**`scoring/diff.py`**
- Atomized-vs-aggregated alias-recovery logic (lines 274–275): kept as insurance.

**`tests/`**
- New tests for petsmart 5-row Executed expansion (S1).
- New tests for mac-gray 2-row Executed expansion (S2).

### C4 — Range bids → informal

**`pipeline.py` `_invariant_p_g2`** (lines 780–825)
- Existing `bid_range_inverted` check stays.
- New sub-check `bid_range_must_be_informal` (hard): range present (`lower < upper`, both numeric) AND `bid_type != "informal"` → fail.
- Note-or-range satisfier path unchanged.

**`pipeline.py` `_rank()`** (lines 828–835): no change. Formal-bid rank-7 bump still works for non-range formal bids.

**`scripts/build_reference.py` `_migrate_bid_note()`** (lines 641–701)
- Add: if migrated row has `bid_value_lower` and `bid_value_upper` both numeric and `lower < upper`, override `bid_type = "informal"` regardless of legacy label. Emit info flag `range_forced_informal_per_g1`.

**`tests/`**
- `test_invariants.py` lines 291–292: update to test new hard flag.
- New test: range coexisting with formal trigger phrase → `bid_type = "informal"` + soft flag `range_with_formal_trigger_override`.

### C5 — §L2 wording tighten

No code changes.

---

## §7 — Reference data regeneration (C6, Layer C)

**Pre-step.** Tag current state: `git tag pre-reextract-2026-04-27`.

**Regeneration.** Run converter top-to-bottom: `python scripts/build_reference.py --all`. Verified entry-point at `scripts/build_reference.py:1162` (argparse main).

**Per-deal change profile** (from scan):

| Deal | Executed Δ | bidder_type changed | Acquirer rewrite | Range coercion |
|---|---|---|---|---|
| medivation | 0 | yes (all rows) | no | possibly |
| imprivata | 0 | yes | no | possibly |
| zep | 0 (single sponsor: New Mountain) | yes | yes (NM Z Parent → New Mountain Capital) | possibly |
| providence-worcester | 0 | yes | no | possibly |
| penford | 0 | yes | no | possibly |
| mac-gray | +1 (CSC + Pamplona) | yes | yes (Spin Holdco → CSC ServiceWorks) | possibly |
| petsmart-inc | +4 (BC Partners + Caisse + GIC + StepStone + Longview) | yes | yes (Argos Holdings → BC Partners) | possibly |
| stec | 0 | yes | no | possibly |
| saks | 0 (single: Hudson's Bay) | yes | yes (Harry Acquisition → Hudson's Bay) | possibly |

Total: +5 new Executed rows across the 9 deals.

**Verification gate** (must all pass before C6 commits):
1. Converter runs without errors on all 9 deals.
2. `git diff pre-reextract-2026-04-27 -- reference/alex/` — every diff line traces to C1, C2, C3, or C4. Anything else blocks commit.
3. `python run.py validate-only reference/alex/<deal>.json` for each of 9 — no new hard validator fires (`bid_range_must_be_informal`, etc.). Soft / info flags expected: `acquirer_normalized`, `executed_atomized`, `range_forced_informal_per_g1`.
4. Manual spot-check petsmart and mac-gray: open JSON, confirm Executed rows expanded correctly.

**Stale-file deletion (same commit):**
- `state/flags.jsonl` deleted.
- `output/extractions/*.json` deleted (all 9 files).
- `quality_reports/decisions/2026-04-26_six-policy-decisions.md` deleted.

**Handoff doc creation (same commit):**
- `quality_reports/handoffs/2026-04-27_six-policy-update.md` written. Summarizes the rule changes for whoever runs C7 later. Cross-references this spec.

**Commit message:** `reference: regenerate alex/*.json under universal-atomization + scalar bidder_type + operational-acquirer + range-informal rules; delete stale state/output/decisions docs`

---

## §8 — Verification per commit

Each of C1–C5 passes this gate before commit:
1. `pytest tests/` — full suite passes.
2. `python -c "from pipeline import validate"` — import smoke test.
3. `git diff --stat` — only files in §6's list changed.
4. `grep -r "<deleted-symbol>" rules/ prompts/ pipeline.py scripts/` after C1 + C2: zero matches for `non_us`, `Acquirer_legal`, `\"public\"`. Catches leftovers.

C6 has its own gate (§7).

C7 is per-deal, deferred, runs on Austin's adjudication clock.

---

## §9 — Rollback

Each commit is isolated; rollback is a single `git revert`.

| Commit | Defect class | Action |
|---|---|---|
| C1 | Wire-format breaks downstream tool | revert C1; rule + code revert together; reference JSONs untouched (still old format until C6) |
| C2 | Acquirer rewrite wrong for one deal | revert C2; fix `Q6_ACQUIRER_REWRITE` entry; recommit |
| C3 | Q7 dict has wrong member name | revert C3; edit `Q7_EXECUTED_MEMBERS`; recommit |
| C4 | Range coercion misclassifies a legitimate formal bid | revert C4; reconsider auto-coerce policy |
| C5 | Wording-only — defect unlikely | revert C5 |
| C6 | Regenerated JSON unexpectedly differs | revert C6; re-run converter after fix |

No shim layers, no preserved-old-format paths. Rollback is clean by construction.

---

## §10 — Clarity status

All major aspects of this spec are **CLEAR**. No `ASSUMED` items. No `BLOCKED` items.

Three brainstorming clarifications were resolved before drafting:
- Universal atomization extends to `Executed` rows (Q1)
- Range coexisting with formal trigger emits soft flag, range still wins (Q2 → Option B)
- 180-day rule is ratification of existing §L2 / §P-L2, not extension (Q3 → Option A)

Six edge-case calls were resolved:
- `state/flags.jsonl` → delete (clean slate)
- `output/extractions/*.json` → delete (clean slate)
- `SKILL.md` / `skill_open_questions.md` → updated in lockstep with each concept's commit
- Old decisions doc → delete (no annotation)
- Q5 docstring → updated in C3
- Legacy tests → deleted (not converted to negative tests)

---

## §11 — Implementation handoff

After user approves this spec:
1. Invoke `superpowers:writing-plans` skill to draft an implementation plan.
2. Plan saved to `quality_reports/plans/2026-04-27_six-policy-update.md`.
3. Plan executed via orchestrator protocol (CLAUDE.md, plan-first-workflow rule). Each commit gets a TodoWrite item.
4. C6 verification gate must pass cleanly before commit.
5. C7 (live re-extraction on 9 reference deals) is deferred to a separate workstream that runs per-deal under Austin's adjudication clock.

End of spec.
