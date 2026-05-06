"""Storage helpers for deal_graph_v2 run artifacts."""
from __future__ import annotations

import sqlite3
import json
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any, Iterable

from .schema import DDL, EXPECTED_TABLES


DB_FILENAME = "deal_graph.duckdb"
SNAPSHOT_FILENAME = "deal_graph_v2.json"


def _load_duckdb():
    try:
        import duckdb  # type: ignore
    except ModuleNotFoundError:
        return None
    return duckdb


@dataclass(frozen=True)
class DealGraphArtifacts:
    repo_root: Path
    slug: str
    run_id: str

    @property
    def run_dir(self) -> Path:
        return self.repo_root / "output" / "audit" / self.slug / "runs" / self.run_id

    @property
    def database_path(self) -> Path:
        return self.run_dir / DB_FILENAME

    @property
    def snapshot_path(self) -> Path:
        return self.run_dir / SNAPSHOT_FILENAME


def artifact_paths(repo_root: str | Path, slug: str, run_id: str) -> DealGraphArtifacts:
    if not slug or "/" in slug or slug in {".", ".."}:
        raise ValueError(f"invalid deal slug: {slug!r}")
    if not run_id or "/" in run_id or run_id in {".", ".."}:
        raise ValueError(f"invalid run_id: {run_id!r}")
    return DealGraphArtifacts(Path(repo_root), slug, run_id)


class DealGraphStore:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.backend = "duckdb" if _load_duckdb() is not None else "sqlite"
        self._conn: Any | None = None

    def connect(self) -> "DealGraphStore":
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        duckdb = _load_duckdb()
        if duckdb is not None:
            self.backend = "duckdb"
            self._conn = duckdb.connect(str(self.database_path))
        else:
            self.backend = "sqlite"
            self._conn = sqlite3.connect(str(self.database_path))
        return self

    @property
    def conn(self) -> Any:
        if self._conn is None:
            raise RuntimeError("DealGraphStore is not connected")
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "DealGraphStore":
        return self.connect()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc_type is None:
            self.commit()
        self.close()

    def execute(self, sql: str, parameters: Iterable[Any] | None = None) -> Any:
        if parameters is None:
            return self.conn.execute(sql)
        return self.conn.execute(sql, tuple(parameters))

    def executemany(self, sql: str, seq_of_parameters: Iterable[Iterable[Any]]) -> Any:
        return self.conn.executemany(sql, [tuple(params) for params in seq_of_parameters])

    def commit(self) -> None:
        if self.backend == "sqlite":
            self.conn.commit()

    def init_schema(self) -> None:
        for statement in DDL:
            self.execute(statement)
        self.commit()
        self.assert_expected_tables()

    def list_tables(self) -> set[str]:
        if self.backend == "duckdb":
            rows = self.execute("SHOW TABLES").fetchall()
            return {row[0] for row in rows}
        rows = self.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
        return {row[0] for row in rows}

    def assert_expected_tables(self) -> None:
        missing = set(EXPECTED_TABLES) - self.list_tables()
        if missing:
            raise RuntimeError(f"deal_graph_v2 store missing tables: {sorted(missing)}")

    def reject_legacy_canonical_tables(self) -> None:
        legacy = self.list_tables().intersection({"event_rows", "row_events", "bidder_registry"})
        if legacy:
            raise RuntimeError(f"legacy row-per-event tables are not canonical: {sorted(legacy)}")

    def table_columns(self, table: str) -> list[str]:
        rows = self.execute(f"PRAGMA table_info('{table}')").fetchall()
        return [row[1] for row in rows]

    def insert_rows(self, table: str, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        columns = [column for column in self.table_columns(table) if any(column in row for row in rows)]
        if not columns:
            return
        placeholders = ", ".join(["?"] * len(columns))
        column_sql = ", ".join(columns)
        values = []
        seen: set[tuple[Any, ...]] = set()
        for row in rows:
            key = _dedupe_key(table, row)
            if key in seen:
                continue
            seen.add(key)
            values.append(tuple(_sql_value(row.get(column)) for column in columns))
        self.executemany(
            f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders})",
            values,
        )

    def insert_snapshot(self, graph: dict[str, Any]) -> None:
        table_map = {
            "deals": "deals",
            "process_cycles": "process_cycles",
            "claims": "claims",
            "claim_coverage_links": "claim_coverage_links",
            "claim_evidence": "claim_evidence",
            "claim_dispositions": "claim_dispositions",
            "coverage_results": "coverage_results",
            "actors": "actors",
            "actor_relations": "actor_relations",
            "events": "events",
            "event_actor_links": "event_actor_links",
            "participation_counts": "participation_counts",
            "row_evidence": "row_evidence",
            "review_flags": "review_flags",
            "review_rows": "review_rows",
        }
        if graph.get("evidence"):
            self.insert_rows("spans", graph["evidence"])
        for graph_key, table in table_map.items():
            rows = graph.get(graph_key)
            if isinstance(rows, list):
                self.insert_rows(table, rows)
        self.commit()


def _sql_value(value: Any) -> Any:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return value


def _dedupe_key(table: str, row: dict[str, Any]) -> tuple[Any, ...]:
    if table == "row_evidence":
        return (row.get("row_table"), row.get("row_id"), row.get("evidence_id"))
    if table == "claim_evidence":
        return (row.get("claim_id"), row.get("evidence_id"))
    if table == "claim_coverage_links":
        return (row.get("claim_id"), row.get("obligation_id"))
    return tuple(sorted((key, _freeze(value)) for key, value in row.items()))


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((key, _freeze(child)) for key, child in value.items()))
    if isinstance(value, list):
        return tuple(_freeze(child) for child in value)
    return value


def init_store(repo_root: str | Path, slug: str, run_id: str) -> DealGraphStore:
    paths = artifact_paths(repo_root, slug, run_id)
    store = DealGraphStore(paths.database_path).connect()
    store.init_schema()
    return store
