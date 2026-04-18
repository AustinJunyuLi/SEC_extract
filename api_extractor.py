"""api_extractor.py — Python-driven M&A extractor using linkflow (OpenAI-compatible).

Architecture pivot (2026-04-18): replaces the Claude Code subagent pathway for
the Extractor step. The Python Validator + Adjudicator flow below remains
unchanged — this module only produces the `{deal, events}` raw JSON that the
existing `pipeline.finalize()` consumes.

Secrets live in `.env.linkflow` (gitignored):
    LINKFLOW_API_KEY=sk-...
    LINKFLOW_BASE_URL=https://www.linkflow.run/v1
    LINKFLOW_MODEL=gpt-5.4
    LINKFLOW_REASONING_EFFORT=high

Usage (CLI):
    python api_extractor.py --slugs medivation,imprivata,zep,penford,providence-worcester
    python api_extractor.py --slug medivation --dry-prompt   # print prompt, no call
    python api_extractor.py --slug medivation --workers 1    # serial
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as _dt
import json
import os
import re
import sys
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
ENV_FILE = REPO_ROOT / ".env.linkflow"
DATA_DIR = REPO_ROOT / "data" / "filings"
RULES_DIR = REPO_ROOT / "rules"
PROMPTS_DIR = REPO_ROOT / "prompts"
RUNLOG_DIR = REPO_ROOT / "runlog"

HEARTBEAT_SECONDS = 5.0
STALE_WARNING_SECONDS = 30.0
CALL_TIMEOUT_SECONDS = float(os.environ.get("LINKFLOW_CALL_TIMEOUT_SECONDS", "1200"))
STREAM_IDLE_TIMEOUT_SECONDS = float(os.environ.get("LINKFLOW_STREAM_IDLE_TIMEOUT_SECONDS", "180"))

RULE_FILES = ("schema.md", "events.md", "bidders.md", "bids.md", "dates.md", "invariants.md")

_print_lock = threading.Lock()


def _tprint(*args, **kwargs):
    with _print_lock:
        print(*args, **kwargs, flush=True)


# ---------------------------------------------------------------------------
# Config loading (from .env.linkflow)
# ---------------------------------------------------------------------------

def load_config() -> dict:
    cfg = {
        "api_key": os.environ.get("LINKFLOW_API_KEY"),
        "base_url": os.environ.get("LINKFLOW_BASE_URL"),
        "model": os.environ.get("LINKFLOW_MODEL", "gpt-5.4"),
        "reasoning_effort": os.environ.get("LINKFLOW_REASONING_EFFORT", "high"),
    }
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k == "LINKFLOW_API_KEY" and not cfg["api_key"]:
                cfg["api_key"] = v
            elif k == "LINKFLOW_BASE_URL" and not cfg["base_url"]:
                cfg["base_url"] = v
            elif k == "LINKFLOW_MODEL" and cfg["model"] == "gpt-5.4":
                cfg["model"] = v
            elif k == "LINKFLOW_REASONING_EFFORT" and cfg["reasoning_effort"] == "high":
                cfg["reasoning_effort"] = v
    if not cfg["api_key"]:
        raise RuntimeError("LINKFLOW_API_KEY not set (check .env.linkflow or env var)")
    if not cfg["base_url"]:
        raise RuntimeError("LINKFLOW_BASE_URL not set")
    return cfg


# ---------------------------------------------------------------------------
# Prompt assembly — self-contained (API model can't Read files on disk)
# ---------------------------------------------------------------------------

def _read(p: Path) -> str:
    return p.read_text()


def _find_background_start(pages: list[dict]) -> int:
    patterns = [
        "Background of the Merger",
        "Background of the Offer",
        "Background of the Transaction",
        "Background of the Acquisition",
        "Background of the Proposed Merger",
        "Background of the Proposed Transaction",
        "Background of Offer and Merger",
    ]
    hits = []
    for i, p in enumerate(pages):
        c = p.get("content", "")
        for phrase in patterns:
            if phrase in c:
                hits.append(i)
                break
    if not hits:
        return 0
    # Prefer the LAST occurrence (body) over TOC hits earlier in the doc.
    return hits[-1] if len(hits) == 1 else hits[-1]


def load_filing_context(slug: str) -> tuple[str, dict]:
    deal_dir = DATA_DIR / slug
    pages = json.loads((deal_dir / "pages.json").read_text())
    manifest = json.loads((deal_dir / "manifest.json").read_text())
    start = _find_background_start(pages)
    # Include from start page onward — model will identify section boundaries.
    # Cap at 60 pages to keep prompt under context limit.
    cap = min(len(pages), start + 60)
    chunks = [f"[page {p['number']}]\n{p.get('content','')}" for p in pages[start:cap]]
    text = "\n\n".join(chunks)
    return text, manifest


def build_api_prompt(slug: str) -> str:
    operating_proc = _read(PROMPTS_DIR / "extract.md")
    rulebook = []
    for fn in RULE_FILES:
        rulebook.append(f"===== rules/{fn} =====\n{_read(RULES_DIR / fn)}")
    rulebook_text = "\n\n".join(rulebook)
    filing_text, manifest = load_filing_context(slug)

    deal_meta = {
        "slug": slug,
        "target_name": manifest.get("target_name"),
        "acquirer": manifest.get("acquirer"),
        "date_announced": manifest.get("date_announced"),
        "form_type": manifest.get("source", {}).get("form_type"),
        "primary_url": manifest.get("source", {}).get("index_url"),
    }

    return f"""You are the Extractor in an M&A auction extraction pipeline. Run \
