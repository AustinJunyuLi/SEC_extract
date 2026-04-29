import asyncio
import json

import pytest

from pipeline import run_pool


def _cfg(**kwargs):
    base = run_pool.PoolConfig()
    for key, value in kwargs.items():
        setattr(base, key, value)
    return base


def test_selection_filters_and_explicit_slugs(minimal_state_repo):
    env = minimal_state_repo
    env.seed_deal("a", status="pending", is_reference=True)
    env.seed_deal("b", status="failed", is_reference=False)
    env.seed_deal("c", status="passed_clean", is_reference=True)
    state = json.loads(env.progress.read_text())

    assert run_pool.resolve_selection(_cfg(filter="pending"), state) == ["a"]
    assert run_pool.resolve_selection(_cfg(filter="failed"), state) == ["b"]
    assert run_pool.resolve_selection(_cfg(filter="reference"), state) == ["a", "c"]
    assert run_pool.resolve_selection(_cfg(slugs=("c", "a")), state) == ["c", "a"]


def test_reference_filter_selects_nine_reference_deals():
    selected = run_pool.resolve_selection(_cfg(filter="reference"))

    assert len(selected) == 9


def test_mutually_exclusive_args():
    parser = run_pool.build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--slugs", "a,b", "--filter", "pending"])


def test_force_alias_is_not_supported():
    parser = run_pool.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--filter", "reference", "--force"])


def test_per_deal_token_cap_is_not_supported():
    parser = run_pool.build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(["--filter", "reference", "--max-tokens-" "per-deal", "200000"])

    assert not hasattr(run_pool.PoolConfig(), "max_tokens_" "per_deal")


def test_reasoning_effort_defaults_to_high(monkeypatch):
    monkeypatch.delenv("EXTRACT_REASONING_EFFORT", raising=False)
    monkeypatch.delenv("ADJUDICATE_REASONING_EFFORT", raising=False)
    parser = run_pool.build_parser()

    cfg = run_pool.config_from_args(parser.parse_args(["--filter", "reference", "--dry-run"]))

    assert cfg.extract_reasoning_effort == "high"
    assert cfg.adjudicate_reasoning_effort == "high"
    assert run_pool.PoolConfig().extract_reasoning_effort == "high"
    assert run_pool.PoolConfig().adjudicate_reasoning_effort == "high"


