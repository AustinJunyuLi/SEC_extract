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
    assert payload["citation_units"]
    assert {
        "unit_id",
        "page_number",
        "paragraph_index",
        "text",
    } <= set(payload["citation_units"][0])
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


def test_build_messages_adds_paragraph_local_citation_units(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    prompts = env.tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "extract.md").write_text("EXTRACT PROMPT")
    for name in extract.EXTRACTOR_RULE_FILES:
        (env.rules / name).write_text(f"RULE {name}")
    env.seed_filing(
        "synthetic",
        pages=background_section_pages(
            "First exact receipt paragraph.\n\nTable of Contents\n\nSecond exact receipt paragraph."
        ),
    )
    monkeypatch.setattr(extract.core, "PROMPTS_DIR", prompts)

    _, user = extract.build_messages("synthetic")
    payload = json.loads(user)

    texts = [unit["text"] for unit in payload["citation_units"]]
    assert any("First exact receipt paragraph" in text for text in texts)
    assert any("Second exact receipt paragraph" in text for text in texts)
    assert "Table of Contents" not in texts


class StubClient:
    def __init__(self):
        self.calls = []

    async def complete(self, **kwargs):
        payload = _valid_claim_payload()
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


def _raw_deal():
    return {
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
    }


def _valid_claim_payload():
    return {
        "actor_claims": [
            {
                "claim_type": "actor",
                "coverage_obligation_id": "obl_actor_1",
                "actor_label": "CSC/Pamplona",
                "actor_kind": "group",
                "observability": "named",
                "confidence": "high",
                "quote_text": "CSC and Pamplona, who together we refer to as CSC/Pamplona",
                "quote_texts": None,
            }
        ],
        "event_claims": [],
        "bid_claims": [],
        "participation_count_claims": [],
        "actor_relation_claims": [],
    }


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

    assert result.raw_extraction["actor_claims"][0]["actor_label"] == "CSC/Pamplona"
    assert "deal" not in result.raw_extraction
    assert usage.used == 15
    assert client.calls[0]["model"] == "test-model"
    assert client.calls[0]["max_output_tokens"] == 123
    assert "tools" not in client.calls[0] or client.calls[0]["tools"] is None
    assert "tool_choice" not in client.calls[0] or client.calls[0]["tool_choice"] is None
    assert client.calls[0]["stream"] is True
    assert (audit.root / "prompts" / "extractor.txt").read_text().startswith("=== SYSTEM ===\nPROMPT")
    assert json.loads((audit.root / "raw_response.json").read_text())["parsed_json"]["actor_claims"][0]["actor_label"] == "CSC/Pamplona"
    call_entries = (audit.root / "calls.jsonl").read_text().splitlines()
    assert len(call_entries) == 1
    assert json.loads(call_entries[0])["phase"] == "extract"


