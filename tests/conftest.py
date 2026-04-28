"""Shared pytest fixtures for the extraction pipeline test suite.

The goal here is to avoid mocking `subprocess.run`, `pipeline.core.mark_failed`,
`pipeline.core.update_progress`, etc. Those mocks pass tests that the real
failure paths wouldn't. Each fixture sets up a minimal on-disk environment so
the real functions run end-to-end.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

import pipeline.core as pipeline


@dataclass
class StateRepo:
    """Handle to a tmp_path-backed pipeline environment.

    Attribute paths reflect the monkeypatched `pipeline.core.*` constants.
    Helper methods seed deals and filings so individual tests don't have to
    replicate dictionary shape.
    """
    tmp_path: Path
    rules: Path
    state: Path
    progress: Path
    flags: Path
    data: Path
    extractions: Path

    def seed_deal(self, slug: str, **fields) -> None:
        prog = json.loads(self.progress.read_text())
        base = {
            "is_reference": False,
            "status": "pending",
            "flag_count": 0,
            "last_run": None,
            "last_verified_by": None,
            "last_verified_at": None,
            "notes": "",
        }
        base.update(fields)
        prog["deals"][slug] = base
        self.progress.write_text(json.dumps(prog, indent=2))

    def seed_filing(
        self,
        slug: str,
        pages: list[dict] | None = None,
        manifest: dict | None = None,
    ) -> None:
        filing_dir = self.data / slug
        filing_dir.mkdir(parents=True, exist_ok=True)
        (filing_dir / "pages.json").write_text(json.dumps(
            pages or [{"number": 1, "content": "stub filing text"}]
        ))
        (filing_dir / "manifest.json").write_text(json.dumps(
            manifest or {"slug": slug, "form_type": "DEFM14A"}
        ))

    def empty_rules(self) -> None:
        for path in self.rules.iterdir():
            path.unlink()


@pytest.fixture
def minimal_state_repo(tmp_path, monkeypatch) -> StateRepo:
    """tmp_path mirror of the repo with minimal rules + state + data dirs.

    Monkeypatches every pipeline path constant used by update_progress,
    mark_failed, append_flags_log, write_output, rulebook_version, and
    load_filing.
    """
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "schema.md").write_text("# stub schema\n")

    state = tmp_path / "state"
    state.mkdir()
    progress = state / "progress.json"
    progress.write_text(json.dumps({
        "schema_version": "v1",
        "created": "2026-04-24T00:00:00Z",
        "updated": None,
        "deal_count_total": 0,
        "deal_count_reference": 0,
        "deals": {},
    }, indent=2))
    flags = state / "flags.jsonl"

    data = tmp_path / "data" / "filings"
    data.mkdir(parents=True)

    extractions = tmp_path / "output" / "extractions"
    extractions.mkdir(parents=True)

    monkeypatch.setattr(pipeline, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(pipeline, "RULES_DIR", rules)
    monkeypatch.setattr(pipeline, "STATE_DIR", state)
    monkeypatch.setattr(pipeline, "PROGRESS_PATH", progress)
    monkeypatch.setattr(pipeline, "FLAGS_PATH", flags)
    monkeypatch.setattr(pipeline, "DATA_DIR", data)
    monkeypatch.setattr(pipeline, "EXTRACTIONS_DIR", extractions)

    # run.py carries its own PROGRESS_PATH + REPO_ROOT derived at import time.
    # Tests that go through the CLI need those redirected too; importing here
    # keeps pure core tests independent from CLI setup.
    import run as run_cli
    monkeypatch.setattr(run_cli, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(run_cli, "PROGRESS_PATH", progress)

    return StateRepo(
        tmp_path=tmp_path,
        rules=rules,
        state=state,
        progress=progress,
        flags=flags,
        data=data,
        extractions=extractions,
    )


@pytest.fixture
def git_repo(tmp_path, monkeypatch) -> Path:
    """Real `git init` repo at tmp_path with a baseline empty commit.

    Monkeypatches `run.REPO_ROOT` so `commit_deal_outputs` runs against this
    repo instead of the real project checkout.
    """
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=tmp_path, check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path, check=True,
    )
    subprocess.run(
        ["git", "config", "commit.gpgsign", "false"],
        cwd=tmp_path, check=True,
    )
    subprocess.run(
        ["git", "commit", "--allow-empty", "-q", "-m", "init"],
        cwd=tmp_path, check=True,
    )
    import run as run_cli
    monkeypatch.setattr(run_cli, "REPO_ROOT", tmp_path)
    return tmp_path