on a single deal and emit ONE JSON object conforming to rules/schema.md §R1. \
No prose outside the final JSON block.

Deal: {json.dumps(deal_meta, indent=2)}

===== OPERATING PROCEDURE (prompts/extract.md) =====
{operating_proc}

===== RULEBOOK (all resolved — halt on any 🟥 OPEN) =====
{rulebook_text}

===== FILING (authoritative for every source_quote and source_page) =====
Filing pages below are the Background section of the merger filing, with
page markers. Every emitted row's `source_quote` MUST be a verbatim substring
of the content under its cited `[page N]` marker. `source_page` is the
integer N.

{filing_text}

===== OUTPUT CONTRACT =====
Emit exactly one JSON object of shape:

  {{"deal": {{ ... }}, "events": [ ... ]}}

Nothing else — no prose, no markdown fence, no commentary. Begin the response
with `{{` and end with `}}`. If a 🟥 OPEN rule is encountered, emit instead:

  {{"status": "blocked_by_open_rule", "open_rules": ["rules/xxx.md §Y"]}}

Apply every non-negotiable and every self-check item from the operating
procedure before emitting.
"""


# ---------------------------------------------------------------------------
# Heartbeat / watchdog
# ---------------------------------------------------------------------------

class Watchdog:
    def __init__(self, slug: str, model: str, log_path: Path):
        self.slug = slug
        self.model = model
        self.log_path = log_path
        self.start_time = time.time()
        self.last_activity = self.start_time
        self.output_chars = 0
        self.phase = "waiting"
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._append(f"[{self._ts()}] BEGIN slug={self.slug} model={self.model}")
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name=f"watchdog-{self.slug}")
        self._thread.start()
        return self

    def mark(self, chars: int = 0, phase: str | None = None):
        with self._lock:
            self.last_activity = time.time()
            self.output_chars += chars
            if phase is not None:
                self.phase = phase

    def set_phase(self, phase: str):
        with self._lock:
            self.phase = phase

    def elapsed(self) -> float:
        return time.time() - self.start_time

    def finish(self, status: str, note: str = ""):
        with self._lock:
            self.phase = status
        self._append(f"[{self._ts()}] END slug={self.slug} status={status} "
                     f"elapsed={self.elapsed():.1f}s chars={self.output_chars} {note}")
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=HEARTBEAT_SECONDS * 2)

    def _ts(self) -> str:
        return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")

    def _append(self, line: str):
        try:
            with self.log_path.open("a") as fh:
                fh.write(line + "\n")
        except Exception:
            pass

    def _run(self):
        while not self._stop.wait(HEARTBEAT_SECONDS):
            with self._lock:
                phase = self.phase
                chars = self.output_chars
                idle = time.time() - self.last_activity
            elapsed = self.elapsed()
            prefix = "WARN" if idle >= STALE_WARNING_SECONDS else "BEAT"
            tokens = chars // 4
            line = (f"[{self._ts()}] {prefix} slug={self.slug} phase={phase} "
                    f"elapsed={elapsed:.1f}s idle={idle:.1f}s ~{tokens:,}out_tok")
            self._append(line)
            _tprint(f"    {prefix} {self.slug:25s} {phase:12s} {elapsed:6.1f}s elapsed "
                    f"{idle:5.1f}s idle  ~{tokens:,} tok")


# ---------------------------------------------------------------------------
# OpenAI (linkflow) call
# ---------------------------------------------------------------------------

def _parse_json_response(text: str):
    # 1) direct
    try:
        return json.loads(text)
    except Exception:
        pass
    # 2) fenced block
    m = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # 3) first balanced { ... } block
    start = text.find("{")
    if start >= 0:
        depth = 0
        for i in range(start, len(text)):
            ch = text[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except Exception:
                        break
    return None


def call_linkflow(prompt: str, slug: str, cfg: dict, log_path: Path) -> tuple[dict | None, str, float]:
    """Stream a single response from linkflow. Returns (parsed_json, raw_text, elapsed)."""
    import httpx
    from openai import OpenAI

    timeout = httpx.Timeout(CALL_TIMEOUT_SECONDS, read=STREAM_IDLE_TIMEOUT_SECONDS)
    client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"], timeout=timeout)

    watchdog = Watchdog(slug=slug, model=cfg["model"], log_path=log_path).start()
    text = ""
    kwargs = {
        "model": cfg["model"],
        "input": [{"role": "user", "content": prompt}],
        "reasoning": {"effort": cfg["reasoning_effort"]},
    }

    try:
        watchdog.set_phase("connecting")
        with client.responses.stream(**kwargs) as stream:
            watchdog.set_phase("streaming")
            for event in stream:
                etype = getattr(event, "type", "")
                if etype == "response.output_text.delta":
                    delta = getattr(event, "delta", "") or ""
                    text += delta
                    watchdog.mark(chars=len(delta), phase="streaming")
                else:
                    watchdog.mark(phase=f"streaming ({etype})" if etype else "streaming")
            final = stream.get_final_response()
        if not text:
            text = getattr(final, "output_text", "") or ""
    except Exception as exc:
        watchdog.finish("failed", note=f"{type(exc).__name__}: {exc}")
        raise
    elapsed = watchdog.elapsed()
    parsed = _parse_json_response(text)
    watchdog.finish("ok" if parsed is not None else "parse_fail",
                    note=f"chars={len(text)}")
    return parsed, text, elapsed


# ---------------------------------------------------------------------------
# Per-deal extraction + parallel runner
# ---------------------------------------------------------------------------

def extract_one(slug: str, cfg: dict, out_dir: Path = Path("/tmp")) -> dict:
    out_path = out_dir / f"{slug}.raw.json"
    log_path = RUNLOG_DIR / f"{slug}.log"
    _tprint(f"\n==> Starting {slug}  (model={cfg['model']} reasoning={cfg['reasoning_effort']})")
    prompt = build_api_prompt(slug)
    _tprint(f"    prompt size: {len(prompt):,} chars (~{len(prompt)//4:,} tokens est)")
    result = {"slug": slug, "status": "failed", "elapsed": 0.0, "out_path": None, "events": 0, "error": None}
    try:
        parsed, text, elapsed = call_linkflow(prompt, slug, cfg, log_path)
        result["elapsed"] = elapsed
        if parsed is None:
            _tprint(f"    X {slug}: JSON parse failed ({len(text)} chars response)")
            (out_dir / f"{slug}.raw.txt").write_text(text)
            result["error"] = f"parse_failed; raw in {slug}.raw.txt"
            return result
        out_path.write_text(json.dumps(parsed, indent=2))
        result["status"] = "ok"
        result["out_path"] = str(out_path)
        result["events"] = len(parsed.get("events", []))
        _tprint(f"    OK {slug}: {result['events']} events in {elapsed:.1f}s -> {out_path}")
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        _tprint(f"    X {slug}: {result['error']}")
    return result


def extract_parallel(slugs: list[str], cfg: dict, workers: int = 5) -> list[dict]:
    RUNLOG_DIR.mkdir(parents=True, exist_ok=True)
    workers = max(1, min(workers, len(slugs)))
    _tprint(f"\n=== Running {len(slugs)} deals with {workers} workers ===")
    _tprint(f"    slugs: {', '.join(slugs)}")
    start = time.time()
    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(extract_one, slug, cfg): slug for slug in slugs}
        for fut in concurrent.futures.as_completed(futs):
            results.append(fut.result())
    elapsed = time.time() - start
    ok = sum(1 for r in results if r["status"] == "ok")
    _tprint(f"\n=== Batch complete: {ok}/{len(slugs)} ok in {elapsed:.1f}s ===")
    for r in sorted(results, key=lambda x: x["slug"]):
        flag = "OK" if r["status"] == "ok" else "X"
        extra = f"events={r['events']}" if r["status"] == "ok" else r.get("error", "")
        _tprint(f"    {flag} {r['slug']:25s} {r['elapsed']:6.1f}s  {extra}")
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--slug", help="Single deal slug")
    parser.add_argument("--slugs", help="Comma-separated deal slugs (overrides --slug)")
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--dry-prompt", action="store_true",
                        help="Build and print the prompt; do not call API.")
    args = parser.parse_args()

    if args.slugs:
        slugs = [s.strip() for s in args.slugs.split(",") if s.strip()]
    elif args.slug:
        slugs = [args.slug]
    else:
        parser.error("--slug or --slugs required")

    if args.dry_prompt:
        for s in slugs:
            p = build_api_prompt(s)
            print(f"=== {s} prompt ({len(p):,} chars) ===")
            print(p[:2000] + "\n[...truncated...]" if len(p) > 2000 else p)
        return 0

    cfg = load_config()
    extract_parallel(slugs, cfg, workers=args.workers)
    return 0


if __name__ == "__main__":
    sys.exit(main())
