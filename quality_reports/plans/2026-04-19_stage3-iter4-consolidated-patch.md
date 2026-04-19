# Stage 3 Iteration 4 — Consolidated Patch Plan

**Status:** APPROVED 2026-04-19
**Predecessor:** `2026-04-19_stage3-iter3b-handoff.md`
**Worktree:** `claude/sharp-sutherland-8d60d7` (branch), clean at commit `90102f9`
**Goal:** Close all 6 defect classes surfaced in iter 3b + the outstanding
Providence §B3 rough-date symmetry rule in **one** atomic rulebook +
prompt + pipeline patch, then re-run all 9 reference deals under the
patched pipeline as iteration 1 of 3 toward the Stage 3 exit clock.

---

## Decisions ratified at kickoff (2026-04-19)

1. **Class D (pre-NDA concrete price indication).** Option 1 — treat as
   `bid_note="Bid"` with `bid_type="informal"`, attach a
   `pre_nda_informal_bid` flag, and exempt these rows from `§P-D6`
   (NDA-before-Bid existence check).
2. **Diff.py audit first.** Audit the `bid_value_pershare` null-vs-value
   bug before writing the patch so iter-4 diffs are trustworthy.
3. **Batch all 9 deals.** Do not ship stec independently — batch behind
   the consolidated patch as iter-1 of 3.

---

## Phase 0 — Diff.py audit (30 min, before any patch)

**Target.** `scoring/diff.py`. Adjudicator on mac-gray flagged 7 spurious
`bid_value_pershare` null-vs-value divergences where the AI JSON in fact
populates the field.

**Method.**

1. Open `scoring/results/mac-gray_20260419T102428Z.md` and identify the
   7 false divergences (row refs).
2. Cross-reference against `output/extractions/mac-gray.json` to confirm
   the field is populated AI-side.
3. Read `scoring/diff.py` field-pairing logic — focus on how the AI row
   is matched to the Alex row, and how `bid_value_pershare` is extracted
   from each side's shape.
4. If bug confirmed: patch `diff.py` field extraction; add a unit test or
   at minimum re-run mac-gray diff to confirm the 7 spurious rows drop.
5. If no bug: document that the adjudicator's suspicion was misplaced
   and close the action item.

**Deliverable.** Either (a) `scoring/diff.py` patched + verification
diff re-run, or (b) a note in the iter-4 patch commit that the audit
found no bug. Standalone commit if a fix is needed.

---

## Phase 1 — Consolidated iter-4 patch (one commit)

### Rulebook patches (`rules/*.md`)

**1. `rules/bidders.md` §E2 — joint-Executed exception (Class A).**

Add a carve-out: Executed rows are always exactly 1 per deal, named
after the merger-agreement counterparty (e.g., "Buyer Group",
"CSC/Pamplona"), with a `joint_bidder_members` field listing
constituent bidder_NN IDs. §E2's per-constituent atomization rule
applies to NDAs, Bids, and Drops, but NOT to the Executed row.

**2. `rules/bidders.md` §I1 — joint-NDA aggregation (Class E).**

Clarify that when the filing narrates a consortium / joint-bidder NDA
as a single group event without per-constituent detail, emit ONE NDA
row with `bidder_alias = consortium_label` and a
`joint_bidder_members` field. Emit per-constituent NDA rows ONLY when
the filing separately narrates each constituent's NDA execution.

**3. `rules/events.md` §C1 / §D1 — multi-activist atomization (Class F).**

One-line addition: "If multiple activists are narrated separately,
emit one Activist Sale row per activist. Collapse to a single row only
when the filing treats them as a coordinated group."

**4. `rules/bids.md` §C3 — pre-NDA informal Bid (Class D).**

Add subsection: concrete price indications delivered BEFORE the bidder
signs an NDA emit a `bid_note="Bid"` row with `bid_type="informal"`
and a flag `pre_nda_informal_bid` (severity: info). §P-D6 is exempt
for these rows. This supersedes the ad-hoc saks-extractor convention
of using `Bidder Sale` for this pattern.

**5. `rules/dates.md` §B3 — Providence rough-date symmetry (from prior handoff).**

Re-state the symmetry rule for "mid-month" → 15th, "late-month" → last
day, "early-month" → 1st, applied consistently to both the day-side
and cross-month-boundary cases. Exact language to be fixed in the
commit — check Providence iter-3 handoff for the specific formulation.

