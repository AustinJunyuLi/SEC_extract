"""Export helpers for deal_graph_v2 snapshots and review rows."""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any, Iterable

from .project_review import REVIEW_ROW_FIELDS


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    tmp_path.write_text(text)
    os.replace(tmp_path, path)


def write_snapshot(graph: dict[str, Any], path: Path) -> None:
    _atomic_write_text(path, json.dumps(graph, indent=2, sort_keys=True) + "\n")


def write_jsonl(rows: Iterable[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    with tmp_path.open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")
    os.replace(tmp_path, path)


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(REVIEW_ROW_FIELDS)
    tmp_path = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    with tmp_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp_path, path)
