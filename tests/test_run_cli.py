"""CLI-level tests for the SDK-backed single-deal runner."""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

import run as run_cli


@dataclass
class DummyOutcome:
    status: str = "passed_clean"
    flag_count: int = 0
    notes: str = ""
    output_path: Path | None = None
    audit_path: Path | None = None


def _set_argv(monkeypatch, *args: str) -> None:
    monkeypatch.setattr(sys, "argv", ["run.py", *args])


def test_print_prompt_prints_system_and_user(monkeypatch, capsys):
    monkeypatch.setattr(
        run_cli,
        "_build_messages",
        lambda slug: ("system prompt for " + slug, "user prompt for " + slug),
    )
    _set_argv(monkeypatch, "--slug", "medivation", "--print-prompt")

    assert run_cli.main() == 0

    out = capsys.readouterr().out
    assert "=== SYSTEM ===" in out
    assert "system prompt for medivation" in out
    assert "=== USER ===" in out
    assert "user prompt for medivation" in out


def test_default_mode_is_extract(monkeypatch):
    calls = []

    def fake_run(slug, *, mode, args):
        calls.append((slug, mode, args.commit, args.dry_run))
        return DummyOutcome()

    monkeypatch.setattr(run_cli, "_run_single_deal", fake_run)
    _set_argv(monkeypatch, "--slug", "medivation")

    assert run_cli.main() == 0
    assert calls == [("medivation", "extract", False, False)]


def test_extract_flag_selects_extract_mode(monkeypatch):
    calls = []
    monkeypatch.setattr(
        run_cli,
        "_run_single_deal",
        lambda slug, *, mode, args: calls.append(mode) or DummyOutcome(),
    )
    _set_argv(monkeypatch, "--slug", "medivation", "--extract")

    assert run_cli.main() == 0
    assert calls == ["extract"]


def test_re_validate_selects_cache_mode(monkeypatch):
    calls = []
    monkeypatch.setattr(
        run_cli,
        "_run_single_deal",
        lambda slug, *, mode, args: calls.append(mode) or DummyOutcome(),
    )
    _set_argv(monkeypatch, "--slug", "medivation", "--re-validate")

    assert run_cli.main() == 0
    assert calls == ["re_validate"]


def test_re_extract_selects_fresh_mode(monkeypatch):
    calls = []
    monkeypatch.setattr(
        run_cli,
        "_run_single_deal",
        lambda slug, *, mode, args: calls.append(mode) or DummyOutcome(),
    )
    _set_argv(monkeypatch, "--slug", "medivation", "--re-extract")

    assert run_cli.main() == 0
    assert calls == ["re_extract"]


def test_commit_passes_through_to_config(monkeypatch):
    calls = []

    def fake_run(slug, *, mode, args):
        calls.append(args.commit)
        return DummyOutcome()

    monkeypatch.setattr(run_cli, "commit_deal_outputs", lambda slug, outcome: None)
    monkeypatch.setattr(run_cli, "_run_single_deal", fake_run)
    _set_argv(monkeypatch, "--slug", "medivation", "--commit")

    assert run_cli.main() == 0
    assert calls == [True]


def test_dry_run_does_not_require_api_key(monkeypatch):
    calls = []

    def fake_run(slug, *, mode, args):
        calls.append((slug, args.dry_run))
        return DummyOutcome()

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(run_cli, "_run_single_deal", fake_run)
    _set_argv(monkeypatch, "--slug", "medivation", "--dry-run")

    assert run_cli.main() == 0
    assert calls == [("medivation", True)]


def test_reasoning_effort_args_pass_through_to_pool_config():
    args = run_cli._parser().parse_args([
        "--slug",
        "medivation",
        "--extract-reasoning-effort",
        "high",
        "--adjudicate-reasoning-effort",
        "xhigh",
    ])

    cfg = run_cli._make_pool_config(args, mode="extract")

    assert cfg.extract_reasoning_effort == "high"
    assert cfg.adjudicate_reasoning_effort == "xhigh"


