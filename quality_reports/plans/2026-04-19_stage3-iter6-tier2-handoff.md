# Stage 3 Iter-6 TIER 2 Handoff — Rulebook/Prompt Deletion Pass

**Status:** DRAFT → handoff for fresh Claude post-`/compact`
**Branch:** `claude/sharp-sutherland-8d60d7`
**Worktree:** `/Users/austinli/bids_try/.claude/worktrees/sharp-sutherland-8d60d7`
**Date:** 2026-04-19

---

## TL;DR

TIER 0 and TIER 1 of the iter-6 deletion pass are complete (9 commits,
`f4d36d9` through `32c35f8`). Net: 21 files changed, +345/−418 lines.
Each tier passed clean-slate adversarial `/review` + `/simplify` passes.
TIER 2 is the biggest remaining tier — target ~−350 net lines across
rule markdown, prompts, and dead pipeline branches. No new logic.

---

## Commit graph (TIER 0 + TIER 1)

```
32c35f8 Iter-6 TIER 1 simplify: dedup flag-codes helper, collapse prose
2cb4c77 Iter-6 TIER 1 post-review fixes
be78588 Iter-6 TIER 1e: generalize parse_accession + route through canonical URL
c9d5eac Iter-6 TIER 1d: drop phantom schema field `multiplier`
46e0cec Iter-6 TIER 1c: registry integrity in _apply_unnamed_nda_promotions
9f08142 Iter-6 TIER 1b: implement _invariant_p_g2 (bid_type evidence check)
009ea83 Iter-6 TIER 1a: delete _invariant_p_d2 legacy-fixture tolerance
16f65e8 Iter-6 TIER 0 simplify: compress §D1.a text, fix stale JSON example
cff34de Iter-6 TIER 0: revert §D1.a closed verb list overfit
f4d36d9 Handoff: Stage 3 iter 6 deletion pass — audit-driven consolidation
```

Resume checkpoint: `git log --oneline f4d36d9..HEAD` should show these
9 commits. If missing any, something is wrong — investigate before
proceeding.

---

## What changed in TIER 0 + 1 (for situational awareness)

### TIER 0: §D1.a revert + simplify
- `rules/events.md` §D1.a attachment conditions collapsed 4→3 and the
  closed 10-verb list deleted. New semantic rule: "filing narrates
  target declining OR bidder withdrawing before any NDA" + ≤120-char
  verbatim audit quote in `reason`.
- `prompts/extract.md` step 5 restructured to bullet list with
  cross-references to §D1, §D1.a, §D1.b, §K2, §C4.
- `pipeline.py build_extractor_prompt` §D1.a block compressed.

### TIER 1: safety gates (5 sub-commits)
- **1a**: `_invariant_p_d2` strict XOR; deleted legacy-fixture
  `rough.startswith(precise)` carve-out.
- **1b**: new `_invariant_p_g2` enforces §G2 evidence requirement
  (trigger phrase in quote OR true range bid OR
  `bid_type_inference_note`). `FORMAL_TRIGGERS`, `INFORMAL_TRIGGERS`,
  `ALL_G1_TRIGGERS` module constants. Wired into validator.
- **1c**: `_apply_unnamed_nda_promotions` registry integrity
  (promote_to_bidder_name must be in registry; can't overwrite
  already-named rows). `finalize()` emits `nda_promotion_failed`
  hard flags POST-canonicalize so row indices stay stable.
- **1d**: dropped `multiplier` from schema + builders + diff compare
  list + reference JSONs (regenerated all 9). Kept `stock_per_share`
  and `aggregate_basis` (semantic §H2/§H4 fields, dormant).
- **1e**: `parse_accession` handles all 3 EDGAR URL forms (compact
  index, nested index, direct document) + fragment/query stripping.
  New `canonical_index_url(cik, accession)` helper normalizes.
  `resolve_substantive_document` now returns `(doc, index_url)`.

### TIER 1 post-review + simplify (2 more commits)
- Fixed mutation-safety bug (hint pop timing), flag-emission index
  drift, range-bid degenerate `lower == upper`,
  `bid_type_inference_note` length cap.
