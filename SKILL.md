# SKILL.md — M&A Background Extraction

**Purpose.** Given one SEC merger filing (DEFM14A / PREM14A / SC-TO-T / S-4), extract the "Background of the Merger" section into a structured row-per-event JSON matching Alex Gorbenko's auction schema.

**You are one iteration of the per-deal extraction loop.** The code
orchestrator hands the SDK one deal at a time. `run.py --slug X --extract`
is the single-deal wrapper; `python -m pipeline.run_pool --filter reference
--workers N` is the batch runner. Do not carry state across deals.

---

## Invocation contract

**Input** (from the orchestrator): a single `slug` (short identifier, e.g.
`medivation`). `pipeline.llm.extract.build_messages(slug)` assembles SDK
messages: the system message contains `prompts/extract.md` plus
`rules/schema.md`, `rules/events.md`, `rules/bidders.md`, `rules/bids.md`,
and `rules/dates.md`; the user message contains the slug, `manifest.json`,
and page-numbered filing text from `pages.json`. Extraction does not fetch
from SEC, EDGAR, the web, or local files during the model call.
`state/progress.json` carries the `is_reference` flag used downstream by
`scoring/diff.py`.

**Output** (written by `pipeline.core.finalize_prepared()` or
`pipeline.core.finalize()` after validation):
- `output/extractions/{slug}.json` — the extracted rows + deal-level fields.
- Append to `state/flags.jsonl` — any ambiguities flagged during validation.
- Update `state/progress.json` — set the deal's status.
- `output/audit/{slug}/runs/{run_id}/` — immutable run audit artifacts, with
  `tool_calls.jsonl` and `repair_turns.jsonl` when applicable, and
  `output/audit/{slug}/latest.json` as the only mutable audit pointer.

---

## Pipeline (Strict Extractor + Tools + Repair + Scoped Adjudicator)

**Architecture:** `pipeline.run_pool` and `run.py` make direct `AsyncOpenAI`
SDK calls to the Responses streaming endpoint (`responses.stream`) through the
Linkflow/NewAPI-compatible provider configured by `OPENAI_BASE_URL` /
`OPENAI_API_KEY`. Every extractor turn that emits a full extraction body uses
strict `text.format=json_schema` with the hardened `SCHEMA_R1`. The model has
three native function-calling tools while drafting:

- `check_row(row)` — row-local validator wrapper (§P-R0..R9 + §P-D1/D2/D7 +
  §P-G2).
- `search_filing(query, page_range, max_hits)` — substring search over filing
  pages.
- `get_pages(start_page, end_page)` — contiguous page fetch (cap = 10 pages
  per call).

The extractor may emit parallel `function_call` items. The harness runs each
tool locally against the deal's `pages.json`, appends `function_call_output`
items, and replays the full input each turn. There is no
`previous_response_id` chain because Linkflow returns 400. Full extraction and
repair-body turns stream; short tool-call/output turns are non-streaming to
avoid the SDK accumulator empty-output bug.

There is no free-form JSON fallback and no provider branch that turns off
structured output.
Phase 1 Linkflow probes accepted the live `SCHEMA_R1` only after keeping the
provider schema strict-but-not-maximalist: no `oneOf` event variants and no
dynamic `bidder_registry` enforcement in the provider payload. Those remain
live Python contract duties; the pipeline rebuilds and enforces
`bidder_registry` before validation/finalization, and the validator/tooling
enforce conditional row semantics.

The Extractor and optional Adjudicator are model calls; validation,
bidder-registry rebuilding, repair-loop control, and finalization remain Python
code in `pipeline/core.py` and the extraction orchestrator.

**Why deterministic validation stays in Python.**
Every invariant in `rules/invariants.md` (§P-R, §P-D, §P-G, §P-H, §P-L, §P-S) is
mechanically checkable — substring, regex, set membership, graph
traversal. A model-based validator would just re-derive the same checks
non-deterministically and cost money. The Python Validator is deterministic,
free, and instant. The Adjudicator is scoped to the judgment call Python
cannot make: "this soft flag
says the filing seems to stop mentioning this bidder mid-process — is
that a real extraction miss or is the filing genuinely silent?"

### 1. Extractor — SDK call
- **Called by:** `pipeline.run_pool` or `run.py`, one deal per call, no
  cross-deal state.
