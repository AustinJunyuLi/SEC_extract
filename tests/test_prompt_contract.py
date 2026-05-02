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
DOC_CONTRACT_PATHS = [
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "CLAUDE.md",
    REPO_ROOT / "SKILL.md",
    *sorted((REPO_ROOT / "docs").rglob("*.md")),
]


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
    assert "page-numbered `pages`" in text
    assert "Do not fetch from SEC/EDGAR" in text
    assert "access local files, run arbitrary code" in text
    assert "No tools are available during initial extraction" in text
    assert "`check_row(row)`" not in text
    assert "`search_filing(query, page_range, max_hits)`" not in text
    assert "`get_pages(start_page, end_page)`" not in text
    assert "deal.bidder_registry` is schema-empty" in text
    assert "`rules/invariants.md` remains validator-facing only" in text
    assert "Return exactly one raw JSON object" in text
    assert "Do not include prose, markdown fences" in text
    assert "Always call " "`check_row`" not in text
    assert "After tool calls " "return" not in text
    assert "```" not in text
    assert "Do not emit pipeline-stamped\nfields" in text
    assert "Use `null` for unsupported optional facts" in text
    assert "Every emitted row MUST have `source_quote` and `source_page`" in text
    assert "Each individual quote string MUST be 1500 characters or shorter" in text
    assert "Use the\n  list form of `source_quote` / `source_page`" in text
    assert "A same-day `Bid` row does not replace the process-level non-announcement" in text
    assert "Emit `DropSilent` only for true post-NDA filing silence" in text
    assert "Advisor NDA rows are not skip rows" in text
    assert "Exact-count unnamed NDA placeholders are lifecycle handles" in text
    assert "label such as `Buyer Group`" in text
    assert "Atomize buyer-group `NDA`, `Bid`, `Drop`, `DropSilent`, and `Executed`" in text
    assert "joins an already-NDA-bound buyer group" in text
    assert "`ConsortiumCA` never substitutes for a same-bidder `NDA`" in text
    assert "never collapse to a single `Buyer Group` row" in text
    assert "Slash or relationship labels such as `CSC/Pamplona`" in text
    assert "Buyer-group constituents/count unsupported by embedded filing evidence" in text
    assert "bid_type` still ambiguous" in text
    assert "status\": \"blocked_by_open_rule\"" not in text
    assert "blocked_by_open_rule" not in text
    assert "§M3 (legal advisor NDA)" not in text
    for stale_phrase in ["Read " "tool", "Read these " "files", "sub" "agent"]:
        assert stale_phrase not in text


def test_repair_prompt_documents_single_obligation_tool_round():
    text = (REPO_ROOT / "prompts" / "repair.md").read_text()

    assert "one repair round" in text
    assert "Repair has access to all four tools" in text
    assert "`check_obligations(candidate_extraction)`" in text
    assert "## Previous complete extraction" in text
    assert "## Deterministic filing pages" in text
    assert "Call `check_obligations` at most once" in text
    assert "Do not call it on row subsets" in text
    assert "Call `check_row` on every revised row" in text
    assert "Repair turn 1 has no tools" not in text
    assert "Repair turn 2" not in text
    assert "Do not emit patches or partial output" in text


def test_live_repair_prompt_formats_without_unescaped_literal_braces():
    text = (REPO_ROOT / "prompts" / "repair.md").read_text()

    formatted = text.format(
        validator_report="{}",
        obligation_report="{}",
        conservation_report="{}",
        previous_extraction="{}",
        filing_pages="[]",
        affected_rows="[]",
        filing_snippets="[]",
    )

    assert "Previous complete extraction" in formatted


