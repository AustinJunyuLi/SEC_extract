from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
LIVE_CONTRACT_PATHS = [
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "CLAUDE.md",
    REPO_ROOT / "SKILL.md",
    REPO_ROOT / "docs" / "linkflow-extraction-guide.md",
    REPO_ROOT / "prompts" / "extract.md",
    *sorted((REPO_ROOT / "rules").glob("*.md")),
]


def test_extractor_messages_embed_claim_context():
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
    assert "actor_claims" in system
    assert "bid_claims" in system
    assert "Provider claims should not emit `BidderID`" in system
    assert "rules/invariants.md" not in system
    assert "medivation" in user
    assert '"pages"' in user
    assert '"citation_units"' in user
    assert '"content"' in user


def test_prompt_is_claim_only_and_tool_free():
    text = (REPO_ROOT / "prompts" / "extract.md").read_text()

    assert "Return exactly one JSON object" in text
    assert '"actor_claims": []' in text
    assert '"event_claims": []' in text
    assert '"bid_claims": []' in text
    assert '"participation_count_claims": []' in text
    assert '"actor_relation_claims": []' in text
    assert "No tools are available during" in text
    assert "extraction." in text
    assert "Never emit `deal`, `events`, `BidderID`" in text
    assert "`evidence_refs`" in text
    assert "`citation_unit_id`" in text
    assert "not paraphrase quotes" in text
    assert "must exactly match one embedded `citation_units[].id`" in text
    assert "exact contiguous substring of that citation unit's" in text
    assert "source-addressed" in text
    assert "Never emit provider-level `quote_text` or `quote_texts`" in text
    assert "Do not delete words" in text
    assert "from the middle of" in text
    assert "join non-adjacent fragments into one quote" in text
    assert "smooth page breaks" in text
    assert "include SEC/typesetting metadata" in text
    assert "Do not emit an `actor_claim` merely to identify the target company" in text
    assert "Target" in text
    assert "identity comes from the filing manifest" in text
    assert "`check_row`" not in text
    assert "`search_filing`" not in text
    assert "`get_pages`" not in text


def test_rules_document_graph_boundary_and_forbidden_provider_fields():
    schema = (REPO_ROOT / "rules" / "schema.md").read_text()
    invariants = (REPO_ROOT / "rules" / "invariants.md").read_text()

    assert "The provider emits claims only" in schema
    assert "Top-level `deal` / `events` row JSON is retired" in schema
    assert "Provider-owned fields are forbidden" in schema
    assert "`T`, `bI`, `bF`" in schema
    assert "Old row-event invariants are retained in git history only" in invariants
    assert "projections are not emitted while blocking review flags remain" in invariants


def test_consortium_doctrine_preserves_group_bidder_units():
    prompt = (REPO_ROOT / "prompts" / "extract.md").read_text()
    bidders = (REPO_ROOT / "rules" / "bidders.md").read_text()
    bids = (REPO_ROOT / "rules" / "bids.md").read_text()

    combined = "\n".join([prompt, bidders, bids])
    assert "Preserve the filing's bidding unit" in combined
    assert "`CSC/Pamplona` is one group actor" in combined
    assert "`Buyer Group` is one group actor" in combined
    assert "Longview" in combined
    assert "Member relations are composition facts" in combined
    assert "member actors are not projected unless" in combined.lower()


def test_date_contract_keeps_dates_provider_factual_only():
    dates = (REPO_ROOT / "rules" / "dates.md").read_text()

    assert "Use ISO `YYYY-MM-DD` only when the filing supports a precise date" in dates
    assert "Use null when the filing gives only vague sequencing" in dates
    assert "`joins_group`, `exits_group`" in dates
    assert "Python owns ordering, process cycles" in dates


def test_live_contract_files_do_not_describe_old_live_row_pipeline():
    banned = [
        "model emits final {deal, events}",
        "prepare_for_validate()",
        "finalize_prepared()",
        "obligation_gated_single_repair",
        "prompt_then_filing_tools",
        "Every full extraction body uses strict `text.format=json_schema` with the hardened `SCHEMA_R1`",
        "The scoped Adjudicator",
        "one tool-enabled repair round",
    ]
    offenders: list[str] = []
    for path in LIVE_CONTRACT_PATHS:
        text = path.read_text()
        for phrase in banned:
            if phrase in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {phrase}")
    assert offenders == []


def test_extractor_contract_version_changes_when_prompt_changes(tmp_path, monkeypatch):
    extract = pytest.importorskip("pipeline.llm.extract")

    prompts = tmp_path / "prompts"
    prompts.mkdir()
    prompt_path = prompts / "extract.md"
    prompt_path.write_text("prompt version one")
    monkeypatch.setattr(extract.core, "REPO_ROOT", tmp_path)

    first = extract.extractor_contract_version()
    prompt_path.write_text("prompt version two")
    second = extract.extractor_contract_version()

    assert first != second


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
        "duckdb==",
    ]:
        assert any(line.startswith(prefix) for line in lines)
