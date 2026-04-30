import json

import pytest

import pipeline as pipeline_pkg
import pipeline.core as pipeline


def _current_deal(**overrides):
    deal = {
        "TargetName": "Synthetic Target",
        "Acquirer": "Synthetic Buyer",
        "DateAnnounced": "2026-04-24",
        "DateEffective": None,
        "auction": False,
        "all_cash": True,
        "target_legal_counsel": None,
        "acquirer_legal_counsel": None,
        "bidder_registry": {},
        "deal_flags": [],
    }
    deal.update(overrides)
    return deal


# ---------------------------------------------------------------------------
# package layout
# ---------------------------------------------------------------------------


def test_pipeline_package_reexports_core_api():
    assert pipeline_pkg.load_filing is pipeline.load_filing
    assert pipeline_pkg.rulebook_version is pipeline.rulebook_version
    assert not hasattr(pipeline_pkg, "_invariant_p_r0")
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
        status="failed",
        flag_count=0,
        notes="brand new slug",
        current_rulebook_version="r1",
        last_run="2026-04-24T12:00:00Z",
        run_id="run-mystery",
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


def test_append_flags_log_uses_provided_run_ts_and_run_id(minimal_state_repo):
    """Every line's logged_at is the caller-provided run_ts AND every line
    carries the same run_id — no per-line `datetime.now()`, no per-line UUID.
    The (deal, run_id) pair is the audit primary key for the rulebook-stability
    gate."""
    env = minimal_state_repo
    final = {
        "deal": {"deal_flags": [{"code": "x", "severity": "info"}]},
        "events": [
            {"flags": [{"code": "y", "severity": "soft"}]},
            {"flags": []},
        ],
    }
    count = pipeline.append_flags_log(
        "synthetic", final,
        run_ts="2026-04-24T12:00:00Z",
        run_id="run-flag-test",
    )
    assert count == 2
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
            "deal": {"deal_flags": []},
            "events": [
                {"flags": [{
                    "code": f"{prefix}_code_{i}",
                    "severity": "info",
                    "reason": "x" * 200,
                }]} for i in range(60)
            ],
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
    # Minimal live-contract extraction: one Executed row so §P-S4 passes
    # and §P-S3 has a phase-1 terminator.
    raw = {
        "deal": _current_deal(),
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
        "deal": _current_deal(),
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
    # Both runs same rulebook → two entries, same hash, distinct run_ids.
    assert len(history) == 2
    assert history[0]["version"] == history[1]["version"]
    assert history[0]["run_id"] != history[1]["run_id"]


def test_finalize_extraction_output_is_byte_idempotent_modulo_run_stamps(minimal_state_repo):
    """Identical input must produce identical extraction JSON across reruns
    modulo per-run stamps (last_run, last_run_id). Otherwise the
    "3 consecutive unchanged-rulebook clean runs" gate is meaningless.
    """
    env = minimal_state_repo
    env.seed_deal("synthetic", is_reference=True)
    env.seed_filing(
        "synthetic",
        pages=[{"number": 1, "content": "the target entered a merger agreement on 2026-04-24"}],
    )

    def fresh_raw():
        return {
            "deal": _current_deal(),
            "events": [{
                "BidderID": 1,
                "bid_note": "Executed",
                "bid_date_precise": "2026-04-24",
                "bid_date_rough": None,
                "bidder_name": None,
                "bidder_alias": None,
                "process_phase": 1,
                "source_quote": "the target entered a merger agreement on 2026-04-24",
                "source_page": 1,
            }],
        }

    pipeline.finalize("synthetic", fresh_raw())
    out1 = json.loads(env.extractions.joinpath("synthetic.json").read_text())
    pipeline.finalize("synthetic", fresh_raw())
    out2 = json.loads(env.extractions.joinpath("synthetic.json").read_text())

    # Strip per-run stamps before comparing.
    for o in (out1, out2):
        o["deal"].pop("last_run", None)
        o["deal"].pop("last_run_id", None)
    assert out1 == out2, (
        "extraction output must be byte-identical across reruns on identical "
        "input modulo per-run stamps; mismatch indicates non-determinism in "
        "the validator or pre-validation ordering"
    )

    # Flag set per run must also be identical (modulo per-line run_id/logged_at).
    # If the deal passes clean, flags.jsonl never gets written — skip that
    # half of the assertion. The extraction-JSON parity above is enough.
    if env.flags.exists():
        lines = [json.loads(l) for l in env.flags.read_text().splitlines()]
        by_run: dict[str, list[dict]] = {}
        for line in lines:
            by_run.setdefault(line["run_id"], []).append(
                {k: v for k, v in line.items() if k not in {"run_id", "logged_at", "deal"}}
            )
        if by_run:
            run_ids = list(by_run.keys())
            assert len(run_ids) == 2
            assert by_run[run_ids[0]] == by_run[run_ids[1]]


# ---------------------------------------------------------------------------
# Existing test preserved (unrelated: promotion + canonicalize)
# ---------------------------------------------------------------------------


def test_prepare_for_validate_applies_failed_promotion_flag_and_canonicalizes():
    raw = {
        "deal": _current_deal(bidder_registry={}),
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
                        "promote_to_bidder_name": "bidder_98",
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
    assert "unnamed_nda_promotion" not in prepared["events"][1]


def test_prepare_for_validate_rebuilds_empty_bidder_registry_from_events():
    raw = {
        "deal": _current_deal(bidder_registry={}),
        "events": [
            {
                "BidderID": 2,
                "bid_note": "Bid",
                "bidder_name": "bidder_01",
                "bidder_alias": "Party A",
                "bid_date_precise": "2020-02-01",
            },
            {
                "BidderID": 1,
                "bid_note": "NDA",
                "bidder_name": "bidder_01",
                "bidder_alias": "Acquirer",
                "bid_date_precise": "2020-01-01",
            },
        ],
    }
    filing = pipeline.Filing(slug="synthetic", pages=[{"number": 1, "content": ""}])

    prepared, _, _ = pipeline.prepare_for_validate("synthetic", raw, filing=filing)

    registry = prepared["deal"]["bidder_registry"]
    assert registry["bidder_01"]["aliases_observed"] == ["Party A", "Acquirer"]
    assert registry["bidder_01"]["resolved_name"] is None
    assert registry["bidder_01"]["first_appearance_row_index"] == 1


def test_prepare_for_validate_rejects_extra_deal_fields():
    raw = {
        "deal": _current_deal(FormType="DEFM14A"),
        "events": [],
    }
    filing = pipeline.Filing(slug="synthetic", pages=[])

    with pytest.raises(ValueError, match="unexpected current AI-produced field"):
        pipeline.prepare_for_validate("synthetic", raw, filing=filing)


def test_successful_unnamed_nda_promotion_leaves_visible_flag(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    env.seed_deal("synthetic")
    env.seed_filing(
        "synthetic",
        pages=[{
            "number": 1,
            "content": (
                "Strategic 1 executed a confidentiality agreement. "
                "Party E submitted a preliminary indication of interest. "
                "The parties executed the merger agreement."
            ),
        }],
    )
    monkeypatch.setattr(pipeline, "rulebook_version", lambda: "rules-v1")
    raw = {
        "deal": _current_deal(
            bidder_registry={
                "bidder_01": {
                    "resolved_name": "Party E",
                    "aliases_observed": ["Party E"],
                    "first_appearance_row_index": 2,
                }
            }
        ),
        "events": [
            {
                "BidderID": 1,
                "process_phase": 1,
                "role": "bidder",
                "exclusivity_days": None,
                "bidder_name": None,
                "bidder_alias": "Strategic 1",
                "bidder_type": "s",
                "bid_note": "NDA",
                "bid_type": None,
                "bid_type_inference_note": None,
                "drop_initiator": None,
                "drop_reason_class": None,
                "final_round_announcement": None,
                "final_round_extension": None,
                "final_round_informal": None,
                "press_release_subject": None,
                "invited_to_formal_round": None,
                "submitted_formal_bid": None,
                "bid_date_precise": "2020-01-01",
                "bid_date_rough": None,
                "bid_value": None,
                "bid_value_pershare": None,
                "bid_value_lower": None,
                "bid_value_upper": None,
                "bid_value_unit": None,
                "consideration_components": None,
                "additional_note": None,
                "comments": None,
                "source_quote": "Strategic 1 executed a confidentiality agreement.",
                "source_page": 1,
                "flags": [],
            },
            {
                "BidderID": 2,
                "process_phase": 1,
                "role": "bidder",
                "exclusivity_days": None,
                "bidder_name": "bidder_01",
                "bidder_alias": "Party E",
                "bidder_type": "s",
                "bid_note": "Bid",
                "bid_type": "informal",
                "bid_type_inference_note": "preliminary indication of interest before formal round",
                "drop_initiator": None,
                "drop_reason_class": None,
                "final_round_announcement": None,
                "final_round_extension": None,
                "final_round_informal": None,
                "press_release_subject": None,
                "invited_to_formal_round": None,
                "submitted_formal_bid": None,
                "bid_date_precise": "2020-01-02",
                "bid_date_rough": None,
                "bid_value": None,
                "bid_value_pershare": None,
                "bid_value_lower": None,
                "bid_value_upper": None,
                "bid_value_unit": None,
                "consideration_components": None,
                "additional_note": None,
                "comments": None,
                "unnamed_nda_promotion": {
                    "target_bidder_id": 1,
                    "promote_to_bidder_alias": "Party E",
                    "promote_to_bidder_name": "bidder_01",
                    "reason": "Party E is the later named Strategic 1 placeholder.",
                },
                "source_quote": "Party E submitted a preliminary indication of interest.",
                "source_page": 1,
                "flags": [],
            },
            {
                "BidderID": 3,
                "process_phase": 1,
                "role": "bidder",
                "exclusivity_days": None,
                "bidder_name": "bidder_01",
                "bidder_alias": "Party E",
                "bidder_type": "s",
                "bid_note": "Executed",
                "bid_type": None,
                "bid_type_inference_note": None,
                "drop_initiator": None,
                "drop_reason_class": None,
                "final_round_announcement": None,
                "final_round_extension": None,
                "final_round_informal": None,
                "press_release_subject": None,
                "invited_to_formal_round": None,
                "submitted_formal_bid": None,
                "bid_date_precise": "2020-01-03",
                "bid_date_rough": None,
                "bid_value": None,
                "bid_value_pershare": None,
                "bid_value_lower": None,
                "bid_value_upper": None,
                "bid_value_unit": None,
                "consideration_components": None,
                "additional_note": None,
                "comments": None,
                "source_quote": "The parties executed the merger agreement.",
                "source_page": 1,
                "flags": [],
            },
        ],
    }
    filing = pipeline.load_filing("synthetic")
    prepared, _, promotion_log = pipeline.prepare_for_validate("synthetic", raw, filing=filing)
    validation = pipeline.validate(prepared, filing)

    pipeline.finalize_prepared("synthetic", prepared, filing, validation, promotion_log)
    final = json.loads(env.extractions.joinpath("synthetic.json").read_text())

    assert "_unnamed_nda_promotions" not in final["deal"]
    promoted_nda = final["events"][0]
    assert promoted_nda["bidder_name"] == "bidder_01"
    assert promoted_nda["bidder_alias"] == "Party E"
    assert any(flag["code"] == "nda_promoted_from_placeholder" for flag in promoted_nda["flags"])
    assert "unnamed_nda_promotion" not in final["events"][1]
