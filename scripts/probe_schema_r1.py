"""Probe Linkflow strict json_schema acceptance on the live SCHEMA_R1 shape.

Run with OPENAI_API_KEY and OPENAI_BASE_URL set. Writes the response status and
parse outcome to quality_reports/schema_probe/.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from openai import AsyncOpenAI

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.llm import extract  # noqa: E402
from pipeline.llm.response_format import SCHEMA_R1, json_schema_format  # noqa: E402


async def main(slug: str = "medivation") -> int:
    client = AsyncOpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ["OPENAI_BASE_URL"],
    )
    system, user = extract.build_messages(slug)
    payload = {
        "model": os.environ.get("EXTRACT_MODEL", "gpt-5.5"),
        "input": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "reasoning": {"effort": "medium"},
        "text": {"format": json_schema_format(SCHEMA_R1)},
        "max_output_tokens": 8192,
    }
    out_dir = ROOT / "quality_reports" / "schema_probe"
    out_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    result: dict[str, object] = {
        "slug": slug,
        "started_utc": started.isoformat(),
    }
    try:
        resp = await client.responses.create(**payload)
        text = resp.output_text or ""
        result["status"] = "ok"
        result["output_text_chars"] = len(text)
        result["output_text_head"] = text[:400]
        usage = getattr(resp, "usage", None)
        if usage is not None:
            result["usage"] = usage.model_dump()
        try:
            json.loads(text)
            result["parses"] = True
        except json.JSONDecodeError as exc:
            result["parses"] = False
            result["parse_error"] = str(exc)
    except Exception as exc:  # noqa: BLE001 - probe captures provider errors
        result["status"] = "error"
        result["error_class"] = type(exc).__name__
        result["error_str"] = str(exc)[:2000]
    result["finished_utc"] = datetime.now(timezone.utc).isoformat()
    out_path = out_dir / f"{started.date()}_schema_r1_baseline_{slug}.json"
    out_path.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") == "ok" and result.get("parses") else 1


if __name__ == "__main__":
    selected_slug = sys.argv[1] if len(sys.argv) > 1 else "medivation"
    sys.exit(asyncio.run(main(selected_slug)))
