"""scripts/synth_extraction.py — Generate a synthetic AI extraction for tests.

Until the real pipeline (`run.py`) is implemented, `scoring/diff.py` still
needs something to diff against. This script takes `reference/alex/{slug}.json`,
perturbs it in known ways, and writes the result to
`output/extractions/{slug}.json` so `diff.py` can be exercised end-to-end.

The output is NOT a real AI extraction — it is a test fixture. Four
perturbations, each designed to exercise a different diff code path:

    1. Flip one bid_type (informal → formal) on a matched row.
    2. Nudge one bid_value_pershare by ~0.5$ on another matched row.
    3. Add an AI-only row (synthetic NDA on an earlier date).
    4. Drop one row that Alex has (simulate an AI miss).

Plus one deal-level disagreement (DateEffective off by 1 day).

USAGE
-----
    python scripts/synth_extraction.py --slug medivation
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REFERENCE_DIR = REPO_ROOT / "reference" / "alex"
EXTRACTION_DIR = REPO_ROOT / "output" / "extractions"


def _add_ai_fields(events: list[dict]) -> None:
    """Stamp each row with placeholder AI-only fields."""
    for ev in events:
        ev["source_quote"] = "placeholder verbatim passage from the filing."
        ev["source_page"] = 42


def perturb_medivation(payload: dict) -> dict:
    ai = copy.deepcopy(payload)
    _add_ai_fields(ai["events"])

    # 1. Flip Pfizer 8/8 informal → formal.
    for ev in ai["events"]:
        if ev["bidder_alias"] == "Pfizer" and ev["bid_date_precise"] == "2016-08-08":
            ev["bid_type"] = "formal"

    # 2. Nudge Pfizer 8/20 formal bid 81.5 → 82.0.
    for ev in ai["events"]:
        if (ev["bidder_alias"] == "Pfizer"
                and ev["bid_date_precise"] == "2016-08-20"
                and ev.get("bid_value_pershare") == 81.5):
            ev["bid_value_pershare"] = 82.0

    # 3. Add AI-only synthetic NDA.
    ai["events"].append({
        "BidderID": 99,
        "bidder_name": "bidder_ai_extra",
        "bidder_alias": "Hypothetical Strategic A",
        "bidder_type": {"base": "s", "non_us": False, "public": True, "note": None},
        "bid_note": "NDA",
        "bid_type": None,
        "bid_date_precise": "2016-07-01",
        "bid_date_rough": None,
        "bid_value": None, "bid_value_pershare": None,
        "bid_value_lower": None, "bid_value_upper": None,
        "bid_value_unit": None,
        "source_quote": (
            "On July 1, 2016, the Company and a financial sponsor executed "
            "a confidentiality agreement."
        ),
        "source_page": 45,
        "flags": [],
    })

    # 4. Drop Sanofi "Drop" 8/20 row (AI misses it).
    ai["events"] = [
        ev for ev in ai["events"]
        if not (ev.get("bidder_alias") == "Sanofi" and ev.get("bid_note") == "Drop")
    ]

    # Deal-level: 1-day DateEffective mismatch.
    ai["deal"]["DateEffective"] = "2016-09-29"
    # Scrub converter provenance flags — these are reference-JSON-only.
    ai["deal"]["deal_flags"] = []

    return ai


PERTURBERS = {
    "medivation": perturb_medivation,
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", required=True, help=f"one of {list(PERTURBERS)}")
    args = parser.parse_args()
    if args.slug not in PERTURBERS:
        parser.error(f"no perturber for {args.slug}; available: {list(PERTURBERS)}")

    ref_path = REFERENCE_DIR / f"{args.slug}.json"
    if not ref_path.exists():
        parser.error(f"reference JSON not found: {ref_path}. Run scripts/build_reference.py first.")

    ref = json.loads(ref_path.read_text())
    ai = PERTURBERS[args.slug](ref)

    EXTRACTION_DIR.mkdir(parents=True, exist_ok=True)
    out = EXTRACTION_DIR / f"{args.slug}.json"
    out.write_text(json.dumps(ai, indent=2, default=str))
    print(f"wrote {out.relative_to(REPO_ROOT)} with {len(ai['events'])} events")


if __name__ == "__main__":
    main()
