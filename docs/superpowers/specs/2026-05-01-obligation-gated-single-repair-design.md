# Obligation-Gated Single-Repair Extraction Design

**Date:** 2026-05-01

**Status:** Approved for spec by Austin; pending implementation plan.

## Goal

Replace the staged repair architecture with a simpler, fail-closed pipeline:
one prompt-only extraction pass, deterministic validation plus filing-derived
obligations, and at most one tool-enabled repair round.

The design fixes the PetSmart failure class where an initial 60-row extraction
with a few local hard flags was repaired into a 15-row validator-passing output
that deleted most of the valid chronology. A deal must not pass by becoming
smaller, internally consistent, and wrong.

## Non-Goals

- Do not add an Alex-based validator. Alex references remain review aids, not
  ground truth.
- Do not add another model role.
- Do not keep the old prompt-only repair turn as a compatibility path.
- Do not preserve stale cache compatibility with previous repair contracts.
- Do not introduce free-form JSON fallback, non-strict output fallback, or
  partial legacy readers.

## Live Pipeline Shape

```text
run.py / pipeline.run_pool
  -> prompt-only extractor with strict SCHEMA_R1
       model emits {deal, events}
  -> prepare_for_validate()
       Python rebuilds/enforces bidder_registry and canonical row order
  -> validate()
       existing deterministic invariants
  -> derive_obligations()
       deterministic filing-text obligation extraction
  -> check_obligations()
       obligation satisfaction against current extraction
  -> if hard validator flags or hard unmet obligations:
       one tool-enabled repair round
       tools: check_row, search_filing, get_pages, check_obligations
       model emits a complete corrected extraction plus repair-only assertions
  -> prepare_for_validate()
  -> validate()
  -> check_obligations()
  -> check_repair_conservation()
  -> finalize_prepared()
       passed / passed_clean only if no hard flags remain
       validated if any hard validator, obligation, or conservation flag remains
```

There is exactly one extraction pass and at most one repair round. Extraction
has no tools. Repair has the full deterministic repair toolkit immediately.

## Deterministic Obligations

Add a first-class obligation layer that reads only filing text from
`data/filings/{slug}/pages.json`. It does not read Alex references, scoring
outputs, chat history, or generated reports.

An obligation is a Python data object with:

- `obligation_id`: stable id within the run.
- `kind`: closed vocabulary such as `exact_count_nda`,
  `exact_count_bid`, `exact_count_final_round`, `buyer_group_definition`,
  `buyer_group_executed_constituents`, `late_member_inherited_nda`, or
  `countable_dropout_outcome`.
- `severity`: hard unless explicitly documented otherwise.
- `source_quote` and `source_page`: filing evidence for the obligation.
- `expected`: machine-readable count or predicate.
- `matched_rows`: `BidderID` values or zero-based row indexes satisfying the
  obligation.
- `reason`: concise human-readable explanation.

Initial obligation detectors should be intentionally high precision. If a
pattern cannot be made deterministic and filing-grounded, leave it to human
review instead of guessing.

### Required Initial Obligation Families

1. **Exact-count current-process NDAs**
   Detect passages such as "entered into confidentiality and standstill
   agreements with 15 potentially interested financial buyers." The extraction
   must emit exactly that many bidder-side current-process `NDA` rows for the
   stated cohort. Additional later inherited `NDA` rows require separate filing
   evidence and separate obligations.

2. **Exact-count bid submissions**
   Detect passages such as "six of the potentially interested parties submitted
   indications of interest." The extraction must emit exactly that many
   current-process `Bid` rows for the stated submission cohort, unless a
   filing-grounded hard ambiguity flag explains why the count cannot be mapped
   mechanically to rows.

3. **Final-round advancement counts**
   Detect passages such as "allow the four bidders ... to proceed to the final
   round." The extraction must include the process-level `Final Round` row and
   compatible bidder fates for parties eliminated or advanced when the filing
   gives countable outcomes.

