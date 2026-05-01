# Reference Stability Goal Design

**Date:** 2026-05-02

**Status:** Approved design; reviewed by Codex-administered GPT-5.5 xhigh
agent and revised for material findings.

## Purpose

Define the objective for a long-running `/goal` agent that will stabilize the
M&A extraction pipeline and produce a committed, evidence-backed reference
release proof.

The agent must operate from the current repo contract in
`/Users/austinli/bids_try`, but it may redesign pipeline components when
reference-deal evidence proves the current obligation-gated single-repair
architecture cannot reach the proof. Any redesign is a replacement of the live
contract, not an additive compatibility path.

This objective intentionally changes verification authority: for this release
process, agent verification may mark reference deals `verified` after documented
filing-grounded review. The long-running agent must update `AGENTS.md`,
`CLAUDE.md`, `SKILL.md`, and `docs/linkflow-extraction-guide.md` in the same
finished implementation/proof work so those live contracts no longer define
`verified` as Austin-only manual verification.

## Goal Objective

Use this objective for the long-running agent:

> Stabilize the M&A extraction pipeline so the nine reference deals are fully
> extracted, tested, reconciled, agent-verified against SEC filing text,
> committed with current code/docs/tests/generated proof artifacts, and accepted
> by the reference stability gate as `STABLE_FOR_REFERENCE_REVIEW`.

The agent should keep working until the success criteria in this spec are met,
unless it is blocked by missing credentials or an external provider outage that
prevents live model runs. Ordinary model mistakes, hard flags, stale docs, stale
artifacts, failing tests, or incomplete reference verification are not terminal
blockers.

## Scope

In scope:

- Pipeline code, prompts, rules, tests, and live contract docs.
- Reference-run generated artifacts under `state/`, `output/extractions/`,
  selected current/proof-supporting `output/audit/` run directories, and
  `quality_reports/`.
- Agent verification artifacts for all nine reference deals under the canonical
  path `quality_reports/reference_verification/{slug}.md`.
- Stale-code, stale-doc, stale-test, stale-report, and stale-generated-artifact
  cleanup.
- Commits containing the finished code/docs/tests and current generated proof
  artifacts.

Out of scope:

- Target-deal extraction, unless the reference gate proof exists and Austin
  separately authorizes target release with `--release-targets`.
- Treating Alex reference JSON or workbook data as ground truth.
- Preserving retired schemas, repair strategies, cache formats, prompt
  contracts, audit layouts, or state/output contracts.

## Baseline Procedure

The long-running agent must begin by refreshing local facts rather than trusting
this document as a live snapshot:

1. Inspect `git status --short` and preserve unrelated user edits.
2. Read `AGENTS.md`, `SKILL.md`, `docs/linkflow-extraction-guide.md`, and the
   current implementation/spec/plan docs relevant to the active architecture.
3. Inspect current reference statuses in `state/progress.json`.
4. Inspect existing audit runs and stability artifacts.
5. Run or plan a fast local test baseline before making behavior changes.

At design time, the repo had a dirty worktree and the reference gate was not
fully open. The long-running agent must verify the current state directly.

## Work Sequence

The agent should execute the work in this order:

1. Establish the refreshed baseline and identify the current live architecture.
2. Finish the current implementation or redesign only where reference evidence
   shows the current design cannot reach the success proof.
3. Use tests first for behavior-changing code work when feasible.
4. Run the full test suite and fix failures without adding fallbacks or
   compatibility shims.
5. Run fresh reference extractions using `gpt-5.5` with `high` reasoning by
   default, with controlled worker concurrency and `.env` or shell environment
   credentials.
6. For each reference deal, inspect the finalized extraction, hard/soft flags,
   diff output, audit files, and SEC filing evidence.
7. Perform filing-grounded agent verification before setting a reference deal
   to `verified`, and update the live contract docs before relying on agent
   verification as a valid `verified` source.
8. Repeat fixes, rule/prompt updates, and reference reruns until all nine
   reference deals are verified under the live contract.
9. Run `python -m pipeline.reconcile --scope reference`.
10. Ensure at least three stable archived reference runs per slug under
    unchanged prompt/schema/rulebook/contract hashes.
11. Run `python -m pipeline.stability --scope reference --runs 3 --json --write
    quality_reports/stability/target-release-proof.json`.
12. Deep-clean stale code, docs, tests, fixtures, reports, helpers, and
    generated artifacts.
13. Commit the finished state, including code/docs/tests and current generated
    proof artifacts scoped to this objective.

## Success Criteria

The `/goal` succeeds only when all of these are true:

- `python -m pytest -q` exits 0.
- All nine reference deals are `status=verified` in `state/progress.json`.
- Agent verification artifacts exist at
  `quality_reports/reference_verification/{slug}.md` for all nine reference
  deals and cite SEC filing evidence.
- Current `output/extractions/{slug}.json` files exist for all nine reference
  slugs.
- Current reference extractions have no hard validator, obligation, or
  repair-conservation flags.
- `python -m pipeline.reconcile --scope reference` exits 0.
- `python -m pipeline.stability --scope reference --runs 3 --json --write
  quality_reports/stability/target-release-proof.json` exits 0.
- `quality_reports/stability/target-release-proof.json` has
  `schema_version: target_gate_proof_v1`,
  `classification: STABLE_FOR_REFERENCE_REVIEW`, `requested_runs >= 3`, and at
  least three selected immutable run IDs for every reference slug.
- Target extraction remains blocked unless separately authorized.
- Tracked repo docs describe only the current live architecture and explicitly
  define agent filing-grounded verification as sufficient authority for
  reference-deal `verified` status under this release process.
- Stale code, docs, tests, fixtures, reports, and generated artifacts have been
  deleted or rewritten.
