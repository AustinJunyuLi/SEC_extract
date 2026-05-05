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


def test_build_messages_accepts_marked_heading_after_unrelated_cross_reference(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    prompts = env.tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "extract.md").write_text("EXTRACT PROMPT")
    for name in extract.EXTRACTOR_RULE_FILES:
        (env.rules / name).write_text(f"RULE {name}")
    body = "The board began evaluating strategic opportunities and alternatives. " * 80
    env.seed_filing(
        "synthetic",
        pages=[
            {
                "number": 9,
                "content": "Table of Contents | Background of the Merger | 29 | Reasons for the Merger | 32 |",
            },
            {
                "number": 29,
                "content": (
                    "The merger consideration is described elsewhere. "
                    "See Merger Consideration on page 27.\n\n"
                    f"**Background of the Merger**\n\n{body}"
                ),
            },
            {
                "number": 31,
                "content": "More background narrative. " * 90 + "\n\n**Reasons for the Merger**\n\nStop.",
            },
        ],
    )
    monkeypatch.setattr(extract.core, "PROMPTS_DIR", prompts)

    _, user = extract.build_messages("synthetic")

    payload = json.loads(user)
    assert payload["section"]["start_page"] == 29
    assert payload["pages"][0]["content"].startswith("Background of the Merger")


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
                "evidence_refs": [
                    {
                        "citation_unit_id": "page_22_paragraph_2",
                        "quote_text": "CSC and Pamplona, who together we refer to as CSC/Pamplona",
                    }
                ],
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
