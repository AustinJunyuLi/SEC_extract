import json

import pytest

import pipeline.core as pipeline


# ---------------------------------------------------------------------------
# package layout
# ---------------------------------------------------------------------------


def test_pipeline_package_reexports_core_api():
    import pipeline as pipeline_pkg

    assert pipeline_pkg.load_filing is pipeline.load_filing
    assert pipeline_pkg.rulebook_version is pipeline.rulebook_version
    assert not hasattr(pipeline_pkg, "_invariant_p_r0")
    assert not hasattr(pipeline_pkg, "finalize")
    assert hasattr(pipeline, "_PROCESS_STATE_LOCK")


# ---------------------------------------------------------------------------
# rulebook_version()
# ---------------------------------------------------------------------------


def test_rulebook_version_changes_with_rule_content(tmp_path, monkeypatch):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    rule = rules_dir / "schema.md"
    rule.write_text("one\n")
    monkeypatch.setattr(pipeline, "RULES_DIR", rules_dir)

    first = pipeline.rulebook_version()
    rule.write_text("two\n")
    second = pipeline.rulebook_version()

    assert first != second
    assert len(first) == 64
    assert len(second) == 64


def test_rulebook_version_empty_rules_dir_raises(tmp_path, monkeypatch):
    """Fail-loud contract: rulebook_version() on an empty rules/ is NOT a soft
    fallback. `mark_failed` wraps this with "unavailable"; everyone else must
    see the raw error."""
    empty = tmp_path / "empty_rules"
    empty.mkdir()
    monkeypatch.setattr(pipeline, "RULES_DIR", empty)
    with pytest.raises(FileNotFoundError, match="no rule files"):
        pipeline.rulebook_version()


# ---------------------------------------------------------------------------
# update_progress()
# ---------------------------------------------------------------------------


def test_update_progress_records_per_deal_rulebook_version(minimal_state_repo):
    """Post plan §1.2: top-level `state["rulebook_version"]` is gone; only the
    per-deal record + history survive."""
    env = minimal_state_repo
    env.seed_deal("synthetic")
    pipeline.update_progress(
        "synthetic",
        status="passed_clean",
        flag_count=0,
        notes="clean",
        current_rulebook_version="abc123",
        last_run="2026-04-24T12:00:00Z",
        run_id="run-abc",
    )
    state = json.loads(env.progress.read_text())
    assert "rulebook_version" not in state, (
        "top-level rulebook_version must not be written — races on concurrent finalizes"
    )
    deal = state["deals"]["synthetic"]
    assert deal["rulebook_version"] == "abc123"
    assert deal["last_run"] == "2026-04-24T12:00:00Z"
    assert deal["last_run_id"] == "run-abc"
    assert deal["rulebook_version_history"] == [
        {"ts": "2026-04-24T12:00:00Z", "run_id": "run-abc", "version": "abc123"},
    ]


def test_update_progress_rejects_stale_top_level_rulebook_version(minimal_state_repo):
    """No compatibility cleanup: stale progress state fails loudly."""
    env = minimal_state_repo
    prog = json.loads(env.progress.read_text())
    prog["rulebook_version"] = "stale_hash_from_prior_schema"
    env.progress.write_text(json.dumps(prog, indent=2))
    env.seed_deal("synthetic")
    with pytest.raises(ValueError, match="stale top-level rulebook_version"):
        pipeline.update_progress(
            "synthetic",
            status="passed_clean",
            flag_count=0,
            notes="",
            current_rulebook_version="new_hash",
            last_run="2026-04-24T12:00:00Z",
            run_id="run-stale",
        )


def test_update_progress_auto_creates_missing_slug(minimal_state_repo):
    """`mark_failed` needs to record even when the slug was never seeded.
    That's done by update_progress creating a minimal entry rather than
    raising KeyError."""
    env = minimal_state_repo
    pipeline.update_progress(
        "mystery",
        status="failed_system",
        flag_count=0,
        notes="brand new slug",
        current_rulebook_version="r1",
        last_run="2026-04-24T12:00:00Z",
        run_id="run-mystery",
    )
    state = json.loads(env.progress.read_text())
    assert "mystery" in state["deals"]
    entry = state["deals"]["mystery"]
    assert entry["status"] == "failed_system"
    assert entry["rulebook_version"] == "r1"
    assert entry["notes"] == "brand new slug"


def test_update_progress_history_caps_at_10(minimal_state_repo):
    env = minimal_state_repo
    env.seed_deal("synthetic")
    for i in range(12):
        pipeline.update_progress(
            "synthetic",
            status="passed_clean",
            flag_count=0,
            notes="",
            current_rulebook_version=f"hash_{i:02d}",
            last_run=f"2026-04-24T12:{i:02d}:00Z",
            run_id=f"run-{i:02d}",
        )
    state = json.loads(env.progress.read_text())
    history = state["deals"]["synthetic"]["rulebook_version_history"]
    assert len(history) == pipeline.RULEBOOK_HISTORY_CAP
    # Cap keeps the most recent entries.
    assert history[0]["version"] == "hash_02"
    assert history[-1]["version"] == "hash_11"


def test_update_progress_raises_when_progress_missing(tmp_path, monkeypatch):
    """Missing progress.json is a genuine setup error, not an auto-repair
    case. Fail loudly."""
    monkeypatch.setattr(pipeline, "PROGRESS_PATH", tmp_path / "nonexistent.json")
    with pytest.raises(FileNotFoundError):
        pipeline.update_progress(
            "x",
            status="passed_clean",
            flag_count=0,
            notes="",
            current_rulebook_version="r",
            last_run="2026-04-24T12:00:00Z",
            run_id="run-missing",
        )


