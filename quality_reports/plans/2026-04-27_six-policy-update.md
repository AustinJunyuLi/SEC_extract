# Six-Policy Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the six rule-and-code changes in `quality_reports/specs/2026-04-27_six-policy-update.md` across rules, prompt, validator, converter, scoring, tests, and reference JSONs.

**Architecture:** Six atomic commits (C1–C6) each pair a rule rewrite with its code implementation so no intermediate state is broken. C6 is the mechanical regeneration of reference JSONs plus stale-data cleanup plus handoff doc. C7 (live re-extraction on the 9 reference deals) is deferred to a separate workstream not covered by this plan.

**Tech Stack:** Python 3.11+, pytest, openpyxl (xlsx reader), git. No new dependencies.

**Spec:** `quality_reports/specs/2026-04-27_six-policy-update.md`. The spec is the source of truth on requirements. This plan operationalizes it with exact file paths, line numbers, and code.

**Status taxonomy:**
- 🟢 = task complete and committed
- 🟡 = task in progress
- ⬜ = not yet started

---

## §0 — Non-negotiable principles (re-state before each commit)

**No backward compatibility, no shims, no preservation of stale paths.** Per the spec's §0 and the project's CLAUDE.md no-backward-compat clause, every commit deletes stale code/rules/data without leaving migration helpers, deprecated markers, annotated supersedes, or fallback readers. Git history is the compatibility record.

**Atomic commits per logical unit.** Each commit C1–C6 is one cohesive change with its rules, code, prompt, tests, and skill-file updates aligned. Do not split a concept across two commits.

**TDD where it bites.** For new validator behavior (C3 atomization checks, C4 `bid_range_must_be_informal`), write the failing test first. For deletions (C1 / C2), update the existing tests in the same commit so the suite stays green.

**Verification before each commit:**
1. `pytest tests/ -q` passes.
2. `python -c "import pipeline; import scripts.build_reference; import scoring.diff"` succeeds.
3. `git diff --stat` matches the file list in this plan's task.
4. After C1 + C2 specifically: `grep -rn "non_us\|\"public\"\|Acquirer_legal" rules/ prompts/ pipeline.py scripts/ scoring/ tests/` returns zero matches.

---

## Pre-flight (one-time setup)

### Step P.1 — Confirm starting state

- [ ] Run from repo root and confirm clean working tree on `main`:

```bash
cd /Users/austinli/bids_try
git status -sb
git log --oneline -3
```

Expected: branch `main`, last commit `f1c7264 docs(handoff): post-six-decisions handoff for re-extraction on other machine`. Working tree may have unstaged modifications from prior sessions; **do not commit those as part of this batch** — stash or discard before starting C1:

```bash
git stash push -u -m "pre-six-policy-update wip"
```

After C1–C6 complete, decide separately whether to restore the stash.

### Step P.2 — Create work branch

- [ ] Create a new branch off `main`:

```bash
git checkout -b six-policy-update-2026-04-27
```

### Step P.3 — Tag baseline reference state for the C6 diff

- [ ] Tag current `reference/alex/*.json` state so C6 can diff against it:

```bash
git tag pre-reextract-2026-04-27
```

This tag is consumed by Step T6.6's `git diff` verification.

### Step P.4 — Verify pytest baseline

- [ ] Run the test suite and record the baseline pass count:

```bash
pytest tests/ -q
```

Expected: all tests pass on `main` (the test suite is green at start). If anything fails, **stop and resolve before proceeding** — the plan assumes a green baseline.

---

## Task 1 — C1: Drop `non_us` + `public`, flatten `bidder_type` to scalar

**Goal:** `bidder_type` collapses from `{"base": "s", "non_us": false, "public": null}` to `"s"`. The `non_us` and `public` fields disappear from schema, rules, prompt, code, tests, and (after C6) reference JSONs.

**Files this commit touches:**
- Modify: `rules/bidders.md` — rewrite §F1, delete §F2
- Modify: `rules/schema.md:244–251` — rewrite `bidder_type` entry
- Modify: `prompts/extract.md:74` — delete `bidder_type.public` paragraph; line 121 change `bidder_type: null` example
- Modify: `pipeline.py` — comparator changes from dict to string
- Modify: `scripts/build_reference.py` — delete `_bidder_type_note_signals`, rewrite `build_bidder_type`, update callsites
- Modify: `scripts/export_alex_csv.py:206–240` — replace `_bidder_type_components` with scalar emission
- Modify: `scoring/diff.py` — comparator works on scalar
- Modify: `tests/test_reference_converter.py` — assertions updated to scalar
- Modify: `tests/test_diff.py` — same
- Modify: `SKILL.md` — drop tri-state public language
- Modify: `skill_open_questions.md` — drop §F2 / public-status entries (the questions no longer exist)

### Step T1.1 — Rewrite `rules/bidders.md` §F1 and delete §F2

- [ ] Open `rules/bidders.md` and replace lines 232–402 (currently §F2 followed by §F1) with the following new §F1 (no §F2; the classification logic moves entirely into the simpler §F1):

````markdown
### §F1 — Bidder type canonical format (🟩 RESOLVED, 2026-04-18; rewritten 2026-04-27 per Alex directive)

**Decision.** `bidder_type` is a **scalar string** (not an object) holding one of three values: `"s"`, `"f"`, `"mixed"`, or `null`.

```json
"bidder_type": "s"
```

