# Reference batch — gpt-5.5 / reasoning=high — findings (2026-04-30)

## Pool result
`Pool summary: selected=9 succeeded=7 skipped=0 failed=0`

7 of 9 finalized as `passed`. Two finalized as `validated` (have hard flags) —
`providence-worcester` and `petsmart-inc`. Reconcile correctly raises
`validated_reference_blocked` for both. The reference gate is open.

| slug | status | flags | Δ vs prior xhigh | new run_id |
|---|---|---:|---:|---|
| providence-worcester | **validated** | 112 | +6 | `bfbf845d0e79` |
| medivation | passed | 21 | +6 | `c49f3c644669` |
| imprivata | passed | 13 | -1 | `05dbc977c133` |
| zep | passed | 61 | -4 | `9f6b4b1ce4fb` |
| petsmart-inc | **validated** | 65 | +12 | `67b6b102ce0f` |
| penford | passed | 17 | +1 | `11bb83b29a72` |
| mac-gray | passed | 48 | -6 | `60e5caaa9c17` |
| saks | passed | 41 | -12 | `94352cc39238` |
| stec | passed | 19 | -1 | `4dbb3f767e98` |

## Reconcile (read-only)
```
reconcile FAILED: checked=9 errors=2 warnings=0
ERROR validated_reference_blocked [providence-worcester] hard flags block reference gate
ERROR validated_reference_blocked [petsmart-inc]        hard flags block reference gate
```
No archive drift, no progress/output/audit inconsistency. Both errors are the
expected gate behavior for the two validated deals.

CLI note: `pipeline.reconcile --strict` is referenced in `CLAUDE.md` but no
longer exists in the current `pipeline/reconcile.py`. The current scope flags
are `--scope {reference,all}` and `--slugs`. Either re-add `--strict` or
update CLAUDE.md.

## providence-worcester — **real regression on row 41**

Hard flags (3, all on row 41, `code=conditional_field_mismatch`, §P-R9):
- `bid_value_pershare must be null outside Bid rows`
- `bid_value_unit must be null outside Bid rows`
- `consideration_components must be null outside Bid rows`

Row 41 is an `Executed` row (G&W merger execution / press release):

```json
{
  "bid_note": "Executed",
  "bidder_alias": "G&W",
  "bid_value_pershare": 25.0,
  "bid_value_unit": "USD_per_share",
  "consideration_components": ["cash"]
}
```

§P-R9 (`rules/invariants.md`) requires bid-economics fields to be null on any
non-`Bid` row.

**Prior xhigh run had no hard flags on this deal** — Executed row 39 (same
row, before re-numbering) had `bid_value_pershare=null`, `bid_value_unit=null`,
`consideration_components=null`. So the regression is new under this run.

Probable cause: commit `8a51724` ("fix: require consideration components on
value-bearing bids") added an emphatic paragraph at `prompts/extract.md:79`
("§H2 / §P-R9") that pushes the model to populate `consideration_components`
on every value-bearing Bid. Under `high` the model overgeneralized "value-
bearing" to also cover the all-cash $25/share deal restated in the press-
release `Executed` row. The Executed-row null requirement is buried in a
checklist line (`prompts/extract.md:193`), not in a salient paragraph.

**Recommended fix** (prompt-level, low risk):

1. Add a salient paragraph next to the §H2/§P-R9 block stating that bid-economics
   fields (`bid_value`, `bid_value_pershare`, `bid_value_lower`, `bid_value_upper`,
   `bid_value_unit`, `consideration_components`) are forbidden on non-Bid rows
   (Executed, Final Round, Drop, etc.). The press-release restatement of the
   signed price belongs in `additional_note`, not in the bid-economics fields.
2. Re-extract `providence-worcester` only.

This is the highest-priority finding.

## petsmart-inc — **honest self-flag, not a regression**

Hard flags (6, `code=buyer_group_constituents_unidentified`):
- 1 deal-level
- 5 row-level (rows 22, 43, 51, 52, 55) — all `Buyer Group` `Bid`/`Executed` rows

The filing slice uses "Buyer Group" without naming each economic constituent
in the supporting text, so atomization to per-constituent rows is not possible
from the slice alone. The diff confirms this is a structural tradeoff:

- AI `deal.Acquirer = "Buyer Group"` vs Alex `"BC Partners, Inc."`
- 4 of 7 cardinality mismatches are `code=atomization_vs_aggregation` (e.g.,
  AI emits 15 atomized Drop rows where Alex aggregates to 12; AI emits 2 rows
  where Alex aggregates to 1).

The prior xhigh run had the same 6 Buyer Group rows but did not self-flag.
The current `high` run is more honest: it raises the structural limitation
instead of silently aggregating. This is a quality improvement.

**Recommended fix** (manual / rule decision, not a re-run):

Austin's call. Three options:

1. **Verify with external reference.** Manually identify the Buyer Group
   constituents from `reference/CollectionInstructions_Alex_2026.pdf` or the
   filing's plan-of-merger exhibits, add per-constituent atomization in
   `reference/alex/petsmart-inc.json`, and update the rulebook so the
   extractor is allowed to atomize using deal-context exhibits beyond the
   Background slice.
2. **Relax the rule.** Allow `Buyer Group` as a placeholder bidder when the
   slice does not name constituents, downgrade the flag to `soft` in
   `rules/invariants.md`, and document the policy in `rules/bidders.md`.
3. **Leave as-is.** Keep the deal in `validated` status and rely on Austin's
   manual `verified` adjudication.

If you want this deal to count toward the reference gate without further
prompt churn, options (1) or (2) are the path forward.

## Diff summary — passed deals

The seven passed deals have field-level disagreements with Alex reference but
no hard flags. The diff reporter suppression notes (DropSilent vs Drop, formal-
stage enrichment, source-workbook noise) are operating as designed. Nothing
new to investigate from this batch.

## Action items

- [ ] **High priority.** Patch `prompts/extract.md` to make Executed-row null
      requirement salient, then re-extract providence-worcester.
- [ ] **Medium priority.** Decide petsmart-inc atomization policy
      (verify-with-exhibits, relax-to-soft, or accept validated status).
- [ ] **Low priority.** Sync CLAUDE.md `pipeline.reconcile --strict` reference
      with the actual CLI.
- [ ] Reference-set gate remains **open**: 0 verified, 2 validated, 7 passed.
      Stability harness (`pipeline.stability --scope reference --runs 3`) is
      not yet applicable while the validated deals stand.

## Artifacts

- Run log: `quality_reports/runs/2026-04-30_reference-batch-high.log`
- Reconcile log: `quality_reports/runs/2026-04-30_reconcile-after-high.log`
- Diff reports: `scoring/results/petsmart-inc.{md,json}`
- Audit runs: `output/audit/{slug}/runs/{run_id}/` for the 9 new run_ids above
