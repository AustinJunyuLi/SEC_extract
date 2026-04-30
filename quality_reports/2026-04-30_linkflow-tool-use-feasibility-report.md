# Linkflow Tool Use & Structured Output — Feasibility Report

**Date:** 2026-04-30
**Branch:** `api-call`
**Author:** Claude (orchestration) + clean-slate experiment subagent; Codex follow-up probe and handoff edits
**Audience:** A fresh agent designing the refactor. Read sections 1–4 first if you don't know the project; jump to sections 6 and 12 if you do.

**Codex follow-up status (same day):** strict `text.format=json_schema`
was re-probed on full Background payloads for `providence-worcester`,
`petsmart-inc`, and `medivation` using `pipeline.llm.extract.build_messages`.
It passed on ~41k-44k input-token prompts, including streaming probes for
Providence and Medivation. `json_object` failed fast with Linkflow/Cloudflare
502s on all three full-input probes. Therefore, the refactor should prefer
strict `json_schema`; do not treat `json_object` as the fallback.

---

## 1. What this project is (60-second background)

`bids_try` is an extraction pipeline that reads SEC merger filings (DEFM14A, PREM14A, S-4, SC-TO-T) and emits one JSON row per "thing that happened" in the takeover auction (NDAs, bids, drops, executions, etc.). The goal is research-grade data for Alex Gorbenko's M&A informal-bidding research.

**Architecture:** direct AsyncOpenAI SDK calls to Linkflow (a Linkflow/NewAPI-compatible OpenAI proxy at `https://www.linkflow.run/v1`) using the streaming Responses endpoint. Default model: `gpt-5.5`, default reasoning effort: `xhigh`. Per-deal flow:

```
filing pages → Extractor (LLM) → raw {deal, events} JSON
            → Python validator (pipeline/core.py) → flags
            → optional scoped Adjudicator (LLM) for soft flags
            → finalized output/extractions/{slug}.json
            → state/progress.json + state/flags.jsonl
```

**Status:** Stage 3 (build, iterate, manually verify against 9 reference deals). Current local state has 7 reference deals passed and 2 validated/blocking (`zep`, `petsmart-inc`). Target-deal gate (392 remaining deals) **closed** until reference set clears 3 consecutive unchanged-rulebook clean runs.

