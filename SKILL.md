# SKILL.md — M&A Background Extraction

**Purpose.** Given one SEC merger filing (DEFM14A / PREM14A / SC-TO-T / S-4), extract the "Background of the Merger" section into a structured row-per-event JSON matching Alex Gorbenko's auction schema.

**You are one iteration of the per-deal extraction loop.** The code
orchestrator hands the SDK one deal at a time. `run.py --slug X --extract`
is the single-deal wrapper; `python -m pipeline.run_pool --filter reference
--workers N` is the batch runner. Do not carry state across deals.

---

## Invocation contract

**Input** (from the orchestrator): a single `slug` (short identifier, e.g.
`medivation`). `pipeline.llm.extract.build_messages(slug)` assembles SDK
messages: the system message contains `prompts/extract.md` plus
`rules/schema.md`, `rules/events.md`, `rules/bidders.md`, `rules/bids.md`,
and `rules/dates.md`; the user message contains the slug, `manifest.json`,
and page-numbered filing text from `pages.json`. Extraction does not fetch
from SEC, EDGAR, the web, or local files during the model call.
`state/progress.json` carries the `is_reference` flag used downstream by
`scoring/diff.py`.

**Output** (written by `pipeline.core.finalize()` after validation):
- `output/extractions/{slug}.json` — the extracted rows + deal-level fields.
- Append to `state/flags.jsonl` — any ambiguities flagged during validation.
- Update `state/progress.json` — set the deal's status.

---

## Pipeline (Extractor SDK Call + Python Validator + Scoped Adjudicator)

**Architecture (current Stage 3 MVP):** `pipeline.run_pool` and `run.py`
make direct SDK calls through an OpenAI-compatible provider configured by
`OPENAI_BASE_URL` / `OPENAI_API_KEY`. The Extractor and optional Adjudicator
are model calls; validation/finalization remain Python code in
`pipeline/core.py`.

**Why this shape, not "two LLM agents in series" as originally drafted.**
Every invariant in `rules/invariants.md` (§P-R, §P-D, §P-G, §P-S) is
mechanically checkable — substring, regex, set membership, graph
traversal. An LLM Validator would just re-derive the same checks
non-deterministically and cost money. The Python Validator is deterministic,
free, and instant. The Adjudicator is still scoped to the one judgment call
Python cannot make: "this soft flag
says the filing seems to stop mentioning this bidder mid-process — is
that a real extraction miss or is the filing genuinely silent?"

### 1. Extractor — SDK call
- **Called by:** `pipeline.run_pool` or `run.py`, one deal per call, no
  cross-deal state.
- **Receives:** a system message containing `prompts/extract.md` and the
  operative extractor rules (`rules/schema.md`, `rules/events.md`,
  `rules/bidders.md`, `rules/bids.md`, `rules/dates.md`), plus a user
  message containing the slug, `manifest.json`, and page-numbered filing
  text from `pages.json`.
- **Does not receive:** `rules/invariants.md`. That file is
  validator-facing only; extractor prompts may name validator check codes
  only as fail-loud guidance for the JSON they emit.
- **Emits:** a single JSON payload `{deal: {...}, events: [...]}` conforming
  to `rules/schema.md` §R1. Every event row carries `source_quote` (NFKC
  substring of the cited page) and `source_page` (integer matching
  `pages.json[i].number`).
- **Prompt builder:** `pipeline.llm.extract.build_messages(slug)`.

### 2. Validator — Python (`pipeline/core.py`)
- **Entry:** `pipeline.validate(raw_extraction, filing) -> ValidatorResult`.
- **Runs:** every invariant in `rules/invariants.md` — §P-R1..5 (structural
  row checks), §P-D1..3 (date/BidderID integrity), §P-G2 (bid-type
  evidence), §P-S1..4 (semantic process checks).
- **Returns:** `row_flags` and `deal_flags` lists of
  `{code, severity, reason, [row_index|deal_level]}` dicts.
- **Never rewrites the extraction.** Flag-only discipline preserves the
  Extractor's output as the single source of what was extracted.

### 3. Adjudicator — SDK call, scoped
- **Fires when:** the Python Validator raises a soft flag (MVP: §P-S1
  `missing_nda_dropsilent`). No-op when zero soft flags.