def test_value_bearing_bid_consideration_contract_is_explicit():
    prompt = (REPO_ROOT / "prompts" / "extract.md").read_text()
    bids = (REPO_ROOT / "rules" / "bids.md").read_text()
    schema = (REPO_ROOT / "rules" / "schema.md").read_text()

    assert "A `Bid` row with any stated value must never leave `consideration_components` null" in bids
    assert "Dollar-denominated per-share acquisition proposals default to `[\"cash\"]`" in bids
    assert "`deal.all_cash` describes the signed merger-agreement consideration" in bids
    assert "`deal.all_cash = true` iff EVERY bid event row" not in bids
    assert (
        "`consideration_components` — list[str] OR null. Required and non-empty "
        "on every `Bid` row with a stated value."
    ) in schema
    assert "A value-bearing `Bid` row must have `bid_value_unit` and a non-empty" in prompt
    assert "Every non-`Bid` row, including `Executed`, `Final Round`, `Drop`, and" in prompt
    assert "If an `Executed` quote restates the signed price" in prompt
    assert (
        "each bid row has `consideration_components` and `exclusivity_days` "
        "populated or explicitly null"
    ) not in prompt


def test_date_contract_covers_year_roughness_and_bare_sequence_words():
    dates = (REPO_ROOT / "rules" / "dates.md").read_text()
    prompt = (REPO_ROOT / "prompts" / "extract.md").read_text()

    assert "| `early <Year>` | `<Year>-02-15` |" in dates
    assert "| `late <Year>` | `<Year>-11-15` |" in dates
    assert "\"approximately/about/around N weeks later\" — anchor + 7*N days" in dates
    assert "bare sequencing words such as \"subsequently\"" in dates
    assert "Do not put bare sequencing words such as `subsequently`" in prompt


def test_data_room_access_is_not_confidentiality_agreement_by_itself():
    prompt = (REPO_ROOT / "prompts" / "extract.md").read_text()
    events = (REPO_ROOT / "rules" / "events.md").read_text()

    assert "Data-room access alone is not a confidentiality agreement" in events
    assert "Do not emit `NDA` solely because a bidder received data-room access" in prompt


def test_prompt_rewrite_keeps_raw_extractor_example_free_of_pipeline_fields():
    schema = (REPO_ROOT / "rules" / "schema.md").read_text()

    assert "## Raw extractor schema example" in schema
    assert "the extractor must not emit those fields" in schema
    example = schema.split("## Raw extractor schema example", 1)[1]
    example_json = example.split("```json", 1)[1].split("```", 1)[0]
    assert '"rulebook_version"' not in example_json
    assert '"last_run"' not in example_json
    assert '"last_run_id"' not in example_json


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


def test_documented_reconcile_command_matches_current_cli():
    offenders: list[str] = []
    for path in DOC_CONTRACT_PATHS:
        text = path.read_text()
        if "pipeline.reconcile --scope reference --strict" in text:
            offenders.append(str(path.relative_to(REPO_ROOT)))
        if "pipeline.reconcile --scope all --strict" in text:
            offenders.append(str(path.relative_to(REPO_ROOT)))

    assert offenders == []


def test_live_contract_files_do_not_carry_stale_rule_prose():
    banned_substrings = [
        "Final-round fixtures to mirror",
        "Conversion fixtures",
        "Reference deals affected",
        "Longview and the Buyer Group\"`",
        "Longview and the Buyer Group\"",
        "Inf suffix",
        "which `Inf` suffix",
        "Ralph",
        "subagent",
        "sub-agent",
        "strict " "Extractor + tools",
        "Every extractor call uses **strict `text.format=json_schema`** with "
        "the hardened `SCHEMA_R1`, plus three native function-calling tools",
        "The model has three native function-calling " "tools while drafting",
        "Always call " "`check_row`",
        "call `check_row` on every event " "row",
        "first-pass " "tool use",
        "prompt_then_" "filing_tools",
    ]
    banned_legacy_labels = [
        "Final Round Inf",
        "DropBelowInf",
        "DropAtInf",
    ]
    offenders: list[str] = []
    for path in LIVE_CONTRACT_PATHS:
        text = path.read_text()
        for phrase in banned_substrings + banned_legacy_labels:
            if phrase in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {phrase}")

    assert offenders == []


def test_live_contract_files_do_not_describe_old_staged_repair():
    banned = [
        "Repair turn 1",
        "Repair turn 2",
        "prompt_then_targeted_tools",
        "2 repair turns",
        "repair_loop_exhausted",
    ]
    offenders: list[str] = []
    for path in LIVE_CONTRACT_PATHS:
        text = path.read_text()
        for phrase in banned:
            if phrase in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {phrase}")

    assert offenders == []


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