- **Receives:** a system message containing `prompts/extract.md` and the
  operative extractor rules (`rules/schema.md`, `rules/events.md`,
  `rules/bidders.md`, `rules/bids.md`, `rules/dates.md`), plus a user
  message containing the slug, `manifest.json`, and page-numbered filing
  text from `pages.json`.
- **Does not receive:** `rules/invariants.md`. That file is
  validator-facing only; extractor prompts may name validator check codes
  only as fail-loud guidance for the JSON they emit.
- **Emits:** a single JSON payload `{deal: {...}, events: [...]}` conforming
  to `rules/schema.md` §R1. Every event row carries `source_quote` (NFKC
  substring of the cited page) and `source_page` (integer matching
  `pages.json[i].number`).
- **Can call:** `check_row`, `search_filing`, and `get_pages` during drafting.
  The model should call `check_row` on every event row before final submission
  and use the filing tools to verify quotes, pages, and buyer-group evidence.
- **Prompt builder:** `pipeline.llm.extract.build_messages(slug)`.

### 2. Validator — Python (`pipeline/core.py`)
- **Entry:** `pipeline.validate(raw_extraction, filing) -> ValidatorResult`.
- **Runs:** every invariant in `rules/invariants.md` — §P-R0..9 (structural
  row checks and conditional fields), §P-D1..3 + §P-D5..8 (date/BidderID
  integrity), §P-G2..3 (bid-type and final-round pairing), §P-H5
  (cross-row consistency), §P-L1..2 (lifecycle integrity), §P-S1..5
  (semantic process checks).
- **Returns:** `row_flags` and `deal_flags` lists of
  `{code, severity, reason, [row_index|deal_level]}` dicts.
- **Never rewrites the extraction by itself.** Flag-only discipline preserves
  the Extractor's output as the single source of what was extracted. Python may
  rebuild and enforce `bidder_registry` before validation/finalization, but
  row-level extraction content is repaired only by the model repair loop.

### 3. Repair loop — Python-controlled model turns
- **Fires when:** the Python Validator raises hard flags after the extractor's
  final draft.
- **Receives:** a compact validator report, affected rows, and filing snippets
  needed to repair the specific failures. The model must return a complete
  revised `{deal, events}` extraction, not patches.
- **Cap:** 2 repair turns. If hard flags remain after turn 2, finalization uses
  the latest draft and appends a deal-level hard `repair_loop_exhausted` flag;
  status becomes `validated`.
- **Audit:** one `repair_turns.jsonl` entry per repair turn.

### 4. Adjudicator — SDK call, scoped
- **Fires when:** the Python Validator raises a soft flag (currently §P-S1
  `missing_nda_dropsilent`) after the repair loop has closed or exhausted hard
  flags. No-op when zero soft flags.
- **Receives:** the flagged row + same-bidder context rows + a small window
  of filing pages.
- **Emits:** `{verdict: "upheld" | "dismissed", reason: str}` appended to
  the flag's `reason` field. Severity is not flipped — human review
  stays explicit.
- **Execution model:** this is an SDK call inside the code orchestrator. The
  orchestrator reads validator output, calls the Adjudicator when needed,
  mutates `raw_extraction`, and only then calls
  `pipeline.core.finalize_prepared()`.

### Orchestration

```
  run.py / pipeline.run_pool:
    1. call Extractor SDK with strict json_schema + tools
         parallel function_call → tool dispatch → function_call_output replay
         repeat until model emits final {deal, events}
    2. write audit raw response, prompts, call metadata, and tool_calls.jsonl
    3. filing = pipeline.core.load_filing(slug)
    4. prepared = pipeline.core.prepare_for_validate(raw_extraction, filing)
         includes Python bidder_registry rebuilding/enforcement
    5. result = pipeline.core.validate(prepared, filing)
    6. if any hard flags and repair turns used < 2:
         send compact validator report + affected rows + filing snippets
         model emits complete revised extraction
         prepare + validate again
         record repair_turns.jsonl
       if hard flags remain after turn 2:
         append deal-level hard repair_loop_exhausted flag
    7. if any(flag["severity"] == "soft" for flag in result.row_flags + result.deal_flags):
         call Adjudicator SDK and annotate raw_extraction before finalize
    8. pipeline.core.finalize_prepared(slug, prepared, filing, validation, promotion_log, run_id=run_id)
         → output/extractions/{slug}.json
         → output/audit/{slug}/runs/{run_id}/final_output.json (immutable snapshot)
         → state/flags.jsonl (append)
         → state/progress.json (update)
    9. scoring/diff.py --slug {slug}   (on reference deals)
```