def test_skip_decisions_and_cache_policy(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    cfg = _cfg(audit_root=env.tmp_path / "output" / "audit")
    current = "rules-v1"
    monkeypatch.setattr(run_pool, "extractor_contract_version", lambda: "contract-v1")
    contract = run_pool.extractor_contract_version()
    env.seed_deal("done", status="passed_clean", rulebook_version=current)
    env.seed_deal("stale", status="passed_clean", rulebook_version="old")
    env.seed_deal("failed", status="failed", rulebook_version=current)
    state = json.loads(env.progress.read_text())

    assert run_pool.decide_skip("done", cfg, current, state).action == "skip"
    assert run_pool.decide_skip("stale", cfg, current, state).action == "run"
    assert run_pool.decide_skip("failed", cfg, current, state).action == "run"
    assert run_pool.decide_skip("done", _cfg(re_extract=True, audit_root=cfg.audit_root), current, state).action == "run"

    audit = cfg.audit_root / "done"
    audit.mkdir(parents=True)
    (audit / "raw_response.json").write_text(json.dumps({
        "schema_version": "v1",
        "slug": "done",
        "rulebook_version": current,
        "extractor_contract_version": contract,
        "parsed_json": {"deal": {}, "events": []},
    }))
    assert run_pool.decide_skip("done", _cfg(re_validate=True, audit_root=cfg.audit_root), current, state).action == "re_validate"
    (audit / "raw_response.json").write_text(json.dumps({
        "schema_version": "v1",
        "slug": "done",
        "rulebook_version": "old",
        "extractor_contract_version": contract,
        "parsed_json": {"deal": {}, "events": []},
    }))
    assert run_pool.decide_skip("done", _cfg(re_validate=True, audit_root=cfg.audit_root), current, state).action == "blocked"
    (audit / "raw_response.json").write_text(json.dumps({
        "schema_version": "v1",
        "slug": "done",
        "rulebook_version": current,
        "extractor_contract_version": "old-contract",
        "parsed_json": {"deal": {}, "events": []},
    }))
    decision = run_pool.decide_skip("done", _cfg(re_validate=True, audit_root=cfg.audit_root), current, state)
    assert decision.action == "blocked"
    assert "extractor_contract_version" in decision.reason


@pytest.mark.parametrize(
    "payload",
    [
        {"schema_version": None},
        {"schema_version": "v0", "slug": "done", "rulebook_version": "rules-v1", "parsed_json": {"deal": {}, "events": []}},
        {"schema_version": "v1", "slug": "other", "rulebook_version": "rules-v1", "parsed_json": {"deal": {}, "events": []}},
        {"schema_version": "v1", "slug": "done", "rulebook_version": "rules-v1", "extractor_contract_version": None, "parsed_json": {"deal": {}, "events": []}},
        {"schema_version": "v1", "slug": "done", "rulebook_version": "rules-v1", "parsed_json": {"events": []}},
        {"schema_version": "v1", "slug": "done", "rulebook_version": "rules-v1", "parsed_json": {"deal": {}, "events": {}}},
    ],
)
def test_re_validate_rejects_stale_raw_response_shapes(minimal_state_repo, monkeypatch, payload):
    env = minimal_state_repo
    cfg = _cfg(re_validate=True, audit_root=env.tmp_path / "output" / "audit")
    env.seed_deal("done", status="passed_clean", rulebook_version="rules-v1")
    monkeypatch.setattr(run_pool, "extractor_contract_version", lambda: "contract-v1")
    audit = cfg.audit_root / "done"
    audit.mkdir(parents=True)
    payload = {
        "schema_version": "v1",
        "slug": "done",
        "rulebook_version": "rules-v1",
        "extractor_contract_version": run_pool.extractor_contract_version(),
        "parsed_json": {"deal": {}, "events": []},
        **payload,
    }
    (audit / "raw_response.json").write_text(json.dumps(payload))
    state = json.loads(env.progress.read_text())

    decision = run_pool.decide_skip("done", cfg, "rules-v1", state)

    assert decision.action == "blocked"
    assert "cached raw_response.json" in decision.reason


def test_dry_run_no_api_construction_probe_or_writes(minimal_state_repo, monkeypatch, capsys):
    env = minimal_state_repo
    env.seed_deal("a", status="pending")
    monkeypatch.setattr(run_pool.core, "rulebook_version", lambda: "rules-v1")
    monkeypatch.setattr(run_pool, "_build_client", lambda cfg: pytest.fail("client constructed"))
    monkeypatch.setattr(run_pool, "extract_deal", lambda *a, **k: pytest.fail("LLM called"))

    summary = asyncio.run(run_pool.run_pool(_cfg(filter="pending", dry_run=True, audit_root=env.tmp_path / "output" / "audit")))

    assert summary.selected == 1
    assert "DRY RUN selected deals" in capsys.readouterr().out
    assert not (env.tmp_path / "output" / "audit").exists()


def test_worker_limit_behavior(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    for slug in ("a", "b", "c"):
        env.seed_deal(slug, status="pending")
    monkeypatch.setattr(run_pool.core, "rulebook_version", lambda: "rules-v1")
    active = 0
    max_active = 0

    async def fake_process(slug, **kwargs):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        return run_pool.DealOutcome(slug=slug, status="passed_clean")

    monkeypatch.setattr(run_pool, "process_deal", fake_process)

    summary = asyncio.run(run_pool.run_pool(_cfg(filter="pending", workers=2), llm_client=object()))

    assert summary.succeeded == 3
    assert max_active == 2


def test_exceptions_are_summarized_without_cancelling_all(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    for slug in ("a", "b"):
        env.seed_deal(slug, status="pending")
    monkeypatch.setattr(run_pool.core, "rulebook_version", lambda: "rules-v1")

    async def fake_process(slug, **kwargs):
        if slug == "a":
            raise RuntimeError("boom")
        return run_pool.DealOutcome(slug=slug, status="passed_clean")

    monkeypatch.setattr(run_pool, "process_deal", fake_process)

    summary = asyncio.run(run_pool.run_pool(_cfg(filter="pending", workers=2), llm_client=object()))

    assert summary.failed == 1
    assert summary.succeeded == 1
    assert {outcome.slug for outcome in summary.outcomes} == {"a", "b"}


def test_xhigh_worker_count_is_capped_before_real_run(minimal_state_repo):
    env = minimal_state_repo
    env.seed_deal("a", status="pending")

    with pytest.raises(ValueError, match="xhigh.*workers.*5"):
        asyncio.run(
            run_pool.run_pool(
                _cfg(
                    filter="pending",
                    workers=6,
                    extract_reasoning_effort="xhigh",
                    dry_run=True,
                ),
                llm_client=object(),
            )
        )


def test_main_reports_xhigh_worker_cap_without_traceback(capsys):
    result = run_pool.main([
        "--filter",
        "reference",
        "--workers",
        "6",
        "--extract-reasoning-effort",
        "xhigh",
        "--dry-run",
    ])

    assert result == 2
    captured = capsys.readouterr()
    assert "workers <= 5" in captured.err
    assert "Traceback" not in captured.err


def test_failed_rerun_preserves_prior_success_state(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    env.seed_deal(
        "a",
        status="passed",
        flag_count=2,
        notes="hard=0 soft=2 info=0",
        rulebook_version="rules-v1",
        last_run="2026-04-28T10:00:00Z",
        last_run_id="run-good",
    )
    monkeypatch.setattr(run_pool.core, "rulebook_version", lambda: "rules-v1")

    async def fail_extract(*args, **kwargs):
        raise RuntimeError("provider cut stream")

    monkeypatch.setattr(run_pool, "extract_deal", fail_extract)

    summary = asyncio.run(
        run_pool.run_pool(
            _cfg(
                slugs=("a",),
                re_extract=True,
                audit_root=env.tmp_path / "output" / "audit",
            ),
            llm_client=object(),
        )
    )

    assert summary.failed == 1
    state = json.loads(env.progress.read_text())
    assert state["deals"]["a"]["status"] == "passed"
    assert state["deals"]["a"]["last_run_id"] == "run-good"


def test_fresh_run_starts_with_clean_call_log(minimal_state_repo):
    env = minimal_state_repo
    env.seed_deal("a", status="pending")
    audit_dir = env.tmp_path / "output" / "audit" / "a"
    audit_dir.mkdir(parents=True)
    (audit_dir / "calls.jsonl").write_text('{"old": true}\n')
    (audit_dir / "raw_response.json").write_text('{"old": true}\n')
    (audit_dir / "prompts").mkdir()
    (audit_dir / "prompts" / "extractor.txt").write_text("old prompt")

    audit = run_pool._build_audit_writer(
        env.tmp_path / "output" / "audit",
        "a",
        run_action="run",
    )

    assert audit.root == audit_dir
    assert not (audit_dir / "calls.jsonl").exists()
    assert not (audit_dir / "raw_response.json").exists()
    assert not (audit_dir / "prompts" / "extractor.txt").exists()


def test_re_validate_keeps_raw_response_cache(minimal_state_repo):
    env = minimal_state_repo
    audit_dir = env.tmp_path / "output" / "audit" / "a"
    audit_dir.mkdir(parents=True)
    raw_response = audit_dir / "raw_response.json"
    raw_response.write_text('{"keep": true}\n')

    run_pool._build_audit_writer(
        env.tmp_path / "output" / "audit",
        "a",
        run_action="re_validate",
    )

    assert raw_response.exists()


def test_soft_flags_routes_only_semantic_adjudication_codes():
    result = run_pool.core.ValidatorResult(
        row_flags=[
            {
                "row_index": 0,
                "code": "missing_nda_dropsilent",
                "severity": "soft",
                "reason": "semantic absence check",
            },
            {
                "row_index": 1,
                "code": "resolved_name_not_observed",
                "severity": "soft",
                "reason": "registry hygiene",
            },
            {
                "row_index": 2,
                "code": "formal_round_status_inconsistent",
                "severity": "soft",
                "reason": "deterministic row-scope issue",
            },
        ],
        deal_flags=[
            {
                "code": "deal_level_soft",
                "severity": "soft",
                "reason": "not allow-listed",
                "deal_level": True,
            }
        ],
    )

    routed = run_pool._soft_flags(result)

    assert [flag["code"] for flag in routed] == ["missing_nda_dropsilent"]
