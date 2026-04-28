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


def test_skip_decisions_and_cache_policy(minimal_state_repo):
    env = minimal_state_repo
    cfg = _cfg(audit_root=env.tmp_path / "output" / "audit")
    current = "rules-v1"
    env.seed_deal("done", status="passed_clean", rulebook_version=current)
    env.seed_deal("stale", status="passed_clean", rulebook_version="old")
    env.seed_deal("failed", status="failed", rulebook_version=current)
    state = json.loads(env.progress.read_text())

    assert run_pool.decide_skip("done", cfg, current, state).action == "skip"
    assert run_pool.decide_skip("stale", cfg, current, state).action == "run"
    assert run_pool.decide_skip("failed", cfg, current, state).action == "run"
    assert run_pool.decide_skip("done", _cfg(re_extract=True, audit_root=cfg.audit_root), current, state).action == "run"
    assert run_pool.decide_skip("done", _cfg(force=True, audit_root=cfg.audit_root), current, state).action == "run"

    audit = cfg.audit_root / "done"
    audit.mkdir(parents=True)
    (audit / "raw_response.json").write_text(json.dumps({
        "schema_version": "v1",
        "slug": "done",
        "rulebook_version": current,
        "parsed_json": {"deal": {}, "events": []},
    }))
    assert run_pool.decide_skip("done", _cfg(re_validate=True, audit_root=cfg.audit_root), current, state).action == "re_validate"
    (audit / "raw_response.json").write_text(json.dumps({
        "schema_version": "v1",
        "slug": "done",
        "rulebook_version": "old",
        "parsed_json": {"deal": {}, "events": []},
    }))
    assert run_pool.decide_skip("done", _cfg(re_validate=True, audit_root=cfg.audit_root), current, state).action == "run"


@pytest.mark.parametrize(
    "payload",
    [
        {"slug": "done", "rulebook_version": "rules-v1", "parsed_json": {"deal": {}, "events": []}},
        {"schema_version": "v0", "slug": "done", "rulebook_version": "rules-v1", "parsed_json": {"deal": {}, "events": []}},
        {"schema_version": "v1", "slug": "other", "rulebook_version": "rules-v1", "parsed_json": {"deal": {}, "events": []}},
        {"schema_version": "v1", "slug": "done", "rulebook_version": "rules-v1", "parsed_json": {"events": []}},
        {"schema_version": "v1", "slug": "done", "rulebook_version": "rules-v1", "parsed_json": {"deal": {}, "events": {}}},
    ],
)
def test_re_validate_rejects_stale_raw_response_shapes(minimal_state_repo, payload):
    env = minimal_state_repo
    cfg = _cfg(re_validate=True, audit_root=env.tmp_path / "output" / "audit")
    env.seed_deal("done", status="passed_clean", rulebook_version="rules-v1")
    audit = cfg.audit_root / "done"
    audit.mkdir(parents=True)
    (audit / "raw_response.json").write_text(json.dumps(payload))
    state = json.loads(env.progress.read_text())

    decision = run_pool.decide_skip("done", cfg, "rules-v1", state)

    assert decision.action == "run"
    assert decision.reason == "no current cache for re-validate"


def test_dry_run_no_api_construction_probe_or_writes(minimal_state_repo, monkeypatch, capsys):
    env = minimal_state_repo
    env.seed_deal("a", status="pending")
    monkeypatch.setattr(run_pool.core, "rulebook_version", lambda: "rules-v1")
    monkeypatch.setattr(run_pool, "_build_client", lambda cfg: pytest.fail("client constructed"))
    async def fail_probe(*args, **kwargs):
        pytest.fail("probe called")
    monkeypatch.setattr(run_pool, "supports_json_schema", fail_probe)
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
    async def probe(*args, **kwargs):
        return True
    monkeypatch.setattr(run_pool, "supports_json_schema", probe)
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
    async def probe(*args, **kwargs):
        return True
    monkeypatch.setattr(run_pool, "supports_json_schema", probe)

    async def fake_process(slug, **kwargs):
        if slug == "a":
            raise RuntimeError("boom")
        return run_pool.DealOutcome(slug=slug, status="passed_clean")

    monkeypatch.setattr(run_pool, "process_deal", fake_process)

    summary = asyncio.run(run_pool.run_pool(_cfg(filter="pending", workers=2), llm_client=object()))

    assert summary.failed == 1
    assert summary.succeeded == 1
    assert {outcome.slug for outcome in summary.outcomes} == {"a", "b"}
