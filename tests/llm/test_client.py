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


class MissingCompletedStream(FakeStream):
    async def get_final_response(self):
        raise RuntimeError("Didn't receive a `response.completed` event.")


class FakeResponses:
    def __init__(self):
        self.kwargs = None

    def stream(self, **kwargs):
        self.kwargs = kwargs
        return FakeStream()

    async def create(self, **kwargs):
        self.kwargs = kwargs
        usage = type("Usage", (), {
            "input_tokens": 7,
            "output_tokens": 8,
            "output_tokens_details": {"reasoning_tokens": 2},
        })()
        output = [
            type("Item", (), {
                "type": "function_call",
                "name": "example_function",
                "call_id": "c1",
                "arguments": "{}",
                "model_dump": lambda self: {
                    "type": "function_call",
                    "name": "example_function",
                    "call_id": "c1",
                    "arguments": "{}",
                },
            })()
        ]
        return type("Response", (), {
            "output_text": "",
            "output": output,
            "usage": usage,
            "status": "completed",
        })()


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
    assert result.text == '{"deal":{},"events":[]}'
    assert result.input_tokens == 11
    assert result.output_tokens == 13
    assert result.reasoning_tokens == 5


def test_openai_compatible_client_keeps_structured_output_for_linkflow_newapi():
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
    assert client.supports_structured_output is True
    assert kwargs["model"] == "gpt-test"
    assert kwargs["input"][0]["role"] == "system"
    assert kwargs["input"][1]["role"] == "user"
    assert kwargs["reasoning"] == {"effort": "high"}
    assert "text" not in kwargs
    assert "max_output_tokens" not in kwargs
    assert result.text == '{"deal":{},"events":[]}'


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
            stream=True,
        )
    )

    assert result.text == '{"deal":{},"events":[]}'
    assert result.finish_reason == "missing_response_completed"
    assert result.input_tokens == 0


def test_complete_passes_tools_and_tool_choice_through_non_streaming():
    fake = FakeOpenAI()
    client = OpenAICompatibleClient(
        api_key="secret",
        base_url="https://www.linkflow.run/v1",
        openai_client=fake,
    )
    tool_defs = [{
        "type": "function",
        "name": "example_function",
        "parameters": {"type": "object", "properties": {}},
    }]

    result = asyncio.run(
        client.complete(
            model="gpt-test",
            input_items=[{"role": "user", "content": "u"}],
            tools=tool_defs,
            tool_choice="auto",
            stream=False,
        )
    )

    kwargs = fake.responses.kwargs
    assert kwargs["tools"] == tool_defs
    assert kwargs["tool_choice"] == "auto"
    assert kwargs["input"] == [{"role": "user", "content": "u"}]
    assert result.tool_calls == [{
        "type": "function_call",
        "name": "example_function",
        "call_id": "c1",
        "arguments": "{}",
    }]
    assert result.input_tokens == 7
    assert result.output_tokens == 8
    assert result.reasoning_tokens == 2
