# Six-Policy Update Handoff — 2026-04-27

**For:** whoever runs C7 (per-deal re-extraction on the 9 reference deals)
**Spec:** `quality_reports/specs/2026-04-27_six-policy-update.md`
**Plan:** `quality_reports/plans/2026-04-27_six-policy-update.md`
**Branch landed on `main` at:** the C6 commit that adds this handoff doc

## What changed

Six commits (C1–C6) landed updates from Alex's 2026-04-27 directive:

1. **C1 — `bidder_type` flattened to scalar.** Geography and listing status are no longer recorded.
2. **C2 — `Acquirer_legal` deleted.** Only the operating acquirer is recorded. The 4 sponsor-backed reference deals (petsmart-inc, mac-gray, zep, saks) had their xlsx `Acquirer` column rewritten to the operational name; the legal shell is gone.
3. **C3 — Universal atomization.** The Executed-row joint-bidder collapse is deleted. Petsmart now has 5 Executed rows (BC Partners + La Caisse + GIC + StepStone + Longview); mac-gray has 2 (CSC + Pamplona). Single-sponsor deals unchanged.
4. **C4 — Range bids unconditionally informal.** Whenever `bid_value_lower < bid_value_upper` (both numeric), `bid_type = "informal"`. New hard validator `bid_range_must_be_informal` fires on contradictions. Soft flag `range_with_formal_trigger_override` flags edge cases.
5. **C5 — §L2 wording tighten.** "6 months" -> "180 calendar days." Validator constant unchanged at 180.
6. **C6 — Reference data regeneration + stale-file deletion + this handoff doc.**

## What was deleted

- `state/flags.jsonl` (clean slate; pipeline recreates on first run)
- All 9 `output/extractions/*.json` (clean slate; C7 regenerates per deal)
- `quality_reports/decisions/2026-04-26_six-policy-decisions.md` (decisions #2, #3, #6 reversed by this batch — full delete, no annotation, per spec §0)

## What C7 needs to do (per deal)

For each of the 9 reference deals (medivation -> imprivata -> zep -> providence-worcester -> penford -> mac-gray -> petsmart-inc -> stec -> saks):

1. Spawn a fresh Claude session.
2. Extractor reads the updated `prompts/extract.md` and runs against the SEC filing.
3. Pipeline validator runs the new invariants. Watch for new hard fires:
   - `bid_range_must_be_informal` — should not fire after C4 unless the AI emits a range with `bid_type="formal"`.
   - No other new hard codes were added.
4. `scoring/diff.py` produces an Austin-readable diff against the freshly-regenerated `reference/alex/<deal>.json`.
5. Austin manually adjudicates each disagreement against the SEC filing per the four-verdict framework (CLAUDE.md):
   - AI correct, Alex wrong -> record the AI correction; do not change rules.
   - AI wrong, Alex correct -> update the rules / prompt.
   - Both correct, different interpretations -> log a judgment call in the rulebook.
   - Both wrong -> fix the rulebook against the filing.
6. On clean: mark `state/progress.json` `verified` for the deal.

## Exit gate (unchanged from CLAUDE.md)

The 392 target deals remain blocked until:
- All 9 reference deals are manually verified by Austin.
- The rulebook remains unchanged across 3 consecutive full-reference-set runs.

## What this batch did NOT change

- §I1 DropSilent atomization (already conformant with universal atomization).
- §P-L2 validator constant (already 180 days; only the §L2 wording moved).
- BidderID assignment (still strict 1..N event sequence).
- `source_quote` / `source_page` requirement (still mandatory on every row).
- Auction classifier (`§Scope-1`).
- Skip rules (§M1, §M3, §M5).

## Where to look first if something looks wrong

- **Wrong number of Executed rows:** check `Q7_EXECUTED_MEMBERS` in `scripts/build_reference.py`.
- **Wrong Acquirer name:** check `Q6_ACQUIRER_REWRITE` in `scripts/build_reference.py`.
- **`bidder_type` is dict instead of scalar:** check `build_bidder_type` in `scripts/build_reference.py`.
- **Validator firing `bid_range_must_be_informal` on AI output:** the extractor needs the prompt's Step 8 update; verify `prompts/extract.md` line 60.
