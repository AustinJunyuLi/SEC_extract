from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_extractor_messages_embed_sdk_context():
    extract = pytest.importorskip("pipeline.llm.extract")

    system, user = extract.build_messages("medivation")

    assert "prompts/extract.md" in system
    for rule_name in [
        "rules/schema.md",
        "rules/events.md",
        "rules/bidders.md",
        "rules/bids.md",
        "rules/dates.md",
    ]:
        assert rule_name in system

    assert "`rules/invariants.md` remains validator-facing only" in system
    assert "RULE FILE: rules/invariants.md" not in system
    assert "slug" in user
    assert "medivation" in user
    assert "manifest" in user
    assert "pages" in user
    assert '"number"' in user
    assert '"content"' in user

    combined = "\n".join([system, user])
    for stale_phrase in ["Read " "tool", "Read these " "files", "sub" "agent"]:
        assert stale_phrase not in combined


def test_extractor_prompt_contract_describes_embedded_filing_text():
    text = (REPO_ROOT / "prompts" / "extract.md").read_text()

    assert "SDK-call role" in text
    assert "page-numbered filing text" in text
    assert "do not fetch from SEC/EDGAR" in text
    assert "`rules/invariants.md` remains validator-facing only" in text
    for stale_phrase in ["Read " "tool", "Read these " "files", "sub" "agent"]:
        assert stale_phrase not in text


def test_dependency_manifest_pins_current_project_dependencies():
    lines = [
        line.split("#", 1)[0].strip()
        for line in (REPO_ROOT / "requirements.txt").read_text().splitlines()
    ]
    for prefix in [
        "sec2md==",
        "openpyxl==",
        "pytest==",
        "matplotlib==",
        "numpy==",
        "openai==",
        "httpx==",
        "python-dotenv==",
    ]:
        assert any(line.startswith(prefix) for line in lines), (
            f"requirements.txt must pin {prefix!r} with ==; "
            f"current lines: {[line for line in lines if line]!r}"
        )
