"""Small projection CLI for deal_graph_v1 JSON snapshots."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .export import write_jsonl
from .project_estimation import project_estimation_rows
from .project_review import project_review_rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Project deal_graph_v1 rows from a snapshot.")
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--projection", choices=["review", "estimation", "bidder_cycle_baseline_v1"], default="estimation")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    graph = json.loads(args.snapshot.read_text())
    if args.projection == "review":
        rows = project_review_rows(graph)
    else:
        rows = project_estimation_rows(graph)
    if args.out:
        write_jsonl(rows, args.out)
    else:
        print(json.dumps(rows, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
