import asyncio
import json

from pipeline import core
from pipeline.llm import adjudicate
from pipeline.llm.audit import AuditWriter, TokenBudget
from pipeline.llm.client import CompletionResult


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


def test_adjudicate_failure_then_success_is_sequential_and_budgeted(tmp_path):
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
    audit = AuditWriter(tmp_path / "audit", "synthetic")
    budget = TokenBudget(max_tokens=100)
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
            token_budget=budget,
            schema_supported=True,
        )
    )

    assert client.calls == 2
    assert "adjudicator_unavailable" in annotated[0]["reason"]
    assert "filing is silent" in annotated[1]["reason"]
    assert budget.used == 7
    calls = [json.loads(line) for line in (audit.root / "calls.jsonl").read_text().splitlines()]
    assert calls[0]["outcome"] == "failed"
    assert calls[1]["outcome"] == "ok"
