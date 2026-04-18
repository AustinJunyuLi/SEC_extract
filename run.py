"""run.py — Outer Ralph loop over deals.

Reads state/progress.json, iterates pending deals, invokes the per-deal
Extractor + Validator pipeline in a fresh context per deal, writes
output/extractions/{slug}.json, updates progress, and commits.

USAGE
-----
    python run.py --slug medivation          # single deal
    python run.py --reference-only           # all 9 reference deals
    python run.py --pending                  # every non-complete deal
    python run.py --slug medivation --dry-run

STATUS
------
Stub. The `run_pipeline(deal)` body is intentionally unimplemented until the
Stage 1 rulebook decisions and the Claude Agent SDK invocation pattern are
settled. The outer loop, state management, and commit logic are real and
runnable; they just don't do extraction yet.

ARCHITECTURE NOTE
-----------------
Per CLAUDE.md, each deal runs in a fresh Claude session. This file does not
maintain any cross-deal state beyond what is serialized to state/progress.json.
If you find yourself adding in-memory state that spans deals, stop — that
violates the Ralph discipline.

STATUS SEMANTICS
----------------
  pending    — not yet run.
  extracted  — Extractor emitted rows; Validator has not yet run.
  validated  — Validator ran; may have hard-error flags. Pipeline's terminal
               status for non-reference deals.
  verified   — Austin manually read the filing and adjudicated any AI-vs-Alex
               diff. Only set on reference deals, and only by the manual review
               workflow — the pipeline itself never writes this status.
  failed     — pipeline error (fetch, section-location, etc.).
"""

from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent
PROGRESS_PATH = REPO_ROOT / "state" / "progress.json"
FLAGS_PATH = REPO_ROOT / "state" / "flags.jsonl"
EXTRACTIONS_DIR = REPO_ROOT / "output" / "extractions"
RULES_DIR = REPO_ROOT / "rules"
PROMPTS_DIR = REPO_ROOT / "prompts"


@dataclass
class Deal:
    slug: str
    is_reference: bool
    target_name: str
    acquirer: str
    date_announced: str
    filing_url: str


@dataclass
class PipelineResult:
    status: str  # pending | extracted | validated | verified | failed
    flag_count: int
    notes: str
    rows: list[dict[str, Any]]
    flags: list[dict[str, Any]]


def load_progress() -> dict[str, Any]:
    with PROGRESS_PATH.open() as f:
        return json.load(f)


def save_progress(state: dict[str, Any]) -> None:
    state["updated"] = datetime.datetime.utcnow().isoformat() + "Z"
    with PROGRESS_PATH.open("w") as f:
        json.dump(state, f, indent=2, sort_keys=False)


def current_rulebook_sha() -> str | None:
    """git SHA of rules/ at current HEAD, or None if not a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD:rules"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def run_pipeline(deal: Deal) -> PipelineResult:
    """Invoke the Extractor + Validator pipeline on one deal.

    STUB. Intended integration surface:
      1. Fetch filing text from deal.filing_url.
      2. Invoke Extractor (Claude SDK) with prompts/extract.md + rules/*.md
         + filing text. Receive candidate rows JSON.
      3. Invoke Validator (Claude SDK) with prompts/validate.md +
         rules/invariants.md + candidate rows + filing text. Receive
         final rows + flags.
      4. Return PipelineResult. Pipeline's terminal status is `validated`
         (or `failed`); `verified` is set only by the manual review workflow.
    """
    raise NotImplementedError(
        "Pipeline not yet implemented. Stage 1 (rulebook) and Stage 2 "
        "(reference JSON + diff) must complete first. See CLAUDE.md."
    )


def process_deal(deal: Deal, state: dict[str, Any], dry_run: bool = False) -> None:
    print(f"[{deal.slug}] starting (reference={deal.is_reference})")

    if dry_run:
        print(f"[{deal.slug}] dry-run: skipping pipeline invocation")
        return

    try:
        result = run_pipeline(deal)
    except NotImplementedError as e:
        print(f"[{deal.slug}] pipeline stub: {e}")
        return
    except Exception as e:
        print(f"[{deal.slug}] failed: {e}", file=sys.stderr)
        state["deals"][deal.slug].update({
            "status": "failed",
            "notes": f"pipeline_error: {e}",
            "last_run": datetime.datetime.utcnow().isoformat() + "Z",
        })
        save_progress(state)
        return

    # Write extraction output.
    EXTRACTIONS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EXTRACTIONS_DIR / f"{deal.slug}.json"
    with out_path.open("w") as f:
        json.dump({"deal": deal.__dict__, "events": result.rows}, f, indent=2)

    # Append flags.
    with FLAGS_PATH.open("a") as f:
        for flag in result.flags:
            f.write(json.dumps({"deal": deal.slug, **flag}) + "\n")

    # Update progress. Pipeline never writes `verified` — only manual review does.
    if result.status == "verified":
        raise RuntimeError(
            f"[{deal.slug}] pipeline attempted to set status=verified; "
            "that status is reserved for the manual adjudication workflow."
        )
    state["deals"][deal.slug].update({
        "status": result.status,
        "flag_count": result.flag_count,
        "last_run": datetime.datetime.utcnow().isoformat() + "Z",
        "notes": result.notes,
    })
    save_progress(state)

    # Commit.
    commit_message = (
        f"deal={deal.slug} status={result.status} flags={result.flag_count}"
    )
    try:
        subprocess.run(["git", "add", "-A"], cwd=REPO_ROOT, check=True)
        subprocess.run(["git", "commit", "-m", commit_message], cwd=REPO_ROOT, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[{deal.slug}] git commit failed: {e}", file=sys.stderr)

    print(f"[{deal.slug}] done: status={result.status} flags={result.flag_count}")


def deals_to_process(state: dict[str, Any], args: argparse.Namespace) -> list[Deal]:
    selected = []
    for slug, info in state["deals"].items():
        if args.slug and slug != args.slug:
            continue
        if args.reference_only and not info.get("is_reference", False):
            continue
        if args.pending and info["status"] not in ("pending", "failed"):
            continue
        selected.append(Deal(
            slug=slug,
            is_reference=info.get("is_reference", False),
            target_name=info["target_name"],
            acquirer=info["acquirer"],
            date_announced=info["date_announced"],
            filing_url=info["filing_url"],
        ))
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description="Outer loop over deals.")
    parser.add_argument("--slug", help="Process one deal by slug.")
    parser.add_argument(
        "--reference-only",
        action="store_true",
        help="Process only the 9 Alex-reference deals (development regression).",
    )
    parser.add_argument("--pending", action="store_true", help="Process only pending/failed deals.")
    parser.add_argument("--dry-run", action="store_true", help="Skip pipeline invocation.")
    args = parser.parse_args()

    if not any([args.slug, args.reference_only, args.pending]):
        parser.error("specify --slug, --reference-only, or --pending")

    state = load_progress()
    state["rulebook_version"] = current_rulebook_sha()

    deals = deals_to_process(state, args)
    if not deals:
        print("no matching deals")
        return

    print(f"processing {len(deals)} deal(s)")
    for deal in deals:
        process_deal(deal, state, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
