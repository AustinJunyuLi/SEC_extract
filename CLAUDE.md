# CLAUDE.md - M&A Takeover Auction Extraction Project

> Live contract for Claude or any human working in the folder you selected.
> Keep this file current when the architecture, schema, rulebook, state
> format, or output contract changes.

## Purpose

This repo extracts the "Background of the Merger" section from SEC merger
filings (DEFM14A, PREM14A, SC-TO-T, S-4) into one JSON row per auction event
for Alex Gorbenko's M&A takeover auction research.

The research target is informal bidding in corporate takeover auctions. Alex's
legacy workbook is useful calibration data, but it is not ground truth. The SEC
filing text is ground truth. Austin adjudicates AI-vs-Alex disagreements by
reading the filing, then updates the rulebook or reference JSONs as needed.

## Current Architecture

The live architecture is code-orchestrated direct `AsyncOpenAI` SDK calls to
the Responses streaming endpoint (`responses.stream`) through the
Linkflow/NewAPI-compatible `OPENAI_BASE_URL`. Configure it with
`OPENAI_BASE_URL` and `OPENAI_API_KEY`; model names come from `EXTRACT_MODEL`
and `ADJUDICATE_MODEL` or CLI overrides.

Every extractor call uses **strict `text.format=json_schema`** with the
hardened `SCHEMA_R1`, plus three native function-calling tools available to
the model during drafting:

- `check_row(row)` — row-local validator wrapper (§P-R0..R9 + §P-D1/D2/D7 +
  §P-G2).
- `search_filing(query, page_range, max_hits)` — substring search over filing
  pages.
- `get_pages(start_page, end_page)` — contiguous page fetch (cap = 10 pages
  per call).

After the model emits its final extraction, Python `pipeline.core.validate()`
runs. If hard flags remain, an outer **repair loop** (cap = 2 turns) sends the
validator report back and asks for a complete revised extraction. On cap-hit,
finalization records a `repair_loop_exhausted` deal-level hard flag and the
deal status is `validated`.

The scoped Adjudicator stays single-turn, no tools, soft-flag verdicts only.

There is no free-form JSON fallback. There is no provider branch that turns off
structured output. There is no `previous_response_id` chain (Linkflow returns 400).
Streaming is used for every full-extraction turn; non-streaming for short
tool-call turns to avoid the SDK accumulator empty-output bug.

Phase 1 Linkflow probes accepted the live `SCHEMA_R1` only after keeping the
provider schema strict-but-not-maximalist: no `oneOf` event variants and no
dynamic `bidder_registry` enforcement in the provider payload. Those remain
live Python contract duties; the pipeline rebuilds and enforces
`bidder_registry` before validation/finalization, and the validator/tooling
enforce conditional row semantics.

Per deal:

```text
seeds.csv / state/progress.json
  -> run.py or pipeline.run_pool
  -> Extractor SDK call (strict json_schema + tools)
       parallel function_call → tool dispatch → function_call_output replay
       repeat until model emits final {deal, events}
  -> output/audit/{slug}/runs/{run_id}/ immutable raw response, prompts, tool_calls.jsonl
  -> pipeline.core.prepare_for_validate()
  -> pipeline.core.validate()
  -> if hard flags: repair turn (≤ 2 iterations)
       compact validator report + affected rows + filing snippets sent back
       model emits complete revised extraction
       Python validates again
       on cap-hit: finalize latest draft + repair_loop_exhausted flag
  -> repair_turns.jsonl entry per repair turn
  -> optional scoped Adjudicator SDK call for soft flags
  -> pipeline.core.finalize_prepared()
  -> output/extractions/{slug}.json
  -> state/flags.jsonl
  -> state/progress.json
  -> scoring/diff.py for reference deals
```

There is no active external agent loop, manually routed deal workflow, or
top-level pipeline script. Add another model role or orchestration layer only
when current reference-deal evidence shows this strict Extractor + tools +
Python validator/repair + scoped Adjudicator design is insufficient.

## Entrypoints

Single deal:

```bash
python run.py --slug medivation --extract
python run.py --slug medivation --re-validate
python run.py --slug medivation --re-extract
python run.py --slug medivation --print-prompt
python run.py --slug medivation --re-validate --audit-run-id <run_id>
```

Batch:

```bash
python -m pipeline.run_pool --filter reference --workers 1
python -m pipeline.run_pool --slugs medivation,imprivata --workers 2
```

