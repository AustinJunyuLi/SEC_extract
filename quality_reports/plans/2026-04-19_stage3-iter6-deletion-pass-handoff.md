# Stage 3 Iteration 6 Handoff — Deletion Pass + TIER-1 Safety Fixes

**Intended reader.** A fresh Claude (or Austin) opening this repo after a
context clear / `/compact`. Read this file FIRST, then `CLAUDE.md`, then
`git log --oneline -15` before acting.

**Date:** 2026-04-19
**Predecessors:**
- `2026-04-19_stage3-iter3b-handoff.md` — surfaced 6 defect classes
- `2026-04-19_stage3-iter4-consolidated-patch.md` — the iter-4 patch plan
- `2026-04-19_stage3-iter4-handoff.md` — iter-4 results (7/9 clean)
- (unwritten) iter-5 simplification — committed `48ed183`, 9/9 passed_clean

**Branch:** `claude/sharp-sutherland-8d60d7` on the worktree at
`/Users/austinli/bids_try/.claude/worktrees/sharp-sutherland-8d60d7/`.

**HEAD commit at handoff:** `48ed183` (iter-5 simplification).

---

## TL;DR for the fresh reader

After landing iter-4 (6 defect classes + §B3 symmetry) and iter-5 (3
simplifications + 2 tightenings), all 9 reference deals pass
`passed_clean`. The user then requested an adversarial audit pass —
5 subagents with clean slates reviewed the system for overfit.

**The audits converged on a consistent verdict:** the system has been
incrementally patched to fit the 9 references, is **not** ready for
392 target deals, and iter-5's own "tightenings" were themselves
overfit. Recommended remedy is **iter-6 as a deletion pass**: strip
accumulated scars, add missing safety checks, and replace the
9-deal exit clock with a generalization canary.

---

## Where we are

### Commit graph

```
48ed183 Iter-5 simplification: generalize §P-S3, remove redundant §C4
        exemption, schema doc, tighten §D1.a
ccd1338 Handoff: Stage 3 iter 4; 7/9 clean
89a578d stec iter 4 extraction
d02a545 saks iter 4 extraction
eb878c7 petsmart-inc iter 4 extraction
ab78e09 mac-gray iter 4 extraction (1 hard residual, later fixed by iter-5)
2e838d1 penford iter 4 extraction (1 hard residual, later fixed by iter-5)
2ce4ba9 providence-worcester iter 4 extraction
a419cbf zep iter 4 extraction
892a029 imprivata iter 4 extraction
bfd9b2c medivation iter 4 extraction + state bundle
ff627fb Iter-4 consolidated patch: close Classes A/B/C/D/E/F + §B3
90102f9 Handoff: iter 3b
[earlier iter-3 and iter-3b commits]
```

### Current validator state

- All 9 reference deals: `passed_clean`, 0 hard flags under iter-5
  rulebook + pipeline + prompt.
- `state/progress.json` reflects this.
- `state/flags.jsonl` carries iter-3/3b/4 historical flags (append-only).

### Iter-5 changes that should be reconsidered (self-criticism)

Iter-5 commit `48ed183` introduced a "tightening" of §D1.a that is
itself an overfit:

- **§D1.a closed verb list** in `rules/events.md` (10 verbs:
  `declined`, `did not respond`, `did not engage`, `withdrew`,
  `rejected`, `terminated`, `ceased`, `declined to engage`, `took no
  further action`, `no further contact`).
- **Divergence**: `prompts/extract.md:24` only lists 6 verbs
  (`declined`, `did not respond`, `withdrew`, `rejected`, `terminated`,
  `ceased`). This is a **contradiction between the two prompt
  sources**. The extractor will see both (pipeline.py embeds its own
  prompt addendum) and may pick either.
- **Real filings use synonyms** the list doesn't cover: `rebuffed`,
  `elected not to pursue`, `not entertained`, `discontinued further
  discussions`, `the approach was not pursued`. A target deal using
  any of these will fail the prompt-side check, the extractor will
  omit the `unsolicited_first_contact` flag, and §P-D6 will fire
  hard → false positive.

---

## Audit findings (five subagents, clean slate, adversarial)

### Audit 1 — rulebook minimalism

- 94 reference-deal name mentions across 5 rule files (events.md 41,
  dates.md 26, bidders.md 16, bids.md 7, schema.md 4).
- §D1.a closed verb list is overfit (confirmed by audits 3 and 5 too).
- §Q1–§Q5 (`rules/dates.md:400-585`) are **converter-side** rules
  (xlsx → JSON row fixes); they belong in
  `scripts/build_reference.py` or `reference/alex/README.md`, not
  in extractor rules.