- Extracted `_row_flag_codes(ev)` helper (removes duplication).
- Trimmed docstrings + flag reasons.
- Replaced "Fix 1" / "Fix 2C" historical comments with behavioural ones.

---

## Exit clock

**RESET to 0/3.** Any rulebook change resets the counter, and both
TIER 0 + TIER 1 include rulebook changes.

**Current reference-deal state:** last run was iter-5, all 9
passed_clean. **Since then, new invariants have been added but the
deals have NOT been re-run.** So `state/progress.json` still says
`passed_clean` but that's stale — next `finalize()` pass will surface
~33 new `bid_type_unsupported` hard flags (confirmed by dry-run of
`_invariant_p_g2` against existing extractions).

---

## TIER 2 scope (this handoff's actual work)

The original iter-6 handoff at
`quality_reports/plans/2026-04-19_stage3-iter6-deletion-pass-handoff.md`
defines TIER 2. Priority-ordered summary below.

### 2.1 Rule file deletions (~200 lines)

**Delete trailing "Open questions" blocks** in each rule file. These
were Stage-1 scratchpads; everything is resolved and the blocks only
clutter the extractor's prompt context. Targets:
- `rules/events.md` — check for trailing 🟥/🟩/"Open questions" section
- `rules/bidders.md` — same
- `rules/bids.md` — same (around lines 670-700 likely)
- `rules/dates.md` — same
- `rules/schema.md` — same
- `rules/invariants.md` — "Future extensions" stub (§P-G2 entry
  already removed; check if any other future-feature placeholders
  remain)

**Delete tombstone sections**: §F3, §I2, §M2 per the original
handoff. These were rejected alternatives captured for record;
they're noise at this point. Grep:
```
grep -n "### §F3\|### §I2\|### §M2" rules/
```

