# Reference Stability Goal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the committed reference-stability goal so all nine reference deals are extracted, tested, agent-verified against filing text, committed with current proof artifacts, and accepted by the stability gate as `STABLE_FOR_REFERENCE_REVIEW`.

**Architecture:** Treat `docs/superpowers/specs/2026-05-02-reference-stability-goal-design.md` as the controlling release spec. Finish or redesign the live extraction pipeline only when reference-deal evidence proves the current obligation-gated single-repair design cannot reach the proof. Add a small verification-report contract so `verified` status is filing-grounded, auditable, and checked before state mutation.

**Tech Stack:** Python 3, pytest, repo-local JSON/Markdown artifacts, AsyncOpenAI Responses wrappers through Linkflow/NewAPI, strict JSON schema outputs, `pipeline.run_pool`, `pipeline.reconcile`, `pipeline.stability`.

---

## Source Contract

Read these files before starting implementation:

- `docs/superpowers/specs/2026-05-02-reference-stability-goal-design.md`
- `AGENTS.md`
- `CLAUDE.md`
- `SKILL.md`
- `docs/linkflow-extraction-guide.md`
- `docs/superpowers/plans/2026-05-01-obligation-gated-single-repair-implementation.md` if it still exists

This plan deliberately changes the live `verified` authority. For this release process, a Codex agent may mark reference deals `verified` only after a complete filing-grounded verification report exists at `quality_reports/reference_verification/{slug}.md`.

## Reference Slugs

The release target is exactly these nine slugs:

```text
providence-worcester
medivation
imprivata
zep
petsmart-inc
penford
mac-gray
saks
stec
```

## File Structure

- Modify `AGENTS.md`: redefine `verified` to allow agent filing-grounded verification for this release process and document `quality_reports/reference_verification/{slug}.md`.
- Modify `CLAUDE.md`: keep the Claude-facing live contract in sync with `AGENTS.md`.
- Modify `SKILL.md`: update the detailed extraction skill contract for agent verification authority and the canonical verification artifact path.
- Modify `docs/linkflow-extraction-guide.md`: update target-release protocol so `verified` can be Austin-verified or agent-verified with a complete report.
- Create `quality_reports/reference_verification/README.md`: canonical schema for per-deal verification reports.
- Create `scripts/check_reference_verification.py`: validates verification reports before any deal is marked `verified`.
- Create `scripts/mark_reference_verified.py`: updates `state/progress.json` only after a verification report passes the checker and the extraction has no hard flags.
- Create `tests/test_reference_verification_contract.py`: pins live docs to the new verification authority.
- Create `tests/test_reference_verification_reports.py`: tests the verification report checker.
- Create `tests/test_mark_reference_verified.py`: tests the state marker.
- Generate `quality_reports/reference_verification/{slug}.md`: one report per reference slug.
- Generate `quality_reports/stability/target-release-proof.json`: final stability proof.
- Generate `quality_reports/reference_stability_cleanup.md`: cleanup and staging record.
- Modify pipeline code, prompts, rules, tests, state, output, and selected proof-supporting audit artifacts only as required to satisfy the release proof.

Do not add compatibility readers, fallback JSON parsing, non-strict output modes, legacy repair branches, or target-deal extraction.

---

### Task 1: Baseline And Dirty-Tree Inventory

**Files:**
- Read: `docs/superpowers/specs/2026-05-02-reference-stability-goal-design.md`
- Read: `AGENTS.md`
- Read: `SKILL.md`
- Read: `docs/linkflow-extraction-guide.md`
- Read: `state/progress.json`
- Read: `output/audit/`
- No code changes

- [ ] **Step 1: Confirm controlling commit and dirty state**

Run:

```bash
git log --oneline -5
git status --short
```

Expected: the log includes `c263ff8 spec: define reference stability goal`. The status may be dirty. Record the dirty files in the task notes and do not reset or revert unrelated changes.

- [ ] **Step 2: Read the controlling spec**

Run:

```bash
sed -n '1,340p' docs/superpowers/specs/2026-05-02-reference-stability-goal-design.md
```

Expected: the spec states that agent filing-grounded verification may mark reference deals `verified`, generated proof artifacts are in scope, target extraction is out of scope, and stale cleanup is required.

- [ ] **Step 3: Snapshot reference state**

Run:

```bash
jq '.deals | to_entries[] | select(.key | IN("providence-worcester","medivation","imprivata","zep","petsmart-inc","penford","mac-gray","saks","stec")) | {slug:.key,status:.value.status,flag_count:.value.flag_count,last_run_id:.value.last_run_id,last_verified_by:.value.last_verified_by,last_verified_at:.value.last_verified_at}' state/progress.json
```

Expected: output lists exactly the nine reference slugs. Any slug not `verified` is a release blocker until fixed and agent-verified.

- [ ] **Step 4: Run baseline tests**

Run:

```bash
python -m pytest -q
```