- §K3 (`rules/events.md:558-576`) is a 20-line section whose only
  purpose is relabeling Providence row 6058 — another converter concern.
- §D1.b (multi-activist, ~40 lines in `rules/events.md`) is redundant
  with §E1 atomization — delete and add one line to §E1.
- §E2.b iter-5 "simplification" is still 80+ lines with
  mac-gray/petsmart-specific worked examples. Collapse to ≤20 lines.
- §C4 (`rules/bids.md`) and §D1.a (`rules/events.md`) describe the
  same pre-NDA phenomenon with different flags. Merge: one flag
  `pre_nda_bid` + `nda_exists_later: bool`.
- Tombstone sections (`§F3` in bidders.md, `§I2` in events.md, `§M2`
  in bids.md) just say "folded into §X" — delete.
- Trailing "Open questions" blocks in all 5 rule files are duplicates
  of the resolved-rules sections (~200 lines). Delete all 6.
- Rules reference internal validator helpers by name (`_invariant_p_d6`,
  `_rank`) — break encapsulation. Refer to §-tags, not implementation.

**Estimated cleanup: ~25-30% of rulebook content removable without
semantic loss.**

### Audit 2 — validator (`pipeline.py`)

- **CRITICAL: §P-D2 legacy-fixture tolerance** (`pipeline.py:749-751`).
  `rough.startswith(precise)` silently accepts rows that violate §P-D2.
  0 firings across 9 deals — pure dead code path. **Risk on target
  deals**: an extractor that copies `"2016-04-13"` into both
  `bid_date_precise` AND `bid_date_rough` bypasses §P-D2 without any
  flag. Delete the carve-out.

- **CRITICAL: §G2 `bid_type` evidence check is resolved in the
  rulebook but NOT implemented in the validator.** `rules/bids.md §G2`
  says "hard invariant: every non-null `bid_type` requires a trigger
  phrase in `source_quote` OR a `bid_type_inference_note`."
  `rules/invariants.md:202-205` says "should move into MVP." No code
  enforces it. The extractor can stamp `bid_type="formal"` with no
  evidence and it passes. Add `_invariant_p_g2`.

- **CRITICAL: `_apply_unnamed_nda_promotions`** (`pipeline.py:1177-1182`)
  writes `target["bidder_name"] = new_name` BEFORE checking if
  `new_name` is in `bidder_registry`. A promotion to an unregistered
  bidder silently succeeds at finalize, then §P-R5 flags the event
  (misdirecting blame from the promotion logic). Hard-flag the
  mismatch directly.

- `_invariant_p_d3` rules 5 and 6 (date-monotone + same-date rank
  check) are redundant after `_canonicalize_order()` sorts events
  by (date, rank, narrative). They can only fire on pre-canonical
  input. Either (a) only run `_invariant_p_d3` in dry-run mode, or
  (b) delete rules 5/6.

- `ValidatorResult.soft_flags()` method declared but never called.
- `PipelineResult.validator` field never read.
- `_severity_counts()` property recomputes counts on every access.

- **Divergent rank tables**: `pipeline.py EVENT_RANK` and
  `scripts/build_reference.py A3_RANK` drift from each other and from
  `rules/dates.md §A3`. Reconcile to single source.

- `unsolicited_first_contact` validator exemption trusts the
  extractor's flag without verifying the prompt's tightened
  conditions. If iter-6 keeps the flag, mirror the condition check
  in Python.

### Audit 3 — extractor prompt

