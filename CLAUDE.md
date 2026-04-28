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

The live architecture is code-orchestrated direct SDK calls through an
OpenAI-compatible provider. Configure it with `OPENAI_BASE_URL` and
`OPENAI_API_KEY`; model names come from `EXTRACT_MODEL` and
`ADJUDICATE_MODEL` or CLI overrides.

Per deal:

```text
seeds.csv / state/progress.json
  -> run.py or pipeline.run_pool
  -> Extractor SDK call
  -> output/audit/{slug}/ raw response, prompts, call metadata
  -> pipeline.core.prepare_for_validate()
  -> pipeline.core.validate()
  -> optional scoped Adjudicator SDK call for soft flags
  -> pipeline.core.finalize_prepared()
  -> output/extractions/{slug}.json
  -> state/flags.jsonl
  -> state/progress.json
  -> scoring/diff.py for reference deals
```

There is no active external agent loop, manually routed deal workflow, or
top-level pipeline script. Add another model call or orchestration layer only
when current reference-deal evidence shows this direct Extractor + Python
validator + scoped Adjudicator design is insufficient.

## Entrypoints

Single deal:

```bash
python run.py --slug medivation --extract
python run.py --slug medivation --re-validate
python run.py --slug medivation --re-extract
python run.py --slug medivation --print-prompt
```

Batch:

```bash
python -m pipeline.run_pool --filter reference --workers 1
python -m pipeline.run_pool --slugs medivation,imprivata --workers 2
```

Use `--dry-run` to inspect selection without requiring an API key. Use
`--re-validate` to reuse `output/audit/{slug}/raw_response.json` only when its
`rulebook_version` matches the current rulebook. Use `--re-extract` or
`--force` for a fresh SDK extraction.

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

Key conventions:

- `BidderID` is a strict event-sequence number, not a persistent bidder entity.
- Bid rows use the unified current schema: `bid_note = "Bid"` and `bid_type`
  carries informal/formal classification.
- `bidder_type` is `"s"`, `"f"`, or `null`.
- Deal identity fields preserve filing-verbatim casing and punctuation.
- Communication-date anchoring follows `rules/dates.md`.
- Post-execution sale press releases are folded into `Executed`.
- Unnamed parties follow the minimum-supported-count rule in `rules/bidders.md`.

## State and Output Contracts

`state/progress.json` has `schema_version: "v1"` and a `deals` object keyed by
slug. Status values are:

- `pending`: not yet run.
- `validated`: finalized with at least one hard flag.
- `passed`: finalized with only soft/info flags.
- `passed_clean`: finalized with zero flags.
- `verified`: Austin manually verified a reference deal against the filing.
- `failed`: pipeline error.

Per-deal progress entries carry `flag_count`, `last_run`, verification fields,
`notes`, `rulebook_version`, and bounded `rulebook_version_history`. There is no
repo-level global rulebook pin.

`state/flags.jsonl` is append-only. Each finalize appends current-run flags with
the same `logged_at` timestamp used for `deals[slug].last_run`. Older flags stay
on disk as history.

`output/extractions/{slug}.json` is the authoritative latest extraction for a
deal. It must conform to `rules/schema.md` and include pipeline-stamped
`rulebook_version`, `last_run`, row flags, and deal flags.

`output/audit/{slug}/` is the audit cache:

- `raw_response.json`: raw model text, parsed JSON, model, slug, and
  `rulebook_version`.
- `prompts/*.txt`: exact SDK prompts.
- `calls.jsonl`: model-call metadata, token usage, retries, watchdog data.
- `manifest.json`: run summary and cache outcome.

Audit artifacts exist for reproducibility and re-validation. They are not a
second source of truth after finalization.

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
invariants pass, and the rulebook remains unchanged across three consecutive
clean full-reference runs. Any rulebook, prompt, schema, state, or output-format
change resets that clock.

Open current adjudication item: NDA atomization vs aggregation on `zep`,
`mac-gray`, `providence-worcester`, and `petsmart-inc`. Current `rules/bidders.md`
atomizes unless the filing narrates consortium activity. Austin must decide per
deal whether to tighten the rule or regenerate the reference JSON.

## Target-Deal Gate

Do not run extraction on the non-reference target deals until the reference-set
gate is met. The 392 target deals are closed to batch processing until Austin
has verified all nine reference deals and the rulebook stability clock is
satisfied.

Fetching or inspecting target metadata is acceptable only when Austin explicitly
asks and it does not start extraction.

## Repo Layout

| Path | Contract |
|---|---|
| `AGENTS.md` | Same live contract for Codex-oriented sessions. |
| `CLAUDE.md` | This live contract for Claude-oriented sessions. |
| `SKILL.md` | Detailed extraction skill and invocation contract. |
| `.env.example` | Environment variable names, never real secrets. |
| `seeds.csv` | Candidate deals and reference flags. |
| `data/filings/{slug}/` | Downloaded filing artifacts: `manifest.json`, `pages.json`, `raw.md`, `raw.htm`. |
| `prompts/extract.md` | Extractor prompt included in SDK system messages. |
| `rules/*.md` | Schema, event vocabulary, bidder/bid/date rules, invariants. |
| `pipeline/core.py` | Filing loader, preparation, validator, finalizer, state writers. |
| `pipeline/llm/` | SDK client, extraction, adjudication, response format, retry, watchdog, audit. |
| `pipeline/run_pool.py` | Async batch runner, selection, cache policy, SDK orchestration. |
| `run.py` | Single-deal CLI wrapper over `pipeline.run_pool`. |
| `scoring/diff.py` | AI-vs-Alex comparison for human review. |
| `reference/alex/` | Converted reference JSONs and Alex self-flag metadata. |
| `state/progress.json` | Live status ledger. |
| `state/flags.jsonl` | Append-only validator/adjudicator flag log. |
| `output/extractions/` | Finalized per-deal AI extractions. |
| `output/audit/` | Prompt, raw-response, and call audit cache. |
| `scripts/fetch_filings.py` | Filing fetcher. |
| `scripts/build_reference.py` | Reference JSON builder with documented Alex-workbook overrides. |
| `tests/` | Runtime, prompt, LLM wrapper, converter, diff, and invariant tests. |

Generated reports, one-off migration scripts, obsolete working notes, and stale
logs are not live contracts.

## No Backward Compatibility Doctrine

This repo deliberately does not preserve old formats or retired architecture.
When a schema, prompt contract, rule, state format, output format, file layout,
or orchestration path changes:

- Update the live contract files in the same change.
- Regenerate affected reference/output/state/audit artifacts or delete them.
- Delete stale code, stale docs, old reports, old fixtures, and migration
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
