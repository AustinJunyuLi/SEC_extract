# AGENTS.md - M&A Takeover Auction Extraction Project

This is the live contract for Codex or any human working in this repo. Keep it
current when architecture, schema, state, or output contracts change.

## Purpose

This repo extracts SEC merger-filing Background sections into a relational
`deal_graph_v2` representation for M&A takeover-auction research. The research
target is informal bidding in corporate takeover auctions. SEC filing text is
ground truth. Alex's legacy workbook is calibration and review material, not an
oracle.

## Current Architecture

The live architecture is code-orchestrated direct `AsyncOpenAI` SDK calls to
the Responses streaming endpoint through the Linkflow/NewAPI-compatible
`OPENAI_BASE_URL`. Configure `OPENAI_BASE_URL`, `OPENAI_API_KEY`,
`EXTRACT_MODEL`, and optional reasoning-effort overrides in the shell or
`.env`. Do not commit secrets.

The provider emits strict structured claim payloads only:

```json
{
  "actor_claims": [],
  "event_claims": [],
  "bid_claims": [],
  "participation_count_claims": [],
  "actor_relation_claims": []
}
```

The extractor input includes paragraph-local `citation_units` derived from the
Background pages. The AI copies claim receipts from those citation-unit texts.
Python owns quote binding, source spans, canonical ids, claim dispositions,
coverage results, graph rows, graph validation, and review rows. The AI never
emits canonical ids, source offsets, `BidderID`, `T`, `bI`, `bF`,
admitted/dropout outcomes, coverage results, or projection rows.

The provider does emit `actor_class` on actor claims, limited to `financial`,
`strategic`, `mixed`, or `unknown`. Python stores it as canonical
`bidder_class`. Do not restore U.S./non-U.S., public/private, or old
`bidder_type`/`bid_note` fields.

There is no per-event-row canonical schema, no loose JSON fallback, no
provider branch that turns off structured output, no response-chain reuse, and
no secondary model correction path.

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
       project review rows
  -> output/audit/{slug}/runs/{run_id}/deal_graph.duckdb
  -> output/audit/{slug}/runs/{run_id}/deal_graph_v2.json
  -> output/extractions/{slug}.json
  -> output/review_rows/{slug}.jsonl
  -> output/review_csv/{slug}.csv
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

Alex-facing full event ledger:

```bash
python scripts/export_alex_event_ledger.py --scope all --output output/review_csv/alex_event_ledger_ref9_plus_targets5.csv
```

Reasoning defaults to `high`. Explicit `xhigh` is capped by
`LINKFLOW_XHIGH_MAX_WORKERS`.

## Source of Truth

- `data/filings/{slug}/pages.json` is factual ground truth.
- `rules/*.md` is the extractor-readable rulebook.
- `prompts/extract.md` is the provider prompt.
- `pipeline/deal_graph/` is the live canonical graph subsystem.
- `output/extractions/{slug}.json` is the latest portable graph snapshot.
- `output/review_csv/alex_event_ledger_ref9_plus_targets5.csv` is a generated
  human-review ledger for Alex. It is deterministic projection output, not
  canonical truth. Bid rows expose `bid_value`, `bid_value_lower`,
  `bid_value_upper`, and `bid_value_unit`; do not label aggregate values as
  per-share values in this projection.
- `reference/deal_details_Alex_2026.xlsx` and
  `reference/CollectionInstructions_Alex_2026.pdf` are calibration material
  only; they are not live extraction inputs or verification authorities.

## Evidence Requirements

Every claim must include `evidence_refs`. Each evidence ref has:

```json
{"citation_unit_id": "page_35_paragraph_4", "quote_text": "exact filing substring"}
```

`citation_unit_id` must be one of the paragraph-local `citation_units[]` ids in
the extractor input, and `quote_text` must be an exact substring of that unit's
text. Use multiple refs when support is separated across sentences,
paragraphs, or pages. The provider must not emit provider-level `quote_text` or
`quote_texts`. Target identity comes from the filing manifest and Python-owned
deal metadata; the provider does not emit a target-only actor claim. Python
binds evidence refs before canonicalization and creates source spans. Claims
with invalid refs are quarantined into review output. A claim with no valid refs
does not create canonical graph rows; a claim with at least one valid ref can
create a source-backed row while failed refs remain review issues.

Quotes must support the specific actor, event, bid, count, relation, date, and
value being claimed. Ambiguous facts stay low-confidence or unclaimed; do not
invent unsupported facts.

## Consortium Doctrine

Preserve the filing's bidding unit. A group actor can be a bidder unit when the
filing treats the group as the bidding party. Do not atomize group bids unless
the filing shows separate bidding conduct.

Member, support, financing, and rollover facts are source-backed
`actor_relation_claims`, not automatic bidder rows. Changing coalitions remain
time-aware actor-cycle facts. Do not make membership permanent without quote
support.

## State and Output Contracts

`state/progress.json` remains schema version `v1`. Per-run status values:

- `passed_clean`: trusted graph and review output; zero open review rows
- `needs_review`: trusted graph and review output; 1 to 10 open review rows
- `high_burden`: trusted graph and review output; more than 10 open review rows
- `failed_system`: runtime, schema, artifact, or graph-integrity failure
- `stale_after_failure`: prior trusted output remains, but the latest run failed

Reference verification is metadata, not a run status. `verified: true` may be
set by Austin or by agent filing-grounded verification only when
`quality_reports/reference_verification/{slug}.md` exists, cites the current
run, and concludes the deal is verified against the filing. An agent must not
mark a deal verified solely because the model output passes schema validation.
Current extraction artifacts must still be internally consistent and
mechanically grounded in filing pages.

`state/flags.jsonl` is append-only. Current-run flags match exact `run_id`.

## Reference and Target Gates

The nine reference slugs remain:

```text
providence-worcester, medivation, imprivata, zep, petsmart-inc,
penford, mac-gray, saks, stec
```

Target-deal extraction is release-gated, not open by default. A non-reference
selection requires current verified reference metadata, an accepted
`quality_reports/stability/target-release-proof.json`, and the explicit
`--release-targets` operator flag. The current trusted non-reference outputs
are the five target deals listed in `state/progress.json`.

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
