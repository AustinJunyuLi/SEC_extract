import asyncio
import json

from pipeline import core
from pipeline.llm import adjudicate
from pipeline.llm.audit import AuditWriter, TokenUsage
from pipeline.llm.client import CompletionResult


def _audit_writer(tmp_path, run_id="run-adj"):
    return AuditWriter(tmp_path / "audit" / "synthetic" / "runs" / run_id, slug="synthetic", run_id=run_id)


class StubClient:
    def __init__(self):
        self.calls = 0

    async def complete(self, **kwargs):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary outage")
        return CompletionResult(
            text='{"verdict": "dismissed", "reason": "filing is silent"}',
            model=kwargs["model"],
            parsed_json={"verdict": "dismissed", "reason": "filing is silent"},
            input_tokens=3,
            output_tokens=4,
        )


class HighUsageClient:
    def __init__(self):
        self.calls = 0

    async def complete(self, **kwargs):
        self.calls += 1
        return CompletionResult(
            text='{"verdict": "upheld", "reason": "needs review"}',
            model=kwargs["model"],
            parsed_json={"verdict": "upheld", "reason": "needs review"},
            input_tokens=150_000,
            output_tokens=50_000,
        )


class RecordingClient:
    def __init__(self, text):
        self.text = text
        self.calls = []

    async def complete(self, **kwargs):
        self.calls.append(kwargs)
        return CompletionResult(text=self.text, model=kwargs["model"], input_tokens=1, output_tokens=1)


def test_adjudicate_failure_then_success_is_sequential_and_tracks_usage(tmp_path):
    raw = {
        "deal": {},
        "events": [
            {
                "bidder_name": "bidder_1",
                "bidder_alias": "Party A",
                "source_page": 2,
            }
        ],
    }
    filing = core.Filing(
        slug="synthetic",
        pages=[
            {"number": 1, "content": "before"},
            {"number": 2, "content": "flag page"},
            {"number": 3, "content": "after"},
        ],
    )
    flags = [
        {"row_index": 0, "code": "missing_nda_dropsilent", "severity": "soft", "reason": "first"},
        {"row_index": 0, "code": "missing_nda_dropsilent", "severity": "soft", "reason": "second"},
    ]
    audit = _audit_writer(tmp_path)
    usage = TokenUsage()
    client = StubClient()

    annotated = asyncio.run(
        adjudicate.adjudicate(
            "synthetic",
            raw,
            flags,
            filing,
            llm_client=client,
            adjudicate_model="adj-model",
            audit=audit,
            token_usage=usage,
        )
    )

    assert client.calls == 2
    assert "adjudicator_unavailable" in annotated[0]["reason"]
    assert "filing is silent" in annotated[1]["reason"]
    assert usage.used == 7
    calls = [json.loads(line) for line in (audit.root / "calls.jsonl").read_text().splitlines()]
    assert calls[0]["outcome"] == "failed"
    assert calls[1]["outcome"] == "ok"


def test_adjudicate_processes_all_flags_without_token_cap(tmp_path):
    raw = {"deal": {}, "events": [{"source_page": 1}]}
    filing = core.Filing(slug="synthetic", pages=[{"number": 1, "content": "page"}])
    flags = [
        {"row_index": 0, "code": "a", "severity": "soft", "reason": "first"},
        {"row_index": 0, "code": "b", "severity": "soft", "reason": "second"},
    ]
    audit = _audit_writer(tmp_path)
    usage = TokenUsage()
    client = HighUsageClient()

    annotated = asyncio.run(
        adjudicate.adjudicate(
            "synthetic",
            raw,
            flags,
            filing,
            llm_client=client,
            adjudicate_model="adj-model",
            audit=audit,
            token_usage=usage,
        )
    )

    assert client.calls == 2
    assert "needs review" in annotated[0]["reason"]
    assert "needs review" in annotated[1]["reason"]
    assert usage.used == 400_000
    calls = [json.loads(line) for line in (audit.root / "calls.jsonl").read_text().splitlines()]
    assert [call["outcome"] for call in calls] == ["ok", "ok"]


def test_adjudicate_locally_rejects_malformed_schema_output_without_repair(tmp_path):
    raw = {"deal": {}, "events": [{"source_page": 1}]}
    filing = core.Filing(slug="synthetic", pages=[{"number": 1, "content": "page"}])
    flags = [{"row_index": 0, "code": "missing_nda_dropsilent", "severity": "soft", "reason": "first"}]
    audit = _audit_writer(tmp_path)
    usage = TokenUsage()
    client = RecordingClient('{"verdict": "maybe", "reason": "bad"}')

    annotated = asyncio.run(
        adjudicate.adjudicate(
            "synthetic",
            raw,
            flags,
            filing,
            llm_client=client,
            adjudicate_model="adj-model",
            audit=audit,
            token_usage=usage,
        )
    )

    assert len(client.calls) == 1
    assert client.calls[0]["text_format"]["name"] == "custom_json_schema"
    assert "adjudicator_unavailable: MalformedJSONError" in annotated[0]["reason"]
    assert usage.used == 0
    calls = [json.loads(line) for line in (audit.root / "calls.jsonl").read_text().splitlines()]
    assert calls[0]["outcome"] == "failed"
