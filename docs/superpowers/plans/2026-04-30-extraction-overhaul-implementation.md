# Extraction Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Tasks are tagged `[PARALLEL]` (safe to dispatch with peers in the same group) or `[SEQUENTIAL]` (must complete before the next task starts).

**Goal:** Replace the prompt-only-JSON Linkflow extraction path with strict `text.format=json_schema` + native function-calling tools (`check_row`, `search_filing`, `get_pages`) + an outer Python validation-repair loop (cap = 2 turns), and hard-cleanse all stale code, docs, contract files, audit artifacts, and tests in the same merge.

**Architecture:** Extractor turn(s) call tools mid-draft → emit a strict-schema `{deal, events}` body → Python `validate()` runs → if hard flags, repair turn(s) up to N=2 → `repair_loop_exhausted` flag on cap-hit → adjudicator (scoped, no tools) verdicts soft flags → finalize. Every full-extraction turn streams; tool-call/tool-output turns are non-streaming. Full-input replay each turn (no `previous_response_id`). Cost is unbounded by design.

**Tech Stack:** Python 3.11, `openai` AsyncOpenAI SDK against Linkflow proxy (`https://www.linkflow.run/v1`), `gpt-5.5` model with `xhigh` reasoning effort, `pytest` for tests, existing `pipeline.core` validators, existing audit v2 archive shape.

**Spec:** [docs/superpowers/specs/2026-04-30-extraction-overhaul-design.md](../specs/2026-04-30-extraction-overhaul-design.md).

**Branch:** `api-call`. Land all tasks here; final merge to `main` after H.6 stability proof passes.

---

## Real-time API testing protocol (read this first)

**The user has authorized passing the Linkflow API key in chat for real-time testing.** Every task that involves model behavior **must** verify against the live Linkflow proxy with `gpt-5.5` at the documented reasoning effort. Mock-only verification is insufficient.

**Environment variables for every probe:**
```bash
export OPENAI_API_KEY="<linkflow key from user>"
export OPENAI_BASE_URL="https://www.linkflow.run/v1"
export EXTRACT_MODEL="gpt-5.5"
export ADJUDICATE_MODEL="gpt-5.5"
```

**Linkflow constraints to remember:**
- 5-worker ceiling at `xhigh` reasoning (enforced by `LINKFLOW_XHIGH_MAX_WORKERS`).
- 300s streaming idle timeout per response.
- `previous_response_id` returns 400 — always full-input replay.
- Streaming `stream.get_final_response().output` is empty under tools — reconstruct from delta events OR use non-streaming for tool turns.
- `json_object` is **not** a usable fallback (T9 502s on full inputs).

**When a probe fails:** do not paper over it. Capture the actual response, the request payload (sans key), and decide whether the failure is (a) a transient Linkflow blip — retry once, (b) a code defect — fix and re-probe, or (c) a contract mismatch — escalate to the user with the evidence. **Do not invent test outputs or shim around real-API failures.**

---

## Multi-agent execution graph

```text
PHASE 1  [SEQUENTIAL — 1 agent]
   └─ Workstream A — Schema probe (A.1–A.3)
PHASE 2  [PARALLEL — 4 agents in one dispatch]
   ├─ Agent α: Workstream B — Tools (B.1–B.5)
   ├─ Agent β: Workstream F — Prompt rewrite (F.1–F.4)
   ├─ Agent γ: Workstream G-DOCS — Contract docs cleanse (G.5–G.7)
   └─ Agent δ: Workstream E-INFRA — Contract version hashing (E.4)
PHASE 3  [SEQUENTIAL — 1 agent]
   └─ Workstream C — Client + extract orchestration (C.1–C.5)
PHASE 4  [SEQUENTIAL — 1 agent]
   └─ Workstream D — Repair loop (D.1–D.4)
PHASE 5  [SEQUENTIAL — 1 agent]
   └─ Workstream E-AUDIT — Audit extensions (E.1–E.3, E.5)
PHASE 6  [SEQUENTIAL — 1 agent]
   └─ Workstream G-DATA — Cleanse data artifacts (G.1–G.4, G.8–G.12)
PHASE 7  [SEQUENTIAL — 1 agent, multiple iterations]
   └─ Workstream H — Reference verification + stability (H.1–H.7)
```

Total dispatches: 1 + 4 (parallel) + 1 + 1 + 1 + 1 + 1 = **10 agent dispatches**, of which 4 run concurrently in Phase 2.

Between phases, the orchestrator runs `pytest` against the touched modules and verifies the previous phase's commits before dispatching the next phase's agent(s).

---

## Workstream A — Schema verification probe [SEQUENTIAL]

**Why first:** The 04-30 feasibility report (T9) verified strict `json_schema` on a *small* schema. The full hardened `SCHEMA_R1` is untested through Linkflow. If Linkflow rejects it, every subsequent task that depends on strict schema needs to know which fields to soften. We probe before building on assumptions.

### Task A.1: Probe SCHEMA_R1 (current shape) against Linkflow

**Files:**
- Create: `scripts/probe_schema_r1.py`
- Create: `quality_reports/schema_probe/2026-04-30_schema_r1_baseline.json`

- [ ] **Step 1: Write the probe script**

```python
# scripts/probe_schema_r1.py
"""Probe Linkflow's strict json_schema acceptance on the live SCHEMA_R1 shape.

Run with OPENAI_API_KEY + OPENAI_BASE_URL set. Writes the request, response
status, and parse outcome to quality_reports/schema_probe/.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from openai import AsyncOpenAI

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.llm import extract  # noqa: E402
from pipeline.llm.response_format import SCHEMA_R1, json_schema_format  # noqa: E402


async def main(slug: str = "medivation") -> int:
    client = AsyncOpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ["OPENAI_BASE_URL"],
    )
    system, user = extract.build_messages(slug)
    payload = {
        "model": os.environ.get("EXTRACT_MODEL", "gpt-5.5"),
        "input": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "reasoning": {"effort": "medium"},
        "text": {"format": json_schema_format(SCHEMA_R1)},
        "max_output_tokens": 8192,
    }
    out_dir = ROOT / "quality_reports" / "schema_probe"
    out_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    result: dict = {"slug": slug, "started_utc": started.isoformat()}
    try:
        resp = await client.responses.create(**payload)
        text = resp.output_text or ""
        result["status"] = "ok"
        result["output_text_chars"] = len(text)
        result["output_text_head"] = text[:400]
        try:
            json.loads(text)
            result["parses"] = True
        except json.JSONDecodeError as exc:
            result["parses"] = False
            result["parse_error"] = str(exc)
    except Exception as exc:  # noqa: BLE001 — we want to capture the raw error
        result["status"] = "error"
        result["error_class"] = type(exc).__name__
        result["error_str"] = str(exc)[:2000]
    result["finished_utc"] = datetime.now(timezone.utc).isoformat()
    out_path = out_dir / f"{started.date()}_schema_r1_baseline_{slug}.json"
    out_path.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") == "ok" and result.get("parses") else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "medivation")))
```

- [ ] **Step 2: Run the probe against medivation**

```bash
cd /Users/austinli/bids_try
OPENAI_API_KEY=<key> OPENAI_BASE_URL=https://www.linkflow.run/v1 \
  EXTRACT_MODEL=gpt-5.5 \
  python scripts/probe_schema_r1.py medivation
```

Expected: probe writes a JSON record to `quality_reports/schema_probe/`. If `status=ok` and `parses=true`, A.1 passes. If status=error or parses=false, capture the exact error and proceed to A.2.

- [ ] **Step 3: Commit the probe artifact (regardless of outcome)**

```bash
git add scripts/probe_schema_r1.py quality_reports/schema_probe/
git commit -m "schema-probe: baseline SCHEMA_R1 strict acceptance probe (medivation)"
```

### Task A.2: Harden SCHEMA_R1 (only if A.1 passed; otherwise iterate to acceptance)

**Files:**
- Modify: `pipeline/llm/response_format.py:140-277` — `SCHEMA_R1` definition

- [ ] **Step 1: Audit current SCHEMA_R1 against the spec's hardening list**

Spec §3 requires: `additionalProperties: false` everywhere, complete `required` lists per object, tightened enums (bid_note, bidder_type, bid_value_unit, role, consideration_components), `maxLength: 1500` on quote fields, exact-shape arrays. Read `SCHEMA_R1` and list every object that's missing any of these.

- [ ] **Step 2: Apply hardening edits**

Edit `SCHEMA_R1` to add the missing constraints. Do NOT add `oneOf` event variants for §P-R9 — that is explicitly deferred per spec §3.

- [ ] **Step 3: Re-run unit tests for response_format**