**Delete §K3** (Providence 6058 relabel — one-off workbook fix,
belongs in `scripts/build_reference.py` docstring, not in the
extractor's rulebook).

**Delete §D1.b** if redundant with §E1 (check cross-references
first). §E1 is about bidder atomization; §D1.b is about multi-
activist rows. Re-read both carefully before deleting — they may
be complementary, not redundant.

**Move §Q1–§Q5** from `rules/dates.md` to a new docstring block
at the top of `scripts/build_reference.py`. These document
xlsx→JSON overrides (Saks delete, Zep expand, Mac-Gray renumber,
Medivation renumber, Several-parties atomization). The extractor
doesn't need them; only the reference-builder does.

### 2.2 Rule file simplifications (~60 lines)

**Simplify §E2.b** to ≤20 lines. Currently a 3-rule decision tree
(group-narrated NDA, per-constituent NDA, count-only); can be one
principle + examples.

**Merge §C4 and §D1.a** into single section? Both deal with
NDA-vs-Bid timing edge cases (§C4: pre-NDA bid; §D1.a: no NDA at
all). Decide if merging improves clarity or loses distinctions.
If merging: place under §D1 as §D1.x family.

### 2.3 Prompt deduplication (~220 lines)

**Biggest single reduction.** `prompts/extract.md` and
`pipeline.py build_extractor_prompt` contain overlapping rule
prose — roughly 220 lines of duplicated/paraphrased content. Per
the TIER 1 review (Agent 1 on code reuse):

- `api_extractor.py:132-181` is the PRODUCTION path. It reads
  `prompts/extract.md` + all `rules/*.md` VERBATIM and embeds them.
  No paraphrasing.
- `pipeline.py build_extractor_prompt` is the Claude-Code subagent
  variant. It ALSO tells the subagent to read rule files, BUT also
  inlines ~220 lines of "Non-negotiables:" prose that paraphrase
  the rules.

**Recommendation (from Agent 1):** delete all §D1.a, §C4, §E2.a,
§E2.b, §D1.b, §B3 paraphrase blocks in `build_extractor_prompt`
(pipeline.py ~lines 295-370). Trust the subagent directive
("Read these files in full") to pull details from rule files.
Keep compressed summary in `extract.md` only — it flows into the
prod prompt via `api_extractor.py`.

**Caveat:** if the subagent path is actively used (check `run.py`
`--dry-prompt` or similar), this could regress its behaviour.
Verify `run.py` callers first. If unused, easy delete. If used,
make the paraphrases literal `_read(RULES_DIR / ...)` calls so
there's a single source.

### 2.4 Prompt cleanups (~30 lines)

**Reduce self-check from 15 to 9 bullets.** `prompts/extract.md`
has a checklist at the end; some bullets are redundant with
§R1 structural invariants or §R2 evidence check that the validator
already enforces.

**Strip iter tags from prompts.** Phrases like "iter-4 amendments",
"iter-5 tightened", "Class B fix" are narrative history. Keep only
current rules; git provides the history.

**Strip ref-deal names from prompts.** Filenames like
"saks Company H", "zep Party X", "Petsmart JANA + Longview" in the
prompt teach the extractor to pattern-match on the 9 references
rather than generalize. Replace with abstract descriptions.

### 2.5 Constitutional deletions

**Delete `_unnamed_nda_promotions` from output JSON?** TIER 1 kept
this as internal audit trail on deal object. Audit Agent 2 flagged
as harmless (underscore-prefixed) but consider whether downstream
consumers (scoring/diff.py, research scripts) benefit from it being
in the output at all. If not, strip in `finalize()` before writing.
Defer if uncertain.

---

## Operating guardrails

1. **No new logic in TIER 2.** Every change should be a deletion, a
   move, or a refactor that preserves semantics. Verify by running
   the invariant dry-run after each commit (see below).

2. **Atomic commits.** Target ~7 sub-commits for TIER 2:
   - 2a: Delete "Open questions" blocks (all rule files)
   - 2b: Delete tombstones §F3/§I2/§M2
   - 2c: Delete §K3, §D1.b (if redundant)
   - 2d: Move §Q1–§Q5 to build_reference.py
   - 2e: Simplify §E2.b (+ maybe merge §C4+§D1.a)
   - 2f: Deduplicate prompts (biggest reduction; optional based on
     run.py analysis)
   - 2g: Prompt cleanup (self-check, iter tags, ref-deal names)

3. **After each atomic commit, smoke-test:**
   ```bash
   python3 -c "import ast; ast.parse(open('pipeline.py').read())"
   # Optionally: run _invariant_p_g2 + _invariant_p_d2 on all 9
   # extractions to confirm zero regressions.
   ```

4. **Max 5 review-fix rounds per tier** (per orchestrator protocol).
   If you can't get it clean in 5, write a blocker note and stop.

5. **Review + simplify after TIER 2 lands.** Same pattern as TIER 1:
   `/review` with 1 adversarial agent, then `/simplify` with 3
   parallel agents (reuse/quality/efficiency). Apply findings.

6. **Do NOT start target-deal extraction.** Gate remains: 3
   consecutive unchanged-rulebook full reference runs. TIER 2 is
   still rulebook-changing, so the clock stays at 0/3.

---

## Re-run checkpoint (post-TIER 2)

After TIER 2 + TIER 3 land, re-run all 9 reference deals:

```bash
# For each slug in the rollout order:
# medivation → imprivata → zep → providence-worcester → penford →
# mac-gray → petsmart-inc → stec → saks

python3 api_extractor.py --slugs medivation  # (or whatever the live
                                                # extractor call is;
                                                # verify before running)
```

Expected:
- `bid_type_unsupported` hard flags will surface on ~33 rows across
  8 of 9 deals. Austin adjudicates: either attach
  `bid_type_inference_note` to the Bid row (extractor follow-up) or
  expand §G1 trigger list (rulebook decision).
- `nda_promotion_failed` should remain 0 on all 9 (registry is
  well-formed; no failed promotions observed in TIER 1 dry-run).
- `rough_date_mismatch_inference` should remain 0 (strict XOR
  confirmed clean on current outputs).
- URL-parser changes don't affect reference fetches (all 9 already
  have manifests and raw filings).

