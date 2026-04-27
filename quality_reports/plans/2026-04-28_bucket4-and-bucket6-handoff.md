# Handoff — Bucket 4 (extractor prompt skeleton) + Bucket 6 (diff harness)

**Status:** DRAFT — discussion in progress, awaiting Austin's decisions on items A–I.
**Branch:** `main` (ahead of origin once this commit lands).
**Created:** 2026-04-28, end of laptop session, to resume on another machine tomorrow.

## Context for next session

Austin asked me to "proceed with bucket 4 and 6. meticulously investigate and discuss with me." The previous session (2026-04-27 / 28) closed Buckets 1+2+3+5 of the production code-review and reset state for a clean re-extract. Buckets 4 and 6 were explicitly deferred at that time because they touch LLM behavior (4) and the diff-reporting layer (6) and Austin wanted a deliberate pass.

**Do NOT start implementing yet.** Austin asked for discussion first. Read this file, read the linked source files, then resume the conversation by presenting (or re-presenting) the decision points below and asking Austin which way to go on each.

The repo state when this handoff was written:
- 12 modified files + 8 new fixtures from the prior session, ALL uncommitted.
- 9 reference deals reset to `pending`; 392 target deals still `pending`.
- Tests: 141/141 green.
- The last completed work is summarized in [quality_reports/session_logs/2026-04-27_review-and-simplify-pass.md](../session_logs/2026-04-27_review-and-simplify-pass.md).

## Bucket 4 — Extractor prompt missing schema fields

### What's missing from the prompt skeleton

[prompts/extract.md:110-156](../../prompts/extract.md) is the only concrete shape the LLM mimics. Compared against §R1 in [rules/schema.md:191-291](../../rules/schema.md), **18 fields are absent** from the skeleton:

**Deal-level (8):**
- `all_cash` — §N2 derivation. All 9 references = `true`.
- `target_legal_counsel` / `acquirer_legal_counsel` — §J2. Both `null` in all 9 references.
- `go_shop_days`, `termination_fee`, `termination_fee_pct`, `reverse_termination_fee` — §O1. All `null` in references.
- `deal_flags` — §R2. Validator writes here today (`pipeline.py:412, 1659`); LLM behavior is inconsistent.

**Event-level (10):**
- `bid_type_inference_note` — §G2. Validator already enforces (`pipeline.py:1242`); prose mentions it (line 67) but skeleton does not.
- `cash_per_share`, `stock_per_share`, `contingent_per_share`, `consideration_components`, `aggregate_basis` — §H2 / §H4 composite consideration.
- `exclusivity_days`, `financing_contingent`, `highly_confident_letter`, `process_conditions_note` — §O1 process conditions. `highly_confident_letter` defaults `false`; rest default `null`.

### Important caveat: reference data is blind to most of these

I checked all 9 `reference/alex/*.json` files: zero non-default values across deals × events except 1 `exclusivity_days` row in Zep. The diff harness CANNOT validate these — only Austin reading the filing can.

### Bucket 4 decision points (waiting on Austin)

- **A. Scope:** minimal (skeleton only) / **medium (recommended)** (skeleton + new procedure step + 4 self-checks) / maximal (medium + worked examples). My recommendation: medium, ~2 hours.
- **B. Anchor for composite consideration:** new Step 8a between §G1 (Step 8) and §M skip rules (Step 9), or fold into Step 8.
- **C. Validator backstop §P-H1:** assert `cash_per_share + stock_per_share + contingent_per_share == bid_value_pershare` (modulo nulls). Already written as soft `composite_reconciliation_mismatch` in §H2; promoting it to a Python check costs ~30 lines.
- **D. Reference backfill:** `build_reference.py` currently pads composite/process-condition fields as `None`. Pure-cash deals could be backfilled (`consideration_components=["cash"]`, `cash_per_share = bid_value_pershare`) so AI vs Alex actually compares for the cash component. Yes/no.

## Bucket 6 — Diff harness improvements

### Status of the four sub-issues

[scoring/diff.py](../../scoring/diff.py) and [tests/test_diff.py](../../tests/test_diff.py).

