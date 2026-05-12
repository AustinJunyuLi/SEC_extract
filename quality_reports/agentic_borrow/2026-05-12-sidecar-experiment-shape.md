# Agentic Sidecar Experiment Shape

Date: 2026-05-12

Status: archived for memory only. Do not treat this as a live extraction
contract, a pending merge branch, or a source of production code.

## Source Branch

- Branch: `codex/agentic-sec-graph-borrow-20260511T154202Z`
- Worktree before deletion:
  `/Users/austinli/.config/superpowers/worktrees/bids_try/agentic-sec-graph-borrow-20260511T154202Z`
- Shared base with `api-call`: `b368951`
- Sidecar commits observed:
  - `9642ab6 feat: add agentic comparison sidecar`
  - `9b9c246 test: record agentic provider probe`
- The worktree also had dirty OpenAI/backend comparison edits and runtime state
  changes. Those were intentionally not borrowed.

## Purpose

The branch explored a parallel "agentic sidecar" for extraction quality
experiments. It was not a production replacement for `deal_graph_v2`.

The useful question it asked was:

> Can a staged extraction lab reveal missing filing facts, schema gaps, prompt
> weaknesses, or model-quality differences without touching production graph
> artifacts?

The answer was: possibly yes as a lab, but no as a live pipeline.

## Intended Write Boundary

The sidecar was designed to write only to experimental paths:

- `output/audit/agentic/{run_id}/{slug}/`
- `quality_reports/agentic_borrow/{run_id}/`

It had tests asserting that dry runs do not mutate:

- `output/extractions/`
- `output/review_rows/`
- `output/review_csv/`
- `state/progress.json`
- `state/flags.jsonl`

That boundary is the one sound part of the experiment.

## Module Shape

The sidecar added roughly these modules:

- `pipeline/agentic/filing.py`
  - Built a filing package from production Background-section slicing and
    paragraph-local citation units.
  - This reused the same filing source of truth as production.

- `pipeline/agentic/retrieval.py`
  - Built a deterministic paragraph index.
  - Supported exact quote lookup, literal search, regex search, simple BM25
    search, paragraph neighborhoods, and lightweight date/money/count parsers.
  - Useful as a debugging or experiment helper, not as a canonical parser.

- `pipeline/agentic/schemas.py`
  - Defined strict Pydantic role schemas for filing scout, region reader,
    schema specialist, verifier, omission checker, consistency reducer, and
    schema gap reducer.
  - Weak point: `ClaimAttempt.payload` was an arbitrary dictionary, so the
    sidecar did not enforce the production claim schema.

- `pipeline/agentic/run.py`
  - Orchestrated the sidecar flow:
    1. Build filing package.
    2. Build retrieval index.
    3. Call filing scout.
    4. Chunk citation units into regions.
    5. Call region readers.
    6. Call schema specialists for actors, events, bids, counts, and relations.
    7. Bind proposed quotes exactly.
    8. Accept claims with at least one exact quote binding.
    9. Write an experimental graph, review rows, and comparison output.
  - Weak point: the scout did not really choose regions. The runner still used
    fixed 24-citation-unit chunks.
  - Weak point: the verifier checked quote binding, not whether the quote
    semantically supported the claim.
  - Weak point: the graph writer bypassed production `finalize_claim_payload()`.

- `pipeline/agentic/lifecycle.py`
  - Sketched claim lifecycle statuses such as proposed, bound, verified,
    escalated, and accepted.
  - Good idea conceptually, but only lightly used by the runner.

- `pipeline/agentic/verifier.py`
  - Aggregated verifier votes into lifecycle statuses.
  - Useful pattern for future experiments, but not enough for production
    semantic verification.

- `pipeline/agentic/issue_reducer.py`
  - Reduced low-confidence or blocked findings into review issues.
  - Matched the desired philosophy of surfacing material uncertainty without
    creating review spam.

- `pipeline/agentic/tool_loop.py`
  - Encoded Responses API function-call loop history.
  - Not compatible with the current production doctrine, which intentionally
    has no tool loop, no response-chain reuse, and no secondary correction path.

- `pipeline/agentic/compare.py`
  - Compared experimental outputs against current production snapshots using
    stable JSON payload signatures.
  - Useful for drift and coverage comparisons, but not a truth adjudicator.

- `pipeline/agentic/probe.py`
  - Probed provider support for strict structured output and synthetic tool-loop
    history.
  - The probe was OpenAI-specific in the observed worktree and did not match
    the committed Claude-default backend contract.

## Observed Result

The worktree included an OpenAI comparison report for Mac Gray and PetSmart:

- Mac Gray regressed from `passed_clean` with zero open review rows to
  `needs_review` with two open review rows.
- PetSmart remained clean but had mixed new/lost fact drift.
- The report concluded that first-party OpenAI was technically stable on that
  slice but not a drop-in quality replacement.

This reinforced the decision not to adopt the branch as production.

## Why It Was Not Borrowed

The live `bids_try` contract is stricter:

- The provider emits strict claim payloads only.
- Python owns quote binding, source spans, canonical ids, claim dispositions,
  graph rows, graph validation, review rows, state, and DuckDB artifacts.
- Production finalization goes through
  `pipeline.deal_graph.orchestrate.finalize_claim_payload()`.

The sidecar violated that production shape if merged wholesale because it built
an alternate graph writer and review projection. That would create a second
source of truth.

The branch also carried stale backend/doc edits that conflicted with the
committed Claude Agent SDK default plus direct OpenAI optional backend.

## Final Decision

Do not borrow the sidecar now.

Preserve this document as a record of the experiment shape, then hard-delete the
branch and worktree. Future architecture work may revisit the ideas only as a
new first-principles design, not as a merge of the archived branch.

