import asyncio
import json
from types import SimpleNamespace

import pytest

from pipeline import run_pool
from pipeline.llm.audit import AUDIT_RUN_SCHEMA_VERSION
from pipeline.llm.client import CompletionResult
from pipeline.llm.extract import ExtractResult


def _cfg(**kwargs):
    base = run_pool.PoolConfig()
    for key, value in kwargs.items():
        setattr(base, key, value)
    return base


def _claim_payload(label: str = "CSC/Pamplona") -> dict:
    return {
        "actor_claims": [
            {
                "claim_type": "actor",
                "coverage_obligation_id": "obl_actor_1",
                "actor_label": label,
                "actor_kind": "group",
                "observability": "named",
                "confidence": "high",
                "evidence_refs": [
                    {
                        "citation_unit_id": "page_1_paragraph_1",
                        "quote_text": "CSC and Pamplona, who together we refer to as CSC/Pamplona",
                    }
                ],
            }
        ],
        "event_claims": [],
        "bid_claims": [],
        "participation_count_claims": [],
        "actor_relation_claims": [],
    }


def test_selection_filters_and_explicit_slugs(minimal_state_repo):
    env = minimal_state_repo
    env.seed_deal("a", status="pending", is_reference=True)
    env.seed_deal("b", status="failed_system", is_reference=False)
    env.seed_deal("d", status="stale_after_failure", is_reference=False)
    env.seed_deal("c", status="passed_clean", is_reference=True)
    state = json.loads(env.progress.read_text())

    assert run_pool.resolve_selection(_cfg(filter="pending"), state) == ["a"]
    assert run_pool.resolve_selection(_cfg(filter="failed_system"), state) == ["b"]
    assert run_pool.resolve_selection(_cfg(filter="stale_after_failure"), state) == ["d"]
    assert run_pool.resolve_selection(_cfg(filter="reference"), state) == ["a", "c"]
    assert run_pool.resolve_selection(_cfg(slugs=("c", "a")), state) == ["c", "a"]


def test_failure_statuses_are_not_done_or_success_statuses():
    summary = run_pool.PoolSummary([
        run_pool.DealOutcome(slug="system-failed", status="failed_system"),
        run_pool.DealOutcome(slug="stale", status="stale_after_failure"),
        run_pool.DealOutcome(slug="clean", status="passed_clean"),
    ])

    assert summary.succeeded == 1
    assert summary.failed == 2


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
    parser = run_pool.build_parser()

    cfg = run_pool.config_from_args(parser.parse_args(["--filter", "reference", "--dry-run"]))

    assert cfg.extract_reasoning_effort == "high"
    assert run_pool.PoolConfig().extract_reasoning_effort == "high"


def test_backend_defaults_to_claude_agent_sdk(monkeypatch):
    monkeypatch.delenv("LLM_BACKEND", raising=False)
    parser = run_pool.build_parser()

    cfg = run_pool.config_from_args(parser.parse_args(["--filter", "reference", "--dry-run"]))

    assert cfg.llm_backend == "claude_agent_sdk"
    assert cfg.extract_model is None


def test_openai_backend_defaults_model_and_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    parser = run_pool.build_parser()
    cfg = run_pool.config_from_args(parser.parse_args(["--filter", "reference", "--dry-run", "--llm-backend", "openai"]))

    assert cfg.llm_backend == "openai"
    assert cfg.extract_model == "gpt-5.5"
    cfg.dry_run = False
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        run_pool._build_client(cfg)


def test_invalid_backend_name_fails_loudly():
    cfg = _cfg(llm_backend="not-real")

    with pytest.raises(ValueError, match="llm-backend"):
        run_pool._validate_config(cfg)


def test_openai_backend_rejects_retired_base_url_env(monkeypatch):
    cfg = _cfg(llm_backend="openai", extract_model="gpt-test", openai_api_key="secret")
    monkeypatch.setenv("OPENAI_" + "BASE_URL", "https://example.test/v1")

    with pytest.raises(RuntimeError, match="not supported"):
        run_pool._build_client(cfg)