4. **Buyer-group definitions**
   Detect filing definitions such as "the Buyer Group refers to..." and party
   descriptions stating who owns Parent. These obligations supply filing
   evidence for required buyer-group atomization. PetSmart's Buyer Group must
   resolve to BC Partners, La Caisse, GIC, StepStone, and, after December 12,
   Longview.

5. **Late-member inherited NDA / ConsortiumCA**
   Detect passages where a late member and an already-NDA-bound group enter a
   bidder-bidder confidentiality agreement. The extraction must include the
   `ConsortiumCA` row and the late member's inherited `NDA` row when current
   rules require it.

6. **Countable dropout outcomes**
   When a filing gives a countable NDA or bid cohort and narrates elimination,
   non-submission, no response, no ability to remain above a price level, or
   non-competitive status, the extraction must not silently delete the cohort.
   It must emit `Drop`/`DropSilent` rows according to current event rules, or
   surface a hard ambiguity flag.

## Repair Contract

The old two-turn staged repair contract is removed. Repair becomes a single
tool-enabled correction round.

Repair receives:

- the complete prepared draft;
- all hard validator flags;
- all unmet obligations;
- row-conservation context identifying rows not implicated by hard issues;
- unique deterministic filing pages from hard flag and obligation sources,
  including non-Background pages when an obligation depends on those pages,
  such as buyer-group definitions.

Repair can call:

- `check_row(row)`;
- `search_filing(query, page_range, max_hits)`;
- `get_pages(start_page, end_page)`;
- `check_obligations(candidate_extraction)`.

Repair emits a strict repair response:

```json
{
  "deal": {},
  "events": [],
  "obligation_assertions": [
    {
      "obligation_id": "example",
      "status": "satisfied",
      "row_ids": [1, 2],
      "reason": "Rows 1 and 2 satisfy the exact-count obligation."
    }
  ]
}
```

`deal` and `events` remain the complete corrected extraction. The
`obligation_assertions` array is repair-only audit scaffolding. Python strips it
before final output and recomputes every obligation from filing text.

The model never decides whether obligations are waived. It can only propose a
corrected extraction.

## Row Conservation

Repair may replace, split, or add rows needed to satisfy hard validator flags or
unmet obligations. It may not delete unrelated valid work.

Before repair, Python records conservation anchors for rows that are not
directly implicated by hard validator flags or unmet obligations. Anchors should
be robust to canonical row ordering and BidderID renumbering, using fields such
as:

- `bid_note`;
- `bid_date_precise` / `bid_date_rough`;
- `bidder_alias` and `bidder_name` when meaningful;
- bid economics fields;
- source page values;
- normalized source-quote prefixes;
- event-specific classification fields.

After repair, Python checks that each protected anchor still has a compatible
row. A missing anchor is allowed only when Python can tie the replacement or
split to a hard validator flag or obligation. Model-provided assertions do not
waive this check. Missing protected anchors create hard
`repair_lost_unaffected_rows` flags.

This makes the PetSmart 60-row to 15-row collapse impossible to pass.

## Status Semantics

Finalization remains fail-closed:

- no hard validator flags, hard unmet obligations, or hard conservation flags:
  `passed` or `passed_clean`;
- any hard validator flag, hard unmet obligation, or hard conservation flag:
  `validated`;
- provider/runtime failure with no prior successful live extraction: `failed`;
- provider/runtime failure with a prior successful live extraction: preserve
  prior live progress state and record the failed attempt in audit metadata.

Unmet hard obligations after the single repair round are finalized as
`validated`, not retried.

## Audit Contract

Each run archive must make the repair decision inspectable:

- `obligations.json`: derived obligations and satisfaction results before
  repair and after repair.
- `repair_turns.jsonl`: one entry at most, with previous event count, revised
  event count, hard flags before/after, unmet obligations before/after,
  conservation failures, tool call count, and outcome.
- `repair_response.json`: raw parsed repair response including
  `obligation_assertions`.
- `validation.json`: include full row/deal flags and obligation/conservation
  summary, not only counts.
