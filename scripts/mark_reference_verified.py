from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.check_reference_verification import check_reports
from pipeline import core


class MarkVerifiedError(RuntimeError):
    pass


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _hard_flags(payload: dict[str, Any]) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    deal = payload.get("deal")
    if isinstance(deal, dict):
        flags.extend(
            flag
            for flag in deal.get("deal_flags", [])
            if isinstance(flag, dict) and flag.get("severity") == "hard"
        )
    graph = payload.get("graph")
    if isinstance(graph, dict):
        validation_flags = graph.get("validation_flags")
        if isinstance(validation_flags, list):
            flags.extend(
                flag
                for flag in validation_flags
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
    if deal.get("status") not in core.TRUSTED_STATUSES:
        raise MarkVerifiedError(
            f"cannot mark {slug} verified because status {deal.get('status')!r} "
            "is not a trusted extraction status"
        )

    extraction = json.loads(extraction_path.read_text())
    current_run_id = deal.get("last_run_id")
    extraction_run_id = extraction.get("run_id") or extraction.get("deal", {}).get("last_run_id")
    if not isinstance(current_run_id, str) or not current_run_id:
        raise MarkVerifiedError(f"missing current run_id in progress for {slug}")
    if extraction_run_id != current_run_id:
        raise MarkVerifiedError(
            f"cannot mark {slug} verified because extraction run_id {extraction_run_id!r} "
            f"does not match progress last_run_id {current_run_id!r}"
        )
    hard_flags = _hard_flags(extraction)
    if hard_flags:
        raise MarkVerifiedError(f"cannot mark {slug} verified with hard flags: {len(hard_flags)}")

    if extraction.get("schema_version") != "deal_graph_v2":
        raise MarkVerifiedError(
            f"cannot mark {slug} verified because extraction schema_version "
            f"{extraction.get('schema_version')!r} is not deal_graph_v2"
        )
    deal["verified"] = True
    deal["last_verified_by"] = reviewer
    deal["last_verified_at"] = now or _now_iso()
    deal["last_verified_run_id"] = current_run_id
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