- **CRITICAL: §D1.a verb-list contradiction** (see above under "Iter-5
  changes that should be reconsidered").

- **CRITICAL: §B3 legacy-fixture tolerance** in `_invariant_p_d2` is
  NOT documented in the prompt. An extractor that literally obeys the
  bi-directional symmetry rule will believe itself in violation for
  behaviors Python silently tolerates.

- **CRITICAL: inference-flag severity inconsistency.**
  `pipeline.build_extractor_prompt` line 378-382 says IB retention
  inference gets `severity: "soft"`. `prompts/extract.md:26` makes the
  bi-directional `bid_date_rough` rule a hard invariant using
  `date_inferred_from_context` as an example. Extractors may infer
  `soft` means optional.

- Prompt duplication: `prompts/extract.md` (137 lines) and
  `build_extractor_prompt()` (220 lines) restate the same conventions.
  3 points of actual drift between them.

- 4 reference-deal names in prompt (`Medivation`, `Pfizer/Centerview`,
  `Saks`, `CSC/Pamplona`, `Buyer Group`, `Petsmart`).

- Iter tags (`iter-4`, `iter-5 clarification`) litter the prompt;
  extractor doesn't care about iteration history.

- Self-check has 15 bullets; only 9 map to hard validator flags.

- Output template shows `multiplier: null` and exemplar row is
  `"Target Sale"` which never carries `bid_value*` fields → confuses
  structural vs required fields. `joint_bidder_members` and
  `unnamed_nda_promotion` are USED in extractions but MISSING from
  the template.

### Audit 4 — schema (rules/schema.md + output/extractions/)

Population rates across 416 event rows:

| Field | Populated | Action |
|---|---|---|
| `aggregate_basis` | 0/416 | **DROP** |
| `multiplier` | 0/416 | **DROP** (also 0 in Alex ref) |
| `stock_per_share` | 0/416 | **DROP** (0 in Alex; re-add if stock deal appears) |
| `bid_type_inference_note` | 4/416 | **UNDOCUMENTED** — add to §R1 or fold into flags |
| `_unnamed_nda_promotions` | leaked | Pipeline-internal; should not be in output JSON |
| `highly_confident_letter` | 416/416 = `false` always | Drop if no research need |
| `consideration_components` | 76/416 | **REDUNDANT** with `*_per_share` triple — drop; derive downstream |
| `bid_value_pershare` vs `lower/upper` | disjoint (54 vs 42 vs 0 overlap) | Document XOR constraint as §P invariant |
| `bidder_type` | nested `{base, non_us, public}` — 3 subfields always present when object exists | Consider flattening |
| `joint_bidder_members` | 7/416 | Justified for §E2.a; keep but sparse |
| `DateEffective` | 0/9 deals | Flag for Austin: verify a target deal populates it |

### Audit 5 — generalizability to 392 target deals

- **CRITICAL: `seeds.csv` `form_type` column is EMPTY for all 401
  rows.** Reference JSONs have `FormType` set (e.g., `DEFM14A`, `SC
  TO-T (via EX-99.(A)(1)(A))`), but the seed CSV doesn't feed it. The
  fetcher/pipeline derives it from EDGAR URLs — untested path for
  target URLs. Before the target gate opens, backfill and verify every
  URL resolves.

- **Reference set is 8/9 DEFM14A, 1/9 SC TO-T, 0/9 PREM14A, 0/9 S-4.**
  The rulebook claims support for all four, but PREM14A and S-4 paths
  have never been exercised.

- Reference dates span 2013-06 to 2016-08 (3 years). Target deals span
  2009-2021 (~12 years). Pre-2012 (RMBS-era legal templates) and
  post-2017 (SPAC-merge vocabulary) are not covered.

- **Unseen archetypes in the 9**:
  - Hostile tender offers (HIGH risk — different vocabulary)
  - Topped deals (HIGH — two Executed rows would break §E2.a hard)
  - Non-US targets/acquirers (HIGH — 55 foreign-marker acquirers in
    `seeds.csv`; §B1 season mapping, §G1 triggers, §D1.a verbs all
    assume US English)
  - SPAC / de-SPAC (MEDIUM — no §C1 vocabulary for PIPE / lock-up)
  - Bankruptcy §363 sales (MEDIUM — stalking-horse etc. not modeled)
  - Dutch / reverse auctions (LOW)
  - Mid-process consortium fracturing (MEDIUM — breaks §E2.b)

- **The exit criterion is wrong.** "3 consecutive unchanged-rulebook
  runs on 9 references" proves stability on the training set, not
  generalization. The missing piece is a canary run on ≥10 unseen
  target deals with hard-flag rate measured, BEFORE the full 392.

---

## Iter-6 plan — deletion pass, measured in lines removed

**Guiding principle (from user, 2026-04-19):** "I want the best system,
not overfit. Design needs to be minimalistic, efficient, scalable."

Do NOT keep layering. Iter-6 should remove more code/prose than it
adds. The safety checks that ARE added (TIER 1) are all things the
rulebook already promised but never implemented, not new features.

### TIER 0 — revert iter-5's own overfit

1. **Revert §D1.a closed verb list.** In `rules/events.md` §D1.a
   (around lines 162-222) and the corresponding prompt copies
   (`prompts/extract.md:24`, `pipeline.py build_extractor_prompt`
   line ~299), replace the 10-verb closed list with:
   > "Attach the `unsolicited_first_contact` flag when the filing
   > describes the target declining to engage OR the bidder withdrawing
   > before any NDA. The flag's `reason` field must quote the filing
   > language (≤120 chars, single-quoted) that authorized the
   > attachment. If the language is ambiguous, set `severity: 'soft'`
   > and let §P-D6 fire — Austin adjudicates."
2. Confirm extract.md and pipeline.build_extractor_prompt now agree
   on §D1.a (no contradictions).

### TIER 1 — safety checks the rulebook promised

3. **Delete `_invariant_p_d2` legacy-fixture carve-out**
   (`pipeline.py:749-751`). The `rough.startswith(precise)` branch
   is dead; its only purpose was accommodating `build_reference.py`
   fixtures that never flow through `pipeline.validate()`.
4. **Add `_invariant_p_g2`** enforcing `rules/bids.md §G2`: for
   every row with non-null `bid_type`, require either a trigger
   phrase from §G1 in `source_quote` OR a `bid_type_inference_note`
   field populated. Hard flag `bid_type_unsupported`.
5. **Fix `_apply_unnamed_nda_promotions`** (`pipeline.py:1177-1182`):
   raise hard flag `promotion_target_not_in_registry` if
   `promote_to_bidder_name` is not a key in `bidder_registry`. Do
   not perform the rewrite in that case.
6. **Drop phantom schema fields** from `rules/schema.md §R1`:
   `aggregate_basis`, `multiplier`, `stock_per_share`,
   `highly_confident_letter`. Update the prompt's output template
   to match. (If stock-consideration deals later appear, re-add on
   demand with a specific rule.)
7. **Add XOR invariant** for `bid_value_pershare` vs
   `bid_value_lower`/`bid_value_upper` — at most one side populated
   per row. New hard check `bid_value_shape_violation`.
8. **Remove `_unnamed_nda_promotions` leak** — verify
   `pipeline.finalize()` strips the key from the emitted JSON.

### TIER 2 — deletions (rulebook + prompt + pipeline)

9. **Delete trailing "Open questions" blocks** in all 5 rule files.
   They duplicate the resolved-rules sections at the top (~200
   lines removed).
10. **Delete tombstone sections**: `rules/bidders.md §F3`,
    `rules/events.md §I2`, `rules/bids.md §M2`. Each just points to
    another section.
11. **Delete `rules/events.md §K3`** (Providence 6058 relabel — not
    an extractor rule; move the one-sentence `Auction Closed`
    semantic into §C1's definition if not already there).
12. **Delete `rules/events.md §D1.b`** (multi-activist) and add a
    one-line mention to §E1: "Atomization applies to
    `Activist Sale` rows just like NDAs and Bids."
13. **Move `rules/dates.md §Q1-§Q5`** wholesale into
    `scripts/build_reference.py` module docstring or
    `reference/alex/README.md`. The extractor never sees those rows;
    they are converter-side.
14. **Simplify `rules/bidders.md §E2.b`** from 80+ lines with
    mac-gray/petsmart worked examples to ≤20 lines: "Emit one row
    per signer the filing narrates. Aggregate consortium into one
    row only when the filing describes a single signer with no
    per-constituent detail and no numeric count."
15. **Merge `rules/bids.md §C4` and `rules/events.md §D1.a`** into
    a single section with one flag (`pre_nda_bid`) + boolean
    `nda_exists_later`. Validator exempts §P-D6 only when
    `nda_exists_later = false`.
16. **Collapse prompt duplication.** Decide on a canonical source:
    either (a) `prompts/extract.md` is authoritative and
    `build_extractor_prompt` is a thin pointer (file paths + slug +
    output fence), OR (b) `build_extractor_prompt` is authoritative
    and `prompts/extract.md` is a viewer's aid. Pick one; remove
    duplication.
17. **Strip iter tags and ref-deal names from prompts.** No
    `(iter-4, Class D)`, no `"saks Company H"` by name, no
    `"Medivation"` in exemplar row.
18. **Reduce self-check from 15 bullets to 9** — one per hard
    validator flag. Drop items Python auto-corrects (BidderID
    ordering, post-execution press-release skip).
19. **Delete dead code**:
    - `ValidatorResult.soft_flags()` method
    - `PipelineResult.validator` field (unused)
    - `_invariant_p_d3` rules 5 and 6 IF `_canonicalize_order()` is
      guaranteed to run before validation. Otherwise keep but mark
      as dry-run-only.
20. **Reconcile rank tables**: `pipeline.py EVENT_RANK` and
    `scripts/build_reference.py A3_RANK` — derive both from
    `rules/dates.md §A3` or a shared JSON. Note: the worktree should
    not modify `build_reference.py` (per iter-3b handoff rules).
    Document the divergence as an action item for Austin; do not fix
    in iter-6.

### TIER 3 — generalization setup (may span iter-6 and iter-7)

21. **Populate `seeds.csv.form_type`** for all 401 rows. Use the
    EDGAR index URL to derive. Verify every URL fetches; any
    unfetchable URL is a `failed` deal and must be triaged.
22. **Generalization canary.** Pick 10 target deals at random
    (weighted by form type and announcement-year decile). Extract
    all 10 under the iter-6 rulebook. Measure hard-flag rate. This
    is the NEW exit signal — the 9-reference "3 consecutive clean
    runs" criterion is secondary.
23. **Reference set expansion** (Austin decides): add ≥1 PREM14A,
    ≥1 pure S-4, ≥1 non-US target. Without these, §Scope-2's
    advertised coverage is aspirational.

### Out of scope for iter-6

- Schema evolution for SPAC vocabulary / hostile tender mechanics —
  wait for canary to reveal what's missing.
- `_unnamed_nda_promotion` condition verification (mirror prompt
  rule into validator) — wait until iter-5's looser condition is
  stable.
- Mid-process consortium fracturing, topped deals — wait for canary.
- Southern-Hemisphere season mapping — wait for canary.

---

## Reference artifacts to read

Before executing iter-6, the fresh Claude should read:

1. **This file.**
2. `CLAUDE.md` — project context; note Ground-truth epistemology
   (Alex is reference, filing is truth).
3. `SKILL.md` — architecture contract.
4. `git log --oneline -20` — confirm commit state.
5. `rules/invariants.md` — especially §P-D2 and §G2 notes about
   MVP scope.
6. The 5 audit transcripts: they're not saved to disk (only in the
   prior conversation). If needed, re-invoke audits. Summaries
   above should suffice for execution.

---

## First actions on resume (after /compact)

1. `pwd` and `git log --oneline -3` to confirm state.
2. Read this handoff. Then read `CLAUDE.md`.
3. Start TIER 0 (revert iter-5 §D1.a tightening).
4. Continue to TIER 1, then TIER 2.
5. After TIER 2 commits land, re-finalize all 9 deals from
   `/tmp/iter4_extractions/*.raw.json` IF those files still exist —
   they are on /tmp and may have been cleared. If cleared, fresh
   extractions are needed.
6. **If** /tmp files exist: one commit with deletion pass + TIER-1
   checks + state re-finalizes.
7. **If** /tmp files are gone: commit deletion pass + TIER-1 first,
   then spawn the 9-way extractor re-run to produce fresh raw JSONs.
8. After iter-6 lands cleanly on all 9 references, write the iter-7
   canary plan (TIER 3).

## /tmp file check

Before assuming, run:
```
ls -la /tmp/iter4_extractions/ 2>/dev/null | head -12
```

If the directory is empty or gone, schedule a 9-way extractor
re-run after TIER 0/1/2 commits land. Extraction takes ~15-20
minutes wall-clock.

---

## Operating notes

1. **This is a deletion pass.** If you find yourself adding >100
   lines of rules, stop and reconsider. The goal is -350 net lines.
2. **Do NOT re-introduce the §D1.a closed verb list.** The auditors
   (1, 3, 5) converged on it being overfit. The loose form + soft
   flag + Austin adjudication is the correct design.
3. **Do NOT touch `scripts/build_reference.py`** (the iter-3b rule
   is still in force — it has Austin's uncommitted edits in main).
   Divergent rank tables are documented as an action item for Austin,
   not fixed in iter-6.
4. **Do NOT touch `reference/alex/*.json`** (same rule).
5. **Do NOT add new schema fields.** If the canary reveals gaps,
   iter-7 can add; iter-6 only deletes.
6. **Do NOT re-introduce iter tags in the prompt.** Iteration history
   belongs in commit messages and plan docs, not in the extractor's
   input.
7. **Commit discipline**: one atomic commit for TIER 0+1+2 is
   acceptable (they're a coherent deletion pass). TIER 3 is its own
   plan / iter-7. State re-finalizes go in the same commit as
   TIER 0+1+2 OR in follow-up per-deal `--allow-empty` commits per
   the iter-3b convention.

---

## Exit criterion for iter-6

- All 9 reference deals re-finalize `passed_clean` under the
  deletion-pass rulebook.
- Prompt duplication eliminated (one canonical source).
- Net line count reduction: ≥ -350 lines across rules/, prompts/,
  pipeline.py.
- §D1.a verb list reverted.
- §G2 hard invariant implemented.
- 4 phantom schema fields dropped.
- All tombstone sections + trailing Open-Questions blocks deleted.
- §Q1-§Q5 relocated from rules/dates.md.

Once these hold, iter-7 is the canary run (10 unseen target deals),
which replaces the 9-deal-clock as the real gate for the 392-deal
turnover.
