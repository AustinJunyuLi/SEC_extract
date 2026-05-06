from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline import stability
from pipeline.llm.audit import AUDIT_RUN_SCHEMA_VERSION, RAW_RESPONSE_SCHEMA_VERSION


BASE_HASHES = {
    "prompt_hash": "prompt-v1",
    "schema_hash": "schema-v1",
    "rulebook_version": "rules-v1",
    "extractor_contract_version": "contract-v1",
}


def _event(
    *,
    bid_note: str = "bid_submitted",
    bidder_alias: str = "Party A",
    bidder_type: str | None = "organization",
    bid_value_lower: float | None = 10.0,
    bid_value_upper: float | None = 12.0,
    bound_source_quote: str = "Party A submitted an indication of interest.",
    bound_source_page: int = 4,
    flags: list[dict] | None = None,
) -> dict:
    subtype = {
        "Bid": "bid_submitted",
        "NDA": "nda_signed",
        "Drop": "bidder_dropped",
        "DropSilent": "bidder_dropped_silent",
        "Executed": "merger_agreement_executed",
        "Final Round": "formal_boundary",
    }.get(bid_note, bid_note)
    return {
        "deal_slug": "medivation",
        "cycle_id": "cycle_synthetic",
        "event_id": f"event_{subtype}_{bidder_alias}".replace(" ", "_").lower(),
        "event_date": "2026-01-15",
        "event_type": "process",
        "event_subtype": subtype,
        "actor_id": f"actor_{bidder_alias}".replace(" ", "_").lower(),
        "actor_label": bidder_alias,
        "actor_kind": bidder_type,
        "actor_role": "potential bidder",
        "bid_value": None,
        "bid_value_lower": bid_value_lower,
        "bid_value_upper": bid_value_upper,
        "bid_value_unit": "per_share" if bid_value_lower is not None or bid_value_upper is not None else None,
        "consideration_type": "cash" if bid_value_lower is not None or bid_value_upper is not None else None,
        "review_status": "clean",
        "claim_id": "claim_synthetic",
        "claim_type": "event_claim",
        "claim_summary": "Party A submitted an indication of interest.",
        "confidence": "high",
        "citation_unit_id": "page_1_paragraph_1",
        "supplied_quote": bound_source_quote,
        "bound_source_page": bound_source_page,
        "bound_source_quote": bound_source_quote,
        "issue_codes": "",
        "issue_reasons": "",
        "suggested_action": "",
        "evidence_ref_index": "",
        "flags": flags or [],
    }


def _claim_payload() -> dict:
    return {
        "actor_claims": [
            {
                "claim_type": "actor",
                "coverage_obligation_id": "obl_actor_1",
                "actor_label": "Synthetic Target",
                "actor_kind": "organization",
                "observability": "named",
                "confidence": "high",
                "evidence_refs": [
                    {
                        "citation_unit_id": "page_1_paragraph_1",
                        "quote_text": "Synthetic Target entered into a merger agreement.",
                    }
                ],
            }
        ],
        "event_claims": [],
        "bid_claims": [],
        "participation_count_claims": [],
        "actor_relation_claims": [],
    }


