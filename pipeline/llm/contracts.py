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
_REPAIR_LOOP_SOURCE = "pipeline.llm.extract.run_repair_loop"

_REPAIR_LOOP_CONTRACT_INPUTS: dict[str, Any] = {
    "MAX_REPAIR_TURNS": MAX_REPAIR_TURNS,
    "repair_prompt_path": str(_REPAIR_PROMPT_PATH),
    "repair_loop_source": _REPAIR_LOOP_SOURCE,
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

        run_repair_loop = getattr(extract, "run_repair_loop", None)
        if run_repair_loop is None:
            return None
        return _sha256_bytes(inspect.getsource(run_repair_loop).encode("utf-8"))
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