- **Receives:** the flagged row + same-bidder context rows + a small window
  of filing pages.
- **Emits:** `{verdict: "upheld" | "dismissed", reason: str}` appended to
  the flag's `reason` field. Severity is NOT flipped in MVP — human review
  stays explicit.
- **Execution model:** this is an SDK call inside the code orchestrator. The
  orchestrator reads validator output, calls the Adjudicator when needed,
  mutates `raw_extraction`, and only then calls `pipeline.core.finalize()`.

### Orchestration

```
  run.py / pipeline.run_pool:
    1. call Extractor SDK → raw_extraction JSON + audit cache
    2. filing = pipeline.core.load_filing(slug)
    3. result = pipeline.core.validate(raw_extraction, filing)
    4. if any(flag["severity"] == "soft" for flag in result.row_flags + result.deal_flags):
         call Adjudicator SDK and annotate raw_extraction before finalize
    5. pipeline.core.finalize(slug, raw_extraction)
         → output/extractions/{slug}.json
         → state/flags.jsonl (append)
         → state/progress.json (update)
    6. scoring/diff.py --slug {slug}   (on reference deals)
    7. git commit
```

`run.py` is the single-deal CLI wrapper:

```
python run.py --slug X --extract
python run.py --slug X --re-validate
python run.py --slug X --re-extract
python run.py --slug X --print-prompt
```

`--re-validate` uses the cached raw response when valid for the current
rulebook. `--re-extract` forces a fresh model call.

---

## Scope

Defined in `rules/schema.md` §Scope:
- **§Scope-1 🟩** — Research scope is corporate takeover auctions (≥2 non-advisor bidder NDAs in the current process). The pipeline extracts every valid-filing-type deal and emits a deal-level `auction: bool`; downstream filters on `auction == true`. Do NOT pre-gate extraction by auction status.
- **§Scope-2 🟩** — Accepted primary forms: DEFM14A, PREM14A, SC TO-T, S-4. `/A` amendments when they supersede. `SC 14D9` accepted as secondary companion to SC TO-T. `DEFA14A`, `425`, `8-K`, `13D`, `13G` excluded.
- **§Scope-3 🟩** — AI excludes COMPUSTAT fields (`cshoc`, `gvkey*`), EDGAR metadata (`DateFiled`, `FormType`, `URL`, `CIK`, `accession`), and orchestration metadata (`DealNumber`, `rulebook_version`). Filing-read deal-identity fields are cross-checked against seeds; filing wins on mismatch.

If any scope rule is 🟥 OPEN, stop and report — do not extract.

---

## Non-negotiable rules

1. **Every emitted row has `source_quote` and `source_page`.** No exceptions. If you can't cite filing text, don't emit the row.
2. **The event vocabulary in `rules/events.md` is closed.** Do not invent new `bid_note` values. If an event doesn't fit, flag it.
3. **Dates follow `rules/dates.md` exactly.** Natural-language dates ("mid-June 2016") must be mapped deterministically, not creatively.
4. **Bidder names follow the filing verbatim** until the canonicalization rule in `rules/bidders.md` §E4 triggers.
5. **Informal-vs-formal classification must be evidenced per `rules/bids.md` §G2**: either a true range bid (both `bid_value_lower` and `bid_value_upper` numeric with `lower < upper`) or a non-empty `bid_type_inference_note` ≤300 chars. The note should cite the §G1 rule applied (trigger phrase, process-position fallback, or structural signal); the validator (§P-G2) enforces evidence, not a specific justification type. Borderline calls are flagged, not forced.
6. **Skip rules in `rules/bids.md` §M are mandatory.** Do not record unsolicited letters with no NDA, no price, no bid intent.

---

## State contract

**`state/progress.json`** schema:
```json
{
  "schema_version": "v1",
  "deals": {
    "<slug>": {
      "status": "pending | validated | passed | passed_clean | verified | failed",
      "flag_count": 0,
      "last_run": "ISO8601",
      "last_verified_by": null,
      "last_verified_at": null,
      "notes": "",
      "rulebook_version": "<sha256 hash at time of last finalize>",
      "rulebook_version_history": [
        {"ts": "ISO8601", "version": "<sha256>"}
      ]
    }
  }
}
```

