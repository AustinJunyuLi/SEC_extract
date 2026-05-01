import json

import pytest

from pipeline.llm.audit import AuditWriter, TokenUsage, audit_run_dir, prompt_hash
from pipeline.llm.client import CompletionResult


def test_prompt_hash_is_stable_sha256():
    assert prompt_hash("system", "user") == prompt_hash("system", "user")
    assert len(prompt_hash("system", "user")) == 64


def test_token_usage_tracks_without_cap():
    usage = TokenUsage()
    usage.consume(CompletionResult(text="", model="m", input_tokens=3, output_tokens=4, reasoning_tokens=2))

    assert usage.used == 9

    usage.consume(CompletionResult(text="", model="m", input_tokens=200_000))

    assert usage.used == 200_009


def _writer(tmp_path, slug="deal", run_id="run-1"):
    return AuditWriter(audit_run_dir(tmp_path, slug, run_id), slug=slug, run_id=run_id)


def test_audit_writer_requires_explicit_run_directory(tmp_path):
    with pytest.raises(ValueError, match=r"runs/\{run_id\}"):
        AuditWriter(tmp_path / "deal", slug="deal", run_id="run-1")


def test_audit_writer_writes_prompt_call_raw_response_validation_manifest_and_latest(tmp_path):
    writer = _writer(tmp_path)
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
        extractor_contract_version="contracthash",
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
        "extractor_contract_version": "contracthash",
        "tools_contract_version": "toolshash",
        "repair_loop_contract_version": "repairhash",
        "models": {"extract": "gpt-test", "adjudicate": "gpt-test"},
        "total_input_tokens": 1,
        "total_output_tokens": 2,
        "total_reasoning_tokens": 3,
        "repair_turns_used": 0,
        "repair_loop_outcome": "clean",
        "tool_calls_count": 0,
        "outcome": "passed_clean",
        "cache_eligible": True,
    })
    writer.write_validation({
        "final_status": "passed_clean",
        "flag_count": 0,
        "row_flag_count": 0,
        "deal_flag_count": 0,
        "hard_count": 0,
        "soft_count": 0,
        "info_count": 0,
    })
    writer.write_final_output({"deal": {}, "events": []})
    writer.write_latest(outcome="passed_clean", cache_eligible=True)

    audit_dir = tmp_path / "deal" / "runs" / "run-1"
    prompt_text = (audit_dir / "prompts" / "extractor.txt").read_text()
    assert "=== SYSTEM ===\nsystem text" in prompt_text
    assert "=== USER ===\nuser text" in prompt_text
    raw_response = json.loads((audit_dir / "raw_response.json").read_text())
    assert raw_response["schema_version"] == "raw_response_v2"
    assert raw_response["run_id"] == "run-1"
    assert raw_response["parsed_json"] == {"deal": {}, "events": []}
    assert raw_response["extractor_contract_version"] == "contracthash"
    call = json.loads((audit_dir / "calls.jsonl").read_text().strip())
    assert call["prompt_hash"] == digest
    manifest = json.loads((audit_dir / "manifest.json").read_text())
    assert manifest["slug"] == "deal"
    assert manifest["run_id"] == "run-1"
    assert manifest["schema_version"] == "audit_run_v2"
    assert manifest["rulebook_version"] == "ruleshash"
    assert manifest["tools_contract_version"] == "toolshash"
    assert manifest["repair_loop_contract_version"] == "repairhash"
    assert manifest["repair_turns_used"] == 0
    assert manifest["repair_loop_outcome"] == "clean"
    assert manifest["tool_calls_count"] == 0
    assert "json_" + "schema_used" not in manifest
    assert manifest["total_input_tokens"] == 1
    validation = json.loads((audit_dir / "validation.json").read_text())
    assert validation["schema_version"] == "validation_v1"
    final_output = json.loads((audit_dir / "final_output.json").read_text())
    assert final_output == {"deal": {}, "events": []}
    latest = json.loads((tmp_path / "deal" / "latest.json").read_text())
    assert latest["schema_version"] == "audit_v2"
    assert latest["run_id"] == "run-1"
    assert latest["manifest_path"] == "runs/run-1/manifest.json"
    assert latest["raw_response_path"] == "runs/run-1/raw_response.json"


