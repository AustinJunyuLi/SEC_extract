#!/usr/bin/env python3
"""Dedup state/flags.jsonl to only the most-recent finalize per deal.

WHY
---
`state/flags.jsonl` is append-only. A deal that was finalized more than once
has multiple runs' worth of flag lines on disk, while `state/progress.json`
only records the latest run's `flag_count`. The SKILL.md query contract says
to filter by `logged_at == last_run` (after the 1.3 fix). Before that fix,
the file could contain lines whose `logged_at` is strictly older than
`progress.last_run` and whose run is no longer referenced anywhere.

This script runs ONCE: it reads flags.jsonl, groups by deal, and for each
deal keeps only the lines whose `logged_at` matches the current
`progress.deals[deal].last_run`. Lines for deals no longer in progress.json
are dropped. Everything else is rewritten atomically.

USAGE
-----
    python scripts/dedup_flags_jsonl.py              # prints summary + writes
    python scripts/dedup_flags_jsonl.py --dry-run    # prints summary, no write

CONSTRAINTS
-----------
- Idempotent: running twice on an already-clean file is a no-op.
- Atomic: writes to a tmp file and os.replace()'s in, so a crash mid-run
  doesn't corrupt flags.jsonl.
- Fail-loud: malformed lines in flags.jsonl raise; they should not be
  silently dropped.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FLAGS_PATH = REPO_ROOT / "state" / "flags.jsonl"
PROGRESS_PATH = REPO_ROOT / "state" / "progress.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Print summary without writing.")
    args = parser.parse_args()

    if not FLAGS_PATH.exists():
        print(f"no flags.jsonl at {FLAGS_PATH}; nothing to do")
        return 0
    if not PROGRESS_PATH.exists():
        print(f"missing progress.json at {PROGRESS_PATH}", file=sys.stderr)
        return 1

    progress = json.loads(PROGRESS_PATH.read_text())
    last_run_by_deal = {
        slug: entry.get("last_run")
        for slug, entry in (progress.get("deals") or {}).items()
        if entry.get("last_run") is not None
    }

    raw_lines = FLAGS_PATH.read_text().splitlines()
    by_deal: dict[str, list[tuple[str, str]]] = defaultdict(list)
    orphans: list[str] = []

    for line_no, raw in enumerate(raw_lines, start=1):
        raw = raw.strip()
        if not raw:
            continue
        entry = json.loads(raw)  # fail-loud on malformed lines
        deal = entry.get("deal")
        logged_at = entry.get("logged_at")
        if not deal or not logged_at:
            raise ValueError(
                f"flags.jsonl line {line_no} missing required 'deal' or 'logged_at'"
            )
        if deal not in last_run_by_deal:
            orphans.append(deal)
            continue
        by_deal[deal].append((logged_at, raw))

    kept_lines: list[str] = []
    dropped_count = 0
    summary: list[tuple[str, int, int]] = []
    for deal, lines in by_deal.items():
        target = last_run_by_deal[deal]
        kept = [raw for (ts, raw) in lines if ts == target]
        dropped = len(lines) - len(kept)
        dropped_count += dropped
        summary.append((deal, len(lines), len(kept)))
        kept_lines.extend(kept)

    summary.sort()
    print(f"flags.jsonl input lines: {len(raw_lines)}")
    print(f"  kept (current run only): {len(kept_lines)}")
    print(f"  dropped (stale runs):    {dropped_count}")
    print(f"  dropped (orphan deals):  {len(orphans)}")
    print()
    print(f"{'deal':30s} {'before':>8s} {'after':>8s} {'dropped':>8s}")
    for deal, before, after in summary:
        delta = before - after
        print(f"{deal:30s} {before:8d} {after:8d} {delta:8d}")

    if args.dry_run:
        print("\n--dry-run: not writing")
        return 0

    tmp = FLAGS_PATH.with_suffix(".jsonl.tmp")
    with tmp.open("w") as fh:
        if kept_lines:
            fh.write("\n".join(kept_lines) + "\n")
    os.replace(tmp, FLAGS_PATH)
    print(f"\nwrote {FLAGS_PATH} ({len(kept_lines)} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
