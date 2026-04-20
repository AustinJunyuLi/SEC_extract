# 2026-04-20 §P-G2 Recalibration — Results

## Scope

Collapse §P-G2 from a 3-satisfier invariant (trigger OR range OR note≤200) to a 2-satisfier invariant (range OR note≤300). Eliminate the overfit-risk phrase vocabulary that GPT Pro flagged in its round-1 review, mandate inference_note on every non-range bid via the prompt, broaden the note cap from 200→300 chars.

## Trigger (pre-recalibration state)

Fresh 9-deal Extractor rerun (`/tmp/spec-rerun-20260420b/`) produced 3 hard §P-G2 `bid_type_unsupported` flags across 2 deals:

| Deal | Row | Root cause |
|---|---|---|
| medivation | 0 | `bid_type=informal`; source="non-binding proposal"; `"non-binding proposal"` absent from `INFORMAL_TRIGGERS` (list had `"non-binding indication"`); no inference_note, no range |
| medivation | 16 | `bid_type=formal`; source lacks §G1 trigger; inference_note present at ~370 chars, exceeds 200-char cap |
| mac-gray | 44 | `bid_type=formal`; source lacks §G1 trigger; no inference_note, no range |

All three are **AI-defect shape**, not rule shape. The validator did exactly what the TIER 1 tightening intended. Root driver: the extractor can (and did) rely on trigger-phrase matches in `source_quote` as an escape from attaching an inference_note — but the trigger list is inevitably incomplete.

## GPT Pro generalization risk

Round-1 review (`diagnosis/gptpro/2026-04-20/round_1_reply.md` Q3) explicitly called out `FORMAL_TRIGGERS` / `INFORMAL_TRIGGERS` at `pipeline.py:114-131` (20 phrases total) as a generalization-from-9-deals-to-392 risk. Empirical 9-deal satisfier distribution confirmed:

| Satisfier | Bids | Share |
|---|---:|---:|
| Trigger phrase hit | 28 | 30% |
| Range bid | 27 | 29% |
| Inference note | 51 | 55% |

(92 rows with non-null `bid_type`; multi-satisfier rows counted in every column they hit.)

Providence (22 bids) and Penford (8 bids) had **0% trigger coverage**. The trigger list is decorative — the inference_note path already carries the majority of classifications. Removing trigger-match as a validator satisfier is the systematic anti-overfit move.

## Changes shipped

| Commit | Change | CLOCK-RESET |
|---|---|:-:|
| `941d1bb` | `pipeline.py`: delete `FORMAL_TRIGGERS`/`INFORMAL_TRIGGERS` (18 lines); rewrite `_invariant_p_g2` to 2-path (range OR note≤300); −33 net lines | yes |
| `794b2d0` | `rules/invariants.md` §P-G2: rewrite check for 2 satisfiers; cite empirical satisfier data | yes |
| `e5d8f97` | `rules/bids.md` §G2: reshape satisfiers; keep §G1 trigger tables as classification guidance only; raise cap 200→300 | yes |
| `494fa7a` | `tests/`: drop 3 trigger-path fixtures; rewrite `synthetic_pg2_pass` to note path; add 5 note-path fixtures; 65/65 green | no |
| `1f3bbdb` | `prompts/extract.md`: mandate inference_note on every non-range bid, cap=300, §G1 triggers no longer exempt the note | yes |
| `452368a`, `17176cc`, `40af7f0`, `b33ffd0` | Finalize 4 clean-under-new-validator deals (providence-worcester, penford, petsmart-inc, stec) from existing raws | no |
| `1738878`, `a910616`, `0a8faf0`, `225ee47`, `2eb79b5` | Finalize 5 re-extracted deals (medivation, imprivata, zep, mac-gray, saks) | no |

Net `pipeline.py` delta: −33 lines (−18 constants, −15 trigger-branch in validator).

## Re-extraction workflow

Dry-run all 9 raws against the new 2-path validator to identify re-extraction targets:

| Deal | Hard `bid_type_unsupported` under new validator | Path |
|---|---:|---|
| medivation | 4 | re-extract |
| imprivata | 5 | re-extract |
| zep | 1 | re-extract |
| providence-worcester | 0 | finalize existing raw |
| penford | 0 | finalize existing raw |
| mac-gray | 2 | re-extract |
| petsmart-inc | 0 | finalize existing raw |
| stec | 0 | finalize existing raw |
| saks | 2 | re-extract |

5 deals re-extracted in parallel via clean-context Extractor subagents using the updated prompt (`/tmp/spec-rerun-20260420c/*.raw.json`). All 5 produced zero hard §P-G2 flags on first try — the explicit "note mandatory" language in the prompt was sufficient to eliminate the AI defect class.

## Final 9-deal state

