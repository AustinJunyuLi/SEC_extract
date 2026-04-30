import asyncio
import json

import pytest

from pipeline import run_pool
from pipeline.llm.client import CompletionResult
from pipeline.llm.extract import ExtractResult


def _cfg(**kwargs):
    base = run_pool.PoolConfig()
    for key, value in kwargs.items():
        setattr(base, key, value)
    return base


def _write_audit_manifest(
    run_dir,
    *,
    slug: str,
    run_id: str,
    outcome: str = "passed_clean",
    cache_eligible: bool = True,
):
    (run_dir / "manifest.json").write_text(json.dumps({
        "schema_version": "audit_run_v2",
        "slug": slug,
        "run_id": run_id,
        "outcome": outcome,
        "cache_eligible": cache_eligible,
        "rulebook_version": "rules-v1",
        "extractor_contract_version": run_pool.extractor_contract_version(),
        "tools_contract_version": run_pool.tools_contract_version(),
        "repair_loop_contract_version": run_pool.repair_loop_contract_version(),
        "extract_tool_mode": run_pool.EXTRACT_TOOL_MODE,
        "repair_strategy": run_pool.REPAIR_STRATEGY,
    }))


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


def test_validated_is_not_a_done_or_success_status():
    assert "validated" not in run_pool.DONE_STATUSES
    summary = run_pool.PoolSummary([
        run_pool.DealOutcome(slug="hard-flagged", status="validated"),
        run_pool.DealOutcome(slug="clean", status="passed_clean"),
    ])

    assert summary.succeeded == 1


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


def test_reasoning_effort_defaults_to_xhigh(monkeypatch):
    monkeypatch.delenv("EXTRACT_REASONING_EFFORT", raising=False)
    monkeypatch.delenv("ADJUDICATE_REASONING_EFFORT", raising=False)
    parser = run_pool.build_parser()

    cfg = run_pool.config_from_args(parser.parse_args(["--filter", "reference", "--dry-run"]))

    assert cfg.extract_reasoning_effort == "xhigh"
    assert cfg.adjudicate_reasoning_effort == "xhigh"
    assert run_pool.PoolConfig().extract_reasoning_effort == "xhigh"
    assert run_pool.PoolConfig().adjudicate_reasoning_effort == "xhigh"