`run.py` is the single-deal CLI wrapper:

```
python run.py --slug X --extract
python run.py --slug X --re-validate
python run.py --slug X --re-validate --audit-run-id <run_id>
python run.py --slug X --re-extract
python run.py --slug X --print-prompt
python run.py --slug X --extract --extract-reasoning-effort xhigh
```

`--re-validate` uses only a cache-eligible archived audit v2 run. Without
`--audit-run-id`, it reads `output/audit/{slug}/latest.json`; with
`--audit-run-id`, it reads `output/audit/{slug}/runs/{run_id}/raw_response.json`.
The archived run must match current `rulebook_version`,
`extractor_contract_version`, `tools_contract_version`, and
`repair_loop_contract_version`.
Loose legacy raw-response files directly under `output/audit/{slug}/` are not
accepted. `--re-extract` forces a fresh model call and writes a new immutable
audit run directory.
`pipeline.run_pool` and `run.py` default both extractor and adjudicator
reasoning effort to `xhigh`, and pass explicit overrides through to the
Responses API when provided. On Linkflow, `xhigh` is capped at
`LINKFLOW_XHIGH_MAX_WORKERS` concurrent workers (default 5). Use
`--re-extract` for a fresh model call.

Target-deal extraction is fail-closed. Any selection containing non-reference
target deals stops before audit directories, SDK clients, or model calls unless
all nine reference deals are `verified`, the explicit `target_gate_proof_v1`
classifies the reference archive as `STABLE_FOR_REFERENCE_REVIEW`, the proof
records `requested_runs >= 3` with at least three selected immutable run IDs for
every reference slug, and the operator supplies `--release-targets`.

There is no per-deal token-budget cap. Audit metadata records input, output,
and reasoning token totals, but high token use does not skip adjudication or
abort a deal. If a soft flag needs adjudication, the orchestrator runs it;
control provider load with worker count and reasoning effort, not hidden
per-deal cutoff logic.

---

## Scope

Defined in `rules/schema.md` §Scope:
- **§Scope-1 🟩** — Research scope is corporate takeover auctions (≥2 non-advisor bidder NDAs in the current process). The pipeline extracts every valid-filing-type deal and emits a deal-level `auction: bool`; downstream filters on `auction == true`. Do NOT pre-gate extraction by auction status.
- **§Scope-2 🟩** — Accepted primary forms: DEFM14A, PREM14A, SC TO-T, S-4. `/A` amendments when they supersede. `SC 14D9` accepted as secondary companion to SC TO-T. `DEFA14A`, `425`, `8-K`, `13D`, `13G` excluded.
- **§Scope-3 🟩** — AI excludes COMPUSTAT fields (`cshoc`, `gvkey*`), EDGAR metadata (`DateFiled`, `FormType`, `URL`, `CIK`, `accession`), and orchestration metadata (`DealNumber`, `rulebook_version`, `last_run`, `last_run_id`). Filing-read deal-identity fields are cross-checked against seeds; filing wins on mismatch.

If any scope rule is 🟥 OPEN, stop and report — do not extract.

---

## Non-negotiable rules

1. **Every emitted row has `source_quote` and `source_page`.** No exceptions. If you can't cite filing text, don't emit the row.
2. **The event vocabulary in `rules/events.md` is closed.** Do not invent new `bid_note` values. If an event doesn't fit, flag it.
3. **Dates follow `rules/dates.md` exactly.** Natural-language dates ("mid-June 2016") must be mapped deterministically, not creatively.
4. **Bidder names follow the filing verbatim** until the canonicalization rule in `rules/bidders.md` §E4 triggers. Exact-count unnamed NDA placeholders are stable lifecycle handles, and `ConsortiumCA.bidder_alias` names the actor rather than the relationship phrase.
5. **Informal-vs-formal classification must be evidenced per `rules/bids.md` §G2**: either a true range bid (both `bid_value_lower` and `bid_value_upper` numeric with `lower < upper`) or a non-empty `bid_type_inference_note` ≤300 chars. The note should cite the §G1 rule applied (trigger phrase, process-position fallback, or structural signal); the validator (§P-G2) enforces evidence, not a specific justification type. Borderline calls are flagged, not forced.
6. **Skip rules in `rules/bids.md` §M are mandatory.** Do not record unsolicited letters with no NDA, no price, no bid intent.
7. **`DropSilent` is only true post-NDA filing silence.** Narrated
   bidder-specific or group outcomes are explicit `Drop` rows;
   identifiable/countable groups atomize, and vague uncountable groups become
   one placeholder `Drop` with an ambiguity flag.