def test_repair_runs_one_tool_enabled_turn_with_all_tools(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    prompts = env.tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "extract.md").write_text("PROMPT")
    (prompts / "repair.md").write_text(
        "REPORT {validator_report}\nOBLIGATIONS {obligation_report}\n"
        "CONSERVATION {conservation_report}\nPREVIOUS {previous_extraction}\n"
        "PAGES {filing_pages}"
    )
    for name in extract.EXTRACTOR_RULE_FILES:
        (env.rules / name).write_text(f"RULE {name}")
    env.seed_filing("synthetic", pages=background_section_pages("page text"))
    monkeypatch.setattr(extract.core, "PROMPTS_DIR", prompts)

    hard_validation = extract.core.ValidatorResult(
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

    def fake_prepare(slug, raw, filing):
        return raw, filing, []

    def fake_validate(prepared, filing):
        return fixed_validation

    monkeypatch.setattr(extract.core, "prepare_for_validate", fake_prepare)
    monkeypatch.setattr(extract.core, "validate", fake_validate)
    monkeypatch.setattr(
        extract.obligations,
        "check_obligations",
        lambda prepared, filing: extract.obligations.ObligationResult([], []),
    )

    final_payload = _valid_claim_payload()

    class RepairClient:
        def __init__(self):
            self.calls = []

        async def complete(self, **kwargs):
            self.calls.append(kwargs)
            return CompletionResult(
                text=json.dumps({**final_payload, "obligation_assertions": []}),
                model=kwargs["model"],
                input_tokens=2,
                output_tokens=3,
            )

    audit = _audit_writer(env.tmp_path)
    usage = TokenUsage()
    client = RepairClient()
    filing = extract.core.load_filing("synthetic")

    revised, validation, promotion_log, outcome, turns, obligation_result, conservation_flags = asyncio.run(
        extract.run_repair_loop(
            slug="synthetic",
            initial_draft=final_payload,
            filing=filing,
            validation=hard_validation,
            obligation_result=extract.obligations.ObligationResult([], []),
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
    assert turns == 1
    assert obligation_result.has_hard_unmet is False
    assert conservation_flags == []
    tool_names = {tool["name"] for tool in client.calls[0]["tools"]}
    assert tool_names == {"check_row", "search_filing", "get_pages", "check_obligations"}
    assert client.calls[0]["tool_choice"] == "auto"
    assert client.calls[0]["stream"] is True
    input_items = client.calls[0]["input_items"]
    assert input_items[0]["role"] == "system"
    assert input_items[0]["content"] == extract.REPAIR_SYSTEM_PROMPT
    repair_user = input_items[1]["content"]
    assert "actor_claims" in repair_user
    assert "PREVIOUS" in repair_user
    assert "PAGES" in repair_user
    repair_turns = [
        json.loads(line)
        for line in (audit.root / "repair_turns.jsonl").read_text().splitlines()
    ]
    assert len(repair_turns) == 1
    assert repair_turns[0]["tool_mode"] == "obligation_repair_tools"


def test_repair_context_pages_are_unique_and_include_obligation_sources(minimal_state_repo):
    env = minimal_state_repo
    env.seed_filing(
        "synthetic",
        pages=[
            {"number": 1, "content": "First page."},
            {
                "number": 2,
                "content": (
                    "The Company entered into confidentiality and standstill "
                    "agreements with 2 potentially interested financial buyers."
                ),
            },
            {"number": 3, "content": "Repeated hard-flag page."},
        ],
    )
    filing = extract.core.load_filing("synthetic")
    validation = extract.core.ValidatorResult(
        row_flags=[
            {"row_index": 0, "severity": "hard", "source_page": 3},
            {"row_index": 1, "severity": "hard", "source_page": 3},
        ],
        deal_flags=[],
    )
    obligation_result = extract.obligations.check_obligations(
        {
            "deal": _raw_deal(),
            "events": [],
        },
        filing,
    )

    pages = extract._repair_context_pages(
        draft={"deal": _raw_deal(), "events": []},
        validation=validation,
        obligation_result=obligation_result,
        filing=filing,
    )

    assert [page["page"] for page in pages] == [2, 3]
    assert pages[0]["reason"] == "obligation_source"
    assert pages[1]["reason"] == "hard_flag_source"


def test_repair_streams_complete_body_after_tool_calls(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    prompts = env.tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "extract.md").write_text("PROMPT")
    (prompts / "repair.md").write_text(
        "REPORT {validator_report}\nPREVIOUS {previous_extraction}\nPAGES {filing_pages}"
    )
    for name in extract.EXTRACTOR_RULE_FILES:
        (env.rules / name).write_text(f"RULE {name}")
    env.seed_filing("synthetic", pages=background_section_pages("page text"))
    monkeypatch.setattr(extract.core, "PROMPTS_DIR", prompts)
    monkeypatch.setattr(extract.core, "prepare_for_validate", lambda slug, raw, filing: (raw, filing, []))
    monkeypatch.setattr(
        extract.core,
        "validate",
        lambda prepared, filing: extract.core.ValidatorResult(row_flags=[], deal_flags=[]),
    )
    monkeypatch.setattr(
        extract.obligations,
        "check_obligations",
        lambda prepared, filing: extract.obligations.ObligationResult([], []),
    )

    validation = extract.core.ValidatorResult(
        row_flags=[{"row_index": 0, "code": "bad", "severity": "hard", "reason": "bad"}],
        deal_flags=[],
    )
    final_payload = _valid_claim_payload()

    class ToolThenFinalClient:
        def __init__(self):
            self.calls = []

        async def complete(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                return CompletionResult(
                    text="",
                    model=kwargs["model"],
                    tool_calls=[
                        {
                            "call_id": "call_1",
                            "name": "search_filing",
                            "arguments": json.dumps({
                                "query": "Background",
                                "page_range": None,
                                "max_hits": 1,
                            }),
                        }
                    ],
                    output_items=[
                        {
                            "type": "function_call",
                            "call_id": "call_1",
                            "name": "search_filing",
                            "arguments": json.dumps({
                                "query": "Background",
                                "page_range": None,
                                "max_hits": 1,
                            }),
                        }
                    ],
                )
            return CompletionResult(
                text=json.dumps({**final_payload, "obligation_assertions": []}),
                model=kwargs["model"],
            )

    client = ToolThenFinalClient()

    asyncio.run(
        extract.run_repair_loop(
            slug="synthetic",
            initial_draft=final_payload,
            filing=extract.core.load_filing("synthetic"),
            validation=validation,
            obligation_result=extract.obligations.ObligationResult([], []),
            llm_client=client,
            extract_model="test-model",
            audit=_audit_writer(env.tmp_path),
            token_usage=TokenUsage(),
        )
    )

    assert [call["stream"] for call in client.calls] == [True, True]


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
                obligation_result=extract.obligations.ObligationResult([], []),
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
    assert repair_record["tool_mode"] == "obligation_repair_tools"
    assert repair_record["outcome"] == "failed"
    assert repair_record["error"]["type"] == "RuntimeError"


def test_repair_failed_parse_records_completion_usage_before_reraising(minimal_state_repo, monkeypatch):
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

    class MalformedRepairClient:
        async def complete(self, **kwargs):
            return CompletionResult(
                text="{",
                model=kwargs["model"],
                input_tokens=17,
                output_tokens=19,
            )

    audit = _audit_writer(env.tmp_path)
    filing = extract.core.load_filing("synthetic")
    usage = TokenUsage()

    try:
        asyncio.run(
            extract.run_repair_loop(
                slug="synthetic",
                initial_draft={"deal": {}, "events": []},
                filing=filing,
                validation=validation,
                obligation_result=extract.obligations.ObligationResult([], []),
                llm_client=MalformedRepairClient(),
                extract_model="test-model",
                audit=audit,
                token_usage=usage,
            )
        )
    except Exception as exc:
        assert "Expecting property name" in str(exc)
    else:
        raise AssertionError("run_repair_loop should re-raise malformed repair output")

    repair_record = json.loads((audit.root / "repair_turns.jsonl").read_text().strip())
    assert repair_record["completion_turns"] == 1
    assert repair_record["tool_calls_count"] == 0
    assert usage.used == 36


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
