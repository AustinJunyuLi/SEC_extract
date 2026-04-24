"""CLI-level tests for run.py.

No mocking of `pipeline.mark_failed`, `pipeline.update_progress`, or
`subprocess.run`. Each test exercises the real code path against a tmp_path
state + (for commit tests) a real `git init` repo.
"""
import json
import subprocess
import sys

import pytest

import pipeline
import run as run_cli


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_raw_extraction(tmp_path, body=None):
    raw_path = tmp_path / "raw.json"
    raw_path.write_text(json.dumps(body if body is not None else {"deal": {}, "events": []}))
    return raw_path


def _passable_extraction(slug: str, text: str = "the target entered a merger agreement") -> dict:
    """Return a raw extraction that will actually validate, so we can exercise
    the non-failure CLI path end-to-end against a stubbed filing."""
    return {
        "deal": {
            "slug": slug,
            "auction": False,
            "bidder_registry": {},
        },
        "events": [{
            "BidderID": 1,
            "bid_note": "Executed",
            "bid_date_precise": "2026-04-24",
            "bid_date_rough": None,
            "bidder_name": None,
            "bidder_alias": None,
            "process_phase": 1,
            "source_quote": text,
            "source_page": 1,
        }],
    }


# ---------------------------------------------------------------------------
# main(): --commit default behavior
# ---------------------------------------------------------------------------


def test_main_defaults_to_no_commit(minimal_state_repo, git_repo, monkeypatch):
    """No --commit flag → no git commit lands, even in a real repo."""
    env = minimal_state_repo
    env.seed_deal("medivation")
    env.seed_filing("medivation", pages=[{"number": 1, "content": "the target entered a merger agreement"}])
    raw_path = env.tmp_path / "raw.json"
    raw_path.write_text(json.dumps(_passable_extraction("medivation")))

    monkeypatch.setattr(sys, "argv", [
        "run.py",
        "--slug", "medivation",
        "--raw-extraction", str(raw_path),
    ])
    commits_before = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"], cwd=git_repo, capture_output=True, text=True, check=True,
    ).stdout.strip()

    assert run_cli.main() == 0

    commits_after = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"], cwd=git_repo, capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert commits_before == commits_after, "no --commit → repo should not grow"


def test_main_commit_flag_produces_one_commit(minimal_state_repo, git_repo, monkeypatch):
    """--commit → exactly one new commit with only the deal's paths."""
    env = minimal_state_repo
    env.seed_deal("medivation")
    env.seed_filing("medivation", pages=[{"number": 1, "content": "the target entered a merger agreement"}])
    raw_path = env.tmp_path / "raw.json"
    raw_path.write_text(json.dumps(_passable_extraction("medivation")))

    monkeypatch.setattr(sys, "argv", [
        "run.py",
        "--slug", "medivation",
        "--raw-extraction", str(raw_path),
        "--commit",
    ])

    assert run_cli.main() == 0

    commits = subprocess.run(
        ["git", "rev-list", "HEAD"], cwd=git_repo, capture_output=True, text=True, check=True,
    ).stdout.strip().splitlines()
    assert len(commits) == 2, "one baseline + one deal commit"
    # Confirm the deal commit touched only our paths.
    changed = subprocess.run(
        ["git", "show", "--name-only", "--pretty=", "HEAD"],
        cwd=git_repo, capture_output=True, text=True, check=True,
    ).stdout.strip().splitlines()
    assert set(changed) <= {
        "output/extractions/medivation.json",
        "state/progress.json",
        "state/flags.jsonl",
    }


# ---------------------------------------------------------------------------
# main(): failure paths hit the real mark_failed, land in progress.json
# ---------------------------------------------------------------------------


