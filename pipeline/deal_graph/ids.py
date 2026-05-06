"""Deterministic identifiers for deal_graph_v2 rows."""
from __future__ import annotations

import hashlib
import json
from typing import Any


def stable_json(value: Any) -> str:
    """Serialize values in a stable compact form for hashing."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def stable_hash(*parts: Any, length: int = 24) -> str:
    digest = hashlib.sha256()
    for part in parts:
        if isinstance(part, bytes):
            encoded = part
        elif isinstance(part, str):
            encoded = part.encode("utf-8")
        else:
            encoded = stable_json(part).encode("utf-8")
        digest.update(encoded)
        digest.update(b"\x1f")
    return digest.hexdigest()[:length]


def make_id(prefix: str, *parts: Any) -> str:
    if not prefix or not prefix.replace("_", "").isalnum():
        raise ValueError(f"invalid id prefix: {prefix!r}")
    return f"{prefix}_{stable_hash(*parts)}"


def quote_hash(quote_text: str) -> str:
    return hashlib.sha256(quote_text.encode("utf-8")).hexdigest()


def evidence_fingerprint(
    filing_id: str,
    char_start: int,
    char_end: int,
    quote_text_hash: str,
) -> str:
    return hashlib.sha256(
        f"{filing_id}\x1f{char_start}\x1f{char_end}\x1f{quote_text_hash}".encode("utf-8")
    ).hexdigest()
