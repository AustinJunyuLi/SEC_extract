"""Opt-in real smoke test for the OpenAI-compatible SDK path.

This script intentionally requires a real `OPENAI_API_KEY`. Without one it
fails before importing the project SDK modules, so local no-key checks remain
clean while Worker B/C modules are still landing.
"""

from __future__ import annotations

import argparse
import asyncio
import os


def _load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


async def main() -> int:
    _load_dotenv_if_available()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=os.environ.get("EXTRACT_MODEL", "gpt-5.5"))
    args = parser.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is required")

    from pipeline.llm.client import OpenAICompatibleClient
    from pipeline.llm.response_format import supports_json_schema

    client = OpenAICompatibleClient(
        api_key=api_key,
        base_url=os.environ.get("OPENAI_BASE_URL", "https://www.linkflow.run/v1"),
    )
    json_schema_supported = await supports_json_schema(client, model=args.model)
    print(f"json_schema_supported={json_schema_supported}")

    result = await client.complete(
        system="Reply with one short sentence.",
        user="Say API smoke test passed.",
        model=args.model,
        max_output_tokens=100,
    )
    text = getattr(result, "text", "")
    print(text.strip())
    print(
        "tokens "
        f"input={getattr(result, 'input_tokens', None)} "
        f"output={getattr(result, 'output_tokens', None)} "
        f"reasoning={getattr(result, 'reasoning_tokens', None)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