Use `--dry-run` to inspect selection without requiring an API key. Use
`--re-validate` to reuse only a cache-eligible archived v2 audit run. By
default `--re-validate` reads `output/audit/{slug}/latest.json`; use
`--audit-run-id <run_id>` to revalidate an exact archived run under
`output/audit/{slug}/runs/{run_id}/`. The archived raw response must match the
current `rulebook_version`, `extractor_contract_version`,
`tools_contract_version`, and `repair_loop_contract_version`. Loose legacy
files directly under `output/audit/{slug}/` are stale and are not accepted as
cache. Use `--re-extract` for a fresh SDK extraction.

Reasoning effort defaults to `xhigh` for both extractor and adjudicator calls:

```bash
python run.py --slug medivation --extract --extract-reasoning-effort xhigh
python -m pipeline.run_pool --filter reference --workers 5 --extract-reasoning-effort xhigh
```

The empirical Linkflow ceiling for `xhigh` is five concurrent workers. The
runner rejects `xhigh` with more than `LINKFLOW_XHIGH_MAX_WORKERS` workers
(default `5`) before making API calls.

There is no per-deal token-budget cap. The runner records input, output, and
reasoning token usage in audit metadata, but it does not skip adjudication or
abort a deal because a token total is high. If a soft flag needs adjudication,
the scoped Adjudicator is allowed to run; cost control belongs in worker
concurrency and model-effort choices, not hidden per-deal truncation.

If a CLI supports `--commit`, it must commit only current-deal
output/state/audit paths and leave unrelated worktree changes alone.

## Source of Truth

- Filing text in `data/filings/{slug}/pages.json` is factual ground truth.
- `rules/*.md` is the extraction rulebook. Every durable rule decision belongs
  there, not in chat or generated reports.
- `rules/schema.md` is the output schema contract.
- `rules/events.md`, `rules/bidders.md`, `rules/bids.md`, and
  `rules/dates.md` are extractor-readable rule files.
- `rules/invariants.md` is validator-facing. The extractor can be warned about
  invariant codes, but deterministic checks live in Python.
- `prompts/extract.md` is the extractor prompt included in SDK system messages.
- `SKILL.md` is the detailed extraction skill contract. Update it with this file
  when architecture or invocation semantics change.
- `state/progress.json` is the live per-deal status ledger.
- `output/extractions/{slug}.json` is the latest finalized AI extraction.
- `reference/alex/{slug}.json` is the converted reference comparison target,
  not an oracle.
- `scoring/diff.py` is a human-review diff aid, not a grading gate.

Alex's PDF in `reference/CollectionInstructions_Alex_2026.pdf` is
authoritative on the collection rules. Where the PDF, rulebook, and reference
JSON disagree, resolve against the filing and document the rule decision in
`rules/`.

## Evidence Requirements

Every extracted event row must include:

- `source_quote`: a filing-text quote that supports the row.
- `source_page`: the page number from `pages.json`.

Rows without evidence do not ship. Quotes must support the specific event, date,
bidder, bid value, and classification being emitted. If the filing is ambiguous,
emit the supported row and flag the ambiguity; do not invent uncited facts.
Quote strings target and hard-fail at 1500 characters; there is no soft
over-target zone. Use `source_quote` / `source_page` lists for separated
snippets, including separated snippets on the same page.

Key conventions:

- `BidderID` is a strict event-sequence number, not a persistent bidder entity.
- Bid rows use the unified current schema: `bid_note = "Bid"` and `bid_type`
  carries informal/formal classification.
- `bidder_type` is `"s"`, `"f"`, or `null`.
- Deal identity fields preserve filing-verbatim casing and punctuation.
- Communication-date anchoring follows `rules/dates.md`.
- Post-execution sale press releases are folded into `Executed`.
- Unnamed parties follow the minimum-supported-count rule in `rules/bidders.md`.
- Exact-count unnamed NDA placeholders are deal-local lifecycle handles; later
  unnamed bids, drops, DropSilent rows, or executions for the same cohort reuse
  those aliases unless an explicit ambiguity flag explains a genuinely unclear
  cohort boundary.
- `ConsortiumCA.bidder_alias` names the actor represented by `bidder_name`, not
  the buyer-group relationship phrase; relationship language belongs in
  `source_quote` and, when useful, `additional_note`.
- A non-announcement `Final Round` row is a process-level milestone. One row
  may support multiple same-round bids when the filing describes one shared
  deadline, submission event, or outcome.

## State and Output Contracts

`state/progress.json` has `schema_version: "v1"` and a `deals` object keyed by
slug. Status values are:

- `pending`: not yet run.
- `validated`: finalized with at least one hard flag.
- `passed`: finalized with only soft/info flags.
- `passed_clean`: finalized with zero flags.
- `verified`: Austin manually verified a reference deal against the filing.
- `failed`: pipeline error when there is no prior successful live extraction.
  A failed fresh rerun of a deal already in `validated`, `passed`,
  `passed_clean`, or `verified` preserves the prior live progress state and
  records the failed attempt in audit metadata instead of clobbering the last
  good status.

