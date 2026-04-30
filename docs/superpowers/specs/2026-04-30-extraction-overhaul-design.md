---
title: Extraction overhaul — strict schema, native tools, validation-repair loop
status: APPROVED (brainstorming complete; pending implementation plan)
date: 2026-04-30
branch: api-call
supersedes: docs/superpowers/specs/2026-04-29-robust-extraction-redesign.md (delete in same merge)
authoritative_evidence: quality_reports/2026-04-30_linkflow-tool-use-feasibility-report.md
---

# Extraction Overhaul Design

## 1. Goal

Replace the current prompt-only-JSON extraction path with **strict `text.format=json_schema` + native function-calling tools + an outer Python validation-repair loop**. Hard retire the prompt-only path with no fallback. Same architecture for all deals (9 reference + 392 target). Model: `gpt-5.5` via OpenAI Responses API on Linkflow.

This is one atomic overhaul, not a phased rollout. No backward-compatibility shims. The cleanse of stale code, docs, contract files, audit artifacts, and tests is in scope of the same merge.

## 2. Architecture

```text
filing pages (data/filings/{slug}/pages.json)
  ↓
Extractor turn(s)
  • text.format = strict json_schema (SCHEMA_R1, hardened)
  • tools = [check_row, search_filing, get_pages]
  • model drafts → may emit parallel tool calls → harness runs each tool →
    returns results → model emits final {deal, events} JSON
  ↓
Python prepare_for_validate() + validate()
  • no hard flags → finalize
  • hard flags    → Repair loop (cap = 2 turns, fail-loud on cap-hit)
  ↓
Repair turn (≤ 2 iterations)
  • harness sends compact validator report + affected rows + filing snippets
  • model emits COMPLETE revised extraction (not patches)
  • Python validates again
  • clean → finalize
  • still hard flags after turn 2 → finalize latest draft + emit
    `repair_loop_exhausted` (deal-level, severity=hard); status=`validated`
  ↓
Adjudicator (scoped, no tools, single-turn per soft flag)
  • verdict ∈ {upheld, dismissed} + reason; annotates flag.reason only
  ↓
finalize_prepared() → output/extractions/{slug}.json
                   → output/audit/{slug}/runs/{run_id}/...
                   → state/progress.json + state/flags.jsonl
```

## 3. Schema (strict, but not maximalist)

- `text.format = {"type":"json_schema","strict":true,"schema":SCHEMA_R1}` — unconditional, no Linkflow disable branch.
- `SCHEMA_R1` hardened: `additionalProperties:false` everywhere, complete `required` lists, tightened enums (bid_note, bidder_type, bid_value_unit, role, consideration_components), `maxLength: 1500` on quotes, exact-shape arrays.
- §P-R9 conditional ownership stays in `check_row` for now, **not** encoded as `oneOf` event variants. Encoding §P-R9 in the schema (option A from the brainstorming session) is a deferred follow-up after a separate probe verifies Linkflow accepts deeply-nested oneOf with the full SCHEMA_R1 shape.
- T9 verified strict schema works on Linkflow at 41k–44k input tokens with a small schema. Production schema (full SCHEMA_R1) is verified as a first implementation step before the rest of the overhaul lands.

## 4. Tools (final surface = 3)

The tool surface was deliberately constrained based on empirical evidence (LongFuncEval 2025: 7–91% accuracy loss as tool catalog grows; Snorkel 2025: self-critique tools harmful at high baseline; Anthropic 2025 advanced-tool-use guidance: minimal specific tools). See §11 for what was rejected.

### 4a. `check_row(row: dict) → {ok: bool, violations: [...]}`

- Wraps the 15 row-local Python checks already in [pipeline/core.py](../../../pipeline/core.py): §P-R0, §P-R2, §P-R3, §P-R4, §P-R5, §P-R6, §P-R7, §P-R8, §P-R9, §P-D1, §P-D2, §P-D7, §P-G2, plus type and flag-shape checks.
- Returns `{ok: bool, violations: [{code, severity, reason, field?}]}`.
- Filing pages passed via closure for §P-R2 substring verification.
- Model is instructed in `prompts/extract.md` to call this on every row before submitting it. Parallel calls are expected (T7 evidence: model emits ~10 calls in one batch).

### 4b. `search_filing(query: str, page_range: [int, int] | None, max_hits: int = 10) → {hits: [{page, snippet}]}`

