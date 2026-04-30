"""End-to-end probe for Linkflow targeted-repair tool replay.

Sends a tiny input with the repair-2 tool catalog, verifies the model emits at
least one function_call, dispatches locally, then replays the full input plus
function_call_output items and expects final text.
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

from pipeline.llm import tools  # noqa: E402


PAGES = [
    {
        "number": 22,
        "content": (
            "On May 15, 2014, the Special Committee met to discuss the offer "
            "of $25.00 per share."
        ),
    },
    {
        "number": 41,
        "content": "by and among Acquirer and BC Partners L.P. and La Caisse de depot",
    },
]


def _artifact_path(started: datetime) -> Path:
    out_dir = ROOT / "quality_reports" / "tool_probe"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / f"{started.date()}_tools_e2e.json"


async def main() -> int:
    client = AsyncOpenAI(
        api_key=os.environ["OPENAI_API_KEY"],
        base_url=os.environ["OPENAI_BASE_URL"],
    )
    initial_input = [{
        "role": "user",
        "content": (
            "I am drafting a single Bid event row. Before finalizing the row, "
            "call check_row to validate it. Row I am considering: "
            '{"BidderID":1,"process_phase":1,"role":"bidder",'
            '"bidder_alias":"X","bidder_type":"f","bid_note":"Bid",'
            '"bid_type":"informal","bid_type_inference_note":'
            '"G1 trigger phrase: offer of $25.00 per share.",'
            '"invited_to_formal_round":null,"submitted_formal_bid":null,'
            '"bid_value_pershare":25.0,"bid_value_unit":"USD_per_share",'
            '"consideration_components":["cash"],'
            '"source_quote":"On May 15, 2014, the Special Committee met to discuss the offer of $25.00 per share.",'
            '"source_page":22,"flags":[]}. '
            "Then report back what check_row said."
        ),
    }]
    payload = {
        "model": os.environ.get("EXTRACT_MODEL", "gpt-5.5"),
        "input": initial_input,
        "reasoning": {"effort": "medium"},
        "tools": tools.TARGETED_REPAIR_TOOL_DEFINITIONS,
        "tool_choice": "auto",
        "max_output_tokens": 4096,
    }
    started = datetime.now(timezone.utc)
    result: dict[str, object] = {
        "started_utc": started.isoformat(),
        "turns": [],
    }

    try:
        resp1 = await client.responses.create(**payload)
        fcs = [
            item for item in resp1.output
            if getattr(item, "type", "") == "function_call"
        ]
        result["turns"].append({
            "turn": 1,
            "function_calls": [fc.model_dump() for fc in fcs],
        })
        if not fcs:
            result["status"] = "model_did_not_call_tools"
            _artifact_path(started).write_text(json.dumps(result, indent=2))
            print(json.dumps(result, indent=2))
            return 1

        tool_outputs = []
        tool_errors = []
        for fc in fcs:
            args = json.loads(fc.arguments)
            try:
                out = tools.dispatch(name=fc.name, arguments=args, filing_pages=PAGES)
                tool_outputs.append({
                    "call_id": fc.call_id,
                    "output": json.dumps(out),
                })
            except Exception as exc:  # noqa: BLE001 - probe captures tool errors
                tool_errors.append({"call_id": fc.call_id, "error": str(exc)})
                tool_outputs.append({
                    "call_id": fc.call_id,
                    "output": json.dumps({"error": str(exc)}),
                })

        replayed = list(initial_input)
        for item in resp1.output:
            replayed.append(item.model_dump())
        for tool_output in tool_outputs:
            replayed.append({
                "type": "function_call_output",
                "call_id": tool_output["call_id"],
                "output": tool_output["output"],
            })

        payload["input"] = replayed
        resp2 = await client.responses.create(**payload)
        text = (resp2.output_text or "")[:1000]
        result["turns"].append({"turn": 2, "final_text_head": text})
        result["tool_errors"] = tool_errors
        if tool_errors:
            result["status"] = "tool_dispatch_error"
        else:
            result["status"] = "ok" if text else "no_final_text"
    except Exception as exc:  # noqa: BLE001 - probe records provider failures
        result["status"] = "error"
        result["error_class"] = type(exc).__name__
        result["error_str"] = str(exc)[:2000]

    result["finished_utc"] = datetime.now(timezone.utc).isoformat()
    _artifact_path(started).write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
