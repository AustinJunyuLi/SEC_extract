from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.core import _atomic_write_text, _now_iso

from .client import CompletionResult


@dataclass
class TokenUsage:
    input_used: int = 0
    output_used: int = 0
    reasoning_used: int = 0

    @property
    def used(self) -> int:
        return self.input_used + self.output_used + self.reasoning_used

    def consume(self, result: CompletionResult) -> None:
        self.input_used += result.input_tokens
        self.output_used += result.output_tokens
        self.reasoning_used += result.reasoning_tokens


def prompt_hash(system: str, user: str = "") -> str:
    h = hashlib.sha256()
    h.update(system.encode("utf-8"))
    h.update(b"\n---\n")
    h.update(user.encode("utf-8"))
    return h.hexdigest()


class AuditWriter:
    def __init__(self, root: Path, slug: str):
        self.root = root / slug
        self.slug = slug
        self.prompts_dir = self.root / "prompts"
        self.root.mkdir(parents=True, exist_ok=True)
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
        self.started_at = _now_iso()

    def write_prompt(
        self,
        *,
        phase: str,
        system: str,
        user: str,
        flag_index: int | None = None,
    ) -> str:
        suffix = phase if flag_index is None else f"{phase}_{flag_index}"
        path = self.prompts_dir / f"{suffix}.txt"
        _atomic_write_text(path, f"=== SYSTEM ===\n{system}\n\n=== USER ===\n{user}\n")
        return prompt_hash(system, user)

    def append_call(self, entry: dict[str, Any]) -> None:
        path = self.root / "calls.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, sort_keys=False, default=str) + "\n")

    def write_raw_response(
        self,
        *,
        result: CompletionResult,
        parsed_json: dict[str, Any],
        rulebook_version: str,
        extractor_contract_version: str,
    ) -> None:
        payload = {
            "schema_version": "v1",
            "slug": self.slug,
            "rulebook_version": rulebook_version,
            "extractor_contract_version": extractor_contract_version,
            "model": result.model,
            "raw_text": result.text,
            "parsed_json": parsed_json,
        }
        _atomic_write_text(self.root / "raw_response.json", json.dumps(payload, indent=2) + "\n")

    def write_manifest(self, payload: dict[str, Any]) -> None:
        base = {
            "schema_version": "v1",
            "slug": self.slug,
            "started_at": self.started_at,
            "finished_at": _now_iso(),
        }
        base.update(payload)
        _atomic_write_text(self.root / "manifest.json", json.dumps(base, indent=2, default=str) + "\n")
