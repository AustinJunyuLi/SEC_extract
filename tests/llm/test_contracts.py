from __future__ import annotations

from pipeline.llm import contracts, extract


def _repair_loop_one():
    return {"turns": 1}


def _repair_loop_two():
    return {"turns": 2}


def test_repair_loop_contract_version_is_stable():
    a = contracts.repair_loop_contract_version()
    b = contracts.repair_loop_contract_version()

    assert a == b
    assert len(a) == 16
    assert all(char in "0123456789abcdef" for char in a)


def test_repair_loop_contract_version_changes_with_cap(monkeypatch):
    src = contracts._REPAIR_LOOP_CONTRACT_INPUTS
    baseline = contracts.repair_loop_contract_version()

    monkeypatch.setattr(contracts, "MAX_REPAIR_TURNS", 3)
    changed = contracts.repair_loop_contract_version()

    assert src["MAX_REPAIR_TURNS"] == 2
    assert baseline != changed


def test_repair_loop_contract_version_changes_with_repair_prompt(tmp_path, monkeypatch):
    repair_prompt = tmp_path / "repair.md"
    monkeypatch.setattr(contracts, "_REPAIR_PROMPT_PATH", repair_prompt)

    absent = contracts.repair_loop_contract_version()
    repair_prompt.write_text("Repair prompt v1")
    present = contracts.repair_loop_contract_version()
    repair_prompt.write_text("Repair prompt v2")
    changed = contracts.repair_loop_contract_version()

    assert absent != present
    assert present != changed


def test_repair_loop_contract_version_hashes_runner_source(monkeypatch):
    monkeypatch.setattr(extract, "run_repair_loop", _repair_loop_one, raising=False)
    one = contracts.repair_loop_contract_version()
    monkeypatch.setattr(extract, "run_repair_loop", _repair_loop_two, raising=False)
    two = contracts.repair_loop_contract_version()

    assert one != two