**Critical context files** (read these next if you haven't):
- [CLAUDE.md](../CLAUDE.md) — live project contract
- [SKILL.md](../SKILL.md) — extraction skill contract
- [docs/linkflow-extraction-guide.md](../docs/linkflow-extraction-guide.md) — Linkflow transport contract
- [pipeline/llm/extract.py](../pipeline/llm/extract.py) — current SDK extraction call pattern and primary refactor target
- [pipeline/core.py](../pipeline/core.py) — Python validator
- [rules/invariants.md](../rules/invariants.md) — validator-facing hard/soft/info checks (§P-R9 in particular)
- [prompts/extract.md](../prompts/extract.md) — extractor prompt

---

## 2. Why we ran this experiment

The original experiment was motivated by reference-deal failures where the
model did not enforce rules it already knew. Some examples below are now stale
as live blockers, but they remain useful regression cases for the refactor:

### 2a. Providence & Worcester — historical §P-R9 regression case

Row 41 (`Executed`, G&W $25/share execution) populates bid-economics fields:

```json
{
  "bid_note": "Executed",
  "bidder_alias": "G&W",
  "bid_value_pershare": 25.0,         // ← §P-R9 violation
  "bid_value_unit": "USD_per_share",  // ← §P-R9 violation
  "consideration_components": ["cash"] // ← §P-R9 violation
}
```

**Rule (§P-R9.4 in [rules/invariants.md:144](../rules/invariants.md:144)):** *"Bid economics fields are null outside `Bid` rows."*

**Why it regressed:** Commit `8a51724` ("require consideration components on value-bearing bids") added an emphatic paragraph at [prompts/extract.md:79](../prompts/extract.md:79) telling the model to fill bid-economics on every value-bearing Bid. Under high reasoning, the model overgeneralized "value-bearing" to also cover the press-release-restated $25/share on the Executed row. The opposite rule (null on non-Bid rows) is buried in a checklist line at [prompts/extract.md:193](../prompts/extract.md:193) with much weaker prompt salience.

**This is a perfect case for in-flight self-correction**: a deterministic Python validator can spot the violation before the model commits, and the fix is mechanical (set those three fields to null, move the $25 to `additional_note`). A `validate_row` tool would have caught this.

### 2b. PetSmart — current blocker; model self-flag / buyer-group case

The model voluntarily emitted `severity: "hard"` on its own row-level / deal-level `buyer_group_constituents_unidentified` flags, declaring *"I should atomize Buyer Group rows into per-constituent rows but the bidding-narrative slice doesn't name them."*

The flag code `buyer_group_constituents_unidentified` does not exist anywhere in `pipeline/`, `rules/`, or `prompts/` — it's not validator-enforced. The model invented it. Some hards landed on rows that aren't even Buyer Group rows (row 52 is Bidder 2; row 55 is a process-level Final Round row).

This is the kind of thing where **`find_in_filing` could help**: the merger-agreement section later names all 5 constituents (BC Partners, La Caisse, GIC, StepStone, Longview — the model uses them on the Executed rows 56–60). A grep tool would let the model retrieve these and back-fill them onto the Buyer Group rows.

### 2c. Architectural question

The exploration question: **can we give the extractor narrow, deterministic tools (`validate_row`, `lookup_rule`, `find_in_filing`) to self-correct in-flight, instead of accepting overgeneralization and hoping post-extraction validation catches it?**

The blocker on that question was Linkflow. The transport guide ([docs/linkflow-extraction-guide.md](../docs/linkflow-extraction-guide.md)) is explicit:

> "Linkflow/NewAPI-compatible providers may not handle strict OpenAI structured-output payloads the same way OpenAI's native endpoint does. The current client therefore disables structured output for Linkflow."

> "Large Responses calls with strict `json_schema` / `text.format` payloads. This combination was observed to be brittle through Linkflow."

If strict structured output is brittle on Linkflow, native function-calling (which rides the same `tools` / structured-payload plumbing) likely is too — or at least needs verification before we build on top of it. Hence this experiment.

---

## 3. What we tested

Eight Claude-planned tests, T1–T8. T8 was a fallback to demonstrate prompt-only simulated tool use; we didn't need it because T4–T6 worked. Codex then ran a separate full-input JSON-format probe, T9, in `/tmp` without touching official pipeline artifacts.

| Test | Question |
|---|---|
| **T1** | Does the streaming Responses transport work at all on this key/proxy/model? |
| **T2** | Does strict `text.format = json_schema, strict=True` actually fail through Linkflow today? (testing the guide's claim) |
| **T3** | Does looser `text.format = json_object` work? |
| **T4** | Does the model emit `function_call` items when given `tools=[...]`? |
| **T5** | Can we round-trip a tool result back to the model and get a final answer? |
| **T6** | Does T5 work under streaming? |
| **T7** | End-to-end: does giving `validate_row` + `lookup_rule` to the extractor actually change extraction quality on a real reference deal? |
| **T8** | (Fallback, not run) Simulate tool use via prompt+parse if T4–T6 failed. |
| **T9** | Do prompt-only JSON, `json_object`, and strict `json_schema` survive full Background payloads from real reference deals? |

Models tested: `gpt-5.5`. Reasoning efforts: `medium` for plumbing tests and T9, `high` for the T7 E2E test.

---

## 4. Findings — the headline

| Capability | Verdict |
|---|---|
| Streaming Responses baseline | **works** |
| Strict `json_schema` (`text.format`, `strict=True`), non-streaming | **works** — clean parse |
| Strict `json_schema`, streaming | **works** — clean parse |
| Strict `json_schema` on full Background payloads | **works** — clean parse on ~41k-44k input-token prompts |
| `json_object` mode, toy prompt | **works** |
| `json_object` mode, full Background payloads | **broken** — fast Linkflow/Cloudflare 502s |
| Tool definition, model emits `function_call` | **works** |
| Tool round-trip via `previous_response_id` | **broken** (HTTP 400) |
| Tool round-trip via full-input replay | **works** |
| Streaming + tools (wire) | **works** — deltas fire correctly |
| Streaming + tools (SDK accumulator) | **broken** — `stream.get_final_response().output` is `[]` |
| Parallel tool calls in one turn | **works** — model emitted 10 `validate_row` calls in a single output |

### Three surprises worth flagging

1. **The legacy "strict json_schema is brittle" claim no longer reproduces.** T2 returned clean parseable JSON on first try, both streaming and non-streaming, on `gpt-5.5`. T9 then confirmed strict schema on full Background payloads for three reference deals. The current Linkflow guide is stale on this point.

2. **`json_object` is not the safe fallback.** It worked on a toy prompt but failed with 502s on every full-input T9 probe. If strict schema has to be disabled for some reason, fall back to prompt-only JSON plus Python validation, not `json_object`.

3. **Reasoning tokens drop sharply when tools are available.** On Medivation (T7), reasoning tokens dropped 2.4× (2,057 → 848) when validators were in scope. The model offloads "did I get the shape right?" to the deterministic tool instead of reasoning about it. Total tokens still rose 1.8× because of round-trip overhead, but Austin has explicitly prioritized best extraction quality over token cost.

---

## 5. Detailed test results

### T1 Baseline
**Request:** `client.responses.stream(model="gpt-5.5", input="Say hi", reasoning={"effort":"medium"})`
**Result:** OK in 3.40s. Standard event stream (`response.created` → `response.output_text.delta` → `response.completed`).
**Conclusion:** Transport healthy.

### T2 Strict structured output
**Request:**
```python
client.responses.create(
    model="gpt-5.5",
    input="Generate a fictional person profile.",
    reasoning={"effort": "medium"},
    text={
        "format": {
            "type": "json_schema",
            "name": "Person",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "age":  {"type": "integer"},
                    "city": {"type": "string"},
                },
                "required": ["name", "age", "city"],
            },
        }
    },
    max_output_tokens=4096,
)
```

**Result (non-streaming):** OK in 2.78s. Output: `{"age":34,"city":"Portland","name":"Maya Ellison"}`. `json.loads` succeeds.
**Result (streaming):** OK in 2.63s. Same shape, parses cleanly.

**Conclusion:** Strict json_schema works on `gpt-5.5` through Linkflow today. The historical "brittle" finding does not reproduce.

### T3 JSON mode
**Request:** Same as T2 but `text={"format": {"type": "json_object"}}`.
**Result:** OK in 2.52s. Output: `{"name":"Alex","age":30,"city":"New York"}`.
**Conclusion:** Works only on the toy prompt. T9 later showed `json_object`
failing with fast 502s on full Background payloads, so it should not be the
production fallback.

### T4 Tool definition, no round-trip
**Request:**
```python
client.responses.create(
    model="gpt-5.5",
    tools=[{
        "type": "function",
        "name": "validate_row",
        "description": "Validate a single extraction row against the rulebook. Returns ok and any violations.",
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"row": {"type": "object", "additionalProperties": True, "properties": {}}},
            "required": ["row"],
        },
    }],
    tool_choice="auto",
    input='You are reviewing this candidate extraction row. Call validate_row to check it before reporting back. Row: {"event_type": "NDA", "bid_value_low": 100}',
    reasoning={"effort": "medium"},
    max_output_tokens=4096,
)
```

**Result:** OK in 1.90s. Single `function_call` item:
```
output[0].type=function_call
  name=validate_row
  arguments='{"row":{"event_type":"NDA","bid_value_low":100}}'
  call_id=call_5wyr1bW4glKNQGdc16KgzjsI
```

**Conclusion:** Native function calling on Responses works through Linkflow. All three round-trip-critical fields preserved (`name`, `arguments` as JSON string, `call_id`).

### T5 Full tool round-trip — TWO STRATEGIES

**Strategy A (idiomatic OpenAI pattern — `previous_response_id` chain):**
```python
client.responses.create(
    model="gpt-5.5",
    previous_response_id=resp1.id,
    tools=TOOLS,
    input=[{"type": "function_call_output", "call_id": ..., "output": json.dumps(result)}],
    ...
)
```
**Result:** **400 BadRequestError**.
```json
{"error":{"message":"previous_response_id is only supported on Responses WebSocket v2","type":"invalid_request_error","param":"","code":null}}
```
**Conclusion:** Linkflow does NOT proxy server-side conversation state. Cannot use `previous_response_id`.

**Strategy B (full-input replay — works):**
```python
replayed_input = list(initial_input)        # [user msg]
for item in resp1.output:                   # turn 1 outputs (the function_call item)
    replayed_input.append(item.model_dump())
replayed_input.append({                     # tool result
    "type": "function_call_output",
    "call_id": tool_calls[0]["call_id"],
    "output": json.dumps(result),
})
resp2 = client.responses.create(
    model="gpt-5.5",
    tools=TOOLS,
    input=replayed_input,
    ...
)
```
**Result:** OK in 1.85s. Final output:
```
'Does not pass.\n\nViolation:\n- §P-R9: NDA rows must have null `bid_value_low`'
```
**Conclusion:** Works. Full-input replay scales linearly with conversation
length. Since Austin prioritizes best results over cost, treat this as a
latency/reliability consideration rather than a reason to avoid tools.

### T6 Streaming + tools

**Turn 1 (streaming):** Events fired in this order: `response.created` → `response.in_progress` → `response.output_item.added` (×2: reasoning + function_call) → `response.function_call_arguments.delta` → `response.function_call_arguments.done` → `response.output_item.done` (×2) → `response.completed`. The wire-level data is intact:

```python
# from response.output_item.added when item.type=='function_call':
fc_name = "validate_row"
fc_call_id = "call_HDVeb..."
# from response.function_call_arguments.delta accumulation:
fc_args = '{"row":{"event_type":"NDA","bid_value_low":100}}'
```

**Gotcha — SDK accumulator:**
```python
final = stream.get_final_response()
print(final.output)  # → []  ← EMPTY through Linkflow
```

The SDK's `final.output` accessor returns an empty list under Linkflow streaming, even though the wire-level events all fired correctly. The harness must reconstruct the function_call item from delta events:

```python
fc_args_chunks = []
fc_name = None
fc_call_id = None
with client.responses.stream(...) as stream:
    for event in stream:
        etype = getattr(event, "type", "?")
        if etype == "response.function_call_arguments.delta":
            fc_args_chunks.append(getattr(event, "delta", ""))
        elif etype == "response.output_item.added":
            item = getattr(event, "item", None)
            if item:
                d = item.model_dump() if hasattr(item, "model_dump") else item
                if d.get("type") == "function_call":
                    fc_name = d.get("name")
                    fc_call_id = d.get("call_id")
    final = stream.get_final_response()

# Fallback reconstruction
if not final.output and fc_call_id:
    reconstructed_function_call = {
        "type": "function_call",
        "name": fc_name,
        "call_id": fc_call_id,
        "arguments": "".join(fc_args_chunks),
    }
```

**Turn 2 (streaming, full-input replay):** OK in 3.16s. `output_text.delta` events fired normally. Final text matches T5 Strategy B.

**Conclusion:** Streaming + tools works on the wire. The only fix needed is the SDK reconstruction shim. Alternative: just use non-streaming for tool-bearing turns (T7 did this, no issues).

### T7 Medivation end-to-end

**Setup:**
- Pages 24–27 of the Medivation filing (`data/filings/medivation/pages.json`)
- Trimmed extraction prompt with §P-R9 inlined as the critical rule
- Two tools available:
  - `validate_row(row) → {ok, violations}` — implements §P-R9 nullness on non-Bid rows + basic source_quote/source_page checks
  - `lookup_rule(section_id) → {text}` — small in-script rulebook with §P-R9, §C3, §G1, §P-R2
- Two runs: (A) no tools, (B) with tools
- Model: `gpt-5.5`, reasoning=`high`

**Results:**

| Metric | no-tools (A) | with-tools (B) |
|---|---:|---:|
| Wall time | 48.9 s | **37.6 s** |
| Total tokens | 7,545 | 13,703 |
| Reasoning tokens | 2,057 | **848** |
| Events emitted | 10 | 10 |
| §P-R9 violations | 0 | 0 |
| Tool calls | — | 10 (10 `validate_row`, 0 `lookup_rule`) |
| Number of turns | 1 | 2 (parallel tool batch + final) |

**Behavior observed in run B:** The model emitted **all 10 `validate_row` calls in a single Responses output** (parallel function calling, native to the API). The harness collected all 10 function_call items, ran each through `py_validate_row` locally, sent all 10 `function_call_output` items back in the next `input`, and the model produced the final extraction message in turn 2. `lookup_rule` was never called; the model only invoked tools when it saw concrete value.

**Quality observation:** Both runs produced essentially the same 10 events with consistent dates/bidders/types/nullness. The tool-aware run additionally captured a Sanofi `Press Release` row that the no-tools run missed (legitimate filing event). No §P-R9 violations on either side — Medivation's bidding section is clean enough that the model gets nullness right unaided.

**Caveat: Medivation does not stress the regression case.** Providence row 41 is the case that actually fires §P-R9. T7 demonstrates plumbing works end-to-end and that tools don't break extraction quality; it does not yet prove that tools catch the Providence regression. The production repair loop should catch it even if voluntary row-level tool calls miss it.

### T8 (not run)
Skipped because T4–T6 succeeded. Native tool use is the recommended path; simulated prompt+parse is unnecessary.

### T9 Codex full-input JSON-format probe

**Setup:**
- Read-only/scratch-only probe; wrote only under `/tmp/bids_try_linkflow_json_probe_codex`.
- Inputs came from `pipeline.llm.extract.build_messages(slug)`, i.e. the real full Background section payload assembled by the live prompt builder.
- Deals: `providence-worcester`, `petsmart-inc`, and `medivation`.
- Model: `gpt-5.5`; reasoning effort `medium`; small strict schema returning metadata only, not a real extraction.
- Formats tested: prompt-only JSON, `text.format={"type":"json_object"}`, strict `text.format={"type":"json_schema", "strict": true}`. Streaming strict schema was tested on Providence and Medivation.
- Raw filing text and raw model outputs were intentionally not saved.

**Results:**

| slug | format | streaming | result | parse | input tokens | output tokens | latency |
|---|---|---:|---|---:|---:|---:|---:|
| `providence-worcester` | prompt-only JSON | no | success | yes | 43,977 | 141 | 5.35s |
| `providence-worcester` | `json_object` | no | 502 failure | no | — | — | 0.83s |
| `providence-worcester` | strict `json_schema` | no | success | yes | 44,066 | 93 | 3.79s |
| `providence-worcester` | strict `json_schema` | yes | success | yes | 44,066 | 94 | 5.10s |
| `petsmart-inc` | prompt-only JSON | no | success | yes | 43,770 | 158 | 5.34s |
| `petsmart-inc` | `json_object` | no | 502 failure | no | — | — | 0.71s |
| `petsmart-inc` | strict `json_schema` | no | success | yes | 43,859 | 92 | 3.90s |
| `medivation` | prompt-only JSON | no | success | yes | 40,968 | 137 | 6.37s |
| `medivation` | `json_object` | no | 502 failure | no | — | — | 1.19s |
| `medivation` | strict `json_schema` | no | success | yes | 41,057 | 89 | 3.19s |
| `medivation` | strict `json_schema` | yes | success | yes | 41,057 | 92 | 4.86s |

**Conclusion:** strict `json_schema` is robust enough to design against. The old Linkflow guide warning about strict schema is stale for current `gpt-5.5` / Linkflow behavior. `json_object` is actively unattractive on full prompts because it fails before model work begins.

---

## 6. Recommended Refactor Design

Austin's direction after reviewing the cost issue: **optimize for best results,
not token cost**. The design should use strict schema, native extractor tools,
and a validation-driven repair loop. Python validation remains the final
authority; model tools are an in-flight correction mechanism, not a replacement
for `pipeline.core.validate()`.

### 6a. Turn strict `json_schema` on for Linkflow

- Use strict `text.format=json_schema` as the default Linkflow extraction shape,
  not `json_object`.
- Start from `SCHEMA_R1` in [pipeline/llm/response_format.py](../pipeline/llm/response_format.py).
- Strengthen the schema where supported by the Responses strict-schema subset:
  required fields, `additionalProperties=false`, enums, quote max length, and
  conditional ownership of fields such as §P-R9. If direct `if/then` keywords are
  not accepted by the provider/schema subset, encode conditional ownership with
  explicit `oneOf` event variants.
- Keep local schema validation anyway. The provider constrains generation; Python
  still rejects malformed or stale outputs.
- Update [docs/linkflow-extraction-guide.md](../docs/linkflow-extraction-guide.md),
  [AGENTS.md](../AGENTS.md), [CLAUDE.md](../CLAUDE.md), [SKILL.md](../SKILL.md),
  and tests that currently assert `json_schema_used=false` for Linkflow.

### 6b. Add extractor-only native tools

Do **not** give tools to the scoped Adjudicator at first. Its job is to verdict
soft flags on a fixed extraction; tools would blur that boundary.

Recommended extractor tools:

- `validate_row(row, context=None)`: row-local checks such as §P-R2 evidence
  shape/quote length, §P-R9 conditional nullness, §P-G2 bid-type satisfiers, and
  §P-D8 formal-status consistency.
- `validate_extraction(draft)`: run `prepare_for_validate()` and `validate()` on
  a deep copy and return structured row/deal flags plus a compact summary. This
  catches cross-row failures the row tool cannot see.
- `verify_quote(source_quote, source_page)`: use page **number** from
  `pages.json`, not page-array offset. Return exact substring success/failure and
  short nearest-snippet hints.
- `find_in_filing(query, page_range=None, max_hits=10)`: deterministic search
  over filing pages. This is for PetSmart-style buyer-group lookup and other
  missing-evidence cases. Return page numbers and short snippets only.
- `lookup_rule(section_id)`: return exact rulebook snippets by anchor from
  `rules/*.md`.

Drive tools with full-input replay. Do not use `previous_response_id`; Linkflow
rejects it. Prefer non-streaming tool turns first, because streaming tool events
work on the wire but the SDK final-response accumulator is unreliable. If
non-streaming hits proxy timeouts on real full extractions, reconstruct tool
calls from streaming events instead of abandoning tools.

### 6c. Add an outer validation-repair loop

The best-result architecture should be:

```text
Extractor draft with strict schema + tools
  -> Python prepare_for_validate + validate on a copy
  -> if hard flags or fixable soft flags:
       send compact validator report + affected rows + relevant snippets back
       ask model for a complete revised extraction
       repeat
  -> final Python validate
  -> finalize_prepared() and audit
```

Important behavior:

- The model must return a **complete revised extraction**, not patches. This
  keeps finalization simple and avoids partial-update ambiguity.
- The loop should not silently repair fields in Python except for existing
  deterministic transforms (`unnamed_nda_promotion`, canonical ordering). Let the
  model revise, then let Python validate.
- Stop only when validation is clean or the remaining flags are genuine
  ambiguity/human-review flags. If safety caps are needed, they are infinite-loop
  guards, not cost controls.
- Put high-salience instructions in `prompts/extract.md`: call tools when unsure,
  respect tool results, and revise on validator feedback.

### 6d. Audit, cache, and state changes

- Add `tools_contract_version` and `repair_loop_contract_version` to audit
  manifests and cache eligibility checks.
- Log tool calls to `output/audit/{slug}/runs/{run_id}/tool_calls.jsonl` with
  `{turn, name, args_digest or sanitized args, result, latency_ms}`.
- Log repair-loop iterations to `repair_turns.jsonl` with validation summaries,
  not giant raw filing/model dumps. Existing prompt/raw-response artifacts still
  carry the immutable evidence.
- Record `json_schema_used=true` when strict schema is active, and include the
  schema hash already computed from `SCHEMA_R1`.
- Any change to tool signatures, schema, prompt, or repair-loop behavior should
  invalidate cached raw responses and reset the stability clock.

### 6e. Repo hygiene before production runs

- Remove or archive stale loose audit files under `output/audit/{slug}/`; current
  `pipeline.reconcile --scope reference` rejects them.
- Current live blockers are `zep` and `petsmart-inc`. Historical Providence
  remains the important §P-R9 regression test, but it is not the current live
  state/output drift.
- Before target-deal extraction, reconcile and stability must pass under the new
  contract with at least three selected immutable runs per reference slug.

---

## 7. Gotchas (commit these to memory)

1. **`previous_response_id` returns 400 through Linkflow** — *"only supported on Responses WebSocket v2"*. Use full-input replay (rebuild `input` each turn with prior outputs + tool results). 5-line workaround.

2. **`stream.get_final_response().output` is empty under Linkflow streaming.** Wire-level events (`output_item.added`, `function_call_arguments.delta`, `output_item.done`, `output_text.delta`) all fire correctly — only the SDK accumulator misses them. Either reconstruct from delta events, or use non-streaming for tool-bearing turns.

3. **Parallel tool calls are native.** The model can emit N `function_call` items in a single Responses output. Collect ALL of them and emit ALL `function_call_output` items in the next `input` before the model produces a message. Don't loop one-call-at-a-time — that doubles wall time.

4. **`function_call_output` item shape:**
   ```python
   {"type": "function_call_output", "call_id": "<from function_call>", "output": "<JSON string>"}
   ```
   The `output` field must be a string — serialize the dict yourself.

5. **`text` is the param name on the Responses API**, not `response_format`. Chat Completions uses `response_format`; Responses uses `text={"format": {...}}`. Don't mix them — Linkflow will pass the wrong-named arg through and the model will silently ignore it.

6. **Strict json_schema works now.** T2 produced clean parseable output on first try, both streaming and non-streaming. T9 then passed on full Background payloads. The Linkflow guide's "brittle" claim is stale evidence (likely from an older proxy version, older SDK, or different model). Document the new evidence when you re-enable it.

7. **`json_object` is worse than prompt-only JSON on full prompts.** It worked in the toy probe but failed with fast 502s on every full-input probe. Do not use it as the fallback.

8. **Reasoning tokens drop sharply when tools are available.** Net total tokens still rise from round-trip overhead, but Austin has prioritized best extraction quality over token cost.

9. **Empirical Linkflow ceiling: 5 concurrent workers at `xhigh` reasoning.** Already enforced in [pipeline/run_pool.py](../pipeline/run_pool.py) via `LINKFLOW_XHIGH_MAX_WORKERS`. Tool-using extractions take longer (more turns) — the ceiling may need to be re-measured; don't assume 5 still holds with tools enabled.

---

## 8. Open questions (verify before assuming)

These are explicit gaps in what we tested. They should inform the refactor
design; they do not block designing the best-result architecture in §6.

**Q1. Does `validate_row` actually catch the providence row 41 regression?**
T7 used Medivation, which doesn't fire §P-R9. Run the same harness on providence-worcester. Either:
- The model calls `validate_row` on row 41, gets violations back, fixes, and the regression disappears.
- The model fails to call it on Executed rows (because the prompt didn't say to), and the regression persists. → Adjust prompt to require `validate_row` on every row before emitting.
- The model calls it but ignores violations. → Adjust prompt or downgrade to a hard wrapper that re-prompts on violations.

The production design should not depend only on voluntary row calls. The outer
`validate_extraction` / repair loop should catch this even if the model skipped
`validate_row` during drafting.

**Q2. Does `find_in_filing` (third tool, not yet tested) help petsmart?**
The hypothesis: give the model `find_in_filing(regex, page_range=None)` — grep over `data/filings/{slug}/pages.json`, return `[{page, snippet}]`. Test on petsmart: does the model search for the consortium constituent names in the merger-agreement section and back-fill them onto Buyer Group rows? T7 didn't include this tool.

**Q3. Production strict schema for the actual extraction shape.**
T9 used a small strict schema on full inputs. It proves Linkflow can carry strict
schema with full prompts, but it does not prove that the full `SCHEMA_R1`
accepted by [pipeline/llm/response_format.py](../pipeline/llm/response_format.py)
will be accepted by the provider. Test the actual schema, including any
conditional/event-variant encoding chosen in the refactor.

**Q4. Token and latency scaling with full extraction prompts.**
T7 used a trimmed prompt (4 pages). Real extraction uses the full Background
slice (often 30+ pages, 30k+ tokens). With full-input replay, every tool turn
re-sends the conversation. Austin does not want cost to drive the design, but
latency/timeouts still matter for reliability. Measure on full reference runs
and prefer streaming reconstruction if non-streaming tool turns hit proxy
timeouts.

**Q5. Does Linkflow support `cached_tokens` / prompt caching?**
The SDK `usage` object has `input_tokens_details.cached_tokens` — in T7 it was 0. Either Linkflow doesn't proxy caching, or it does but didn't trigger on these tests. Worth a focused test: send the same large `input` twice in a row, see if the second has non-zero `cached_tokens`. If yes, this dramatically changes repeated-turn cost and may improve latency.

**Q6. Adjudicator behavior with tools.**
Recommendation: do not give tools to the adjudicator in the first refactor. The
current architecture has a scoped Adjudicator LLM call for soft flags
([pipeline/llm/adjudicate.py](../pipeline/llm/adjudicate.py)); its role is to
verdict a fixed extraction, not search or rewrite.

**Q7. Streaming for the extractor — keep or drop?**
The current pipeline uses streaming partly because Linkflow has a non-streaming proxy timeout (`STREAMING_TIMEOUT=300s`). Tool-bearing turns add latency from the round-trip; if total extraction takes > 300s and we use non-streaming, we hit the timeout. **Two options:**
- Use streaming throughout, eat the SDK accumulator bug, reconstruct tool calls from deltas.
- Use streaming for the turns that are pure-message generation, non-streaming for tool-result follow-ups.
Test on a real reference deal to find out which path actually completes within budget.

**Q8. Historical state-vs-truth inconsistency from the prior run batch.**
The exact live drift described in the original report is no longer present:
current state/output/latest audit pointers align for all nine reference deals.
However, historical run IDs from the earlier drift still appear in progress
history / `flags.jsonl` without corresponding immutable audit run directories.
Current `pipeline.reconcile --scope reference` catches live mismatches but not
historical run-history integrity. Decide whether the refactor should add a
historical audit-integrity check.

---

## 9. How to reproduce / extend

### Run the experiment scripts

The empirical record lives in the worktree (NOT main):
```
/Users/austinli/bids_try/.claude/worktrees/agent-a82dc1e8cd9f212bc/
  experiments/
    .env                               # API key, gitignored
    scripts/
      common.py                        # shared SDK helpers
      t1_baseline.py
      t2_strict_schema.py
      t3_json_mode.py
      t4_tool_call.py
      t5_tool_roundtrip.py
      t6_streaming_tools.py
      t7_e2e_medivation.py
    results/
      t7_log.txt                       # T7 stdout
      t7_results.json                  # T7 raw outputs (extraction A & B)
```

Run any test:
```bash
cd /Users/austinli/bids_try/.claude/worktrees/agent-a82dc1e8cd9f212bc
python experiments/scripts/t2_strict_schema.py     # quick (~5s)
python experiments/scripts/t7_e2e_medivation.py    # ~90s, runs both A & B
```

The worktree auto-loads `experiments/.env`. To run elsewhere:
```bash
export OPENAI_API_KEY="<your linkflow key>"
export OPENAI_BASE_URL="https://www.linkflow.run/v1"
export EXTRACT_MODEL="gpt-5.5"
```

### Codex T9 scratch artifacts

The full-input JSON-format probe wrote sanitized scratch artifacts here:

```text
/tmp/bids_try_linkflow_json_probe_codex/results.json
/tmp/bids_try_linkflow_json_probe_codex/notes.md
```

These files intentionally contain no raw filing text, raw model output, or API
keys. They are useful as empirical evidence for the refactor designer, but they
are not live repo contracts.

### Recommended next implementation experiments

1. Run the actual full `SCHEMA_R1` strict-schema call through Linkflow on one or
   two reference deals. T9 used a small schema; production needs the real shape.
2. Adapt `t7_e2e_medivation.py` to Providence with the full Background payload
   and a fuller `validate_row` mirroring row-level checks (§P-R2, §P-R9, §P-G2,
   §P-D5/D6/D8). Confirm Providence-style non-Bid bid-economics errors are
   caught by either `validate_row` or the outer `validate_extraction` repair loop.
3. Build a minimal `find_in_filing` prototype and test it on PetSmart buyer-group
   constituents. Use page numbers from `pages.json`, not array offsets.
4. Prototype the outer validation-repair loop on `zep` and `petsmart-inc`, the
   current validated reference blockers.

Expected outcome: the refactor should reduce hard flags by making structural
errors impossible under schema and by giving the model deterministic feedback
before finalization.

### Where to integrate

- [pipeline/llm/extract.py](../pipeline/llm/extract.py) — add the `tools=...` param and the multi-turn loop
- [pipeline/llm/audit.py](../pipeline/llm/audit.py) — add `tool_calls.jsonl` writer
- [pipeline/core.py](../pipeline/core.py) — extract reusable validation helpers for row-level and whole-draft tools without changing final validator authority
- [pipeline/llm/response_format.py](../pipeline/llm/response_format.py) — harden `SCHEMA_R1` for provider strict schema and local validation
- [pipeline/llm/client.py](../pipeline/llm/client.py) — allow Linkflow strict schema and native tool calls under the new contract
- [pipeline/run_pool.py](../pipeline/run_pool.py) — orchestrate strict schema, tool/repair settings, audit manifest fields, cache invalidation, and final validation

---

## 10. Decision points for Austin

Some original decision points are now resolved by Austin's "best result over
cost" direction:

**D1. Roll out tools to extractor only, or also to adjudicator?**
Resolved recommendation: extractor only for the first refactor. Keep the
Adjudicator scoped and tool-free.

**D2. Re-enable strict json_schema together with tools, or separately?**
Resolved recommendation: design both into the target architecture, but implement
in separable commits if possible: strict schema first, then tools, then
validation-repair loop. The production target should include all three.

**D3. Tool safety caps.**
Cost caps should not drive behavior. Use safety caps only to prevent infinite
loops or pathological provider behavior. If a cap is hit, fail loudly into audit
rather than silently finalizing a known-bad extraction.

**D4. PetSmart consortium policy.**
The PetSmart hards include model self-flags, not purely validator-enforced
failures. Three options remain:
- **Atomize:** add `find_in_filing` and require the model to back-fill Buyer Group rows with the merger-agreement constituents. Cleaner data, more effort.
- **Allow placeholder:** document Buyer Group as an acceptable bidder_alias when the bidding-narrative slice doesn't name constituents; tell the model to stop self-flagging this case at hard severity.
- **Hand-verify:** accept `validated`, move to manual `verified` adjudication for this deal.

Best-result recommendation: prototype `find_in_filing` and attempt atomization
first. If the filing support is genuinely outside the extractor scope or creates
rulebook tension, document the rule decision explicitly in `rules/`.

**D5. State-vs-truth drift (Q8 above).**
The exact live drift is stale, but historical run IDs without immutable audit
dirs remain suspicious. Recommendation: add a historical audit-integrity mode to
reconcile or stability before relying on old archives for the reference gate.

---

## 11. What this report does NOT cover

- Any test of `find_in_filing` (filing search tool). The PetSmart Buyer Group hypothesis is unverified.
- Production strict schema using the complete `SCHEMA_R1` extraction shape. T9 tested strict schema transport on full inputs, not the whole extraction schema.
- Tool-loop behavior on full extraction prompts. T7 used a trimmed 4-page prompt; T9 used full inputs but did not use tools.
- Prompt caching support on Linkflow (`cached_tokens` was 0 in T7; could be inactive or unsupported).
- Adjudicator-side tool use (deliberately scoped out per the design discussion).
- Whether the Linkflow proxy preserves tool-call ordering under high concurrency (workers > 1). Tested only with single-worker.
- Stability across many runs. T1–T7 each ran 1–2 times. Production reliability needs N×9 reference deals.

---

## 12. TL;DR for the next agent

1. **Design for best extraction quality, not token cost.** Austin explicitly does not want cost to be the deciding constraint.
2. **Strict `json_schema` through Linkflow works now, including full Background payloads.** T9 passed on Providence, PetSmart, and Medivation full inputs.
3. **Do not use `json_object` as fallback.** It failed with fast 502s on every full-input T9 probe; fallback should be prompt-only JSON plus Python validation.
4. **Native function calling on Linkflow + `gpt-5.5` works.** Use full-input replay, not `previous_response_id`.
5. **Target architecture:** strict schema + extractor-only tools + outer Python validation-repair loop + final Python validation.
6. **Recommended tools:** `validate_row`, `validate_extraction`, `verify_quote`, `find_in_filing`, and `lookup_rule`.
7. **Keep Adjudicator scoped and tool-free** for the first refactor.
8. **Current repo health:** current reference state/output/latest audit pointers align, but `pipeline.reconcile --scope reference` fails due loose legacy audit files plus current validated blockers `zep` and `petsmart-inc`.
9. **Integration targets:** [pipeline/llm/extract.py](../pipeline/llm/extract.py), [pipeline/llm/client.py](../pipeline/llm/client.py), [pipeline/llm/response_format.py](../pipeline/llm/response_format.py), [pipeline/llm/audit.py](../pipeline/llm/audit.py), [pipeline/core.py](../pipeline/core.py), and [pipeline/run_pool.py](../pipeline/run_pool.py).

Pick this up at §6 to design the refactor. Use §8 only as the verification
checklist for experiments that should accompany implementation.