**Values.**
- `"s"` — strategic. Filing names a corporate operating buyer (active in target's industry or adjacent).
- `"f"` — financial. Filing names a private-equity firm, buyout fund, sovereign-wealth fund, family office, pension fund, or SPAC.
- `"mixed"` — consortium with both strategic and financial members.
- `null` — filing does not classify.

**Why scalar, not structured object.** The pre-2026-04-27 schema carried a nested object `{base, non_us, public}` to capture three orthogonal axes. Per Alex's 2026-04-27 directive we no longer record geography or capital structure of the bidding firm. With one axis remaining, the object shape is dead weight; the scalar is direct.

**Decision rule** (evaluate top-to-bottom; first match wins):

| # | Filing signal | `bidder_type` |
|---|---|---|
| 1 | Filing explicitly names a **PE firm / buyout fund / private-equity sponsor** as the bidder | `"f"` |
| 2 | Filing names a **publicly traded operating company** as the bidder | `"s"` |
| 3 | Point of contact is a **CEO or named corporate executive**; letterhead / counsel is corporate | `"s"` |
| 4 | Point of contact is a **partner / managing director / principal at a fund**; letterhead is fund | `"f"` |
| 5 | Consortium explicitly described as including **both** PE and strategic members | `"mixed"` |
| 6 | **Sovereign-wealth fund, pension fund, or family office** acting alone | `"f"` |
| 7 | **SPAC** (special-purpose acquisition company) | `"f"` |
| 8 | Genuinely ambiguous → default | `"f"` + `bidder_type_ambiguous` (soft flag) |

**Why default `"f"` on ambiguity.** Anecdotally, when filings are coy about bidder identity, it's usually because the bidder is a PE sponsor. Operating companies have less competitive reason to hide their name.

**Rejected alternatives.**
- **Default `"s"` on ambiguity** — empirically wrong direction.
- **Hard-flag all ambiguity** — creates too much manual-review burden on a recoverable judgment.

**Cross-references.**
- `rules/schema.md` §R1 — event-level `bidder_type` field signature.
- `rules/bidders.md` §E1 (atomization), §E3 (canonical IDs).

---
````

- [ ] Verify §F1 is the only bidder-type section (§F2 should be gone) by grepping:

```bash
grep -n "^### §F" rules/bidders.md
```

Expected: only `§F1` appears as a section heading. Other sections (§F3 if any, etc.) untouched.

### Step T1.2 — Rewrite `rules/schema.md` §R1 entry for `bidder_type`

- [ ] In `rules/schema.md`, replace lines 244–251 (the `bidder_type` entry) with:

```markdown
- `bidder_type` — string OR null. One of `"s"` / `"f"` / `"mixed"` per `rules/bidders.md` §F1 (rewritten 2026-04-27). Geography (`non_us`) and listing status (`public`) are NOT recorded — Alex's 2026-04-27 directive dropped both fields entirely.
```

- [ ] In the same file, find the §R1 footer cross-references (around line 297) and update:

```markdown
- `rules/bidders.md` §F1 — `bidder_type` canonical scalar format.
```

(remove the `§F2` entry if present in cross-refs; it doesn't exist anymore.)

### Step T1.3 — Update `prompts/extract.md`

- [ ] Delete the entire bullet at line 74 (the `bidder_type.public` strict-filing-only constraint paragraph).
- [ ] In the example output skeleton (around line 121), confirm `"bidder_type": null` already uses scalar form. No change needed if it does.
- [ ] In the self-check list (lines 145–151), remove any line that mentions `non_us` or `public` strictness. Keep all other self-checks.

### Step T1.4 — Write failing tests for scalar `bidder_type`

- [ ] Open `tests/test_reference_converter.py` and at line 18 (the existing `assert g_and_w_nda["bid_type"] is None` test or its sibling), add a NEW test before any existing test that asserts the dict shape:

```python
def test_bidder_type_emits_scalar_after_drop_geography_and_listing():
    """C1 — bidder_type is a scalar string, not a dict.

    Pre-C1 the converter emitted {"base": "s", "non_us": ..., "public": ...}.
    Post-C1 it emits "s" (or "f" / "mixed" / None).
    """
    from scripts.build_reference import build_deal

    payload = build_deal("medivation")
    for ev in payload["events"]:
        bt = ev.get("bidder_type")
        assert bt is None or isinstance(bt, str), f"bidder_type must be str|None, got {type(bt).__name__}: {bt!r}"
        if isinstance(bt, str):
            assert bt in ("s", "f", "mixed"), f"unexpected bidder_type value: {bt!r}"
```

- [ ] Run it:

```bash
pytest tests/test_reference_converter.py::test_bidder_type_emits_scalar_after_drop_geography_and_listing -v
```

Expected: **FAIL** with assertion error showing dict shape (because C1 hasn't landed yet).

### Step T1.5 — Replace `_bidder_type_note_signals` and rewrite `build_bidder_type` in the converter

- [ ] In `scripts/build_reference.py`, **delete the entire function `_bidder_type_note_signals`** (currently lines 546–591). 

- [ ] Replace the function `build_bidder_type` (currently lines 594–634) with this scalar-returning version:

```python
def build_bidder_type(r: RawRow) -> str | None:
    """Return scalar bidder_type per `rules/bidders.md` §F1 (2026-04-27).

    Reads the four boolean columns from Alex's xlsx (bt_financial,
    bt_strategic, bt_mixed, bt_nonUS — the last is now ignored) plus the
    free-text `bidder_type_note`. Returns one of "s" / "f" / "mixed" / None.

    Geography (non_us) and listing status (public) are no longer recorded
    per Alex's 2026-04-27 directive; this function does not attempt to
    parse them from the note column.
    """
    fin   = _bool(r.get("bt_financial"))
    strat = _bool(r.get("bt_strategic"))
    mixed = _bool(r.get("bt_mixed"))
    note  = r.get("bidder_type_note")

    # Boolean-column path (Alex's 4-boolean schema).
    if mixed:
        return "mixed"
    if fin and strat:
        return "mixed"
    if fin:
        return "f"
    if strat:
        return "s"

    # Note-column fallback when boolean columns are blank but the note has
    # signal. Tokenize the note and match the F/S/mixed letters.
    if isinstance(note, str):
        normalized = re.sub(r"non[-\s]?us", "", note.strip().lower())
        tokens = re.findall(r"[a-z]+|\d+[a-z]+", normalized)
        has_financial = any(t in {"f", "financial"} or re.fullmatch(r"\d+f", t) for t in tokens)
        has_strategic = any(t in {"s", "strategic"} or re.fullmatch(r"\d+s", t) for t in tokens)
        has_mixed     = "mixed" in tokens
        if has_mixed or (has_financial and has_strategic):
            return "mixed"
        if has_financial:
            return "f"
        if has_strategic:
            return "s"

    return None
```

- [ ] Update every callsite in `build_reference.py` that used `bt["base"]`, `bt["non_us"]`, or `bt["public"]` to use the scalar directly. Run:

```bash
grep -n 'bidder_type\["base"\]\|bidder_type\["non_us"\]\|bidder_type\["public"\]\|bt\["base"\]\|bt\["non_us"\]\|bt\["public"\]\|\.get("base")\|\.get("non_us")\|\.get("public")' scripts/build_reference.py
```

For each match, examine the context. The expected pattern: `bidder_type` (or local alias `bt`) is now a `str | None`, so:
- `bt["base"]` becomes `bt`
- `bt["non_us"]` removed entirely
- `bt["public"]` removed entirely

**Common callsite — the §Q5 Medivation expansion at line ~999:**
The line `sanofi_type = ev.get("bidder_type")` is fine — it returns the scalar now. The line that copies `bidder_type` onto cloned rows works unchanged.

### Step T1.6 — Verify the scalar test now passes

- [ ] Run:

```bash
pytest tests/test_reference_converter.py::test_bidder_type_emits_scalar_after_drop_geography_and_listing -v
```

Expected: **PASS**.

### Step T1.7 — Update `scoring/diff.py` comparator

- [ ] Open `scoring/diff.py`. The line at `COMPARE_EVENT_FIELDS` (line 33) lists `"bidder_type"`. The comparator code that handles dict-equality for `bidder_type` no longer applies because the field is now scalar. Find the dict-aware comparator and simplify.

```bash
grep -n "bidder_type" scoring/diff.py
```

For every occurrence, check whether it assumes `bidder_type` is a dict (e.g., `bt.get("base")`). Replace with scalar comparison. The default `==` works on scalars.

If no specialized dict-handling code is present, the default field-equality compare is fine — no change needed.

### Step T1.8 — Replace `_bidder_type_components` in `scripts/export_alex_csv.py`

- [ ] In `scripts/export_alex_csv.py`, delete the entire function `_bidder_type_components` (currently lines 206–240).

- [ ] Replace it with a scalar emitter:

```python
def _bidder_type_scalar(bt: str | None) -> str:
    """Emit bidder_type for CSV export. Per `rules/bidders.md` §F1
    (2026-04-27) bidder_type is a scalar string in {"s", "f", "mixed"} or
    null. CSV represents null as "NA".
    """
    if bt is None:
        return "NA"
    return bt
```

- [ ] Update the CSV header row (around line 86–110, search for `bidder_type` in the column list) to remove `bidder_type_financial`, `bidder_type_strategic`, `bidder_type_mixed`, `bidder_type_nonUS`, `bidder_type_note` and replace with a single column `bidder_type`.

```bash
grep -n 'bidder_type_financial\|bidder_type_strategic\|bidder_type_mixed\|bidder_type_nonUS\|bidder_type_note' scripts/export_alex_csv.py
```

Replace each occurrence in the header list and in the row-emission code with a single `bidder_type` column populated by `_bidder_type_scalar(ev.get("bidder_type"))`.

### Step T1.9 — Update / delete legacy tests

- [ ] In `tests/test_reference_converter.py`, find every assertion that compares `bidder_type` to a dict. Run:

```bash
grep -n 'bidder_type.*non_us\|bidder_type.*public\|"base":\|"non_us":\|"public":' tests/test_reference_converter.py
```

For each line, replace the dict-compare with scalar-compare. Examples:
- `assert sanofi_bid["bidder_type"] == {"base": "s", "non_us": True, "public": True}` → `assert sanofi_bid["bidder_type"] == "s"`
- `assert ev["bidder_type"]["base"] == "f"` → `assert ev["bidder_type"] == "f"`
- `assert ev["bidder_type"]["public"] is None` → DELETE the assertion entirely (the field no longer exists).

- [ ] Delete the test `test_bidder_type_pe_token_keeps_public_null` (around line 80–102) entirely. The behavior it tested (PE sponsor → `public = null`) no longer exists.

- [ ] In `tests/test_diff.py`, repeat the same exercise:

```bash
grep -n '"base":\|"non_us":\|"public":' tests/test_diff.py
```

Replace dict-shaped test data with scalar values. E.g., `"bidder_type": {"base": "s", "non_us": False, "public": None}` becomes `"bidder_type": "s"`.

### Step T1.10 — Update `SKILL.md` and `skill_open_questions.md`

- [ ] Search both files for references to the deleted concepts:

```bash
grep -n "non_us\|tri-state\|F2\|public-status\|listing status" SKILL.md skill_open_questions.md
```

For each match:
- If the line states a rule or contract that no longer exists (e.g., "tri-state public"), DELETE the line.
- If the line is a tracker entry referencing §F2's open question (which is now moot), DELETE the tracker entry.
- Do NOT add annotation, supersede markers, or "see new spec" cross-links — per the spec's §0, history goes in git, not in skill files.

### Step T1.11 — Verify no leftover references

- [ ] Run the orphan-grep:

```bash
grep -rn "non_us\|\"public\":\|\.public\|Acquirer_legal" rules/ prompts/ pipeline.py scripts/ scoring/ tests/ SKILL.md skill_open_questions.md 2>&1 | grep -v "^Binary file"
```

Expected: no matches in `rules/`, `prompts/`, `pipeline.py`, `scripts/`, `scoring/`, `tests/`, `SKILL.md`, `skill_open_questions.md` for `non_us` or `\"public\":`. (The `Acquirer_legal` cleanup is C2's job and may still appear here — that's expected.)

If matches appear in `non_us` / `public` searches, find and remove them.

### Step T1.12 — Run full test suite

- [ ] Run:

```bash
pytest tests/ -q
```

Expected: all tests pass.

### Step T1.13 — Commit C1

- [ ] Stage and commit:

```bash
git add rules/bidders.md rules/schema.md prompts/extract.md pipeline.py scripts/build_reference.py scripts/export_alex_csv.py scoring/diff.py tests/ SKILL.md skill_open_questions.md
git diff --cached --stat
git commit -m "$(cat <<'EOF'
schema: drop bidder_type.non_us and bidder_type.public; flatten to scalar

Per Alex 2026-04-27 directive: geography and listing status of the
bidding firm are not recorded. bidder_type collapses from
{"base": "s", "non_us": false, "public": null} to "s".

Touches:
- rules/bidders.md: §F1 rewritten to scalar; §F2 deleted
- rules/schema.md: §R1 bidder_type entry rewritten
- prompts/extract.md: drop strict-filing-only-tri-state paragraph
- scripts/build_reference.py: delete _bidder_type_note_signals;
  rewrite build_bidder_type to return scalar
- scripts/export_alex_csv.py: 5 CSV columns collapse to 1
- tests/: assertions updated to scalar; tri-state test deleted

No backward compatibility, no shims. See spec
quality_reports/specs/2026-04-27_six-policy-update.md for context.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] Mark Task 1 complete in this plan: change the heading to `## Task 1 — C1: ... 🟢`.

---

## Task 2 — C2: Drop legal acquirer

**Goal:** Delete `Acquirer_legal` field everywhere. `Acquirer` records the operating entity only. The 4 sponsor-backed reference deals get `Acquirer` rewritten by a slimmed-down converter override (`Q6_ACQUIRER_REWRITE`).

**Files this commit touches:**
- Modify: `rules/schema.md` — delete §N4 entirely; rewrite §R1 `Acquirer` entry; delete `Acquirer_legal` entry
- Modify: `prompts/extract.md:79` — rewrite the `Acquirer is the operating acquirer` paragraph; example skeleton at line 106 drops `Acquirer_legal`
- Modify: `scripts/build_reference.py` — delete `Q6_ACQUIRER_OVERRIDES`, delete `apply_q6_acquirer_override`, delete its call, delete `Acquirer_legal` from deal-init, add `Q6_ACQUIRER_REWRITE` + `apply_q6_acquirer_rewrite`
- Modify: `scoring/diff.py:44` — remove `Acquirer_legal` from `COMPARE_DEAL_FIELDS`
- Modify: `tests/test_reference_converter.py` — delete any `Acquirer_legal` assertions
- Modify: `SKILL.md`, `skill_open_questions.md` — drop §N4 references

### Step T2.1 — Delete `rules/schema.md` §N4

- [ ] In `rules/schema.md`, delete lines 397–478 (the entire §N4 section, from `### §N4 — \`Acquirer\` semantics:` through the closing `---`).

### Step T2.2 — Rewrite `rules/schema.md` §R1 `Acquirer` entry, delete `Acquirer_legal` entry

- [ ] In `rules/schema.md`, replace lines 197–204 (the `Acquirer` and `Acquirer_legal` entries) with a single `Acquirer` entry:

```markdown
- `Acquirer` — string. The **operating acquirer** — the entity that actually negotiated and will own the target's assets. Skip Delaware shells and merger-vehicle entities formed solely to execute the transaction (typically named `<Word> Holdings Inc.`, `<Word> Acquisition Inc.`, `<Word> Merger Sub`). For consortium / club deals, the **lead sponsor** named in the primary position ("BC Partners, together with [others]"); fall back to the filing's verbatim consortium label only when no lead is identifiable. For sponsor-backed corporate buyers (operating company funded by a sponsor that is not itself the bidder), the operating company; the funding sponsor goes in the `Executed` row's `additional_note`. Per Alex 2026-04-27 directive: the legal shell is NOT recorded separately.
```

- [ ] Verify `Acquirer_legal` is fully gone from this file:

```bash
grep -n "Acquirer_legal" rules/schema.md
```

Expected: zero matches.

### Step T2.3 — Update `prompts/extract.md`

- [ ] Replace line 79 (the `**\`Acquirer\` is the operating acquirer, not the legal shell (§N4).**` bullet) with:

```markdown
- **`Acquirer` is the operating acquirer.** Populate `Acquirer` with the entity that actually negotiated and will own the target's assets. Skip Delaware shells / merger-vehicle entities formed solely to execute the transaction (typically named `<Word> Holdings Inc.`, `<Word> Acquisition Inc.`, `<Word> Parent Inc.`, `<Word> Merger Sub`). For PE consortia / club deals, populate `Acquirer` with the **lead sponsor** the filing identifies in the primary position ("BC Partners, together with …"); fall back to the filing's verbatim consortium label (e.g., `"Buyer Group"`) only when no lead is identifiable. For sponsor-backed corporate buyers (operating company funded by a sponsor that is not itself the bidder, e.g., CSC ServiceWorks funded by Pamplona for mac-gray), use the operating company in `Acquirer` and document the funding sponsor in the `Executed` row's `additional_note`. Per Alex 2026-04-27: the legal shell is NOT recorded.
```

- [ ] In the output-format example (around line 102–113), delete line 106 (`"Acquirer_legal": null,`).

### Step T2.4 — Delete `Q6_ACQUIRER_OVERRIDES` and `apply_q6_acquirer_override` in the converter

- [ ] In `scripts/build_reference.py`, delete:
  - The §Q6 docstring block at lines 82–99 (the docstring header explaining sponsor-backed deals).
  - The `Q6_ACQUIRER_OVERRIDES` dict at lines 140–183.
  - The `apply_q6_acquirer_override` function at lines 186–207.
  - The call to `apply_q6_acquirer_override(slug, deal)` (search the file):

```bash
grep -n "apply_q6_acquirer_override" scripts/build_reference.py
```

Delete every match.

### Step T2.5 — Add `Q6_ACQUIRER_REWRITE` and `apply_q6_acquirer_rewrite`

- [ ] At the location where `Q6_ACQUIRER_OVERRIDES` was (around line 140), add the new slim rewrite dict:

```python
# §Q6 — Acquirer rewrite for the 4 sponsor-backed reference deals.
# Per Alex 2026-04-27 directive, only the operating acquirer is recorded;
# the legal shell is NOT preserved as a sidecar. Alex's xlsx Acquirer
# column for these 4 deals contains the consortium label or shell name;
# the converter overwrites it with the operating-acquirer string.
# Operational acquirer values are sourced from each filing's signature
# block (signature page on the merger agreement).
Q6_ACQUIRER_REWRITE: dict[str, str] = {
    "petsmart-inc": "BC Partners, Inc.",
    "mac-gray":     "CSC ServiceWorks, Inc.",
    "zep":          "New Mountain Capital",
    "saks":         "Hudson's Bay Company",
}


def apply_q6_acquirer_rewrite(slug: str, deal: dict[str, Any]) -> None:
    """§Q6 — overwrite deal['Acquirer'] with the operating acquirer for the
    4 sponsor-backed reference deals. Mutates `deal` in place. Records the
    original xlsx string in an `acquirer_normalized` info flag for audit.
    """
    new_value = Q6_ACQUIRER_REWRITE.get(slug)
    if new_value is None:
        return
    original = deal.get("Acquirer")
    if original == new_value:
        return
    deal["Acquirer"] = new_value
    deal["deal_flags"].append({
        "code": "acquirer_normalized",
        "severity": "info",
        "reason": (
            f"§Q6: xlsx Acquirer={original!r} normalized to operating "
            f"acquirer {new_value!r} per Alex 2026-04-27 directive."
        ),
    })
```

- [ ] Find where `apply_q6_acquirer_override(slug, deal)` was called (you deleted it in T2.4) and replace it with `apply_q6_acquirer_rewrite(slug, deal)`. The line number was around 1074 — re-grep to confirm:

```bash
grep -n "apply_q6_acquirer" scripts/build_reference.py
```

Expected: only the new `apply_q6_acquirer_rewrite` (the function definition) and one call site.

### Step T2.6 — Remove `Acquirer_legal` from deal-init

- [ ] In `scripts/build_reference.py`, find the `build_deal_object` function (around line 464). Delete lines 479–482 (the `Acquirer_legal` block and its comment):

Before:
```python
    "Acquirer":          pick("Acquirer"),
    # §N4 sidecar; populated by apply_q6_acquirer_override() for the
    # 4 sponsor-backed reference deals (petsmart-inc, mac-gray, zep,
    # saks). Null for everything else.
    "Acquirer_legal":    None,
```

After:
```python
    "Acquirer":          pick("Acquirer"),
```

### Step T2.7 — Remove `Acquirer_legal` from `scoring/diff.py`

- [ ] In `scoring/diff.py:43–46`, replace:

```python
COMPARE_DEAL_FIELDS = [
    "TargetName", "Acquirer", "Acquirer_legal", "DateAnnounced",
    "DateEffective", "auction", "all_cash",
]
```

with:

```python
COMPARE_DEAL_FIELDS = [
    "TargetName", "Acquirer", "DateAnnounced",
    "DateEffective", "auction", "all_cash",
]
```

### Step T2.8 — Remove `Acquirer_legal` test assertions

- [ ] Search:

```bash
grep -rn "Acquirer_legal" tests/
```

For each match, delete the assertion (or whole test if its sole purpose was checking `Acquirer_legal`).

### Step T2.9 — Update `SKILL.md` and `skill_open_questions.md`

- [ ] Search:

```bash
grep -n "N4\|Acquirer_legal\|legal shell\|sidecar\|operating acquirer" SKILL.md skill_open_questions.md
```

Delete entries that reference §N4, the sidecar mechanic, or `Acquirer_legal`. The `operating acquirer` concept survives — keep mentions of it where they describe the new (single-field) behavior.

### Step T2.10 — Verify no leftover references

```bash
grep -rn "Acquirer_legal\|N4\|sidecar" rules/ prompts/ pipeline.py scripts/ scoring/ tests/ SKILL.md skill_open_questions.md 2>&1 | grep -v "^Binary file"
```

Expected: zero `Acquirer_legal` matches; zero `§N4` matches; zero `sidecar` matches in the rule/code surface. (References inside `quality_reports/decisions/` are about to be deleted in C6 — leave them.)

### Step T2.11 — Run full test suite

```bash
pytest tests/ -q
```

Expected: all tests pass.

### Step T2.12 — Commit C2

```bash
git add rules/schema.md prompts/extract.md scripts/build_reference.py scoring/diff.py tests/ SKILL.md skill_open_questions.md
git diff --cached --stat
git commit -m "$(cat <<'EOF'
schema: drop Acquirer_legal sidecar; record operating acquirer only

Per Alex 2026-04-27 directive: the legal shell is not preserved as a
sidecar field. Acquirer holds the operating entity; for the 4 sponsor-
backed reference deals (petsmart-inc, mac-gray, zep, saks) the converter
rewrites Alex's xlsx Acquirer column to the operational name and emits
an info flag `acquirer_normalized` for audit.

Touches:
- rules/schema.md: §N4 deleted; §R1 Acquirer entry rewritten; Acquirer_legal entry deleted
- prompts/extract.md: rewrite operating-acquirer paragraph; drop Acquirer_legal from example
- scripts/build_reference.py: delete Q6_ACQUIRER_OVERRIDES + apply_q6_acquirer_override;
  add Q6_ACQUIRER_REWRITE + apply_q6_acquirer_rewrite (operating-only)
- scoring/diff.py: drop Acquirer_legal from COMPARE_DEAL_FIELDS
- tests/: delete Acquirer_legal assertions

No backward compatibility, no shims. See spec
quality_reports/specs/2026-04-27_six-policy-update.md for context.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] Mark Task 2 complete: `## Task 2 — C2: ... 🟢`.

---

## Task 3 — C3: Universal atomization

**Goal:** Bidders never aggregate. The `Executed` row joint-bidder collapse (§E2.a) is deleted. The `§E2.b` group-narrated NDA aggregation table simplifies to "atomize per identifiable signer; emit count-many placeholder rows when filing gives a count without names." A new `Q7_EXECUTED_MEMBERS` static dict drives Executed-row expansion for the 4 sponsor-backed reference deals (petsmart 1→5; mac-gray 1→2; zep 1→1; saks 1→1).

**Files this commit touches:**
- Modify: `rules/bidders.md` — delete §E2.a; rewrite §E2.b table; rewrite §E1 to make atomization unconditional
- Modify: `prompts/extract.md` — Step 7 references §E2.a / §E2.b; simplify; add Executed-atomization instruction
- Modify: `scripts/build_reference.py` — add `Q7_EXECUTED_MEMBERS` and `apply_q7_executed_atomization`; call from build pipeline
- Modify: `tests/test_reference_converter.py` — add petsmart 5-row + mac-gray 2-row tests
- Modify: `SKILL.md`, `skill_open_questions.md` — drop §E2.a / §E2.b references where stale

### Step T3.1 — Delete `rules/bidders.md` §E2.a entirely

- [ ] In `rules/bidders.md`, delete lines 46–78 (the entire `### §E2.a — Executed-row joint-bidder exception` section, from the heading through the closing line before §E2.b).

### Step T3.2 — Rewrite `rules/bidders.md` §E2.b

- [ ] Replace lines 80–106 (`### §E2.b — Group-narrated NDA aggregation` through the cross-references block) with this collapsed version:

````markdown
### §E2.b — Group-narrated event atomization (🟩 RESOLVED, 2026-04-27 per Alex directive)

**Decision.** Filing granularity decides the shape — but every event of every type atomizes per identifiable signer. There is no "consortium-as-1-row" shortcut for any event type, including Executed.

**Rule.**

| Filing narrates the event as… | Emit |
|---|---|
| Named individual signers (e.g., *"BC Partners, Caisse, GIC, … each executed CAs"*) | **N rows**, one per named signer per §E3 |
| Numeric count without names (e.g., *"15 financial sponsors executed CAs"*) | **N rows**, where N is the stated count, with `bidder_alias` placeholders (`"Strategic 1"`, `"Financial 1"`, …) per §E5 |
| Single consortium event with no per-constituent detail and no count (e.g., *"Buyer Group executed a CA on 7/11/2013"*) | **N rows**, where N is the number of consortium constituents named elsewhere in the filing. If the filing names zero constituents, emit one row per constituent the merger-agreement signature block names. If the filing names neither count nor constituents, emit one row with `bidder_alias = filing's consortium label` and `joint_bidder_members = null`. |

The pre-2026-04-27 §E2.a exception (Executed-row collapse-to-1) is deleted: when the merger-agreement counterparty is a consortium (e.g., petsmart's BC Partners + Caisse + GIC + StepStone + Longview), emit one Executed row per constituent, all with the same date.

**Rationale.** Per Alex 2026-04-27 directive: atomization is unconditional and applies symmetrically to NDA, Bid, Drop, Restarted, Terminated, and Executed. This matches the `DropSilent` convention (§I1) of one row per bidder.

**Cross-references.**
- §E1 (universal atomization).
- §E3 (canonical IDs / placeholders).
- §E5 (numeric-count → row-count commitment).
- `rules/events.md` §I1 (consortium-drop splitting).
````

### Step T3.3 — Strengthen `rules/bidders.md` §E1

- [ ] Find §E1 in `rules/bidders.md` (around line 415, search for `### §E1`):

```bash
grep -n "^### §E1" rules/bidders.md
```

- [ ] In the §E1 "Rule" subsection, ensure the language reads (rewriting if needed):

```markdown
**Rule.**
- Atomization is **unconditional**. There are no exceptions — NDA, Bid, Drop*, Restarted, Terminated, AND Executed all atomize one row per bidder.
- No aggregated per-bidder rows. No aggregated per-group rows.
- Each atomized row carries its own `source_quote` for the specific event.
- Anonymous bidders get placeholder names per §E3.
- Joint bidders are handled per §E2 (every constituent gets its own row).
```

If the existing §E1 already says this, leave it. If it has carve-outs ("Executed is the exception", "single consortium row when filing aggregates"), rewrite to match the unconditional version.

### Step T3.4 — Update `prompts/extract.md` Step 7

- [ ] Find Step 7 of the extractor instructions (around line 49, search for `Handle group/joint/aggregate rows`):

```bash
grep -n "Handle group/joint/aggregate" prompts/extract.md
```

- [ ] Replace the bullet that references §E2.a (around line 49) with this version:

```markdown
7. **Handle group/joint/aggregate rows.** Apply `rules/bidders.md` §E1 (atomize events — UNCONDITIONALLY, including Executed), §E2 (joint bidders), §E2.b (filing-granularity atomization table), and §E5 (unnamed-party quantifiers: exact counts stay exact; `"several"` = 3 minimum; vaguer plurals emit one placeholder plus ambiguity flag). When the merger agreement is signed by a consortium, emit one `Executed` row per signer named in the signature block; do NOT collapse to a single Executed row. See `rules/bidders.md` for the full decision tables and `joint_bidder_members` flag shapes.
```

(The original line referenced `§E2.a (Executed collapse to one row)` and `§E2.b (NDA granularity follows filing narration)` — both behaviors are now subsumed into the unconditional rule.)

### Step T3.5 — Write failing tests for Executed atomization

- [ ] In `tests/test_reference_converter.py`, append new tests (any location after the existing tests is fine):

```python
def test_petsmart_executed_atomizes_to_five_rows():
    """C3 — petsmart's Buyer Group consortium emits 5 Executed rows
    (BC Partners + Caisse + GIC + StepStone + Longview), one per
    consortium signer named in the merger-agreement signature block.
    """
    from scripts.build_reference import build_deal

    payload = build_deal("petsmart-inc")
    executed_rows = [ev for ev in payload["events"] if ev.get("bid_note") == "Executed"]
    assert len(executed_rows) == 5, (
        f"expected 5 atomized Executed rows for petsmart-inc; "
        f"got {len(executed_rows)}"
    )
    aliases = [ev.get("bidder_alias") for ev in executed_rows]
    expected = {"BC Partners, Inc.", "La Caisse", "GIC Pte Ltd",
                "StepStone Group", "Longview Asset Management"}
    assert set(aliases) == expected, (
        f"expected aliases {expected}; got {set(aliases)}"
    )


def test_mac_gray_executed_atomizes_to_two_rows():
    """C3 — mac-gray's CSC + Pamplona consortium emits 2 Executed rows."""
    from scripts.build_reference import build_deal

    payload = build_deal("mac-gray")
    executed_rows = [ev for ev in payload["events"] if ev.get("bid_note") == "Executed"]
    assert len(executed_rows) == 2, (
        f"expected 2 atomized Executed rows for mac-gray; "
        f"got {len(executed_rows)}"
    )
    aliases = [ev.get("bidder_alias") for ev in executed_rows]
    expected = {"CSC ServiceWorks, Inc.", "Pamplona Capital Partners"}
    assert set(aliases) == expected
```

- [ ] Run them to confirm failure:

```bash
pytest tests/test_reference_converter.py::test_petsmart_executed_atomizes_to_five_rows tests/test_reference_converter.py::test_mac_gray_executed_atomizes_to_two_rows -v
```

Expected: **FAIL** (the converter still emits 1 Executed row per deal because Q7 doesn't exist yet).

### Step T3.6 — Add `Q7_EXECUTED_MEMBERS` and `apply_q7_executed_atomization`

- [ ] In `scripts/build_reference.py`, add these definitions in the §Q-overrides region (somewhere near `Q6_ACQUIRER_REWRITE` you added in C2, around line 140):

```python
# §Q7 — Executed-row atomization for the consortium reference deals.
# Per `rules/bidders.md` §E1 + §E2.b (rewritten 2026-04-27): when the
# merger-agreement counterparty is a consortium, emit one Executed row
# per signer named in the merger-agreement signature block. Member
# names sourced from each filing's signature page.
#
# Single-sponsor deals (zep, saks) appear here for documentation but
# the function below short-circuits when `len(members) == 1` (no
# expansion needed).
Q7_EXECUTED_MEMBERS: dict[str, list[str]] = {
    "petsmart-inc": [
        "BC Partners, Inc.",
        "La Caisse",
        "GIC Pte Ltd",
        "StepStone Group",
        "Longview Asset Management",
    ],
    "mac-gray": [
        "CSC ServiceWorks, Inc.",
        "Pamplona Capital Partners",
    ],
    "zep":  ["New Mountain Capital"],
    "saks": ["Hudson's Bay Company"],
}


def apply_q7_executed_atomization(
    slug: str, events: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """§Q7 — atomize Executed row(s) per consortium constituent.

    For consortium-signed mergers, the xlsx contains a single Executed
    row whose `bidder_alias` is the consortium label or shell. This
    function clones the row N times, one per member in
    `Q7_EXECUTED_MEMBERS[slug]`, sets `bidder_alias` and
    `bidder_name` per member, removes `joint_bidder_members` (no
    longer needed because each row IS a member), and emits an info
    flag `executed_atomized` per row.

    For single-member entries (zep, saks) the function short-circuits:
    no expansion, but still emits the `executed_atomized` flag for
    audit-trail consistency.
    """
    members = Q7_EXECUTED_MEMBERS.get(slug)
    if not members:
        return events

    out: list[dict[str, Any]] = []
    for ev in events:
        if ev.get("bid_note") != "Executed":
            out.append(ev)
            continue

        original_alias = ev.get("bidder_alias")
        for i, member_name in enumerate(members):
            new_ev = json.loads(json.dumps(ev, default=str))
            new_ev["bidder_alias"] = member_name
            # Canonical id assignment is deferred to canonicalize_bidders;
            # we set bidder_name to None here so the canonicalizer assigns
            # a fresh bidder_NN id in narrative order. (For single-member
            # deals we also clear it — consistency.)
            new_ev["bidder_name"] = None
            new_ev["joint_bidder_members"] = None
            new_ev["flags"] = list(ev.get("flags") or []) + [{
                "code": "executed_atomized",
                "severity": "info",
                "reason": (
                    f"§Q7 (per §E1+§E2.b 2026-04-27): xlsx Executed row "
                    f"alias={original_alias!r} atomized to member "
                    f"{i+1}/{len(members)} = {member_name!r}."
                ),
            }]
            out.append(new_ev)
    return out
```

### Step T3.7 — Wire `apply_q7_executed_atomization` into the build pipeline

- [ ] Find the build pipeline. The §Q5 Medivation atomization is called from `build_deal` (search for `apply_q5_medivation`):

```bash
grep -n "apply_q5_medivation\|apply_q2_zep\|apply_q6_acquirer" scripts/build_reference.py
```

- [ ] In `build_deal` (or wherever the pipeline assembles `events` and calls `apply_q5_medivation` and `apply_q2_zep`), add the call to `apply_q7_executed_atomization` AFTER `apply_q5_medivation` and `apply_q2_zep` and BEFORE the canonicalization step. Example insertion point:

```python
    events = apply_q2_zep(events)          # existing
    events = apply_q5_medivation(events)   # existing
    events = apply_q7_executed_atomization(slug, events)  # NEW

    # canonicalize_bidders runs after all expansions
```

If the canonicalization-and-renumbering step needs the post-Q7 events to assign fresh `bidder_NN` ids, this insertion order is correct. Verify by re-reading the surrounding code and ensuring the canonicalizer is called downstream.

### Step T3.8 — Verify the petsmart and mac-gray tests pass

```bash
pytest tests/test_reference_converter.py::test_petsmart_executed_atomizes_to_five_rows tests/test_reference_converter.py::test_mac_gray_executed_atomizes_to_two_rows -v
```

Expected: both **PASS**.

If they fail, the most common causes are:
- `apply_q7_executed_atomization` not called from `build_deal` — check the wire-up in T3.7.
- Member names in `Q7_EXECUTED_MEMBERS` don't match the test expectations — re-check both lists for typos.
- Canonicalizer assigning unexpected `bidder_alias` overrides — double-check the `bidder_alias` field is preserved on the cloned rows.

### Step T3.9 — Update `tests/test_reference_converter.py` for §Q5 and §Q2 docstring expectations

- [ ] Existing tests that check §Q5 Medivation expansion or §Q2 Zep expansion should still pass without change. Verify:

```bash
pytest tests/test_reference_converter.py -v
```

Expected: all tests pass.

### Step T3.10 — Update `SKILL.md` and `skill_open_questions.md`

- [ ] Search for stale references:

```bash
grep -n "E2.a\|consortium collapse\|Executed exception\|joint-bidder collapse" SKILL.md skill_open_questions.md
```

For each match: if the line states a rule that no longer exists (e.g., "Executed collapses to 1 row"), DELETE the line. No annotation.

### Step T3.11 — Update §Q5 Medivation docstring

- [ ] In `scripts/build_reference.py`, find the §Q5 docstring (around line 65, search for `§Q5 — Medivation`):

```bash
grep -n "§Q5 — Medivation" scripts/build_reference.py
```

- [ ] Update the rationale paragraph to reflect that atomization is now universal — replace any phrase that frames §Q5 as "protecting against §E2.b's aggregation carve-out" with "implementing the universal atomization rule per §E1 (rewritten 2026-04-27)." Concretely, look for sentences that reference §E2.b's narrate-aggregation behavior and update them.

### Step T3.12 — Run full test suite

```bash
pytest tests/ -q
```

Expected: all tests pass.

### Step T3.13 — Commit C3

```bash
git add rules/bidders.md prompts/extract.md scripts/build_reference.py tests/ SKILL.md skill_open_questions.md
git diff --cached --stat
git commit -m "$(cat <<'EOF'
schema: universal atomization; delete §E2.a; expand consortium Executed rows

Per Alex 2026-04-27 directive: atomization is unconditional and applies
to all event types including Executed. The §E2.a Executed-row joint-
bidder collapse is deleted; the §E2.b group-narrated aggregation table
collapses to "atomize per identifiable signer / count placeholder."

Touches:
- rules/bidders.md: §E2.a deleted; §E2.b table simplified; §E1 strengthened
- prompts/extract.md: Step 7 simplified; explicit Executed-atomization instruction
- scripts/build_reference.py: new Q7_EXECUTED_MEMBERS dict + apply_q7_executed_atomization;
  wires into build pipeline after Q2/Q5 and before canonicalization
- tests/: new petsmart 5-row Executed test; new mac-gray 2-row Executed test
- §Q5 Medivation docstring updated to reflect universal atomization

petsmart-inc: 1 Executed row → 5 (BC Partners + La Caisse + GIC +
StepStone + Longview).
mac-gray: 1 Executed row → 2 (CSC + Pamplona).
zep, saks: single-member entries; no expansion but flag for audit.

No backward compatibility, no shims. See spec
quality_reports/specs/2026-04-27_six-policy-update.md for context.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] Mark Task 3 complete: `## Task 3 — C3: ... 🟢`.

---

## Task 4 — C4: Range bids → informal

**Goal:** Whenever `bid_value_lower` and `bid_value_upper` are both numeric and `lower < upper`, `bid_type = "informal"` unconditionally. New hard validator `bid_range_must_be_informal` fires if the row carries a different `bid_type`. New soft flag `range_with_formal_trigger_override` fires when a formal trigger phrase coexists with a range (range still wins). The xlsx-→-JSON converter auto-coerces legacy rows where Alex labeled a range as `formal`.

**Files this commit touches:**
- Modify: `rules/bids.md` — rewrite §G1 range-vs-formal-trigger paragraph; tighten §H1 wording; extend §G2 hard requirement
- Modify: `rules/invariants.md` — extend §P-G2 to add `bid_range_must_be_informal`
- Modify: `prompts/extract.md` — Step 8 range exemption clarified
- Modify: `pipeline.py:779–825` — extend `_invariant_p_g2` with the new hard check
- Modify: `scripts/build_reference.py` — extend `_migrate_bid_note` with auto-coerce
- Modify: `tests/test_invariants.py` — new tests for the validator extension
- Modify: `tests/test_reference_converter.py` — test for auto-coerce

### Step T4.1 — Update `rules/bids.md` §G1 range carve-out

- [ ] In `rules/bids.md`, find the §G1 informal-triggers list (around line 213). Replace lines 219–224 (the "Structural signal: bid is stated as a true range …" bullet and the formal-trigger-wins clause) with:

```markdown
- **Structural signal: bid is stated as a true range** (both `bid_value_lower` and `bid_value_upper` populated, numeric, with `lower < upper` per §G2) — **range always wins**. Whenever a true range is present, `bid_type = "informal"` regardless of any formal trigger phrase the filing uses. If a formal trigger coexists with the range, emit soft flag `range_with_formal_trigger_override` to preserve the audit trail; do NOT change `bid_type` based on the trigger. Per Alex 2026-04-27 directive.
```

### Step T4.2 — Update `rules/bids.md` §G2 hard requirement

- [ ] Find §G2 (around line 255) in `rules/bids.md`. After the existing satisfier list (lines 257–267), add:

```markdown

**Additional hard requirement (per 2026-04-27 directive).** When the row
satisfies satisfier (1) — i.e., is a true range bid — `bid_type` MUST
equal `"informal"`. A range with `bid_type = "formal"` is a structural
contradiction and the validator (§P-G2) flags it hard as
`bid_range_must_be_informal`.
```

### Step T4.3 — Update `rules/bids.md` §H1 endpoint wording

- [ ] Find §H1 (line 801). In the "Key invariants" subsection (around line 817), rewrite the first invariant to use MUST language:

Before:
```markdown
- Exactly one of `{pershare, (lower, upper), (lower only), (upper only), all-null}` is populated per bid row.
```

After:
```markdown
- Exactly one of `{pershare, (lower, upper), (lower only), (upper only), all-null}` is populated per bid row. When the bid is shaped as a range, both `bid_value_lower` and `bid_value_upper` MUST be populated and numeric with `lower < upper`. Per Alex 2026-04-27.
```

### Step T4.4 — Update `rules/invariants.md` §P-G2

- [ ] Find §P-G2 (line 274). Extend the **Check** subsection to add the third sub-check:

```markdown
- **Check.** Every row with non-null `bid_type` satisfies one of:
  (1) the row is a true range bid — both `bid_value_lower` and
  `bid_value_upper` populated, numeric, and `bid_value_lower <
  bid_value_upper` (§G1 informal structural signal), or (2) the row
  carries a non-empty `bid_type_inference_note: str` of ≤300 chars
  justifying the classification. §G1 trigger tables are *classification
  guidance for the extractor*, NOT a validator satisfier path: a
  trigger phrase alone does not pass §P-G2.
  
  **Additional hard requirement (per 2026-04-27 directive).** When (1)
  is true (the row is a true range bid), `bid_type` MUST equal
  `"informal"`. Otherwise emit hard `bid_range_must_be_informal`.
- **Fail action.** Flag `bid_type_unsupported` (no range, no note).
  Inverted ranges (`lower >= upper`) flag `bid_range_inverted`. Range
  with `bid_type != "informal"` flags `bid_range_must_be_informal`.
  All hard.
```

### Step T4.5 — Update `prompts/extract.md` Step 8

- [ ] Find Step 8 in `prompts/extract.md` (around line 60). The existing language already exempts ranges from `bid_type_inference_note` requirement. Add a sentence after the existing exemption:

```markdown
... a §G1 informal structural signal). Range bids additionally lock `bid_type = "informal"` per Alex 2026-04-27 — never emit a range-shaped Bid row with `bid_type = "formal"`. If a formal trigger phrase appears alongside a range, attach the soft flag `range_with_formal_trigger_override` (range still wins). The §G1 trigger tables guide which classification you pick; they do NOT exempt you from writing the note. Validator §P-G2 enforces this.
```

### Step T4.6 — Write failing test for `bid_range_must_be_informal`

- [ ] In `tests/test_invariants.py`, add a new test:

```python
def test_p_g2_range_with_formal_bid_type_fails_hard():
    """C4 — a range bid (lower < upper, both numeric) with bid_type="formal"
    must emit hard flag `bid_range_must_be_informal` per Alex 2026-04-27.
    """
    from pipeline import _invariant_p_g2

    events = [{
        "BidderID": 1,
        "bid_note": "Bid",
        "bid_type": "formal",
        "bid_value_lower": 42.0,
        "bid_value_upper": 48.0,
        "bid_type_inference_note": None,
    }]
    flags = _invariant_p_g2(events)
    codes = [f["code"] for f in flags]
    assert "bid_range_must_be_informal" in codes, (
        f"expected hard flag bid_range_must_be_informal; got {codes}"
    )
    severities = {f["code"]: f["severity"] for f in flags}
    assert severities["bid_range_must_be_informal"] == "hard"


def test_p_g2_range_with_informal_bid_type_passes():
    """C4 — same range with bid_type='informal' is the canonical valid shape."""
    from pipeline import _invariant_p_g2

    events = [{
        "BidderID": 1,
        "bid_note": "Bid",
        "bid_type": "informal",
        "bid_value_lower": 42.0,
        "bid_value_upper": 48.0,
        "bid_type_inference_note": None,
    }]
    flags = _invariant_p_g2(events)
    codes = [f["code"] for f in flags]
    assert "bid_range_must_be_informal" not in codes
    assert "bid_type_unsupported" not in codes  # range satisfies §G2
```

- [ ] Run them:

```bash
pytest tests/test_invariants.py::test_p_g2_range_with_formal_bid_type_fails_hard tests/test_invariants.py::test_p_g2_range_with_informal_bid_type_passes -v
```

Expected: the first **FAILS** (validator doesn't emit `bid_range_must_be_informal` yet); the second **PASSES** (range satisfies §G2 unconditionally).

### Step T4.7 — Extend `_invariant_p_g2` in `pipeline.py`

- [ ] In `pipeline.py`, replace the function `_invariant_p_g2` (lines 779–825) with this extended version. Note the new sub-check inserted between the inverted-range check and the note check:

```python
def _invariant_p_g2(events: list[dict]) -> list[dict]:
    """§P-G2 — every row with non-null bid_type satisfies one of:
    (1) the row is a true range bid (both `bid_value_lower` and
    `bid_value_upper` numeric with `lower < upper`, a §G1 informal
    structural signal), or (2) the row carries a non-empty
    `bid_type_inference_note: str` of ≤300 chars. §G1 trigger tables are
    classification guidance for the extractor, not a validator satisfier.

    Additional hard rule (per Alex 2026-04-27): when (1) is true, the row
    MUST have `bid_type = "informal"`. A range with bid_type="formal" is
    a structural contradiction.

    Violations emit hard `bid_type_unsupported`, `bid_range_inverted`, or
    `bid_range_must_be_informal`."""
    flags: list[dict[str, Any]] = []
    for i, ev in enumerate(events):
        bid_type = ev.get("bid_type")
        if bid_type in (None, "", []):
            continue

        lower = ev.get("bid_value_lower")
        upper = ev.get("bid_value_upper")
        try:
            lo_num = float(lower) if lower not in (None, "", []) else None
            hi_num = float(upper) if upper not in (None, "", []) else None
        except (TypeError, ValueError):
            lo_num = hi_num = None
        if lo_num is not None and hi_num is not None:
            if lo_num >= hi_num:
                flags.append({
                    "row_index": i, "code": "bid_range_inverted", "severity": "hard",
                    "reason": (
                        f"§P-G2: bid_value_lower={lower!r} >= "
                        f"bid_value_upper={upper!r}; ranges require lower < upper."
                    ),
                })
                continue
            # True range: lower < upper, both numeric. §G2 satisfier (1).
            # Additional 2026-04-27 rule: bid_type must be "informal".
            if bid_type != "informal":
                flags.append({
                    "row_index": i, "code": "bid_range_must_be_informal", "severity": "hard",
                    "reason": (
                        f"§P-G2 (2026-04-27): true range "
                        f"({lower!r}..{upper!r}) requires bid_type='informal'; "
                        f"got bid_type={bid_type!r}. Range bids are unconditionally informal."
                    ),
                })
            continue

        note = ev.get("bid_type_inference_note")
        if isinstance(note, str) and 0 < len(note.strip()) <= 300:
            continue

        flags.append({
            "row_index": i, "code": "bid_type_unsupported", "severity": "hard",
            "reason": (
                f"§P-G2: bid_type={bid_type!r} lacks both a true range "
                f"(lower<upper) and a non-empty ≤300-char "
                f"bid_type_inference_note."
            ),
        })
    return flags
```

### Step T4.8 — Verify the validator tests pass

```bash
pytest tests/test_invariants.py::test_p_g2_range_with_formal_bid_type_fails_hard tests/test_invariants.py::test_p_g2_range_with_informal_bid_type_passes -v
```

Expected: both **PASS**.

### Step T4.9 — Extend `_migrate_bid_note` in `build_reference.py` with auto-coerce

- [ ] In `scripts/build_reference.py`, find `_migrate_bid_note` (line 641). The function currently maps legacy xlsx labels to `(bid_note, bid_type, legacy_label)`. We need to know the row's `bid_value_lower` / `bid_value_upper` to apply the auto-coerce.

The cleanest approach: leave `_migrate_bid_note` unchanged (it doesn't see the value fields) and apply the auto-coerce in the row-assembly function that DOES see all the fields. Search for the assembly site:

```bash
grep -n "_migrate_bid_note\|build_event_row\|_row_from_xlsx\|_assemble_event" scripts/build_reference.py
```

In the row-assembly function (where `bid_note`, `bid_type`, `bid_value_lower`, `bid_value_upper` are all set on a single row dict), add a post-processing block immediately before the return:

```python
    # §G1+§G2 (2026-04-27): true range bids are unconditionally informal.
    # Auto-coerce legacy xlsx rows where Alex labeled a range "formal".
    lower = row.get("bid_value_lower")
    upper = row.get("bid_value_upper")
    try:
        lo_num = float(lower) if lower is not None else None
        hi_num = float(upper) if upper is not None else None
    except (TypeError, ValueError):
        lo_num = hi_num = None
    if (
        lo_num is not None and hi_num is not None and lo_num < hi_num
        and row.get("bid_type") not in (None, "informal")
    ):
        original = row["bid_type"]
        row["bid_type"] = "informal"
        row.setdefault("flags", []).append({
            "code": "range_forced_informal_per_g1",
            "severity": "info",
            "reason": (
                f"§G1+§G2 (2026-04-27): xlsx bid_type={original!r} on a true "
                f"range ({lower!r}..{upper!r}) forced to 'informal'."
            ),
        })
    return row
```

(Adapt the variable name `row` to whatever the function uses — likely `ev` or `event`.)

### Step T4.10 — Add a test for the auto-coerce

- [ ] In `tests/test_reference_converter.py`, add:

```python
def test_range_bid_with_formal_legacy_label_is_coerced_to_informal():
    """C4 — when the xlsx labels a range as formal, the converter forces
    bid_type='informal' and emits info flag range_forced_informal_per_g1.

    This depends on whether any of the 9 reference deals actually has a
    range row labeled formal in Alex's xlsx. If not, this test is trivially
    satisfied (no rows to coerce); leave the assertion structure in place
    so future xlsx revisions can't regress.
    """
    from scripts.build_reference import build_deal

    for slug in ("medivation", "imprivata", "zep", "providence-worcester",
                 "penford", "mac-gray", "petsmart-inc", "stec", "saks"):
        payload = build_deal(slug)
        for ev in payload["events"]:
            lower = ev.get("bid_value_lower")
            upper = ev.get("bid_value_upper")
            if lower is None or upper is None:
                continue
            if not (isinstance(lower, (int, float)) and isinstance(upper, (int, float))):
                continue
            if lower < upper:
                # True range — must be informal post-C4.
                assert ev.get("bid_type") == "informal", (
                    f"{slug} row has range ({lower}..{upper}) but "
                    f"bid_type={ev.get('bid_type')!r}; expected informal "
                    f"per C4 auto-coerce."
                )
```

- [ ] Run:

```bash
pytest tests/test_reference_converter.py::test_range_bid_with_formal_legacy_label_is_coerced_to_informal -v
```

Expected: **PASS**. (If it fails, the auto-coerce wire-up missed a code path.)

### Step T4.11 — Run full test suite

```bash
pytest tests/ -q
```

Expected: all tests pass.

### Step T4.12 — Commit C4

```bash
git add rules/bids.md rules/invariants.md prompts/extract.md pipeline.py scripts/build_reference.py tests/
git diff --cached --stat
git commit -m "$(cat <<'EOF'
schema: range bids unconditionally informal; new validator + auto-coerce

Per Alex 2026-04-27 directive: whenever bid_value_lower and bid_value_upper
are both numeric with lower < upper, bid_type = "informal". The pre-2026
"formal trigger wins over range" carve-out in §G1 is deleted; range
always wins, formal triggers emit a soft flag.

Touches:
- rules/bids.md: §G1 range-vs-trigger rewrite; §G2 + §H1 hardened
- rules/invariants.md: §P-G2 extended with bid_range_must_be_informal
- prompts/extract.md: Step 8 range exemption clarifies informal lock
- pipeline.py: _invariant_p_g2 emits hard `bid_range_must_be_informal`
  when range coexists with bid_type != "informal"
- scripts/build_reference.py: row-assembly auto-coerces legacy rows where
  Alex labeled a range "formal", emits info flag range_forced_informal_per_g1
- tests/: validator + converter coverage

No backward compatibility, no shims. See spec
quality_reports/specs/2026-04-27_six-policy-update.md for context.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] Mark Task 4 complete: `## Task 4 — C4: ... 🟢`.

---

## Task 5 — C5: §L2 wording tighten "6 months" → "180 calendar days"

**Goal:** Wording-only change. The §L2 phase-boundary heuristic in `rules/events.md` currently says "6 months or more apart"; the validator constant in `pipeline.py:1008` already uses 180. Tighten the rule wording to match.

**Files this commit touches:**
- Modify: `rules/events.md:741–772` — three "6 months" → "180 calendar days" replacements

### Step T5.1 — Replace "6 months" with "180 calendar days" in §L2

- [ ] In `rules/events.md`, find §L2 (line 726):

```bash
grep -n "6 months\|6-month" rules/events.md
```

- [ ] Replace each occurrence inside §L2 (do NOT edit other sections that may use "6 months" in unrelated contexts; only the §L2 phase-boundary references):

| Before | After |
|---|---|
| `**6-month silence heuristic (Austin's rule).** If two consecutive events in chronological order are **6 months or more apart**` | `**180-day silence heuristic (Austin's rule).** If two consecutive events in chronological order are **180 calendar days or more apart**` |
| `Events separated from the main/restart chain by a ≥ 6-month gap` | `Events separated from the main/restart chain by a ≥ 180-day gap` |
| `No \`process_phase = 0\` rows exist within 6 months of any phase-1/phase-2 event (§P-L2).` | `No \`process_phase = 0\` rows exist within 180 calendar days of any phase-1/phase-2 event (§P-L2).` |

If the third occurrence is worded differently, adapt — the substantive change is "6 months" → "180 calendar days" (or "180-day"); the structural prose stays.

- [ ] Verify zero `6 months` / `6-month` strings remain inside §L2:

```bash
sed -n '/^### §L2/,/^### §L3\|^---$/p' rules/events.md | grep -n "6 months\|6-month"
```

Expected: zero matches.

### Step T5.2 — Run full test suite

```bash
pytest tests/ -q
```

Expected: all tests pass (this commit is doc-only).

### Step T5.3 — Commit C5

```bash
git add rules/events.md
git diff --cached --stat
git commit -m "$(cat <<'EOF'
rules: §L2 wording — "6 months" → "180 calendar days"

Wording-only change. Aligns the §L2 phase-boundary rule's prose with
the §P-L2 validator constant (already 180 days at pipeline.py:1008).
No semantic change.

Per Alex 2026-04-27 directive ratifying the existing design.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] Mark Task 5 complete: `## Task 5 — C5: ... 🟢`.

---

## Task 6 — C6: Regenerate reference data + delete stale + handoff doc

**Goal:** Mechanical regeneration of all 9 `reference/alex/*.json` files from the updated converter. Same commit also deletes `state/flags.jsonl`, all 9 `output/extractions/*.json`, the stale `quality_reports/decisions/2026-04-26_six-policy-decisions.md`, and writes the handoff doc for whoever runs C7 later.

**Files this commit touches:**
- Modify: 9 files in `reference/alex/*.json` (regenerated)
- Delete: `state/flags.jsonl`
- Delete: `output/extractions/imprivata.json`, `mac-gray.json`, `medivation.json`, `penford.json`, `petsmart-inc.json`, `providence-worcester.json`, `saks.json`, `stec.json`, `zep.json`
- Delete: `quality_reports/decisions/2026-04-26_six-policy-decisions.md`
- Create: `quality_reports/handoffs/2026-04-27_six-policy-update.md`

### Step T6.1 — Run the converter on all 9 deals

- [ ] From repo root:

```bash
python scripts/build_reference.py --all
```

Expected output: nine summary lines, one per deal, each pointing to the rewritten JSON path. No exceptions, no Python errors.

If any deal fails, **stop**: the converter has a defect that one of C1–C5 introduced. Diagnose by re-running per-deal:

```bash
python scripts/build_reference.py --slug petsmart-inc --dump | head -50
```

Fix the converter, re-run T6.1, do not proceed until all 9 succeed.

### Step T6.2 — Diff regenerated JSONs against the baseline

- [ ] Diff against the `pre-reextract-2026-04-27` tag from Step P.3:

```bash
git diff pre-reextract-2026-04-27 -- reference/alex/ | head -200
```

Expected change classes (every diff line should fit one of these):

1. **C1 changes:** `bidder_type` collapses from `{"base": "...", "non_us": ..., "public": ...}` to a scalar string or null. Every event row affected.
2. **C2 changes:** `Acquirer_legal` field disappears from every deal object. The 4 sponsor-backed deals (petsmart-inc, mac-gray, zep, saks) have `Acquirer` rewritten to operating name. New `acquirer_normalized` info flag in `deal_flags`.
3. **C3 changes:** petsmart-inc gains 4 Executed rows (1→5); mac-gray gains 1 (1→2). `joint_bidder_members` field disappears from Executed rows. New `executed_atomized` info flag on each Executed row in those 4 deals.
4. **C4 changes:** any range row that was previously `bid_type: "formal"` becomes `"informal"` with new `range_forced_informal_per_g1` info flag.
5. **BidderID renumbering:** because petsmart and mac-gray gain rows, downstream `BidderID` integers shift. This is expected.

If a diff line doesn't fit any of the above, **stop and investigate**: the converter or rule change has an unintended side effect. Common culprits:
- A test that updates a JSON file as a side effect — should not happen if T1.x–T5.x went cleanly.
- A bug in T1.5's new `build_bidder_type` returning the wrong value for a known bidder.

### Step T6.3 — Validator dry-run on each regenerated JSON

- [ ] For each of the 9 deals, run validator-only:

```bash
for slug in providence-worcester medivation imprivata zep petsmart-inc penford mac-gray saks stec; do
  echo "=== $slug ==="
  python run.py validate --slug "$slug" --reference 2>&1 | tail -20
done
```

Expected: no new HARD validator fires (no `bid_range_must_be_informal`, no `bid_range_inverted`, no `executed_member_no_nda` from the deferred Y1, no other new hard codes). Soft / info flags may appear and are fine — examples:

- `acquirer_normalized` (info, from C2) on the 4 sponsor deals
- `executed_atomized` (info, from C3) on the 4 sponsor deals
- `range_forced_informal_per_g1` (info, from C4) on rows where Alex labeled a range formal

If a HARD flag fires, **stop**:
- `bid_range_must_be_informal` firing means the auto-coerce in T4.9 missed a code path.
- `bid_range_inverted` firing means the xlsx has `lower >= upper`; investigate that specific row.
- `bidder_id_structural_error` firing means the canonicalizer's BidderID renumbering is wrong; investigate the Q7 wire-up in T3.7.

(Adjust the `run.py` invocation if the project's CLI signature differs — verify by `python run.py --help` first.)

### Step T6.4 — Spot-check petsmart and mac-gray

- [ ] Spot-check petsmart's Executed rows:

```bash
python -c "import json; d=json.load(open('reference/alex/petsmart-inc.json')); rows=[e for e in d['events'] if e.get('bid_note')=='Executed']; print(len(rows)); [print(r['bidder_alias'], r['bid_date_precise']) for r in rows]"
```

Expected output:
```
5
BC Partners, Inc. 2014-12-14
La Caisse 2014-12-14
GIC Pte Ltd 2014-12-14
StepStone Group 2014-12-14
Longview Asset Management 2014-12-14
```

(Date may differ if Alex's xlsx had a different signing date — confirm against the filing.)

- [ ] Same for mac-gray:

```bash
python -c "import json; d=json.load(open('reference/alex/mac-gray.json')); rows=[e for e in d['events'] if e.get('bid_note')=='Executed']; print(len(rows)); [print(r['bidder_alias']) for r in rows]"
```

Expected: 2 rows with aliases `CSC ServiceWorks, Inc.` and `Pamplona Capital Partners`.

- [ ] Verify all 4 sponsor deals have no `Acquirer_legal` key:

```bash
for slug in petsmart-inc mac-gray zep saks; do
  python -c "import json; print('$slug:', 'Acquirer_legal' in json.load(open('reference/alex/$slug.json')))"
done
```

Expected: all four print `False`.

### Step T6.5 — Delete `state/flags.jsonl`

- [ ] Delete:

```bash
rm state/flags.jsonl
```

The pipeline recreates this file on first append.

### Step T6.6 — Delete all `output/extractions/*.json`

- [ ] Delete:

```bash
rm output/extractions/imprivata.json
rm output/extractions/mac-gray.json
rm output/extractions/medivation.json
rm output/extractions/penford.json
rm output/extractions/petsmart-inc.json
rm output/extractions/providence-worcester.json
rm output/extractions/saks.json
rm output/extractions/stec.json
rm output/extractions/zep.json
```

(Confirm only those 9 files existed first via `ls output/extractions/`.) These are stale AI outputs; C7's per-deal re-extraction regenerates them later.

### Step T6.7 — Delete the stale 2026-04-26 decisions doc

- [ ] Delete:

```bash
rm quality_reports/decisions/2026-04-26_six-policy-decisions.md
```

Per the spec's §0 (no annotation, full delete).

### Step T6.8 — Write the handoff doc

- [ ] Create `quality_reports/handoffs/2026-04-27_six-policy-update.md` with this content (no placeholder values; this is the actual content):

````markdown
# Six-Policy Update Handoff — 2026-04-27

**For:** whoever runs C7 (per-deal re-extraction on the 9 reference deals)
**Spec:** `quality_reports/specs/2026-04-27_six-policy-update.md`
**Plan:** `quality_reports/plans/2026-04-27_six-policy-update.md`
**Branch landed on `main` at:** [hash from `git log` after merge]

## What changed

Six commits (C1–C6) landed updates from Alex's 2026-04-27 directive:

1. **C1 — `bidder_type` flattened to scalar.** `{"base": "s", "non_us": ..., "public": ...}` → `"s"`. Geography and listing status are no longer recorded.
2. **C2 — `Acquirer_legal` deleted.** Only the operating acquirer is recorded. The 4 sponsor-backed reference deals (petsmart-inc, mac-gray, zep, saks) had their xlsx `Acquirer` column rewritten to the operational name; the legal shell is gone.
3. **C3 — Universal atomization.** The §E2.a Executed-row joint-bidder collapse is deleted. Petsmart now has 5 Executed rows (BC Partners + La Caisse + GIC + StepStone + Longview); mac-gray has 2 (CSC + Pamplona). Single-sponsor deals unchanged.
4. **C4 — Range bids unconditionally informal.** Whenever `bid_value_lower < bid_value_upper` (both numeric), `bid_type = "informal"`. New hard validator `bid_range_must_be_informal` fires on contradictions. Soft flag `range_with_formal_trigger_override` flags edge cases.
5. **C5 — §L2 wording tighten.** "6 months" → "180 calendar days." Validator constant unchanged at 180.
6. **C6 — Reference data regeneration + stale-file deletion + this handoff doc.**

## What was deleted

- `state/flags.jsonl` (clean slate; pipeline recreates on first run)
- All 9 `output/extractions/*.json` (clean slate; C7 regenerates per deal)
- `quality_reports/decisions/2026-04-26_six-policy-decisions.md` (decisions #2, #3, #6 reversed by this batch — full delete, no annotation, per spec §0)

## What C7 needs to do (per deal)

For each of the 9 reference deals (medivation → imprivata → zep → providence-worcester → penford → mac-gray → petsmart-inc → stec → saks):

1. Spawn a fresh Claude session.
2. Extractor reads the updated `prompts/extract.md` and runs against the SEC filing.
3. Pipeline validator runs the new invariants. Watch for new hard fires:
   - `bid_range_must_be_informal` — should not fire after C4 unless the AI emits a range with `bid_type="formal"`.
   - No other new hard codes were added.
4. `scoring/diff.py` produces an Austin-readable diff against the freshly-regenerated `reference/alex/<deal>.json`.
5. Austin manually adjudicates each disagreement against the SEC filing per the four-verdict framework (CLAUDE.md):
   - AI correct, Alex wrong → record the AI correction; do not change rules.
   - AI wrong, Alex correct → update the rules / prompt.
   - Both correct, different interpretations → log a judgment call in the rulebook.
   - Both wrong → fix the rulebook against the filing.
6. On clean: mark `state/progress.json` `verified` for the deal.

## Exit gate (unchanged from CLAUDE.md)

The 392 target deals remain blocked until:
- All 9 reference deals are manually verified by Austin.
- The rulebook remains unchanged across 3 consecutive full-reference-set runs.

## What this batch did NOT change

- §I1 DropSilent atomization (already conformant with universal atomization).
- §P-L2 validator constant (already 180 days; only the §L2 wording moved).
- BidderID assignment (still strict 1..N event sequence).
- `source_quote` / `source_page` requirement (still mandatory on every row).
- Auction classifier (`§Scope-1`).
- Skip rules (§M1, §M3, §M5).

## Where to look first if something looks wrong

- **Wrong number of Executed rows:** check `Q7_EXECUTED_MEMBERS` in `scripts/build_reference.py`.
- **Wrong Acquirer name:** check `Q6_ACQUIRER_REWRITE` in `scripts/build_reference.py`.
- **`bidder_type` is dict instead of scalar:** check `build_bidder_type` in `scripts/build_reference.py`.
- **Validator firing `bid_range_must_be_informal` on AI output:** the extractor needs the prompt's Step 8 update; verify `prompts/extract.md` line 60.
````

### Step T6.9 — Final verification

- [ ] Run the test suite one more time:

```bash
pytest tests/ -q
```

Expected: all tests pass.

- [ ] Check no stray non_us / Acquirer_legal references remain anywhere live:

```bash
grep -rn "non_us\|Acquirer_legal\|\"public\":" rules/ prompts/ pipeline.py scripts/ scoring/ tests/ SKILL.md skill_open_questions.md 2>&1 | grep -v "^Binary"
```

Expected: zero matches.

- [ ] Check `state/flags.jsonl` is gone and `output/extractions/` is empty:

```bash
ls state/flags.jsonl 2>&1 ; ls output/extractions/
```

Expected: `ls: state/flags.jsonl: No such file or directory`. `output/extractions/` either empty or only `.gitkeep`.

### Step T6.10 — Commit C6

- [ ] Stage and commit:

```bash
git add reference/alex/*.json quality_reports/handoffs/2026-04-27_six-policy-update.md
git rm state/flags.jsonl 2>&1 || true
git rm output/extractions/imprivata.json output/extractions/mac-gray.json \
       output/extractions/medivation.json output/extractions/penford.json \
       output/extractions/petsmart-inc.json output/extractions/providence-worcester.json \
       output/extractions/saks.json output/extractions/stec.json output/extractions/zep.json
git rm quality_reports/decisions/2026-04-26_six-policy-decisions.md
git diff --cached --stat
git commit -m "$(cat <<'EOF'
reference: regenerate alex/*.json under 2026-04-27 rules; clean slate stale data

Mechanical regeneration of all 9 reference JSONs from the updated
converter (C1–C5 landed in the prior 5 commits). Per Alex 2026-04-27
directive: scalar bidder_type, no Acquirer_legal, universal atomization
(petsmart 1→5 Executed rows; mac-gray 1→2), range bids unconditionally
informal.

Stale-data deletion (clean slate, no backward compatibility per spec §0):
- state/flags.jsonl (pipeline recreates on first run)
- output/extractions/*.json (9 files; C7 regenerates per deal)
- quality_reports/decisions/2026-04-26_six-policy-decisions.md
  (decisions #2, #3, #6 reversed by this batch)

Adds:
- quality_reports/handoffs/2026-04-27_six-policy-update.md
  (handoff doc for whoever runs C7)

C7 (live re-extraction on the 9 reference deals) is deferred to a
separate workstream that runs per-deal under Austin's adjudication
clock per CLAUDE.md.

See spec quality_reports/specs/2026-04-27_six-policy-update.md
and plan quality_reports/plans/2026-04-27_six-policy-update.md.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] Mark Task 6 complete: `## Task 6 — C6: ... 🟢`.

---

## Post-batch: branch hygiene

### Step Z.1 — Confirm 6 commits on the branch

- [ ] Inspect:

```bash
git log --oneline main..six-policy-update-2026-04-27
```

Expected: exactly 6 commits, matching C1–C6 in order.

### Step Z.2 — Decide merge strategy

This plan stops here. The user (or a fresh agent acting on the user's instruction) decides whether to:
- Merge to `main` (fast-forward or `--no-ff`).
- Open a PR for review.
- Leave the branch open and start C7 on a new branch.

**Do NOT** delete the `pre-reextract-2026-04-27` tag — it's evidence of the C6 baseline.

---

## Self-review (already performed by plan author)

**Spec coverage check:**
- ✅ M1 (drop non_us) — Task 1
- ✅ M2 (drop public) — Task 1
- ✅ M3 (flatten bidder_type to scalar) — Task 1
- ✅ M4 (drop Acquirer_legal) — Task 2
- ✅ M5 (Acquirer rewrite for 4 sponsor deals) — Task 2 (T2.5)
- ✅ M6 (delete §E2.a) — Task 3 (T3.1)
- ✅ M7 (rewrite §E2.b) — Task 3 (T3.2)
- ✅ M8 (Q7_EXECUTED_MEMBERS) — Task 3 (T3.6)
- ✅ M9 (apply_q7_executed_atomization) — Task 3 (T3.6, T3.7)
- ✅ M10 (range bids → informal) — Task 4 (T4.1)
- ✅ M11 (bid_range_must_be_informal hard validator) — Task 4 (T4.7)
- ✅ M12 (range_with_formal_trigger_override soft flag) — Task 4 (T4.5)
- ✅ M13 (auto-coerce legacy formal-range rows) — Task 4 (T4.9)
- ✅ M14 (§L2 wording tighten) — Task 5
- ✅ M15 (regenerate 9 reference JSONs) — Task 6 (T6.1)
- ✅ M16 (delete state/flags.jsonl) — Task 6 (T6.5)
- ✅ M17 (delete output/extractions/*.json) — Task 6 (T6.6)
- ✅ M18 (delete 2026-04-26 decisions doc) — Task 6 (T6.7)
- ✅ M19 (delete legacy non_us/public/Acquirer_legal tests) — Tasks 1, 2
- ✅ M20 (skill files updated in lockstep) — each task
- ✅ M21 (each commit internally consistent) — by construction
- ✅ M22 (handoff doc bundled into C6) — Task 6 (T6.8)
- ✅ M23 (commit ordering) — by structure
- ✅ S1 (petsmart 5-row test) — Task 3 (T3.5)
- ✅ S2 (mac-gray 2-row test) — Task 3 (T3.5)
- ✅ S3 (Q5 docstring update) — Task 3 (T3.11)
- ✅ S4 (commit messages reference spec) — every commit message includes the spec path
- ✅ S5 (pre-reextract-2026-04-27 tag) — Step P.3, used in T6.2
- ⏸️ Y1 (executed_member_no_nda soft validator) — MAY-only; deferred to a future commit if desired

**Placeholder scan:** ran. No "TBD", "TODO", "fill in details" present in plan steps.

**Type consistency:**
- `Q6_ACQUIRER_REWRITE: dict[str, str]` — used consistently between T2.5 (definition) and downstream callsites.
- `Q7_EXECUTED_MEMBERS: dict[str, list[str]]` — used consistently between T3.6 (definition) and T3.7 (call).
- `apply_q6_acquirer_rewrite(slug, deal)` — defined T2.5, called from `build_deal` (T2.5 last bullet).
- `apply_q7_executed_atomization(slug, events)` — defined T3.6, called T3.7.
- `_bidder_type_scalar(bt: str | None) -> str` — defined T1.8, called from CSV emission (replacing `_bidder_type_components`).
- `build_bidder_type(r: RawRow) -> str | None` — return-type changed from dict to scalar T1.5; callsites updated T1.5 last bullet.

End of plan.