1. **`--write` filename non-determinism.** [diff.py:526](../../scoring/diff.py) uses `datetime.now()` UTC → reruns produce N+1 result files instead of overwriting. Real bug, small fix.
2. **`COMPARE_EVENT_FIELDS` skips composite fields.** Half-real. `bid_value` (aggregate USD) genuinely should be compared. The other 5 (`cash_per_share`, `stock_per_share`, `contingent_per_share`, `consideration_components`, `aggregate_basis`) are intentionally in `AI_ONLY_EVENT_FIELDS` ([diff.py:59-64](../../scoring/diff.py)) because Alex's references are all null — bringing them in would mass-false-positive.
3. **Closed-list annotation.** Mostly redundant. Validator §P-R3 ([pipeline.py:616](../../pipeline.py)) already hard-flags `invalid_event_type`; such extractions never reach `passed`, so the diff would never see them. My recommendation: drop this sub-issue.
4. **`alex_flagged_rows.json` integration test.** Real but small. Existing tests cover cardinality + zip; never exercise `_alex_flag_note_for` ([diff.py:181](../../scoring/diff.py)).

### Bucket 6 decision points (waiting on Austin)

- **E. `--write` filename strategy:** stable name `{slug}.md` / `{slug}.json` (recommended) / run-id stamp `{slug}_{run_id_short}.md` / status quo (bad).
- **F. Add `bid_value` to COMPARE_EVENT_FIELDS:** yes/no. Surfaces aggregate-vs-per-share §H4 disagreements.
- **G. Bring composite fields into compare:** **NO** — keep in `AI_ONLY_EVENT_FIELDS` unless D is yes. Locked decision unless Austin overrides.
- **H. Closed-list annotation:** **DROP** — validator already covers it. My recommendation.
- **I. `alex_flagged_rows.json` integration test:** small win, add it.

## Recommended execution order (after Austin decides)

1. Bucket 4 first (changes LLM output). Decide A/B/C/D up front. Implementation lives in `prompts/extract.md` + possibly `pipeline.py` (if C=yes) + possibly `scripts/build_reference.py` (if D=yes).
2. Bucket 6 second. Once we know what the AI emits, the diff harness can be tuned correctly. Apply E + F + I; drop H; keep G as null-pass.
3. Re-run `python scripts/build_reference.py --all` if D=yes.
4. Re-render the 9 reference deals (eventually) once a clean prompt is in.

## How to resume on the new machine

```bash
git pull origin main
git status                                  # confirm clean (commit pulled)
python -m pytest -x                         # confirm 141 tests still green
cat quality_reports/plans/2026-04-28_bucket4-and-bucket6-handoff.md
cat quality_reports/session_logs/2026-04-27_review-and-simplify-pass.md
```

Then in a fresh Claude session:
> "Resume Bucket 4 + Bucket 6 work. Read `quality_reports/plans/2026-04-28_bucket4-and-bucket6-handoff.md` for the open decision points. Present items A through I and wait for my decisions before implementing."

## Open files / artifacts

- [prompts/extract.md](../../prompts/extract.md) — main edit target for Bucket 4.
- [rules/schema.md §R1](../../rules/schema.md) — schema contract; do not modify, only conform to.
- [rules/bids.md §H2 §H4 §O1](../../rules/bids.md) — composite-consideration + process-condition specs.
- [rules/events.md §J2](../../rules/events.md) — legal-counsel structural home.
- [pipeline.py:1192-1267 (§P-G2)](../../pipeline.py) — existing validator for `bid_type_inference_note`.
- [scoring/diff.py](../../scoring/diff.py) — Bucket 6 edit target.
- [tests/test_diff.py](../../tests/test_diff.py) — extend for sub-issue 4.

## Out of scope for this work

- Re-running the 9 reference extractions (gate stays closed).
- Touching the 392 target deals.
- Bucket 7 (additional fixture matrix) — separate pass.
- Pre-existing tech debt: `apply_q5_medivation` inline `_next_cid` collapse (out of scope).