- Case-insensitive substring search over `data/filings/{slug}/pages.json`.
- Returns up to `max_hits` with page numbers (from `pages.json` metadata, not array offsets) and ±200-char snippets.
- Plain substring, not regex (deterministic, low-surprise).
- Use case: petsmart-style "find consortium constituent names in merger-agreement section". Prompt guidance directs the model to scan party-block patterns (e.g., `"by and among"`, `"Parent:"`, `"Schedule A"`) when emitting Buyer Group / Consortium rows.

### 4c. `get_pages(start_page: int, end_page: int) → {pages: [{page, text}]}`

- Fetches contiguous filing pages by number from `pages.json`.
- Complements `search_filing`: separates *find* from *load*, per Anthropic's 2025 cookbook recommendation.
- Use case: model already knows the page (e.g., from a `search_filing` hit or a candidate `source_page`) and wants the full surrounding text.
- Bounded: `end_page - start_page <= 10` to prevent the model from re-loading the entire filing into the conversation.

### 4d. Prompt-side enhancements (bigger lever than any additional tool)

These are not tools but are part of this overhaul because the empirical evidence (BAML SAP, EMNLP 2025 LLM-PEE) shows few-shot evidence-cited row examples gain ~5–6 F1 points on extraction tasks:

- Add a small bank of canonical row examples in `prompts/extract.md` covering: Bid vs Executed nullness (§P-R9 canonical case), unnamed NDA placeholder + later promotion, ConsortiumCA bidder_alias semantics, Buyer Group with constituent atomization.
- Promote §P-R9 nullness rule from line-193 checklist position to high-salience prose paragraph.
- Add explicit tool-call instructions: *"Call `check_row` on every event row before submission. Use `search_filing` and `get_pages` to verify evidence. When emitting a Buyer Group / Consortium / Investor Group row, scan merger-agreement party blocks for constituents."*
- Drop the existing "do not call tools" warning (lines 18–24).

## 5. Repair loop semantics