Run: `pytest tests/llm/test_response_format.py -v`
Expected: PASS (existing tests should still pass; if they fail because they used the looser shape, that's a sign the hardening is biting — fix the tests to match the new contract).

- [ ] **Step 4: Re-probe against medivation**

```bash
python scripts/probe_schema_r1.py medivation
```

Expected: `status=ok`, `parses=true`. If rejected, soften the specific fields the error names, document in the probe artifact, re-probe.

- [ ] **Step 5: Probe two more reference deals**

```bash
python scripts/probe_schema_r1.py providence-worcester
python scripts/probe_schema_r1.py petsmart-inc
```

Expected: both probes return `status=ok`, `parses=true`. These are the largest reference inputs (~44k tokens). If both pass, the hardened schema is production-ready.

- [ ] **Step 6: Commit**

```bash
git add pipeline/llm/response_format.py quality_reports/schema_probe/ tests/llm/test_response_format.py
git commit -m "schema: harden SCHEMA_R1 with additionalProperties:false, complete required, maxLength

Verified against medivation, providence-worcester, petsmart-inc (~44k input tokens)
on Linkflow gpt-5.5 with strict json_schema mode."
```

### Task A.3: Document the verified schema baseline

**Files:**
- Modify: `quality_reports/schema_probe/README.md` (create if absent)

- [ ] **Step 1: Write a one-page baseline record**

Capture: schema commit SHA, three probe artifact filenames, total input tokens per probe, parsing outcome, any field softenings made during A.2. This is the empirical baseline future agents reference when changing the schema.

- [ ] **Step 2: Commit**

```bash
git add quality_reports/schema_probe/README.md
git commit -m "docs: SCHEMA_R1 strict-mode baseline record"
```

**Phase 1 acceptance gate:** A.1+A.2+A.3 commits exist; three probe artifacts show `status=ok` and `parses=true`; nothing else has been touched. The orchestrator dispatches Phase 2.

---

## Workstream B — Tools [PARALLEL with F, G-DOCS, E-INFRA]

### Task B.1: Implement `check_row` tool

**Files:**
- Create: `pipeline/llm/tools.py`
- Create: `tests/llm/test_tools.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/llm/test_tools.py
import json
from pathlib import Path
import pytest
from pipeline.llm import tools


def _filing_pages():
    return [{"number": 22, "content": "On May 15, 2014, the Special Committee met to discuss the offer."}]


def test_check_row_passes_clean_bid_row():
    row = {
        "bid_note": "Bid",
        "bid_type": "informal",
        "bidder_alias": "Bidder F",
        "bidder_type": "f",
        "bid_value_low": 25.0,
        "bid_value_high": 25.0,
        "bid_value_unit": "USD_per_share",
        "consideration_components": ["cash"],
        "source_quote": "On May 15, 2014, the Special Committee met to discuss the offer.",
        "source_page": 22,
        "process_phase": 1,
        "submitted_formal_bid": None,
        "invited_to_formal_round": None,
        "role": "bidder",
        "BidderID": 1,
    }
    result = tools.check_row(row, filing_pages=_filing_pages())
    assert result["ok"] is True
    assert result["violations"] == []


def test_check_row_catches_p_r9_violation_on_executed_row():
    row = {
        "bid_note": "Executed",
        "bidder_alias": "G&W",
        "bid_value_low": 25.0,           # §P-R9: must be null on Executed
        "bid_value_unit": "USD_per_share",
        "consideration_components": ["cash"],
        "source_quote": "On May 15, 2014, the Special Committee met to discuss the offer.",
        "source_page": 22,
        "process_phase": 1,
        "role": "bidder",
        "BidderID": 1,
    }
    result = tools.check_row(row, filing_pages=_filing_pages())
    assert result["ok"] is False
    codes = {v["code"] for v in result["violations"]}
    assert "conditional_field_mismatch" in codes


def test_check_row_catches_quote_not_in_page():
    row = {
        "bid_note": "Bid",
        "bid_type": "informal",
        "bidder_alias": "X",
        "bid_value_low": 30.0,
        "bid_value_high": 30.0,
        "bid_value_unit": "USD_per_share",
        "consideration_components": ["cash"],
        "source_quote": "This text does not appear anywhere on page 22.",
        "source_page": 22,
        "process_phase": 1,
        "role": "bidder",
        "BidderID": 1,
    }
    result = tools.check_row(row, filing_pages=_filing_pages())
    codes = {v["code"] for v in result["violations"]}
    assert "source_quote_not_in_page" in codes
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/llm/test_tools.py -v
```
Expected: ImportError or "module pipeline.llm.tools has no attribute check_row".

- [ ] **Step 3: Implement `check_row` in `pipeline/llm/tools.py`**

Implementation strategy: extract the row-local check helpers from `pipeline/core.py` into reusable functions (or call them directly via a Filing-shaped argument). The 15 row-local rules to enforce: §P-R0 type checking, §P-R2 source_quote substring (NFKC + filing pages), §P-R3 bid_note vocabulary, §P-R4 role vocab, §P-R5 bidder registry consistency (skip if no registry yet), §P-R6 bidder_type, §P-R7 ca_type_ambiguous, §P-R8 flag shape, §P-R9 conditional nullness, §P-D1 bid_date_precise format, §P-D2 bid_date_rough/inference, §P-D7 drop reason matrix, §P-G2 bid_type evidence.

```python
# pipeline/llm/tools.py
"""Native function-calling tools available to the extractor at draft time.

Three tools: check_row, search_filing, get_pages. Each is a thin deterministic
wrapper around existing pipeline.core / data.filings logic. The model invokes
them via Responses-API function calling; the harness in pipeline.llm.extract
runs the tool and replies via function_call_output items.
"""
from __future__ import annotations

import unicodedata
from typing import Any

from pipeline import core


# ---------- check_row ----------

CHECK_ROW_SCHEMA = {
    "type": "function",
    "name": "check_row",
    "description": (
        "Validate a single proposed extraction event row against the row-local "
        "rulebook (§P-R0 through §P-R9, §P-D1/D2/D7, §P-G2). Returns ok=true "
        "if the row passes all checks, otherwise ok=false with a violations "
        "list naming each broken rule. Call this before submitting any row."
    ),
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "row": {
                "type": "object",
                "additionalProperties": True,
                "description": "A single proposed event row matching SCHEMA_R1 event shape.",
            },
        },
        "required": ["row"],
    },
}


def _nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s)


def check_row(row: dict[str, Any], *, filing_pages: list[dict[str, Any]]) -> dict[str, Any]:
    """Run all row-local validators on a single proposed row.

    `filing_pages` is the same shape as `data/filings/{slug}/pages.json` and is
    captured by the harness via closure when registering the tool — it is NOT
    a parameter the model passes.
    """
    violations: list[dict[str, Any]] = []
    pages_by_number = {p["number"]: _nfkc(p.get("content", "")) for p in filing_pages}

    # Delegate to pipeline.core helpers. Each helper appends violation dicts of
    # shape {"code": str, "severity": "hard"|"soft"|"info", "reason": str, "field"?: str}.
    core.check_row_p_r0(row, violations)
    core.check_row_p_r2(row, pages_by_number, violations)
    core.check_row_p_r3(row, violations)
    core.check_row_p_r4(row, violations)
    core.check_row_p_r6(row, violations)
    core.check_row_p_r7(row, violations)
    core.check_row_p_r8(row, violations)
    core.check_row_p_r9(row, violations)
    core.check_row_p_d1(row, violations)
    core.check_row_p_d2(row, violations)
    core.check_row_p_d7(row, violations)
    core.check_row_p_g2(row, violations)
    # §P-R5 bidder registry consistency requires the whole-draft registry; skip
    # in the row-local tool — the outer validator catches it post-draft.

    return {"ok": len(violations) == 0, "violations": violations}
```

**Note for the implementing agent:** the helper names `check_row_p_r0` etc. may not exist as separate functions in `pipeline/core.py` today — `validate()` is monolithic. Part of this task is **extracting reusable per-rule helpers** from `validate()` into module-level functions, then having `validate()` and `check_row()` both call them. Do not duplicate logic. If extraction is non-trivial, do it as a refactor commit before the test passes.

- [ ] **Step 4: Run tests until all pass**

```bash
pytest tests/llm/test_tools.py -v
```
Expected: all three tests pass.

- [ ] **Step 5: Run full pipeline.core test suite to confirm no regression**

```bash
pytest tests/test_invariants.py tests/test_pipeline_runtime.py -v
```
Expected: PASS — the refactor must not change validator behavior.

- [ ] **Step 6: Commit**

```bash
git add pipeline/llm/tools.py pipeline/core.py tests/llm/test_tools.py
git commit -m "feat: implement check_row tool wrapping row-local validators

Extract per-rule helpers from pipeline.core.validate() and expose them via
the check_row() tool function. Tool returns {ok, violations} on a single
proposed event row. Filing pages captured via closure.

Tests cover clean Bid, §P-R9 nullness violation on Executed row, and
source_quote_not_in_page case."
```

### Task B.2: Implement `search_filing` tool

**Files:**
- Modify: `pipeline/llm/tools.py`
- Modify: `tests/llm/test_tools.py`

- [ ] **Step 1: Add failing test**

```python
def test_search_filing_finds_substring_returns_page_and_snippet():
    pages = [
        {"number": 5, "content": "Pre-merger discussions began in early 2013."},
        {"number": 22, "content": "On May 15, 2014, the Special Committee met."},
        {"number": 41, "content": "by and among Acquirer and BC Partners and La Caisse."},
    ]
    result = tools.search_filing("BC Partners", filing_pages=pages, page_range=None, max_hits=10)
    hits = result["hits"]
    assert len(hits) == 1
    assert hits[0]["page"] == 41
    assert "BC Partners" in hits[0]["snippet"]


def test_search_filing_respects_page_range():
    pages = [
        {"number": 1, "content": "Match here."},
        {"number": 10, "content": "Match here."},
        {"number": 50, "content": "Match here."},
    ]
    result = tools.search_filing("Match", filing_pages=pages, page_range=[5, 20], max_hits=10)
    assert {h["page"] for h in result["hits"]} == {10}


def test_search_filing_caps_at_max_hits():
    pages = [{"number": i, "content": "match"} for i in range(1, 21)]
    result = tools.search_filing("match", filing_pages=pages, page_range=None, max_hits=3)
    assert len(result["hits"]) == 3
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/llm/test_tools.py::test_search_filing_finds_substring_returns_page_and_snippet -v
```

- [ ] **Step 3: Implement `search_filing`**

```python
# Append to pipeline/llm/tools.py

SEARCH_FILING_SCHEMA = {
    "type": "function",
    "name": "search_filing",
    "description": (
        "Case-insensitive substring search over filing pages. Returns up to "
        "max_hits page+snippet pairs. Use this to find consortium constituents, "
        "dates, dollar amounts, or any other text that may not be in the "
        "Background section. Use plain words/phrases, not regex."
    ),
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "query": {"type": "string", "description": "Plain-text substring to search for."},
            "page_range": {
                "type": ["array", "null"],
                "items": {"type": "integer"},
                "minItems": 2,
                "maxItems": 2,
                "description": "Inclusive [start_page, end_page] or null for whole filing.",
            },
            "max_hits": {"type": "integer", "minimum": 1, "maximum": 50},
        },
        "required": ["query", "page_range", "max_hits"],
    },
}


def search_filing(
    query: str,
    *,
    filing_pages: list[dict[str, Any]],
    page_range: list[int] | None = None,
    max_hits: int = 10,
) -> dict[str, Any]:
    needle = _nfkc(query).lower()
    hits: list[dict[str, Any]] = []
    for page in filing_pages:
        page_no = page["number"]
        if page_range is not None and not (page_range[0] <= page_no <= page_range[1]):
            continue
        haystack = _nfkc(page.get("content", ""))
        idx = haystack.lower().find(needle)
        if idx == -1:
            continue
        start = max(0, idx - 200)
        end = min(len(haystack), idx + len(query) + 200)
        snippet = haystack[start:end]
        hits.append({"page": page_no, "snippet": snippet})
        if len(hits) >= max_hits:
            break
    return {"hits": hits}
```

- [ ] **Step 4: Run tests to verify pass**

```bash
pytest tests/llm/test_tools.py -v
```

- [ ] **Step 5: Commit**

```bash
git add pipeline/llm/tools.py tests/llm/test_tools.py
git commit -m "feat: implement search_filing tool (substring search over pages.json)"
```

### Task B.3: Implement `get_pages` tool

**Files:**
- Modify: `pipeline/llm/tools.py`
- Modify: `tests/llm/test_tools.py`

- [ ] **Step 1: Add failing test**

```python
def test_get_pages_returns_contiguous_pages():
    pages = [{"number": i, "content": f"page {i} text"} for i in range(20, 30)]
    result = tools.get_pages(start_page=22, end_page=24, filing_pages=pages)
    assert [p["page"] for p in result["pages"]] == [22, 23, 24]
    assert result["pages"][0]["text"] == "page 22 text"


def test_get_pages_rejects_range_over_cap():
    pages = [{"number": i, "content": "x"} for i in range(1, 100)]
    with pytest.raises(ValueError, match="page range too wide"):
        tools.get_pages(start_page=1, end_page=20, filing_pages=pages)


def test_get_pages_skips_missing_page_numbers():
    pages = [{"number": 22, "content": "x"}, {"number": 24, "content": "y"}]
    result = tools.get_pages(start_page=22, end_page=24, filing_pages=pages)
    assert {p["page"] for p in result["pages"]} == {22, 24}
```

- [ ] **Step 2: Run to verify it fails**

- [ ] **Step 3: Implement `get_pages`**

```python
GET_PAGES_SCHEMA = {
    "type": "function",
    "name": "get_pages",
    "description": (
        "Fetch the full text of a contiguous range of filing pages by page "
        "number. Use after search_filing or when you need surrounding context "
        "for a specific page. Maximum 10 pages per call."
    ),
    "parameters": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "start_page": {"type": "integer", "minimum": 1},
            "end_page": {"type": "integer", "minimum": 1},
        },
        "required": ["start_page", "end_page"],
    },
}

GET_PAGES_MAX_RANGE = 10


def get_pages(
    *,
    start_page: int,
    end_page: int,
    filing_pages: list[dict[str, Any]],
) -> dict[str, Any]:
    if end_page < start_page:
        raise ValueError(f"end_page {end_page} < start_page {start_page}")
    if end_page - start_page + 1 > GET_PAGES_MAX_RANGE:
        raise ValueError(
            f"page range too wide: {end_page - start_page + 1} > {GET_PAGES_MAX_RANGE}"
        )
    out = []
    for page in filing_pages:
        if start_page <= page["number"] <= end_page:
            out.append({"page": page["number"], "text": page.get("content", "")})
    return {"pages": out}
```

- [ ] **Step 4: Run tests, commit**

```bash
pytest tests/llm/test_tools.py -v
git add pipeline/llm/tools.py tests/llm/test_tools.py
git commit -m "feat: implement get_pages tool (contiguous page fetch, cap=10)"
```

### Task B.4: Tool registry + dispatcher

**Files:**
- Modify: `pipeline/llm/tools.py`
- Modify: `tests/llm/test_tools.py`

- [ ] **Step 1: Add failing test**

```python
def test_tool_registry_has_all_three():
    names = {t["name"] for t in tools.TOOL_DEFINITIONS}
    assert names == {"check_row", "search_filing", "get_pages"}


def test_dispatch_invokes_check_row():
    pages = [{"number": 22, "content": "On May 15, 2014, the Committee met."}]
    result = tools.dispatch(
        name="check_row",
        arguments={"row": {
            "bid_note": "Bid", "bid_type": "informal", "bidder_alias": "X",
            "source_quote": "On May 15, 2014, the Committee met.",
            "source_page": 22, "process_phase": 1, "BidderID": 1, "role": "bidder",
            "bid_value_low": 25.0, "bid_value_high": 25.0,
            "bid_value_unit": "USD_per_share", "consideration_components": ["cash"],
            "submitted_formal_bid": None, "invited_to_formal_round": None,
        }},
        filing_pages=pages,
    )
    assert "ok" in result and "violations" in result
```

- [ ] **Step 2: Run to verify it fails**

- [ ] **Step 3: Implement `TOOL_DEFINITIONS` + `dispatch`**

```python
# Append to pipeline/llm/tools.py

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    CHECK_ROW_SCHEMA,
    SEARCH_FILING_SCHEMA,
    GET_PAGES_SCHEMA,
]


def tools_contract_version() -> str:
    """Hash of the tool definitions plus implementation source.

    Captured in audit manifests for cache eligibility checks.
    """
    import hashlib
    import inspect
    payload = {
        "definitions": TOOL_DEFINITIONS,
        "impl_src": (
            inspect.getsource(check_row)
            + inspect.getsource(search_filing)
            + inspect.getsource(get_pages)
        ),
    }
    blob = repr(payload).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def dispatch(
    name: str,
    arguments: dict[str, Any],
    *,
    filing_pages: list[dict[str, Any]],
) -> dict[str, Any]:
    if name == "check_row":
        return check_row(arguments["row"], filing_pages=filing_pages)
    if name == "search_filing":
        return search_filing(
            arguments["query"],
            filing_pages=filing_pages,
            page_range=arguments.get("page_range"),
            max_hits=arguments.get("max_hits", 10),
        )
    if name == "get_pages":
        return get_pages(
            start_page=arguments["start_page"],
            end_page=arguments["end_page"],
            filing_pages=filing_pages,
        )
    raise ValueError(f"unknown tool: {name!r}")
```

- [ ] **Step 4: Run tests, commit**

```bash
pytest tests/llm/test_tools.py -v
git add pipeline/llm/tools.py tests/llm/test_tools.py
git commit -m "feat: tool registry, dispatch, contract version hash"
```

### Task B.5: Real-API end-to-end probe of tools

**Files:**
- Create: `scripts/probe_tools_e2e.py`
- Create: `quality_reports/tool_probe/2026-04-30_tools_e2e.json`

- [ ] **Step 1: Write the probe**

```python
# scripts/probe_tools_e2e.py
"""End-to-end probe: send a tiny input + tools to gpt-5.5 via Linkflow,
verify model emits function_calls, run them locally, replay full input
with function_call_outputs, verify model emits a final message.

Tests the entire harness pattern in miniature before C.* wires it into extract.
"""
from __future__ import annotations
import asyncio, json, os, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from openai import AsyncOpenAI  # noqa: E402
from pipeline.llm import tools  # noqa: E402


PAGES = [
    {"number": 22, "content": "On May 15, 2014, the Special Committee met to discuss the offer of $25.00 per share."},
    {"number": 41, "content": "by and among Acquirer and BC Partners L.P. and La Caisse de dépôt"},
]


async def main() -> int:
    client = AsyncOpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ["OPENAI_BASE_URL"],
    )
    initial_input = [{
        "role": "user",
        "content": (
            "I am drafting a single Bid event row. The filing pages are available "
            "via search_filing and get_pages. Before finalizing the row, call "
            "check_row to validate it. Row I am considering: "
            '{"bid_note":"Bid","bidder_alias":"X","bid_value_low":25.0,'
            '"bid_value_high":25.0,"bid_value_unit":"USD_per_share",'
            '"source_quote":"$25.00 per share","source_page":22,'
            '"BidderID":1,"role":"bidder","process_phase":1,'
            '"bid_type":"informal","consideration_components":["cash"],'
            '"submitted_formal_bid":null,"invited_to_formal_round":null}. '
            "Then report back what check_row said."
        ),
    }]
    payload = {
        "model": os.environ.get("EXTRACT_MODEL", "gpt-5.5"),
        "input": initial_input,
        "reasoning": {"effort": "medium"},
        "tools": tools.TOOL_DEFINITIONS,
        "tool_choice": "auto",
        "max_output_tokens": 4096,
    }
    started = datetime.now(timezone.utc)
    result: dict = {"started_utc": started.isoformat(), "turns": []}
    resp1 = await client.responses.create(**payload)
    fcs = [item for item in resp1.output if getattr(item, "type", "") == "function_call"]
    result["turns"].append({"turn": 1, "function_calls": [fc.model_dump() for fc in fcs]})

    if not fcs:
        result["status"] = "model_did_not_call_tools"
        Path("quality_reports/tool_probe").mkdir(parents=True, exist_ok=True)
        Path(f"quality_reports/tool_probe/{started.date()}_tools_e2e.json").write_text(
            json.dumps(result, indent=2)
        )
        return 1

    # Run each tool locally
    tool_outputs = []
    for fc in fcs:
        args = json.loads(fc.arguments)
        try:
            out = tools.dispatch(name=fc.name, arguments=args, filing_pages=PAGES)
            tool_outputs.append({"call_id": fc.call_id, "output": json.dumps(out)})
        except Exception as exc:
            tool_outputs.append({"call_id": fc.call_id, "output": json.dumps({"error": str(exc)})})

    # Replay full input + outputs
    replayed = list(initial_input)
    for item in resp1.output:
        replayed.append(item.model_dump())
    for to in tool_outputs:
        replayed.append({"type": "function_call_output", "call_id": to["call_id"], "output": to["output"]})

    payload["input"] = replayed
    resp2 = await client.responses.create(**payload)
    text = (resp2.output_text or "")[:1000]
    result["turns"].append({"turn": 2, "final_text_head": text})
    result["status"] = "ok" if text else "no_final_text"
    Path("quality_reports/tool_probe").mkdir(parents=True, exist_ok=True)
    out_path = Path(f"quality_reports/tool_probe/{started.date()}_tools_e2e.json")
    out_path.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

- [ ] **Step 2: Run the probe**

```bash
OPENAI_API_KEY=<key> OPENAI_BASE_URL=https://www.linkflow.run/v1 \
  EXTRACT_MODEL=gpt-5.5 \
  python scripts/probe_tools_e2e.py
```

Expected: probe writes a JSON record. Turn 1 has at least one `function_call` (most likely `check_row`). Turn 2 has non-empty `final_text_head`. `status=ok`.

- [ ] **Step 3: Commit the probe + artifact**

```bash
git add scripts/probe_tools_e2e.py quality_reports/tool_probe/
git commit -m "tools-probe: gpt-5.5 invokes check_row and emits final text after replay"
```

**Workstream B acceptance:** `pytest tests/llm/test_tools.py` passes; `scripts/probe_tools_e2e.py` returns 0; tool registry + contract hash function exist.

---

## Workstream F — Prompt rewrite [PARALLEL with B, G-DOCS, E-INFRA]

### Task F.1: Drop the "do not call tools" warning + restructure prompt sections

**Files:**
- Modify: `prompts/extract.md`

- [ ] **Step 1: Read the current prompt**

```bash
cat prompts/extract.md
```

- [ ] **Step 2: Find the input-boundary warning lines (currently 18–24)**

The current prompt warns "Do not... call tools." Replace this with explicit tool-call guidance.

- [ ] **Step 3: Rewrite the input-boundary section**

```markdown
## Tools available to you

You have three deterministic Python tools you can call as native function calls during drafting:

- `check_row(row)` — validates a single proposed event row against the row-local rulebook (§P-R0/R2/R3/R4/R5/R6/R7/R8/R9, §P-D1/D2/D7, §P-G2). Returns `{ok: bool, violations: [...]}`. **Call this on every event row before submitting.** Multiple rows may be checked in parallel in a single turn.
- `search_filing(query, page_range, max_hits)` — case-insensitive substring search over filing pages. Returns page+snippet hits. **Use this to find consortium constituents, dates, or amounts that may not be in the Background slice.** When emitting a Buyer Group / Consortium / Investor Group row, search merger-agreement party blocks (e.g., "by and among", "Parent:", "Schedule A").
- `get_pages(start_page, end_page)` — fetches the full text of up to 10 contiguous filing pages. Use after `search_filing` when you need the surrounding context.

After tool calls return, emit the final `{deal, events}` JSON body matching SCHEMA_R1.
```

- [ ] **Step 4: Commit**

```bash
git add prompts/extract.md
git commit -m "prompt: replace 'no tools' warning with explicit tool-use guidance"
```

### Task F.2: Promote §P-R9 nullness rule to high-salience prose

**Files:**
- Modify: `prompts/extract.md` (currently around line 79 has the "value-bearing" emphasis; line 193 has the buried nullness checklist)

- [ ] **Step 1: Add a new prose paragraph immediately after the schema introduction**

```markdown
## Critical rule — bid economics field ownership (§P-R9)

The fields `bid_value_low`, `bid_value_high`, `bid_value_unit`, `consideration_components`, `submitted_formal_bid`, and `invited_to_formal_round` belong **exclusively** to `Bid` rows. On any other `bid_note` row (including `Executed`, `Final Round`, `NDA`, `Drop`, `DropSilent`, `Restarted`, `Terminated`, `Press Release`, `Background`, `ConsortiumCA`, `Auction Closed`), these fields **MUST be null**.

If a press release on the Executed row restates a final price, the price belongs to the earlier `Bid` row that the executed deal is consummating, not to the `Executed` row itself. Note the restatement in `additional_note`, leave the bid economics fields null on the Executed row.

Always call `check_row` on every row before submitting it. The tool will catch §P-R9 violations.
```

- [ ] **Step 2: Remove the buried duplicate at the previous location**

If line ~193 still has a checklist line stating the same rule, remove it (DRY).

- [ ] **Step 3: Commit**

```bash
git add prompts/extract.md
git commit -m "prompt: promote §P-R9 nullness rule to high-salience prose paragraph"
```

### Task F.3: Add few-shot evidence-cited row examples

**Files:**
- Modify: `prompts/extract.md`

The four canonical archetypes that drive the failure modes the new pipeline must handle: (a) clean Bid row with all fields, (b) Executed row with null bid economics (the §P-R9 case), (c) unnamed NDA placeholder + later promotion to a named bidder, (d) Buyer Group with `find_in_filing`-discovered constituents.

- [ ] **Step 1: Add an "Examples" section to the prompt**

```markdown
## Canonical row examples

These illustrate the exact shape and evidence discipline the rulebook requires.

### Example 1 — Informal Bid (clean)

```json
{
  "BidderID": 4,
  "bid_note": "Bid",
  "bid_type": "informal",
  "bidder_alias": "Bidder F",
  "bidder_type": "f",
  "process_phase": 1,
  "bid_value_low": 24.50,
  "bid_value_high": 25.50,
  "bid_value_unit": "USD_per_share",
  "consideration_components": ["cash"],
  "submitted_formal_bid": null,
  "invited_to_formal_round": null,
  "role": "bidder",
  "source_quote": "On April 8, 2014, Bidder F submitted a non-binding indication of interest in the range of $24.50 to $25.50 per share, payable in cash.",
  "source_page": 23,
  "bid_date_precise": "2014-04-08",
  "bid_date_rough": null,
  "flags": []
}
```

### Example 2 — Executed (§P-R9 nullness)

```json
{
  "BidderID": 7,
  "bid_note": "Executed",
  "bidder_alias": "G&W",
  "bidder_type": "s",
  "process_phase": 1,
  "bid_value_low": null,
  "bid_value_high": null,
  "bid_value_unit": null,
  "consideration_components": null,
  "submitted_formal_bid": null,
  "invited_to_formal_round": null,
  "role": "bidder",
  "source_quote": "On May 15, 2014, the Company entered into a definitive agreement with G&W for the acquisition.",
  "source_page": 27,
  "bid_date_precise": "2014-05-15",
  "additional_note": "Press release restated the previously-disclosed $25.00 per share consideration.",
  "flags": []
}
```

### Example 3 — Unnamed NDA placeholder + later named-bid promotion

```json
{
  "BidderID": 2,
  "bid_note": "NDA",
  "bidder_alias": "Unnamed Cohort N=3",
  "bidder_type": null,
  "process_phase": 1,
  "role": "bidder",
  "source_quote": "Three additional financial sponsors executed confidentiality agreements during this period.",
  "source_page": 24,
  "bid_date_rough": "early-2014-Q2",
  "bid_date_precise": null,
  "unnamed_nda_promotion": null,
  "flags": []
}
```

A subsequent named bid by Bidder F (one of those three) promotes the placeholder:

```json
{
  "BidderID": 4,
  "bid_note": "Bid",
  ...
  "unnamed_nda_promotion": {
    "from_bidder_id": 2,
    "cohort_remaining_count": 2
  },
  ...
}
```

### Example 4 — Buyer Group with constituents found via search_filing

After calling `search_filing("by and among", page_range=null, max_hits=10)` and discovering merger-agreement page 41, atomize the Buyer Group into per-constituent rows:

```json
{
  "BidderID": 6,
  "bid_note": "Bid",
  "bid_type": "formal",
  "bidder_alias": "BC Partners",
  "bidder_type": "f",
  "process_phase": 2,
  "buyer_group_constituents": ["BC Partners", "La Caisse", "GIC", "StepStone", "Longview"],
  "consortium_role": "lead",
  ...
  "source_quote": "by and among Petsmart, Inc., and Argos Holdings Inc., a Delaware corporation formed by funds advised by BC Partners, with co-investment from La Caisse de dépôt et placement du Québec, GIC Pte. Ltd., StepStone Group LP, and Longview Asset Management.",
  "source_page": 41,
  "flags": []
}
```
```

- [ ] **Step 2: Commit**

```bash
git add prompts/extract.md
git commit -m "prompt: add four canonical few-shot row examples (Bid/Executed/Unnamed/Consortium)"
```

### Task F.4: Update the pre-flight checklist + completion check

**Files:**
- Modify: `prompts/extract.md` (currently lines 202–224)

- [ ] **Step 1: Rewrite the completion checklist to reference tool calls**

```markdown
## Before submitting your final extraction, verify

1. You called `check_row` on every emitted event row and the result was `ok: true`.
2. Every row has a `source_quote` that appears verbatim (after NFKC normalization) on the cited `source_page` — `check_row` enforces this.
3. Every Bid row's `bid_value_*` fields are populated; every non-Bid row's `bid_value_*` fields are null (§P-R9).
4. Buyer Group / Consortium rows have `buyer_group_constituents` populated. If the Background slice does not name them, you searched the merger-agreement section with `search_filing` first.
5. BidderIDs are 1, 2, 3, ... contiguous, monotonic in time, no gaps.
6. Your final output is a single JSON object `{deal, events}` with no commentary, no markdown fences.
```

- [ ] **Step 2: Commit**

```bash
git add prompts/extract.md
git commit -m "prompt: completion checklist references tool calls and atomization"
```

**Workstream F acceptance:** `prompts/extract.md` contains tool-use guidance, promoted §P-R9 paragraph, four canonical examples, updated completion checklist; old "do not call tools" warning is gone.

---

## Workstream G-DOCS — Contract docs cleanse [PARALLEL with B, F, E-INFRA]

### Task G.5: Delete the superseded design spec

- [ ] **Step 1: Verify the file exists**

```bash
ls docs/superpowers/specs/2026-04-29-robust-extraction-redesign.md
```

- [ ] **Step 2: Delete and commit**

```bash
git rm docs/superpowers/specs/2026-04-29-robust-extraction-redesign.md
git commit -m "docs: remove superseded 04-29 redesign spec (replaced by 04-30 overhaul spec)"
```

### Task G.6: Synchronized rewrite of CLAUDE.md, AGENTS.md, SKILL.md

**Files:**
- Modify: `CLAUDE.md` (lines 23-26 about prompt-only JSON / structured output disabled)
- Modify: `AGENTS.md` (same lines)
- Modify: `SKILL.md` (lines 39-41)

- [ ] **Step 1: Find every reference to "prompt-only JSON", "structured output", "json_schema_used", "Linkflow disables"**

```bash
grep -n -E "prompt-only JSON|structured output|json_schema_used|Linkflow.*disable" CLAUDE.md AGENTS.md SKILL.md
```

- [ ] **Step 2: Replace the architecture paragraph in all three files with the new contract**

The replacement text (paste into all three; they should remain in lockstep):

```markdown
## Current Architecture

The live architecture is code-orchestrated direct `AsyncOpenAI` SDK calls to
the Responses streaming endpoint (`responses.stream`) through the
Linkflow/NewAPI-compatible `OPENAI_BASE_URL`. Configure it with
`OPENAI_BASE_URL` and `OPENAI_API_KEY`; model names come from `EXTRACT_MODEL`
and `ADJUDICATE_MODEL` or CLI overrides.

Every extractor call uses **strict `text.format=json_schema`** with the
hardened `SCHEMA_R1`, plus three native function-calling tools available to
the model during drafting:

- `check_row(row)` — row-local validator wrapper (§P-R0..R9 + §P-D1/D2/D7 + §P-G2).
- `search_filing(query, page_range, max_hits)` — substring search over filing pages.
- `get_pages(start_page, end_page)` — contiguous page fetch (cap = 10 pages per call).

After the model emits its final extraction, Python `pipeline.core.validate()`
runs. If hard flags remain, an outer **repair loop** (cap = 2 turns) sends the
validator report back and asks for a complete revised extraction. On cap-hit,
finalization records a `repair_loop_exhausted` deal-level hard flag and the
deal status is `validated`.

The scoped Adjudicator stays single-turn, no tools, soft-flag verdicts only.

There is no prompt-only JSON path. There is no structured-output disable
branch. There is no `previous_response_id` chain (Linkflow returns 400).
Streaming is used for every full-extraction turn; non-streaming for short
tool-call turns to avoid the SDK accumulator empty-output bug.
```

- [ ] **Step 3: Update the per-deal flow diagram in all three files**

Replace the existing flow diagram with:

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

- [ ] **Step 4: Verify no stale references remain**

```bash
grep -n -E "prompt-only|json_schema_used=false|structured-output disable" CLAUDE.md AGENTS.md SKILL.md
```
Expected: zero hits.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md AGENTS.md SKILL.md
git commit -m "docs: rewrite live contracts for strict schema + tools + repair loop architecture

Synchronized rewrite of CLAUDE.md, AGENTS.md, SKILL.md. Removes prompt-only-JSON
language, documents the three extractor tools, the repair loop semantics, and
the kept-but-scoped adjudicator. No backward-compatibility prose."
```

### Task G.7: Rewrite docs/linkflow-extraction-guide.md from scratch

**Files:**
- Modify: `docs/linkflow-extraction-guide.md` (full rewrite; keep filename and any external links pointing at it stable)

- [ ] **Step 1: Replace the file with the new operator-facing guide**

The new guide should cover:

1. Linkflow proxy facts (key, base URL, gpt-5.5, xhigh, 5-worker ceiling, 300s streaming timeout).
2. Strict json_schema is the default extraction shape; SCHEMA_R1 hardened with `additionalProperties:false`, complete `required` lists, `maxLength: 1500` on quotes.
3. The three extractor tools (signatures, when to use, examples).
4. Multi-turn extraction loop: full-input replay every turn, no `previous_response_id`, parallel function_calls expected.
5. Streaming policy: streaming for full-extraction turns, non-streaming for tool-call turns.
6. Repair loop semantics: cap = 2, fail-loud on cap-hit, complete-revision protocol, `repair_loop_exhausted` flag.
7. Audit additions: `tool_calls.jsonl`, `repair_turns.jsonl`, manifest fields (`tools_contract_version`, `repair_loop_contract_version`, `repair_turns_used`, `repair_loop_outcome`).
8. Cache eligibility: requires all three contract versions to match.
9. Stability gate operator protocol (unchanged from prior guide; reference the existing pipeline.stability + pipeline.reconcile commands).

Do NOT carry forward the old "prompt-only JSON matters on Linkflow", "What Makes Linkflow Shaky", or "structured output disabled" paragraphs.

- [ ] **Step 2: Commit**

```bash
git add docs/linkflow-extraction-guide.md
git commit -m "docs: rewrite linkflow-extraction-guide.md for strict schema + tools + repair loop"
```

**Workstream G-DOCS acceptance:** spec deleted, three contract files synchronized, linkflow guide rewritten. `grep -nR "prompt-only JSON\|json_schema_used=false" docs/ CLAUDE.md AGENTS.md SKILL.md` returns zero hits.

---

## Workstream E-INFRA — Contract version hashing [PARALLEL with B, F, G-DOCS]

### Task E.4: Implement repair_loop_contract_version

**Files:**
- Modify: `pipeline/llm/tools.py` (add `tools_contract_version` — already done in B.4)
- Create: `pipeline/llm/contracts.py`
- Create: `tests/llm/test_contracts.py`

- [ ] **Step 1: Write failing test**

```python
# tests/llm/test_contracts.py
from pipeline.llm import contracts


def test_repair_loop_contract_version_is_stable():
    a = contracts.repair_loop_contract_version()
    b = contracts.repair_loop_contract_version()
    assert a == b
    assert len(a) == 16  # truncated sha256


def test_repair_loop_contract_version_changes_with_cap():
    """Pin the cap value into the hash so changing it invalidates cache."""
    src = contracts._REPAIR_LOOP_CONTRACT_INPUTS
    assert "MAX_REPAIR_TURNS" in src
```

- [ ] **Step 2: Run to verify it fails**

- [ ] **Step 3: Implement `pipeline/llm/contracts.py`**

```python
# pipeline/llm/contracts.py
"""Centralized contract-version hashing for cache eligibility checks.

Three contract hashes are tracked in audit manifests:
- rulebook_version (rules/*.md)         → pipeline.core.rulebook_version()
- extractor_contract_version (prompt+local schema mirror)
                                          → pipeline.llm.extract.extractor_contract_version()
- tools_contract_version (tool defs + impls)
                                          → pipeline.llm.tools.tools_contract_version()
- repair_loop_contract_version (cap + repair prompt + report formatter)
                                          → this module

Cache eligibility = all four hashes match the cached run's manifest.
"""
from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

MAX_REPAIR_TURNS = 2

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"
_REPAIR_PROMPT_PATH = _PROMPTS_DIR / "repair.md"


def _load_repair_prompt() -> str:
    if _REPAIR_PROMPT_PATH.exists():
        return _REPAIR_PROMPT_PATH.read_text()
    return ""  # may not exist yet during E.4 (prompts/repair.md is created in D.1)


_REPAIR_LOOP_CONTRACT_INPUTS = {
    "MAX_REPAIR_TURNS": MAX_REPAIR_TURNS,
    "repair_prompt_path": str(_REPAIR_PROMPT_PATH),
    # Note: extract.run_repair_loop source is hashed here once D.2 lands.
    # This module deliberately only depends on the cap + prompt for E.4;
    # D.2 will wire in the source hash via importlib at runtime.
}


def repair_loop_contract_version() -> str:
    """Truncated sha256 of cap + repair prompt + repair-loop runner source.

    Source hashing of the repair loop runner is deferred until D.2 lands.
    """
    payload = repr(_REPAIR_LOOP_CONTRACT_INPUTS) + _load_repair_prompt()
    try:
        from pipeline.llm import extract  # noqa: WPS433 — runtime import
        if hasattr(extract, "run_repair_loop"):
            payload += inspect.getsource(extract.run_repair_loop)
    except Exception:  # pragma: no cover — extract may not yet have run_repair_loop
        pass
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
```

- [ ] **Step 4: Run tests, commit**

```bash
pytest tests/llm/test_contracts.py -v
git add pipeline/llm/contracts.py tests/llm/test_contracts.py
git commit -m "feat: repair_loop_contract_version hash for cache eligibility"
```

**Workstream E-INFRA acceptance:** `pytest tests/llm/test_contracts.py` passes. The full source-hashing wires up later when `extract.run_repair_loop` exists (D.2).

---

## Workstream C — Client + extract orchestration [SEQUENTIAL after Phase 2]

### Task C.1: Strip schema_supported / structured-output disable from client

**Files:**
- Modify: `pipeline/llm/client.py` — remove `_is_newapi_base_url`, set `supports_structured_output = True` unconditionally, add `tools` and `tool_choice` parameters

- [ ] **Step 1: Update existing test for the new contract**

In `tests/llm/test_client.py`, find any test asserting `supports_structured_output is False` for newapi base_urls; rewrite to assert `True` unconditionally.

- [ ] **Step 2: Add a failing test for tools parameter pass-through**

```python
# tests/llm/test_client.py — add this test
import pytest
from unittest.mock import AsyncMock, MagicMock
from pipeline.llm.client import OpenAICompatibleClient


@pytest.mark.asyncio
async def test_complete_passes_tools_and_tool_choice_through():
    client = OpenAICompatibleClient(
        base_url="https://www.linkflow.run/v1", api_key="x", default_model="gpt-5.5",
    )
    mock_resp = MagicMock()
    mock_resp.output_text = '{"a":1}'
    mock_resp.output = []
    mock_resp.usage = MagicMock(input_tokens=0, output_tokens=0, reasoning_tokens=0)
    client._client = MagicMock()
    client._client.responses.create = AsyncMock(return_value=mock_resp)

    tools = [{"type": "function", "name": "x", "parameters": {"type": "object", "properties": {}}}]
    await client.complete(
        model="gpt-5.5", system="s", user="u",
        tools=tools, tool_choice="auto",
    )
    call_kwargs = client._client.responses.create.call_args.kwargs
    assert call_kwargs["tools"] == tools
    assert call_kwargs["tool_choice"] == "auto"
```

- [ ] **Step 3: Run to verify it fails**

- [ ] **Step 4: Implement**

In `pipeline/llm/client.py`:
- Delete `_is_newapi_base_url` and any reference to it.
- Set `OpenAICompatibleClient.supports_structured_output = True` unconditionally; remove the conditional in `__init__`.
- Add `tools: list[dict] | None = None` and `tool_choice: str = "auto"` parameters to `LLMClient.complete()` (abstract) and `OpenAICompatibleClient.complete()` (concrete).
- In the concrete impl, pass `tools=tools, tool_choice=tool_choice` through to `self._client.responses.create(...)` when `tools` is not None.
- Update `CompletionResult` to add `tool_calls: list[dict] = field(default_factory=list)` and populate it from `response.output` items where `type == "function_call"`.

- [ ] **Step 5: Run tests, commit**

```bash
pytest tests/llm/test_client.py -v
git add pipeline/llm/client.py tests/llm/test_client.py
git commit -m "feat: client supports tools+tool_choice; strict schema unconditional; remove newapi disable"
```

### Task C.2: Drop schema_supported branching in response_format and adjudicate

**Files:**
- Modify: `pipeline/llm/response_format.py:331-356` — `call_json` signature
- Modify: `pipeline/llm/extract.py:260` — `extract_deal` signature
- Modify: `pipeline/llm/adjudicate.py:78,96,114,137` — `adjudicate_extraction`

- [ ] **Step 1: Remove `schema_supported` parameter from `call_json`**

`call_json` should now always pass `text_format=json_schema_format(schema)`. Inline the unconditional path; remove the conditional.

- [ ] **Step 2: Remove `schema_supported` parameter from `extract_deal` and `adjudicate_extraction`**

Replace `"json_schema_used": schema_supported` audit entries with literal `True` (or drop the field; see E.3 for the audit shape change).

- [ ] **Step 3: Update all call sites in `pipeline/run_pool.py`**

```bash
grep -n schema_supported pipeline/run_pool.py
```
Remove every reference; the parameter no longer exists.

- [ ] **Step 4: Run all LLM tests**

```bash
pytest tests/llm/ -v
```

- [ ] **Step 5: Commit**

```bash
git add pipeline/llm/response_format.py pipeline/llm/extract.py pipeline/llm/adjudicate.py pipeline/run_pool.py tests/
git commit -m "refactor: drop schema_supported parameter throughout (strict schema unconditional)"
```

### Task C.3: Multi-turn extraction loop (tool execution harness)

**Files:**
- Modify: `pipeline/llm/extract.py` — replace single-turn call with multi-turn loop
- Modify: `tests/llm/test_extract.py` — update tests for new shape

- [ ] **Step 1: Write failing test for multi-turn behavior**

```python
# Add to tests/llm/test_extract.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from pipeline.llm import extract
from pipeline.llm.client import CompletionResult


@pytest.mark.asyncio
async def test_extract_runs_tool_calls_and_replays_until_final_message(tmp_path, monkeypatch):
    # Turn 1 returns a function_call; turn 2 returns final extraction text.
    fc = {"type": "function_call", "name": "check_row", "call_id": "c1", "arguments": '{"row":{}}'}
    turn1 = CompletionResult(
        text="", model="gpt-5.5", parsed_json=None, tool_calls=[fc],
    )
    turn2 = CompletionResult(
        text='{"deal":{},"events":[]}', model="gpt-5.5",
        parsed_json={"deal": {}, "events": []}, tool_calls=[],
    )
    mock_client = MagicMock()
    mock_client.complete = AsyncMock(side_effect=[turn1, turn2])
    # ... (fixture setup for extract.extract_deal omitted for brevity in plan;
    #      executing agent should mirror the existing test_extract.py fixtures)

    # Verify: client.complete is called twice; second call's input includes
    # the function_call item and a function_call_output item for c1.
```

- [ ] **Step 2: Implement the multi-turn loop**

The loop in `extract_deal`:
1. Build initial `input` = [system msg, user msg].
2. Loop (max safety bound, e.g., 5 tool-call turns):
   a. Call `client.complete(input=input, tools=TOOL_DEFINITIONS, tool_choice="auto", text_format=json_schema_format(SCHEMA_R1), ...)`.
   b. If `result.tool_calls` is empty AND `result.parsed_json` is non-null → break (final extraction received).
   c. Otherwise: dispatch each tool call locally via `tools.dispatch(name, args, filing_pages=...)`; append the function_call items and function_call_output items to `input`; continue.
3. Return the final extraction.
4. Each tool call is logged for the audit writer (E.1).

Streaming policy: turns where the model is expected to emit a long body (initial + final after tools) use `client.complete_stream(...)` (or however the existing streaming wrapper is named); turns that consist of tool calls only use non-streaming.

- [ ] **Step 3: Run tests, real-API probe**

```bash
pytest tests/llm/test_extract.py -v
```

- [ ] **Step 4: Real-API probe — single-deal extraction with new loop**

```bash
# Uses medivation pages 24-27 to mirror T7
OPENAI_API_KEY=<key> OPENAI_BASE_URL=https://www.linkflow.run/v1 \
  EXTRACT_MODEL=gpt-5.5 \
  python run.py --slug medivation --extract --extract-reasoning-effort xhigh --print-prompt false
```

Expected: extraction completes; `output/audit/medivation/runs/{run_id}/` is written with at least one tool call recorded; final extraction parses against SCHEMA_R1.

- [ ] **Step 5: Commit**

```bash
git add pipeline/llm/extract.py tests/llm/test_extract.py
git commit -m "feat: multi-turn extraction loop with tool dispatch and full-input replay"
```

### Task C.4: Streaming policy (stream long turns, non-stream tool turns)

**Files:**
- Modify: `pipeline/llm/extract.py`

- [ ] **Step 1: In the extraction loop, branch by expected turn type**

- Initial turn: streaming (model may emit final extraction directly with no tool calls).
- After turn 1, if `tool_calls` were emitted, the next turn is non-streaming (we send tool outputs; model responds with either more tool calls or the final body — we want non-streaming to bypass the SDK accumulator empty-output bug; if the response body comes back large, the SDK gives us the full text in a single object).
- For the final body (no more tool calls expected), use streaming.

A simpler heuristic: alternate streaming/non-streaming based on `tool_choice`. When the model is expected to be done with tools, stream. When we are sending function_call_output and don't yet know if it's the final turn, non-stream the next response.

- [ ] **Step 2: Verify on a deal that triggers many tool calls**

```bash
python run.py --slug petsmart-inc --extract --extract-reasoning-effort xhigh
```

Expected: extraction completes; audit shows N tool turns + 1 final body turn; no `stream.get_final_response().output` empty-output errors.

- [ ] **Step 3: Commit**

```bash
git add pipeline/llm/extract.py
git commit -m "feat: streaming policy — stream long body turns, non-stream tool-call turns"
```

### Task C.5: End-to-end probe of new extraction path

**Files:**
- Create: `quality_reports/extraction_probe/2026-04-30_medivation_new_path.json`

- [ ] **Step 1: Run extraction on medivation, capture outcome**

```bash
python run.py --slug medivation --extract --extract-reasoning-effort xhigh
```

- [ ] **Step 2: Verify the output extraction matches SCHEMA_R1 and contains the expected events**

The medivation reference deal has 16 events (rows 6060-6075 in Alex's workbook). Confirm `output/extractions/medivation.json` parses, has 10–20 events, and that no row violates §P-R9.

- [ ] **Step 3: Commit the probe artifact**

```bash
git add quality_reports/extraction_probe/
git commit -m "extraction-probe: medivation passes through new strict-schema + tools loop"
```

**Workstream C acceptance:** `pytest tests/llm/` passes; medivation extracts cleanly through the new path; audit shows tool calls; no `schema_supported` references remain.

---

## Workstream D — Repair loop [SEQUENTIAL after C]

### Task D.1: Repair turn prompt template

**Files:**
- Create: `prompts/repair.md`

- [ ] **Step 1: Write the repair turn prompt**

```markdown
# Repair turn prompt

You produced a draft extraction that failed Python validation with the hard
flags listed below. Your job: emit a **complete revised extraction** that
addresses every flag. Do not emit patches or partial output. Re-emit the full
{deal, events} JSON body matching SCHEMA_R1.

## Validator report

{validator_report}

## Affected event rows (from your previous draft)

{affected_rows}

## Filing snippets cited by source_quote on those rows

{filing_snippets}

## Rules and tools

The same SCHEMA_R1 contract applies. The same three tools are available
(check_row, search_filing, get_pages). You may call them as needed. After
tool calls, emit the complete revised {deal, events} JSON.

If a flag describes a contradiction in the filing itself rather than your
extraction (e.g., the filing genuinely does not name consortium constituents),
you MAY emit the affected row with an explicit `flags: [{"code": ...,
"severity": "soft", "reason": "filing does not name X"}]` annotation rather
than fabricate evidence. The repair loop will accept soft-flagged rows; only
hard flags trigger another repair turn.
```

- [ ] **Step 2: Commit**

```bash
git add prompts/repair.md
git commit -m "prompt: repair turn template (validator report + rows + snippets)"
```

### Task D.2: Repair loop orchestration in extract.py

**Files:**
- Modify: `pipeline/llm/extract.py` — add `run_repair_loop`
- Modify: `pipeline/core.py` — add `compact_validator_report(flags)` helper

- [ ] **Step 1: Write failing test**

```python
# Add to tests/llm/test_extract.py
@pytest.mark.asyncio
async def test_repair_loop_revises_until_clean_or_cap(monkeypatch, tmp_path):
    # Mock client: turn 1 returns extraction with §P-R9 violation; repair turn
    # returns clean extraction. Verify validate() called twice, extract returned.
    ...


@pytest.mark.asyncio
async def test_repair_loop_emits_repair_loop_exhausted_on_cap_hit(monkeypatch, tmp_path):
    # Mock client: turn 1 + 2 + 3 all return same hard flag. Verify final
    # extraction has a deal-level repair_loop_exhausted flag with severity=hard.
    ...
```

- [ ] **Step 2: Run to verify it fails**

- [ ] **Step 3: Implement `compact_validator_report` in `pipeline/core.py`**

```python
def compact_validator_report(row_flags, deal_flags) -> dict:
    """Return a compact summary suitable for sending back to the model.

    {
      "row_flags": [{"row_index": int, "code": str, "severity": str, "reason": str}],
      "deal_flags": [{"code": str, "severity": str, "reason": str}],
      "hard_count": int, "soft_count": int, "info_count": int,
    }
    """
    ...
```

- [ ] **Step 4: Implement `run_repair_loop` in `pipeline/llm/extract.py`**

```python
from pipeline.llm.contracts import MAX_REPAIR_TURNS


async def run_repair_loop(
    *,
    initial_draft: dict,
    initial_flags: tuple[list, list],
    slug: str,
    llm_client,
    extract_model: str,
    audit: AuditWriter,
    filing_pages: list,
    repair_prompt_template: str,
) -> tuple[dict, str]:
    """Run up to MAX_REPAIR_TURNS repair turns. Returns (final_draft, outcome).

    outcome ∈ {"clean", "fixed", "exhausted"}.
    "clean": initial draft had no hard flags (no repair needed).
    "fixed": repair turn(s) closed all hard flags.
    "exhausted": cap hit; final draft still has hard flags; caller must append
                 a deal-level `repair_loop_exhausted` flag.
    """
    draft = initial_draft
    row_flags, deal_flags = initial_flags
    if not any(f.severity == "hard" for f in row_flags + deal_flags):
        return draft, "clean"
    for turn in range(1, MAX_REPAIR_TURNS + 1):
        # Build repair prompt: validator report + affected rows + snippets
        report = core.compact_validator_report(row_flags, deal_flags)
        affected = [draft["events"][f.row_index] for f in row_flags if hasattr(f, "row_index")]
        snippets = _gather_snippets(affected, filing_pages)
        repair_user = repair_prompt_template.format(
            validator_report=json.dumps(report, indent=2),
            affected_rows=json.dumps(affected, indent=2),
            filing_snippets=json.dumps(snippets, indent=2),
        )
        # Call extractor again with same tools, full input replay
        revised = await _call_with_tools(
            llm_client=llm_client, model=extract_model,
            system=_repair_system_prompt(), user=repair_user,
            filing_pages=filing_pages, audit=audit,
            phase=f"repair_turn_{turn}",
        )
        # Re-validate
        prep = core.prepare_for_validate(slug, revised)
        row_flags, deal_flags = core.validate(prep)
        audit.write_repair_turn({
            "turn": turn,
            "validator_report_summary": report,
            "hard_flags_before": report["hard_count"],
            "hard_flags_after": sum(1 for f in row_flags + deal_flags if f.severity == "hard"),
        })
        draft = revised
        if not any(f.severity == "hard" for f in row_flags + deal_flags):
            return draft, "fixed"
    return draft, "exhausted"
```

- [ ] **Step 5: Wire `run_repair_loop` into `extract_deal` and `process_deal`**

After the initial extraction, call `validate()`, then `run_repair_loop()`. If `outcome == "exhausted"`, append `{"code": "repair_loop_exhausted", "severity": "hard", "reason": "..."}` to deal flags before finalizing.

- [ ] **Step 6: Run tests, commit**

```bash
pytest tests/llm/test_extract.py -v
git add pipeline/llm/extract.py pipeline/core.py tests/
git commit -m "feat: repair loop orchestration (cap=2, fail-loud on cap-hit)"
```

### Task D.3: Real-API probe — repair loop on a known-bad deal

- [ ] **Step 1: Run on zep (currently 2 hard flags)**

```bash
python run.py --slug zep --extract --extract-reasoning-effort xhigh
```

- [ ] **Step 2: Inspect audit**

```bash
cat output/audit/zep/runs/$(jq -r .run_id output/audit/zep/latest.json)/repair_turns.jsonl
cat output/audit/zep/runs/$(jq -r .run_id output/audit/zep/latest.json)/manifest.json | jq '.repair_loop_outcome,.repair_turns_used'
```

Expected outcomes — any one of:
- `outcome=clean` (initial draft had no hard flags; tools/prompt enhancements prevented them).
- `outcome=fixed` (repair loop closed the hard flags).
- `outcome=exhausted` (cap hit; deal-level `repair_loop_exhausted` flag appended; status=`validated`).

Capture the outcome in a probe artifact.

- [ ] **Step 3: Commit probe artifact**

```bash
git add quality_reports/repair_probe/
git commit -m "repair-probe: zep extraction with repair loop (outcome captured)"
```

**Workstream D acceptance:** `pytest tests/llm/test_extract.py` passes; zep run completes with one of the three valid outcomes; `output/audit/zep/runs/.../repair_turns.jsonl` exists when repair turns run.

---

## Workstream E-AUDIT — Audit extensions [SEQUENTIAL after D]

### Task E.1: tool_calls.jsonl writer

**Files:**
- Modify: `pipeline/llm/audit.py` — add `write_tool_call(record)`

- [ ] **Step 1: Write failing test in `tests/llm/test_audit.py`**

```python
def test_audit_writer_records_tool_calls(tmp_path):
    writer = AuditWriter(tmp_path / "runs/r1", slug="x", run_id="r1")
    writer.write_tool_call({
        "turn": 1, "call_id": "c1", "name": "check_row",
        "args": {"row": {"a": 1}},
        "result": {"ok": True, "violations": []},
        "latency_ms": 12.4,
    })
    lines = (tmp_path / "runs/r1/tool_calls.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["name"] == "check_row"
```

- [ ] **Step 2: Implement**

Truncate `result` JSON if it exceeds 8000 chars; mark `result_truncated=true`.

- [ ] **Step 3: Test, commit**

```bash
pytest tests/llm/test_audit.py -v
git add pipeline/llm/audit.py tests/llm/test_audit.py
git commit -m "feat: AuditWriter.write_tool_call writes to tool_calls.jsonl"
```

### Task E.2: repair_turns.jsonl writer

**Files:**
- Modify: `pipeline/llm/audit.py`
- Modify: `tests/llm/test_audit.py`

- [ ] **Step 1: Write failing test**

```python
def test_audit_writer_records_repair_turns(tmp_path):
    writer = AuditWriter(tmp_path / "runs/r1", slug="x", run_id="r1")
    writer.write_repair_turn({
        "turn": 1,
        "validator_report_summary": {"hard_count": 3, "soft_count": 2, "info_count": 0},
        "hard_flags_before": 3, "hard_flags_after": 0,
        "latency_ms": 18000.5,
    })
    lines = (tmp_path / "runs/r1/repair_turns.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
```

- [ ] **Step 2: Implement, test, commit**

```bash
pytest tests/llm/test_audit.py -v
git add pipeline/llm/audit.py tests/llm/test_audit.py
git commit -m "feat: AuditWriter.write_repair_turn writes to repair_turns.jsonl"
```

### Task E.3: Manifest extension

**Files:**
- Modify: `pipeline/llm/audit.py` — extend `write_manifest`
- Modify: `tests/llm/test_audit.py`

- [ ] **Step 1: Write failing test**

```python
def test_manifest_includes_new_contract_fields(tmp_path):
    writer = AuditWriter(tmp_path / "runs/r1", slug="x", run_id="r1")
    writer.write_manifest(
        action="extract", rulebook_version="rb1",
        extractor_contract_version="ec1", tools_contract_version="tc1",
        repair_loop_contract_version="rlc1", repair_turns_used=1,
        repair_loop_outcome="fixed", tool_calls_count=12,
        # ... existing fields ...
    )
    m = json.loads((tmp_path / "runs/r1/manifest.json").read_text())
    assert m["tools_contract_version"] == "tc1"
    assert m["repair_loop_contract_version"] == "rlc1"
    assert m["repair_turns_used"] == 1
    assert m["repair_loop_outcome"] == "fixed"
    assert m["tool_calls_count"] == 12
    assert "json_schema_used" not in m  # field dropped
```

- [ ] **Step 2: Implement**

Drop the `json_schema_used` field. Add the four new fields. Update any test that asserts the old `json_schema_used` key — it should be deleted (per spec §8.a).

- [ ] **Step 3: Test, commit**

```bash
pytest tests/llm/test_audit.py -v
git add pipeline/llm/audit.py tests/llm/test_audit.py
git commit -m "feat: manifest carries tools/repair-loop contract versions; drop json_schema_used"
```

### Task E.5: Cache eligibility threading

**Files:**
- Modify: `pipeline/run_pool.py` — cache eligibility checks

- [ ] **Step 1: Find all cache eligibility checks**

```bash
grep -n "rulebook_version\|extractor_contract_version" pipeline/run_pool.py
```

- [ ] **Step 2: Extend the check**

A cached run is eligible for `--re-validate` only if all four hashes match: `rulebook_version`, `extractor_contract_version`, `tools_contract_version`, `repair_loop_contract_version`.

- [ ] **Step 3: Update `pipeline/reconcile.py` and `pipeline/stability.py`** to require the same four fields when matching archived runs.

- [ ] **Step 4: Run reconcile/stability tests**

```bash
pytest tests/test_reconcile.py tests/test_stability.py tests/test_run_pool.py -v
```

- [ ] **Step 5: Commit**

```bash
git add pipeline/run_pool.py pipeline/reconcile.py pipeline/stability.py tests/
git commit -m "refactor: cache eligibility requires four contract hashes"
```

**Workstream E-AUDIT acceptance:** `pytest tests/llm/test_audit.py tests/test_reconcile.py tests/test_stability.py tests/test_run_pool.py` passes; manifest and audit files written by a real run have the new fields.

---

## Workstream G-DATA — Cleanse data artifacts [SEQUENTIAL after E]

### Task G.1 / G.2: Delete obsolete tests

**Files:**
- Modify: `tests/llm/test_extract.py` — delete `test_extract_deal_uses_prompt_only_json_when_schema_unsupported`
- Modify: `tests/llm/test_adjudicate.py` — delete `test_adjudicate_prompt_only_json_when_schema_unsupported`

- [ ] **Step 1: Delete the obsolete tests**

If C.2 already removed them via `schema_supported` cleanup, this task is a no-op verification step.

- [ ] **Step 2: Run full test suite**

```bash
pytest tests/ -v
```

- [ ] **Step 3: Commit (if any deletion happened)**

```bash
git add tests/
git commit -m "test: remove obsolete json_schema_used=False assertions"
```

### Task G.3 / G.4: Verify cleanup of `_is_newapi_base_url` and `schema_supported`

- [ ] **Step 1: Sanity grep**

```bash
grep -rn "_is_newapi_base_url\|schema_supported" pipeline/ tests/ docs/ scripts/ prompts/
```

Expected: zero hits. If any remain, fix and commit.

### Task G.8: Archive state/flags.jsonl

- [ ] **Step 1: Move and reset**

```bash
mkdir -p state/flags.archive
mv state/flags.jsonl state/flags.archive/2026-04-30_pre-overhaul.jsonl
touch state/flags.jsonl
git add state/flags.archive/2026-04-30_pre-overhaul.jsonl state/flags.jsonl
git commit -m "state: archive pre-overhaul flags.jsonl; start fresh empty log"
```

### Task G.9: Reset reference progress entries

- [ ] **Step 1: Update state/progress.json**

For each of the 9 reference slugs (providence-worcester, medivation, imprivata, zep, petsmart-inc, penford, mac-gray, saks, stec), set:

```json
{
  "status": "pending",
  "flag_count": 0,
  "last_run": null,
  "last_run_id": null,
  "rulebook_version": null,
  "rulebook_version_history": [],
  "notes": "reset for 2026-04-30 overhaul"
}
```

Target-deal entries are not modified.

- [ ] **Step 2: Commit**

```bash
git add state/progress.json
git commit -m "state: reset 9 reference deals to pending for 2026-04-30 overhaul"
```

### Task G.10–G.12: Delete loose audit files, runs, and extractions

- [ ] **Step 1: Delete loose audit files**

```bash
for slug in providence-worcester medivation imprivata zep petsmart-inc penford mac-gray saks stec; do
  rm -f output/audit/$slug/calls.jsonl
  rm -f output/audit/$slug/manifest.json
  rm -f output/audit/$slug/raw_response.json
done
```

- [ ] **Step 2: Delete runs and extractions for the 9 reference slugs**

```bash
for slug in providence-worcester medivation imprivata zep petsmart-inc penford mac-gray saks stec; do
  rm -rf output/audit/$slug/runs
  rm -f output/audit/$slug/latest.json
  rm -f output/extractions/$slug.json
done
```

- [ ] **Step 3: Verify nothing remains for the references**

```bash
for slug in providence-worcester medivation imprivata zep petsmart-inc penford mac-gray saks stec; do
  ls output/audit/$slug/ 2>/dev/null && echo "$slug remains" || true
done
```

Expected: `latest.json` removed; only an empty (or near-empty) directory.

- [ ] **Step 4: Commit**

```bash
git add output/
git commit -m "data: delete legacy audit + extractions for 9 reference slugs (full regen pending)"
```

**Workstream G-DATA acceptance:** `pytest tests/` passes; no `_is_newapi_base_url` or `schema_supported` references; reference deals are pending; their audit/extraction artifacts are gone.

---

## Workstream H — Reference verification + stability [SEQUENTIAL, may iterate]

### Task H.1: First reference batch under new pipeline

- [ ] **Step 1: Run the reference batch**

```bash
OPENAI_API_KEY=<key> OPENAI_BASE_URL=https://www.linkflow.run/v1 \
  EXTRACT_MODEL=gpt-5.5 ADJUDICATE_MODEL=gpt-5.5 \
  python -m pipeline.run_pool --filter reference --workers 5 \
  --extract-reasoning-effort xhigh
```

Expected wall time: ~30-60 minutes (5 deals in parallel × ~10-15 min each at xhigh with tools).

- [ ] **Step 2: Inspect outcomes**

```bash
cat state/progress.json | jq '.deals | to_entries | map(select(.value.status != "pending"))'
cat state/flags.jsonl | jq -s '.'
```

Per slug, capture: status, flag_count, repair_turns_used, repair_loop_outcome.

- [ ] **Step 3: Save batch summary**

```bash
mkdir -p quality_reports/reference_batches
python -c "
import json, pathlib
prog = json.load(open('state/progress.json'))
refs = ['providence-worcester','medivation','imprivata','zep','petsmart-inc','penford','mac-gray','saks','stec']
out = {s: prog['deals'][s] for s in refs}
pathlib.Path('quality_reports/reference_batches/2026-04-30_batch_1.json').write_text(json.dumps(out, indent=2))
"
git add quality_reports/reference_batches/
git commit -m "reference-batch-1: first run under new strict-schema + tools + repair pipeline"
```

### Task H.2: Reconcile and analyze hard flags

- [ ] **Step 1: Run reconcile**

```bash
python -m pipeline.reconcile --scope reference
```

Expected: PASS for all 9 deals. If any fail, the reconcile output names the mismatched fields — fix the underlying cause (likely a missed manifest field).

- [ ] **Step 2: List remaining hard flags**

For any deal in `validated` status, list the `repair_loop_outcome` and the post-repair flags. Categorize each remaining hard flag into:
- **A. Content-correctness, fixable by retry** — the model misread; a fresh run may pass.
- **B. Content-correctness, fixable by prompt sharpening** — the model needs better guidance; iterate F.* and re-batch.
- **C. Rule-decision needed** — e.g., petsmart `buyer_group_constituents_incomplete` may genuinely require `rules/bidders.md` to specify whether the placeholder is acceptable.

- [ ] **Step 3: If any category-B issues, iterate**

Loop:
1. Sharpen `prompts/extract.md` (more specific guidance, additional few-shot example).
2. Commit prompt change.
3. Re-extract the affected deals: `python -m pipeline.run_pool --slugs <slug,slug> --workers 2 --extract-reasoning-effort xhigh`.
4. Re-reconcile.

Stop when all 9 deals are `passed`, `passed_clean`, or have only category-C blockers documented in `rules/`.

### Task H.3: Stability batches 2 and 3

- [ ] **Step 1: Re-run the reference batch twice more under unchanged hashes**

```bash
# Run 2
python -m pipeline.run_pool --filter reference --workers 5 --extract-reasoning-effort xhigh
# Save batch_2 summary as in H.1
# Run 3
python -m pipeline.run_pool --filter reference --workers 5 --extract-reasoning-effort xhigh
# Save batch_3 summary
```

- [ ] **Step 2: Run stability proof**

```bash
mkdir -p quality_reports/stability
python -m pipeline.stability --scope reference --runs 3 --json \
  --write quality_reports/stability/target-release-proof.json
```

Expected: `STABLE_FOR_REFERENCE_REVIEW` classification with `requested_runs >= 3` and at least 3 selected immutable run IDs per slug.

- [ ] **Step 3: Verify the gate would open**

```bash
python -m pipeline.run_pool --slugs <one_target_slug> --dry-run --release-targets
```

Expected: dry-run accepts the target deal selection (gate condition met).

- [ ] **Step 4: Commit stability proof**

```bash
git add quality_reports/stability/ quality_reports/reference_batches/
git commit -m "stability: 3 consecutive clean reference runs under new contract; gate opens"
```

### Task H.4: Final cleanup

- [ ] **Step 1: Run full test suite one last time**

```bash
pytest tests/ -v
```

Expected: PASS.

- [ ] **Step 2: Final grep for any forgotten staleness**

```bash
grep -rn -E "json_schema_used|prompt-only JSON|_is_newapi_base_url|schema_supported|do not call tools" \
  pipeline/ tests/ docs/ prompts/ rules/ CLAUDE.md AGENTS.md SKILL.md
```

Expected: zero hits.

- [ ] **Step 3: Push branch and open PR**

```bash
git push -u origin api-call
gh pr create --title "Extraction overhaul: strict schema + tools + repair loop" \
  --body "$(cat <<'EOF'
## Summary
- Replaces prompt-only-JSON Linkflow path with strict json_schema, three native function-calling tools (check_row, search_filing, get_pages), and an outer Python validation-repair loop (cap=2, fail-loud).
- Hard cleanse of stale code, docs, contract files, audit artifacts, tests in the same merge.
- Reference set re-extracted from scratch under the new contract; stability proof passes.

## Test plan
- [x] All unit tests pass (`pytest tests/`).
- [x] Three reference batches under unchanged hashes; `STABLE_FOR_REFERENCE_REVIEW`.
- [x] No stale references via grep gauntlet.
- [x] Linkflow real-API probes (schema, tools e2e, repair) all green.
EOF
)"
```

**Workstream H acceptance:** stability proof passes; all 9 reference deals are `passed`, `passed_clean`, or `verified`; PR open.

---

## Self-review checklist (executed during plan-writing)

**Spec coverage:**
- §1 Goal → covered by overall plan
- §2 Architecture → C.3, C.4, D.2 implement the diagram
- §3 Schema → A.1–A.3 (probe + harden) and C.2 (drop branching)
- §4 Tools → B.1–B.5 (all three tools + registry + e2e)
- §4d Prompt enhancements → F.1–F.4
- §5 Repair loop → D.1, D.2, D.3
- §6 Adjudicator → covered by C.2 (drop schema_supported); no other changes
- §7 Audit → E.1, E.2, E.3, E.5
- §8a Cleanse delete → G.1–G.4 (code), G.5 (spec), G.10–G.12 (audit/extraction)
- §8b Archive → G.8, G.9
- §8c Rewrite → C.1, C.2, F.*, G.6, G.7
- §9 Migration & verification → H.1–H.4
- §10 Risks → A.* (schema risk), C.4 (streaming risk), H.2 (petsmart resolution)
- §11 Tools rejected → not implemented (correctly)

All sections covered.

**Placeholder scan:** searched for "TBD", "TODO", "fill in", "appropriate error handling", "similar to Task N". None found.

**Type consistency:** `compact_validator_report` referenced in D.2 is created in D.2's Step 3. `tools.dispatch` is created in B.4 and referenced in C.3 and B.5. `MAX_REPAIR_TURNS` is in `pipeline/llm/contracts.py` (E.4) and referenced in D.2. `TOOL_DEFINITIONS` is in `pipeline/llm/tools.py` (B.4) and referenced in C.3 and B.5. Field names in audit manifest (`tools_contract_version`, `repair_loop_contract_version`, `repair_turns_used`, `repair_loop_outcome`, `tool_calls_count`) consistent across E.3 and E.5.

---

## Plan complete

Saved to `docs/superpowers/plans/2026-04-30-extraction-overhaul-implementation.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — orchestrator dispatches a fresh subagent per task, reviews between tasks, fast iteration. Phase 2 dispatches 4 agents in parallel. Best fit for this overhaul because of the parallel Phase 2 group and the per-task real-API verification gates.

2. **Inline Execution** — execute tasks in this session using `superpowers:executing-plans`, batch with checkpoints. Slower for this plan because Phase 2's parallelism is lost.

Which approach?
