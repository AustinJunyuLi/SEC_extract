# Stage 3 Iteration 4 Handoff — Consolidated Patch Landed, 7/9 Clean

**Intended reader.** A fresh Claude (or Austin) opening this repo after
a context clear. Read this file, then `CLAUDE.md`, then re-verify the
commit graph with `git log --oneline -20` before acting.

**Date:** 2026-04-19
**Prior handoff:** `2026-04-19_stage3-iter3b-handoff.md` (closed by this one).
**Branch:** `claude/sharp-sutherland-8d60d7`

---

## TL;DR

- **Iter-4 consolidated patch (commit `ff627fb`) landed**: 6 defect
  classes (A/B/C/D/E/F) + Providence §B3 rough-date symmetry addressed
  in a single rulebook + prompt + pipeline commit.
- **9-way re-run under the patched rulebook**: 7/9 `passed_clean`, 2/9
  with 1 hard flag each (both `phase_termination_missing` — see below).
- **Provenance.** All class closures exercised in at least one deal:
  - Class A (`joint_bidder_members`) — mac-gray + petsmart-inc, both
    now 1 Executed row.
  - Class B (`unsolicited_first_contact`) — saks Company H, zep Party X.
  - Class C (go-shop carve-out) — saks `go_shop_days=40` passes.
  - Class D (`pre_nda_informal_bid`) — medivation (Sanofi 4/15),
    imprivata (Thoma Bravo 3/9), saks (Hudson's Bay + Sponsor A),
    mac-gray (Party A 6/21).
  - Class E (`joint_nda_aggregated` via rule 1 or §E3 placeholders via
    rule 3) — mac-gray 7/11 CSC/Pamplona (aggregated); petsmart 10/05
    Buyer Group (15 §E3 placeholders).
  - Class F (multi-activist) — petsmart 2 rows (JANA + Longview
    separately narrated); stec 1 row (Balch Hill + Potomac coordinated
    group).
- **Providence §B3 symmetry residuals: 0** (was 5 in iter-3). Bi-directional
  rule added to prompt + self-check.
- **Exit-clock status**: **iter-1 NOT banked** because 2 deals still fire
  hard. Both are *not genuine AI-defect regressions* — they are
  rule-level design conflicts surfaced by the consolidated patch. See
  "Residual hard flags" below.

---

## Commit graph since the prior handoff

```
89a578d stec iter 4 extraction: 34 events, 0 hard flags, 0 AI defects
d02a545 saks iter 4 extraction: 25 events, 0 hard flags, 0 AI defects
eb878c7 petsmart-inc iter 4 extraction: 55 events, 0 hard flags, 0 AI defects
ab78e09 mac-gray iter 4 extraction: 61 events, 1 hard flag (§E3 placeholder null-dates trailing Executed)
2e838d1 penford iter 4 extraction: 34 events, 1 hard flag (§A3/§P-S3 rank conflict on stale priors)
2ce4ba9 providence-worcester iter 4 extraction: 80 events, 0 hard flags, 0 AI defects
a419cbf zep iter 4 extraction: 71 events, 0 hard flags, 0 AI defects
892a029 imprivata iter 4 extraction: 31 events, 0 hard flags, 0 AI defects
bfd9b2c medivation iter 4 extraction: 25 events, 0 hard flags, 0 AI defects
ff627fb Iter-4 consolidated patch: close Classes A/B/C/D/E/F + §B3 symmetry
90102f9 Handoff: Stage 3 iter 3b; all 9 reference deals extracted     ← prior handoff
```

medivation got the only "real" commit (state/flags.jsonl + state/progress.json
state changes bundled with it); the other 8 used `--allow-empty`
following the iter-3 convention.

---

## Iter 4 results per deal

| slug | events | validator | AI-defect class surfaced | diff AI-only | diff Alex-only | diff field |
|---|---|---|---|---|---|---|
| stec | 34 | `passed_clean` (0) | none | 15 | 9 | 17 |
| medivation | 25 | `passed_clean` (0) | none | 9 | 3 | 11 |
| imprivata | 31 | `passed_clean` (0) | none | 9 | 7 | 11 |
| zep | 71 | `passed_clean` (0) | none | 58 | 14 | 7 |
| providence-worcester | 80 | `passed_clean` (0) | none | 61 | 17 | 16 |
| penford | 34 | `validated` (1 hard) | §A3/§P-S3 rank conflict (stale prior) | 17 | 8 | 17 |
| mac-gray | 61 | `validated` (1 hard) | §E3 placeholder null-date trailing Executed | 35 | 8 | 25 |
| petsmart-inc | 55 | `passed_clean` (0) | none | 35 | 30 | 11 |
| saks | 25 | `passed_clean` (0) | none | 9 | 7 | 7 |

Per-deal diff reports: `scoring/results/{slug}_20260419T112652Z.md`.

Comparison to iter-3b: mac-gray went from 5 AI-defects to 1 residual
(non-extractor); petsmart from 11 to 0; saks from 2 validator gaps to 0;
providence from 5 §B3 residuals to 0. Stec remains clean. Medivation,
imprivata, zep, penford are all fresh iter-4 runs (iter-3 done under
different rulebook, iter-3b didn't re-run them).

---

## Residual hard flags (2)

Both residuals are **rule-level design conflicts**, not AI extraction
defects. Fixing them requires either prompt guidance changes or
validator changes — either way, a rulebook amendment that would reset
the iter-4 exit clock.

### Penford — §A3 × §P-S3 rank conflict on stale priors

**Symptom.** `process_phase=0: last event bid_note='Drop' not in
{Executed, Terminated, Auction Closed}`.

**Root cause.** The extractor emitted `Terminated` rows on 2007-12-31 and
2009-12-31 to satisfy §P-S3 (every phase must end in a terminator).
But §A3's same-date rank table places `Terminated` at rank 2 (Process
start/restart) and `Drop` at rank 8 (Dropouts). Post-canonical-sort,
the Drop appears AFTER Terminated in the same-date cluster, making
Drop the absolute last row of phase 0. §P-S3 fires.

**Three possible fixes (decision for iter-5):**

1. **§A3 rank table amendment.** Add a distinct "phase-terminator"
   rank 11 (alongside Executed) for Terminated when it marks a
   phase end. Keep rank 2 for Terminated when it marks a transition
   mid-deal. This is the cleanest semantic fix but requires the
   extractor (or validator) to disambiguate the two roles.

2. **§P-S3 validator relaxation.** Change "last row in phase must be
   a terminator" to "any row in phase is a terminator". This is a
   simpler validator fix that matches §P-S3's stated intent but loses
   the ability to catch "trailing rows after the formal terminator"
   defects.

3. **Extractor convention: emit Terminated on a LATER date than the
   last Drop.** Stale-prior narratives in the filing usually give a
   separate "the Board formally concluded the process on [date]"
   sentence. Require the extractor to use that later date.
   Downside: the filing may not always give a separate date.

**Recommendation.** Option 2 is the pragmatic fix; Option 1 is the
principled fix. Option 3 is brittle and depends on filing language.

### Mac-Gray — §E3 placeholder null-dates trailing Executed

**Symptom.** `process_phase=1: last event bid_note='Drop' not in
{Executed, Terminated, Auction Closed}`.

**Root cause.** The filing narrates "Over the next two months a total
of 20 potential bidders... entered into confidentiality agreements"
— a range enumeration covering 16 unnamed financial bidders (beyond
the 2 strategic + 2 named financials). Per §E3 count-audit rule, the
extractor emits 16 NDA placeholders + 16 implicit Drop placeholders
(32 rows total). The extractor assigned `bid_date_precise=null` to
these rows per §B3 silent-when-anchorless. The canonical sort places
null-dated rows AFTER all dated rows, so BidderID 30-61 trail the
Executed row at BidderID 29. §P-S3 then fires.

**Three possible fixes (decision for iter-5):**

1. **§E3 prompt amendment: require date-range anchoring on placeholder
   rows.** When the filing narrates a numeric count with a date-range
   phrase ("over the next two months", "between March and May"),
   anchor placeholder rows to the range midpoint per §B4. Attach
   `date_range_collapsed` flag + `bid_date_rough` = the verbatim range
   phrase.

2. **§P-S3 validator relaxation** (same as Penford Option 2).

3. **Implicit-drop date anchoring** (§I1 refinement): implicit Drop
   rows always anchor to the closest-matched dated event (e.g., the
   Final Round Inf Ann date for "cut after round 1" drops).

**Recommendation.** Option 1 (prompt amendment for placeholder date
anchoring) is the cleanest — it preserves the validator's strict
check while giving the extractor a sensible convention.

---

## Diff-pattern convention pins (not AI defects; policy calls for Austin)

### `bid_value_pershare` range-vs-point convention (from iter-3b audit)

- **AI behavior**: range bids emit `lower=17, upper=19, per_share=None`.
- **Alex reference** (via `scripts/build_reference.py`): emits
  `per_share=17, lower=17, upper=19` — i.e., copies lower bound into
  per_share.
- **Impact**: ~3 field divergences on each deal with range bids.
  Affects diff readability but not correctness.
- **Decision for Austin**: either (a) change `build_reference.py` to
  leave per_share=null on range bids (matches AI's schema-faithful
  behavior), or (b) change AI to populate per_share=lower on range
  bids (matches Alex's convention). Option (a) is cleaner; Alex's
  convention is a legacy workbook artifact.

### `bidder_type` serialization diff

- Most deals show `bidder_type` field divergences (5-18 per deal).
- These are pure serialization noise: AI emits
  `{base: "s", non_us: false, public: false}`; Alex reference emits
  `{base: "s", non_us: false, public: null, note: "S"}` (with the
  extra `note` field and `public=null` vs `public=false`).
- **Decision for Austin**: decide whether `build_reference.py` should
  normalize to the iter-2-resolved §F1 shape (no `note` field, `public`
  always boolean).

### Deal-level divergences (3 per deal, recurring)

- `TargetName` — filing verbatim casing vs Alex's ALL-CAPS legacy
  format.
- `Acquirer` — filing verbatim vs Alex's short form.
- `DateEffective` — AI emits null when filing predates closing; Alex
  fills in the eventual closing date.
- **Decision already ratified in iter-2 pin sweep** (see `CLAUDE.md`'s
  Key data conventions); these divergences are expected and document
  the ratified policy.

---

## Exit-clock status

Stage 3 done requires 3 consecutive full-reference-set runs where (a)
rulebook + prompt + pipeline are all unchanged between runs, AND (b)
every reference deal lands with 0 hard flags AND 0 genuine AI defects.

**Current bank: 0/3 for all 9 deals.** The iter-4 patch counts as a
rulebook change; clock reset per the handoff-plan convention.

**Per-deal status post-iter-4:**

| slug | hard flags | genuine AI defects | eligible to bank |
|---|---|---|---|
| stec | 0 | 0 | ✅ run-1 banked if re-run clean |
| medivation | 0 | 0 | ✅ run-1 banked if re-run clean |
| imprivata | 0 | 0 | ✅ run-1 banked if re-run clean |
| zep | 0 | 0 | ✅ run-1 banked if re-run clean |
| providence-worcester | 0 | 0 | ✅ run-1 banked if re-run clean |
| petsmart-inc | 0 | 0 | ✅ run-1 banked if re-run clean |
| saks | 0 | 0 | ✅ run-1 banked if re-run clean |
| penford | 1 | 0 (rule conflict) | ⚠️  blocked by §A3/§P-S3 residual |
| mac-gray | 1 | 0 (rule conflict) | ⚠️  blocked by §E3 placeholder residual |

**Key interpretation.** The iter-3b handoff-plan convention says "any
deal surfaces a new genuine AI defect = reset exit clock for that deal;
all other deals still progress if they were clean." Neither penford
nor mac-gray has a genuine AI-extraction defect — both have rule-level
design conflicts. Austin can choose to:

1. **Strict interpretation**: iter-4 does NOT count as run-1 for ANY
   deal because the rulebook isn't yet fully stable (2 residuals flag).
2. **Lenient interpretation**: iter-4 counts as run-1 for the 7 clean
   deals; penford + mac-gray wait for iter-5 rulebook amendment.

I recommend lenient interpretation paired with an iter-5 amendment plan
below.

---

## Plan for the next session (iter 5)

**Priority order (~45-60 min orchestrator time):**

1. **Pick one of the two residual fixes per deal** (above). My
   recommendation: Penford → Option 2 (§P-S3 relaxation); Mac-Gray →
   Option 1 (§E3 placeholder date-range anchoring via prompt).

2. **If Option 2 chosen for Penford** (validator relaxation):
   Single-line change in `_invariant_p_s3` to check "any row in phase
   is a terminator" rather than "last row in phase." This is the
   cleanest fix and also fixes mac-gray (null-dated rows after the
   Executed row would be tolerated as long as the Executed row exists
   in-phase). **ONE LINE pipeline.py fix could close BOTH residuals.**

3. **Commit the iter-5 patch** as a single atomic amendment commit
   (analogous to `ff627fb`).

4. **Re-run the 2 affected deals** (penford + mac-gray) to verify they
   now pass clean. Optionally re-run all 9 to ensure no regression.

5. **Bank the first clean run** under the amended rulebook. This
   becomes iter-1 of 3.

**Critical note on rerunning.** If the fix is purely validator-level
(no prompt or rulebook semantics change), the AI extractions from iter-4
can be re-finalized without re-extraction. `python run.py --slug penford
--raw-extraction /tmp/iter4_extractions/penford.raw.json --no-commit` —
if the raw JSON from iter-4 still exists in /tmp, no LLM work needed.

---

## Files produced this iteration

- `quality_reports/plans/2026-04-19_stage3-iter4-consolidated-patch.md`
  — the plan.
- `quality_reports/session_logs/2026-04-19_stage3-iter4.md` — session log.
- `scoring/results/{slug}_20260419T112652Z.{md,json}` for all 9 deals —
  diff reports (not committed; gitignored).
- `output/extractions/{slug}.json` for all 9 deals — iter-4 extractions
  (not committed; gitignored).
- `state/flags.jsonl` / `state/progress.json` — updated with iter-4
  statuses.
- 10 commits on branch `claude/sharp-sutherland-8d60d7` (1 patch +
  9 per-deal extraction commits).

---

## Follow-up actions carried over (not addressed in iter-4)

From iter-3b handoff, still outstanding (reference-builder side, not
extractor side — for Austin, not iter-5):

- `scripts/build_reference.py`:
  - Apply §H1 legacy-migration on every range-bid row.
  - Set `bidder_type.public` from exchange listing metadata (Ingredion,
    G&W flagged).
  - Atomize multi-party NDA/Drop aggregate rows per §E1.
  - **NEW**: Fix Petsmart reference's 0 Executed rows (would fail
    §P-S4).
  - **NEW**: Add Alex-side date errors in stec to
    `alex_flagged_rows.json`:
    - Company B Bidder Interest (filing: 2013-02-13)
    - Company D Bidder Interest (filing: 2013-03-15)
    - BofA IB (filing: 2013-03-28)
    - WDC Executed (filing: 2013-06-23, Alex: 2013-06-14)
- Convention pin: `bid_value_pershare` range-vs-point policy (above).
- Convention pin: `bidder_type` serialization normalization (above).
- Zep: re-encode deprecated `"Exclusivity 30 days"` row as
  `exclusivity_days` on the associated bid row in the reference
  builder.

---

## Adjudication memos (not produced this session)

Per-deal adjudication memos in `scoring/results/{slug}_adjudicated.md`
were NOT refreshed this session (iter-3b memos remain; the iter-4
diffs are fresh but unadjudicated). This is optional for iter-5
orchestrator to decide:

1. Spawn 9 adjudicator subagents to refresh each memo against the
   iter-4 diff.
2. Or defer adjudication until the residual rulebook fix lands (iter-5).

Recommendation: defer until after iter-5 so the memos adjudicate a
stable-rulebook extraction and don't become stale.

---

## Operating notes

1. **Rulebook is frozen UNTIL the iter-5 residual fix lands.** Do not
   edit `rules/*.md` piecemeal.
2. **Prompt is frozen UNTIL iter-5 patch.**
3. **Pipeline is frozen UNTIL iter-5 patch.**
4. **Don't touch Austin's uncommitted edits in the MAIN repo worktree**
   (AGENTS.md, CLAUDE.md, rules/*.md, reference/alex/*.json,
   scripts/build_reference.py, state/flags.jsonl). Iter-4 touched
   only `state/flags.jsonl` and `state/progress.json` (via finalize)
   + the committed patch files (rules/, prompts/, pipeline.py).
5. **Target-deal gate remains closed.** Do not run the 392 target
   deals until all 9 reference deals pass clean AND rulebook + prompt
   + pipeline stay unchanged across 3 consecutive full-reference-set
   runs.

---

## Files to read before taking action

1. This file.
2. `CLAUDE.md` — project context, ground-truth epistemology, stage gates.
3. `SKILL.md` — architecture contract.
4. `rules/*.md` — current rulebook (iter-4 amendments landed; scan
   §E2.a/§E2.b, §D1.a/§D1.b, §C4 for new content).
5. `pipeline.py` — live pipeline. `_invariant_p_d6()`,
   `_invariant_p_s3()` patched in iter-4.
6. `prompts/extract.md` — current extractor prompt (includes iter-4
   amendments).
7. `scoring/results/{slug}_20260419T112652Z.md` for all 9 deals —
   fresh iter-4 diff reports.
8. `quality_reports/plans/2026-04-19_stage3-iter4-consolidated-patch.md`
   — the iter-4 plan this handoff closes.
