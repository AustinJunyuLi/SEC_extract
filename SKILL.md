# SKILL.md — M&A Background Extraction

**Purpose.** Given one SEC merger filing (DEFM14A / PREM14A / SC-TO-T / S-4), extract the "Background of the Merger" section into a structured row-per-event JSON matching Alex Gorbenko's auction schema.

**You are one iteration of the per-deal extraction loop.** The outer
orchestration conversation (or Ralph wrapper) hands you one deal, usually in
a fresh context. `run.py` is only the CLI shim that finalizes a saved raw
extraction; it is **not** the live orchestrator. Do not read other deals.
Do not carry state across invocations.

---

## Invocation contract

**Input** (from the orchestrator): a single `slug` (short identifier, e.g.
`medivation`). Full filing text + deal metadata live on disk under
`data/filings/{slug}/` (`pages.json`, `manifest.json`); the extractor
subagent reads them directly. `state/progress.json` carries the `is_reference`
flag used downstream by `scoring/diff.py`.

**Output** (written by `pipeline.finalize()` / `run.py` after validation):
- `output/extractions/{slug}.json` — the extracted rows + deal-level fields.
- Append to `state/flags.jsonl` — any ambiguities flagged during validation.
- Update `state/progress.json` — set the deal's status.

---

## Pipeline (Extractor LLM + Python Validator + scoped Adjudicator)

**Architecture (current Stage 3 MVP):** the Extractor and Adjudicator run as
clean-slate subagents administered by the outer conversation. The Validator
is **pure Python** in `pipeline.py`. No model SDK calls from Python.

### Validator philosophy: authority rule

> **Code may block on invariants. Code may not block on semantic
> interpretation of prose.**

An **invariant** is a property of the extraction JSON verifiable without
re-reading filing prose (closed-vocabulary membership, NFKC substring
check, BidderID monotonicity, exactly-one-Executed). Invariants are
**hard**; failure blocks save.

