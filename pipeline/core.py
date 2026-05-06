"""Shared deterministic helpers for the M&A extraction pipeline.

SDK orchestration lives in `pipeline.llm` and `pipeline.run_pool`. The
`deal_graph_v2` finalizer owns claim parsing, graph validation, and review projection.
This module keeps only shared plumbing: filing artifact loading, atomic writes,
state updates, flag logging, and status classification.
"""

from __future__ import annotations

import contextlib
import datetime as _dt
import fcntl
import hashlib
import json
import os
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "filings"
RULES_DIR = REPO_ROOT / "rules"
PROMPTS_DIR = REPO_ROOT / "prompts"
EXTRACTIONS_DIR = REPO_ROOT / "output" / "extractions"
STATE_DIR = REPO_ROOT / "state"
PROGRESS_PATH = STATE_DIR / "progress.json"
FLAGS_PATH = STATE_DIR / "flags.jsonl"
PROGRESS_LOCK_PATH = STATE_DIR / "progress.lock"
_PROCESS_STATE_LOCK = threading.Lock()

REFERENCE_SLUGS: tuple[str, ...] = (
    "providence-worcester",
    "medivation",
    "imprivata",
    "zep",
    "petsmart-inc",
    "penford",
    "mac-gray",
    "saks",
    "stec",
)

RULEBOOK_HISTORY_CAP = 10
_FLAG_SEVERITIES = frozenset({"hard", "soft", "info"})
TRUSTED_STATUSES = frozenset({"passed_clean", "needs_review", "high_burden"})
FAILURE_STATUSES = frozenset({"failed_system", "stale_after_failure"})
ALL_RUN_STATUSES = TRUSTED_STATUSES | FAILURE_STATUSES


@dataclass
class Filing:
    slug: str
    pages: list[dict[str, Any]]

    def page_content(self, number: int) -> str | None:
        for page in self.pages:
            if page.get("number") == number:
                return page.get("content", "")
        return None

    def page_numbers(self) -> set[int]:
        return {page.get("number") for page in self.pages if "number" in page}


def _atomic_write_text(path: Path, text: str) -> None:
    """POSIX-atomic write: tmp file + fsync + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(text)
        fd = os.open(tmp, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()
        raise


@contextlib.contextmanager
def _state_file_lock() -> Iterator[None]:
    """Advisory exclusive lock for state-file mutations."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with _PROCESS_STATE_LOCK:
        fd = os.open(PROGRESS_LOCK_PATH, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)


def rulebook_version() -> str:
    """Stable content hash for the live rulebook."""
    h = hashlib.sha256()
    rule_files = sorted(RULES_DIR.glob("*.md"))
    if not rule_files:
        raise FileNotFoundError(f"no rule files found under {RULES_DIR}")
    for path in rule_files:
        h.update(path.name.encode("utf-8"))
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def _now_iso() -> str:
    """UTC ISO-8601 timestamp with Z suffix."""
    return _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _new_run_id() -> str:
    """Per-run UUID stamped on state, flags, and audit artifacts."""
    return uuid.uuid4().hex


def load_filing(slug: str) -> Filing:
    deal_dir = DATA_DIR / slug
    if not deal_dir.exists():
        raise FileNotFoundError(f"no filing directory at {deal_dir}")
    pages_path = deal_dir / "pages.json"
    manifest_path = deal_dir / "manifest.json"
    for path in (pages_path, manifest_path):
        if not path.exists():
            raise FileNotFoundError(f"missing artifact: {path}")
    pages = json.loads(pages_path.read_text())
    return Filing(slug=slug, pages=pages)


def count_flags(final_extraction: dict[str, Any]) -> dict[str, int]:
    """Count current graph validation flags in a finalized output."""
    counts = dict.fromkeys(_FLAG_SEVERITIES, 0)
    deal_flags = (final_extraction.get("deal") or {}).get("deal_flags") or []
    flags = deal_flags
    if not flags:
        graph_flags = final_extraction.get("validation_flags") or []
        graph = final_extraction.get("graph") or {}
        if isinstance(graph, dict):
            graph_flags = [*graph_flags, *(graph.get("validation_flags") or [])]
        flags = graph_flags

    for flag in flags:
        if not isinstance(flag, dict):
            severity = "hard"
        else:
            severity = flag.get("severity", "hard")
        if severity == "blocking":
            severity = "hard"
        if severity not in counts:
            severity = "hard"
        counts[severity] += 1
    return counts


def summarize(final_extraction: dict[str, Any]) -> tuple[str, int, str]:
    """Return (status, flag_count, notes) per the status taxonomy."""
    review_rows = final_extraction.get("review_rows")
    if final_extraction.get("schema_version") != "deal_graph_v2" or not isinstance(review_rows, list):
        return "failed_system", 0, "trusted deal_graph_v2 review output is missing"
    burden = sum(
        1 for row in review_rows
        if isinstance(row, dict) and row.get("review_status") != "clean"
    )
    if burden == 0:
        status = "passed_clean"
    elif burden <= 10:
        status = "needs_review"
    else:
        status = "high_burden"
    return status, burden, f"review_burden={burden}"