`validated` is a finalized status but not a completed/success status. It does
not count toward the reference exit gate and is not skipped by runner
freshness logic; hard-flagged deals need rerun or human rule/output work.

Per-deal progress entries carry `flag_count`, `last_run`, `last_run_id`,
verification fields, `notes`, `rulebook_version`, and bounded
`rulebook_version_history` entries of `{ts, run_id, version}`. There is no
repo-level global rulebook pin.

`state/flags.jsonl` is append-only. Each finalize appends current-run flags with
the same `logged_at` timestamp used for `deals[slug].last_run` and the same
`run_id` used for `deals[slug].last_run_id`. Older flags stay on disk as
history; current-run queries use exact `run_id == last_run_id` or exact
`logged_at == last_run`, never timestamp ranges.

`output/extractions/{slug}.json` is the authoritative latest extraction for a
deal. It must conform to `rules/schema.md` and include pipeline-stamped
`rulebook_version`, `last_run`, `last_run_id`, row flags, and deal flags.

`output/audit/{slug}/` is the audit archive. The only mutable file is
`latest.json`; every extraction or re-validation attempt writes a new immutable
run directory:

```text
output/audit/{slug}/runs/{run_id}/
  manifest.json
  calls.jsonl
  tool_calls.jsonl
  repair_turns.jsonl
  raw_response.json
  validation.json
  final_output.json
  prompts/
    extractor.txt
    adjudicator_{n}.txt

output/audit/{slug}/latest.json
```

Fresh runs never delete or overwrite older run directories. Failed fresh runs
still write a run manifest and update `latest.json` with
`cache_eligible=false`. Re-validation copies the selected archived raw response
into the new run directory and records `cache_used=true` /
`source_audit_run_id`. Cache eligibility requires the current rulebook pin plus
extractor, tools, and repair-loop contract versions to match the archived run.
`final_output.json` is the immutable per-run finalized snapshot used by
stability tooling; `output/extractions/{slug}.json` remains the authoritative
latest extraction.

## API Key and Environment Safety

Use `.env` or shell environment variables for secrets. `.env.example` documents
the required names, but real API keys must not be committed, pasted into docs,
or copied into reports. `OPENAI_API_KEY` is required for real SDK calls and is
not required for `--dry-run`.

SDK prompts and audit files may contain filing text and model output; treat them
as research artifacts. They must never contain API keys. If a log or audit file
accidentally captures a secret, stop and rotate the key before continuing.

## Reference-Set Gate

The nine reference deals are:

| Deal slug | Target | Rows | Archetype |
|---|---|---:|---|
| `providence-worcester` | Providence & Worcester | 6024-6059 | English auction; CVR; rough dates |
| `medivation` | Medivation | 6060-6075 | Simple bidder sale; press release |
| `imprivata` | Imprivata | 6076-6104 | Bidder interest to bidder sale; drops |
| `zep` | Zep | 6385-6407 | Terminated and restarted processes |
| `petsmart-inc` | Petsmart | 6408-6457 | Activist sale; consortium winner; many NDAs |
| `penford` | Penford | 6461-6485 | Stale prior attempts; near-single-bidder endgame |
| `mac-gray` | Mac Gray | 6927-6960 | Banker termination/rehire; target drops high formal bid |
| `saks` | Saks | 6996-7020 | Alex delete flags; go-shop |
| `stec` | STec | 7144-7171 | Multiple pre-IB bidder interests; single-bound informals |

Reference-set work is complete only when all nine deals are manually verified
against the filings, every AI-vs-Alex disagreement is adjudicated, hard
invariants pass, and the stability harness produces a `target_gate_proof_v1`
classifying the archive as `STABLE_FOR_REFERENCE_REVIEW` across at least three
archived reference runs per slug under unchanged prompt/schema/rulebook hashes.
Any rulebook, prompt, schema, state, or output-format change resets that clock.

Behavior-specific extraction doctrine lives in `rules/*.md`, with validator
checks in `rules/invariants.md` and `pipeline/core.py`. AI-vs-Alex comparison
suppression lives in `scoring/diff.py`. Do not restate those doctrines in this
high-level operating file; point future readers to the owning rule or comparator
section instead.

## Target-Deal Gate