Expected: record exit code and failing tests. If tests fail, continue with this plan; do not treat baseline failure as terminal.

- [ ] **Step 5: Run baseline reference dry-run**

Run:

```bash
python -m pipeline.run_pool --filter reference --workers 4 --dry-run
```

Expected: exit 0 and selection contains only the nine reference slugs. If it fails, fix selection/gate code before any live model calls.

- [ ] **Step 6: Run baseline reconcile**

Run:

```bash
python -m pipeline.reconcile --scope reference
```

Expected: record exit code and all reported blockers. Reconcile may fail before the release work is complete.

- [ ] **Step 7: Commit nothing**

Run:

```bash
git status --short
```

Expected: no new staged files from Task 1.

---

### Task 2: Pin Agent Verification Authority In Live Contracts

**Files:**
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `SKILL.md`
- Modify: `docs/linkflow-extraction-guide.md`
- Create: `tests/test_reference_verification_contract.py`

- [ ] **Step 1: Write failing contract test**

Create `tests/test_reference_verification_contract.py` with:

```python
from __future__ import annotations

from pathlib import Path


CONTRACT_FILES = (
    Path("AGENTS.md"),
    Path("CLAUDE.md"),
    Path("SKILL.md"),
    Path("docs/linkflow-extraction-guide.md"),
)


def test_live_contracts_define_agent_verification_authority():
    required_phrases = (
        "agent filing-grounded verification",
        "quality_reports/reference_verification/{slug}.md",
        "must not mark a deal verified solely because the model output passes schema validation",
    )
    for path in CONTRACT_FILES:
        text = path.read_text()
        missing = [phrase for phrase in required_phrases if phrase not in text]
        assert not missing, f"{path} missing {missing}"
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
python -m pytest tests/test_reference_verification_contract.py -q
```

Expected: FAIL because the live contract files do not yet include the new agent verification authority language.

- [ ] **Step 3: Update `AGENTS.md` status contract**

In the `State and Output Contracts` status list, replace the `verified` bullet with this text:

```markdown
- `verified`: a reference deal verified against filing text. During this
  reference-stability release process, `verified` may be set by Austin or by
  agent filing-grounded verification when
  `quality_reports/reference_verification/{slug}.md` exists, every AI-vs-Alex
  disagreement is adjudicated against the filing text and rulebook, and the
  report concludes `VERIFIED`. The agent must not mark a deal verified solely
  because the model output passes schema validation.
```

In the `Reference-Set Gate` section, replace "manually verified" language with:

```markdown
Reference-set work is complete only when all nine deals are verified against
the filings by Austin or by agent filing-grounded verification, every
AI-vs-Alex disagreement is adjudicated, hard invariants pass, and the stability
harness produces a `target_gate_proof_v1` classifying the archive as
`STABLE_FOR_REFERENCE_REVIEW` across at least three archived reference runs per
slug under unchanged prompt/schema/rulebook hashes.
```

- [ ] **Step 4: Mirror the `AGENTS.md` contract in `CLAUDE.md`**

Apply the same two text replacements from Step 3 to `CLAUDE.md`.

- [ ] **Step 5: Update `SKILL.md` status contract**

In the status section, replace the existing `verified` bullet with:

```markdown
- `verified` — a reference deal verified against filing text. During this
  reference-stability release process, `verified` may be set by Austin or by
  agent filing-grounded verification when
  `quality_reports/reference_verification/{slug}.md` exists, every AI-vs-Alex
  disagreement is adjudicated against the filing text and rulebook, and the
  report concludes `VERIFIED`. The agent must not mark a deal verified solely
  because the model output passes schema validation. On target deals this
  status is never used.
```

- [ ] **Step 6: Update `docs/linkflow-extraction-guide.md` target-release protocol**

In the `Stability And Target Release` section, replace the verified prerequisite with:

```markdown
- all nine reference deals are `verified` through Austin review or agent
  filing-grounded verification documented at
  `quality_reports/reference_verification/{slug}.md`;
```

Add this sentence in the same section:

```markdown
The agent must not mark a deal verified solely because the model output passes
schema validation; every AI-vs-Alex disagreement must be adjudicated against
filing text before `verified` is set.
```

- [ ] **Step 7: Run contract test**

Run:

```bash
python -m pytest tests/test_reference_verification_contract.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit contract update**

Run:

```bash
git add AGENTS.md CLAUDE.md SKILL.md docs/linkflow-extraction-guide.md tests/test_reference_verification_contract.py
git commit -m "docs: allow agent reference verification"
```

Expected: commit succeeds and includes only the five listed files.

---

### Task 3: Add Verification Report Checker

**Files:**
- Create: `quality_reports/reference_verification/README.md`
- Create: `scripts/check_reference_verification.py`
- Create: `tests/test_reference_verification_reports.py`

- [ ] **Step 1: Write failing checker tests**

Create `tests/test_reference_verification_reports.py` with:

```python
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
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
python -m pytest tests/test_reference_verification_reports.py -q
```

Expected: FAIL because `scripts/check_reference_verification.py` does not exist.

- [ ] **Step 3: Implement checker**

Create `scripts/check_reference_verification.py` with:

```python
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


