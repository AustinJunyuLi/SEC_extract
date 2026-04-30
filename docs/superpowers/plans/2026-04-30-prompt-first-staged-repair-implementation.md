# Prompt-First Staged Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace first-pass LLM tool use with prompt-only extraction, prompt-only repair 1, and targeted repair tools only on repair 2.

**Architecture:** The extractor will make a single strict structured-output prompt-only call for the initial draft. If Python validation raises hard flags, repair 1 is also prompt-only; repair 2, and only repair 2, exposes `search_filing`, `get_pages`, and `check_row`. No fallback modes, compatibility shims, or old tool-heavy entrypoints remain.

**Tech Stack:** Python 3, `AsyncOpenAI` Responses API, strict `text.format=json_schema`, pytest, repo-local audit/state contracts.

---

## Scope And Non-Negotiables

- Do not add a CLI flag to preserve the old first-pass tool path.
- Do not keep compatibility readers or aliases for retired audit contracts.
- Do not implement free-form JSON fallback or patch-style repair output.
- Do not leave stale docs describing first-pass tools as live behavior.
- Do not delete or revert unrelated dirty worktree changes.
- Use `apply_patch` for manual edits.
- After implementation, run a hard cleanup sweep for stale prose, stale tests, stale constants, and dead code.

## File Map

- Modify `pipeline/llm/tools.py`: replace generic `TOOL_DEFINITIONS` with `TARGETED_REPAIR_TOOL_DEFINITIONS`; keep `check_row`, `search_filing`, `get_pages`, and `dispatch`.
- Modify `pipeline/llm/extract.py`: add prompt-only call path; restrict tool calls to repair 2; record `tool_mode` in repair audit.
- Modify `pipeline/run_pool.py`: add manifest fields `extract_tool_mode` and `repair_strategy`; keep cache fail-closed through changed contract hashes.
- Modify `pipeline/llm/contracts.py`: no functional change expected, but verify repair contract hash changes because `run_repair_loop` source changes.
- Modify `prompts/extract.md`: remove first-pass tool instructions and `check_row` mandate.
- Modify `prompts/repair.md`: document staged repair modes and repair-2 targeted tool rules.
- Modify `AGENTS.md`, `CLAUDE.md`, `SKILL.md`, `docs/linkflow-extraction-guide.md`: update the live architecture contract.
- Modify `rules/events.md` or `rules/invariants.md`: add a Zep-style §L2 example clarifying stale-side episodes.
- Modify `tests/llm/test_tools.py`: assert targeted repair tool catalog and keep dispatch tests.
- Modify `tests/llm/test_extract.py`: assert prompt-only extraction and staged repair tool behavior.
- Modify `tests/test_run_pool.py`: assert manifest fields and stale cache rejection.
- Modify `tests/test_prompt_contract.py`: assert prompt/docs no longer describe first-pass tool use.
- Modify `tests/test_invariants.py` or create `tests/test_zep_phase_regression.py`: add the Zep interval regression.

---

### Task 1: Update Tool Catalog Tests

**Files:**
- Modify: `tests/llm/test_tools.py`
- Modify later in Task 2: `pipeline/llm/tools.py`

- [ ] **Step 1: Replace the tool catalog test**

In `tests/llm/test_tools.py`, replace the existing `test_tool_definitions_include_expected_tools` with this test:

```python
def test_targeted_repair_tool_definitions_include_expected_tools_only():
    names = {tool["name"] for tool in tools.TARGETED_REPAIR_TOOL_DEFINITIONS}

    assert names == {"check_row", "search_filing", "get_pages"}
```

- [ ] **Step 2: Add a test that there is no generic first-pass tool catalog**

Add this test near the tool-definition test:

```python
def test_no_generic_extractor_tool_catalog_is_exposed():
    assert not hasattr(tools, "TOOL_DEFINITIONS")
```

- [ ] **Step 3: Keep dispatch tests for all three tools**

Keep the existing tests that call:

```python
tools.dispatch(name="check_row", arguments={"row": _clean_bid_row()}, filing_pages=_filing_pages())
tools.dispatch(name="search_filing", arguments={"query": "page text", "page_range": None, "max_hits": 5}, filing_pages=_filing_pages())
tools.dispatch(name="get_pages", arguments={"start_page": 1, "end_page": 1}, filing_pages=_filing_pages())
```

If the file does not already include `search_filing` and `get_pages` dispatch tests, add:

```python
def test_dispatch_invokes_search_filing():
    result = tools.dispatch(
        name="search_filing",
        arguments={"query": "page text", "page_range": None, "max_hits": 5},
        filing_pages=_filing_pages(),
    )

    assert result["hits"]
    assert result["hits"][0]["page"] == 1


def test_dispatch_invokes_get_pages():
    result = tools.dispatch(
        name="get_pages",
        arguments={"start_page": 1, "end_page": 1},
        filing_pages=_filing_pages(),
    )

    assert result["pages"] == [{"page": 1, "text": "page text"}]
```

- [ ] **Step 4: Run the targeted test and verify it fails**

Run:

```bash
pytest tests/llm/test_tools.py::test_targeted_repair_tool_definitions_include_expected_tools_only tests/llm/test_tools.py::test_no_generic_extractor_tool_catalog_is_exposed -q
```

