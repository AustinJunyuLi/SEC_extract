from __future__ import annotations

import json
from pathlib import Path

from scripts import mark_reference_verified


GOOD_REPORT = """# medivation Agent Verification

## Run Metadata

- Slug: medivation
- Target: MEDIVATION INC
- Run ID: run-123
- Model: gpt-5.5
- Reasoning effort: high
- Audit path: output/audit/medivation/runs/run-123

## Commands

- python -m pipeline.run_pool --slugs medivation --workers 1 --re-extract

## Extraction And Flag Summary

- Rows: 16
- Hard flags: 0

## AI-vs-Alex Diff Ledger

| Item | Filing evidence | Decision |
|---|---|---|
| diff-1 | Filing page 42 supports the AI row. | Verified against filing text. |

## Filing Evidence Review

The report cites Filing page 42.

## Contract Updates

No rulebook, reference JSON, or comparator update was required.

## Conclusion

Conclusion: VERIFIED
"""


def _write_progress(root: Path, status: str = "passed_clean") -> None:
    state_dir = root / "state"
    state_dir.mkdir()
    (state_dir / "progress.json").write_text(
        json.dumps(
            {
                "schema_version": "v1",
                "deals": {
                    "medivation": {
                        "status": status,
                        "is_reference": True,
                        "target_name": "MEDIVATION INC",
                        "flag_count": 0,
                        "last_run": "2026-05-02T00:00:00Z",
                        "last_run_id": "run-123",
                        "last_verified_by": None,
                        "last_verified_at": None,
                        "notes": "review_burden=0",
                    }
                },
            }
        )
    )


def _write_extraction(root: Path, hard_flag: bool = False, review_blocker: bool = False) -> None:
    out = root / "output" / "extractions"
    out.mkdir(parents=True)
    flags = [{"severity": "hard", "code": "bad", "reason": "bad"}] if hard_flag else []
    review_flags = [{"severity": "blocking", "code": "bad", "reason": "bad"}] if review_blocker else []
    (out / "medivation.json").write_text(
        json.dumps(
            {
                "schema_version": "deal_graph_v2",
                "run_id": "run-123",
                "deal": {"deal_flags": flags},
                "graph": {
                    "evidence": [
                        {
                            "source_page": 42,
                            "quote_text": "Filing page 42 supports the AI row.",
                        }
                    ],
                    "validation_flags": flags,
                    "review_flags": review_flags,
                },
                "review_rows": [
                    {
                        "review_status": "clean",
                        "claim_id": "claim-1",
                        "claim_type": "event_claim",
                        "claim_summary": "AI row support",
                        "confidence": "high",
                        "citation_unit_id": "page_42_paragraph_1",
                        "supplied_quote": "Filing page 42 supports the AI row.",
                        "bound_source_page": 42,
                        "bound_source_quote": "Filing page 42 supports the AI row.",
                    }
                ],
            }
        )
    )


def _write_filing_and_audit(root: Path) -> None:
    filing_dir = root / "data" / "filings" / "medivation"
    filing_dir.mkdir(parents=True)
    (filing_dir / "pages.json").write_text(json.dumps([
        {
            "number": 42,
            "content": "Filing page 42 supports the AI row.",
        }
    ]))
    run_dir = root / "output" / "audit" / "medivation" / "runs" / "run-123"
    run_dir.mkdir(parents=True)
    (run_dir / "raw_response.json").write_text(json.dumps({
        "schema_version": "raw_response_v3",
        "run_id": "run-123",
        "slug": "medivation",
        "parsed_json": {
            "actor_claims": [
                {
                    "evidence_refs": [
                        {
                            "citation_unit_id": "page_42_paragraph_1",
                            "quote_text": "Filing page 42 supports the AI row.",
                        }
                    ]
                }
            ],
            "event_claims": [],
            "bid_claims": [],
            "participation_count_claims": [],
            "actor_relation_claims": [],
        },
    }))


def _write_report(root: Path, text: str = GOOD_REPORT) -> None:
    path = root / "quality_reports" / "reference_verification" / "medivation.md"
    path.parent.mkdir(parents=True)
    path.write_text(text)


def test_mark_verified_updates_reference_progress(tmp_path):
    _write_progress(tmp_path)
    _write_extraction(tmp_path)
    _write_filing_and_audit(tmp_path)
    _write_report(tmp_path)

    mark_reference_verified.mark_verified(
        tmp_path,
        "medivation",
        reviewer="Codex agent",
        now="2026-05-02T12:00:00Z",
    )

    progress = json.loads((tmp_path / "state" / "progress.json").read_text())
    deal = progress["deals"]["medivation"]
    assert deal["status"] == "passed_clean"
    assert deal["verified"] is True
    assert deal["last_verified_by"] == "Codex agent"
    assert deal["last_verified_at"] == "2026-05-02T12:00:00Z"
    assert deal["last_verified_run_id"] == "run-123"
    assert deal["verification_report"] == "quality_reports/reference_verification/medivation.md"


def test_mark_verified_rejects_hard_flags(tmp_path):
    _write_progress(tmp_path)
    _write_extraction(tmp_path, hard_flag=True)
    _write_filing_and_audit(tmp_path)
    _write_report(tmp_path)

    try:
        mark_reference_verified.mark_verified(
            tmp_path,
            "medivation",
            reviewer="Codex agent",
            now="2026-05-02T12:00:00Z",
        )
    except mark_reference_verified.MarkVerifiedError as exc:
        assert "hard flags" in str(exc)
    else:
        raise AssertionError("expected MarkVerifiedError")


def test_mark_verified_allows_open_review_flags(tmp_path):
    _write_progress(tmp_path)
    _write_extraction(tmp_path, review_blocker=True)
    _write_filing_and_audit(tmp_path)
    _write_report(tmp_path)

    mark_reference_verified.mark_verified(
        tmp_path,
        "medivation",
        reviewer="Codex agent",
        now="2026-05-02T12:00:00Z",
    )

    progress = json.loads((tmp_path / "state" / "progress.json").read_text())
    assert progress["deals"]["medivation"]["verified"] is True


def test_mark_verified_rejects_missing_report(tmp_path):
    _write_progress(tmp_path)
    _write_extraction(tmp_path)
    _write_filing_and_audit(tmp_path)

    try:
        mark_reference_verified.mark_verified(
            tmp_path,
            "medivation",
            reviewer="Codex agent",
            now="2026-05-02T12:00:00Z",
        )
    except mark_reference_verified.MarkVerifiedError as exc:
        assert "verification report failed checks" in str(exc)
    else:
        raise AssertionError("expected MarkVerifiedError")


def test_mark_verified_rejects_stale_extraction_run_id(tmp_path):
    _write_progress(tmp_path)
    _write_extraction(tmp_path)
    extraction_path = tmp_path / "output" / "extractions" / "medivation.json"
    payload = json.loads(extraction_path.read_text())
    payload["run_id"] = "old-run"
    extraction_path.write_text(json.dumps(payload))
    _write_filing_and_audit(tmp_path)
    _write_report(tmp_path)

    try:
        mark_reference_verified.mark_verified(
            tmp_path,
            "medivation",
            reviewer="Codex agent",
            now="2026-05-02T12:00:00Z",
        )
    except mark_reference_verified.MarkVerifiedError as exc:
        assert "does not match progress last_run_id" in str(exc)
    else:
        raise AssertionError("expected MarkVerifiedError")