def test_main_missing_raw_extraction_marks_failed_in_state(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    env.seed_deal("medivation")
    missing_path = env.tmp_path / "missing.json"

    monkeypatch.setattr(sys, "argv", [
        "run.py",
        "--slug", "medivation",
        "--raw-extraction", str(missing_path),
    ])

    assert run_cli.main() == 1

    state = json.loads(env.progress.read_text())
    deal = state["deals"]["medivation"]
    assert deal["status"] == "failed"
    assert deal["notes"].startswith("missing_raw_extraction")


def test_main_malformed_raw_json_marks_failed_in_state(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    env.seed_deal("medivation")
    raw_path = env.tmp_path / "bad.json"
    raw_path.write_text("{not-json")

    monkeypatch.setattr(sys, "argv", [
        "run.py",
        "--slug", "medivation",
        "--raw-extraction", str(raw_path),
    ])

    assert run_cli.main() == 1

    state = json.loads(env.progress.read_text())
    deal = state["deals"]["medivation"]
    assert deal["status"] == "failed"
    assert deal["notes"].startswith("malformed_raw_json")


def test_main_finalization_failure_marks_failed_in_state(minimal_state_repo, monkeypatch):
    """Finalize fails because filing artifacts aren't seeded — real failure path."""
    env = minimal_state_repo
    env.seed_deal("medivation")
    # Deliberately do NOT seed the filing — load_filing will raise.
    raw_path = _write_raw_extraction(env.tmp_path, _passable_extraction("medivation"))

    monkeypatch.setattr(sys, "argv", [
        "run.py",
        "--slug", "medivation",
        "--raw-extraction", str(raw_path),
    ])

    assert run_cli.main() == 1

    state = json.loads(env.progress.read_text())
    deal = state["deals"]["medivation"]
    assert deal["status"] == "failed"
    # load_filing raises FileNotFoundError → recorded with that class name.
    assert "FileNotFoundError" in deal["notes"]


# ---------------------------------------------------------------------------
# Exit code 2: recorder itself crashed
# ---------------------------------------------------------------------------


def test_main_exits_2_when_recorder_crashes(minimal_state_repo, monkeypatch):
    """If pipeline.mark_failed itself raises (e.g., progress.json disappears
    between validate and record), run.py must exit 2 rather than 1, so CI
    can tell the recorder broke."""
    env = minimal_state_repo
    env.seed_deal("medivation")

    # Let validate_slug succeed; delete progress.json just before
    # _record_failure so mark_failed/update_progress raise FileNotFoundError.
    real_record_failure = run_cli._record_failure

    def deleting_record_failure(slug, note):
        env.progress.unlink()
        return real_record_failure(slug, note)

    monkeypatch.setattr(run_cli, "_record_failure", deleting_record_failure)

    missing_path = env.tmp_path / "missing.json"
    monkeypatch.setattr(sys, "argv", [
        "run.py",
        "--slug", "medivation",
        "--raw-extraction", str(missing_path),
    ])

    assert run_cli.main() == 2


# ---------------------------------------------------------------------------
# Commit pre-flight: --only would overwrite staged drift
# ---------------------------------------------------------------------------


def _prep_commit_result(env, slug="medivation"):
    """Create the minimum files commit_deal_outputs needs to exist.

    Returns a `PipelineResult` whose paths point under the tmp repo.
    """
    output_path = env.extractions / f"{slug}.json"
    output_path.write_text("{}")
    env.flags.write_text("")
    return pipeline.PipelineResult(
        status="passed_clean",
        flag_count=0,
        notes="",
        output_path=output_path,
    )


def test_commit_aborts_on_staged_drift(minimal_state_repo, git_repo):
    """Austin has manually staged a different version of the output file;
    --only would rewrite it. Pre-flight must refuse."""
    env = minimal_state_repo
    result = _prep_commit_result(env)

    # Stage one version (as if from manual review)...
    env.extractions.joinpath("medivation.json").write_text('{"staged": true}')
    subprocess.run(
        ["git", "add", "--", "output/extractions/medivation.json"],
        cwd=git_repo, check=True,
    )
    # ...then change working tree to a different version.
    env.extractions.joinpath("medivation.json").write_text('{"working_tree": true}')

    with pytest.raises(RuntimeError, match="staged content"):
        run_cli.commit_deal_outputs("medivation", result)


def test_commit_proceeds_when_no_staged_drift(minimal_state_repo, git_repo):
    """Clean index + working tree → commit lands."""
    env = minimal_state_repo
    env.progress.write_text("{}")
    result = _prep_commit_result(env)

    run_cli.commit_deal_outputs("medivation", result)

    # Verify a commit landed.
    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=git_repo, capture_output=True, text=True, check=True,
    ).stdout
    assert "deal=medivation" in log


def test_commit_ignores_unrelated_staged_files(minimal_state_repo, git_repo):
    """An unrelated staged file must NOT ride along in the deal commit."""
    env = minimal_state_repo
    env.progress.write_text("{}")
    result = _prep_commit_result(env)

    # Stage something unrelated.
    unrelated = env.tmp_path / "AGENTS.md"
    unrelated.write_text("unrelated change\n")
    subprocess.run(["git", "add", "--", "AGENTS.md"], cwd=git_repo, check=True)

    run_cli.commit_deal_outputs("medivation", result)

    # Verify HEAD's file list excludes AGENTS.md.
    files = subprocess.run(
        ["git", "show", "--name-only", "--pretty=", "HEAD"],
        cwd=git_repo, capture_output=True, text=True, check=True,
    ).stdout.strip().splitlines()
    assert "AGENTS.md" not in files
    assert any(f.startswith("output/extractions/") for f in files)
