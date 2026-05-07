"""Single-deal CLI wrapper for the SDK-backed extraction pipeline.

`python run.py --slug medivation --extract` runs one deal through the same
`pipeline.run_pool` interface used by the batch runner. The default mode is
`--extract`; `--re-extract` forces a fresh SDK call.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from pipeline import core
from pipeline.run_pool import DEFAULT_REASONING_EFFORT, TargetGateClosedError

REPO_ROOT = Path(__file__).resolve().parent
PROGRESS_PATH = REPO_ROOT / "state" / "progress.json"


def _build_messages(slug: str) -> tuple[str, str]:
    from pipeline.llm.extract import build_messages

    return build_messages(slug)


def _mode_from_args(args: argparse.Namespace) -> str:
    if args.re_extract:
        return "re_extract"
    return "extract"


def _make_pool_config(args: argparse.Namespace, *, mode: str) -> Any:
    from pipeline.run_pool import PoolConfig

    return PoolConfig(
        slugs=(args.slug,),
        workers=1,
        re_extract=mode == "re_extract",
        release_targets=args.release_targets,
        target_gate_proof=args.target_gate_proof,
        extract_model=args.extract_model or os.environ.get("EXTRACT_MODEL", "gpt-5.5"),
        extract_reasoning_effort=(
            args.extract_reasoning_effort
            or os.environ.get("EXTRACT_REASONING_EFFORT")
            or DEFAULT_REASONING_EFFORT
        ),
        commit=False,
        dry_run=args.dry_run,
    )


async def _run_single_deal_async(slug: str, *, mode: str, args: argparse.Namespace) -> Any:
    import pipeline.run_pool as run_pool

    cfg = _make_pool_config(args, mode=mode)
    summary = await run_pool.run_pool(cfg)
    return summary.outcomes[0] if summary.outcomes else summary


def _run_single_deal(slug: str, *, mode: str, args: argparse.Namespace) -> Any:
    return asyncio.run(_run_single_deal_async(slug, mode=mode, args=args))


def _repo_relative_path(path: Path) -> str:
    return str(path.resolve().relative_to(REPO_ROOT.resolve()))


def _maybe_path(value: Any) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    return path if path.exists() else None


def _commit_pathspecs(result: Any) -> list[str]:
    paths: list[Path] = []
    output_path = _maybe_path(getattr(result, "output_path", None))
    audit_path = _maybe_path(getattr(result, "audit_path", None))
    latest_path = _maybe_path(getattr(result, "latest_path", None))
    if output_path is not None:
        paths.append(output_path)
    paths.append(PROGRESS_PATH)
    if core.FLAGS_PATH.exists():
        paths.append(core.FLAGS_PATH)
    if audit_path is not None:
        paths.append(audit_path)
    if latest_path is not None:
        paths.append(latest_path)

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
    """Abort if any target path has staged content that differs from working tree."""
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
            f"write from the working tree; resolve before re-running with --commit"
        )


def commit_deal_outputs(slug: str, result: Any) -> None:
    """Commit only files produced for this deal, excluding unrelated staged files."""
    if getattr(result, "audit_path", None) is None:
        raise ValueError("SDK deal outcomes must include audit_path for --commit")
    pathspecs = _commit_pathspecs(result)
    _check_no_staged_drift(pathspecs)
    status = getattr(result, "status", "unknown")
    flag_count = getattr(result, "flag_count", "unknown")
    commit_message = f"deal={slug} status={status} flag_count={flag_count}"
    subprocess.run(["git", "add", "--", *pathspecs], cwd=REPO_ROOT, check=True)
    subprocess.run(
        ["git", "commit", "--only", "-m", commit_message, "--", *pathspecs],
        cwd=REPO_ROOT,
        check=True,
    )


def _print_outcome(slug: str, outcome: Any) -> None:
    status = getattr(outcome, "status", None)
    flag_count = getattr(outcome, "flag_count", None)
    notes = getattr(outcome, "notes", None)
    output_path = getattr(outcome, "output_path", None)
    if status is None and flag_count is None and output_path is None:
        print(f"[{slug}] completed")
        return
    bits = [f"[{slug}]"]
    if status is not None:
        bits.append(f"status={status}")
    if flag_count is not None:
        bits.append(f"flag_count={flag_count}")
    if notes:
        bits.append(f"notes={notes}")
    if output_path:
        try:
            bits.append(f"-> {_repo_relative_path(Path(output_path))}")
        except ValueError:
            bits.append(f"-> {output_path}")
    print(" ".join(bits))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", required=True, help="Deal slug to process.")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--extract", action="store_true", help="Run extraction; default mode.")
    modes.add_argument("--re-extract", action="store_true", help="Force a fresh extraction call.")
    modes.add_argument("--print-prompt", action="store_true", help="Print SDK system/user messages and exit.")
    parser.add_argument("--commit", action="store_true", help="Commit only current-deal output/state/audit files.")
    parser.add_argument(
        "--release-targets",
        action="store_true",
        help="Explicitly allow target-deal selection when the reference/stability gate is open.",
    )
    parser.add_argument(
        "--target-gate-proof",
        type=Path,
        default=REPO_ROOT / "quality_reports" / "stability" / "target-release-proof.json",
        help="JSON target-release proof file produced after stable reference runs.",
    )
    parser.add_argument("--extract-model", help="Model for extraction calls.")
    parser.add_argument(
        "--extract-reasoning-effort",
        choices=["none", "minimal", "low", "medium", "high", "xhigh"],
        help="reasoning.effort for extraction calls.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Plan the run without requiring an API key.")
    return parser


def main() -> int:
    from pipeline.run_pool import load_dotenv_if_available

    load_dotenv_if_available()
    args = _parser().parse_args()
    if args.commit and args.dry_run:
        print("--commit cannot be used with --dry-run", file=sys.stderr)
        return 2
    if args.print_prompt:
        system, user = _build_messages(args.slug)
        print("=== SYSTEM ===")
        print(system)
        print("=== USER ===")
        print(user)
        return 0

    mode = _mode_from_args(args)
    try:
        outcome = _run_single_deal(args.slug, mode=mode, args=args)
    except TargetGateClosedError as e:
        print(f"[{args.slug}] failed: TargetGateClosedError: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"[{args.slug}] failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    if outcome is None:
        outcome = SimpleNamespace(status="completed", flag_count=None, notes="", output_path=None)
    _print_outcome(args.slug, outcome)
    exit_code = 1 if getattr(outcome, "status", None) in core.FAILURE_STATUSES else 0
    if args.commit:
        try:
            commit_deal_outputs(args.slug, outcome)
        except (subprocess.CalledProcessError, ValueError) as e:
            print(f"[{args.slug}] git commit failed: {e}", file=sys.stderr)
            return 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