Expected: fails because `TARGETED_REPAIR_TOOL_DEFINITIONS` does not exist and `TOOL_DEFINITIONS` still exists.

- [ ] **Step 5: Commit the failing tests**

```bash
git add tests/llm/test_tools.py
git commit -m "test: specify targeted repair tool catalog"
```

---

### Task 2: Implement Targeted Repair Tool Catalog

**Files:**
- Modify: `pipeline/llm/tools.py`
- Test: `tests/llm/test_tools.py`

- [ ] **Step 1: Rename the exposed catalog**

In `pipeline/llm/tools.py`, replace:

```python
TOOL_DEFINITIONS: list[dict[str, Any]] = [
    CHECK_ROW_SCHEMA,
    SEARCH_FILING_SCHEMA,
    GET_PAGES_SCHEMA,
]
```

with:

```python
TARGETED_REPAIR_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    CHECK_ROW_SCHEMA,
    SEARCH_FILING_SCHEMA,
    GET_PAGES_SCHEMA,
]
```

- [ ] **Step 2: Tighten the `check_row` tool description**

In `CHECK_ROW_SCHEMA`, replace the description string with:

```python
"Validate a single proposed extraction event row against the row-local "
"rulebook (P-R0/R2/R3/R4/R6/R7/R8/R9, P-D1/D2/D7, P-G2). "
"Returns ok=true if the row passes all checks, otherwise ok=false "
"with a violations list naming each broken rule. Registry-dependent "
"P-R5 runs in the full validator. In the live pipeline this tool is "
"available only during repair 2 and should be used only for hard-flagged, "
"revised, or revision-dependent rows."
```

- [ ] **Step 3: Update the tool contract hash**

In `tools_contract_version()`, replace:

```python
"definitions": TOOL_DEFINITIONS,
```

with:

```python
"definitions": TARGETED_REPAIR_TOOL_DEFINITIONS,
```

- [ ] **Step 4: Verify no old catalog name remains**

Run:

```bash
rg -n "TOOL_DEFINITIONS" pipeline/llm/tools.py tests/llm/test_tools.py
```

Expected: no output.

- [ ] **Step 5: Run the tool tests**

Run:

```bash
pytest tests/llm/test_tools.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add pipeline/llm/tools.py tests/llm/test_tools.py
git commit -m "refactor: expose targeted repair tool catalog"
```

---

### Task 3: Specify Prompt-Only Extraction Tests

**Files:**
- Modify: `tests/llm/test_extract.py`
- Modify later in Task 4: `pipeline/llm/extract.py`

- [ ] **Step 1: Update the first-pass extraction test expectations**

In `test_extract_deal_writes_audit_and_tracks_token_usage`, replace:

```python
assert client.calls[0]["tools"]
assert client.calls[0]["tool_choice"] == "auto"
assert client.calls[0]["stream"] is True
```

with:

```python
assert "tools" not in client.calls[0] or client.calls[0]["tools"] is None
assert "tool_choice" not in client.calls[0] or client.calls[0]["tool_choice"] is None
assert client.calls[0]["stream"] is True
```

- [ ] **Step 2: Replace the first-pass tool replay test with a repair-2 replay test**

Delete `test_extract_runs_tool_calls_and_replays_until_final_message`.

Add this test in its place:

```python
def test_repair_second_turn_runs_targeted_tools_after_prompt_only_repair_fails(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    prompts = env.tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "extract.md").write_text("PROMPT")
    (prompts / "repair.md").write_text(
        "REPORT {validator_report}\nROWS {affected_rows}\nSNIPPETS {filing_snippets}"
    )
    for name in extract.EXTRACTOR_RULE_FILES:
        (env.rules / name).write_text(f"RULE {name}")
    env.seed_filing("synthetic", pages=background_section_pages("page text"))
    monkeypatch.setattr(extract.core, "PROMPTS_DIR", prompts)

    invalid_validation = extract.core.ValidatorResult(
        row_flags=[
            {
                "row_index": 0,
                "code": "source_quote_not_in_page",
                "severity": "hard",
                "reason": "bad quote",
            }
        ],
        deal_flags=[],
    )
    fixed_validation = extract.core.ValidatorResult(row_flags=[], deal_flags=[])
    validations = iter([invalid_validation, fixed_validation])

    def fake_prepare(slug, raw, filing):
        return raw, filing, []

    def fake_validate(prepared, filing):
        return next(validations)

    monkeypatch.setattr(extract.core, "prepare_for_validate", fake_prepare)
    monkeypatch.setattr(extract.core, "validate", fake_validate)

    final_payload = {
        "deal": {
            "TargetName": "Synthetic Target",
            "Acquirer": "Synthetic Buyer",
            "DateAnnounced": "2026-04-24",
            "DateEffective": None,
            "auction": False,
            "all_cash": True,
            "target_legal_counsel": None,
            "acquirer_legal_counsel": None,
            "bidder_registry": {},
            "deal_flags": [],
        },
        "events": [],
    }
    tool_call = {
        "type": "function_call",
        "name": "search_filing",
        "call_id": "call-search",
        "arguments": json.dumps({"query": "page text", "page_range": None, "max_hits": 5}),
    }

    class RepairClient:
        def __init__(self):
            self.calls = []

        async def complete(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                return CompletionResult(
                    text=json.dumps(final_payload),
                    model=kwargs["model"],
                    input_tokens=2,
                    output_tokens=3,
                )
            if len(self.calls) == 2:
                return CompletionResult(
                    text="",
                    model=kwargs["model"],
                    tool_calls=[tool_call],
                    output_items=[tool_call],
                    input_tokens=5,
                    output_tokens=7,
                )
            return CompletionResult(
                text=json.dumps(final_payload),
                model=kwargs["model"],
                input_tokens=11,
                output_tokens=13,
            )

    audit = _audit_writer(env.tmp_path)
    usage = TokenUsage()
    client = RepairClient()
    filing = extract.core.load_filing("synthetic")

    revised, validation, promotion_log, outcome, turns = asyncio.run(
        extract.run_repair_loop(
            slug="synthetic",
            initial_draft=final_payload,
            filing=filing,
            validation=invalid_validation,
            llm_client=client,
            extract_model="test-model",
            audit=audit,
            token_usage=usage,
            reasoning_effort="high",
        )
    )

    assert revised == final_payload
    assert validation is fixed_validation
    assert promotion_log == []
    assert outcome == "fixed"
    assert turns == 2
    assert "tools" not in client.calls[0] or client.calls[0]["tools"] is None
    repair_2_tools = {tool["name"] for tool in client.calls[1]["tools"]}
    assert repair_2_tools == {"check_row", "search_filing", "get_pages"}
    assert client.calls[1]["tool_choice"] == "auto"
    repair_turns = [
        json.loads(line)
        for line in (audit.root / "repair_turns.jsonl").read_text().splitlines()
    ]
    assert [row["tool_mode"] for row in repair_turns] == ["none", "targeted_repair_tools"]
    assert repair_turns[-1]["tool_calls_count"] == 1
```

