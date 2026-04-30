---
session: 2026-04-29 prod reference-batch re-extract at xhigh
branch: api-call
operator: Austin (executed by Claude in auto mode)
---

## Goal

Re-extract all 9 reference deals at `--extract-reasoning-effort xhigh` and
`--adjudicate-reasoning-effort xhigh`, throttled to 3 workers to ease API
pressure. Replaces the earlier 2026-04-29 high/xhigh run.

## Configuration

- `OPENAI_BASE_URL=https://www.linkflow.run/v1`
- `EXTRACT_MODEL=gpt-5.5`, `--extract-reasoning-effort xhigh`
- `ADJUDICATE_MODEL=gpt-5.5`, `--adjudicate-reasoning-effort xhigh`
- `--filter reference --workers 3 --re-extract`
- API key supplied inline via env (not committed); audit/log scrubbed for the key string.

## Pre-step

Deleted `output/extractions/{slug}.json` and `output/audit/{slug}/` for all 9
reference deals before launch. `output/` is gitignored, no git impact.

## Result

`Pool summary: selected=9 succeeded=9 skipped=0 failed=0`

| slug | status (xhigh) | total | hard | warn | info | soft | (was at high) |
|---|---|---:|---:|---:|---:|---:|---:|
| medivation | passed | 14 | 0 | 0 | 10 | 4 | 15 |
| imprivata | passed | 14 | 0 | 0 | 12 | 2 | 15 |
| penford | passed | 13 | 0 | 0 | 12 | 1 | 26 |
| stec | passed | 19 | 0 | 0 | 13 | 6 | 20 |
| saks | passed | 55 | 0 | 0 | 42 | 13 | 61 |
| **mac-gray** | **validated** | 67 | **1** | 0 | 48 | 18 | 47 (passed) |
| petsmart-inc | passed | 74 | 0 | 0 | 67 | 7 | 49 |
| **zep** | **passed** | 92 | **0** | 0 | 45 | 47 | 47 (validated, 1 hard) |
| providence-worcester | passed | 122 | 0 | 0 | 71 | 51 | 112 |

All 9 stamped with `rulebook_version=eaeb2c7d…`,
`extractor_contract_version=05ff4f6d…`, `api_endpoint=responses`,
`json_schema_used=false` (Linkflow prompt-only JSON).

## Cross-run delta

- **zep**: 1 hard flag at high → 0 hard flags at xhigh. The earlier
  `ca_type_ambiguous` on Party Y row was a cohort-counting symptom — the
  high extractor double-counted the 25-CA cohort by emitting an explicit
  Party Y NDA row alongside 24 unnamed placeholders + New Mountain. The
  xhigh extractor handled the cohort consistently with how it handled
  Party X (no separate NDA row for the named identity), so the count is
  now 25 = 24 unnamed + 1 New Mountain, with Party X and Party Y embedded
  in the 24 unnamed slots.
- **mac-gray**: 0 hard at high → 1 hard at xhigh
  (`final_round_missing_non_announcement_pair`, row idx 45). The high
  extractor missed a §P-G3 invariant: when a Final Round announcement has
  subsequent bids, a paired non-announcement Final Round row is required
  for the submission/deadline milestone. xhigh self-flagged the
  omission. mac-gray idx 45 (announcement, 2013-09-21) is followed by
  CSC/Pamplona's formal best-and-final at idx 46 (same day) without the
  required milestone row.

xhigh is more thorough about flagging soft/info ambiguities — total flag
counts shifted up on long deals (providence-worcester 112→122,
petsmart-inc 49→74, zep 47→92) and down on short deals (penford 26→13,
medivation 15→14, imprivata 15→14, saks 61→55, stec 20→19).

## SDK call profile

- 9 extract calls (xhigh), 9 scoped adjudicate calls (xhigh, all on
  providence-worcester for `missing_nda_dropsilent` soft flags).
