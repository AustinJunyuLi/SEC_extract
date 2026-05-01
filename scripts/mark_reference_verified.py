from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any, Iterable

from scripts.check_reference_verification import check_reports


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
    events = payload.get("events")
    if isinstance(events, list):
        for event in events:
            if not isinstance(event, dict):
                continue
            flags.extend(
                flag
                for flag in event.get("flags", [])
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