- [ ] **Step 3: Add a repair failure audit test**

Add this test below the repair-2 replay test:

```python
def test_repair_records_failed_turn_before_reraising(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    prompts = env.tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "extract.md").write_text("PROMPT")
    (prompts / "repair.md").write_text(
        "REPORT {validator_report}\nROWS {affected_rows}\nSNIPPETS {filing_snippets}"
    )
    for name in extract.EXTRACTOR_RULE_FILES:
        (env.rules / name).write_text(f"RULE {name}")
    env.seed_filing("synthetic", pages=background_section_pages("page text"))
    monkeypatch.setattr(extract.core, "PROMPTS_DIR", prompts)

    validation = extract.core.ValidatorResult(
        row_flags=[{"row_index": 0, "code": "bad", "severity": "hard", "reason": "bad"}],
        deal_flags=[],
    )

    class FailingRepairClient:
        async def complete(self, **kwargs):
            raise RuntimeError("repair provider failed")

    audit = _audit_writer(env.tmp_path)
    filing = extract.core.load_filing("synthetic")

    try:
        asyncio.run(
            extract.run_repair_loop(
                slug="synthetic",
                initial_draft={"deal": {}, "events": []},
                filing=filing,
                validation=validation,
                llm_client=FailingRepairClient(),
                extract_model="test-model",
                audit=audit,
                token_usage=TokenUsage(),
            )
        )
    except RuntimeError as exc:
        assert "repair provider failed" in str(exc)
    else:
        raise AssertionError("run_repair_loop should re-raise repair failures")

    repair_record = json.loads((audit.root / "repair_turns.jsonl").read_text().strip())
    assert repair_record["turn"] == 1
    assert repair_record["tool_mode"] == "none"
    assert repair_record["outcome"] == "failed"
    assert repair_record["error"]["type"] == "RuntimeError"
```

- [ ] **Step 4: Run the new/changed tests and verify they fail**

Run:

```bash
pytest tests/llm/test_extract.py::test_extract_deal_writes_audit_and_tracks_token_usage tests/llm/test_extract.py::test_repair_second_turn_runs_targeted_tools_after_prompt_only_repair_fails tests/llm/test_extract.py::test_repair_records_failed_turn_before_reraising -q
```

Expected: fails because extraction still passes tools on the first call and repair does not record `tool_mode`.

- [ ] **Step 5: Commit the failing tests**

```bash
git add tests/llm/test_extract.py
git commit -m "test: specify prompt-first staged repair"
```

---

### Task 4: Implement Prompt-Only Extraction And Staged Repair

**Files:**
- Modify: `pipeline/llm/extract.py`
- Test: `tests/llm/test_extract.py`

- [ ] **Step 1: Update imports**

In `pipeline/llm/extract.py`, replace:

```python
from .tools import TOOL_DEFINITIONS, dispatch
```

with:

```python
from .tools import TARGETED_REPAIR_TOOL_DEFINITIONS, dispatch
```

- [ ] **Step 2: Add `_call_prompt_only` above `_call_with_tools`**

Add this function before `_call_with_tools`:

```python
async def _call_prompt_only(
    *,
    llm_client: LLMClient,
    model: str,
    system: str,
    user: str,
    max_output_tokens: int | None,
    reasoning_effort: str | None,
) -> tuple[dict[str, Any], CompletionResult, list[CompletionResult], int]:
    input_items: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    completion = await llm_client.complete(
        model=model,
        input_items=input_items,
        text_format=json_schema_format(SCHEMA_R1),
        max_output_tokens=max_output_tokens,
        reasoning_effort=reasoning_effort,
        stream=True,
    )
    parsed = parse_json_text(completion.text)
    _ensure_extraction_shape(parsed)
    completion.parsed_json = parsed
    return parsed, completion, [completion], 0
```

