import asyncio
import json

from pipeline.llm import extract
from pipeline.llm.audit import AuditWriter, TokenBudget
from pipeline.llm.client import CompletionResult


def test_build_messages_embeds_prompt_rules_manifest_and_page_text(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    prompts = env.tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "extract.md").write_text("EXTRACT PROMPT")
    for name in extract.EXTRACTOR_RULE_FILES:
        (env.rules / name).write_text(f"RULE {name}")
    env.seed_filing(
        "synthetic",
        pages=[{"number": 1, "content": "embedded filing page text"}],
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
    assert payload["pages"][0]["content"] == "embedded filing page text"
    assert "data/filings/synthetic/pages.json" not in user


class StubClient:
    def __init__(self):
        self.calls = []

    async def complete(self, **kwargs):
        self.calls.append(kwargs)
        return CompletionResult(
            text='{"deal": {"slug": "synthetic"}, "events": []}',
            model=kwargs["model"],
            parsed_json={"deal": {"slug": "synthetic"}, "events": []},
            input_tokens=10,
            output_tokens=5,
        )


def test_extract_deal_writes_audit_and_consumes_budget(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    prompts = env.tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "extract.md").write_text("PROMPT")
    for name in extract.EXTRACTOR_RULE_FILES:
        (env.rules / name).write_text(f"RULE {name}")
    env.seed_filing("synthetic", pages=[{"number": 1, "content": "page text"}])
    monkeypatch.setattr(extract.core, "PROMPTS_DIR", prompts)

    audit = AuditWriter(env.tmp_path / "output" / "audit", "synthetic")
    budget = TokenBudget(max_tokens=100)
    client = StubClient()

    result = asyncio.run(
        extract.extract_deal(
            "synthetic",
            llm_client=client,
            extract_model="test-model",
            audit=audit,
            token_budget=budget,
            rulebook_version="rules-v1",
            schema_supported=True,
            max_output_tokens=123,
        )
    )

    assert result.raw_extraction == {"deal": {"slug": "synthetic"}, "events": []}
    assert budget.used == 15
    assert client.calls[0]["model"] == "test-model"
    assert client.calls[0]["max_output_tokens"] == 123
    assert (audit.root / "prompts" / "extractor.txt").read_text().startswith("=== SYSTEM ===\nPROMPT")
    assert json.loads((audit.root / "raw_response.json").read_text())["parsed_json"]["deal"]["slug"] == "synthetic"
    call_entries = (audit.root / "calls.jsonl").read_text().splitlines()
    assert len(call_entries) == 1
    assert json.loads(call_entries[0])["phase"] == "extract"
