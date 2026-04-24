import json

import pytest

import pipeline


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
    )
    state = json.loads(env.progress.read_text())
    assert "rulebook_version" not in state, (
        "top-level rulebook_version must not be written — races on concurrent finalizes"
    )
    deal = state["deals"]["synthetic"]
    assert deal["rulebook_version"] == "abc123"
    assert deal["last_run"] == "2026-04-24T12:00:00Z"
    assert deal["rulebook_version_history"] == [
        {"ts": "2026-04-24T12:00:00Z", "version": "abc123"},
    ]


def test_update_progress_drops_legacy_top_level_rulebook_version(minimal_state_repo):
    """A progress.json from an older pipeline still carries state["rulebook_version"].
    The new code must drop it on the next write, not preserve it."""
    env = minimal_state_repo
    prog = json.loads(env.progress.read_text())
    prog["rulebook_version"] = "legacy_hash_from_old_pipeline"
    env.progress.write_text(json.dumps(prog, indent=2))
    env.seed_deal("synthetic")
    pipeline.update_progress(
        "synthetic",
        status="passed_clean",
        flag_count=0,
        notes="",
        current_rulebook_version="new_hash",
        last_run="2026-04-24T12:00:00Z",
    )
    state = json.loads(env.progress.read_text())
    assert "rulebook_version" not in state


def test_update_progress_auto_creates_missing_slug(minimal_state_repo):
    """`mark_failed` needs to record even when the slug was never seeded.
    That's done by update_progress creating a minimal entry rather than
    raising KeyError."""
    env = minimal_state_repo
    pipeline.update_progress(
        "mystery",
        status="failed",
        flag_count=0,
        notes="brand new slug",
        current_rulebook_version="r1",
        last_run="2026-04-24T12:00:00Z",
    )
    state = json.loads(env.progress.read_text())
    assert "mystery" in state["deals"]
    entry = state["deals"]["mystery"]
    assert entry["status"] == "failed"
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
    assert deal["status"] == "failed"
    assert deal["flag_count"] == 0
    assert deal["notes"] == "missing_filing_artifacts: pages.json"
    assert deal["rulebook_version"] == "rules-v1"


def test_mark_failed_brand_new_slug(minimal_state_repo):
    """Slug not in seeds → mark_failed must still record, not crash."""
    env = minimal_state_repo
    pipeline.mark_failed("ghost", "slug was never seeded")
    state = json.loads(env.progress.read_text())
    assert state["deals"]["ghost"]["status"] == "failed"
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
    assert entry["status"] == "failed"
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


def test_append_flags_log_uses_provided_run_ts(minimal_state_repo):
    """Every line's logged_at is the caller-provided run_ts — no per-line
    `datetime.now()`. This is what makes `logged_at == last_run` a clean query."""
    env = minimal_state_repo
    final = {
        "deal": {"deal_flags": [{"code": "x", "severity": "info"}]},
        "events": [
            {"flags": [{"code": "y", "severity": "soft"}]},
            {"flags": []},
        ],
    }
    count = pipeline.append_flags_log("synthetic", final, run_ts="2026-04-24T12:00:00Z")
    assert count == 2
    lines = [json.loads(line) for line in env.flags.read_text().splitlines()]
    assert all(line["logged_at"] == "2026-04-24T12:00:00Z" for line in lines)


# ---------------------------------------------------------------------------
# finalize() — end-to-end parity of timestamps
# ---------------------------------------------------------------------------