- [ ] **Step 3: Parameterize `_call_with_tools`**

Change the `_call_with_tools` signature by adding `tool_definitions`:

```python
    tool_definitions: list[dict[str, Any]],
```

Then replace the `llm_client.complete` tool arguments inside `_call_with_tools` with:

```python
            tools=tool_definitions,
            tool_choice="auto",
```

- [ ] **Step 4: Make `extract_deal` prompt-only**

In `extract_deal`, replace the `_call_with_tools(...)` call with:

```python
        parsed, completion, completions, tool_calls_count = await _call_prompt_only(
            llm_client=llm_client,
            system=system,
            user=user,
            model=extract_model,
            max_output_tokens=max_output_tokens,
            reasoning_effort=reasoning_effort,
        )
```

Confirm `filing_pages = _load_tool_pages(slug)` is no longer needed in `extract_deal`; remove that assignment.

- [ ] **Step 5: Make `run_repair_loop` staged**

Inside `run_repair_loop`, replace the unconditional `_call_with_tools(...)` block with:

```python
        tool_mode = "none" if turn == 1 else "targeted_repair_tools"
        try:
            if turn == 1:
                revised, _completion, completions, _tool_calls_count = await _call_prompt_only(
                    llm_client=llm_client,
                    model=extract_model,
                    system=system,
                    user=repair_user,
                    max_output_tokens=max_output_tokens,
                    reasoning_effort=reasoning_effort,
                )
            else:
                revised, _completion, completions, _tool_calls_count = await _call_with_tools(
                    llm_client=llm_client,
                    model=extract_model,
                    system=system,
                    user=repair_user,
                    filing_pages=filing_pages,
                    max_output_tokens=max_output_tokens,
                    reasoning_effort=reasoning_effort,
                    audit=audit,
                    audit_phase=f"repair_{turn}",
                    tool_definitions=TARGETED_REPAIR_TOOL_DEFINITIONS,
                )
        except Exception as exc:
            audit.write_repair_turn({
                "turn": turn,
                "tool_mode": tool_mode,
                "validator_report_summary": report,
                "hard_flags_before": report["hard_count"],
                "hard_flags_after": None,
                "tool_calls_count": 0,
                "completion_turns": 0,
                "outcome": "failed",
                "error": {"type": type(exc).__name__, "message": str(exc)[:500]},
            })
            raise
```

Then add `"tool_mode": tool_mode,` to the successful `audit.write_repair_turn({...})` payload.

- [ ] **Step 6: Verify there is no first-pass tool catalog import**

Run:

```bash
rg -n "TOOL_DEFINITIONS|tools=TARGETED_REPAIR_TOOL_DEFINITIONS|tool_definitions=TARGETED_REPAIR_TOOL_DEFINITIONS" pipeline/llm/extract.py
```

Expected output includes `tool_definitions=TARGETED_REPAIR_TOOL_DEFINITIONS` only for repair 2 and no `TOOL_DEFINITIONS`.

- [ ] **Step 7: Run extraction tests**

Run:

```bash
pytest tests/llm/test_extract.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add pipeline/llm/extract.py tests/llm/test_extract.py
git commit -m "feat: use prompt-first staged repair"
```

---

### Task 5: Add Manifest Contract Tests

**Files:**
- Modify: `tests/test_run_pool.py`
- Modify later in Task 6: `pipeline/run_pool.py`

- [ ] **Step 1: Add manifest field assertions to a successful process test**

Find the test that exercises a successful `process_deal` or add this test near other run-pool audit tests:

```python
from pipeline.llm.client import CompletionResult
from pipeline.llm.extract import ExtractResult


def test_success_manifest_records_prompt_first_repair_strategy(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    env.seed_deal("a", is_reference=True, status="pending", rulebook_version="rules-v1")
    monkeypatch.setattr(run_pool.core, "rulebook_version", lambda: "rules-v1")

    async def fake_extract(*args, **kwargs):
        raw = {
            "deal": {
                "TargetName": "A",
                "Acquirer": "B",
                "DateAnnounced": None,
                "DateEffective": None,
                "auction": False,
                "all_cash": None,
                "target_legal_counsel": None,
                "acquirer_legal_counsel": None,
                "bidder_registry": {},
                "deal_flags": [],
            },
            "events": [],
        }
        return ExtractResult(
            raw_extraction=raw,
            completion=CompletionResult(
                text=json.dumps(raw),
                model="test-model",
                input_tokens=1,
                output_tokens=1,
            ),
            rulebook_version="rules-v1",
            tool_calls_count=0,
        )

    def fake_prepare(slug, raw, filing):
        return raw, filing, []

    def fake_validate(prepared, filing):
        return run_pool.core.ValidatorResult(row_flags=[], deal_flags=[])

    class FinalizeResult:
        status = "passed_clean"
        flag_count = 0
        notes = "hard=0 soft=0 info=0"
        output_path = env.tmp_path / "output" / "extractions" / "a.json"

    def fake_finalize_prepared(slug, prepared, filing, validation, promotion_log, run_id):
        FinalizeResult.output_path.parent.mkdir(parents=True, exist_ok=True)
        FinalizeResult.output_path.write_text(json.dumps(prepared))
        return FinalizeResult()

    monkeypatch.setattr(run_pool, "extract_deal", fake_extract)
    monkeypatch.setattr(run_pool.core, "load_filing", lambda slug: run_pool.core.Filing(slug=slug, pages=[]))
    monkeypatch.setattr(run_pool.core, "prepare_for_validate", fake_prepare)
    monkeypatch.setattr(run_pool.core, "validate", fake_validate)
    monkeypatch.setattr(run_pool.core, "finalize_prepared", fake_finalize_prepared)

    summary = asyncio.run(
        run_pool.run_pool(
            _cfg(slugs=("a",), audit_root=env.tmp_path / "output" / "audit"),
            llm_client=object(),
        )
    )

    manifest = json.loads((summary.outcomes[0].audit_path / "manifest.json").read_text())
    assert manifest["extract_tool_mode"] == "none"
    assert manifest["repair_strategy"] == "prompt_then_targeted_tools"
```