### Prompt patches (`prompts/extract.md` + `pipeline.build_extractor_prompt()`)

**Additions (kept terse — prompt is already 130 lines):**

1. Joint-bidder NDA aggregation (§I1).
2. Joint-bidder Executed-row exception (§E2).
3. §D1 unsolicited-first-contact flag: when emitting a §D1 Bid row with
   no prior NDA (bidder declined / never executed NDA), attach
   `{"code": "unsolicited_first_contact", "severity": "info", ...}` to
   exempt the row from §P-D6.
4. §B3 Providence rough-date symmetry rule.
5. Multi-activist atomization convention.
6. Pre-NDA informal Bid convention + `pre_nda_informal_bid` flag.

### Pipeline patches (`pipeline.py`)

**1. `_invariant_p_d6()`.** Add exemptions for rows carrying any of:
- `unsolicited_first_contact` flag (Class B)
- `pre_nda_informal_bid` flag (Class D)

**2. `_invariant_phase_termination()`.** Add go-shop carve-out for
phase 1 when `deal.go_shop_days > 0`: if any phase-1 event is
`Executed` / `Terminated` / `Auction Closed`, treat the phase as
terminated regardless of whether it's the LAST row (Class C).

**3. `_invariant_multiple_executed()`.** Stays hard. Class A fix is in
the prompt, not the validator.

**Verification commands before commit:**
```
python -c "import pipeline; print('pipeline imports OK')"
python -c "import ast; ast.parse(open('pipeline.py').read()); print('pipeline.py parses OK')"
```

---

## Phase 2 — Re-run all 9 reference deals (iter-1 of 3)

**Parallelization.** Spawn 9 extractor subagents in one message. Each
runs:
1. Extract against the patched prompt
2. `run.py --finalize` (Python validator)
3. `scoring/diff.py` vs `reference/alex/{slug}.json`
4. Adjudicator subagent on the diff output

**Commit discipline.** Each deal commits atomically like iter 3b:
- `{slug} iter 4 extraction: N events, H hard flags, {defect-count} AI defects`
- `--allow-empty` if the patch's finalize side-effects are batched in
  the first commit

**Deliverable.** 9 fresh extraction commits + 9 fresh adjudicator memos
in `scoring/results/{slug}_adjudicated.md`.

---

## Phase 3 — Iter-4 handoff

Write `quality_reports/plans/2026-04-19_stage3-iter4-handoff.md` with:
- Per-deal results table (events / hard flags / AI defects / new classes)
- Exit-clock status (banked runs per deal: 0/3 pre-patch → 1/3 if clean
  across all 9; otherwise continue to iter 5)
- Any residual defect classes surfaced by the re-run
- Plan for iter 5 (either re-run under unchanged rulebook if clean, or
  next consolidated patch if defects remain)

---

## Exit-clock logic

- 9 deals all clean under the same unchanged rulebook/prompt/pipeline =
  run 1 of 3 banked for all 9
- Any deal surfaces a new genuine AI defect = reset exit clock for
  that deal; all other deals still progress if they were clean
- Only unchanged-rulebook runs count. If Class G / H / ... emerges in
  iter 4 and requires a rulebook patch, exit clock resets to 0/3 for
  all affected deals

---

## Files touched (expected)

- `rules/bidders.md` §E2, §I1
- `rules/events.md` §C1, §D1
- `rules/bids.md` §C3 (Class D)
- `rules/dates.md` §B3 (Providence symmetry)
- `prompts/extract.md`
- `pipeline.py` (`_invariant_p_d6`, `_invariant_phase_termination`,
  `build_extractor_prompt` if it embeds prompt strings)
- `scoring/diff.py` (Phase 0, only if bug confirmed)

---

## Non-goals for this iter

- Do NOT reopen convention pins classified as both-defensible in the
  §B5/§K2/§D1/§F1/§R1/§N2/§Scope-3/§E3 list.
- Do NOT touch Austin's uncommitted edits in the MAIN repo worktree
  (AGENTS.md, CLAUDE.md, rules/*.md, reference/alex/*.json,
  scripts/build_reference.py, state/flags.jsonl). This patch happens
  in the `claude/sharp-sutherland-8d60d7` worktree only.
- Do NOT run the 392 target deals. Gate remains closed.
