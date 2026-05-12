from __future__ import annotations

from pathlib import Path


CONTRACT_FILES = (
    Path("AGENTS.md"),
    Path("SKILL.md"),
)


def test_live_contracts_define_agent_verification_authority():
    required_phrases = (
        "agent filing-grounded verification",
        "quality_reports/reference_verification/{slug}.md",
        "must not mark a deal verified solely because the model output passes schema validation",
    )
    for path in CONTRACT_FILES:
        text = " ".join(path.read_text().split())
        missing = [phrase for phrase in required_phrases if phrase not in text]
        assert not missing, f"{path} missing {missing}"
