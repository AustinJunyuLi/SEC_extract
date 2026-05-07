import asyncio

from pipeline.llm.client import OpenAICompatibleClient

CLAIM_ONLY_TEXT = (
    '{"actor_claims":[],"event_claims":[],"bid_claims":[],'
    '"participation_count_claims":[],"actor_relation_claims":[]}'
)


class FakeStream:
    def __init__(self):
        self.events = [
            type("Event", (), {"type": "response.output_text.delta", "delta": CLAIM_ONLY_TEXT[:28]}),
            type("Event", (), {"type": "response.output_text.delta", "delta": CLAIM_ONLY_TEXT[28:70]}),
            type("Event", (), {"type": "response.output_text.delta", "delta": CLAIM_ONLY_TEXT[70:]}),
        ]

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    def __aiter__(self):
        return self._iter()

    async def _iter(self):
        for event in self.events:
            yield event

    async def get_final_response(self):
        usage = type("Usage", (), {"input_tokens": 11, "output_tokens": 13, "output_tokens_details": {"reasoning_tokens": 5}})()
        return type("Response", (), {"usage": usage, "status": "completed"})()


class MissingCompletedStream(FakeStream):
    async def get_final_response(self):
        raise RuntimeError("Didn't receive a `response.completed` event.")


class FakeResponses:
    def __init__(self):
        self.kwargs = None

    def stream(self, **kwargs):
        self.kwargs = kwargs
        return FakeStream()


class FakeOpenAI:
    def __init__(self):
        self.responses = FakeResponses()


class MissingCompletedResponses(FakeResponses):
    def stream(self, **kwargs):
        self.kwargs = kwargs
        return MissingCompletedStream()


class MissingCompletedOpenAI:
    def __init__(self):
        self.responses = MissingCompletedResponses()


def test_openai_compatible_client_uses_responses_text_format_not_chat_response_format():
    fake = FakeOpenAI()
    text_format = {"type": "json_schema", "name": "unit", "schema": {"type": "object"}, "strict": True}
    client = OpenAICompatibleClient(
        api_key="secret",
        base_url="https://example.test/v1",
        openai_client=fake,
    )

    result = asyncio.run(
        client.complete(
            model="gpt-test",
            system="system prompt",
            user="user prompt",
            text_format=text_format,
            max_output_tokens=123,
        )
    )

    kwargs = fake.responses.kwargs
    assert kwargs["model"] == "gpt-test"
    assert kwargs["input"][0]["role"] == "system"
    assert kwargs["input"][1]["role"] == "user"
    assert kwargs["text"] == {"format": text_format}
    assert kwargs["max_output_tokens"] == 123
    assert "response_format" not in kwargs
    assert result.text == CLAIM_ONLY_TEXT
    assert result.input_tokens == 11
    assert result.output_tokens == 13
    assert result.reasoning_tokens == 5


def test_openai_compatible_client_requires_structured_output_for_linkflow_newapi():
    fake = FakeOpenAI()
    text_format = {"type": "json_schema", "name": "unit", "schema": {"type": "object"}, "strict": True}
    client = OpenAICompatibleClient(
        api_key="secret",
        base_url="https://www.linkflow.run/v1",
        openai_client=fake,
    )

    result = asyncio.run(
        client.complete(
            model="gpt-test",
            system="system prompt",
            user="user prompt",
            text_format=text_format,
            max_output_tokens=None,
            reasoning_effort="high",
        )
    )

    kwargs = fake.responses.kwargs
    assert client.endpoint == "responses"
    assert client.supports_structured_output is True
    assert kwargs["model"] == "gpt-test"
    assert kwargs["input"][0]["role"] == "system"
    assert kwargs["input"][1]["role"] == "user"
    assert kwargs["reasoning"] == {"effort": "high"}
    assert kwargs["text"] == {"format": text_format}
    assert "max_output_tokens" not in kwargs
    assert result.text == CLAIM_ONLY_TEXT


def test_streaming_client_salvages_text_when_completed_event_is_missing():
    fake = MissingCompletedOpenAI()
    client = OpenAICompatibleClient(
        api_key="secret",
        base_url="https://www.linkflow.run/v1",
        openai_client=fake,
    )

    result = asyncio.run(
        client.complete(
            model="gpt-test",
            input_items=[{"role": "user", "content": "u"}],
            text_format={"type": "json_schema", "name": "unit", "schema": {"type": "object"}, "strict": True},
        )
    )

    assert result.text == CLAIM_ONLY_TEXT
    assert result.finish_reason == "missing_response_completed"
    assert result.input_tokens == 0

def test_complete_rejects_missing_text_format():
    fake = FakeOpenAI()
    client = OpenAICompatibleClient(
        api_key="secret",
        base_url="https://www.linkflow.run/v1",
        openai_client=fake,
    )

    try:
        asyncio.run(client.complete(model="gpt-test", input_items=[{"role": "user", "content": "u"}], text_format=None))
    except ValueError as exc:
        assert "text_format is required" in str(exc)
    else:
        raise AssertionError("expected ValueError")