Notes on the schema:
- There is NO top-level `rulebook_version`. Per-deal finalizes race on a
  global key and never had history anyway. Use `deals[slug].rulebook_version`
  for the current pin and `rulebook_version_history` (last 10 entries) to
  audit the "3 consecutive unchanged-rulebook clean runs" exit gate.
- `rulebook_version_history` is append-only; `pipeline.RULEBOOK_HISTORY_CAP`
  (default 10) truncates the oldest entries on overflow.
- Target deals that have never been finalized have no `rulebook_version` and
  no history — those fields appear on first finalize.

**`state/flags.jsonl`** — append-only. One flag per line:
```json
{"deal": "medivation", "logged_at": "2026-04-24T12:00:00Z", "row_index": 7, "code": "informal_vs_formal_borderline", "severity": "soft", "reason": "…"}
```

`finalize()` captures a single `run_ts` and stamps it on every flag's
`logged_at` AND on `deals[slug].last_run`. The current-run query is an
exact match:

```
logged_at == deals[slug].last_run
```

Older entries for the same deal (prior finalizes) remain on disk as
history. Do not use `>=` — that returns zero rows, because `last_run` is
the same value as the newest `logged_at`. For the authoritative latest
view without scanning jsonl, read `output/extractions/{slug}.json` `flags[]`
and deal-level `deal_flags[]`.

**`output/extractions/{deal.slug}.json`** schema conforms to `rules/schema.md`.
Pipeline-stamped deal-level fields: `rulebook_version`, `last_run` (both
ISO8601-Z, both populated on every finalize; both equal to the matching
entries in `state/progress.json`).

**Status semantics:**
- `pending` — not yet run.
- `validated` — combined extractor + validator flags contain at least one hard flag.
- `passed` — combined extractor + validator flags contain only soft/info flags.
- `passed_clean` — combined extractor + validator flags are zero.
- `verified` — Austin manually read the filing and adjudicated any AI-vs-Alex diff. Only set on reference deals, and only by the manual review workflow (not by the pipeline). On target deals this status is never used; they typically stop at `validated`, `passed`, or `passed_clean`.
- `failed` — pipeline error (fetch, section-location, etc.).

`extracted` remains a useful conceptual stage in the orchestration flow, but
the current repo does not persist it into `state/progress.json`.

---

## Fail-loud rules

- If the filing artifacts are missing from `data/filings/{slug}/` →
  `status: failed`, `notes: "missing_filing_artifacts: <detail>"`, exit.
- If the "Background of the Merger" section can't be located → `status: failed`, `notes: "no_background_section"`, exit.
- If any invariant in `rules/invariants.md` fails → `status: validated`, `flag_count: N` (the row is still emitted, but flagged).
- If any 🟥 OPEN rule is encountered in the extractor-read rule files → stop immediately and report. Never guess around an open question.

---

## What this skill deliberately does NOT do

Full list in `rules/schema.md` §Scope-3. In summary:

- Compute COMPUSTAT fields: `cshoc`, `gvkey`, `gvkeyT`, `gvkeyA`. Downstream merge.
- Re-derive EDGAR metadata: `DateFiled`, `FormType`, `URL`, `CIK`, `accession`. Fetcher (`manifest.json`) owns these.
- Assign `DealNumber`. Pipeline keys on `slug`; downstream joins if needed.
- Fetch any external data (news, COMPUSTAT, other filings). Only reads the filing already downloaded under `data/filings/{slug}/`.
- Fix Chicago-collected source workbook rows or overwrite `reference/deal_details_Alex_2026.xlsx`.
- Cross-deal bidder canonicalization (is this deal's "Sponsor A" the same as that deal's "Sponsor A"?). Explicit non-goal.
- Re-classify the form type. The fetcher already classified it from the EDGAR index; AI copies it through unchanged.

Final Excel assembly is out of scope for the current repo. This skill stops
at JSON extraction + validator flags.

---

## When to change this file

- Never during routine extraction.
- Only when the architecture itself changes (e.g., adding a Planner or Canonicalizer agent after MVP-phase learnings).
- Architecture changes are git-committed with a clear rationale that names the assumption the new component encodes.
