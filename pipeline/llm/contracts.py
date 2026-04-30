"""Centralized LLM contract-version hashing for cache eligibility."""

from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
from typing import Any

MAX_REPAIR_TURNS = 2

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"
_REPAIR_PROMPT_PATH = _PROMPTS_DIR / "repair.md"
_REPAIR_SOURCE_NAMES = (
    "run_repair_loop",
    "_call_prompt_only",
    "_call_with_tools",
)

_REPAIR_LOOP_CONTRACT_INPUTS: dict[str, Any] = {
    "MAX_REPAIR_TURNS": MAX_REPAIR_TURNS,
    "repair_prompt_path": str(_REPAIR_PROMPT_PATH),
    "repair_sources": _REPAIR_SOURCE_NAMES,
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _repair_prompt_hash() -> str | None:
    if not _REPAIR_PROMPT_PATH.exists():
        return None
    return _sha256_bytes(_REPAIR_PROMPT_PATH.read_bytes())


def _repair_loop_source_hash() -> str | None:
    try:
        from pipeline.llm import extract

        source_parts: list[str] = []
        for name in _REPAIR_SOURCE_NAMES:
            obj = getattr(extract, name, None)
            if obj is None:
                return None
            source_parts.append(f"# {name}\n{inspect.getsource(obj)}")
        source_parts.append(f"MAX_TOOL_TURNS={getattr(extract, 'MAX_TOOL_TURNS', None)!r}")
        return _sha256_bytes("\n".join(source_parts).encode("utf-8"))
    except Exception:  # pragma: no cover - source may be unavailable in some runners.
        return None


def _repair_loop_payload() -> dict[str, Any]:
    return {
        **_REPAIR_LOOP_CONTRACT_INPUTS,
        "MAX_REPAIR_TURNS": MAX_REPAIR_TURNS,
        "repair_prompt_present": _REPAIR_PROMPT_PATH.exists(),
        "repair_prompt_sha256": _repair_prompt_hash(),
        "repair_loop_source_sha256": _repair_loop_source_hash(),
    }


def repair_loop_contract_version() -> str:
    """Return a truncated sha256 for repair-loop cache eligibility."""
    payload = json.dumps(_repair_loop_payload(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
