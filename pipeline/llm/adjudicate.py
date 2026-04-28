"""Scoped soft-flag adjudication SDK path."""

from __future__ import annotations

import json
from typing import Any

from pipeline import core

from .audit import AuditWriter, TokenBudget, TokenBudgetExceeded
from .client import LLMClient
from .response_format import call_json


ADJUDICATOR_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["upheld", "dismissed"]},
        "reason": {"type": "string"},
    },
    "required": ["verdict", "reason"],
    "additionalProperties": False,
}


def build_adjudicator_messages(
    slug: str,
    raw_extraction: dict[str, Any],
    soft_flag: dict[str, Any],
    filing: core.Filing,
) -> tuple[str, str]:
    system = (
        "You are the scoped Adjudicator for soft validator flags in an M&A extraction. "
        "Return JSON only: {\"verdict\":\"upheld|dismissed\",\"reason\":\"short rationale\"}. "
        "Do not rewrite the extraction."
    )
    source_page = soft_flag.get("source_page")
    row_index = soft_flag.get("row_index")
    events = raw_extraction.get("events") or []
    if source_page is None and isinstance(row_index, int) and 0 <= row_index < len(events):
        row_page = events[row_index].get("source_page") if isinstance(events[row_index], dict) else None
        if isinstance(row_page, int):
            source_page = row_page
    pages: list[dict[str, Any]] = []
    if isinstance(source_page, int):
        pages = [
            page for page in filing.pages
            if abs(int(page.get("number", -9999)) - source_page) <= 1
        ]
    user = json.dumps(
        {
            "slug": slug,
            "soft_flag": soft_flag,
            "events": events,
            "filing_pages": pages,
        },
        indent=2,
        sort_keys=True,
    )
    return system, user


def _annotate_flag(flag: dict[str, Any], annotation: str) -> None:
    reason = flag.get("reason") or ""
    flag["reason"] = f"{reason} | {annotation}" if reason else annotation


async def adjudicate(
    slug: str,
    raw_extraction: dict[str, Any],
    soft_flags: list[dict[str, Any]],
    filing: core.Filing,
    *,
    llm_client: LLMClient,
    adjudicate_model: str,
    audit: AuditWriter,
    token_budget: TokenBudget,
    schema_supported: bool,
    reasoning_effort: str | None = None,
) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    for index, flag in enumerate(soft_flags):
        if token_budget.used >= token_budget.max_tokens:
            _annotate_flag(flag, "adjudicator_skipped: token_budget_exceeded")
            audit.append_call({
                "ts": core._now_iso(),
                "phase": "adjudicate",
                "flag_index": index,
                "model": adjudicate_model,
                "reasoning_effort": reasoning_effort,
                "json_schema_used": schema_supported,
                "outcome": "skipped",
                "error": {
                    "type": "TokenBudgetExceeded",
                    "message": (
                        f"token_budget_exceeded: used={token_budget.used} "
                        f"cap={token_budget.max_tokens}"
                    ),
                },
            })
            annotated.append(flag)
            continue
        system, user = build_adjudicator_messages(slug, raw_extraction, flag, filing)
        prompt_digest = audit.write_prompt(
            phase="adjudicator",
            flag_index=index,
            system=system,
            user=user,
        )
        try:
            completion = await call_json(
                llm_client,
                system=system,
                user=user,
                model=adjudicate_model,
                schema_supported=schema_supported,
                schema=ADJUDICATOR_SCHEMA,
                max_output_tokens=1000,
                reasoning_effort=reasoning_effort,
            )
            verdict = completion.parsed_json or {}
            _annotate_flag(
                flag,
                f"adjudicator={verdict.get('verdict')}: {verdict.get('reason')}",
            )
            budget_error: TokenBudgetExceeded | None = None
            try:
                token_budget.consume(completion)
            except TokenBudgetExceeded as exc:
                budget_error = exc
                _annotate_flag(flag, f"adjudicator_budget_exhausted: {exc}")
            audit.append_call({
                "ts": core._now_iso(),
                "phase": "adjudicate",
                "flag_index": index,
                "model": completion.model,
                "reasoning_effort": reasoning_effort,
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
                "error": (
                    None if budget_error is None
                    else {"type": type(budget_error).__name__, "message": str(budget_error)[:500]}
                ),
            })
        except Exception as exc:  # noqa: BLE001 - one failed flag must not stop later flags.
            _annotate_flag(flag, f"adjudicator_unavailable: {type(exc).__name__}")
            audit.append_call({
                "ts": core._now_iso(),
                "phase": "adjudicate",
                "flag_index": index,
                "model": adjudicate_model,
                "reasoning_effort": reasoning_effort,
                "prompt_hash": prompt_digest,
                "json_schema_used": schema_supported,
                "outcome": "failed",
                "error": {"type": type(exc).__name__, "message": str(exc)[:500]},
            })
        annotated.append(flag)
    return annotated
