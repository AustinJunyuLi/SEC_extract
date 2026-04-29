import json
from pathlib import Path

from pipeline import reconcile
from pipeline.core import REFERENCE_SLUGS


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def _write_progress(root: Path, deals: dict[str, dict]) -> None:
    _write_json(
        root / "state" / "progress.json",
        {
            "schema_version": "v1",
            "created": "2026-04-29T00:00:00Z",
            "updated": "2026-04-29T00:00:00Z",
            "deal_count_total": len(deals),
            "deal_count_reference": sum(1 for d in deals.values() if d.get("is_reference")),
            "deals": deals,
        },
    )


def _progress_deal(
    *,
    is_reference: bool = True,
    status: str = "passed_clean",
    run_id: str = "run-clean",
    last_run: str = "2026-04-29T00:00:00Z",
    flag_count: int = 0,
    rulebook_version: str = "rules-v1",
) -> dict:
    return {
        "is_reference": is_reference,
        "status": status,
        "flag_count": flag_count,
        "last_run": last_run,
        "last_run_id": run_id,
        "last_verified_by": None,
        "last_verified_at": None,
        "notes": "",
        "rulebook_version": rulebook_version,
        "rulebook_version_history": [
            {"ts": last_run, "run_id": run_id, "version": rulebook_version}
        ],
    }


def _output_payload(
    *,
    run_id: str = "run-clean",
    last_run: str = "2026-04-29T00:00:00Z",
    rulebook_version: str = "rules-v1",
    deal_flags: list[dict] | None = None,
    row_flags: list[dict] | None = None,
) -> dict:
    return {
        "deal": {
            "TargetName": "Synthetic Target",
            "rulebook_version": rulebook_version,
            "last_run": last_run,
            "last_run_id": run_id,
            "deal_flags": deal_flags or [],
        },
        "events": [
            {
                "BidderID": 1,
                "bid_note": "NDA",
                "flags": row_flags or [],
            }
        ],
    }


def _write_output(
    root: Path,
    slug: str,
    *,
    run_id: str = "run-clean",
    last_run: str = "2026-04-29T00:00:00Z",
    rulebook_version: str = "rules-v1",
    deal_flags: list[dict] | None = None,
    row_flags: list[dict] | None = None,
) -> None:
    _write_json(
        root / "output" / "extractions" / f"{slug}.json",
        _output_payload(
            run_id=run_id,
            last_run=last_run,
            rulebook_version=rulebook_version,
            deal_flags=deal_flags,
            row_flags=row_flags,
        ),
    )


def _write_audit(
    root: Path,
    slug: str,
    *,
    run_id: str = "run-clean",
    outcome: str = "passed_clean",
    cache_eligible: bool = True,
    rulebook_version: str = "rules-v1",
    include_raw: bool = True,
    include_validation: bool = True,
    include_final_output: bool = True,
) -> None:
    run_dir = root / "output" / "audit" / slug / "runs" / run_id
    _write_json(
        run_dir / "manifest.json",
        {
            "schema_version": "audit_run_v2",
            "slug": slug,
            "run_id": run_id,
            "outcome": outcome,
            "cache_eligible": cache_eligible,
            "rulebook_version": rulebook_version,
        },
    )
    if include_raw:
        _write_json(
            run_dir / "raw_response.json",
            {
                "schema_version": "raw_response_v2",
                "slug": slug,
                "run_id": run_id,
                "rulebook_version": rulebook_version,
                "parsed_json": {"deal": {}, "events": []},
            },
        )
    if include_validation:
        _write_json(
            run_dir / "validation.json",
            {
                "schema_version": "validation_v1",
                "slug": slug,
                "run_id": run_id,
                "final_status": outcome,
            },
        )
    if include_final_output:
        _write_json(run_dir / "final_output.json", _output_payload(run_id=run_id))
    _write_json(
        root / "output" / "audit" / slug / "latest.json",
        {
            "schema_version": "audit_v2",
            "slug": slug,
            "run_id": run_id,
            "outcome": outcome,
            "cache_eligible": cache_eligible,
            "manifest_path": f"runs/{run_id}/manifest.json",
            "raw_response_path": f"runs/{run_id}/raw_response.json" if include_raw else None,
            "validation_path": f"runs/{run_id}/validation.json" if include_validation else None,
            "final_output_path": f"runs/{run_id}/final_output.json"
            if include_final_output
            else None,
        },
    )


