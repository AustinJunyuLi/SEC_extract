from __future__ import annotations

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
- python scoring/diff.py --slug medivation
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


def _write_report(root: Path, slug: str, text: str) -> Path:
    path = root / "quality_reports" / "reference_verification" / f"{slug}.md"
    path.parent.mkdir(parents=True)
    path.write_text(text)
    return path


def test_check_reports_accepts_complete_verified_report(tmp_path):
    _write_report(tmp_path, "medivation", GOOD_REPORT)

    failures = checker.check_reports(tmp_path, slugs=("medivation",))

    assert failures == []


def test_check_reports_rejects_missing_diff_ledger(tmp_path):
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
    _write_report(
        tmp_path,
        "medivation",
        GOOD_REPORT.replace("Conclusion: VERIFIED", "Conclusion: BLOCKED"),
    )

    failures = checker.check_reports(tmp_path, slugs=("medivation",))

    assert len(failures) == 1
    assert "must conclude with 'Conclusion: VERIFIED'" in failures[0].message


def test_check_reports_rejects_missing_report(tmp_path):
    failures = checker.check_reports(tmp_path, slugs=("medivation",))

    assert len(failures) == 1
    assert "missing verification report" in failures[0].message