- `manifest.json`: record `obligation_contract_version` and
  `repair_strategy = "obligation_gated_single_repair"`.

The only mutable audit pointer remains `latest.json`.

## Tool Contract

`check_obligations(candidate_extraction)` is deterministic and read-only. It:

1. prepares the candidate extraction enough to rebuild bidder registry and row
   order;
2. derives filing obligations for the slug;
3. checks candidate rows against those obligations;
4. returns obligation ids, statuses, matched rows, source pages, and concise
   reasons.

For exact-count NDA and bid obligations, buyer-group constituent sibling rows
that cite the same aggregate filing event count as one filing-party unit. This
keeps the obligation layer aligned with the atomized output schema when the
filing's party count treats a buyer group as one party.

The tool is a repair aid only. The orchestrator reruns the same code after
repair and uses the post-repair result as the authority.

## Contract Versioning And No Backward Compatibility

This design changes the live architecture. Implementation must:

- replace the old staged repair contract;
- update `AGENTS.md`, `CLAUDE.md`, `SKILL.md`, and
  `docs/linkflow-extraction-guide.md`;
- update repair prompts and prompt-contract tests;
- add `obligation_contract_version` to cache eligibility and stability
  fingerprints;
- mark old cached runs stale through contract-hash changes;
- remove tests and docs that describe prompt-only repair 1 / targeted repair 2
  as the live architecture.

No compatibility shim should accept both repair strategies as live.

## Reference Review And Diff

Alex references remain non-authoritative. However, reference review tooling
should surface obvious unresolved review blockers, including:

- zero matched rows;
- major cardinality mismatches;
- passed-but-unverified reference outputs with unresolved scoring reports.

These diagnostics do not change extraction validation by themselves. They help
Austin decide what to inspect before marking a reference deal verified.

`pipeline.reconcile` may remain an archive-consistency tool, but the target gate
must still require all nine reference deals to be manually verified and stable
under the new obligation contract.

## Testing Strategy

Tests should be written before implementation and should fail under the current
architecture.

Required regression tests:

1. PetSmart-style repair collapse: initial draft has many valid rows and one
   repair issue; repaired output deletes unrelated rows; final result must
   contain hard `repair_lost_unaffected_rows`.
2. Exact-count NDA under-emission: filing says 15 confidentiality agreements;
   candidate emits two NDA rows; obligation check hard-fails.
3. Buyer Group definition: filing defines Buyer Group constituents outside the
   Background section; obligation extraction finds them and requires
   constituent-level execution rows.
4. Bidder 3 vs Buyer Group: a passage saying two bidders requested permission
   to work together cannot satisfy a Buyer Group constituent obligation when
   the filing separately labels those two bidders as Bidder 3.
5. Late Longview join: filing says Longview and Buyer Group entered a
   confidentiality agreement; candidate needs `ConsortiumCA` plus inherited
   Longview `NDA` where current rules require it.
6. Single repair round: hard issues trigger exactly one repair call with all
   four tools; no prompt-only repair turn and no second repair call exist.
7. Cache invalidation: old audit runs missing `obligation_contract_version` or
   carrying the old repair strategy are not cache eligible.
8. Audit completeness: repair archive includes obligations, repair response,
   row-count delta, and full validation flags.

## Rollout

Implementation should land as one architecture change, not a compatibility
layer:

1. Add failing tests for obligations, repair conservation, single repair, audit,
   and cache invalidation.
2. Implement the obligation data model and PetSmart-class detectors.
3. Replace the repair loop with one tool-enabled repair round.
4. Add `check_obligations` to the repair tool catalog.
5. Add row-conservation checks and hard flags.
6. Update audit, manifest, docs, prompts, and live contracts.
7. Rerun PetSmart under the new contract and inspect that it either passes with
   the correct broad chronology or finalizes as `validated` with actionable hard
   obligations.

The target-deal gate remains closed until all nine reference deals are manually
verified and stability is proven under this new contract.
