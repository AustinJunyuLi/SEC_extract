"""Extractor SDK message construction and call path."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pipeline import core

from .audit import AuditWriter, TokenBudget
from .client import CompletionResult, LLMClient
from .response_format import SCHEMA_R1, call_json


EXTRACTOR_RULE_FILES = ("schema.md", "events.md", "bidders.md", "bids.md", "dates.md")


@dataclass
class ExtractResult:
    raw_extraction: dict[str, Any]
    completion: CompletionResult
    rulebook_version: str


def build_messages(slug: str) -> tuple[str, str]:
    prompt = (core.PROMPTS_DIR / "extract.md").read_text()
    rule_chunks = []
    for name in EXTRACTOR_RULE_FILES:
        path = core.RULES_DIR / name
        rule_chunks.append(f"\n\n# rules/{path.name}\n\n{path.read_text()}")
    manifest = json.loads((core.DATA_DIR / slug / "manifest.json").read_text())
    pages = json.loads((core.DATA_DIR / slug / "pages.json").read_text())
    system = prompt + "\n\n" + "\n".join(rule_chunks)
    user = json.dumps(
        {"slug": slug, "manifest": manifest, "pages": pages},
        indent=2,
        sort_keys=True,
    )
    return system, user


async def extract_deal(
    slug: str,
    *,
    llm_client: LLMClient,
    extract_model: str,
    audit: AuditWriter,
    token_budget: TokenBudget,
    rulebook_version: str,
    schema_supported: bool,
    max_output_tokens: int | None = 32000,
) -> ExtractResult:
    system, user = build_messages(slug)
    prompt_digest = audit.write_prompt(phase="extractor", system=system, user=user)
    completion = await call_json(
        llm_client,
        system=system,
        user=user,
        model=extract_model,
        schema_supported=schema_supported,
        schema=SCHEMA_R1,
        max_output_tokens=max_output_tokens,
    )
    token_budget.consume(completion)
    parsed = completion.parsed_json or {}
    audit.write_raw_response(
        result=completion,
        parsed_json=parsed,
        rulebook_version=rulebook_version,
    )
    audit.append_call({
        "ts": core._now_iso(),
        "phase": "extract",
        "flag_index": None,
        "model": completion.model,
        "prompt_hash": prompt_digest,
        "json_schema_used": schema_supported,
        "input_tokens": completion.input_tokens,
        "output_tokens": completion.output_tokens,
        "reasoning_tokens": completion.reasoning_tokens,
        "latency_seconds": completion.latency_seconds,
        "attempts": completion.attempts,
        "finish_reason": completion.finish_reason,
        "watchdog": {
            "warnings": completion.watchdog.warnings,
            "max_idle_seconds": completion.watchdog.max_idle_seconds,
        },
        "outcome": "ok",
        "error": None,
    })
    return ExtractResult(
        raw_extraction=parsed,
        completion=completion,
        rulebook_version=rulebook_version,
    )
