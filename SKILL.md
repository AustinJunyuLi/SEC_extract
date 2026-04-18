# SKILL.md — M&A Background Extraction

**Purpose.** Given one SEC merger filing (DEFM14A / PREM14A / SC-TO-T / S-4), extract the "Background of the Merger" section into a structured row-per-event JSON matching Alex Gorbenko's auction schema.

**You are one iteration of a Ralph loop.** The outer loop (`run.py`) hands you one deal. You process it end-to-end in a fresh context, write `output/extractions/{deal}.json`, update `state/progress.json`, and exit. Do not read other deals. Do not carry state across invocations.

---

## Invocation contract

**Input** (from `run.py`):
- `deal.slug` — short identifier, e.g. `medivation`.
- `deal.filing_url` — SEC URL.
- `deal.is_reference` — bool. If true, `scoring/diff.py` will compare against `reference/alex/{slug}.json` after extraction so Austin can manually review divergences. The diff is a development aid, not a grade — Alex's workbook is a reference, not ground truth.

**Output** (to disk, before exit):
- `output/extractions/{deal.slug}.json` — the extracted rows + deal-level fields.
- Append to `state/flags.jsonl` — any ambiguities flagged during validation.
- Update `state/progress.json` — set the deal's status.

---

## Pipeline (two agents)

### 1. Extractor
- **Load:** `rules/schema.md`, `rules/events.md`, `rules/bidders.md`, `rules/bids.md`, `rules/dates.md`, `prompts/extract.md`, the filing text at `deal.filing_url`.
- **Do:** locate the "Background of the Merger" section; emit candidate rows conforming to `rules/schema.md`. Every row must include `source_quote` (verbatim filing text) and `source_page`.
- **Emit:** candidate rows as JSON array.

### 2. Validator
- **Load:** `rules/invariants.md`, `prompts/validate.md`, the Extractor's candidate rows, the original filing text (for count cross-checks).
- **Do:** run every invariant in `rules/invariants.md`. Flag ambiguities. **Do not rewrite rows** — only annotate.
- **Emit:** final rows + `flags[]`.

Both agents run in series inside this one session. No other agents at MVP.

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
5. **Informal-vs-formal classification must cite the specific phrase** that triggered the call (see `rules/bids.md` §G). Borderline calls are flagged, not forced.
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
      "status": "pending | extracted | validated | verified | failed",
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

**`output/extractions/{deal.slug}.json`** schema conforms to `rules/schema.md`.

**Status semantics:**
- `pending` — not yet run.
- `extracted` — Extractor emitted rows; Validator has not yet run.
- `validated` — Validator ran; may have hard-error flags.
- `verified` — Austin manually read the filing and adjudicated any AI-vs-Alex diff. Only set on reference deals, and only by the manual review workflow (not by the pipeline). On target deals this status is never used — they pass through `extracted` → `validated` and stop.
- `failed` — pipeline error (fetch, section-location, etc.).

---

## Fail-loud rules

- If the filing URL can't be fetched → `status: failed`, `notes: "fetch_error: <detail>"`, exit.
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

Final Excel assembly is a separate mechanical step (`run.py --rebuild-excel`), not this skill.

---

## When to change this file

- Never during routine extraction.
- Only when the architecture itself changes (e.g., adding a Planner or Canonicalizer agent after MVP-phase learnings).
- Architecture changes are git-committed with a clear rationale that names the assumption the new component encodes.
