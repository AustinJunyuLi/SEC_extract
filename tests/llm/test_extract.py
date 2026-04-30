import asyncio
import json

from pipeline.llm import extract
from pipeline.llm.audit import AuditWriter, TokenUsage
from pipeline.llm.client import CompletionResult


def _audit_writer(tmp_path, slug="synthetic", run_id="run-extract"):
    return AuditWriter(tmp_path / "output" / "audit" / slug / "runs" / run_id, slug=slug, run_id=run_id)


def background_section_pages(section_text="embedded filing page text"):
    body = (
        "The following chronology summarizes the key meetings and events. "
        + (section_text + " ") * 120
    )
    continuation = (
        "Additional background chronology before the next section. "
        + ("continued filing page text " * 80)
    )
    return [
        {
            "number": 4,
            "content": "Table of Contents | Background of the Merger | 23 | Reasons for the Merger | 37 |",
        },
        {
            "number": 17,
            "content": "See the section entitled Background of the Merger for details.",
        },
        {
            "number": 22,
            "content": f"Introductory material.\n\n**Background of the Merger**\n\n{body}",
        },
        {
            "number": 23,
            "content": f"{continuation}\n\n**Reasons for the Merger**\n\nNot part of background.",
        },
    ]


def test_build_messages_embeds_prompt_rules_manifest_and_page_text(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    prompts = env.tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "extract.md").write_text("EXTRACT PROMPT")
    for name in extract.EXTRACTOR_RULE_FILES:
        (env.rules / name).write_text(f"RULE {name}")
    env.seed_filing(
        "synthetic",
        pages=background_section_pages(),
        manifest={"slug": "synthetic", "form_type": "DEFM14A"},
    )
    monkeypatch.setattr(extract.core, "PROMPTS_DIR", prompts)

    system, user = extract.build_messages("synthetic")

    assert "EXTRACT PROMPT" in system
    for name in extract.EXTRACTOR_RULE_FILES:
        assert f"RULE {name}" in system
    payload = json.loads(user)
    assert payload["slug"] == "synthetic"
    assert payload["manifest"]["form_type"] == "DEFM14A"
    assert payload["section"] == {
        "name": "Background",
        "start_page": 22,
        "end_page": 23,
        "source": "verbatim slices from the source filing pages",
    }
    assert [page["number"] for page in payload["pages"]] == [22, 23]
    assert payload["pages"][0]["content"].startswith("Background of the Merger")
    assert "embedded filing page text" in payload["pages"][0]["content"]
    assert "Not part of background" not in payload["pages"][-1]["content"]
    assert "data/filings/synthetic/pages.json" not in user


def test_build_messages_ignores_toc_and_cross_reference_background_hits(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    prompts = env.tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "extract.md").write_text("EXTRACT PROMPT")
    for name in extract.EXTRACTOR_RULE_FILES:
        (env.rules / name).write_text(f"RULE {name}")
    env.seed_filing("synthetic", pages=background_section_pages("actual background sentence"))
    monkeypatch.setattr(extract.core, "PROMPTS_DIR", prompts)

    _, user = extract.build_messages("synthetic")

    payload = json.loads(user)
    assert payload["section"]["start_page"] == 22
    combined_pages = "\n".join(page["content"] for page in payload["pages"])
    assert "Table of Contents | Background of the Merger" not in combined_pages
    assert "See the section entitled Background of the Merger" not in combined_pages
    assert "actual background sentence" in combined_pages


class StubClient:
    def __init__(self):
        self.calls = []

    async def complete(self, **kwargs):
        payload = {
            "deal": {
                "TargetName": "Synthetic Target",
                "Acquirer": "Synthetic Buyer",
                "DateAnnounced": "2026-04-24",
                "DateEffective": None,
                "auction": False,
                "all_cash": True,
                "target_legal_counsel": None,
                "acquirer_legal_counsel": None,
                "bidder_registry": {},
                "deal_flags": [],
            },
            "events": [],
        }
        self.calls.append(kwargs)
        return CompletionResult(
            text=json.dumps(payload),
            model=kwargs["model"],
            input_tokens=10,
            output_tokens=5,
        )