- The final committed worktree is clean except for ignored local secret files.

## Redesign Authority

The agent may redesign pipeline components, but only under these rules:

- State the reference-deal failure class before adding a new rule, module, model
  role, or orchestration layer.
- Keep SEC filing text as factual ground truth.
- Keep Python deterministic validation, obligation checks, conservation checks,
  reconciliation, and stability proof as authoritative gates.
- Replace stale contracts rather than supporting old and new contracts in
  parallel.
- Update live contract docs in the same change as any architecture, schema,
  rulebook, state, output, audit, prompt, or orchestration change.
- Regenerate affected reference/output/state/audit artifacts or delete them.

## Compatibility And Fallback Bans

The agent must not add or preserve:

- Free-form JSON fallback.
- Non-strict structured-output bypass.
- Provider branches that disable schema enforcement.
- `previous_response_id` chains.
- Legacy cache readers.
- Backward-compatible aliases for retired schema fields.
- Old and new repair strategies as simultaneous live paths.
- Transition helpers that survive completion.
- Docs that describe retired and current behavior as both supported.

Use git history as the compatibility record.

## Agent Verification

The long-running agent is authorized to mark reference deals `verified`, but
only after agent review against SEC filing text and after updating the live
contract docs to recognize agent filing-grounded verification for this release
process.

For each reference slug, the agent must create a verification artifact at
`quality_reports/reference_verification/{slug}.md`. Each artifact must include:

- Slug, target name, run ID, model, reasoning effort, and audit path.
- Commands used for extraction, diff, and validation.
- Summary of row-count, flag, and diff status.
- A complete AI-vs-Alex diff ledger where every disagreement is adjudicated
  against the filing text and, when the issue is a collection-rule question,
  against Alex's PDF and the repo rulebook.
- Any rulebook or prompt changes made because of the review.
- Any reference JSON, rulebook, or comparator update made because the filing
  showed Alex or the existing comparator was wrong.
- Explicit conclusion that the extraction is verified, or a blocker list if it
  cannot be verified yet.

The agent must not mark a deal `verified` solely because the model output passes
schema validation.

## Generated Artifact And Commit Rules

Generated artifacts are part of the deliverable. The agent should commit the
current proof artifacts needed to reproduce the reference release state.

The audit archive rule is precise:

- Preserve valid immutable run directories.
- Delete only contract-invalid loose legacy files, stale failed experiments, or
  obsolete generated reports, and record those deletions in the cleanup report.
- Stage `output/audit/{slug}/latest.json` pointers for the nine reference
  slugs.
- Stage the immutable run directories selected by
  `quality_reports/stability/target-release-proof.json`.
- Stage any current `last_run_id` run directory that supports a verified
  reference extraction even if it is not selected by the stability proof.
- Do not blindly `git add output/audit/` without checking for stale or unrelated
  generated artifacts.

Required generated proof paths include:

- `state/progress.json`
- `state/flags.jsonl`
- `output/extractions/`
- selected current/proof-supporting `output/audit/{slug}/runs/{run_id}/`
  directories and `output/audit/{slug}/latest.json` pointers
- `quality_reports/stability/target-release-proof.json`
- `quality_reports/reference_verification/`
- any current cleanup/proof report created for this objective

The agent must avoid committing unrelated dirty changes or obsolete generated
reports. If a CLI supports `--commit`, it must commit only current-deal
output/state/audit paths and leave unrelated worktree changes alone.

## Credential Boundary

Austin allows the session-provided API key to be used during this development
session for live testing. The agent must still keep the literal key out of:

- tracked files;
- committed generated artifacts;
- docs;
- prompts;
- audit files;
- final reports.

Prefer `.env` or exported environment variables for live runs. If a prompt,
audit file, log, shell history, markdown note, or any generated artifact captures
the literal key, stop and require key rotation before continuing. Before final
completion, run a secret scan over tracked files and every generated artifact
intended for staging.

## Required Commands

The final verification command set must include at minimum:

```bash
python -m pytest -q
python -m pipeline.run_pool --filter reference --workers 4 --dry-run
python -m pipeline.run_pool \
  --filter reference \
  --workers 4 \
  --extract-model gpt-5.5 \
  --adjudicate-model gpt-5.5 \
  --extract-reasoning-effort high \
  --adjudicate-reasoning-effort high \
  --re-extract
python -m pipeline.reconcile --scope reference
python -m pipeline.stability \
  --scope reference \
  --runs 3 \
  --json \
  --write quality_reports/stability/target-release-proof.json
```

The agent may adjust worker count downward for provider stability. It may use
`xhigh` for targeted one-off diagnosis or review runs, but the standard release
proof should be reproducible with documented model and reasoning settings.

## Required Review

Before Austin is asked to review this spec, Codex must administer a
GPT-5.5 xhigh review agent. The review agent should check this spec for:

- contradictions with `AGENTS.md`, `SKILL.md`, and
  `docs/linkflow-extraction-guide.md`;
- ambiguity in terminal success criteria;
- accidental fallback or backward-compatibility loopholes;
- missing stale-cleanup requirements;
- unsafe credential handling;
- unclear authority for marking deals `verified`;
- missing generated-artifact or commit boundaries.

Codex must resolve material review findings in this spec before asking Austin
for review.

## Final Deliverables

The long-running agent should finish with:

- committed pipeline code, prompts, rules, docs, and tests aligned to the final
  live architecture;
- committed fresh reference outputs, state, selected proof-supporting audit
  archives, verification artifacts, and stability proof;
- a stale-cleanup record listing deleted or replaced stale artifacts;
- a final operator summary with exact commands run, model/reasoning settings,
  selected run IDs, reconcile/stability results, commits created, and residual
  risks.
