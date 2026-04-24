"""run.py — CLI shim for the Python pieces of the extraction pipeline.

The LLM extraction and soft-flag adjudication run as **Claude Code subagents**
administered by the orchestrating conversation, not as API calls from Python.
This module handles the deterministic, non-LLM finalization:

  1. Read a subagent-produced raw extraction JSON from disk.
  2. Run pipeline.validate() on it.
  3. Merge flags, write output/extractions/{slug}.json, append
     state/flags.jsonl, update state/progress.json.
  4. Optionally commit only the current deal's output/state files.

USAGE
-----
    # Finalize a single deal from a subagent-produced JSON file:
    python run.py --slug medivation --raw-extraction /tmp/medivation.raw.json

    # Finalize and commit only the current deal's output/state files:
    python run.py --slug medivation --raw-extraction /tmp/medivation.raw.json --commit

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

EXIT CODES
----------
  0  success
  1  pipeline error; failure recorded in state/progress.json
  2  pipeline error AND the failure recorder itself crashed — investigate
     state/progress.json, rules/, or disk state before re-running
"""

from __future__ import annotations

import argparse
import copy
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
    commit: bool = False,
) -> pipeline.PipelineResult | None:
    """Run validator, merge flags, write output + state. Optionally commit."""
    filing = pipeline.load_filing(slug)

    if dry_run:
        prepared, filing, _ = pipeline.prepare_for_validate(
            slug,
            copy.deepcopy(raw_extraction),
            filing=filing,
        )
        result = pipeline.validate(prepared, filing)
        final = pipeline.merge_flags(prepared, result.row_flags, result.deal_flags)
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
        try:
            commit_deal_outputs(slug, result)
        except subprocess.CalledProcessError as e:
            print(f"[{slug}] git commit failed: {e}", file=sys.stderr)

    return result


def _repo_relative_path(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT.resolve()))


def _commit_pathspecs(result: pipeline.PipelineResult) -> list[str]:
    paths = [
        result.output_path,
        PROGRESS_PATH,
    ]
    if pipeline.FLAGS_PATH.exists():
        paths.append(pipeline.FLAGS_PATH)

    pathspecs: list[str] = []
    seen: set[str] = set()
    for path in paths:
        pathspec = _repo_relative_path(path)
        if pathspec in seen:
            continue
        seen.add(pathspec)
        pathspecs.append(pathspec)
    return pathspecs


def _check_no_staged_drift(pathspecs: list[str]) -> None:
    """Abort if any target path has staged content that differs from working tree.

    `git commit --only -- <paths>` commits the working-tree version of the
    listed paths, silently ignoring any deliberately-staged content for those
    paths. If the user staged a different version (e.g., during manual
    review), `--commit` would silently overwrite it. Refuse and tell the
    user how to resolve.
    """
    if not pathspecs:
        return
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--", *pathspecs],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    drifted = [p for p in result.stdout.splitlines() if p.strip()]
    if drifted:
        raise RuntimeError(
            f"staged content for {drifted!r} differs from what --commit would "
            f"write from the working tree; resolve (git commit or git reset) "
            f"before re-running with --commit"
        )


def commit_deal_outputs(slug: str, result: pipeline.PipelineResult) -> None:
    """Commit only files finalized for this deal.

    `git add -A` is intentionally avoided because the repo often has unrelated
    edits in flight. `git commit --only -- <paths>` also prevents already-staged
    unrelated files from riding along with this deal commit. A pre-flight
    check refuses if any target path has drifted between index and working
    tree, since `--only` would silently rewrite staged content.
    """
    pathspecs = _commit_pathspecs(result)
    _check_no_staged_drift(pathspecs)
    commit_message = f"deal={slug} status={result.status} flag_count={result.flag_count}"
    subprocess.run(["git", "add", "--", *pathspecs], cwd=REPO_ROOT, check=True)
    subprocess.run(
        ["git", "commit", "--only", "-m", commit_message, "--", *pathspecs],
        cwd=REPO_ROOT,
        check=True,
    )


def validate_slug(slug: str) -> None:
    if not PROGRESS_PATH.exists():
        raise FileNotFoundError(f"{PROGRESS_PATH} does not exist")
    state = json.loads(PROGRESS_PATH.read_text())
    if slug not in state["deals"]:
        raise KeyError(f"slug={slug!r} not in state/progress.json")


def _short_failure_note(code: str, detail: object) -> str:
    detail_text = " ".join(str(detail).split())
    return f"{code}: {detail_text}"[:500]


def _record_failure(slug: str, note: str) -> bool:
    """Try to record a failed run. Returns False if the recorder itself crashed.

    `pipeline.mark_failed` can still raise on missing `state/progress.json` or
    disk errors; that means the failure-recording promise itself is broken,
    and the caller should surface that distinctly (exit 2) rather than treat
    it as a normal pipeline failure (exit 1).
    """
    try:
        pipeline.mark_failed(slug, note)
    except Exception as e:
        print(
            f"[{slug}] unable to record failure "
            f"(recorder crashed with {type(e).__name__}: {e}); "
            f"original failure was: {note}",
            file=sys.stderr,
        )
        return False
    print(f"[{slug}] failed: {note}", file=sys.stderr)
    return True


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
        "--commit",
        action="store_true",
        help="After writing output/state, commit only the current deal's output/state files.",
    )
    args = parser.parse_args()

    if args.print_extractor_prompt:
        print(pipeline.build_extractor_prompt(args.slug))
        return 0

    if args.raw_extraction is None:
        parser.error("--raw-extraction is required (unless --print-extractor-prompt)")

    validate_slug(args.slug)

    if not args.raw_extraction.exists():
        note = _short_failure_note("missing_raw_extraction", args.raw_extraction)
        if args.dry_run:
            print(f"[{args.slug}] failed: {note}", file=sys.stderr)
            return 1
        return 1 if _record_failure(args.slug, note) else 2

    try:
        raw = json.loads(args.raw_extraction.read_text())
    except json.JSONDecodeError as e:
        note = _short_failure_note("malformed_raw_json", e)
        if args.dry_run:
            print(f"[{args.slug}] failed: {note}", file=sys.stderr)
            return 1
        return 1 if _record_failure(args.slug, note) else 2

    try:
        finalize_deal(args.slug, raw, dry_run=args.dry_run, commit=args.commit)
    except Exception as e:
        note = _short_failure_note(type(e).__name__, e)
        if args.dry_run:
            print(f"[{args.slug}] failed: {note}", file=sys.stderr)
            return 1
        return 1 if _record_failure(args.slug, note) else 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