def _write_flags(root: Path, entries: list[dict] | None = None) -> None:
    path = root / "state" / "flags.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(entry, sort_keys=True) + "\n" for entry in entries or [])
    )


def _clean_reference_repo(root: Path) -> None:
    deals = {slug: _progress_deal() for slug in REFERENCE_SLUGS}
    _write_progress(root, deals)
    _write_flags(root)
    for slug in REFERENCE_SLUGS:
        _write_output(root, slug)
        _write_audit(root, slug)


def test_clean_synthetic_reference_state_passes(tmp_path):
    _clean_reference_repo(tmp_path)

    report = reconcile.reconcile_repo(tmp_path, scope="reference")

    assert report.ok
    assert report.error_count == 0
    assert report.warning_count == 0


def test_missing_latest_output_for_finalized_reference_fails(tmp_path):
    _clean_reference_repo(tmp_path)
    (tmp_path / "output" / "extractions" / "medivation.json").unlink()

    report = reconcile.reconcile_repo(tmp_path, scope="reference")

    assert not report.ok
    assert any(
        issue.code == "missing_output" and issue.slug == "medivation"
        for issue in report.issues
    )


def test_progress_and_output_run_id_mismatch_fails(tmp_path):
    _clean_reference_repo(tmp_path)
    _write_output(tmp_path, "medivation", run_id="run-output")

    report = reconcile.reconcile_repo(tmp_path, scope="reference")

    assert any(
        issue.code == "run_id_mismatch" and issue.slug == "medivation"
        for issue in report.issues
    )


def test_validated_reference_deal_is_reported_as_blocked(tmp_path):
    _clean_reference_repo(tmp_path)
    hard_flag = {"code": "source_quote_missing", "severity": "hard", "reason": "missing"}
    progress = json.loads((tmp_path / "state" / "progress.json").read_text())
    progress["deals"]["medivation"] = _progress_deal(
        status="validated",
        flag_count=1,
        run_id="run-hard",
    )
    _write_progress(tmp_path, progress["deals"])
    _write_output(tmp_path, "medivation", run_id="run-hard", row_flags=[hard_flag])
    _write_audit(tmp_path, "medivation", run_id="run-hard", outcome="validated")
    _write_flags(
        tmp_path,
        [
            {
                "deal": "medivation",
                "run_id": "run-hard",
                "logged_at": "2026-04-29T00:00:00Z",
                "row_index": 0,
                **hard_flag,
            }
        ],
    )

    report = reconcile.reconcile_repo(tmp_path, scope="reference")

    assert any(
        issue.code == "validated_reference_blocked" and issue.slug == "medivation"
        for issue in report.issues
    )


def test_target_marked_verified_fails_even_for_reference_scope(tmp_path):
    _clean_reference_repo(tmp_path)
    progress = json.loads((tmp_path / "state" / "progress.json").read_text())
    progress["deals"]["target-deal"] = _progress_deal(
        is_reference=False,
        status="verified",
        run_id="run-target",
    )
    _write_progress(tmp_path, progress["deals"])

    report = reconcile.reconcile_repo(tmp_path, scope="reference")

    assert any(
        issue.code == "target_verified" and issue.slug == "target-deal"
        for issue in report.issues
    )


def test_legacy_loose_audit_files_always_fail(tmp_path):
    _clean_reference_repo(tmp_path)
    (tmp_path / "output" / "audit" / "medivation" / "raw_response.json").write_text("{}\n")
    (tmp_path / "output" / "audit" / "medivation" / "prompts").mkdir()

    report = reconcile.reconcile_repo(tmp_path, scope="reference")

    assert any(
        issue.code == "legacy_loose_audit_file" and issue.severity == "error"
        for issue in report.issues
    )
    assert report.error_count == 2
    assert report.warning_count == 0