def write_output(slug: str, final_extraction: dict[str, Any]) -> Path:
    """Atomic write of the latest per-deal extraction snapshot."""
    out_path = EXTRACTIONS_DIR / f"{slug}.json"
    _atomic_write_text(
        out_path,
        json.dumps(final_extraction, indent=2, default=str) + "\n",
    )
    return out_path


def _append_flags_log_locked(
    slug: str,
    final_extraction: dict[str, Any],
    run_ts: str,
    run_id: str,
) -> int:
    """Inner half of `append_flags_log`. Caller must hold `_state_file_lock`."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    deal = final_extraction.get("deal") or {}
    graph = final_extraction.get("graph") if isinstance(final_extraction.get("graph"), dict) else {}
    flags = [
        *(
            {**flag, "deal_level": True}
            for flag in deal.get("deal_flags") or []
            if isinstance(flag, dict)
        ),
        *(
            dict(flag)
            for flag in graph.get("review_flags") or []
            if isinstance(flag, dict)
        ),
    ]
    for flag in flags:
        entry = {
            "deal": slug,
            "run_id": run_id,
            "logged_at": run_ts,
            **flag,
        }
        lines.append(json.dumps(entry, default=str))
    if not lines:
        return 0
    with FLAGS_PATH.open("a") as fh:
        for line in lines:
            fh.write(line + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return len(lines)


def append_flags_log(
    slug: str,
    final_extraction: dict[str, Any],
    run_ts: str,
    run_id: str,
) -> int:
    """Append this run's graph validation flags to `state/flags.jsonl`."""
    with _state_file_lock():
        return _append_flags_log_locked(slug, final_extraction, run_ts, run_id)


def _update_progress_locked(
    slug: str,
    status: str,
    flag_count: int,
    notes: str,
    current_rulebook_version: str,
    last_run: str,
    run_id: str,
) -> None:
    """Inner half of `update_progress`. Caller must hold `_state_file_lock`."""
    if status not in ALL_RUN_STATUSES:
        raise ValueError(
            f"status {status!r} is not in the live extraction taxonomy: "
            f"{', '.join(sorted(ALL_RUN_STATUSES))}"
        )
    try:
        state = json.loads(PROGRESS_PATH.read_text())
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            f"{PROGRESS_PATH} does not exist; run scripts/build_seeds.py first"
        ) from exc
    if "rulebook_version" in state:
        raise ValueError(
            "state/progress.json contains stale top-level rulebook_version; "
            "regenerate state/progress.json under the current schema"
        )
    deals = state.setdefault("deals", {})
    if slug not in deals:
        deals[slug] = {
            "is_reference": False,
            "status": status,
            "flag_count": 0,
            "last_run": None,
            "last_verified_by": None,
            "last_verified_at": None,
            "notes": f"auto-created at {last_run} by update_progress; was not in seeds",
        }
    history = deals[slug].setdefault("rulebook_version_history", [])
    history.append({"ts": last_run, "run_id": run_id, "version": current_rulebook_version})
    if len(history) > RULEBOOK_HISTORY_CAP:
        deals[slug]["rulebook_version_history"] = history[-RULEBOOK_HISTORY_CAP:]
    previous = deals[slug]
    write_notes = notes
    if (
        previous.get("is_reference") is True
        and status in TRUSTED_STATUSES
        and isinstance(previous.get("verification_report"), str)
        and isinstance(previous.get("last_verified_by"), str)
    ):
        previous["verified"] = True
        write_notes = f"{notes}; prior filing-grounded verification metadata preserved"
    deals[slug].update({
        "status": status,
        "flag_count": flag_count,
        "last_run": last_run,
        "last_run_id": run_id,
        "notes": write_notes,
        "rulebook_version": current_rulebook_version,
    })
    state["updated"] = last_run
    _atomic_write_text(
        PROGRESS_PATH,
        json.dumps(state, indent=2, sort_keys=False) + "\n",
    )


def update_progress(
    slug: str,
    status: str,
    flag_count: int,
    notes: str,
    current_rulebook_version: str,
    last_run: str,
    run_id: str,
) -> None:
    """Lock-serialized progress update."""
    with _state_file_lock():
        _update_progress_locked(
            slug,
            status,
            flag_count,
            notes,
            current_rulebook_version,
            last_run,
            run_id,
        )


def mark_failed(slug: str, notes: str) -> None:
    """Record a runtime failure before a valid finalized output exists."""
    if not notes.strip():
        raise ValueError("failure notes must be non-empty")
    try:
        current_version = rulebook_version()
    except FileNotFoundError:
        current_version = "unavailable"
    update_progress(
        slug=slug,
        status=_failure_status_for_slug(slug),
        flag_count=0,
        notes=notes,
        current_rulebook_version=current_version,
        last_run=_now_iso(),
        run_id=_new_run_id(),
    )


def _failure_status_for_slug(slug: str) -> str:
    try:
        state = json.loads(PROGRESS_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return "failed_system"
    deal = state.get("deals", {}).get(slug, {})
    if (
        isinstance(deal, dict)
        and deal.get("status") in TRUSTED_STATUSES
        and (EXTRACTIONS_DIR / f"{slug}.json").exists()
    ):
        return "stale_after_failure"
    return "failed_system"
