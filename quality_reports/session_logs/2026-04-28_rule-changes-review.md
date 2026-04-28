---
date: 2026-04-28
branch: api-call
status: in_progress
---

# Session: Code review of recent rule changes + 4-bug fix bundle + stale cleanse

## Goal

**Phase 1 (complete).** Read-only review of the five rule-touching commits on
`api-call` (2739f6b, 497123a, 85fd0d6, 3536270, bcf9a5c). Verify that each
commit encodes the doctrine described in `CLAUDE.md` / `AGENTS.md`, that the
rulebook stays internally consistent, and that the prompt + pipeline + schema
are not drifting from each other.

**Phase 2 (in progress).** Austin approved the 4-bug bundle ("yes fix all of
them"). Apply the four real-bug fixes in one rule-doc commit so the
reference-clock only resets once. Then run a no-backward-compat stale
doc/code cleanse to timeless-ify the rulebook. Extractions are already
deleted (`output/` does not exist) — Austin will re-run after the rule fixes
land.

Deploy a small team of clean-slate agents (per Austin's administrator-mode
preference): bug-fix agent → stale-cleanse agent → verifier agent →
atomic commits.

## Approach

1. List recent commits affecting `rules/`.
2. Read each commit diff scoped to `rules/`, `prompts/extract.md`, and
   the relevant `pipeline/` or `scoring/` neighbors.
3. Cross-check rule text against the doctrine paragraphs in `CLAUDE.md`.
4. Run text searches for naming consistency: enum values mentioned in
   schema vs. listed in prompt vs. used in `scoring/diff.py`.
5. Surface findings with severity (real bug vs. soft concern vs.
   cosmetic) and concrete fix suggestions.

## Key context

- The reference-set rulebook stability clock requires three consecutive
  unchanged-rulebook clean reference runs. Any rule fix from this review
  resets that clock.
- Doctrine intent is "rulebook is timeless" — strip iter tags, dated
  "policy revision" notes, and Saks/Petsmart/etc. migration prose.
- Pipeline boundary: Python validators are matrix/structural checks;
  the prompt/extractor owns filing-prose reading. Rules' "Boundary"
  clauses encode this split.

## Findings (high level)

Real bugs:
1. `below_market` enum exists in schema/events but is missing from
   prompt's drop-classification doctrine — orphan value.
2. Vague-group `Drop` "ambiguity flag" has no canonical code name.
3. `pipeline/core.py:_consortium_lifecycle_evidence_keys` excludes
   `Drop` rows from the witness set, but rules say "lifecycle row"
   without that exclusion — spec/code drift.

Soft concerns:
4. §P-D5 exemption lists `buyer_group_constituent OR consortium_drop_split`,
   but per §I1 split-Drops always carry both, so the OR is redundant.
5. §P-D7 boundary frames `target_other` as "narrow fallback" but it
   covers a broad common bucket (financing/certainty/antitrust/board).
6. Timeless-ification sweep is incomplete in `rules/dates.md`,
   `rules/invariants.md`, and `rules/schema.md`.
7. "Reference conversion" wording in §C2 reads awkwardly.

## Decisions and execution

Austin approved the bundled fix and the cleanse on 2026-04-28. Decisions:

- `below_market` survives as a distinct class. The fix is to teach the
  prompt about it; do not remove it from the schema.
- Tighten the rules-prose to match `pipeline.core._consortium_lifecycle_evidence_keys`
  (which deliberately excludes `Drop` rows from the witness set), not the
  other way around. A `Drop` row witnessing for itself would make §P-D5
  vacuous.
- Name the unnamed-group-drop ambiguity flag
  `drop_group_count_unspecified` (severity `soft`) so validators and the
  comparator can recognize it.
- Drop the redundant `or consortium_drop_split` from §P-D5 exemption #4
  since `buyer_group_constituent` is already universally required by §I1.

## Execution order

1. Bug-fix agent — focused, four edits in one bundle, one commit.
2. Stale-cleanse agent — strip date-stamped section tags, "Per Alex
   2026-04-27 directive" archeology, "pre-2026-04-27" historical asides,
   "Decision #4/#5/#6" tags, and dated empirical commentary. One commit.
3. Verifier agent — cross-check schema/events/invariants/prompt for enum
   and flag agreement; run `pytest`; confirm no stale references remain
   and `output/extractions/` does not exist.

User's uncommitted polish on AGENTS.md / CLAUDE.md / scoring/diff.py /
tests/test_diff.py stays untouched. They are independent in-progress work
on the comparator's bidder-label diagnostic (registry-aware match) and
matching tests.