def test_latest_failed_attempt_after_prior_finalized_run_is_valid_audit_history(tmp_path):
    _clean_reference_repo(tmp_path)
    _write_audit(
        tmp_path,
        "medivation",
        run_id="run-failed",
        outcome="failed",
        cache_eligible=False,
        include_raw=False,
        include_validation=False,
        include_final_output=False,
    )

    report = reconcile.reconcile_repo(tmp_path, scope="reference")

    assert report.ok
    assert not any(
        issue.code == "audit_run_id_mismatch" and issue.slug == "medivation"
        for issue in report.issues
    )


def test_corrupt_flags_jsonl_reports_exact_one_based_line(tmp_path):
    _clean_reference_repo(tmp_path)
    flags = tmp_path / "state" / "flags.jsonl"
    flags.write_text(json.dumps({"deal": "old", "run_id": "old"}) + "\nnot-json\n")

    report = reconcile.reconcile_repo(tmp_path, scope="reference")

    assert any(
        issue.code == "bad_flags_jsonl"
        and issue.path == "state/flags.jsonl"
        and issue.line == 2
        for issue in report.issues
    )


def test_flags_jsonl_latest_run_must_match_output_flags(tmp_path):
    _clean_reference_repo(tmp_path)
    soft_flag = {"code": "ambiguous_drop", "severity": "soft", "reason": "ambiguous"}
    progress = json.loads((tmp_path / "state" / "progress.json").read_text())
    progress["deals"]["medivation"] = _progress_deal(
        status="passed",
        flag_count=1,
        run_id="run-soft",
    )
    _write_progress(tmp_path, progress["deals"])
    _write_output(tmp_path, "medivation", run_id="run-soft", row_flags=[soft_flag])
    _write_audit(tmp_path, "medivation", run_id="run-soft", outcome="passed")
    _write_flags(tmp_path, [])

    report = reconcile.reconcile_repo(tmp_path, scope="reference")

    assert any(
        issue.code == "flags_jsonl_mismatch" and issue.slug == "medivation"
        for issue in report.issues
    )


def test_failed_latest_audit_must_not_be_cache_eligible(tmp_path):
    _clean_reference_repo(tmp_path)
    progress = json.loads((tmp_path / "state" / "progress.json").read_text())
    progress["deals"]["medivation"] = _progress_deal(
        status="failed",
        flag_count=0,
        run_id="run-failed",
    )
    _write_progress(tmp_path, progress["deals"])
    (tmp_path / "output" / "extractions" / "medivation.json").unlink()
    _write_audit(
        tmp_path,
        "medivation",
        run_id="run-failed",
        outcome="failed",
        cache_eligible=True,
        include_raw=False,
        include_validation=False,
        include_final_output=False,
    )

    report = reconcile.reconcile_repo(tmp_path, scope="reference")

    assert any(
        issue.code == "failed_cache_eligible" and issue.slug == "medivation"
        for issue in report.issues
    )


def test_latest_audit_pointer_must_reference_manifest(tmp_path):
    _clean_reference_repo(tmp_path)
    latest = tmp_path / "output" / "audit" / "medivation" / "latest.json"
    payload = json.loads(latest.read_text())
    payload["manifest_path"] = None
    latest.write_text(json.dumps(payload))

    report = reconcile.reconcile_repo(tmp_path, scope="reference")

    assert any(
        issue.code == "audit_manifest_missing" and issue.slug == "medivation"
        for issue in report.issues
    )


def test_cli_json_accepts_repo_root_scope_and_slugs(tmp_path, capsys):
    _clean_reference_repo(tmp_path)

    rc = reconcile.main(
        [
            "--repo-root",
            str(tmp_path),
            "--scope",
            "all",
            "--slugs",
            "medivation,imprivata",
            "--json",
        ]
    )

    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["checked_slugs"] == ["medivation", "imprivata"]