If all 9 pass clean under TIER 2 rulebook and no rule changes are
required, that's the FIRST of 3 unchanged-rulebook runs toward the
exit gate.

---

## First actions for fresh Claude post-compact

1. `pwd && git log --oneline -10` — confirm state matches this handoff.
2. Read this file (`2026-04-19_stage3-iter6-tier2-handoff.md`).
3. Read `CLAUDE.md` for project context.
4. Read the original iter-6 handoff
   (`quality_reports/plans/2026-04-19_stage3-iter6-deletion-pass-handoff.md`)
   for TIER 2/3 specifics the TL;DR may have glossed.
5. Start with **2a** — delete "Open questions" blocks. Grep first:
   ```bash
   grep -n "Open questions\|🟥" rules/
   ```
   Confirm each section is truly resolved before deleting. Some
   "Open questions" blocks may have been merged into "Future
   extensions" and already addressed.
6. One atomic commit per sub-tier (2a, 2b, ...). Verify pipeline
   parses after each.
7. After all sub-tiers: dispatch `/review` + `/simplify` pass. Apply
   findings. Commit fixes.
8. Update CLAUDE.md's "Current status" section to reflect the new
   state (exit clock reset, ~33 expected §P-G2 violations pending
   adjudication on re-run).
9. Report back to Austin with summary + next-step options (TIER 3 vs
   re-run first).

---

## Known surprises / gotchas

- **`stock_per_share`, `aggregate_basis`, `highly_confident_letter` are NOT phantom.**
  Despite what the original iter-6 handoff said. Verified populations
  in TIER 1d. Only `multiplier` was truly phantom (dropped).

- **`seeds.csv` has NO `form_type` column.** The iter-6 handoff's
  "backfill form_type" task was a misread of repo structure.
  form_type is derived at fetch time from EDGAR index table and
  stored in `data/filings/{slug}/manifest.json`. TIER 1e fixed the
  actual latent risk (5 seeds with unparseable URLs).

- **`_invariant_p_d6` now uses `_row_flag_codes(ev)` helper** (TIER
  1 simplify). Don't re-inline it if you see the 3-line comprehension
  pattern elsewhere — use the helper.

- **`finalize()` flag emission happens POST-canonicalize now.** If
  you add new promotion-like pre-validation transforms, follow the
  same pattern: mutate before sort, emit flags after sort via
  residual-artifact identity (not by stale index).

- **§G2 is existence-only.** `_invariant_p_g2` doesn't check whether
  the trigger's formal/informal classification MATCHES the declared
  `bid_type`. That's §G1's job. Don't "fix" this without consulting
  rulebook — it's deliberate per iter-6 review Agent 1's finding.

- **Reference JSONs were regenerated in TIER 1d** via
  `scripts/build_reference.py --all`. If you run `--slug <one>` now,
  that one file will stay consistent with the other 8 (all drop
  `multiplier`). If you modify `build_reference.py`, regenerate all
  9 again and commit atomically.

---

## TIER 3 preview (for when TIER 2 is done)

Quick summary so you can plan:
- Dead-code sweep in `pipeline.py`:
  - `ValidatorResult.soft_flags()` — check if actually called
  - `PipelineResult.validator` attribute — check consumers
  - Post-canonicalize dead branches in `_invariant_p_d3` rules 5/6
- Unused imports
- Unreferenced constants

This is a smaller tier than TIER 2. Maybe −50 lines.

---

## Success criteria for TIER 2

- [ ] ~−350 net lines across rules/, prompts/, pipeline.py
- [ ] No new logic; pure deletion/move/refactor
- [ ] `pipeline.py` parses after every sub-commit
- [ ] `_invariant_p_g2` still fires 33 on current extractions (no regression)
- [ ] `_invariant_p_d2` still fires 0 on current extractions
- [ ] All rule cross-references resolve (no broken §X references)
- [ ] Review + simplify pass produces only cosmetic findings
- [ ] Ready for re-run on 9 references (which is the actual first of 3
  toward exit clock)