def test_skip_decisions_have_no_revalidation_cache_path(minimal_state_repo):
    env = minimal_state_repo
    cfg = _cfg(audit_root=env.tmp_path / "output" / "audit")
    current = "rules-v1"
    env.seed_deal("done", status="passed_clean", rulebook_version=current)
    env.seed_deal("unknown_status", status="old_status", rulebook_version=current)
    env.seed_deal("stale", status="passed_clean", rulebook_version="old")
    env.seed_deal("failed", status="failed_system", rulebook_version=current)
    state = json.loads(env.progress.read_text())

    assert run_pool.decide_skip("done", cfg, current, state).action == "skip"
    assert run_pool.decide_skip("unknown_status", cfg, current, state).action == "blocked"
    assert run_pool.decide_skip("stale", cfg, current, state).action == "run"
    assert run_pool.decide_skip("failed", cfg, current, state).action == "run"
    assert run_pool.decide_skip("done", _cfg(re_extract=True, audit_root=cfg.audit_root), current, state).action == "run"


def test_success_manifest_records_claim_only_graph_strategy(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    env.seed_deal("a", is_reference=True, status="pending", rulebook_version="rules-v1")
    monkeypatch.setattr(run_pool.core, "rulebook_version", lambda: "rules-v1")

    async def fake_extract(*args, **kwargs):
        raw = _claim_payload("A")
        return ExtractResult(
            raw_extraction=raw,
            completion=CompletionResult(
                text=json.dumps(raw),
                model="test-model",
                input_tokens=1,
                output_tokens=1,
            ),
            rulebook_version="rules-v1",
        )

    def fake_finalize_claim_payload(**kwargs):
        output_path = env.tmp_path / "output" / "extractions" / "a.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        final_output = {
            "schema_version": "deal_graph_v2",
            "run_id": kwargs["run_id"],
            "deal": {"deal_flags": [], "last_run_id": kwargs["run_id"]},
            "review_rows": [],
        }
        output_path.write_text(json.dumps(final_output))
        return SimpleNamespace(
            status="passed_clean",
            flag_count=0,
            notes="review_burden=0",
            output_path=output_path,
            snapshot_path=env.tmp_path / "output" / "audit" / "a" / "runs" / kwargs["run_id"] / "deal_graph_v2.json",
            database_path=env.tmp_path / "output" / "audit" / "a" / "runs" / kwargs["run_id"] / "deal_graph.duckdb",
            review_rows_path=env.tmp_path / "output" / "review_rows" / "a.jsonl",
            review_csv_path=env.tmp_path / "output" / "review_csv" / "a.csv",
            final_output=final_output,
            validation_flags=[],
        )

    monkeypatch.setattr(run_pool, "extract_deal", fake_extract)
    monkeypatch.setattr(run_pool, "finalize_claim_payload", fake_finalize_claim_payload)

    summary = asyncio.run(
        run_pool.run_pool(
            _cfg(slugs=("a",), audit_root=env.tmp_path / "output" / "audit"),
            llm_client=object(),
        )
    )

    manifest = json.loads((summary.outcomes[0].audit_path / "manifest.json").read_text())
    assert manifest["llm_backend"] == "claude_agent_sdk"
    assert manifest["models"] == {"extract": None}
    assert "extract_tool_mode" not in manifest
    assert "repair_strategy" not in manifest
    assert "obligation_contract_version" not in manifest


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
        env.seed_deal(
            slug,
            status="passed_clean",
            verified=True,
            is_reference=True,
            last_run_id=f"{slug}-current",
            last_verified_run_id=f"{slug}-current",
            verification_report=f"quality_reports/reference_verification/{slug}.md",
        )
    env.seed_deal("target", status="pending", is_reference=False)
    proof = env.tmp_path / "quality_reports" / "stability" / "target-release-proof.json"
    proof.parent.mkdir(parents=True)
    proof.write_text(json.dumps({
        "schema_version": "target_gate_proof_v3",
        "classification": "STABLE_FOR_REFERENCE_REVIEW",
        "llm_content_variation": {"allowed": True},
        "reference_slugs": reference_slugs,
        "requested_runs": 3,
        "slug_results": [
            {
                "slug": slug,
                "classification": "STABLE_FOR_REFERENCE_REVIEW",
                "status": "passed_clean",
                "eligible_archived_runs": 3,
                "selected_runs": [f"{slug}-run-1", f"{slug}-run-2", f"{slug}-run-3"],
                "selected_run_dirs": [
                    f"output/audit/{slug}/runs/{slug}-run-1",
                    f"output/audit/{slug}/runs/{slug}-run-2",
                    f"output/audit/{slug}/runs/{slug}-run-3",
                ],
            }
            for slug in reference_slugs
        ],
    }))
    for slug in reference_slugs:
        for idx in range(1, 4):
            (env.tmp_path / "output" / "audit" / slug / "runs" / f"{slug}-run-{idx}").mkdir(parents=True)
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
        env.seed_deal(
            slug,
            status="passed_clean",
            verified=True,
            is_reference=True,
            last_run_id=f"{slug}-current",
            last_verified_run_id=f"{slug}-current",
            verification_report=f"quality_reports/reference_verification/{slug}.md",
        )
    env.seed_deal("target", status="pending", is_reference=False)
    proof = env.tmp_path / "quality_reports" / "stability" / "target-release-proof.json"
    proof.parent.mkdir(parents=True)
    proof.write_text(json.dumps({
        "schema_version": "target_gate_proof_v3",
        "classification": "STABLE_FOR_REFERENCE_REVIEW",
        "llm_content_variation": {"allowed": True},
        "reference_slugs": reference_slugs,
        "requested_runs": 1,
        "slug_results": [
            {
                "slug": slug,
                "classification": "STABLE_FOR_REFERENCE_REVIEW",
                "status": "passed_clean",
                "eligible_archived_runs": 1,
                "selected_runs": [f"{slug}-run-1"],
                "selected_run_dirs": [f"output/audit/{slug}/runs/{slug}-run-1"],
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


def test_target_gate_rejects_missing_selected_run_directory(minimal_state_repo):
    env = minimal_state_repo
    reference_slugs = sorted(run_pool.REFERENCE_SLUGS)
    for slug in reference_slugs:
        env.seed_deal(
            slug,
            status="passed_clean",
            verified=True,
            is_reference=True,
            last_run_id=f"{slug}-current",
            last_verified_run_id=f"{slug}-current",
            verification_report=f"quality_reports/reference_verification/{slug}.md",
        )
    env.seed_deal("target", status="pending", is_reference=False)
    proof = env.tmp_path / "quality_reports" / "stability" / "target-release-proof.json"
    proof.parent.mkdir(parents=True)
    proof.write_text(json.dumps({
        "schema_version": "target_gate_proof_v3",
        "classification": "STABLE_FOR_REFERENCE_REVIEW",
        "llm_content_variation": {"allowed": True},
        "reference_slugs": reference_slugs,
        "requested_runs": 3,
        "slug_results": [
            {
                "slug": slug,
                "classification": "STABLE_FOR_REFERENCE_REVIEW",
                "status": "passed_clean",
                "eligible_archived_runs": 3,
                "selected_runs": [f"{slug}-run-1", f"{slug}-run-2", f"{slug}-run-3"],
                "selected_run_dirs": [
                    f"output/audit/{slug}/runs/{slug}-run-1",
                    f"output/audit/{slug}/runs/{slug}-run-2",
                    f"output/audit/{slug}/runs/{slug}-run-3",
                ],
            }
            for slug in reference_slugs
        ],
    }))
    state = json.loads(env.progress.read_text())

    status = run_pool.target_gate_status(state, proof)

    assert status.is_open is False
    assert "selected run directory is missing" in status.stability_proof_reason


def test_target_gate_accepts_prior_verified_reference_metadata(minimal_state_repo):
    env = minimal_state_repo
    reference_slugs = sorted(run_pool.REFERENCE_SLUGS)
    for slug in reference_slugs:
        env.seed_deal(
            slug,
            status="passed_clean",
            verified=True,
            is_reference=True,
            last_run_id=f"{slug}-current",
            last_verified_run_id="old-run",
            verification_report=f"quality_reports/reference_verification/{slug}.md",
        )
    state = json.loads(env.progress.read_text())

    status = run_pool.target_gate_status(state, env.tmp_path / "missing-proof.json")

    assert status.reference_verified == len(reference_slugs)
    assert status.missing_verified_references == ()
    assert status.stability_proof_ok is False


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


def test_openai_backend_rejects_xhigh_reasoning(minimal_state_repo):
    env = minimal_state_repo
    env.seed_deal("a", status="pending", is_reference=True)

    with pytest.raises(ValueError, match="OpenAI backend does not support"):
        asyncio.run(
            run_pool.run_pool(
                _cfg(
                    filter="pending",
                    llm_backend="openai",
                    openai_api_key="secret",
                    extract_reasoning_effort="xhigh",
                    dry_run=True,
                ),
                llm_client=object(),
            )
        )


def test_main_reports_unsupported_reasoning_without_traceback(capsys):
    result = run_pool.main([
        "--filter",
        "reference",
        "--llm-backend",
        "openai",
        "--extract-reasoning-effort",
        "xhigh",
        "--dry-run",
    ])

    assert result == 2
    captured = capsys.readouterr()
    assert "OpenAI backend does not support" in captured.err
    assert "Traceback" not in captured.err


def test_failed_rerun_preserves_prior_success_state(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    env.seed_deal(
        "a",
        is_reference=True,
        status="needs_review",
        flag_count=2,
        notes="hard=0 soft=2 info=0",
        rulebook_version="rules-v1",
        last_run="2026-04-28T10:00:00Z",
        last_run_id="run-good",
    )
    env.extractions.mkdir(parents=True, exist_ok=True)
    (env.extractions / "a.json").write_text(json.dumps({
        "schema_version": "deal_graph_v2",
        "run_id": "run-good",
        "deal": {"last_run_id": "run-good", "deal_flags": []},
        "review_rows": [{"review_status": "needs_review"}],
    }))
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
    latest = json.loads((env.tmp_path / "output" / "audit" / "a" / "latest.json").read_text())
    state = json.loads(env.progress.read_text())
    assert state["deals"]["a"]["status"] == "stale_after_failure"
    assert state["deals"]["a"]["last_run_id"] == manifest["run_id"]
    assert manifest["schema_version"] == AUDIT_RUN_SCHEMA_VERSION
    assert manifest["outcome"] == "stale_after_failure"
    assert manifest["stability_eligible"] is False
    assert latest["run_id"] == manifest["run_id"]
    assert latest["stability_eligible"] is False
    assert latest["raw_response_path"] is None


def test_failed_initial_run_records_latest_run_id_in_progress(minimal_state_repo, monkeypatch):
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
    assert state["deals"]["a"]["status"] == "failed_system"
    assert state["deals"]["a"]["last_run_id"] == manifest["run_id"]


def test_successful_verified_reference_rerun_preserves_verification_metadata(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    env.seed_deal(
        "a",
        is_reference=True,
        status="passed_clean",
        verified=True,
        flag_count=0,
        rulebook_version="rules-v1",
        last_run_id="old-run",
        last_verified_by="Codex agent",
        last_verified_at="2026-05-01T00:00:00Z",
        last_verified_run_id="old-run",
        verification_report="quality_reports/reference_verification/a.md",
    )
    monkeypatch.setattr(run_pool.core, "rulebook_version", lambda: "rules-v1")
    monkeypatch.setattr(run_pool.core, "_new_run_id", lambda: "new-run")

    async def fake_extract(*args, **kwargs):
        raw = _claim_payload("A")
        return ExtractResult(
            raw_extraction=raw,
            completion=CompletionResult(
                text=json.dumps(raw),
                model="test-model",
                input_tokens=1,
                output_tokens=1,
            ),
            rulebook_version="rules-v1",
        )

    def fake_finalize_claim_payload(**kwargs):
        output_path = env.tmp_path / "output" / "extractions" / "a.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        final_output = {
            "schema_version": "deal_graph_v2",
            "run_id": kwargs["run_id"],
            "deal": {"deal_flags": [], "last_run_id": kwargs["run_id"]},
            "review_rows": [],
        }
        output_path.write_text(json.dumps(final_output))
        run_pool.core.update_progress(
            "a",
            "passed_clean",
            0,
            "review_burden=0",
            kwargs["rulebook_version"],
            "2026-05-06T00:00:00Z",
            kwargs["run_id"],
        )
        return SimpleNamespace(
            status="passed_clean",
            flag_count=0,
            notes="review_burden=0",
            output_path=output_path,
            snapshot_path=env.tmp_path / "output" / "audit" / "a" / "runs" / kwargs["run_id"] / "deal_graph_v2.json",
            database_path=env.tmp_path / "output" / "audit" / "a" / "runs" / kwargs["run_id"] / "deal_graph.duckdb",
            review_rows_path=env.tmp_path / "output" / "review_rows" / "a.jsonl",
            review_csv_path=env.tmp_path / "output" / "review_csv" / "a.csv",
            final_output=final_output,
            validation_flags=[],
        )

    monkeypatch.setattr(run_pool, "extract_deal", fake_extract)
    monkeypatch.setattr(run_pool, "finalize_claim_payload", fake_finalize_claim_payload)

    summary = asyncio.run(
        run_pool.run_pool(
            _cfg(slugs=("a",), re_extract=True, audit_root=env.tmp_path / "output" / "audit"),
            llm_client=object(),
        )
    )

    assert summary.succeeded == 1
    state = json.loads(env.progress.read_text())
    deal = state["deals"]["a"]
    assert deal["status"] == "passed_clean"
    assert deal["verified"] is True
    assert deal["last_run_id"] == "new-run"
    assert deal["last_verified_by"] == "Codex agent"
    assert deal["last_verified_at"] == "2026-05-01T00:00:00Z"
    assert deal["last_verified_run_id"] == "old-run"
    assert deal["verification_report"] == "quality_reports/reference_verification/a.md"


def test_clean_reference_rerun_restores_prior_verification_after_hard_flag_run(minimal_state_repo):
    env = minimal_state_repo
    env.seed_deal(
        "a",
        is_reference=True,
        status="needs_review",
        flag_count=1,
        rulebook_version="rules-v1",
        last_run_id="hard-run",
        last_verified_by="Codex agent",
        last_verified_at="2026-05-01T00:00:00Z",
        last_verified_run_id="old-verified-run",
        verification_report="quality_reports/reference_verification/a.md",
    )

    run_pool.core.update_progress(
        "a",
        "passed_clean",
        0,
        "review_burden=0",
        "rules-v1",
        "2026-05-06T00:00:00Z",
        "clean-run",
    )

    state = json.loads(env.progress.read_text())
    deal = state["deals"]["a"]
    assert deal["status"] == "passed_clean"
    assert deal["verified"] is True
    assert deal["flag_count"] == 0
    assert deal["last_run_id"] == "clean-run"
    assert deal["last_verified_by"] == "Codex agent"
    assert deal["last_verified_run_id"] == "old-verified-run"
    assert deal["verification_report"] == "quality_reports/reference_verification/a.md"


def test_failed_verified_reference_rerun_preserves_last_verified_state(minimal_state_repo, monkeypatch):
    env = minimal_state_repo
    env.seed_deal(
        "a",
        is_reference=True,
        status="passed_clean",
        flag_count=0,
        rulebook_version="rules-v1",
        last_run_id="old-run",
        last_verified_by="Codex agent",
        last_verified_at="2026-05-01T00:00:00Z",
        last_verified_run_id="old-run",
        verification_report="quality_reports/reference_verification/a.md",
    )
    env.extractions.mkdir(parents=True, exist_ok=True)
    (env.extractions / "a.json").write_text(json.dumps({
        "schema_version": "deal_graph_v2",
        "run_id": "old-run",
        "deal": {"last_run_id": "old-run", "deal_flags": []},
        "review_rows": [],
    }))
    monkeypatch.setattr(run_pool.core, "rulebook_version", lambda: "rules-v1")
    monkeypatch.setattr(run_pool.core, "_new_run_id", lambda: "new-run")

    async def fail_extract(*args, **kwargs):
        raise RuntimeError("provider cut stream")

    monkeypatch.setattr(run_pool, "extract_deal", fail_extract)

    summary = asyncio.run(
        run_pool.run_pool(
            _cfg(slugs=("a",), re_extract=True, audit_root=env.tmp_path / "output" / "audit"),
            llm_client=object(),
        )
    )

    assert summary.failed == 1
    state = json.loads(env.progress.read_text())
    deal = state["deals"]["a"]
    assert deal["status"] == "stale_after_failure"
    assert deal["last_run_id"] == "new-run"
    assert deal["last_verified_by"] == "Codex agent"
    assert deal["last_verified_at"] == "2026-05-01T00:00:00Z"
    assert deal["last_verified_run_id"] == "old-run"
    assert deal["verification_report"] == "quality_reports/reference_verification/a.md"


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


def test_build_audit_writer_requires_new_run_directory(minimal_state_repo):
    env = minimal_state_repo
    env.seed_deal("a", status="pending")
    slug_dir = env.tmp_path / "output" / "audit" / "a"

    audit = run_pool._build_audit_writer(
        env.tmp_path / "output" / "audit",
        "a",
        run_id="new-run",
    )

    assert audit.root == slug_dir / "runs" / "new-run"