def test_finalize_stamps_deal_last_run_and_single_run_ts(minimal_state_repo):
    """End-to-end check: finalize() captures one run_ts and uses it for
    deal.last_run (output JSON), progress.last_run, and every flag's
    logged_at. Query `logged_at == last_run` returns exactly this run's
    flags."""
    env = minimal_state_repo
    env.seed_deal("synthetic", is_reference=True)
    env.seed_filing(
        "synthetic",
        pages=[{"number": 1, "content": "the target entered a merger agreement on 2026-04-24"}],
    )
    # Minimal schema-conformant extraction: one Executed row so §P-S4 passes
    # and §P-S3 has a phase-1 terminator.
    raw = {
        "deal": {
            "slug": "synthetic",
            "auction": False,
            "bidder_registry": {},
        },
        "events": [
            {
                "BidderID": 1,
                "bid_note": "Executed",
                "bid_date_precise": "2026-04-24",
                "bid_date_rough": None,
                "bidder_name": None,
                "bidder_alias": None,
                "process_phase": 1,
                "source_quote": "the target entered a merger agreement on 2026-04-24",
                "source_page": 1,
            },
        ],
    }
    result = pipeline.finalize("synthetic", raw)
    assert result.status in {"passed", "passed_clean", "validated"}

    # deal.last_run on output.
    out = json.loads(env.extractions.joinpath("synthetic.json").read_text())
    last_run_output = out["deal"]["last_run"]
    assert last_run_output is not None and last_run_output.endswith("Z")

    # progress.last_run.
    state = json.loads(env.progress.read_text())
    last_run_state = state["deals"]["synthetic"]["last_run"]
    assert last_run_output == last_run_state

    # Every flags.jsonl line (if any) has logged_at == last_run.
    if env.flags.exists():
        for line in env.flags.read_text().splitlines():
            entry = json.loads(line)
            assert entry["logged_at"] == last_run_output


def test_finalize_appends_to_rulebook_version_history(minimal_state_repo):
    env = minimal_state_repo
    env.seed_deal("synthetic", is_reference=True)
    env.seed_filing(
        "synthetic",
        pages=[{"number": 1, "content": "transaction closed"}],
    )
    raw = {
        "deal": {"slug": "synthetic", "auction": False, "bidder_registry": {}},
        "events": [{
            "BidderID": 1,
            "bid_note": "Executed",
            "bid_date_precise": "2026-04-24",
            "bid_date_rough": None,
            "bidder_name": None,
            "bidder_alias": None,
            "process_phase": 1,
            "source_quote": "transaction closed",
            "source_page": 1,
        }],
    }
    pipeline.finalize("synthetic", raw)
    pipeline.finalize("synthetic", raw)

    state = json.loads(env.progress.read_text())
    history = state["deals"]["synthetic"]["rulebook_version_history"]
    # Both runs same rulebook → two entries, same hash.
    assert len(history) == 2
    assert history[0]["version"] == history[1]["version"]


# ---------------------------------------------------------------------------
# Existing test preserved (unrelated: promotion + canonicalize)
# ---------------------------------------------------------------------------


def test_prepare_for_validate_applies_failed_promotion_flag_and_canonicalizes():
    raw = {
        "deal": {
            "bidder_registry": {},
        },
        "events": [
            {
                "BidderID": 2,
                "bid_note": "NDA",
                "bidder_name": None,
                "bidder_alias": "Strategic 5",
                "bid_date_precise": "2020-01-01",
            },
            {
                "BidderID": 1,
                "bid_note": "Bid",
                "bidder_name": "bidder_99",
                "bidder_alias": "Party E",
                "bid_date_precise": "2020-02-01",
                "unnamed_nda_promotion": {
                    "target_bidder_id": 2,
                    "promote_to_bidder_alias": "Party E",
                    "promote_to_bidder_name": "bidder_99",
                    "reason": "synthetic",
                },
            },
        ],
    }
    filing = pipeline.Filing(slug="synthetic", pages=[{"number": 1, "content": ""}])

    prepared, _, promotion_log = pipeline.prepare_for_validate(
        "synthetic",
        raw,
        filing=filing,
    )

    assert promotion_log[0]["status"] == "failed"
    assert prepared["events"][0]["BidderID"] == 1
    assert prepared["events"][1]["BidderID"] == 2
    assert prepared["events"][1]["flags"][0]["code"] == "nda_promotion_failed"