- Triggered when `pipeline.core.validate()` returns hard flags after the extractor's final draft.
- Sends back: (a) compact validator report with one line per hard flag — `{code, severity, reason, affected_row_index}`; (b) the affected event rows verbatim; (c) filing page snippets cited by `source_quote` for affected rows. No raw filing dump.
- Asks the model for a **complete revised extraction**, not patches. Avoids partial-update ambiguity and finalization-time merging.
- Hard cap: **2 repair turns**. If turn 2 still has hard flags, finalize the latest draft and append a deal-level `repair_loop_exhausted` flag (severity=hard). Status becomes `validated`. The cap is an infinite-loop guard, not a cost control.
- Full-input replay each turn (no `previous_response_id` — Linkflow returns 400; T5 evidence).
- **Streaming policy:** every turn that emits a full `{deal, events}` extraction body uses streaming (the initial extraction draft, *and* every repair turn). Short turns where the model emits only `function_call` items and the harness replies with `function_call_output` items use non-streaming, avoiding the SDK accumulator bug. T6 verified both halves of this policy on the wire.
- Cost is unbounded by design (Austin's "best result over cost" direction). Worker concurrency and reasoning effort are the only cost controls.

## 6. Adjudicator (kept, scoped, no tools)

- Same role as today: per-soft-flag LLM call returning `verdict ∈ {upheld, dismissed} + reason`.
- Runs **after** repair loop closes hard flags. Soft flags only.
- No tools. No extraction rewrite. Annotates `flag.reason` field only.
- Deliberate scope boundary: extractor produces evidence; adjudicator judges it; neither crosses lanes.
- File: [pipeline/llm/adjudicate.py](../../../pipeline/llm/adjudicate.py) — minor changes only (drop `schema_supported` param, log to extended audit manifest).

## 7. Audit additions

New per-run files under `output/audit/{slug}/runs/{run_id}/`:

- **`tool_calls.jsonl`** — one row per tool invocation:
  `{turn, call_id, name, args, result, latency_ms, error?}`. Full `args` and `result` are stored verbatim (JSON-serialized); `result` may be truncated at a documented cap (proposed 8000 chars per row) with a `result_truncated: true` marker if so. Truncation cap is an open question for the implementation plan (§13).
- **`repair_turns.jsonl`** — one row per repair turn:
  `{turn, validator_report_summary, hard_flags_before, hard_flags_after, latency_ms}`. Validator report summary is a compact list of flag codes + counts, not the full report sent to the model (which lives in the prompt artifact).

`manifest.json` extended fields:

- `tools_contract_version` (string, hash of tool definitions + impls)
- `repair_loop_contract_version` (string, hash of repair loop logic + cap)
- `repair_turns_used` (int ∈ {0, 1, 2})
- `repair_loop_outcome` (enum: `clean` | `fixed` | `exhausted`)
- `tool_calls_count` (int, total across all turns)

The `json_schema_used` field is **dropped** (always true under the new contract). Old audit entries with `"json_schema_used": false` are stale (see cleanse boundary).

Cache eligibility checks now require all three contract versions to match: `rulebook_version`, `extractor_contract_version`, `tools_contract_version`. Any change to tool definitions, repair loop semantics, or the schema invalidates cached raw responses.

## 8. Cleanse boundary (concrete file ops, single merge)

### 8a. Delete outright

- `docs/superpowers/specs/2026-04-29-robust-extraction-redesign.md` — superseded by this spec; git history preserves it.
- All loose `output/audit/{slug}/{calls.jsonl, manifest.json, raw_response.json}` for the 9 reference slugs (~27 files, legacy v1 artifacts; reconcile already rejects them).
- All `output/audit/{slug}/runs/*` for the 9 reference slugs (full regeneration).
- All `output/extractions/{9 reference slugs}.json` (full regeneration).
- Tests asserting `json_schema_used=False`:
  - `tests/llm/test_extract.py::test_extract_deal_uses_prompt_only_json_when_schema_unsupported`
  - `tests/llm/test_adjudicate.py::test_adjudicate_prompt_only_json_when_schema_unsupported`
- `_is_newapi_base_url` function in [pipeline/llm/client.py:60](../../../pipeline/llm/client.py:60).
- `schema_supported` parameter from every call site: `extract_deal`, `adjudicate_extraction`, `run_pool`, manifest writer.

### 8b. Archive

- `state/flags.jsonl` → `state/flags.archive/2026-04-30_pre-overhaul.jsonl`. New `state/flags.jsonl` starts empty.
- 9 reference entries in `state/progress.json` reset to `pending` with `notes: "reset for 2026-04-30 overhaul"`. Target-deal entries untouched (gate is closed anyway).

### 8c. Rewrite synchronously in same merge

- [CLAUDE.md](../../../CLAUDE.md), [AGENTS.md](../../../AGENTS.md), [SKILL.md](../../../SKILL.md) — synchronized rewrite. Strict schema + tools + repair loop are the *only* path. All "Linkflow disables structured output" language removed.
- [docs/linkflow-extraction-guide.md](../../../docs/linkflow-extraction-guide.md) — rewrite from scratch around the new architecture. Document the operator-facing repair loop semantics, audit fields, and stability gate.
- [prompts/extract.md](../../../prompts/extract.md) — incorporate tool-call instructions, promote §P-R9 nullness from buried checklist line to high-salience location, drop "do not call tools" warning, add the few-shot evidence-cited row examples described in §4d.
- [pipeline/llm/extract.py](../../../pipeline/llm/extract.py) — add tools param, multi-turn loop, repair loop orchestration, full-input replay.
- [pipeline/llm/client.py](../../../pipeline/llm/client.py) — strict schema unconditional; add `tools` and `tool_choice` params; remove newapi disable branch.
- [pipeline/llm/response_format.py](../../../pipeline/llm/response_format.py) — harden SCHEMA_R1 (`additionalProperties:false`, full required lists, maxLength on quotes); remove conditional schema passing.
- [pipeline/llm/audit.py](../../../pipeline/llm/audit.py) — add `tool_calls.jsonl` and `repair_turns.jsonl` writers; extend manifest fields per §7.
- [pipeline/run_pool.py](../../../pipeline/run_pool.py) — orchestrate new audit fields; drop `schema_supported` threading.
- **NEW** `pipeline/llm/tools.py` — `check_row`, `search_filing`, `get_pages` implementations + JSON schemas + integration with `pipeline.core` validators.

## 9. Migration & verification

1. All code/docs/state changes ship in **one merge** to `api-call`, then to `main`. No phased rollout, no feature flag, no compatibility shim.
2. Implementation pre-step (before the rest lands): verify the full hardened `SCHEMA_R1` is accepted by Linkflow under strict mode. T9 verified a small schema; production needs the real shape. If rejected, soften specific fields and document.
3. After merge: re-extract all 9 reference deals — `python -m pipeline.run_pool --filter reference --workers 5 --extract-reasoning-effort xhigh`.
4. Stability clock starts from this run. Three consecutive clean runs per slug under unchanged hashes (rulebook + extractor + tools/repair) opens the target-deal gate.
5. Verification commands:
   - `python -m pipeline.reconcile --scope reference` — archive consistency.
   - `python -m pipeline.stability --scope reference --runs 3 --json --write quality_reports/stability/target-release-proof.json` — stability proof.
6. Live blocker resolution path:
   - **zep §P-D6 / §P-L2**: repair loop sends validator report → model adds NDA or fixes phase tagging → close.
   - **petsmart §P-R9 ×6**: `check_row` catches each row at draft time; model fixes before submission.
   - **petsmart `buyer_group_constituents_incomplete` ×4**: model uses `search_filing` to scan merger-agreement party blocks per the new prompt guidance, atomizes Buyer Group into constituent rows OR triggers an explicit rule-decision discussion in `rules/` (do we require atomization, or accept "Buyer Group" as a valid `bidder_alias`?).
   - **petsmart `source_quote_not_in_page`**: `check_row` flags during drafting; model uses `search_filing` or `get_pages` to find the correct page or fix the quote.

## 10. Risks tracked (not blockers)

1. **Strict schema with full SCHEMA_R1 untested through Linkflow.** T9 used a small schema. Mitigation: implementation sequencing — verify schema as the first step; soften specific fields if rejected; document in the guide.
2. **Repair loop on a 40k-token-input deal × 2 turns may hit the Linkflow streaming timeout (300s).** Mitigation: streaming the repair turns themselves is in the plan; non-streaming only for the short tool-call turns.
3. **`search_filing` may not fully resolve petsmart's `buyer_group_constituents_incomplete`** even with prompt guidance — the model might still emit "Buyer Group" as a placeholder. If so, that triggers an explicit rule-decision discussion: require atomization (`rules/bidders.md` change) or accept the placeholder as a valid `bidder_alias`. This is a rulebook decision, not a tool gap.
4. **Cross-row violations (§P-D5/D6/D8) may oscillate across repair turns.** The N=2 cap + `repair_loop_exhausted` flag handles this fail-loud.
5. **Linkflow `xhigh` 5-worker ceiling may need re-measurement** with tools enabled (longer per-deal wall time may reduce safe concurrency). Mitigation: empirical re-measurement during the first reference batch.

## 11. Tools considered and rejected (with reason)

The empirical evidence is that smaller tool catalogs perform better. These were considered and explicitly rejected:

| Candidate | Verdict | Reason |
|---|---|---|
| `validate_extraction(draft)` (whole-draft tool) | **Reject** | Redundant with the outer Python repair loop. The loop already runs `pipeline.core.validate()` and feeds back hard flags. |
| `verify_quote(quote, page)` | **Reject** | Strict subset of `check_row` (§P-R2). |
| `lookup_rule(section_id)` | **Reject** | T7 evidence: model never calls it; rules already in prompt. Cargo-cult per Anthropic 2025 minimal-tools guidance. |
| `normalize_date(text, anchor)` | **Reject** | Schema enforces ISO-8601 format. Clinical-temporal literature (CLINES, PubMed timeline 2025) shows date normalization is itself an LLM task — outsourcing it to a tool wins nothing. |
| `normalize_money(text)` | **Reject** | Schema splits `bid_value_low/high/unit`. BAML SAP 2025 handles this in the parser, not via tool. |
| `normalize_entity(text)` / KB lookup (GLEIF, EDGAR CIK, OpenCorporates) | **Reject** | Anti-fit: many bidders are private/PE/unnamed (per `rules/bidders.md`). KB "not found" would push the model to over-reject valid private bidders. |
| Coreference / `find_mentions_of(entity)` | **Reject** | Anti-fit: BidderID is an event-sequence number, not a persistent entity needing clustering. xCoRe / LINK-KG help when entities are unknown post-hoc, not the inverse. |
| Section/TOC navigator (`list_sections`, `get_section`) | **Reject** | "Background of the Merger" is single narrative, not nested sections. HiPS / DocAgent gains come from textbooks/multi-section reports. EdgarTools section detector exists but covers compensation/governance, not Background narrative. |
| `reflect_on_draft` / `score_completeness` | **Strong reject** | Snorkel 2025 self-critique benchmark: -41pp accuracy on high-baseline tasks (Sonnet 4.5: 98% → 57%). CRITIC paper: pure introspection hurts when external signals are available. Active anti-pattern. |
| `count_events`, `compute_timeline` | **Reject** | No empirical paper shows computational tools beating a deterministic post-processor. |
| Specialized `buyer_group_verifier` / `find_buyer_group_constituents` | **Reject** | `search_filing` + new prompt guidance covers it. Specialized tool would bloat catalog (LongFuncEval evidence). |
| `bidder_tree_linker` (finalization-time placeholder linker) | **Reject** | Repair loop's "validator report → revised extraction" path covers unnamed NDA placeholder linkage. |
| RapidFuzz fuzzy quote verification inside `check_row` | **Reject** | Current NFKC + exact substring is rigorous; failures get repaired by the loop. Adds complexity for marginal benefit. |
| `cross_check_draft(rows)` (whole-draft cross-row tool) | **Defer** | Only worth adding if telemetry shows cross-row violations are common. Outer repair loop catches them today. Revisit after first reference batch. |

## 12. Decision record

| # | Decision | Choice |
|---|---|---|
| Q1 | Repair loop scope | **Production loop on every deal**, hard cap N=2 turns, fail loudly into audit on cap-hit (`repair_loop_exhausted` deal-level flag). |
| Q2 | Validation layering | **Schema as shape, tools as gate.** Strict json_schema enforces structure; `check_row` catches §P-R9 conditional nullness. `oneOf` event variants deferred to a follow-up after schema-hardening probe. |
| Q3 | Tool surface | **`check_row` + `search_filing` + `get_pages`.** Plus prompt-side few-shot examples. Everything else rejected with reason (§11). |
| Q4a | Reference output regeneration | **Regenerate from scratch.** Delete `output/extractions/*.json` and `output/audit/*/runs/*` for 9 reference slugs. |
| Q4b | Adjudicator | **Keep, scoped, no tools.** Soft-flag verdict only. |
| Q4c | Migration | **One atomic merge.** No backward compatibility, no shims. |

## 13. Open questions for implementation plan

These are not blockers but should be resolved during implementation:

1. **Pre-step: full SCHEMA_R1 strict probe** — implement a one-shot test harness that POSTs the hardened SCHEMA_R1 against a reference deal full input. If accepted, proceed; if rejected, iterate on schema until accepted, then proceed.
2. **Repair-turn prompt design** — exact format of the validator report sent back to the model. Compact JSON? Bullet list? Per-flag with snippets? Pick one and codify in `prompts/repair.md` (NEW).
3. **Few-shot example bank size and content** — how many canonical row examples in `prompts/extract.md`? Recommend 4–6 covering the failure archetypes (§P-R9, unnamed NDA, ConsortiumCA, Buyer Group atomization). Actual examples drawn from the verified reference deals once they pass the new pipeline.
4. **`tools_contract_version` hash inputs** — must include tool definitions JSON, tool implementation source, and the prompt section instructing tool use. Pick the exact hash inputs and document.
5. **`get_pages` page-range cap** — proposed `<= 10` pages per call. Confirm during first reference batch; relax if model hits the cap meaningfully.
6. **`tool_calls.jsonl` result truncation cap** — proposed 8000 chars per row with explicit `result_truncated: true` marker. `get_pages` results can exceed this on dense pages. Decide whether to keep a single cap, vary by tool, or split large results into a separate `tool_call_payloads/` directory.

## 14. Pointers

- Authoritative empirical evidence: [quality_reports/2026-04-30_linkflow-tool-use-feasibility-report.md](../../../quality_reports/2026-04-30_linkflow-tool-use-feasibility-report.md).
- Validator coverage inventory: see brainstorming agent output (100% of `rules/invariants.md` rules have deterministic Python checks; 15 row-local + 10 whole-draft).
- Live reference state at brainstorming time: 7 of 9 deals pass; zep (2 hard flags) and petsmart-inc (11 hard flags) blocking. All hard flags have a documented resolution path under §9.6.