| Deal | Status | Hard | Soft | Info | Total |
|---|---|---:|---:|---:|---:|
| medivation | passed | 0 | 5 | 3 | 8 |
| imprivata | passed | 0 | 1 | 18 | 19 |
| zep | passed | 0 | 8 | 42 | 50 |
| providence-worcester | passed | 0 | 33 | 88 | 121 |
| penford | passed | 0 | 12 | 15 | 27 |
| mac-gray | passed | 0 | 17 | 31 | 48 |
| petsmart-inc | passed | 0 | 0 | 29 | 29 |
| stec | passed | 0 | 11 | 11 | 22 |
| saks | passed | 0 | 3 | 22 | 25 |

**Aggregate: hard=0, soft=90, info=259, total=349.**

All 9 deals `passed` (no `validated`). Zero hard flags. `petsmart-inc` is the only `passed_clean` candidate (0 soft).

## Diff summary (AI vs Alex)

| Deal | Matched | AI-only | Alex-only | Card. mismatches | Field disagreements |
|---|---:|---:|---:|---:|---|
| medivation | 13 | 2 | 5 | 1 | 7 [bid_value_pershare=1, bid_value_unit=1, bidder_type=5] |
| imprivata | 25 | 2 | 3 | 1 | 13 [bid_value_pershare=1, bidder_type=12] |
| zep | 11 | 4 | 3 | 4 | 5 [bid_value_pershare=2, bidder_type=3] |
| providence-worcester | 17 | 9 | 11 | 4 | 11 [bid_date_rough=5, bid_type=2, bidder_type=4] |
| penford | 14 | 8 | 7 | 3 | 2 [bid_value_pershare=2] |
| mac-gray | 30 | 1 | 2 | 1 | 16 [bid_value_pershare=7, bidder_type=9] |
| petsmart-inc | 18 | 16 | 13 | 5 | 10 [bid_value_pershare=2, bid_value_upper=1, bidder_type=7] |
| stec | 22 | 5 | 3 | 2 | 20 [bid_value_pershare=3, bidder_type=17] |
| saks | 10 | 2 | 2 | 4 | 4 [bidder_type=4] |

`bidder_type` remains the dominant field-disagreement across deals (73 of 88 total disagreements across deals where it appears). This is a converter-side policy issue in `scripts/build_reference.py` (Alex's xlsx→JSON emits `public=null` where the AI infers strategic/public); unrelated to §P-G2.

## Test coverage

| Path | Pre-recalibration | Post-recalibration |
|---|:-:|:-:|
| Trigger hit (formal) | 1 fixture | — (path deleted) |
| Trigger hit (informal) | 1 fixture | — |
| Trigger direction mismatch | 1 fixture | — |
| Range valid | 1 fixture | 1 fixture |
| Range inverted | 1 fixture | 1 fixture |
| Range non-numeric | 1 fixture | 1 fixture |
| Inference-note pass | 1 (old `synthetic_pg2_pass` via trigger only) | 3 (`synthetic_pg2_pass`, `pg2_note_formal_process_position`, `pg2_note_informal_process_position`) |
| Inference-note at cap | 0 | 1 (`pg2_note_at_cap`) |
| Inference-note over cap | 0 | 1 (`pg2_note_over_cap`) |
| Inference-note empty | 0 | 1 (`pg2_note_empty`) |
| No-satisfier violation | 1 (`synthetic_pg2_fail`) | 1 |
| **Total fixtures** | **8** | **10** |
| **Tests passing** | 63 | 65 |

Note-path coverage went from **0% to 60%** of §P-G2 fixtures (6 of 10), matching the 55% production share.

## Exit-clock accounting

- Prior state (TIER 3 `c0ae73f`): `clock run 1/3` — but that rerun reused TIER 1 raws and wasn't a legitimate end-to-end test.
- Today's commits 1, 2, 3, 5 are tagged `CLOCK-RESET`: validator semantics, rulebook, and prompt all changed.
- **Clock resets to 0/3.** Today's finalize (commits 6, 7) is the post-reset baseline. It does NOT count as `1/3` because rule changes happened in the same session.
- Next clean rerun with unchanged rulebook would be `1/3`.

## What this closes

- GPT Pro round-1 Q3 (overfitting risk): no phrase vocabulary in validator; §G1 tables remain as advisory extractor guidance only. ✓
- Generalization to 392 target deals: 2-path validator is phrase-agnostic; extractor contract is now "always write a short note, justify your classification, cite a §G1 rule you followed." ✓
- iter-8 three hard flags (medivation×2, mac-gray×1): all resolved. ✓

## What remains open

- `bidder_type` field disagreements (converter-side `public=null` policy in `scripts/build_reference.py`) — still 73 of the residual field diffs. Separate workstream.
- NDA atomization-vs-aggregation disagreement on zep / mac-gray / providence / petsmart (AI atomizes; Alex aggregates) — already flagged in `CLAUDE.md`; orthogonal to §P-G2.
- Exit clock: 0/3. Needs 3 consecutive unchanged-rulebook clean runs before target-deal rollout gate opens.
