import json

import pytest

from pipeline.llm.audit import AuditWriter, TokenBudget, TokenBudgetExceeded, prompt_hash
from pipeline.llm.client import CompletionResult


def test_prompt_hash_is_stable_sha256():
    assert prompt_hash("system", "user") == prompt_hash("system", "user")
    assert len(prompt_hash("system", "user")) == 64


def test_token_budget_tracks_usage_and_raises_at_limit():
    budget = TokenBudget(max_tokens=10)
    budget.consume(CompletionResult(text="", model="m", input_tokens=3, output_tokens=4, reasoning_tokens=2))

    assert budget.used == 9

    with pytest.raises(TokenBudgetExceeded):
        budget.consume(CompletionResult(text="", model="m", input_tokens=2))


def test_audit_writer_writes_prompt_call_raw_response_and_manifest(tmp_path):
    writer = AuditWriter(tmp_path, "deal")
    result = CompletionResult(
        text='{"deal":{},"events":[]}',
        model="gpt-test",
        input_tokens=1,
        output_tokens=2,
        reasoning_tokens=3,
        attempts=2,
    )

    digest = writer.write_prompt(phase="extractor", system="system text", user="user text")
    writer.write_raw_response(
        result=result,
        parsed_json={"deal": {}, "events": []},
        rulebook_version="ruleshash",
    )
    writer.append_call({
        "phase": "extract",
        "prompt_hash": digest,
        "input_tokens": 1,
        "output_tokens": 2,
        "reasoning_tokens": 3,
    })
    writer.write_manifest({
        "rulebook_version": "ruleshash",
        "models": {"extract": "gpt-test", "adjudicate": "gpt-test"},
        "total_input_tokens": 1,
        "total_output_tokens": 2,
        "total_reasoning_tokens": 3,
        "outcome": "passed_clean",
    })

    audit_dir = tmp_path / "deal"
    prompt_text = (audit_dir / "prompts" / "extractor.txt").read_text()
    assert "=== SYSTEM ===\nsystem text" in prompt_text
    assert "=== USER ===\nuser text" in prompt_text
    assert json.loads((audit_dir / "raw_response.json").read_text())["parsed_json"] == {"deal": {}, "events": []}
    call = json.loads((audit_dir / "calls.jsonl").read_text().strip())
    assert call["prompt_hash"] == digest
    manifest = json.loads((audit_dir / "manifest.json").read_text())
    assert manifest["slug"] == "deal"
    assert manifest["rulebook_version"] == "ruleshash"
    assert manifest["total_input_tokens"] == 1
