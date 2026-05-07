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


RAW_RESPONSE_SCHEMA_VERSION = "raw_response_v3"
AUDIT_RUN_SCHEMA_VERSION = "audit_run_v3"
AUDIT_LATEST_SCHEMA_VERSION = "audit_v3"
VALIDATION_SCHEMA_VERSION = "validation_v1"
AUDIT_SLUG_ROOT_ALLOWED_NAMES: frozenset[str] = frozenset({"latest.json", "runs"})


def audit_slug_root(audit_root: Path, slug: str) -> Path:
    return audit_root / slug


def audit_run_dir(audit_root: Path, slug: str, run_id: str) -> Path:
    return audit_slug_root(audit_root, slug) / "runs" / run_id


class AuditWriter:
    def __init__(self, run_dir: Path, *, slug: str, run_id: str):
        self.root = run_dir
        self.slug = slug
        self.run_id = run_id
        self.prompts_dir = self.root / "prompts"
        if self.root.name != run_id or self.root.parent.name != "runs":
            raise ValueError(
                "AuditWriter requires an explicit output/audit/{slug}/runs/{run_id} directory"
            )
        self.root.mkdir(parents=True, exist_ok=True)
        self.prompts_dir.mkdir(parents=True, exist_ok=True)
        self.started_at = _now_iso()

    @property
    def slug_root(self) -> Path:
        return self.root.parent.parent

    @property
    def latest_path(self) -> Path:
        return self.slug_root / "latest.json"

    def _relative_to_slug_root(self, path: Path) -> str:
        return path.resolve().relative_to(self.slug_root.resolve()).as_posix()

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
            "schema_version": RAW_RESPONSE_SCHEMA_VERSION,
            "slug": self.slug,
            "run_id": self.run_id,
            "rulebook_version": rulebook_version,
            "extractor_contract_version": extractor_contract_version,
            "model": result.model,
            "raw_text": result.text,
            "parsed_json": parsed_json,
        }
        _atomic_write_text(self.root / "raw_response.json", json.dumps(payload, indent=2) + "\n")

    def write_validation(self, payload: dict[str, Any]) -> None:
        base = {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "slug": self.slug,
            "run_id": self.run_id,
        }
        base.update(payload)
        _atomic_write_text(self.root / "validation.json", json.dumps(base, indent=2, default=str) + "\n")

    def write_manifest(self, payload: dict[str, Any] | None = None, **kwargs: Any) -> None:
        base = {
            "schema_version": AUDIT_RUN_SCHEMA_VERSION,
            "slug": self.slug,
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": _now_iso(),
        }
        payload = dict(payload or {})
        payload.update(kwargs)
        base.update(payload)
        _atomic_write_text(self.root / "manifest.json", json.dumps(base, indent=2, default=str) + "\n")

    def write_latest(self, *, outcome: str, stability_eligible: bool) -> None:
        raw_response_path = self.root / "raw_response.json"
        validation_path = self.root / "validation.json"
        payload = {
            "schema_version": AUDIT_LATEST_SCHEMA_VERSION,
            "slug": self.slug,
            "run_id": self.run_id,
            "outcome": outcome,
            "stability_eligible": stability_eligible,
            "manifest_path": self._relative_to_slug_root(self.root / "manifest.json"),
            "raw_response_path": (
                self._relative_to_slug_root(raw_response_path)
                if raw_response_path.exists() else None
            ),
            "validation_path": (
                self._relative_to_slug_root(validation_path)
                if validation_path.exists() else None
            ),
        }
        _atomic_write_text(self.latest_path, json.dumps(payload, indent=2) + "\n")