8. **Formal-stage status fields are evidence-bound.** On informal current
   process `Bid` rows, set `invited_to_formal_round` and
   `submitted_formal_bid` true/false only when the filing supports that
   bidder-specific status; otherwise leave them null and flag uncertainty.
9. **Drop classification is evidence-bound and specific.** Filing verb
   subject controls `drop_initiator`; use `unknown` only for genuine agency
   ambiguity. Use the most specific supported `drop_reason_class`, not a
   generic fallback.
10. **Final-round milestone rows are process-level.** One non-announcement
    `Final Round` row can support multiple same-round bids when the filing
    describes one shared deadline, submission event, or outcome.

Evidence quote strings target and hard-fail at 1500 characters. There is no
soft over-target zone; split evidence into the multi-quote form when evidence
is separated or one contiguous paragraph would exceed the cap. Multi-quote
lists may cite separated snippets on the same page.

---

## State contract

**`state/progress.json`** schema:
```json
{
  "schema_version": "v1",
  "deals": {
    "<slug>": {
      "status": "pending | validated | passed | passed_clean | verified | failed",
      "flag_count": 0,
      "last_run": "ISO8601",
      "last_run_id": "<run-uuid>",
      "last_verified_by": null,
      "last_verified_at": null,
      "notes": "",
      "rulebook_version": "<sha256 hash at time of last finalize>",
      "rulebook_version_history": [
        {"ts": "ISO8601", "run_id": "<run-uuid>", "version": "<sha256>"}
      ]
    }
  }
}
```

Notes on the schema:
- There is NO top-level `rulebook_version`. Per-deal finalizes race on a
  global key and never had history anyway. Use `deals[slug].rulebook_version`
  for the current pin and `rulebook_version_history` (last 10 entries) to
  audit the "3 consecutive unchanged-rulebook clean runs" exit gate.
- `rulebook_version_history` is append-only;
  `pipeline.core.RULEBOOK_HISTORY_CAP` (default 10) truncates the oldest
  entries on overflow.
- Target deals that have never been finalized have no `rulebook_version` and
  no history — those fields appear on first finalize.

**`state/flags.jsonl`** — append-only. One flag per line:
```json
{"deal": "medivation", "logged_at": "2026-04-24T12:00:00Z", "row_index": 7, "code": "informal_vs_formal_borderline", "severity": "soft", "reason": "…"}
```

`finalize()` captures a single `run_ts` and stamps it on every flag's
`logged_at` AND on `deals[slug].last_run`. The current-run query is an
exact match:

```
logged_at == deals[slug].last_run
```

Older entries for the same deal (prior finalizes) remain on disk as
history. Do not use `>=` — that returns zero rows, because `last_run` is
the same value as the newest `logged_at`. For the authoritative latest
view without scanning jsonl, read `output/extractions/{slug}.json` `flags[]`
and deal-level `deal_flags[]`.

**`output/extractions/{deal.slug}.json`** schema conforms to `rules/schema.md`.
Pipeline-stamped deal-level fields: `rulebook_version`, `last_run`, and
`last_run_id` (populated on every finalize and matching the entries in
`state/progress.json`).

**Status semantics:**
- `pending` — not yet run.
- `validated` — combined extractor + validator flags contain at least one hard flag.
- `passed` — combined extractor + validator flags contain only soft/info flags.
- `passed_clean` — combined extractor + validator flags are zero.
- `verified` — Austin manually read the filing and adjudicated any AI-vs-Alex diff. Only set on reference deals, and only by the manual review workflow (not by the pipeline). On target deals this status is never used; they typically stop at `validated`, `passed`, or `passed_clean`.
- `failed` — pipeline error (fetch, section-location, etc.) when no prior
  successful live extraction exists. If a fresh rerun fails after a deal was
  already `validated`, `passed`, `passed_clean`, or `verified`, preserve that
  prior live state and write the failed attempt to audit instead.

`extracted` remains a useful conceptual stage in the orchestration flow, but
the current repo does not persist it into `state/progress.json`.