- [ ] **Step 2: Add cache rejection for old strategy manifests**

In `test_skip_decisions_and_cache_policy`, after the valid revalidate assertion, mutate the manifest:

```python
    manifest = json.loads((audit / "manifest.json").read_text())
    manifest["repair_strategy"] = "prompt_then_filing_tools"
    (audit / "manifest.json").write_text(json.dumps(manifest))
    decision = run_pool.decide_skip("done", _cfg(re_validate=True, audit_root=cfg.audit_root), current, state)
    assert decision.action == "blocked"
    assert "repair_strategy" in decision.reason
```

- [ ] **Step 3: Run and verify failure**

Run:

```bash
pytest tests/test_run_pool.py::test_success_manifest_records_prompt_first_repair_strategy tests/test_run_pool.py::test_skip_decisions_and_cache_policy -q
```

Expected: fails because manifest fields are not written and cache contracts do not include `repair_strategy`.

- [ ] **Step 4: Commit failing tests**

```bash
git add tests/test_run_pool.py
git commit -m "test: require prompt-first audit contract"
```

---

### Task 6: Implement Manifest Contract Fields

**Files:**
- Modify: `pipeline/run_pool.py`
- Test: `tests/test_run_pool.py`

- [ ] **Step 1: Add constants near existing defaults**

In `pipeline/run_pool.py`, below `DEFAULT_REASONING_EFFORT = "xhigh"`, add:

```python
EXTRACT_TOOL_MODE = "none"
REPAIR_STRATEGY = "prompt_then_targeted_tools"
```

- [ ] **Step 2: Include manifest fields in cache contract values**

In `_current_contract_values`, return:

```python
    return {
        "rulebook_version": current_rulebook_version,
        "extractor_contract_version": extractor_contract_version(),
        "tools_contract_version": tools_contract_version(),
        "repair_loop_contract_version": repair_loop_contract_version(),
        "extract_tool_mode": EXTRACT_TOOL_MODE,
        "repair_strategy": REPAIR_STRATEGY,
    }
```

- [ ] **Step 3: Include manifest fields in `_manifest_payload`**

In the dict returned by `_manifest_payload`, add:

```python
        "extract_tool_mode": EXTRACT_TOOL_MODE,
        "repair_strategy": REPAIR_STRATEGY,
```

Place these near `api_endpoint` and `reasoning_efforts` so audit readers see them early.

- [ ] **Step 4: Update `_write_audit_manifest` helper in tests**

In `tests/test_run_pool.py`, update `_write_audit_manifest` so it writes:

```python
        "extract_tool_mode": run_pool.EXTRACT_TOOL_MODE,
        "repair_strategy": run_pool.REPAIR_STRATEGY,
```

- [ ] **Step 5: Run run-pool tests**

Run:

```bash
pytest tests/test_run_pool.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add pipeline/run_pool.py tests/test_run_pool.py
git commit -m "feat: stamp prompt-first audit contract"
```

---

### Task 7: Update Prompts And Prompt Contract Tests

**Files:**
- Modify: `prompts/extract.md`
- Modify: `prompts/repair.md`
- Modify: `tests/test_prompt_contract.py`

- [ ] **Step 1: Update prompt contract test for first-pass no-tools**

In `test_extractor_prompt_contract_describes_embedded_filing_text`, replace tool assertions:

```python
    assert "## Tools available to you" in text
    assert "`check_row(row)`" in text
    assert "`search_filing(query, page_range, max_hits)`" in text
    assert "`get_pages(start_page, end_page)`" in text
```

with:

```python
    assert "No tools are available during initial extraction" in text
    assert "`check_row(row)`" not in text
    assert "`search_filing(query, page_range, max_hits)`" not in text
    assert "`get_pages(start_page, end_page)`" not in text
```

Also replace:

```python
    assert "return exactly one raw JSON object" in text
```

with:

```python
    assert "Return exactly one raw JSON object" in text
```

Add these assertions:

```python
    assert "Always call `check_row`" not in text
    assert "After tool calls return" not in text
```

- [ ] **Step 2: Add repair prompt contract test**

Add this test:

```python
def test_repair_prompt_documents_staged_tool_modes():
    text = (REPO_ROOT / "prompts" / "repair.md").read_text()

    assert "Repair turn 1 has no tools" in text
    assert "Repair turn 2 may use targeted repair tools" in text
    assert "`check_row` only for hard-flagged rows" in text
    assert "Do not emit patches or partial output" in text
```

- [ ] **Step 3: Update `prompts/extract.md`**

Replace the opening paragraph:

```markdown
After any tool use is complete, return exactly one raw JSON object with
top-level keys `deal` and `events`. Do not include prose, markdown fences,
comments, or alternate top-level envelopes in the final answer.
```

with:

```markdown
Return exactly one raw JSON object with top-level keys `deal` and `events`.
Do not include prose, markdown fences, comments, or alternate top-level
envelopes in the final answer.
```

Replace the input boundary sentence:

```markdown
Use only those embedded
pages plus text returned by the deterministic filing tools below. Do not fetch from SEC/EDGAR,
```

with:

```markdown
Use only those embedded pages. No tools are available during initial
extraction. Do not fetch from SEC/EDGAR,
```

Delete the entire `## Tools available to you` section from `prompts/extract.md`, from the heading through:

```markdown
After tool calls return, emit the final `{deal, events}` JSON body matching
SCHEMA_R1.
```

Delete this paragraph:

```markdown
Always call `check_row` on every row before submitting it. The tool will catch
§P-R9 violations.
```

In the final verification checklist, replace:

```markdown
1. You called `check_row` on every emitted event row and each result was
   `ok=true`.
```

with:

```markdown
1. Every emitted event row satisfies the row-local field ownership and evidence
   requirements that Python validation will enforce.
```

- [ ] **Step 4: Update `prompts/repair.md`**

Replace the `## Rules and tools` section with:

```markdown
## Repair turn modes

Repair turn 1 has no tools. Use the validator report, affected rows, and filing
snippets in this prompt to emit the complete revised `{deal, events}` JSON.

Repair turn 2 may use targeted repair tools if hard flags remain after repair
turn 1:

- `check_row` only for hard-flagged rows, directly revised rows, and rows whose
  validity depends on those revisions.
- `search_filing` for targeted evidence lookup.
- `get_pages` for page context after targeted search or when a cited page needs
  surrounding context.

The same SCHEMA_R1 contract applies in both repair turns. After any repair-2
tool calls, emit the complete revised `{deal, events}` JSON.
```

- [ ] **Step 5: Run prompt tests and verify pass**

Run:

```bash
pytest tests/test_prompt_contract.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add prompts/extract.md prompts/repair.md tests/test_prompt_contract.py
git commit -m "docs: make extractor prompt-first"
```

---

### Task 8: Update Live Architecture Docs

**Files:**
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `SKILL.md`
- Modify: `docs/linkflow-extraction-guide.md`
- Test: `tests/test_prompt_contract.py`

- [ ] **Step 1: Add stale-doc assertions**

In `tests/test_prompt_contract.py`, extend `test_live_contract_files_do_not_carry_stale_rule_prose` with these banned substrings:

```python
        "strict Extractor + tools",
        "Every extractor call uses **strict `text.format=json_schema`** with the hardened `SCHEMA_R1`, plus three native function-calling tools",
        "The model has three native function-calling tools while drafting",
        "Always call `check_row`",
        "call `check_row` on every event row",
        "first-pass tool use",
        "prompt_then_filing_tools",
```

- [ ] **Step 2: Update top-level architecture prose**

In `AGENTS.md`, `CLAUDE.md`, and `SKILL.md`, replace the architecture summary with this language:

```markdown
The live architecture is code-orchestrated direct `AsyncOpenAI` SDK calls to
the Responses streaming endpoint (`responses.stream`) through the
Linkflow/NewAPI-compatible `OPENAI_BASE_URL`. Configure it with
`OPENAI_BASE_URL` and `OPENAI_API_KEY`; model names come from `EXTRACT_MODEL`
and `ADJUDICATE_MODEL` or CLI overrides.

Every full extraction body uses strict `text.format=json_schema` with the
hardened `SCHEMA_R1`. The first extraction pass is prompt-only: no native tools
are supplied to the model. Python `pipeline.core.validate()` is the
authoritative deterministic validator.

If hard flags remain, the repair loop is staged. Repair turn 1 is prompt-only.
If hard flags still remain, repair turn 2 exposes only targeted repair tools:
`check_row`, `search_filing`, and `get_pages`. The model must still return a
complete revised `{deal, events}` extraction, not patches. On cap-hit,
finalization records `repair_loop_exhausted` and the deal status is
`validated`.
```

- [ ] **Step 3: Update architecture diagrams**

In the same files, replace the old extraction diagram segment:

```text
  -> Extractor SDK call (strict json_schema + tools)
       parallel function_call → tool dispatch → function_call_output replay
       repeat until model emits final {deal, events}
```

with:

```text
  -> Extractor SDK call (strict json_schema, prompt-only)
       model emits final {deal, events}
```

Replace repair diagram lines with:

```text
  -> if hard flags: staged repair (≤ 2 iterations)
       repair_1 prompt-only
       repair_2 targeted tools only if hard flags remain
       model emits complete revised extraction
```

- [ ] **Step 4: Update `docs/linkflow-extraction-guide.md`**

