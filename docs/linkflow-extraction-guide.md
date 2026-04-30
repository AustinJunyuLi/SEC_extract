# Linkflow Extraction Guide

This note records the Linkflow-specific operating contract for the direct SDK
path. It is a transport/config guide, not a run log or rulebook. If the
Linkflow path changes, update this file in the same change.

## Working Shape

The stable Linkflow shape is:

```text
one deal
  -> direct AsyncOpenAI client
  -> Responses streaming endpoint
  -> prompt-only JSON
  -> Background-section slice only
  -> Python schema/contract checks after the model call
```

Use this environment shape:

```bash
OPENAI_BASE_URL=https://www.linkflow.run/v1
EXTRACT_MODEL=gpt-5.5
ADJUDICATE_MODEL=gpt-5.5
EXTRACT_REASONING_EFFORT=xhigh
ADJUDICATE_REASONING_EFFORT=xhigh
LINKFLOW_XHIGH_MAX_WORKERS=5
```

Xhigh reasoning is the default extraction setting. Override it only when
running an explicit model-effort experiment:

```bash
python -m pipeline.run_pool \
  --slugs penford \
  --workers 1 \
  --extract-model gpt-5.5 \
  --adjudicate-model gpt-5.5 \
  --extract-reasoning-effort xhigh \
  --adjudicate-reasoning-effort xhigh \
  --re-extract
```

The audit should show:

- `api_endpoint: "responses"` in
  `output/audit/{slug}/runs/{run_id}/manifest.json`.
- `json_schema_used=false` in
  `output/audit/{slug}/runs/{run_id}/calls.jsonl` for Linkflow.
- `finish_reason` equivalent to completed, no timeout error, and no repeated
  5xx retry loop.
- Token usage recorded for input, output, and reasoning tokens when the
  provider returns those fields.
- No per-deal token-budget cap. Token totals are audit facts, not a reason to
  skip adjudication or abort an otherwise valid run.

## Why This Works

Streaming matters. Large SEC extraction prompts plus high reasoning can take
longer than a proxy's non-streaming read window. The Responses streaming path
keeps the connection active while the model is working and producing output.

Prompt-only JSON matters on Linkflow. Linkflow/NewAPI-compatible providers may
not handle strict OpenAI structured-output payloads the same way OpenAI's native
endpoint does. The current client therefore disables structured output for
Linkflow and lets Python enforce the live contract after parsing. This is a
transport choice, not a relaxed local schema.

Section slicing matters. The extractor should receive the isolated Background
section with original page numbers, not the full filing and not table-of-
contents/cross-reference pages. This reduces latency, proxy exposure, and quote
verification noise.

Python validation matters. Linkflow should only do the extraction and scoped
adjudication. The repo owns schema enforcement, stale-field rejection, source
quote checks, date/BidderID checks, and finalization.

## What Makes Linkflow Shaky

Avoid these patterns:

- Non-streaming Chat Completions for large high-reasoning extraction prompts.
  This is the easiest way to hit proxy timeout behavior.
- Large Responses calls with strict `json_schema` / `text.format` payloads.
  This combination was observed to be brittle through Linkflow.
- Runtime schema probes before the real extraction. They add a paid request and
  do not prove the full extraction payload will work.
- JSON repair model calls after malformed output. They hide the real failure,
  burn tokens, and make the audit harder to reason about.
- Full-filing prompts. Sending the entire filing increases prompt size and
  makes table-of-contents hits, cross references, and timeout risk worse.
- Low `max_output_tokens` caps on extractor calls. Truncated JSON is worse than
  an explicit failure. The extractor path should normally leave the cap unset.
- Per-deal token-budget caps. They hide the exact soft flags that need
  adjudication and make high-complexity deals look cleaner than they are.
- Worker counts above the tested provider ceiling. `xhigh` is capped at five
  concurrent workers by default; the runner rejects larger `xhigh` pools before
  making API calls.
- Changing reasoning efforts before testing. `xhigh` is the default for `gpt-5.5`
  in this repo; do not leave reasoning effort unset for real extraction. Do not assume every
  proxy accepts every OpenAI reasoning-effort value.
- Stale cached raw responses after prompt, schema, rulebook, or section-slicing
  changes. `--re-validate` is only valid for cache-eligible audit v2 archives
  whose `rulebook_version`, `extractor_contract_version`, and raw-response
  shape are current. Use `--audit-run-id <run_id>` to select a specific
  archived run, and `--re-extract` otherwise.

## Output Contract Discipline

Because Linkflow runs prompt-only JSON, stale fields must not ship locally.
The extractor's `deal` object must contain only current AI-produced fields:

- `TargetName`
- `Acquirer`
- `DateAnnounced`
- `DateEffective`
- `auction`
- `all_cash`
- `target_legal_counsel`
- `acquirer_legal_counsel`
- `bidder_registry`
- `deal_flags`

Do not emit `slug`, `FormType`, `URL`, `DateFiled`, `CIK`, `accession`,
`rulebook_version`, `last_run`, or `last_run_id`. Those are manifest,
orchestration, or finalization fields. Missing current deal fields hard-fail.
Unexpected deal fields hard-fail locally; they are not stripped, repaired, or
allowed to ship as live output.

Every event row still needs exact `source_quote` and `source_page`. Quotes must
be verbatim slices from the embedded Background pages, one paragraph at most,
targeted at no longer than 1500 characters per quote string. There is no soft
over-target zone; above 1500 characters is a hard validator flag.

Audit v2 uses immutable run directories. Fresh runs do not clear or overwrite
older `calls.jsonl`, prompt files, or `raw_response.json`; they write a new
directory under `output/audit/{slug}/runs/{run_id}/` and update only
`output/audit/{slug}/latest.json`. A failed fresh rerun preserves any prior
successful live progress state and records the failure in the new audit
manifest with `cache_eligible=false`, so an older raw response cannot be
silently reused. Cached raw responses carry an `extractor_contract_version`
hash covering `prompts/extract.md` and the local `SCHEMA_R1` mirror, so
prompt/schema-only changes fail loudly instead of reusing old model JSON.

Loose legacy files directly under `output/audit/{slug}/` are stale artifacts,
not cache candidates. Delete or archive them after regeneration; do not add
fallback readers.

Behavioral extraction doctrine lives in `rules/*.md`; comparison behavior lives
in `scoring/diff.py`. Keep this guide focused on Linkflow transport behavior
and local contract enforcement.

## Operator Checklist

Before a real Linkflow run:

```bash
python -m pipeline.run_pool --filter reference --workers 4 --dry-run
python -m pytest -x
```

For a first real run on a reference deal:

```bash
python -m pipeline.run_pool \
  --slugs medivation \
  --workers 1 \
  --extract-model gpt-5.5 \
  --adjudicate-model gpt-5.5 \
  --extract-reasoning-effort xhigh \
  --adjudicate-reasoning-effort xhigh \
  --re-extract
```

After the run:

```bash
python scoring/diff.py --slug medivation
```

Then inspect:

- `output/audit/{slug}/latest.json`
- `output/audit/{slug}/runs/{run_id}/manifest.json`
- `output/audit/{slug}/runs/{run_id}/calls.jsonl`
- `output/audit/{slug}/runs/{run_id}/raw_response.json`
- `output/audit/{slug}/runs/{run_id}/validation.json`
- `output/audit/{slug}/runs/{run_id}/final_output.json`
- `output/extractions/{slug}.json`
- `state/progress.json`
- `state/flags.jsonl`

Reference-run protocol after this redesign:

```bash
python -m pytest -x
python -m pipeline.run_pool --filter reference --workers 4 --dry-run
python -m pipeline.run_pool \
  --filter reference \
  --workers 4 \
  --extract-model gpt-5.5 \
  --adjudicate-model gpt-5.5 \
  --extract-reasoning-effort xhigh \
  --adjudicate-reasoning-effort xhigh \
  --re-extract
python -m pipeline.reconcile --scope reference
```

Repeat until three archived full-reference xhigh runs exist under unchanged
prompt/schema/rulebook hashes, then run:

```bash
python -m pipeline.stability \
  --scope reference \
  --runs 3 \
  --write quality_reports/stability/reference-xhigh-3run.md
```

After Austin manually verifies all nine references, write the explicit
target-gate proof from the same archived runs:

```bash
python -m pipeline.stability \
  --scope reference \
  --runs 3 \
  --json \
  --write quality_reports/stability/target-release-proof.json
```

Only after `STABLE_FOR_REFERENCE_REVIEW`, `requested_runs >= 3`, at least three
selected immutable run IDs for every reference slug in the proof, Austin's
manual verification of all nine references, and that explicit
`target_gate_proof_v1` file should `--release-targets` be considered. Delete
and regenerate generated artifacts after any prompt/schema/rulebook change. Git
history is the compatibility record; stale outputs are not.

## Security

Never commit API keys. Use `OPENAI_API_KEY` from the shell or `.env`, and keep
local credential files ignored. If any prompt, audit file, log, shell history, or
markdown note captures a real key, stop and rotate the key before continuing.
