from __future__ import annotations

import json
from pathlib import Path

from scripts import check_reference_verification as checker


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
- python scripts/check_reference_verification.py --slugs medivation
- python -m pipeline.reconcile --scope reference

## Extraction And Flag Summary

- Rows: 16
- Hard flags: 0
- Soft flags: 0
- Info flags: 0

## AI-vs-Alex Diff Ledger

| Item | Filing evidence | Decision |
|---|---|---|
| diff-1 | Filing page 42 supports the AI row. | Verified against filing text. |

## Filing Evidence Review

The reviewer checked the Background of the Merger pages and confirmed that the
current extraction rows are supported by source quotes and pages.

## Contract Updates

No rulebook, reference JSON, or comparator update was required.

## Conclusion

Conclusion: VERIFIED
"""


def _write_current_run_artifacts(root: Path, slug: str = "medivation", run_id: str = "run-123") -> None:
    state = root / "state"
    state.mkdir(parents=True)
    (state / "progress.json").write_text(json.dumps({
        "schema_version": "v1",
        "deals": {
            slug: {
                "status": "passed_clean",
                "is_reference": True,
                "last_run_id": run_id,
            }
        },
    }))
    filing_dir = root / "data" / "filings" / slug
    filing_dir.mkdir(parents=True)
    page_text = (
        "Filing page evidence. Party A submitted an indication of interest. "
        "The current extraction rows are supported by source quotes and pages."
    )
    (filing_dir / "pages.json").write_text(json.dumps([{"number": 42, "content": page_text}]))
    extraction_dir = root / "output" / "extractions"
    extraction_dir.mkdir(parents=True)
    (extraction_dir / f"{slug}.json").write_text(json.dumps({
        "schema_version": "deal_graph_v2",
        "run_id": run_id,
        "deal": {"last_run_id": run_id, "deal_flags": []},
        "graph": {
            "evidence": [
                {
                    "source_page": 42,
                    "quote_text": "Party A submitted an indication of interest.",
                }
            ],
            "validation_flags": [],
            "review_flags": [],
        },
        "review_rows": [
            {
                "source_page": 42,
                "source_quote": "Party A submitted an indication of interest.",
            }
        ],
    }))
    run_dir = root / "output" / "audit" / slug / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "raw_response.json").write_text(json.dumps({
        "schema_version": "raw_response_v3",
        "run_id": run_id,
        "slug": slug,
        "parsed_json": {
            "actor_claims": [
                {
                    "evidence_refs": [
                        {
                            "citation_unit_id": "page_42_paragraph_1",
                            "quote_text": "Party A submitted an indication of interest.",
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


def _write_report(root: Path, slug: str, text: str) -> Path:
    path = root / "quality_reports" / "reference_verification" / f"{slug}.md"
    path.parent.mkdir(parents=True)
    path.write_text(text)
    return path


def test_check_reports_accepts_complete_verified_report(tmp_path):
    _write_current_run_artifacts(tmp_path)
    _write_report(tmp_path, "medivation", GOOD_REPORT)

    failures = checker.check_reports(tmp_path, slugs=("medivation",))

    assert failures == []


def test_check_reports_rejects_missing_diff_ledger(tmp_path):
    _write_current_run_artifacts(tmp_path)
    _write_report(
        tmp_path,
        "medivation",
        GOOD_REPORT.replace("## AI-vs-Alex Diff Ledger", "## Diff Notes"),
    )

    failures = checker.check_reports(tmp_path, slugs=("medivation",))

    assert len(failures) == 1
    assert failures[0].slug == "medivation"
    assert "missing section: ## AI-vs-Alex Diff Ledger" in failures[0].message


def test_check_reports_rejects_blocker_conclusion(tmp_path):
    _write_current_run_artifacts(tmp_path)
    _write_report(
        tmp_path,
        "medivation",
        GOOD_REPORT.replace("Conclusion: VERIFIED", "Conclusion: BLOCKED"),
    )

    failures = checker.check_reports(tmp_path, slugs=("medivation",))

    assert len(failures) == 1
    assert "must conclude with 'Conclusion: VERIFIED'" in failures[0].message


def test_check_reports_rejects_missing_report(tmp_path):
    _write_current_run_artifacts(tmp_path)
    failures = checker.check_reports(tmp_path, slugs=("medivation",))

    assert len(failures) == 1
    assert "missing verification report" in failures[0].message


def test_check_reports_accepts_prior_report_run_metadata_when_current_artifacts_are_grounded(tmp_path):
    _write_current_run_artifacts(tmp_path, run_id="current-run")
    _write_report(tmp_path, "medivation", GOOD_REPORT.replace("Run ID: run-123", "Run ID: old-run"))

    failures = checker.check_reports(tmp_path, slugs=("medivation",))

    assert failures == []


def test_check_reports_rejects_ungrounded_raw_evidence_ref(tmp_path):
    _write_current_run_artifacts(tmp_path)
    raw_path = tmp_path / "output" / "audit" / "medivation" / "runs" / "run-123" / "raw_response.json"
    payload = json.loads(raw_path.read_text())
    payload["parsed_json"]["actor_claims"][0]["evidence_refs"][0]["quote_text"] = "not in filing"
    raw_path.write_text(json.dumps(payload))
    _write_report(tmp_path, "medivation", GOOD_REPORT)

    failures = checker.check_reports(tmp_path, slugs=("medivation",))

    assert any("evidence_ref[0] quote_text is not an exact substring" in failure.message for failure in failures)
