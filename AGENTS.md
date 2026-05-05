# AGENTS.md - M&A Takeover Auction Extraction Project

This is the live contract for Codex or any human working in this repo. Keep it
current when architecture, schema, state, or output contracts change.

## Purpose

This repo extracts SEC merger-filing Background sections into a relational
`deal_graph_v1` representation for M&A takeover-auction research. The research
target is informal bidding in corporate takeover auctions. SEC filing text is
ground truth. Alex's legacy workbook is calibration and review material, not an
oracle.

## Current Architecture

The live architecture is code-orchestrated direct `AsyncOpenAI` SDK calls to
the Responses streaming endpoint through the Linkflow/NewAPI-compatible
`OPENAI_BASE_URL`. Configure `OPENAI_BASE_URL`, `OPENAI_API_KEY`,
`EXTRACT_MODEL`, and optional reasoning-effort overrides in the shell or
`.env`. Do not commit secrets.

The provider emits strict structured `deal_graph_v1` claim payloads only:

```json
{
  "actor_claims": [],
  "event_claims": [],
  "bid_claims": [],
  "participation_count_claims": [],
  "actor_relation_claims": []
}
```

Python owns quote binding, source spans, canonical ids, claim dispositions,
coverage results, graph rows, graph validation, review rows, and estimator
bidder rows. The AI never emits canonical ids, source offsets, `BidderID`,
`T`, `bI`, `bF`, admitted/dropout outcomes, coverage results, or projection
rows.

There is no row-per-event canonical schema, no loose JSON fallback, no
provider branch that turns off structured output, no `previous_response_id`
chain, and no live repair/adjudicator path. Retired row-event helpers may
exist only as non-live legacy code until cleaned; they are not output authority.

Per deal:

```text
run.py / pipeline.run_pool
  -> Extractor SDK call with strict claim-only json_schema
  -> output/audit/{slug}/runs/{run_id}/raw_response.json
  -> pipeline.deal_graph.orchestrate.finalize_claim_payload()
       parse provider claims
       bind each quote to Background filing text
       canonicalize actors/events/relations/counts
       validate graph evidence/disposition/coverage
       project review and estimation rows only when unblocked
  -> output/audit/{slug}/runs/{run_id}/deal_graph.duckdb
  -> output/audit/{slug}/runs/{run_id}/deal_graph_v1.json
  -> output/extractions/{slug}.json
  -> output/review_rows/{slug}.jsonl
  -> output/review_csv/{slug}.csv
  -> output/projections/estimation_bidder_rows/{slug}.jsonl
  -> state/flags.jsonl and state/progress.json
```

## Entrypoints

Single deal:

```bash
python run.py --slug mac-gray --re-extract
python run.py --slug petsmart-inc --re-extract
python run.py --slug zep --re-extract
python run.py --slug mac-gray --print-prompt
```

Batch:

```bash
python -m pipeline.run_pool --filter reference --workers 1
python -m pipeline.run_pool --slugs mac-gray,petsmart-inc,zep --workers 3 --re-extract
```

Reasoning defaults to `high`. Explicit `xhigh` is capped by
`LINKFLOW_XHIGH_MAX_WORKERS`.

## Source of Truth

- `data/filings/{slug}/pages.json` is factual ground truth.
- `rules/*.md` is the extractor-readable rulebook.
- `prompts/extract.md` is the provider prompt.
- `pipeline/deal_graph/` is the live canonical graph subsystem.
- `output/extractions/{slug}.json` is the latest portable graph snapshot.
- `reference/alex/{slug}.json` is comparison material only.

## Evidence Requirements

Every claim must include exact `quote_text` and `quote_texts`. Use
`quote_texts: null` when the primary quote supports the claim; use an ordered
list of exact snippets when support is separated across sentences, paragraphs,
or page breaks, with the first entry equal to `quote_text`. Python binds quote
text to the Background pages and creates source spans. Claims or canonical rows
without source-backed evidence produce hard graph flags and do not support
projection.

Quotes must support the specific actor, event, bid, count, relation, date, and
value being claimed. Ambiguous facts stay low-confidence or unclaimed; do not
invent unsupported facts.

## Consortium Doctrine

Preserve the filing's bidding unit. A group actor can be a bidder and estimator
unit. Member relations are composition facts, not automatic bidder rows.

Mac Gray: `CSC/Pamplona` is one group actor and one bidder unit when the filing
treats it that way. CSC and Pamplona are represented through source-backed
relations. Pamplona financing is not a separate bidder row by itself.

PetSmart: `Buyer Group` is a group actor and bidder unit. Longview membership,
rollover, voting support, or financing is dated only when the filing supports
the timing and does not atomize the Buyer Group bid.

Changing coalitions remain time-aware actor-cycle facts. Do not make
membership permanent without quote support.

## State and Output Contracts

`state/progress.json` remains schema version `v1`. Status values:

- `pending`
- `validated`: finalized with hard graph flags
- `passed`: finalized with only soft/info graph flags
- `passed_clean`: finalized with no graph flags
- `verified`: filing-grounded reference verification completed
- `failed`: runtime failure without a valid finalized output

During reference work, `verified` may be set by Austin or by agent filing-grounded verification only when `quality_reports/reference_verification/{slug}.md` exists and concludes the deal is verified against the filing. An agent must not mark a deal verified solely because the model output passes schema validation.

`state/flags.jsonl` is append-only. Current-run flags match exact `run_id`.

## Reference and Target Gates

The nine reference slugs remain:

```text
providence-worcester, medivation, imprivata, zep, petsmart-inc,
penford, mac-gray, saks, stec
```

Target-deal extraction remains fail-closed until the reference set is
re-established under `deal_graph_v1` and a target-release stability proof is
accepted. Fetching or inspecting target metadata is allowed only when Austin
explicitly asks and it does not start extraction.

## No Backward Compatibility Doctrine

Do not preserve old formats. When the schema, prompt, rulebook, state, output,
file layout, or orchestration changes, update live contracts in the same
change, regenerate or delete stale artifacts, and fail loudly on stale inputs.
Do not add compatibility shims, deprecated aliases, fallback readers, or docs
that describe old and current behavior as simultaneously live.

## Working Rules

- Read `AGENTS.md` and `SKILL.md` before changing extraction behavior.
- Edit only files needed for the task.
- Do not revert user edits or unrelated worktree changes.
- Keep secrets in runtime environment only.
- Use filing text as ground truth.
- Before adding a new rule file or model role, state the specific failure it
  fixes.