REFERENCE_SLUGS: tuple[str, ...] = (
    "providence-worcester",
    "medivation",
    "imprivata",
    "zep",
    "petsmart-inc",
    "penford",
    "mac-gray",
    "saks",
    "stec",
)

REQUIRED_SECTIONS: tuple[str, ...] = (
    "## Run Metadata",
    "## Commands",
    "## Extraction And Flag Summary",
    "## AI-vs-Alex Diff Ledger",
    "## Filing Evidence Review",
    "## Contract Updates",
    "## Conclusion",
)


@dataclass(frozen=True)
class VerificationFailure:
    slug: str
    path: Path
    message: str


def report_path(repo_root: Path, slug: str) -> Path:
    return repo_root / "quality_reports" / "reference_verification" / f"{slug}.md"


def validate_report_text(slug: str, path: Path, text: str) -> list[VerificationFailure]:
    failures: list[VerificationFailure] = []
    title = f"# {slug} Agent Verification"
    if title not in text:
        failures.append(VerificationFailure(slug, path, f"missing title: {title}"))
    for section in REQUIRED_SECTIONS:
        if section not in text:
            failures.append(VerificationFailure(slug, path, f"missing section: {section}"))
    if "Conclusion: VERIFIED" not in text:
        failures.append(
            VerificationFailure(
                slug,
                path,
                "verification report must conclude with 'Conclusion: VERIFIED'",
            )
        )
    if "Conclusion: BLOCKED" in text:
        failures.append(VerificationFailure(slug, path, "verification report still has blockers"))
    if "Filing page" not in text and "source_page" not in text:
        failures.append(
            VerificationFailure(
                slug,
                path,
                "verification report must cite filing pages or source_page evidence",
            )
        )
    return failures


def check_reports(
    repo_root: Path,
    *,
    slugs: Sequence[str] = REFERENCE_SLUGS,
) -> list[VerificationFailure]:
    failures: list[VerificationFailure] = []
    for slug in slugs:
        path = report_path(repo_root, slug)
        if not path.exists():
            failures.append(VerificationFailure(slug, path, "missing verification report"))
            continue
        failures.extend(validate_report_text(slug, path, path.read_text()))
    return failures


def _parse_slugs(value: str | None) -> tuple[str, ...]:
    if not value:
        return REFERENCE_SLUGS
    return tuple(item.strip() for item in value.split(",") if item.strip())


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--slugs", help="Comma-separated slug list. Defaults to all reference slugs.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    failures = check_reports(args.repo_root, slugs=_parse_slugs(args.slugs))
    for failure in failures:
        print(f"{failure.slug}: {failure.path}: {failure.message}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Add verification README**

Create `quality_reports/reference_verification/README.md` with:

````markdown
# Reference Verification Reports

This directory stores canonical agent filing-grounded verification reports for
the nine reference deals. A reference deal may be marked `verified` by the agent
only when its report exists, every AI-vs-Alex disagreement is adjudicated
against filing text and the rulebook, and the report concludes
`Conclusion: VERIFIED`.

Each report must be named:

```text
quality_reports/reference_verification/{slug}.md
```

Required sections:

- `# {slug} Agent Verification`
- `## Run Metadata`
- `## Commands`
- `## Extraction And Flag Summary`
- `## AI-vs-Alex Diff Ledger`
- `## Filing Evidence Review`
- `## Contract Updates`
- `## Conclusion`

Run this check before marking any reference deal verified:

```bash
python scripts/check_reference_verification.py --slugs {slug}
```

Run this check before final release:

```bash
python scripts/check_reference_verification.py
```
````

- [ ] **Step 5: Run checker tests**

Run:

```bash
python -m pytest tests/test_reference_verification_reports.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit checker**

Run:

```bash
git add quality_reports/reference_verification/README.md scripts/check_reference_verification.py tests/test_reference_verification_reports.py
git commit -m "test: require reference verification reports"
```

Expected: commit succeeds and includes only the three listed files.

---

### Task 4: Add Explicit Verified-State Marker

**Files:**
- Create: `scripts/mark_reference_verified.py`
- Create: `tests/test_mark_reference_verified.py`
- Modify: `SKILL.md`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Write failing marker tests**

Create `tests/test_mark_reference_verified.py` with:

```python
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
    (state_dir / "progress.json").write_text(json.dumps({
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
                "notes": "hard=0 soft=0 info=0",
            }
        },
    }))


def _write_extraction(root: Path, hard_flag: bool = False) -> None:
    out = root / "output" / "extractions"
    out.mkdir(parents=True)
    flags = [{"severity": "hard", "code": "bad", "reason": "bad"}] if hard_flag else []
    (out / "medivation.json").write_text(json.dumps({
        "deal": {"deal_flags": flags},
        "events": [{"flags": []}],
    }))