Do not run extraction on the non-reference target deals until the reference-set
gate is met. The runner enforces this fail-closed: any selection containing a
target deal fails before audit directories, SDK clients, or model calls unless
all nine reference deals are `verified`, a `target_gate_proof_v1` stability
proof classifies the reference archive as `STABLE_FOR_REFERENCE_REVIEW`,
records `requested_runs >= 3`, and includes at least three selected immutable
run IDs for every reference slug, and the operator supplies
`--release-targets`. The 392 target deals are closed to batch processing until
Austin has verified all nine reference deals and the rulebook stability clock
is satisfied.

Fetching or inspecting target metadata is acceptable only when Austin explicitly
asks and it does not start extraction.

The proof file is produced by `python -m pipeline.stability --scope reference
--runs 3 --json --write quality_reports/stability/target-release-proof.json`.
Archive consistency is checked by `python -m pipeline.reconcile --scope
reference`. Both are read-only. The full operator protocol lives in
`docs/linkflow-extraction-guide.md`.

## Repo Layout

| Path | Contract |
|---|---|
| `AGENTS.md` | Same live contract for Codex-oriented sessions. |
| `CLAUDE.md` | This live contract for Claude-oriented sessions. |
| `SKILL.md` | Detailed extraction skill and invocation contract. |
| `.env.example` | Environment variable names, never real secrets. |
| `seeds.csv` | Candidate deals and reference flags. |
| `data/filings/{slug}/` | Downloaded filing artifacts: `manifest.json`, `pages.json`, `raw.md`, `raw.htm`. |
| `docs/linkflow-extraction-guide.md` | Linkflow-specific extraction operating guide. |
| `prompts/extract.md` | Extractor prompt included in SDK system messages. |
| `rules/*.md` | Schema, event vocabulary, bidder/bid/date rules, invariants. |
| `pipeline/core.py` | Filing loader, preparation, validator, finalizer, state writers. |
| `pipeline/llm/` | SDK client, extraction, tools, repair loop, adjudication, response format, retry, watchdog, audit. |
| `pipeline/run_pool.py` | Async batch runner, selection, cache policy, SDK orchestration. |
| `pipeline/reconcile.py` | Read-only progress / output / flags / audit reconciliation. |
| `pipeline/stability.py` | Read-only stability harness producing `target_gate_proof_v1`. |
| `run.py` | Single-deal CLI wrapper over `pipeline.run_pool`. |
| `scoring/diff.py` | AI-vs-Alex comparison for human review. |
| `reference/alex/` | Converted reference JSONs and Alex self-flag metadata. |
| `state/progress.json` | Live status ledger. |
| `state/flags.jsonl` | Append-only validator/adjudicator flag log. |
| `output/extractions/` | Finalized per-deal AI extractions. |
| `output/audit/` | Immutable audit v2 run archive plus mutable latest pointer. |
| `scripts/fetch_filings.py` | Filing fetcher. |
| `scripts/build_reference.py` | Reference JSON builder with documented Alex-workbook overrides. |
| `scripts/render_review_csv.py` | Pure projection from finalized extraction JSON to Alex-facing review CSV. |
| `scripts/smoke_linkflow.py` | Optional real-key Linkflow Responses smoke test. |
| `tests/` | Runtime, prompt, LLM wrapper, converter, diff, and invariant tests. |

Generated reports, one-off conversion helpers, obsolete working notes, and
stale logs are not live contracts.

## No Backward Compatibility Doctrine

This repo deliberately does not preserve old formats or retired architecture.
When a schema, prompt contract, rule, state format, output format, file layout,
or orchestration path changes:

- Update the live contract files in the same change.
- Regenerate affected reference/output/state/audit artifacts or delete them.
- Delete stale code, stale docs, old reports, old fixtures, and transition
  helpers once the live format is established.
- Fail loudly on stale inputs instead of silently reading old formats.
- Do not add compatibility shims, deprecated aliases, fallback readers, or docs
  that describe old and current behavior as simultaneously supported.
- Use git history as the compatibility record.

After every refactor, deep-clean the repo. Search for retired command names,
retired labels, old paths, obsolete architecture prose, stale generated reports,
and dead code. If a file no longer represents the current live contract, delete
it or rewrite it immediately. Do not leave archaeological artifacts in the
working tree to "help future agents."

## Working Rules

- Read this file and `SKILL.md` before changing extraction behavior.
- Edit only files needed for the requested task.
- Do not revert user edits or unrelated worktree changes.
- Commit only when the task calls for a finished repo state, branch
  preservation, or publishing; otherwise leave changes for Austin to review.
- Use the folder you selected when referring to paths in user-facing prose.
- Be skeptical: cite rows, check dates, and adjudicate against filing text.
- Reset model context per deal; persistent state belongs in `rules/`, `state/`,
  `output/`, `reference/alex/`, and audit files.
- Before adding a new rule file or model role, state the specific failure it
  fixes. If that assumption is unclear, do not add it.
