from pathlib import Path

import pipeline


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_extractor_prompt_contract_uses_local_filing_artifacts_only():
    text = (REPO_ROOT / "prompts" / "extract.md").read_text()

    assert "`deal.filing_url`" not in text
    assert "or fetch it via the provided tool" not in text
    assert "Use local filing artifacts only" in text
    assert "Do not fetch from SEC/EDGAR" in text
    assert "data/filings/{deal.slug}/pages.json" in text


def test_invariants_are_validator_facing_not_extractor_read_set():
    prompt_text = (REPO_ROOT / "prompts" / "extract.md").read_text()
    skill_text = (REPO_ROOT / "SKILL.md").read_text()
    built_prompt = pipeline.build_extractor_prompt("medivation")

    assert "`rules/invariants.md` is validator-facing only" in prompt_text
    assert "**Does not read:** `rules/invariants.md`" in skill_text
    assert "rules/invariants.md" not in built_prompt
    assert "rules/*.md" not in built_prompt

    for rule_name in [
        "schema.md",
        "events.md",
        "bidders.md",
        "bids.md",
        "dates.md",
    ]:
        assert str(pipeline.RULES_DIR / rule_name) in built_prompt

    assert str(pipeline.DATA_DIR / "medivation" / "pages.json") in built_prompt
    assert str(pipeline.DATA_DIR / "medivation" / "manifest.json") in built_prompt


def test_dependency_manifest_pins_current_project_dependencies():
    """Assert each dependency has a pinned version, not a specific pin value.

    The previous form hard-coded exact versions; any dependency bump required
    a test edit. This form catches "pin is missing" and "pin was replaced by
    a floating >=" while surviving routine version bumps.
    """
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
    ]:
        assert any(line.startswith(prefix) for line in lines), (
            f"requirements.txt must pin {prefix!r} with ==; "
            f"current lines: {[line for line in lines if line]!r}"
        )