`validated` is finalized but blocked. It is not a success/completed status for
runner skip logic or the reference gate.

**Audit v2 archive:**
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

Fresh attempts never delete or overwrite prior run directories. Failed attempts
write a run manifest and `latest.json` with `cache_eligible=false`. Re-validation
copies the selected archived raw response into a new run directory and records
`cache_used=true` plus `source_audit_run_id`. Cache eligibility requires the
current rulebook pin plus extractor, tools, and repair-loop contract versions
to match the archived run. `final_output.json` is the immutable finalized
snapshot used by stability checks. Each run-dir JSON file carries its own
`schema_version` (`audit_run_v2`, `raw_response_v2`, `validation_v1`,
`final_output_v1`); `latest.json` carries `audit_v2`.

**Reconcile and stability commands.** Two read-only entrypoints close the
target gate. `python -m pipeline.reconcile --scope reference` checks
that `state/progress.json`, `output/extractions/{slug}.json`,
`state/flags.jsonl`, and `output/audit/{slug}/` all agree on the same
`last_run_id`, flag counts, and rulebook version. `python -m pipeline.stability
--scope reference --runs 3 --json --write quality_reports/stability/target-release-proof.json`
walks immutable run archives, computes substantive metrics across at least
three reference runs per slug, and writes `target_gate_proof_v1` JSON with a
final classification (`STABLE_FOR_REFERENCE_REVIEW`,
`UNSTABLE_RULE_OR_VALIDATOR_FIX_NEEDED`,
`UNSTABLE_ARCHITECTURE_ESCALATION_CANDIDATE`, or `INSUFFICIENT_ARCHIVED_RUNS`).
The runner consumes that proof; see `docs/linkflow-extraction-guide.md` for the
full operator protocol.

---

## Fail-loud rules

- If the filing artifacts are missing from `data/filings/{slug}/` →
  `status: failed`, `notes: "missing_filing_artifacts: <detail>"`, exit.
- If the "Background of the Merger" section can't be located → `status: failed`, `notes: "no_background_section"`, exit.
- If any invariant in `rules/invariants.md` fails → `status: validated`, `flag_count: N` (the row is still emitted, but flagged).
- If any 🟥 OPEN rule is encountered in the extractor-read rule files → stop immediately and report. Never guess around an open question.

---

## What this skill deliberately does NOT do

Full list in `rules/schema.md` §Scope-3. In summary:

- Compute COMPUSTAT fields: `cshoc`, `gvkey`, `gvkeyT`, `gvkeyA`. Downstream merge.
- Re-derive EDGAR metadata: `DateFiled`, `FormType`, `URL`, `CIK`, `accession`. Fetcher (`manifest.json`) owns these.
- Assign `DealNumber`. Pipeline keys on `slug`; downstream joins if needed.
- Fetch any external data (news, COMPUSTAT, other filings). Only reads the filing already downloaded under `data/filings/{slug}/`.
- Fix Chicago-collected source workbook rows or overwrite `reference/deal_details_Alex_2026.xlsx`.
- Cross-deal bidder canonicalization (is this deal's "Sponsor A" the same as that deal's "Sponsor A"?). Explicit non-goal.
- Re-classify the form type. The fetcher already classified it from the EDGAR index; AI copies it through unchanged.

Final Excel assembly is out of scope for the current repo. This skill stops
at JSON extraction + validator flags.

---

## No backward compatibility

This repo supports only the current live schema, prompt contract, state format,
output format, and direct SDK orchestration path. When any of those change,
update this file, `AGENTS.md`, `CLAUDE.md`, the rulebook, and tests in the same
change. Regenerate or delete affected artifacts. Do not add fallback readers,
retired command aliases, old-format loaders, hidden transition layers, or docs
that present old and current behavior as simultaneously supported. Git history
is the compatibility record.

After a refactor, deep-clean stale code and stale docs immediately. Search for
retired commands, retired file paths, obsolete architecture prose, stale
generated reports, and dead tests. Delete or rewrite anything that no longer
describes the live contract.

---

## When to change this file

- Never during routine extraction.
- Change it whenever architecture, invocation semantics, schema/state/output
  contracts, or no-compatibility doctrine changes.
- Before adding a new model role, orchestration layer, or rule file, name the
  concrete extraction failure it fixes. If the assumption is unclear, do not
  add it.