def test_reasoning_effort_defaults_to_xhigh(monkeypatch):
    monkeypatch.delenv("EXTRACT_REASONING_EFFORT", raising=False)
    monkeypatch.delenv("ADJUDICATE_REASONING_EFFORT", raising=False)
    args = run_cli._parser().parse_args(["--slug", "medivation"])

    cfg = run_cli._make_pool_config(args, mode="extract")

    assert cfg.extract_reasoning_effort == "xhigh"
    assert cfg.adjudicate_reasoning_effort == "xhigh"


def test_commit_and_dry_run_is_rejected(monkeypatch, capsys):
    monkeypatch.setattr(run_cli, "_run_single_deal", lambda *a, **k: pytest.fail("run should not start"))
    _set_argv(monkeypatch, "--slug", "medivation", "--dry-run", "--commit")

    assert run_cli.main() == 2
    assert "--commit cannot be used with --dry-run" in capsys.readouterr().err


@pytest.mark.parametrize(
    "old_flag",
    ["--raw-" "extraction", "--print-extractor-" "prompt", "--max-tokens-" "per-deal"],
)
def test_old_flags_are_unrecognized(monkeypatch, old_flag, tmp_path, capsys):
    args = ["--slug", "medivation", old_flag]
    if old_flag == "--raw-" "extraction":
        args.append(str(tmp_path / "raw.json"))
    if old_flag == "--max-tokens-" "per-deal":
        args.append("200000")
    _set_argv(monkeypatch, *args)

    with pytest.raises(SystemExit) as exc:
        run_cli.main()

    assert exc.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err


def _prep_commit_result(env, slug="medivation"):
    """Create the minimum files commit_deal_outputs needs to exist."""
    output_path = env.extractions / f"{slug}.json"
    output_path.write_text("{}")
    env.flags.write_text("")
    audit_path = env.tmp_path / "output" / "audit" / slug
    audit_path.mkdir(parents=True)
    (audit_path / "manifest.json").write_text("{}")
    (audit_path / "raw_response.json").write_text("{}")
    return SimpleNamespace(
        status="passed_clean",
        flag_count=0,
        notes="",
        output_path=output_path,
        audit_path=audit_path,
    )


def test_commit_requires_sdk_audit_path(minimal_state_repo):
    env = minimal_state_repo
    output_path = env.extractions / "medivation.json"
    output_path.write_text("{}")
    result = SimpleNamespace(status="passed_clean", flag_count=0, notes="", output_path=output_path)

    with pytest.raises(ValueError, match="audit_path"):
        run_cli.commit_deal_outputs("medivation", result)


def test_commit_aborts_on_staged_drift(minimal_state_repo, git_repo):
    env = minimal_state_repo
    result = _prep_commit_result(env)

    env.extractions.joinpath("medivation.json").write_text('{"staged": true}')
    subprocess.run(
        ["git", "add", "--", "output/extractions/medivation.json"],
        cwd=git_repo, check=True,
    )
    env.extractions.joinpath("medivation.json").write_text('{"working_tree": true}')

    with pytest.raises(RuntimeError, match="staged content"):
        run_cli.commit_deal_outputs("medivation", result)


def test_commit_proceeds_when_no_staged_drift(minimal_state_repo, git_repo):
    env = minimal_state_repo
    env.progress.write_text("{}")
    result = _prep_commit_result(env)

    run_cli.commit_deal_outputs("medivation", result)

    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=git_repo, capture_output=True, text=True, check=True,
    ).stdout
    assert "deal=medivation" in log


def test_commit_ignores_unrelated_staged_files(minimal_state_repo, git_repo):
    env = minimal_state_repo
    env.progress.write_text("{}")
    result = _prep_commit_result(env)

    unrelated = env.tmp_path / "AGENTS.md"
    unrelated.write_text("unrelated change\n")
    subprocess.run(["git", "add", "--", "AGENTS.md"], cwd=git_repo, check=True)

    run_cli.commit_deal_outputs("medivation", result)

    files = subprocess.run(
        ["git", "show", "--name-only", "--pretty=", "HEAD"],
        cwd=git_repo, capture_output=True, text=True, check=True,
    ).stdout.strip().splitlines()
    assert "AGENTS.md" not in files
    assert any(f.startswith("output/extractions/") for f in files)