# ---------------------------------------------------------------------------
# mark_failed()
# ---------------------------------------------------------------------------


def test_mark_failed_records_failed_status(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    env.seed_deal("synthetic")
    monkeypatch.setattr(pipeline, "rulebook_version", lambda: "rules-v1")

    pipeline.mark_failed("synthetic", "missing_filing_artifacts: pages.json")

    state = json.loads(env.progress.read_text())
    deal = state["deals"]["synthetic"]
    assert deal["status"] == "failed_system"
    assert deal["flag_count"] == 0
    assert deal["notes"] == "missing_filing_artifacts: pages.json"
    assert deal["rulebook_version"] == "rules-v1"


def test_mark_failed_brand_new_slug(minimal_state_repo):
    """Slug not in seeds → mark_failed must still record, not crash."""
    env = minimal_state_repo
    pipeline.mark_failed("ghost", "slug was never seeded")
    state = json.loads(env.progress.read_text())
    assert state["deals"]["ghost"]["status"] == "failed_system"
    assert state["deals"]["ghost"]["notes"] == "slug was never seeded"


def test_mark_failed_empty_rules_dir_records_unavailable(minimal_state_repo):
    """Empty rules/ → mark_failed uses rulebook_version='unavailable'
    rather than propagating FileNotFoundError up. The failure is still
    recorded; the rulebook just can't be pinned."""
    env = minimal_state_repo
    env.seed_deal("synthetic")
    env.empty_rules()
    pipeline.mark_failed("synthetic", "failed before rules were set up")
    state = json.loads(env.progress.read_text())
    entry = state["deals"]["synthetic"]
    assert entry["status"] == "failed_system"
    assert entry["rulebook_version"] == "unavailable"


def test_mark_failed_missing_progress_json_raises(tmp_path, monkeypatch):
    """Missing progress.json is a genuine environment error — mark_failed
    must propagate it so the CLI can surface exit code 2."""
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "schema.md").write_text("stub\n")
    monkeypatch.setattr(pipeline, "RULES_DIR", rules)
    monkeypatch.setattr(pipeline, "PROGRESS_PATH", tmp_path / "missing.json")
    with pytest.raises(FileNotFoundError):
        pipeline.mark_failed("ghost", "recorder must fail loudly here")


def test_mark_failed_empty_notes_raises(minimal_state_repo):
    """Empty notes should fail loudly — a failure record with nothing to
    say is worse than no record."""
    env = minimal_state_repo
    env.seed_deal("synthetic")
    with pytest.raises(ValueError, match="non-empty"):
        pipeline.mark_failed("synthetic", "   ")


# ---------------------------------------------------------------------------
# append_flags_log() — run_ts propagation
# ---------------------------------------------------------------------------


def test_append_flags_log_uses_provided_run_ts_and_run_id(minimal_state_repo):
    """Every line's logged_at is the caller-provided run_ts AND every line
    carries the same run_id — no per-line `datetime.now()`, no per-line UUID.
    The (deal, run_id) pair is the audit primary key for the rulebook-stability
    gate."""
    env = minimal_state_repo
    final = {
        "deal": {"deal_flags": [{"code": "x", "severity": "info"}]},
    }
    count = pipeline.append_flags_log(
        "synthetic", final,
        run_ts="2026-04-24T12:00:00Z",
        run_id="run-flag-test",
    )
    assert count == 1
    lines = [json.loads(line) for line in env.flags.read_text().splitlines()]
    assert all(line["logged_at"] == "2026-04-24T12:00:00Z" for line in lines)
    assert all(line["run_id"] == "run-flag-test" for line in lines)


def test_append_flags_log_does_not_interleave_under_concurrent_writers(minimal_state_repo):
    """Two concurrent appenders must produce well-formed JSONL, never
    half-merged lines. The advisory flock around the per-line writes is what
    guarantees this; without it, two finalize() calls in parallel would
    interleave bytes once the buffered write exceeded PIPE_BUF."""
    import threading

    env = minimal_state_repo
    # Build two payloads with enough flags that the combined append is
    # well over PIPE_BUF (4 KiB) even line-by-line.
    def build_final(prefix: str) -> dict:
        return {
            "deal": {
                "deal_flags": [{
                    "code": f"{prefix}_code_{i}",
                    "severity": "info",
                    "reason": "x" * 200,
                } for i in range(60)]
            },
        }

    finals = [
        ("alpha", build_final("alpha"), "run-alpha"),
        ("beta", build_final("beta"), "run-beta"),
    ]

    def write(slug, final, run_id):
        pipeline.append_flags_log(slug, final, run_ts="2026-04-24T12:00:00Z", run_id=run_id)

    threads = [threading.Thread(target=write, args=args) for args in finals]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    text = env.flags.read_text()
    assert text.endswith("\n"), "every line must terminate with newline"
    lines = text.splitlines()
    parsed = [json.loads(line) for line in lines]
    counts = {"run-alpha": 0, "run-beta": 0}
    for line in parsed:
        counts[line["run_id"]] += 1
    assert counts == {"run-alpha": 60, "run-beta": 60}


def test_count_flags_uses_deal_graph_flags_once():
    flag = {"code": "source_missing", "severity": "hard"}
    final = {
        "deal": {"deal_flags": [flag]},
        "graph": {"validation_flags": [flag]},
    }

    assert pipeline.count_flags(final) == {"hard": 1, "soft": 0, "info": 0}