def _write_report(root: Path, text: str = GOOD_REPORT) -> None:
    path = root / "quality_reports" / "reference_verification" / "medivation.md"
    path.parent.mkdir(parents=True)
    path.write_text(text)


def test_mark_verified_updates_reference_progress(tmp_path):
    _write_progress(tmp_path)
    _write_extraction(tmp_path)
    _write_report(tmp_path)

    mark_reference_verified.mark_verified(tmp_path, "medivation", reviewer="Codex agent", now="2026-05-02T12:00:00Z")

    progress = json.loads((tmp_path / "state" / "progress.json").read_text())
    deal = progress["deals"]["medivation"]
    assert deal["status"] == "verified"
    assert deal["last_verified_by"] == "Codex agent"
    assert deal["last_verified_at"] == "2026-05-02T12:00:00Z"
    assert deal["verification_report"] == "quality_reports/reference_verification/medivation.md"


def test_mark_verified_rejects_hard_flags(tmp_path):
    _write_progress(tmp_path)
    _write_extraction(tmp_path, hard_flag=True)
    _write_report(tmp_path)

    try:
        mark_reference_verified.mark_verified(tmp_path, "medivation", reviewer="Codex agent", now="2026-05-02T12:00:00Z")
    except mark_reference_verified.MarkVerifiedError as exc:
        assert "hard flags" in str(exc)
    else:
        raise AssertionError("expected MarkVerifiedError")


def test_mark_verified_rejects_missing_report(tmp_path):
    _write_progress(tmp_path)
    _write_extraction(tmp_path)

    try:
        mark_reference_verified.mark_verified(tmp_path, "medivation", reviewer="Codex agent", now="2026-05-02T12:00:00Z")
    except mark_reference_verified.MarkVerifiedError as exc:
        assert "verification report failed checks" in str(exc)
    else:
        raise AssertionError("expected MarkVerifiedError")
```

- [ ] **Step 2: Run failing marker tests**

Run:

```bash
python -m pytest tests/test_mark_reference_verified.py -q
```

Expected: FAIL because `scripts/mark_reference_verified.py` does not exist.

- [ ] **Step 3: Implement marker**

Create `scripts/mark_reference_verified.py` with:

```python
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Iterable

from scripts.check_reference_verification import check_reports, report_path


class MarkVerifiedError(RuntimeError):
    pass


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _hard_flags(payload: dict[str, Any]) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    deal = payload.get("deal")
    if isinstance(deal, dict):
        flags.extend(
            flag for flag in deal.get("deal_flags", [])
            if isinstance(flag, dict) and flag.get("severity") == "hard"
        )
    events = payload.get("events")
    if isinstance(events, list):
        for event in events:
            if not isinstance(event, dict):
                continue
            flags.extend(
                flag for flag in event.get("flags", [])
                if isinstance(flag, dict) and flag.get("severity") == "hard"
            )
    return flags