def test_skip_decisions_and_cache_policy(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    cfg = _cfg(audit_root=env.tmp_path / "output" / "audit")
    current = "rules-v1"
    monkeypatch.setattr(run_pool, "extractor_contract_version", lambda: "contract-v1")
    contract = run_pool.extractor_contract_version()
    env.seed_deal("done", status="passed_clean", rulebook_version=current)
    env.seed_deal("hard_flagged", status="validated", rulebook_version=current)
    env.seed_deal("stale", status="passed_clean", rulebook_version="old")
    env.seed_deal("failed", status="failed", rulebook_version=current)
    state = json.loads(env.progress.read_text())

    assert run_pool.decide_skip("done", cfg, current, state).action == "skip"
    assert run_pool.decide_skip("hard_flagged", cfg, current, state).action == "run"
    assert run_pool.decide_skip("stale", cfg, current, state).action == "run"
    assert run_pool.decide_skip("failed", cfg, current, state).action == "run"
    assert run_pool.decide_skip("done", _cfg(re_extract=True, audit_root=cfg.audit_root), current, state).action == "run"

    run_id = "run-valid"
    audit = cfg.audit_root / "done" / "runs" / run_id
    audit.mkdir(parents=True)
    _write_audit_manifest(audit, slug="done", run_id=run_id)
    (audit / "raw_response.json").write_text(json.dumps({
        "schema_version": "raw_response_v2",
        "run_id": run_id,
        "slug": "done",
        "rulebook_version": current,
        "extractor_contract_version": contract,
        "parsed_json": {"deal": {}, "events": []},
    }))
    (cfg.audit_root / "done" / "latest.json").write_text(json.dumps({
        "schema_version": "audit_v2",
        "slug": "done",
        "run_id": run_id,
        "outcome": "passed_clean",
        "cache_eligible": True,
        "manifest_path": f"runs/{run_id}/manifest.json",
        "raw_response_path": f"runs/{run_id}/raw_response.json",
    }))
    assert run_pool.decide_skip("done", _cfg(re_validate=True, audit_root=cfg.audit_root), current, state).action == "re_validate"
    manifest = json.loads((audit / "manifest.json").read_text())
    valid_manifest = dict(manifest)
    manifest["repair_strategy"] = "prompt_then_filing_tools"
    (audit / "manifest.json").write_text(json.dumps(manifest))
    decision = run_pool.decide_skip("done", _cfg(re_validate=True, audit_root=cfg.audit_root), current, state)
    assert decision.action == "blocked"
    assert "repair_strategy" in decision.reason
    (audit / "manifest.json").write_text(json.dumps(valid_manifest))

    (audit / "raw_response.json").write_text(json.dumps({
        "schema_version": "raw_response_v2",
        "run_id": run_id,
        "slug": "done",
        "rulebook_version": "old",
        "extractor_contract_version": contract,
        "parsed_json": {"deal": {}, "events": []},
    }))
    assert run_pool.decide_skip("done", _cfg(re_validate=True, audit_root=cfg.audit_root), current, state).action == "blocked"
    (audit / "raw_response.json").write_text(json.dumps({
        "schema_version": "raw_response_v2",
        "run_id": run_id,
        "slug": "done",
        "rulebook_version": current,
        "extractor_contract_version": "old-contract",
        "parsed_json": {"deal": {}, "events": []},
    }))
    decision = run_pool.decide_skip("done", _cfg(re_validate=True, audit_root=cfg.audit_root), current, state)
    assert decision.action == "blocked"
    assert "extractor_contract_version" in decision.reason


def test_success_manifest_records_prompt_first_repair_strategy(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    env.seed_deal("a", is_reference=True, status="pending", rulebook_version="rules-v1")
    monkeypatch.setattr(run_pool.core, "rulebook_version", lambda: "rules-v1")

    async def fake_extract(*args, **kwargs):
        raw = {
            "deal": {
                "TargetName": "A",
                "Acquirer": "B",
                "DateAnnounced": None,
                "DateEffective": None,
                "auction": False,
                "all_cash": None,
                "target_legal_counsel": None,
                "acquirer_legal_counsel": None,
                "bidder_registry": {},
                "deal_flags": [],
            },
            "events": [],
        }
        return ExtractResult(
            raw_extraction=raw,
            completion=CompletionResult(
                text=json.dumps(raw),
                model="test-model",
                input_tokens=1,
                output_tokens=1,
            ),
            rulebook_version="rules-v1",
            tool_calls_count=0,
        )

    def fake_prepare(slug, raw, filing):
        return raw, filing, []

    def fake_validate(prepared, filing):
        return run_pool.core.ValidatorResult(row_flags=[], deal_flags=[])

    class FinalizeResult:
        status = "passed_clean"
        flag_count = 0
        notes = "hard=0 soft=0 info=0"
        output_path = env.tmp_path / "output" / "extractions" / "a.json"

    def fake_finalize_prepared(slug, prepared, filing, validation, promotion_log, run_id):
        FinalizeResult.output_path.parent.mkdir(parents=True, exist_ok=True)
        FinalizeResult.output_path.write_text(json.dumps(prepared))
        return FinalizeResult()

    monkeypatch.setattr(run_pool, "extract_deal", fake_extract)
    monkeypatch.setattr(run_pool.core, "load_filing", lambda slug: run_pool.core.Filing(slug=slug, pages=[]))
    monkeypatch.setattr(run_pool.core, "prepare_for_validate", fake_prepare)
    monkeypatch.setattr(run_pool.core, "validate", fake_validate)
    monkeypatch.setattr(run_pool.core, "finalize_prepared", fake_finalize_prepared)

    summary = asyncio.run(
        run_pool.run_pool(
            _cfg(slugs=("a",), audit_root=env.tmp_path / "output" / "audit"),
            llm_client=object(),
        )
    )

    manifest = json.loads((summary.outcomes[0].audit_path / "manifest.json").read_text())
    assert manifest["extract_tool_mode"] == "none"
    assert manifest["repair_strategy"] == "prompt_then_targeted_tools"


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
    run_id = "run-stale-shape"
    audit = cfg.audit_root / "done" / "runs" / run_id
    audit.mkdir(parents=True)
    _write_audit_manifest(audit, slug="done", run_id=run_id)
    payload = {
        "schema_version": "raw_response_v2",
        "run_id": run_id,
        "slug": "done",
        "rulebook_version": "rules-v1",
        "extractor_contract_version": run_pool.extractor_contract_version(),
        "parsed_json": {"deal": {}, "events": []},
        **payload,
    }
    (audit / "raw_response.json").write_text(json.dumps(payload))
    (cfg.audit_root / "done" / "latest.json").write_text(json.dumps({
        "schema_version": "audit_v2",
        "slug": "done",
        "run_id": run_id,
        "outcome": "passed_clean",
        "cache_eligible": True,
        "manifest_path": f"runs/{run_id}/manifest.json",
        "raw_response_path": f"runs/{run_id}/raw_response.json",
    }))
    state = json.loads(env.progress.read_text())

    decision = run_pool.decide_skip("done", cfg, "rules-v1", state)

    assert decision.action == "blocked"
    assert "cached raw_response.json" in decision.reason


def test_re_validate_rejects_legacy_loose_raw_response(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    cfg = _cfg(re_validate=True, audit_root=env.tmp_path / "output" / "audit")
    env.seed_deal("done", status="passed_clean", rulebook_version="rules-v1")
    monkeypatch.setattr(run_pool, "extractor_contract_version", lambda: "contract-v1")
    audit = cfg.audit_root / "done"
    audit.mkdir(parents=True)
    (audit / "raw_response.json").write_text(json.dumps({
        "schema_version": "v1",
        "slug": "done",
        "rulebook_version": "rules-v1",
        "extractor_contract_version": "contract-v1",
        "parsed_json": {"deal": {}, "events": []},
    }))
    state = json.loads(env.progress.read_text())

    decision = run_pool.decide_skip("done", cfg, "rules-v1", state)

    assert decision.action == "blocked"
    assert "latest.json" in decision.reason


def test_run_pool_treats_blocked_revalidate_as_failed(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    cfg = _cfg(
        slugs=("done",),
        re_validate=True,
        audit_root=env.tmp_path / "output" / "audit",
    )
    env.seed_deal("done", status="passed_clean", is_reference=True, rulebook_version="rules-v1")
    monkeypatch.setattr(run_pool.core, "rulebook_version", lambda: "rules-v1")
    monkeypatch.setattr(run_pool, "extractor_contract_version", lambda: "contract-v1")
    audit = cfg.audit_root / "done"
    audit.mkdir(parents=True)
    (audit / "raw_response.json").write_text(json.dumps({
        "schema_version": "raw_response_v2",
        "slug": "done",
        "run_id": "legacy",
        "rulebook_version": "rules-v1",
        "extractor_contract_version": "contract-v1",
        "parsed_json": {"deal": {}, "events": []},
    }))

    summary = asyncio.run(run_pool.run_pool(cfg, llm_client=object()))

    assert summary.failed == 1
    assert summary.skipped == 0
    assert summary.outcomes[0].status == "failed"
    assert "latest.json" in (summary.outcomes[0].error or "")


def test_re_validate_can_select_exact_archived_run_id(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    cfg = _cfg(
        re_validate=True,
        audit_root=env.tmp_path / "output" / "audit",
        audit_run_id="run-one",
    )
    env.seed_deal("done", status="passed_clean", rulebook_version="rules-v1")
    monkeypatch.setattr(run_pool, "extractor_contract_version", lambda: "contract-v1")
    for run_id, target in (("run-one", "one"), ("run-two", "two")):
        run_dir = cfg.audit_root / "done" / "runs" / run_id
        run_dir.mkdir(parents=True)
        _write_audit_manifest(run_dir, slug="done", run_id=run_id)
        (run_dir / "raw_response.json").write_text(json.dumps({
            "schema_version": "raw_response_v2",
            "run_id": run_id,
            "slug": "done",
            "rulebook_version": "rules-v1",
            "extractor_contract_version": "contract-v1",
            "parsed_json": {"deal": {"TargetName": target}, "events": []},
        }))
    (cfg.audit_root / "done" / "latest.json").write_text(json.dumps({
        "schema_version": "audit_v2",
        "slug": "done",
        "run_id": "run-two",
        "outcome": "passed_clean",
        "cache_eligible": True,
        "manifest_path": "runs/run-two/manifest.json",
        "raw_response_path": "runs/run-two/raw_response.json",
    }))

    cached = run_pool._check_cached_raw_response("done", cfg, "rules-v1").parsed_json

    assert cached == {"deal": {"TargetName": "one"}, "events": []}


def test_re_validate_latest_requires_cache_eligible_manifest(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    cfg = _cfg(re_validate=True, audit_root=env.tmp_path / "output" / "audit")
    env.seed_deal("done", status="passed_clean", rulebook_version="rules-v1")
    monkeypatch.setattr(run_pool, "extractor_contract_version", lambda: "contract-v1")
    run_id = "run-failed"
    run_dir = cfg.audit_root / "done" / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(json.dumps({
        "schema_version": "audit_run_v2",
        "slug": "done",
        "run_id": run_id,
        "outcome": "failed",
        "cache_eligible": False,
    }))
    (run_dir / "raw_response.json").write_text(json.dumps({
        "schema_version": "raw_response_v2",
        "run_id": run_id,
        "slug": "done",
        "rulebook_version": "rules-v1",
        "extractor_contract_version": "contract-v1",
        "parsed_json": {"deal": {}, "events": []},
    }))
    (cfg.audit_root / "done" / "latest.json").write_text(json.dumps({
        "schema_version": "audit_v2",
        "slug": "done",
        "run_id": run_id,
        "outcome": "passed_clean",
        "cache_eligible": True,
        "manifest_path": f"runs/{run_id}/manifest.json",
        "raw_response_path": f"runs/{run_id}/raw_response.json",
    }))
    state = json.loads(env.progress.read_text())

    decision = run_pool.decide_skip("done", cfg, "rules-v1", state)

    assert decision.action == "blocked"
    assert "not cache-eligible" in decision.reason


def test_target_gate_blocks_pending_targets_before_client_or_audit(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    env.seed_deal("target", status="pending", is_reference=False)
    env.seed_deal("ref", status="pending", is_reference=True)
    monkeypatch.setattr(run_pool.core, "rulebook_version", lambda: "rules-v1")
    monkeypatch.setattr(run_pool, "_build_client", lambda cfg: pytest.fail("client constructed"))

    with pytest.raises(run_pool.TargetGateClosedError, match="target deals selected=1"):
        asyncio.run(run_pool.run_pool(_cfg(filter="pending", dry_run=True, audit_root=env.tmp_path / "output" / "audit")))

    assert not (env.tmp_path / "output" / "audit").exists()


def test_target_gate_allows_reference_only_selection(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    env.seed_deal("target", status="pending", is_reference=False)
    env.seed_deal("ref", status="pending", is_reference=True)
    monkeypatch.setattr(run_pool.core, "rulebook_version", lambda: "rules-v1")

    summary = asyncio.run(
        run_pool.run_pool(
            _cfg(filter="reference", dry_run=True, audit_root=env.tmp_path / "output" / "audit"),
            llm_client=object(),
        )
    )

    assert summary.selected == 1
    assert summary.outcomes[0].slug == "ref"


def test_target_gate_requires_verified_references_release_flag_and_stability_proof(minimal_state_repo):
    env = minimal_state_repo
    reference_slugs = sorted(run_pool.REFERENCE_SLUGS)
    for slug in reference_slugs:
        env.seed_deal(slug, status="verified", is_reference=True)
    env.seed_deal("target", status="pending", is_reference=False)
    proof = env.tmp_path / "quality_reports" / "stability" / "target-release-proof.json"
    proof.parent.mkdir(parents=True)
    proof.write_text(json.dumps({
        "schema_version": "target_gate_proof_v1",
        "classification": "STABLE_FOR_REFERENCE_REVIEW",
        "reference_slugs": reference_slugs,
        "requested_runs": 3,
        "slug_results": [
            {
                "slug": slug,
                "classification": "STABLE_FOR_REFERENCE_REVIEW",
                "eligible_archived_runs": 3,
                "selected_runs": [f"{slug}-run-1", f"{slug}-run-2", f"{slug}-run-3"],
            }
            for slug in reference_slugs
        ],
    }))
    state = json.loads(env.progress.read_text())
    cfg = _cfg(
        slugs=("target",),
        dry_run=True,
        release_targets=True,
        target_gate_proof=proof,
        audit_root=env.tmp_path / "output" / "audit",
    )

    status = run_pool.target_gate_status(state, proof)

    assert status.is_open is True
    run_pool.enforce_target_gate(["target"], state, cfg)


def test_target_gate_rejects_proof_with_fewer_than_three_runs(minimal_state_repo):
    env = minimal_state_repo
    reference_slugs = sorted(run_pool.REFERENCE_SLUGS)
    for slug in reference_slugs:
        env.seed_deal(slug, status="verified", is_reference=True)
    env.seed_deal("target", status="pending", is_reference=False)
    proof = env.tmp_path / "quality_reports" / "stability" / "target-release-proof.json"
    proof.parent.mkdir(parents=True)
    proof.write_text(json.dumps({
        "schema_version": "target_gate_proof_v1",
        "classification": "STABLE_FOR_REFERENCE_REVIEW",
        "reference_slugs": reference_slugs,
        "requested_runs": 1,
        "slug_results": [
            {
                "slug": slug,
                "classification": "STABLE_FOR_REFERENCE_REVIEW",
                "eligible_archived_runs": 1,
                "selected_runs": [f"{slug}-run-1"],
            }
            for slug in reference_slugs
        ],
    }))
    state = json.loads(env.progress.read_text())
    cfg = _cfg(
        slugs=("target",),
        dry_run=True,
        release_targets=True,
        target_gate_proof=proof,
        audit_root=env.tmp_path / "output" / "audit",
    )

    status = run_pool.target_gate_status(state, proof)

    assert status.is_open is False
    assert "requested_runs" in status.stability_proof_reason
    with pytest.raises(run_pool.TargetGateClosedError, match="requested_runs"):
        run_pool.enforce_target_gate(["target"], state, cfg)


def test_dry_run_no_api_construction_probe_or_writes(minimal_state_repo, monkeypatch, capsys):
    env = minimal_state_repo
    env.seed_deal("a", status="pending", is_reference=True)
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
        env.seed_deal(slug, status="pending", is_reference=True)
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
        env.seed_deal(slug, status="pending", is_reference=True)
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
    env.seed_deal("a", status="pending", is_reference=True)

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
        is_reference=True,
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
    outcome = summary.outcomes[0]
    assert outcome.audit_path is not None
    manifest = json.loads((outcome.audit_path / "manifest.json").read_text())
    latest = json.loads((env.tmp_path / "output" / "audit" / "a" / "latest.json").read_text())
    state = json.loads(env.progress.read_text())
    assert manifest["schema_version"] == "audit_run_v2"
    assert manifest["outcome"] == "failed"
    assert manifest["cache_eligible"] is False
    assert latest["run_id"] == manifest["run_id"]
    assert latest["cache_eligible"] is False
    assert latest["raw_response_path"] is None


def test_failed_initial_run_records_audit_run_id_in_progress(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    env.seed_deal("a", is_reference=True, status="pending", rulebook_version="rules-v1")
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
    outcome = summary.outcomes[0]
    assert outcome.audit_path is not None
    manifest = json.loads((outcome.audit_path / "manifest.json").read_text())
    state = json.loads(env.progress.read_text())
    assert state["deals"]["a"]["status"] == "failed"
    assert state["deals"]["a"]["last_run_id"] == manifest["run_id"]


def test_failed_run_with_commit_commits_current_deal_audit_and_state(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    env.seed_deal("a", is_reference=True, status="pending", rulebook_version="rules-v1")
    monkeypatch.setattr(run_pool.core, "rulebook_version", lambda: "rules-v1")
    captured: list[tuple[str, list]] = []

    async def fail_extract(*args, **kwargs):
        raise RuntimeError("provider cut stream")

    def capture_commit(slug, paths):
        captured.append((slug, list(paths)))

    monkeypatch.setattr(run_pool, "extract_deal", fail_extract)
    monkeypatch.setattr(run_pool, "_commit_paths", capture_commit)

    summary = asyncio.run(
        run_pool.run_pool(
            _cfg(
                slugs=("a",),
                re_extract=True,
                commit=True,
                audit_root=env.tmp_path / "output" / "audit",
            ),
            llm_client=object(),
        )
    )

    assert summary.failed == 1
    assert len(captured) == 1
    slug, paths = captured[0]
    assert slug == "a"
    assert run_pool.core.PROGRESS_PATH in paths
    assert run_pool.core.FLAGS_PATH in paths
    assert summary.outcomes[0].audit_path in paths
    assert env.tmp_path / "output" / "audit" / "a" / "latest.json" in paths


def test_build_audit_writer_creates_new_run_without_deleting_legacy_files(minimal_state_repo):
    env = minimal_state_repo
    env.seed_deal("a", status="pending")
    slug_dir = env.tmp_path / "output" / "audit" / "a"
    old_run = slug_dir / "runs" / "old-run"
    old_run.mkdir(parents=True)
    (old_run / "calls.jsonl").write_text('{"old": true}\n')
    (slug_dir / "raw_response.json").write_text('{"legacy": true}\n')

    audit = run_pool._build_audit_writer(
        env.tmp_path / "output" / "audit",
        "a",
        run_id="new-run",
    )

    assert audit.root == slug_dir / "runs" / "new-run"
    assert (old_run / "calls.jsonl").exists()
    assert (slug_dir / "raw_response.json").exists()


def test_re_validate_source_run_is_not_mutated_by_new_audit_writer(minimal_state_repo):
    env = minimal_state_repo
    source_dir = env.tmp_path / "output" / "audit" / "a" / "runs" / "source-run"
    source_dir.mkdir(parents=True)
    raw_response = source_dir / "raw_response.json"
    raw_response.write_text('{"keep": true}\n')

    audit = run_pool._build_audit_writer(
        env.tmp_path / "output" / "audit",
        "a",
        run_id="new-revalidate-run",
    )

    assert raw_response.exists()
    assert audit.root.name == "new-revalidate-run"
    assert audit.root != source_dir


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
