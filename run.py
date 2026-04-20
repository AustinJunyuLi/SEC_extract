"""run.py — CLI shim for the Python pieces of the extraction pipeline.

The LLM extraction and soft-flag adjudication run as **Claude Code subagents**
administered by the orchestrating conversation, not as API calls from Python.
This module handles the deterministic, non-LLM finalization:

  1. Read a subagent-produced raw extraction JSON from disk.
  2. Run pipeline.validate() on it.
  3. Merge flags, write output/extractions/{slug}.json, append
     state/flags.jsonl, update state/progress.json.
  4. Optionally commit.

USAGE
-----
    # Finalize a single deal from a subagent-produced JSON file:
    python run.py --slug medivation --raw-extraction /tmp/medivation.raw.json

    # Dry-run (validate only, do not write files):
    python run.py --slug medivation --raw-extraction /tmp/medivation.raw.json --dry-run

    # Print the Extractor subagent prompt (for piping into a subagent session):
    python run.py --slug medivation --print-extractor-prompt

STATUS SEMANTICS (mirrors SKILL.md)
-----------------------------------
  pending    — not yet run.
  validated  — Validator ran; has hard flags. Pipeline's terminal status for
               a deal requiring human review.
  passed     — Combined extractor + validator flags contain only soft/info.
  passed_clean — Combined extractor + validator flags are zero.
  failed     — Pipeline error (filing missing, malformed JSON, etc.).
  verified   — Austin manually read the filing and adjudicated every diff.
               Only set by the manual review workflow, never by this script.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pipeline

REPO_ROOT = Path(__file__).resolve().parent
PROGRESS_PATH = REPO_ROOT / "state" / "progress.json"


def finalize_deal(
    slug: str,
    raw_extraction: dict,
    dry_run: bool = False,
    commit: bool = True,
) -> pipeline.PipelineResult | None:
    """Run validator, merge flags, write output + state. Optionally commit."""
    filing = pipeline.load_filing(slug)

    if dry_run:
        result = pipeline.validate(raw_extraction, filing)
        final = pipeline.merge_flags(raw_extraction, result.row_flags, result.deal_flags)
        status, flag_count, notes = pipeline.summarize(final)
        print(f"[{slug}] dry-run: status={status} flag_count={flag_count} notes={notes}")
        if result.row_flags:
            print(f"  row flags ({len(result.row_flags)}):")
            for f in result.row_flags[:10]:
                print(f"    row {f.get('row_index')}: [{f['severity']}] {f['code']} — {f['reason']}")
            if len(result.row_flags) > 10:
                print(f"    ... and {len(result.row_flags) - 10} more")
        if result.deal_flags:
            print(f"  deal flags ({len(result.deal_flags)}):")
            for f in result.deal_flags:
                print(f"    [{f['severity']}] {f['code']} — {f['reason']}")
        return None

    result = pipeline.finalize(slug, raw_extraction, filing=filing)
    print(
        f"[{slug}] status={result.status} flag_count={result.flag_count} "
        f"notes={result.notes} -> {result.output_path.relative_to(REPO_ROOT)}"
    )

    if commit:
        commit_message = (
            f"deal={slug} status={result.status} flag_count={result.flag_count}"
        )
        try:
            subprocess.run(["git", "add", "-A"], cwd=REPO_ROOT, check=True)
            subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=REPO_ROOT, check=True,
            )
        except subprocess.CalledProcessError as e:
            print(f"[{slug}] git commit failed: {e}", file=sys.stderr)

    return result


def validate_slug(slug: str) -> None:
    if not PROGRESS_PATH.exists():
        raise FileNotFoundError(f"{PROGRESS_PATH} does not exist")
    state = json.loads(PROGRESS_PATH.read_text())
    if slug not in state["deals"]:
        raise KeyError(f"slug={slug!r} not in state/progress.json")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--slug", required=True, help="Deal slug (must exist in state/progress.json).")
    parser.add_argument(
        "--raw-extraction",
        type=Path,
        help=(
            "Path to a JSON file holding the subagent-produced raw extraction "
            "({deal, events}). Required unless --print-extractor-prompt."
        ),
    )
    parser.add_argument(
        "--print-extractor-prompt",
        action="store_true",
        help="Print the Extractor subagent prompt for the given slug and exit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the validator and print flags, but do not write files or commit.",
    )
    parser.add_argument(
        "--no-commit",
        action="store_true",
        help="Write output and state, but skip the git commit.",
    )
    args = parser.parse_args()

    if args.print_extractor_prompt:
        print(pipeline.build_extractor_prompt(args.slug))
        return 0

    if args.raw_extraction is None:
        parser.error("--raw-extraction is required (unless --print-extractor-prompt)")
    if not args.raw_extraction.exists():
        parser.error(f"--raw-extraction path does not exist: {args.raw_extraction}")

    validate_slug(args.slug)
    raw = json.loads(args.raw_extraction.read_text())
    finalize_deal(args.slug, raw, dry_run=args.dry_run, commit=not args.no_commit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