def mark_verified(repo_root: Path, slug: str, *, reviewer: str, now: str | None = None) -> None:
    failures = check_reports(repo_root, slugs=(slug,))
    if failures:
        details = "; ".join(f"{failure.path}: {failure.message}" for failure in failures)
        raise MarkVerifiedError(f"verification report failed checks: {details}")

    progress_path = repo_root / "state" / "progress.json"
    extraction_path = repo_root / "output" / "extractions" / f"{slug}.json"
    if not progress_path.exists():
        raise MarkVerifiedError(f"missing progress file: {progress_path}")
    if not extraction_path.exists():
        raise MarkVerifiedError(f"missing extraction file: {extraction_path}")

    progress = json.loads(progress_path.read_text())
    deal = progress.get("deals", {}).get(slug)
    if not isinstance(deal, dict):
        raise MarkVerifiedError(f"slug not found in progress: {slug}")
    if deal.get("is_reference") is not True:
        raise MarkVerifiedError(f"slug is not a reference deal: {slug}")

    extraction = json.loads(extraction_path.read_text())
    hard_flags = _hard_flags(extraction)
    if hard_flags:
        raise MarkVerifiedError(f"cannot mark {slug} verified with hard flags: {len(hard_flags)}")

    deal["status"] = "verified"
    deal["last_verified_by"] = reviewer
    deal["last_verified_at"] = now or _now_iso()
    deal["verification_report"] = f"quality_reports/reference_verification/{slug}.md"
    progress_path.write_text(json.dumps(progress, indent=2, sort_keys=False) + "\n")


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("slug")
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--reviewer", default="Codex agent")
    args = parser.parse_args(list(argv) if argv is not None else None)

    mark_verified(args.repo_root, args.slug, reviewer=args.reviewer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Document marker command in live contracts**

Add this command to `AGENTS.md`, `CLAUDE.md`, and `SKILL.md` near the reference verification/status contract:

```bash
python scripts/check_reference_verification.py --slugs <slug>
python scripts/mark_reference_verified.py <slug> --reviewer "Codex agent"
```

Explain beside the command that `mark_reference_verified.py` is allowed only for reference deals with no hard extraction flags and a completed verification report.

- [ ] **Step 5: Run marker tests**

Run:

```bash
python -m pytest tests/test_mark_reference_verified.py tests/test_reference_verification_contract.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit marker**

Run:

```bash
git add scripts/mark_reference_verified.py tests/test_mark_reference_verified.py AGENTS.md CLAUDE.md SKILL.md
git commit -m "feat: add reference verification marker"
```

Expected: commit succeeds and includes only the listed files.

---

### Task 5: Finish Or Replace The Live Extraction Architecture

**Files:**
- Allowed write scope after a failing test or reference-run blocker identifies current-contract work: `pipeline/`
- Allowed write scope after a failing test or reference-run blocker identifies current-contract work: `prompts/`
- Allowed write scope after a failing test or reference-run blocker identifies current-contract work: `rules/`
- Allowed write scope after a failing test or reference-run blocker identifies current-contract work: `tests/`
- Allowed write scope after a failing test or reference-run blocker identifies current-contract work: `docs/linkflow-extraction-guide.md`
- Allowed write scope after a failing test or reference-run blocker identifies current-contract work: `AGENTS.md`
- Allowed write scope after a failing test or reference-run blocker identifies current-contract work: `CLAUDE.md`
- Allowed write scope after a failing test or reference-run blocker identifies current-contract work: `SKILL.md`

- [ ] **Step 1: Run focused architecture tests**

Run:

```bash
python -m pytest tests/test_obligations.py tests/test_repair_conservation.py tests/llm/test_tools.py tests/llm/test_response_format.py tests/llm/test_extract.py tests/llm/test_contracts.py tests/llm/test_audit.py tests/test_run_pool.py tests/test_reconcile.py tests/test_stability.py tests/test_diff.py tests/test_prompt_contract.py -q
```

Expected: PASS before live reference runs. If any test fails, repair the implementation using failing tests first, then rerun this command.

- [ ] **Step 2: Execute any unfinished obligation-gated single-repair plan tasks**

If `docs/superpowers/plans/2026-05-01-obligation-gated-single-repair-implementation.md` exists and has unchecked tasks, execute the unchecked tasks that still describe the live architecture. Do not restore old staged repair behavior. Do not preserve prompt-only repair 1, targeted repair 2, loose JSON fallback, stale cache readers, or old audit shapes.

Run after completing those tasks:

```bash
python -m pytest -q
```

Expected: PASS.

- [ ] **Step 3: Guard against forbidden compatibility paths**

Run:

```bash
rg -n 'free-form JSON fallback|json_schema_used|previous_response_id|prompt-only repair 1|targeted repair 2|legacy cache|loose legacy|fallback reader|compatibility shim|repair_strategy.*staged' AGENTS.md CLAUDE.md SKILL.md docs prompts pipeline tests rules scoring scripts
```

Expected: no live-path references to forbidden compatibility behavior. Mentions that explicitly reject retired behavior are acceptable only when they state the old behavior is not supported.

- [ ] **Step 4: Commit architecture completion**

Run:

```bash
git status --short
git add pipeline prompts rules tests docs AGENTS.md CLAUDE.md SKILL.md scoring scripts
git status --short
git commit -m "feat: stabilize reference extraction pipeline"
```

Expected: commit succeeds. Before committing, inspect `git status --short` and remove unrelated files from the index with `git restore --staged <path>`.

---

### Task 6: Run Fresh Reference Extractions

**Files:**
- Modify generated: `output/extractions/{slug}.json`
- Modify generated: `output/audit/{slug}/latest.json`
- Create generated: `output/audit/{slug}/runs/{run_id}/`
- Modify generated: `state/progress.json`
- Modify generated: `state/flags.jsonl`

- [ ] **Step 1: Confirm secrets are environment-only**

Run:

```bash
python - <<'PY'
import os
print("OPENAI_API_KEY set:", bool(os.environ.get("OPENAI_API_KEY")))
print("OPENAI_BASE_URL:", os.environ.get("OPENAI_BASE_URL", ""))
PY
```

Expected: `OPENAI_API_KEY set: True` and `OPENAI_BASE_URL` is the Linkflow/NewAPI-compatible endpoint. Do not print the key.

- [ ] **Step 2: Dry-run reference selection**

Run:

```bash
python -m pipeline.run_pool --filter reference --workers 4 --dry-run
```

Expected: exit 0 and selected slugs are exactly the nine reference slugs.

- [ ] **Step 3: Run fresh reference batch**

Run:

```bash
python -m pipeline.run_pool \
  --filter reference \
  --workers 4 \
  --extract-model gpt-5.5 \
  --adjudicate-model gpt-5.5 \
  --extract-reasoning-effort high \
  --adjudicate-reasoning-effort high \
  --re-extract
```

Expected: command completes without provider/runtime failure. If Linkflow capacity or idle timeout failures occur, rerun with `--workers 2`, then `--workers 1`. Do not change model output contracts to work around provider failures.

- [ ] **Step 4: Inspect reference statuses**

Run:

```bash
jq '.deals | to_entries[] | select(.key | IN("providence-worcester","medivation","imprivata","zep","petsmart-inc","penford","mac-gray","saks","stec")) | {slug:.key,status:.value.status,flag_count:.value.flag_count,last_run_id:.value.last_run_id,last_run:.value.last_run}' state/progress.json
```

Expected: no slug has `status="failed"`. Any `validated` reference slug has hard flags and must be fixed or rerun before final verification.

- [ ] **Step 5: Run per-slug diff reports**

Run:

```bash
python scoring/diff.py --slug providence-worcester
python scoring/diff.py --slug medivation
python scoring/diff.py --slug imprivata
python scoring/diff.py --slug zep
python scoring/diff.py --slug petsmart-inc
python scoring/diff.py --slug penford
python scoring/diff.py --slug mac-gray
python scoring/diff.py --slug saks
python scoring/diff.py --slug stec
```

Expected: each command completes and produces reviewable AI-vs-Alex disagreement output. Every disagreement must be resolved in the verification reports.

- [ ] **Step 6: Reconcile generated artifacts**

Run:

```bash
python -m pipeline.reconcile --scope reference
```

Expected: exit 0 before any deal is marked `verified`. If it fails, fix the reported current-contract issue, rerun affected reference slugs with `--re-extract`, and rerun reconcile.

- [ ] **Step 7: Commit extraction batch only after reconcile is clean**

Run:

```bash
git status --short state output quality_reports
```

Expected: generated state/output/audit changes are visible. Do not commit yet if any reference slug is failed, hard-flagged, or unreconciled.

---

### Task 7: Create Verification Reports And Mark All Nine References Verified

**Files:**
- Create: `quality_reports/reference_verification/providence-worcester.md`
- Create: `quality_reports/reference_verification/medivation.md`
- Create: `quality_reports/reference_verification/imprivata.md`
- Create: `quality_reports/reference_verification/zep.md`
- Create: `quality_reports/reference_verification/petsmart-inc.md`
- Create: `quality_reports/reference_verification/penford.md`
- Create: `quality_reports/reference_verification/mac-gray.md`
- Create: `quality_reports/reference_verification/saks.md`
- Create: `quality_reports/reference_verification/stec.md`
- Modify: `state/progress.json`

- [ ] **Step 1: Write verification report for each slug**

For each reference slug, create `quality_reports/reference_verification/{slug}.md` with the exact sections required by `quality_reports/reference_verification/README.md`. Use actual run IDs, audit paths, row counts, flag counts, diff output, and filing page citations from the current run.

Each report must end with:

```markdown
## Conclusion

Conclusion: VERIFIED
```

Expected: nine Markdown files exist under `quality_reports/reference_verification/`.

- [ ] **Step 2: Validate report shape**

Run:

```bash
python scripts/check_reference_verification.py
```

Expected: exit 0. Any missing section, blocker conclusion, or missing filing citation fails the check.

- [ ] **Step 3: Mark each reference verified**

Run:

```bash
python scripts/mark_reference_verified.py providence-worcester --reviewer "Codex agent"
python scripts/mark_reference_verified.py medivation --reviewer "Codex agent"
python scripts/mark_reference_verified.py imprivata --reviewer "Codex agent"
python scripts/mark_reference_verified.py zep --reviewer "Codex agent"
python scripts/mark_reference_verified.py petsmart-inc --reviewer "Codex agent"
python scripts/mark_reference_verified.py penford --reviewer "Codex agent"
python scripts/mark_reference_verified.py mac-gray --reviewer "Codex agent"
python scripts/mark_reference_verified.py saks --reviewer "Codex agent"
python scripts/mark_reference_verified.py stec --reviewer "Codex agent"
```

Expected: every command exits 0. A hard flag or missing verification report blocks the status update.

- [ ] **Step 4: Confirm all nine statuses**

Run:

```bash
jq '.deals | to_entries[] | select(.key | IN("providence-worcester","medivation","imprivata","zep","petsmart-inc","penford","mac-gray","saks","stec")) | {slug:.key,status:.value.status,last_verified_by:.value.last_verified_by,verification_report:.value.verification_report}' state/progress.json
```

Expected: each slug has `status="verified"`, `last_verified_by="Codex agent"`, and `verification_report="quality_reports/reference_verification/{slug}.md"`.

- [ ] **Step 5: Reconcile verified state**

Run:

```bash
python scripts/check_reference_verification.py
python -m pipeline.reconcile --scope reference
```

Expected: both commands exit 0.

- [ ] **Step 6: Commit verification reports and state**

Run:

```bash
git add quality_reports/reference_verification state/progress.json state/flags.jsonl output/extractions
git status --short
git commit -m "data: verify nine reference extractions"
```

Expected: commit succeeds. Before committing, inspect staged files and unstage unrelated changes.

---

### Task 8: Produce Three-Run Stability Proof

**Files:**
- Create generated: `quality_reports/stability/target-release-proof.json`
- Modify generated: `output/audit/{slug}/latest.json`
- Create generated: selected `output/audit/{slug}/runs/{run_id}/`
- Modify generated: `state/progress.json`
- Modify generated: `state/flags.jsonl`

- [ ] **Step 1: Confirm no contract changes are pending**

Run:

```bash
git status --short AGENTS.md CLAUDE.md SKILL.md docs prompts rules pipeline tests scoring scripts
```

Expected: no uncommitted code, prompt, rulebook, schema, docs, or test changes. Stability runs must happen under unchanged hashes.

- [ ] **Step 2: Run enough fresh reference batches for three eligible runs**

Run this full command until each reference slug has at least three eligible immutable runs under unchanged contract hashes:

```bash
python -m pipeline.run_pool \
  --filter reference \
  --workers 4 \
  --extract-model gpt-5.5 \
  --adjudicate-model gpt-5.5 \
  --extract-reasoning-effort high \
  --adjudicate-reasoning-effort high \
  --re-extract
```

Expected: each batch completes without provider/runtime failure. If provider capacity requires lower concurrency, use `--workers 2` or `--workers 1` and record the change in the final summary.

- [ ] **Step 3: Re-run verification checker and marker after final batch**

Run:

```bash
python scripts/check_reference_verification.py
python scripts/mark_reference_verified.py providence-worcester --reviewer "Codex agent"
python scripts/mark_reference_verified.py medivation --reviewer "Codex agent"
python scripts/mark_reference_verified.py imprivata --reviewer "Codex agent"
python scripts/mark_reference_verified.py zep --reviewer "Codex agent"
python scripts/mark_reference_verified.py petsmart-inc --reviewer "Codex agent"
python scripts/mark_reference_verified.py penford --reviewer "Codex agent"
python scripts/mark_reference_verified.py mac-gray --reviewer "Codex agent"
python scripts/mark_reference_verified.py saks --reviewer "Codex agent"
python scripts/mark_reference_verified.py stec --reviewer "Codex agent"
```

Expected: all commands exit 0. The final batch may update `last_run_id`; the verification reports must still refer to the run IDs actually reviewed, or must be updated to the final reviewed run before marking `verified`.

- [ ] **Step 4: Write stability proof**

Run:

```bash
python -m pipeline.stability \
  --scope reference \
  --runs 3 \
  --json \
  --write quality_reports/stability/target-release-proof.json
```

Expected: exit 0 and JSON contains `classification: STABLE_FOR_REFERENCE_REVIEW`, `requested_runs >= 3`, and at least three selected immutable run IDs for every reference slug.

- [ ] **Step 5: Reconcile final proof**

Run:

```bash
python -m pipeline.reconcile --scope reference
```

Expected: exit 0.

- [ ] **Step 6: Commit proof-supporting generated artifacts**

Run:

```bash
git status --short state output quality_reports
```

Stage only:

- `state/progress.json`
- `state/flags.jsonl`
- `output/extractions/{slug}.json` for the nine reference slugs
- `output/audit/{slug}/latest.json` for the nine reference slugs
- `output/audit/{slug}/runs/{run_id}/` directories selected by `quality_reports/stability/target-release-proof.json`
- current `output/audit/{slug}/runs/{last_run_id}/` directories for verified reference extractions
- `quality_reports/reference_verification/`
- `quality_reports/stability/target-release-proof.json`

Run:

```bash
git commit -m "data: add reference stability proof"
```

Expected: commit succeeds. Do not stage stale experiment reports or unrelated target artifacts.

---

### Task 9: Deep Stale Cleanup And Secret Scan

**Files:**
- Delete or rewrite stale files found by this task
- Create: `quality_reports/reference_stability_cleanup.md`

- [ ] **Step 1: Search for retired architecture prose**

Run:

```bash
rg -n 'prompt-only repair 1|targeted repair 2|two-turn repair|staged repair|legacy cache|json_schema_used|schema-used audit boolean|free-form JSON fallback|previous_response_id|external agent loop|manually marked `verified`|Austin manually verified' AGENTS.md CLAUDE.md SKILL.md docs prompts rules pipeline tests scoring scripts quality_reports
```

Expected: matches are either deleted or rewritten unless the text explicitly says the retired behavior is unsupported.

- [ ] **Step 2: Search for stale generated reports**

Run:

```bash
find quality_reports -maxdepth 3 -type f | sort
```

Expected: remove or rewrite stale one-off reports that no longer represent the current live contract. Preserve current reference verification reports, current stability proof, and the cleanup report.

- [ ] **Step 3: Create cleanup record**

Create `quality_reports/reference_stability_cleanup.md` with:

```markdown
# Reference Stability Cleanup

## Deleted Files

List every stale file deleted during the reference-stability release work.

## Rewritten Files

List every stale contract/report file rewritten to the live architecture.

## Preserved Generated Artifacts

List selected audit run directories, extraction files, state files, verification
reports, and stability proof artifacts intentionally committed for the release.

## Secret Scan

Record the exact secret-scan command and result.
```

- [ ] **Step 4: Run secret scan without printing secrets**

Run:

```bash
git grep -nE 'sk-[A-Za-z0-9_-]{20,}|OPENAI_API_KEY=.*[A-Za-z0-9_-]{20,}' -- . ':!.env' ':!*.png' ':!*.jpg' ':!*.jpeg' ':!*.pdf'
```

Expected: no output. If any literal key appears in a tracked or to-be-staged artifact, stop and require key rotation before continuing.

- [ ] **Step 5: Run final stale scan**

Run:

```bash
rg -n 'prompt-only repair 1|targeted repair 2|two-turn repair|staged repair|legacy cache|json_schema_used|schema-used audit boolean|free-form JSON fallback|previous_response_id|manually marked `verified`|Austin manually verified' AGENTS.md CLAUDE.md SKILL.md docs prompts rules pipeline tests scoring scripts quality_reports
```

Expected: no stale live-contract references remain.

- [ ] **Step 6: Commit cleanup**

Run:

```bash
git add -A AGENTS.md CLAUDE.md SKILL.md docs prompts rules pipeline tests scoring scripts quality_reports state output
git status --short
git commit -m "chore: clean stale reference pipeline artifacts"
```

Expected: commit succeeds. Inspect staged files before committing; unstage unrelated user work and target-deal artifacts.

---

### Task 10: Final Release Verification

**Files:**
- Read all release artifacts
- Modify only if a final check fails

- [ ] **Step 1: Run full tests**

Run:

```bash
python -m pytest -q
```

Expected: PASS.

- [ ] **Step 2: Run verification report checker**

Run:

```bash
python scripts/check_reference_verification.py
```

Expected: PASS.

- [ ] **Step 3: Run reconcile**

Run:

```bash
python -m pipeline.reconcile --scope reference
```

Expected: PASS.

- [ ] **Step 4: Run stability proof command**

Run:

```bash
python -m pipeline.stability \
  --scope reference \
  --runs 3 \
  --json \
  --write quality_reports/stability/target-release-proof.json
```

Expected: PASS and `quality_reports/stability/target-release-proof.json` remains classified `STABLE_FOR_REFERENCE_REVIEW`.

- [ ] **Step 5: Confirm target gate status**

Run:

```bash
python - <<'PY'
from pipeline.run_pool import target_gate_status
from pipeline.run_pool import TARGET_GATE_PROOF
from pipeline.run_pool import _load_progress

status = target_gate_status(_load_progress(), TARGET_GATE_PROOF)
print("is_open:", status.is_open)
print("reference_verified:", status.reference_verified)
print("missing:", ",".join(status.missing_verified_references))
print("proof:", status.stability_proof_reason)
PY
```

Expected:

```text
is_open: True
reference_verified: 9
missing:
proof: stability proof accepted
```

- [ ] **Step 6: Final secret scan**

Run:

```bash
git grep -nE 'sk-[A-Za-z0-9_-]{20,}|OPENAI_API_KEY=.*[A-Za-z0-9_-]{20,}' -- . ':!.env' ':!*.png' ':!*.jpg' ':!*.jpeg' ':!*.pdf'
```

Expected: no output.

- [ ] **Step 7: Confirm clean committed worktree**

Run:

```bash
git status --short
```

Expected: no output except ignored local secret files, which do not appear in `git status --short`.

- [ ] **Step 8: Produce final operator summary**

In the final response, include:

- commits created;
- exact model and reasoning settings;
- exact commands run and pass/fail results;
- selected run IDs from `quality_reports/stability/target-release-proof.json`;
- confirmation that all nine reference deals are `verified`;
- confirmation that reconcile and stability passed;
- confirmation that target extraction was not run;
- any residual risk.

---

## Self-Review Checklist

Before claiming this plan is complete, verify:

- Every success criterion from `docs/superpowers/specs/2026-05-02-reference-stability-goal-design.md` maps to a task above.
- The plan contains no unresolved markers or compatibility fallback step.
- The plan requires live contract updates for agent verification authority.
- The plan requires complete AI-vs-Alex disagreement adjudication in verification reports.
- The plan stages only selected proof-supporting audit run directories.
- The plan includes stale cleanup and a secret scan before final completion.
- The plan keeps target-deal extraction out of scope.