Rewrite the "Extractor Tools" and "Repair Loop" sections so they state:

```markdown
Initial extraction has no tools. This is intentional: initial tool-output
replay was too expensive under Linkflow because every replay must resend the
full input.

Repair turn 1 also has no tools. Repair turn 2, only when hard flags remain,
exposes `check_row`, `search_filing`, and `get_pages`. `check_row` is targeted
to hard-flagged, revised, or revision-dependent rows; it is not an initial
row-by-row checklist.
```

Keep the individual tool descriptions, but introduce them as repair-2-only
tools.

- [ ] **Step 5: Run doc contract tests**

Run:

```bash
pytest tests/test_prompt_contract.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add AGENTS.md CLAUDE.md SKILL.md docs/linkflow-extraction-guide.md tests/test_prompt_contract.py
git commit -m "docs: update live staged repair contract"
```

---

### Task 9: Add Zep Interval Regression And Rule Example

**Files:**
- Modify: `rules/events.md`
- Modify: `tests/test_invariants.py` or create `tests/test_zep_phase_regression.py`

- [ ] **Step 1: Add the Zep regression test**

Create `tests/test_zep_phase_regression.py` with:

```python
from pipeline import core


def _row(phase, note, date):
    return {
        "process_phase": phase,
        "role": "bidder",
        "bid_note": note,
        "bid_date_precise": date,
    }


def test_zep_2014_abandoned_process_is_stale_when_2015_gap_exceeds_180_days():
    events = [
        _row(0, "Bidder Interest", "2013-07-01"),
        _row(0, "Drop", "2013-08-20"),
        _row(0, "Target Sale", "2014-01-28"),
        _row(0, "NDA", "2014-02-14"),
        _row(0, "Drop", "2014-06-26"),
        _row(1, "Bidder Interest", "2015-02-10"),
        _row(1, "NDA", "2015-02-27"),
        _row(1, "Bid", "2015-03-18"),
        _row(1, "Executed", "2015-04-07"),
    ]

    assert core._invariant_p_l2(events) == []


def test_zep_current_process_single_nda_keeps_auction_false():
    deal = {"auction": False}
    events = [
        _row(0, "NDA", "2014-02-14"),
        _row(1, "NDA", "2015-02-27"),
    ]

    assert core._invariant_p_s2(deal, events) == []


def test_zep_old_bad_split_triggers_stale_prior_interval_flag():
    events = [
        _row(0, "Bidder Interest", "2013-07-01"),
        _row(0, "Drop", "2013-08-20"),
        _row(1, "Target Sale", "2014-01-28"),
        _row(1, "NDA", "2014-02-14"),
        _row(1, "Drop", "2014-06-26"),
        _row(2, "Bidder Interest", "2015-02-10"),
    ]

    flags = core._invariant_p_l2(events)

    assert [flag["code"] for flag in flags] == ["stale_prior_too_recent"]
```

- [ ] **Step 2: Add the rule example**

In `rules/events.md`, in the stale-prior/restart section around §L2, add:

```markdown
**Zep-style abandoned-process example.** If a target runs an abandoned sale
process in 2014 that terminates on June 26, 2014, then re-engages with the
eventual acquirer on February 10, 2015, the 229-day gap separates the abandoned
process from the executed process. The abandoned 2014 process remains
`process_phase = 0`; the 2015 executed process is `process_phase = 1`. Do not
split internal stale-side episodes into phase 1 merely because there are
multiple stale contacts before the executed process. §P-L2 checks the boundary
between stale-prior activity and the current/main process.
```

- [ ] **Step 3: Run the Zep test**

Run:

```bash
pytest tests/test_zep_phase_regression.py -q
```

Expected: pass.

- [ ] **Step 4: Run invariant tests**

Run:

```bash
pytest tests/test_invariants.py tests/test_zep_phase_regression.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add rules/events.md tests/test_zep_phase_regression.py
git commit -m "test: pin zep stale-process interval"
```

---

### Task 10: Hard Clean Stale Code, Tests, Docs, And Audit Language

**Files:**
- Modify any file found by the searches below.
- Delete stale files only when they are obsolete generated notes or retired architecture artifacts.

- [ ] **Step 1: Run stale-code searches**

Run:

```bash
rg -n "TOOL_DEFINITIONS|strict Extractor \\+ tools|Extractor SDK call \\(strict json_schema \\+ tools\\)|Always call `check_row`|call `check_row` on every event row|Tools available to you|After tool calls return|prompt_then_filing_tools|filing_tools only|model has three native function-calling tools|first-pass tool" .
```

Expected: no live-contract or code hits. Hits inside git history are impossible because `rg` does not search git history. Hits inside the new implementation plan are acceptable only where the plan describes stale strings to remove.

- [ ] **Step 2: Fix every live hit from Step 1**

For each live hit:

- If it is code, remove the stale branch or rename the stale symbol.
- If it is a test, update the assertion to the prompt-first staged contract.
- If it is docs, rewrite to the staged contract.
- If it is an obsolete generated report that claims to be a live contract, delete it.

Use exact deletion for obsolete generated reports:

```bash
git rm quality_reports/2026-04-29_design-review.md
```

Only run that `git rm` if the file is still deleted or obsolete in the working tree.

- [ ] **Step 3: Confirm no unwanted compatibility branch exists**