def test_audit_writer_records_tool_calls(tmp_path):
    writer = AuditWriter(tmp_path / "deal" / "runs" / "run-1", slug="deal", run_id="run-1")

    writer.write_tool_call({
        "turn": 1,
        "call_id": "c1",
        "name": "check_row",
        "args": {"row": {"a": 1}},
        "result": {"ok": True, "violations": []},
        "latency_ms": 12.4,
    })

    lines = (tmp_path / "deal" / "runs" / "run-1" / "tool_calls.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["slug"] == "deal"
    assert record["run_id"] == "run-1"
    assert record["name"] == "check_row"
    assert record["result_truncated"] is False


def test_audit_writer_truncates_large_tool_results(tmp_path):
    writer = AuditWriter(tmp_path / "deal" / "runs" / "run-1", slug="deal", run_id="run-1")

    writer.write_tool_call({
        "turn": 1,
        "call_id": "c1",
        "name": "get_pages",
        "args": {"start_page": 1, "end_page": 1},
        "result": {"pages": [{"page": 1, "text": "x" * 9000}]},
        "latency_ms": 12.4,
    })

    record = json.loads((tmp_path / "deal" / "runs" / "run-1" / "tool_calls.jsonl").read_text())
    assert record["result_truncated"] is True
    assert len(record["result"]) == 8000


def test_audit_writer_records_obligations_and_repair_response(tmp_path):
    writer = AuditWriter(tmp_path / "deal" / "runs" / "run-1", slug="deal", run_id="run-1")

    writer.write_obligations({
        "before_repair": {"hard_unmet_count": 1},
        "after_repair": {"hard_unmet_count": 0},
    })
    writer.write_repair_response({"deal": {}, "events": [], "obligation_assertions": []})

    obligations = json.loads((writer.root / "obligations.json").read_text())
    repair_response = json.loads((writer.root / "repair_response.json").read_text())
    assert obligations["before_repair"]["hard_unmet_count"] == 1
    assert repair_response["obligation_assertions"] == []


def test_audit_writer_records_repair_turns(tmp_path):
    writer = AuditWriter(tmp_path / "deal" / "runs" / "run-1", slug="deal", run_id="run-1")

    writer.write_repair_turn({
        "turn": 1,
        "validator_report_summary": {"hard_count": 3, "soft_count": 2, "info_count": 0},
        "hard_flags_before": 3,
        "hard_flags_after": 0,
        "latency_ms": 18000.5,
    })

    lines = (tmp_path / "deal" / "runs" / "run-1" / "repair_turns.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["turn"] == 1
    assert record["hard_flags_before"] == 3


def test_manifest_includes_new_contract_fields(tmp_path):
    writer = AuditWriter(tmp_path / "deal" / "runs" / "run-1", slug="deal", run_id="run-1")

    writer.write_manifest(
        action="extract",
        rulebook_version="rb1",
        extractor_contract_version="ec1",
        tools_contract_version="tc1",
        repair_loop_contract_version="rlc1",
        obligation_contract_version="oc1",
        repair_turns_used=1,
        repair_loop_outcome="fixed",
        tool_calls_count=12,
        outcome="passed_clean",
        cache_eligible=True,
    )

    manifest = json.loads((tmp_path / "deal" / "runs" / "run-1" / "manifest.json").read_text())
    assert manifest["tools_contract_version"] == "tc1"
    assert manifest["repair_loop_contract_version"] == "rlc1"
    assert manifest["obligation_contract_version"] == "oc1"
    assert manifest["repair_turns_used"] == 1
    assert manifest["repair_loop_outcome"] == "fixed"
    assert manifest["tool_calls_count"] == 12
    assert "json_" + "schema_used" not in manifest


def test_two_audit_runs_are_immutable_and_latest_points_to_second(tmp_path):
    first = _writer(tmp_path, run_id="run-1")
    second = _writer(tmp_path, run_id="run-2")
    result = CompletionResult(text="{}", model="gpt-test")

    first.write_prompt(phase="extractor", system="first", user="user")
    first.write_raw_response(
        result=result,
        parsed_json={"deal": {"TargetName": "first"}, "events": []},
        rulebook_version="rules",
        extractor_contract_version="contract",
    )
    first.write_manifest({"outcome": "passed_clean", "cache_eligible": True})
    first.write_validation({"final_status": "passed_clean", "flag_count": 0})
    first.write_final_output({"deal": {"TargetName": "first"}, "events": []})
    first.write_latest(outcome="passed_clean", cache_eligible=True)

    second.write_prompt(phase="extractor", system="second", user="user")
    second.write_raw_response(
        result=result,
        parsed_json={"deal": {"TargetName": "second"}, "events": []},
        rulebook_version="rules",
        extractor_contract_version="contract",
    )
    second.write_manifest({"outcome": "passed_clean", "cache_eligible": True})
    second.write_validation({"final_status": "passed_clean", "flag_count": 0})
    second.write_final_output({"deal": {"TargetName": "second"}, "events": []})
    second.write_latest(outcome="passed_clean", cache_eligible=True)

    first_raw = json.loads((tmp_path / "deal" / "runs" / "run-1" / "raw_response.json").read_text())
    second_raw = json.loads((tmp_path / "deal" / "runs" / "run-2" / "raw_response.json").read_text())
    latest = json.loads((tmp_path / "deal" / "latest.json").read_text())
    assert first_raw["parsed_json"]["deal"]["TargetName"] == "first"
    assert second_raw["parsed_json"]["deal"]["TargetName"] == "second"
    assert latest["run_id"] == "run-2"