def _write_run(
    repo_root: Path,
    *,
    slug: str,
    run_id: str,
    finished_at: str,
    events: list[dict] | None = None,
    row_flags: list[dict] | None = None,
    deal_flags: list[dict] | None = None,
    manifest_extra: dict | None = None,
) -> Path:
    run_dir = repo_root / "output" / "audit" / slug / "runs" / run_id
    run_dir.mkdir(parents=True)
    manifest = {
        "schema_version": AUDIT_RUN_SCHEMA_VERSION,
        "slug": slug,
        "run_id": run_id,
        "outcome": "passed_clean",
        "cache_eligible": True,
        "cache_used": False,
        "started_at": "2026-04-29T00:00:00Z",
        "finished_at": finished_at,
        "models": {"extract": "gpt-5.5"},
        "reasoning_efforts": {"extract": "xhigh"},
        "api_endpoint": "linkflow",
        "prompt_hashes": {"extract": BASE_HASHES["prompt_hash"]},
        **BASE_HASHES,
    }
    if manifest_extra:
        manifest.update(manifest_extra)
    review_rows = events if events is not None else [_event()]
    graph_flags = row_flags or []
    graph = {
        "schema_version": "deal_graph_v2",
        "run_id": run_id,
        "deal_slug": slug,
        "deals": [
            {
                "deal_id": "deal_synthetic",
                "deal_slug": slug,
                "target_name": "Synthetic Target",
            }
        ],
        "process_cycles": [{"cycle_id": "cycle_synthetic", "deal_id": "deal_synthetic"}],
        "evidence": [],
        "claims": [{"claim_id": "claim_synthetic", "claim_type": "event", "status": "current"}],
        "claim_evidence": [],
        "claim_dispositions": [
            {
                "disposition_id": "disposition_synthetic",
                "claim_id": "claim_synthetic",
                "disposition": "supported",
                "current": True,
            }
        ],
        "claim_coverage_links": [],
        "coverage_results": [
            {
                "coverage_result_id": "coverage_synthetic",
                "obligation_id": "events_core",
                "result": "claims_emitted",
                "current": True,
            }
        ],
        "actors": [
            {
                "actor_id": row["actor_id"],
                "actor_label": row["actor_label"],
                "actor_kind": row["actor_kind"],
                "bidder_class": "unknown",
            }
            for row in review_rows
        ],
        "actor_relations": [],
        "events": [
            {
                "event_id": row["event_id"],
                "cycle_id": row["cycle_id"],
                "event_type": row["event_type"],
                "event_subtype": row["event_subtype"],
                "event_date": row["event_date"],
                "bid_value": row["bid_value"],
                "bid_value_lower": row["bid_value_lower"],
                "bid_value_upper": row["bid_value_upper"],
                "bid_value_unit": row["bid_value_unit"],
                "consideration_type": row["consideration_type"],
            }
            for row in review_rows
        ],
        "event_actor_links": [
            {
                "link_id": f"link_{idx}",
                "event_id": row["event_id"],
                "actor_id": row["actor_id"],
                "actor_label": row["actor_label"],
                "role": row["actor_role"],
            }
            for idx, row in enumerate(review_rows)
        ],
        "participation_counts": [],
        "row_evidence": [],
        "review_flags": graph_flags,
        "review_rows": review_rows,
        "last_run": finished_at,
        "rulebook_version": BASE_HASHES["rulebook_version"],
        "validation_flags": graph_flags,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    (run_dir / "final_output.json").write_text(json.dumps({
        "schema_version": "deal_graph_v2",
        "deal_slug": slug,
        "run_id": run_id,
        "last_run": finished_at,
        "rulebook_version": BASE_HASHES["rulebook_version"],
        "deal": {
            "deal_slug": slug,
            "deal_flags": deal_flags or [],
            "last_run": finished_at,
            "last_run_id": run_id,
            "rulebook_version": BASE_HASHES["rulebook_version"],
            "status": manifest.get("outcome", "passed_clean"),
        },
        "graph": graph,
        "review_rows": review_rows,
    }, indent=2, sort_keys=True))
    (run_dir / "validation.json").write_text(json.dumps({
        "schema_version": "validation_v1",
        "slug": slug,
        "run_id": run_id,
        "final_status": manifest.get("outcome", "passed_clean"),
        "flag_count": len(graph_flags),
        "hard_count": sum(1 for flag in graph_flags if flag.get("severity") == "hard"),
        "soft_count": sum(1 for flag in graph_flags if flag.get("severity") == "soft"),
        "info_count": sum(1 for flag in graph_flags if flag.get("severity") == "info"),
        "validation_flags": graph_flags,
    }, indent=2, sort_keys=True))
    (run_dir / "raw_response.json").write_text(json.dumps({
        "schema_version": RAW_RESPONSE_SCHEMA_VERSION,
        "slug": slug,
        "run_id": run_id,
        "parsed_json": _claim_payload(),
    }, indent=2, sort_keys=True))
    (run_dir / "calls.jsonl").write_text("")
    (run_dir / "prompts").mkdir()
    return run_dir


def _write_runs(repo_root: Path, slug: str = "medivation", count: int = 3, **kwargs) -> None:
    for idx in range(count):
        _write_run(
            repo_root,
            slug=slug,
            run_id=f"run-{idx + 1}",
            finished_at=f"2026-04-29T00:0{idx}:00Z",
            **kwargs,
        )


def test_identical_archived_runs_classify_stable(tmp_path, capsys):
    _write_runs(tmp_path)

    rc = stability.main([
        "--repo-root", str(tmp_path),
        "--slugs", "medivation",
        "--runs", "3",
    ])

    out = capsys.readouterr().out
    assert rc == 0
    assert "STABLE_FOR_REFERENCE_REVIEW" in out
    assert "medivation" in out


def test_hard_flag_movement_classifies_architecture_unstable(tmp_path, capsys):
    _write_run(tmp_path, slug="medivation", run_id="run-1", finished_at="2026-04-29T00:00:00Z")
    _write_run(
        tmp_path,
        slug="medivation",
        run_id="run-2",
        finished_at="2026-04-29T00:01:00Z",
        row_flags=[{"code": "missing_quote", "severity": "hard", "row_index": 0, "reason": "missing"}],
        manifest_extra={"outcome": "validated"},
    )
    _write_run(tmp_path, slug="medivation", run_id="run-3", finished_at="2026-04-29T00:02:00Z")

    rc = stability.main(["--repo-root", str(tmp_path), "--slugs", "medivation", "--runs", "3"])

    out = capsys.readouterr().out
    assert rc == 1
    assert "UNSTABLE_ARCHITECTURE_ESCALATION_CANDIDATE" in out
    assert "hard flag identities changed" in out


def test_stable_hard_flags_cannot_produce_target_gate_proof(tmp_path, capsys):
    hard_flag = {"code": "missing_quote", "severity": "hard", "row_index": 0, "reason": "missing"}
    _write_runs(
        tmp_path,
        row_flags=[hard_flag],
        manifest_extra={"outcome": "validated"},
    )

    rc = stability.main([
        "--repo-root", str(tmp_path),
        "--slugs", "medivation",
        "--runs", "3",
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert payload["classification"] == "UNSTABLE_RULE_OR_VALIDATOR_FIX_NEEDED"
    assert "hard flags present" in " ".join(payload["reasons"])


def test_row_count_movement_is_reported_without_blocking_clean_contract_runs(tmp_path, capsys):
    _write_run(tmp_path, slug="medivation", run_id="run-1", finished_at="2026-04-29T00:00:00Z")
    _write_run(
        tmp_path,
        slug="medivation",
        run_id="run-2",
        finished_at="2026-04-29T00:01:00Z",
        events=[_event(), _event(bid_note="NDA", bid_value_lower=None, bid_value_upper=None)],
    )
    _write_run(tmp_path, slug="medivation", run_id="run-3", finished_at="2026-04-29T00:02:00Z")

    rc = stability.main(["--repo-root", str(tmp_path), "--slugs", "medivation", "--runs", "3"])

    out = capsys.readouterr().out
    assert rc == 0
    assert "STABLE_FOR_REFERENCE_REVIEW" in out
    assert "metric variability observed" in out
    assert "row fingerprints changed" in out


def test_pure_info_count_increase_does_not_force_unstable(tmp_path, capsys):
    _write_run(tmp_path, slug="medivation", run_id="run-1", finished_at="2026-04-29T00:00:00Z")
    _write_run(
        tmp_path,
        slug="medivation",
        run_id="run-2",
        finished_at="2026-04-29T00:01:00Z",
        row_flags=[{"code": "quote_near_limit", "severity": "info", "row_index": 0, "reason": "verbose"}],
        manifest_extra={"outcome": "passed"},
    )
    _write_run(tmp_path, slug="medivation", run_id="run-3", finished_at="2026-04-29T00:02:00Z")

    rc = stability.main(["--repo-root", str(tmp_path), "--slugs", "medivation", "--runs", "3"])

    out = capsys.readouterr().out
    assert rc == 0
    assert "STABLE_FOR_REFERENCE_REVIEW" in out
    assert "info-only flag volume changed" in out


def test_missing_archived_runs_are_insufficient(tmp_path, capsys):
    _write_runs(tmp_path, count=2)

    rc = stability.main(["--repo-root", str(tmp_path), "--slugs", "medivation", "--runs", "3"])

    out = capsys.readouterr().out
    assert rc == 1
    assert "INSUFFICIENT_ARCHIVED_RUNS" in out
    assert "medivation has 2 eligible archived runs; need 3" in out


def test_report_output_is_deterministic(tmp_path):
    _write_runs(tmp_path)

    report_one = stability.build_report(
        stability.analyze(repo_root=tmp_path, slugs=["medivation"], runs=3)
    )
    report_two = stability.build_report(
        stability.analyze(repo_root=tmp_path, slugs=["medivation"], runs=3)
    )

    assert report_one == report_two


def test_json_report_is_target_gate_proof_shape(tmp_path, capsys):
    _write_runs(tmp_path)

    rc = stability.main([
        "--repo-root", str(tmp_path),
        "--slugs", "medivation",
        "--runs", "3",
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert payload["schema_version"] == "target_gate_proof_v2"
    assert payload["classification"] == "STABLE_FOR_REFERENCE_REVIEW"
    assert payload["llm_content_variation"]["allowed"] is True
    assert payload["reference_slugs"] == ["medivation"]
    assert payload["slug_results"][0]["selected_run_dirs"] == [
        "output/audit/medivation/runs/run-1",
        "output/audit/medivation/runs/run-2",
        "output/audit/medivation/runs/run-3",
    ]


def test_model_or_reasoning_drift_classifies_rule_or_validator_needed(tmp_path, capsys):
    _write_run(tmp_path, slug="medivation", run_id="run-1", finished_at="2026-04-29T00:00:00Z")
    _write_run(
        tmp_path,
        slug="medivation",
        run_id="run-2",
        finished_at="2026-04-29T00:01:00Z",
        manifest_extra={"reasoning_efforts": {"extract": "high"}},
    )
    _write_run(tmp_path, slug="medivation", run_id="run-3", finished_at="2026-04-29T00:02:00Z")

    rc = stability.main(["--repo-root", str(tmp_path), "--slugs", "medivation", "--runs", "3"])

    out = capsys.readouterr().out
    assert rc == 1
    assert "UNSTABLE_RULE_OR_VALIDATOR_FIX_NEEDED" in out
    assert "model/reasoning/provider" in out


def test_write_writes_only_requested_path(tmp_path):
    _write_runs(tmp_path)
    requested = tmp_path / "quality_reports" / "stability" / "reference-latest.md"

    rc = stability.main([
        "--repo-root", str(tmp_path),
        "--slugs", "medivation",
        "--runs", "3",
        "--write", str(requested),
    ])

    assert rc == 0
    assert requested.exists()
    written = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*") if p.is_file())
    assert Path("quality_reports/stability/reference-latest.md") in written
    assert Path("output/extractions/medivation.json") not in written


def test_mutable_latest_extraction_is_not_used_for_comparison(tmp_path, capsys):
    _write_runs(tmp_path)
    mutable = tmp_path / "output" / "extractions"
    mutable.mkdir(parents=True)
    (mutable / "medivation.json").write_text(json.dumps({
        "deal": {"auction": False},
        "events": [_event(), _event(bidder_alias="Party B")],
    }))

    rc = stability.main(["--repo-root", str(tmp_path), "--slugs", "medivation", "--runs", "3"])

    out = capsys.readouterr().out
    assert rc == 0
    assert "STABLE_FOR_REFERENCE_REVIEW" in out


def test_strict_mode_rejects_legacy_singleton_audit_files(tmp_path, capsys):
    _write_runs(tmp_path)
    legacy = tmp_path / "output" / "audit" / "medivation" / "manifest.json"
    legacy.write_text(json.dumps({"legacy": True}))

    rc = stability.main(["--repo-root", str(tmp_path), "--slugs", "medivation", "--runs", "3"])

    err = capsys.readouterr().err
    assert rc == 2
    assert "legacy singleton audit file rejected" in err


def test_stale_non_v3_run_directories_are_not_stability_inputs(tmp_path, capsys):
    _write_runs(tmp_path)
    stale_run = tmp_path / "output" / "audit" / "medivation" / "runs" / "stale-v2"
    stale_run.mkdir(parents=True)
    (stale_run / "manifest.json").write_text(json.dumps({
        "schema_version": "audit_run_v2",
        "slug": "medivation",
        "run_id": "stale-v2",
    }))

    rc = stability.main(["--repo-root", str(tmp_path), "--slugs", "medivation", "--runs", "3"])

    out = capsys.readouterr().out
    assert rc == 0
    assert "STABLE_FOR_REFERENCE_REVIEW" in out
    assert "stale-v2" not in out


def test_manifestless_run_directories_are_not_stability_inputs(tmp_path, capsys):
    _write_runs(tmp_path)
    partial_run = tmp_path / "output" / "audit" / "medivation" / "runs" / "partial"
    partial_run.mkdir(parents=True)
    (partial_run / "raw_response.json").write_text("{}")

    rc = stability.main(["--repo-root", str(tmp_path), "--slugs", "medivation", "--runs", "3"])

    out = capsys.readouterr().out
    assert rc == 0
    assert "STABLE_FOR_REFERENCE_REVIEW" in out
    assert "partial" not in out


def test_stale_v3_non_graph_outputs_are_not_stability_inputs(tmp_path, capsys):
    _write_runs(tmp_path)
    stale_run = _write_run(
        tmp_path,
        slug="medivation",
        run_id="stale-v3",
        finished_at="2026-04-29T00:09:00Z",
    )
    (stale_run / "final_output.json").write_text(json.dumps({
        "deal": {"TargetName": "Synthetic Target"},
        "events": [_event()],
    }))

    rc = stability.main(["--repo-root", str(tmp_path), "--slugs", "medivation", "--runs", "3"])

    out = capsys.readouterr().out
    assert rc == 0
    assert "STABLE_FOR_REFERENCE_REVIEW" in out
    assert "stale-v3" not in out


def test_archived_run_manifest_must_use_live_nested_config_shape(tmp_path, capsys):
    _write_runs(tmp_path)
    manifest = tmp_path / "output" / "audit" / "medivation" / "runs" / "run-2" / "manifest.json"
    payload = json.loads(manifest.read_text())
    payload.pop("models")
    payload["extract_model"] = "gpt-5.5"
    manifest.write_text(json.dumps(payload))

    rc = stability.main(["--repo-root", str(tmp_path), "--slugs", "medivation", "--runs", "3"])

    assert rc == 2
    assert "manifest missing required models.extract" in capsys.readouterr().err