Run:

```bash
rg -n "legacy|compat|fallback|old tool|tool-heavy|first_pass_tools|extract_tool_mode.*tools|--extract-tool|--tool-mode" pipeline tests prompts docs AGENTS.md CLAUDE.md SKILL.md
```

Expected: no code path preserving the old first-pass tool mode. Existing policy prose saying legacy audit layouts are rejected is acceptable.

- [ ] **Step 4: Run formatter-free syntax check**

Run:

```bash
python -m compileall pipeline tests scripts -q
```

Expected: exit code 0.

- [ ] **Step 5: Run focused tests**

Run:

```bash
pytest tests/llm/test_tools.py tests/llm/test_extract.py tests/test_run_pool.py tests/test_prompt_contract.py tests/test_zep_phase_regression.py -q
```

Expected: pass.

- [ ] **Step 6: Run full test suite**

Run:

```bash
pytest -q
```

Expected: pass. If a test fails because it asserts the retired first-pass tool architecture, update or delete that test in the same commit; do not add compatibility code to satisfy it.

- [ ] **Step 7: Commit cleanup**

List the files changed by cleanup and stage only those files:

```bash
git status --short
git add AGENTS.md CLAUDE.md SKILL.md docs/linkflow-extraction-guide.md prompts/extract.md prompts/repair.md pipeline/llm/tools.py pipeline/llm/extract.py pipeline/run_pool.py tests/llm/test_tools.py tests/llm/test_extract.py tests/test_run_pool.py tests/test_prompt_contract.py tests/test_zep_phase_regression.py rules/events.md
git status --short
git commit -m "chore: remove stale tool-heavy contract"
```

If `quality_reports/2026-04-29_design-review.md` is intentionally deleted, include it in the commit with:

```bash
git add -u quality_reports/2026-04-29_design-review.md
git commit -m "chore: remove stale generated report"
```

Use one commit if both cleanup sets are already staged together.

---

### Task 11: Recalibration Smoke Run

**Files:**
- Runtime output under `output/audit/petsmart-inc/runs/{run_id}/`
- Runtime output under `output/extractions/petsmart-inc.json`
- Runtime state under `state/progress.json` and `state/flags.jsonl`
- Optional report under `quality_reports/reference_batches/`

- [ ] **Step 1: Dry-run selection**

Run:

```bash
python run.py --slug petsmart-inc --re-extract --dry-run
```

Expected: prints that `petsmart-inc` would run; no audit directory is created.

- [ ] **Step 2: Run the Petsmart smoke only if API credentials are available**

Run:

```bash
python run.py --slug petsmart-inc --re-extract --extract-model gpt-5.5 --adjudicate-model gpt-5.5 --extract-reasoning-effort high --adjudicate-reasoning-effort high
```

Expected: one new immutable audit run for `petsmart-inc`.

- [ ] **Step 3: Inspect the smoke manifest**

Set the run id from `output/audit/petsmart-inc/latest.json`, then run:

```bash
RUN_ID=$(jq -r '.run_id' output/audit/petsmart-inc/latest.json)
jq '{outcome,total_seconds,total_input_tokens,total_output_tokens,total_reasoning_tokens,tool_calls_count,repair_turns_used,repair_loop_outcome,extract_tool_mode,repair_strategy}' output/audit/petsmart-inc/runs/$RUN_ID/manifest.json
```

Expected:

```json
{
  "extract_tool_mode": "none",
  "repair_strategy": "prompt_then_targeted_tools"
}
```

`tool_calls_count` must be `0` unless repair 2 ran.

- [ ] **Step 4: Inspect repair turns if present**

Run:

```bash
if [ -f output/audit/petsmart-inc/runs/$RUN_ID/repair_turns.jsonl ]; then
  jq -c '{turn,tool_mode,hard_flags_before,hard_flags_after,tool_calls_count,outcome}' output/audit/petsmart-inc/runs/$RUN_ID/repair_turns.jsonl
fi
```

Expected: repair 1 has `tool_mode="none"`; repair 2, if present, has `tool_mode="targeted_repair_tools"`.

- [ ] **Step 5: Do not commit smoke artifacts unless Austin asks**

Run:

```bash
git status --short
```

Expected: runtime output/state may be dirty. Leave smoke artifacts uncommitted unless Austin explicitly asks for output/state commits.

---

## Final Acceptance Checklist

- [ ] `extract_deal` never supplies tools on first extraction.
- [ ] Repair 1 never supplies tools.
- [ ] Repair 2 supplies exactly `check_row`, `search_filing`, and `get_pages`.
- [ ] No CLI flag or compatibility branch can re-enable first-pass tools.
- [ ] Audit manifests include `extract_tool_mode="none"` and `repair_strategy="prompt_then_targeted_tools"`.
- [ ] `repair_turns.jsonl` includes `tool_mode`.
- [ ] `prompts/extract.md` contains no tool-use instructions.
- [ ] `prompts/repair.md` documents staged repair modes.
- [ ] `AGENTS.md`, `CLAUDE.md`, `SKILL.md`, and `docs/linkflow-extraction-guide.md` all describe the same live architecture.
- [ ] Zep interval regression is covered.
- [ ] `pytest -q` passes.
- [ ] Stale-search commands in Task 10 return no live architecture drift.