class FailingClient:
    async def complete(self, **kwargs):
        error = RuntimeError("provider exhausted")
        error.attempts = 3
        raise error


def test_extract_deal_writes_audit_and_tracks_token_usage(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    prompts = env.tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "extract.md").write_text("PROMPT")
    for name in extract.EXTRACTOR_RULE_FILES:
        (env.rules / name).write_text(f"RULE {name}")
    env.seed_filing("synthetic", pages=background_section_pages("page text"))
    monkeypatch.setattr(extract.core, "PROMPTS_DIR", prompts)

    audit = _audit_writer(env.tmp_path)
    usage = TokenUsage()
    client = StubClient()

    result = asyncio.run(
        extract.extract_deal(
            "synthetic",
            llm_client=client,
            extract_model="test-model",
            audit=audit,
            token_usage=usage,
            rulebook_version="rules-v1",
            max_output_tokens=123,
        )
    )

    assert result.raw_extraction["deal"]["TargetName"] == "Synthetic Target"
    assert "slug" not in result.raw_extraction["deal"]
    assert usage.used == 15
    assert client.calls[0]["model"] == "test-model"
    assert client.calls[0]["max_output_tokens"] == 123
    assert "tools" not in client.calls[0] or client.calls[0]["tools"] is None
    assert "tool_choice" not in client.calls[0] or client.calls[0]["tool_choice"] is None
    assert client.calls[0]["stream"] is True
    assert (audit.root / "prompts" / "extractor.txt").read_text().startswith("=== SYSTEM ===\nPROMPT")
    assert json.loads((audit.root / "raw_response.json").read_text())["parsed_json"]["deal"]["TargetName"] == "Synthetic Target"
    call_entries = (audit.root / "calls.jsonl").read_text().splitlines()
    assert len(call_entries) == 1
    assert json.loads(call_entries[0])["phase"] == "extract"