- 19 total attempts (medivation extract took 2 attempts, succeeded; all
  others 1 attempt).
- 0 watchdog warnings.
- Extract latencies: 384–583s (vs 183–336s at high; ~1.6× slower as
  expected). Adjudicate latencies: 5–10s (scoped).
- Token totals: input 827,264 / output 469,259 / reasoning 266,012.

## Hard flag for Austin's review

**mac-gray, row idx 45 (BidderID 46), 2013-09-21**:
`final_round_missing_non_announcement_pair` (severity=hard).

Reason: §P-G3 — Final Round announcement has subsequent bids but no
process-level non-announcement Final Round row for the submission/deadline
milestone. The model emitted the announcement (idx 45,
`final_round_announcement: True, final_round_extension: True`) and the
bid response (idx 46, formal Bid by CSC/Pamplona) on the same day, but
skipped the milestone row that earlier rounds in the same deal got
correctly (idx 31→34, idx 37→42).

Resolution path is either:
1. Edit the JSON to add a non-announcement Final Round row for 09-21
   between idx 45 and idx 46.
2. Rulebook clarification: when announcement and bid land on the same
   day, the announcement row may stand in for both. This would soften
   the §P-G3 invariant and the rule edit must propagate to
   `pipeline/core.py` validators.

## AI-vs-Alex comparator

`python -m scoring.diff --all-reference --write` regenerated 9 markdown
reports under `scoring/results/`. Suppressions and cardinality patterns
match expectations for the current rulebook. Austin walks each report
manually; the comparator is a human-review aid, not a gate.

## Reference-set gate status

This is the second clean reference run. Per CLAUDE.md the gate requires
three consecutive clean full-reference runs against the same rulebook
plus manual filing-text verification of all nine deals. None of the deals
have advanced to `verified` yet. If the rulebook is touched (e.g., to
clarify §P-G3 or the named-vs-anonymous-CA-cohort rule), the
stability clock resets per the no-backward-compatibility doctrine.

## Artifacts

- `output/extractions/{slug}.json` (9 files; 81/25/29/69/59/38/64/42/37 events)
- `output/audit/{slug}/` (raw_response.json, manifest.json, calls.jsonl, prompts/*)
- `state/progress.json` (xhigh run_ids stamped)
- `state/flags.jsonl` (current-run rows appended; prior runs preserved)
- `quality_reports/runs/2026-04-29_reference-batch-xhigh.log`
- `scoring/results/{slug}.md|.json` (regenerated)

## Followups

1. Austin to adjudicate mac-gray row 45 (§P-G3 hard flag) against the
   filing — pick fix or rulebook clarification.
2. Austin to walk the nine `scoring/results/*.md` diffs and apply
   verdicts per `reference/alex/README.md`.
3. Decide whether to update `rules/bidders.md` with the named-vs-anonymous
   CA-cohort rule that zep surfaced (the high run double-counted; xhigh
   handled it correctly, but the rule remains implicit).
4. No commit was made — outputs are in the worktree for review.

## 2026-04-30 follow-up: blocked on chat-pasted API key

User asked for a single-deal run on `medivation` ("a code deal run") with
gpt-5.5 + reasoning effort `high`, providing the Linkflow API key inline
in the chat prompt. Plan was: `python run.py --slug medivation --re-extract
--extract-reasoning-effort high --adjudicate-reasoning-effort high` with
the key set as an inline env var (no `.env` write).

Sandbox blocked even `--print-prompt` on the grounds that chat-pasted
secrets aren't authorized for live API use. Did not attempt to bypass.
Told user to (a) rotate the leaked key, (b) drop the new key in `.env`
(gitignored, auto-loaded), (c) confirm scope (single medivation vs full
reference batch), then re-invoke.

No filings were fetched, no SDK calls were made, no state/output/audit
files were touched on this attempt. `state/progress.json` and
`state/flags.jsonl` are unchanged from the 2026-04-29 xhigh run.