A **semantic** check requires prose interpretation ("does this sentence
imply X?"). Semantic checks are **soft** at most; they surface review
signals, never block save. Full classification of every §P-* check in
`rules/invariants.md` §"Authority rule: invariant vs semantic".

This rule prevents false-positive prose-matching from rejecting valid
extractions (e.g., imprivata's "ten of the 11 parties declined" is not
a count-of-NDAs cue; the pipeline must not treat it as one).

**Why this shape, not "two LLM agents in series" as originally drafted.**
Every invariant in `rules/invariants.md` (§P-R, §P-D, §P-G, §P-S) is
mechanically checkable — substring, regex, set membership, graph
traversal. An LLM Validator would just re-derive the same checks
non-deterministically and cost money. The Python Validator is
deterministic, free, and instant. The Adjudicator is still an LLM call,
but scoped to the one judgment call Python cannot make: "this soft flag
says the filing seems to stop mentioning this bidder mid-process — is
that a real extraction miss or is the filing genuinely silent?"

### 1. Extractor — subagent (LLM)
- **Spawned by:** the outer conversation, one subagent per deal, fresh
  context, no cross-deal knowledge.
- **Reads (from disk, via the subagent's Read tool):**
  `prompts/extract.md`, every `rules/*.md`, `data/filings/{slug}/pages.json`,
  `data/filings/{slug}/manifest.json`.
- **Emits:** a single JSON payload `{deal: {...}, events: [...]}` conforming
  to `rules/schema.md` §R1. Every event row carries `source_quote` (NFKC
  substring of the cited page) and `source_page` (integer matching
  `pages.json[i].number`).
- **Prompt builder:** `pipeline.build_extractor_prompt(slug)`.

### 2. Validator — Python (`pipeline.py`)
- **Entry:** `pipeline.validate(raw_extraction, filing) -> ValidatorResult`.
- **Runs:** every invariant in `rules/invariants.md` — §P-R1..5 (structural
  row checks), §P-D1..3 (date/BidderID integrity), §P-G2 (bid-type
  evidence), §P-S1..4 (semantic process checks).
- **Returns:** `row_flags` and `deal_flags` lists of
  `{code, severity, reason, [row_index|deal_level]}` dicts.
- **Never rewrites the extraction.** Flag-only discipline preserves the
  Extractor's output as the single source of what was extracted.

### 3. Adjudicator — subagent (LLM), scoped
- **Fires when:** the Python Validator raises a soft flag (MVP: §P-S1
  `nda_without_bid_or_drop`). No-op when zero soft flags.
- **Reads:** the flagged row + same-bidder context rows + a small window
  of filing pages.
- **Emits:** `{verdict: "upheld" | "dismissed", reason: str}` appended to
  the flag's `reason` field. Severity is NOT flipped in MVP — human review
  stays explicit.
- **Execution model:** this is an orchestrator-side LLM call only. There is
  no Python `adjudicate()` entrypoint. The orchestrator reads validator
  output, spawns the Adjudicator, mutates `raw_extraction`, and only then
  calls `pipeline.finalize()`.

### Orchestration (this conversation drives, not Python)

```
  orchestrator:
    1. spawn Extractor subagent → raw_extraction JSON (written to disk)
    2. filing = pipeline.load_filing(slug)
    3. result = pipeline.validate(raw_extraction, filing)
    4. if any(flag["severity"] == "soft" for flag in result.row_flags + result.deal_flags):
         for each soft flag, spawn Adjudicator subagent, annotate it
         on raw_extraction before finalize (orchestrator-only — no
         Python entrypoint in MVP; see pipeline.finalize() docstring)
    5. pipeline.finalize(slug, raw_extraction)
         → output/extractions/{slug}.json
         → state/flags.jsonl (append)
         → state/progress.json (update)
    6. scoring/diff.py --slug {slug}   (on reference deals)
    7. git commit
```

`run.py` is a thin CLI shim for step 5 when driving from a saved
raw-extraction file (`python run.py --slug X --raw-extraction path.json`).

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
  "rulebook_version": "<git commit sha of rules/ at time of run>",
  "deals": {
    "<slug>": {
      "status": "pending | validated | passed | passed_clean | verified | failed",
      "flag_count": 0,
      "last_run": "ISO8601",
      "last_verified_by": null,
      "last_verified_at": null,
      "notes": ""
    }
  }
}
```

**`state/flags.jsonl`** — append-only. One flag per line:
```json
{"deal": "medivation", "row_index": 7, "flag": "informal_vs_formal_borderline", "reason": "…", "source_quote": "…"}
```
For current-state queries, do not count this file raw: filter by
`logged_at >=` the deal's most recent finalize timestamp, or prefer
`output/extractions/{slug}.json` `flags[]` plus `state/progress.json`
`flag_count` as the latest authoritative view.

**`output/extractions/{deal.slug}.json`** schema conforms to `rules/schema.md`.

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
- If any 🟥 OPEN rule is encountered in `rules/*.md` → stop immediately and report. Never guess around an open question.

---

## What this skill deliberately does NOT do

Full list in `rules/schema.md` §Scope-3. In summary:

- Compute COMPUSTAT fields: `cshoc`, `gvkey`, `gvkeyT`, `gvkeyA`. Downstream merge.
- Re-derive EDGAR metadata: `DateFiled`, `FormType`, `URL`, `CIK`, `accession`. Fetcher (`manifest.json`) owns these.
- Assign `DealNumber`. Pipeline keys on `slug`; downstream joins if needed.
- Fetch any external data (news, COMPUSTAT, other filings). Only reads the filing already downloaded under `data/filings/{slug}/`.
- Fix legacy Chicago-collected rows or overwrite `reference/deal_details_Alex_2026.xlsx`.
- Cross-deal bidder canonicalization (is this deal's "Sponsor A" the same as that deal's "Sponsor A"?). Explicit non-goal.
- Re-classify the form type. The fetcher already classified it from the EDGAR index; AI copies it through unchanged.

Final Excel assembly is out of scope for the current repo. This skill stops
at JSON extraction + validator flags.

---

## When to change this file

- Never during routine extraction.
- Only when the architecture itself changes (e.g., adding a Planner or Canonicalizer agent after MVP-phase learnings).
- Architecture changes are git-committed with a clear rationale that names the assumption the new component encodes.
