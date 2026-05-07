"""Export an Alex-facing event-ledger CSV from latest deal_graph_v2 outputs."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline import core  # noqa: E402
from pipeline.deal_graph import ALEX_EVENT_LEDGER_FIELDS, project_alex_event_ledger  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Alex-facing event-ledger CSV.")
    parser.add_argument(
        "--scope",
        choices=("all", "reference", "targets"),
        default="all",
        help="Deal set to export from state/progress.json.",
    )
    parser.add_argument("--slugs", help="Comma-separated slugs. Overrides --scope.")
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "output" / "review_csv" / "alex_event_ledger.csv",
        help="Output CSV path.",
    )
    args = parser.parse_args()

    state = _read_json(core.PROGRESS_PATH)
    slugs = _select_slugs(state, scope=args.scope, slugs_arg=args.slugs)
    rows: list[dict[str, Any]] = []
    for slug in slugs:
        deal = state["deals"][slug]
        if deal.get("status") not in core.TRUSTED_STATUSES:
            raise SystemExit(f"{slug} has status={deal.get('status')!r}; export only trusted graph outputs")
        extraction = _read_json(core.EXTRACTIONS_DIR / f"{slug}.json")
        graph = extraction.get("graph")
        if not isinstance(graph, dict):
            raise SystemExit(f"{slug} latest extraction is missing graph object")
        rows.extend(project_alex_event_ledger(graph, deal_metadata=_deal_metadata(slug, deal)))

    _write_csv(rows, args.output)
    print(f"wrote {len(rows)} rows for {len(slugs)} deals to {args.output}")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
    except FileNotFoundError as exc:
        raise SystemExit(f"missing required input: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"unreadable JSON input: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"input JSON must be an object: {path}")
    return payload


def _select_slugs(state: dict[str, Any], *, scope: str, slugs_arg: str | None) -> list[str]:
    deals = state.get("deals")
    if not isinstance(deals, dict):
        raise SystemExit("state/progress.json missing deals object")
    if slugs_arg:
        slugs = [slug.strip() for slug in slugs_arg.split(",") if slug.strip()]
        missing = [slug for slug in slugs if slug not in deals]
        if missing:
            raise SystemExit("slug(s) not in state/progress.json: " + ", ".join(missing))
        return slugs
    if scope == "reference":
        return [slug for slug in core.REFERENCE_SLUGS if slug in deals]
    if scope == "targets":
        return [slug for slug, deal in deals.items() if isinstance(deal, dict) and deal.get("is_reference") is not True]
    return list(deals)


def _deal_metadata(slug: str, deal: dict[str, Any]) -> dict[str, str]:
    return {
        "deal_slug": slug,
        "TargetName": _cell(deal.get("target_name")),
        "Acquirer": _cell(deal.get("acquirer")),
        "DateAnnounced": _cell(deal.get("date_announced")),
    }


def _write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ALEX_EVENT_LEDGER_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _cell(value: Any) -> str:
    return "" if value is None else str(value)


if __name__ == "__main__":
    main()