def test_repair_second_turn_runs_targeted_tools_after_prompt_only_repair_fails(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    prompts = env.tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "extract.md").write_text("PROMPT")
    (prompts / "repair.md").write_text(
        "REPORT {validator_report}\nROWS {affected_rows}\nSNIPPETS {filing_snippets}"
    )
    for name in extract.EXTRACTOR_RULE_FILES:
        (env.rules / name).write_text(f"RULE {name}")
    env.seed_filing("synthetic", pages=background_section_pages("page text"))
    monkeypatch.setattr(extract.core, "PROMPTS_DIR", prompts)

    invalid_validation = extract.core.ValidatorResult(
        row_flags=[
            {
                "row_index": 0,
                "code": "source_quote_not_in_page",
                "severity": "hard",
                "reason": "bad quote",
            }
        ],
        deal_flags=[],
    )
    fixed_validation = extract.core.ValidatorResult(row_flags=[], deal_flags=[])
    validations = iter([invalid_validation, fixed_validation])

    def fake_prepare(slug, raw, filing):
        return raw, filing, []

    def fake_validate(prepared, filing):
        return next(validations)

    monkeypatch.setattr(extract.core, "prepare_for_validate", fake_prepare)
    monkeypatch.setattr(extract.core, "validate", fake_validate)

    final_payload = {
        "deal": {
            "TargetName": "Synthetic Target",
            "Acquirer": "Synthetic Buyer",
            "DateAnnounced": "2026-04-24",
            "DateEffective": None,
            "auction": False,
            "all_cash": True,
            "target_legal_counsel": None,
            "acquirer_legal_counsel": None,
            "bidder_registry": {},
            "deal_flags": [],
        },
        "events": [],
    }
    tool_call = {
        "type": "function_call",
        "name": "search_filing",
        "call_id": "call-search",
        "arguments": json.dumps({"query": "page text", "page_range": None, "max_hits": 5}),
    }

    class RepairClient:
        def __init__(self):
            self.calls = []

        async def complete(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                return CompletionResult(
                    text=json.dumps(final_payload),
                    model=kwargs["model"],
                    input_tokens=2,
                    output_tokens=3,
                )
            if len(self.calls) == 2:
                return CompletionResult(
                    text="",
                    model=kwargs["model"],
                    tool_calls=[tool_call],
                    output_items=[tool_call],
                    input_tokens=5,
                    output_tokens=7,
                )
            return CompletionResult(
                text=json.dumps(final_payload),
                model=kwargs["model"],
                input_tokens=11,
                output_tokens=13,
            )

    audit = _audit_writer(env.tmp_path)
    usage = TokenUsage()
    client = RepairClient()
    filing = extract.core.load_filing("synthetic")

    revised, validation, promotion_log, outcome, turns = asyncio.run(
        extract.run_repair_loop(
            slug="synthetic",
            initial_draft=final_payload,
            filing=filing,
            validation=invalid_validation,
            llm_client=client,
            extract_model="test-model",
            audit=audit,
            token_usage=usage,
            reasoning_effort="high",
        )
    )

    assert revised == final_payload
    assert validation is fixed_validation
    assert promotion_log == []
    assert outcome == "fixed"
    assert turns == 2
    assert "tools" not in client.calls[0] or client.calls[0]["tools"] is None
    repair_2_tools = {tool["name"] for tool in client.calls[1]["tools"]}
    assert repair_2_tools == {"check_row", "search_filing", "get_pages"}
    assert client.calls[1]["tool_choice"] == "auto"
    repair_turns = [
        json.loads(line)
        for line in (audit.root / "repair_turns.jsonl").read_text().splitlines()
    ]
    assert [row["tool_mode"] for row in repair_turns] == ["none", "targeted_repair_tools"]
    assert repair_turns[-1]["tool_calls_count"] == 1


def test_repair_records_failed_turn_before_reraising(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    prompts = env.tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "extract.md").write_text("PROMPT")
    (prompts / "repair.md").write_text(
        "REPORT {validator_report}\nROWS {affected_rows}\nSNIPPETS {filing_snippets}"
    )
    for name in extract.EXTRACTOR_RULE_FILES:
        (env.rules / name).write_text(f"RULE {name}")
    env.seed_filing("synthetic", pages=background_section_pages("page text"))
    monkeypatch.setattr(extract.core, "PROMPTS_DIR", prompts)

    validation = extract.core.ValidatorResult(
        row_flags=[{"row_index": 0, "code": "bad", "severity": "hard", "reason": "bad"}],
        deal_flags=[],
    )

    class FailingRepairClient:
        async def complete(self, **kwargs):
            raise RuntimeError("repair provider failed")

    audit = _audit_writer(env.tmp_path)
    filing = extract.core.load_filing("synthetic")

    try:
        asyncio.run(
            extract.run_repair_loop(
                slug="synthetic",
                initial_draft={"deal": {}, "events": []},
                filing=filing,
                validation=validation,
                llm_client=FailingRepairClient(),
                extract_model="test-model",
                audit=audit,
                token_usage=TokenUsage(),
            )
        )
    except RuntimeError as exc:
        assert "repair provider failed" in str(exc)
    else:
        raise AssertionError("run_repair_loop should re-raise repair failures")

    repair_record = json.loads((audit.root / "repair_turns.jsonl").read_text().strip())
    assert repair_record["turn"] == 1
    assert repair_record["tool_mode"] == "none"
    assert repair_record["outcome"] == "failed"
    assert repair_record["error"]["type"] == "RuntimeError"

def test_extract_deal_records_failed_call_attempts(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    prompts = env.tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "extract.md").write_text("PROMPT")
    for name in extract.EXTRACTOR_RULE_FILES:
        (env.rules / name).write_text(f"RULE {name}")
    env.seed_filing("synthetic", pages=background_section_pages("page text"))
    monkeypatch.setattr(extract.core, "PROMPTS_DIR", prompts)

    audit = _audit_writer(env.tmp_path)
    usage = TokenUsage()

    try:
        asyncio.run(
            extract.extract_deal(
                "synthetic",
                llm_client=FailingClient(),
                extract_model="test-model",
                audit=audit,
                token_usage=usage,
                rulebook_version="rules-v1",
            )
        )
    except RuntimeError:
        pass

    call_entry = json.loads((audit.root / "calls.jsonl").read_text().strip())
    assert call_entry["outcome"] == "failed"
    assert call_entry["attempts"] == 3
    assert usage.used == 0
