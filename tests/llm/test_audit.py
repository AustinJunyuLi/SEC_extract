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
        "models": {"extract": "gpt-test", "adjudicate": "gpt-test"},
        "total_input_tokens": 1,
        "total_output_tokens": 2,
        "total_reasoning_tokens": 3,
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
