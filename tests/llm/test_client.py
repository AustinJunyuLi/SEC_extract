import asyncio

from pipeline.llm.client import OpenAICompatibleClient


class FakeStream:
    def __init__(self):
        self.events = [
            type("Event", (), {"type": "response.output_text.delta", "delta": '{"deal":'}),
            type("Event", (), {"type": "response.output_text.delta", "delta": "{}"}),
            type("Event", (), {"type": "response.output_text.delta", "delta": ',"events":[]}'}),
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


class FakeResponses:
    def __init__(self):
        self.kwargs = None

    def stream(self, **kwargs):
        self.kwargs = kwargs
        return FakeStream()


class FakeOpenAI:
    def __init__(self):
        self.responses = FakeResponses()


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
    assert result.text == '{"deal":{},"events":[]}'
    assert result.input_tokens == 11
    assert result.output_tokens == 13
    assert result.reasoning_tokens == 5


def test_openai_compatible_client_disables_structured_output_for_linkflow_newapi():
    fake = FakeOpenAI()
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
            text_format=None,
            max_output_tokens=None,
            reasoning_effort="high",
        )
    )

    kwargs = fake.responses.kwargs
    assert client.endpoint == "responses"
    assert client.supports_structured_output is False
    assert kwargs["model"] == "gpt-test"
    assert kwargs["input"][0]["role"] == "system"
    assert kwargs["input"][1]["role"] == "user"
    assert kwargs["reasoning"] == {"effort": "high"}
    assert "text" not in kwargs
    assert "max_output_tokens" not in kwargs
    assert result.text == '{"deal":{},"events":[]}'
