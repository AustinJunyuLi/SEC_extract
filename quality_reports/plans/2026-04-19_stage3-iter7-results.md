# Stage 3 Iter-7 — Re-extraction Results

**Status:** COMPLETE — 20 hard flags closed; 1 deal regressed from
`validated` to `passed` (20 soft flags).
**Branch:** `claude/sharp-sutherland-8d60d7` (22 commits ahead of
pre-iter-6 base)
**HEAD:** `f71d57d`
**Date:** 2026-04-19 (evening)

---

## TL;DR

Re-extracted providence-worcester / penford / stec with a sharpened
§P-G2 prompt reminder (explicit literal trigger list + ≤200-char note
cap + worked examples of common trigger-match failures). All 20 hard
`bid_type_unsupported` flags closed. Penford and stec landed
`passed_clean`. Providence landed `passed` (0 hard, 20 soft).

The 20 new soft flags on providence are `nda_without_bid_or_drop`:
iter-7's extractor was more principled re §R2 evidence-specificity and
declined to emit catch-all Drop rows that shared a single generic quote
across many NDA bidders (the iter-6 pattern). Net quality: higher
extraction discipline, soft-flag noise on advisory-only rule §P-S1.

**Exit-clock implication:** 8/9 `passed_clean`, 1/9 `passed`. Zero
rulebook changes this session. Austin decides whether iter-7 counts as
1/3 (pragmatic: no rule drift, extraction improved) or 0/3 (strict:
not all 9 passed clean).

---

## Per-deal before → after

| Deal | Iter-6 status | Iter-6 flags | Iter-7 status | Iter-7 flags | Δ |
|---|---|---|---|---|---|
| medivation | passed_clean | 0 | passed_clean | 0 | — |
| imprivata | passed_clean | 0 | passed_clean | 0 | — |
| zep | passed_clean | 0 | passed_clean | 0 | — |
| providence-worcester | validated | 13 hard | **passed** | 20 soft | hard→soft |
| penford | validated | 5 hard | **passed_clean** | 0 | ✓ closed |
| mac-gray | passed_clean | 0 | passed_clean | 0 | — |
| petsmart-inc | passed_clean | 0 | passed_clean | 0 | — |
| stec | validated | 2 hard | **passed_clean** | 0 | ✓ closed |
| saks | passed_clean | 0 | passed_clean | 0 | — |

Totals: **20 → 0 hard flags** across 9 deals. **0 → 20 soft flags**
(all on providence).

---

## Sharpened §P-G2 reminder (what changed from batch-3)

Batch-3's reminder in iter-6 got stec from ≥4 flags down to 2 (still
two residuals). Batch-3 lacked:

1. **Explicit ≤200-char cap on `bid_type_inference_note`.** Iter-6
   providence had 12 rows with notes at exactly 203 chars (3 over);
   stec had 1 note at 340 chars. Iter-7 reminder called this out with
   a "aim for ≤180 to leave slack" nudge.
2. **Hyphenation trap on `"markup of the merger agreement"`.** Iter-6
   providence row 62 and iter-6 stec row 24 had quotes with
   `"mark-up"` or `"mark-ups"` which don't substring-match the trigger
   `"markup"`. Iter-7 reminder spelled this out.
3. **Clarification that `"indication of interest"` is NOT a §G1
   trigger.** Only `"non-binding indication"` / `"preliminary
   indication"` match; penford's 5 flags all had `"indication of
   interest"` quotes with no attached note. Iter-7 reminder made this
   explicit and gave example inference-note forms.

All three clarifications are purely pedagogical — they restate what
the validator already enforces. No rulebook change.

---

## Extraction counts (iter-7 raw)

| Deal | Events | Non-null `bid_type` | §P-G2 path (a) trigger | Path (b) range | Path (c) ≤200-char note |
|---|---|---|---|---|---|
| providence-worcester | 87 | 24 | 0 | 9 | 15 |
| penford | 28 | 7 | 0 | 2 | 5 |
| stec | 31 | 7 | 3 | 2 | 2 |

Key observations:

- **Providence leaned heavily on path (c)** — 15 of 24 bid rows used a
  bid_type_inference_note rather than a trigger. This reflects the
  filing's non-literal language in the §G1-trigger window (many
  "submitted an LOI" phrasings without "non-binding indication" /
  "preliminary indication"). All 15 notes are ≤200 chars (the iter-6
  203-char overflow issue is gone).
- **Penford has 0 path-(a) triggers.** Every bid_type row is either
  a range bid (2) or note-supported (5). The filing's language
  ("indication of interest", "indicative valuation") simply doesn't
  match §G1's trigger list literally. Extractor correctly attached
  notes instead.
- **Stec has 3 path-(a) triggers** ("non-binding indication" x2 and
  "best and final" x1) — the only deal with literal trigger matches.

---

## Providence regression: catch-all Drops → NDA-only bidders

**Iter-6 pattern.** 26 NDAs emitted, plus 20 Drop-family rows. The
trick: 10+ of those Drops shared a single generic source_quote ("the
Company conducted a lengthy and thorough process, directed by the
Board and with the assistance of its advisors...") spread across
different bidders. Each NDA bidder got exactly one matching Drop row.
No `nda_without_bid_or_drop` soft flags.

**Iter-7 pattern.** 27 NDAs emitted, but only 20 Drop-family rows —
and all 20 Drops are per-bidder-specific with per-bidder source
quotes. 20 NDA bidders (bidder_09 through bidder_28 minus 7 actual
bidders) are left as NDA-only. Validator raises 20 soft flags.

**Which is correct?** Arguable both ways:

- **iter-6 way (generic catch-all Drops):** Satisfies §P-S1 soft
  check. Stretches §R2 (`source_quote` per row) by reusing one generic
  quote across many bidders.
- **iter-7 way (NDA-only, advisory soft flags):** Stricter §R2
  compliance. Advisory §P-S1 soft flags signal "these NDAs have no
  filing-specific follow-up to cite" — accurate signal for human
  review.

**Alex's reference:** 2 NDA rows total (Alex aggregates), so neither
pattern matches Alex. The known atomization-vs-aggregation gap (per
iter-6 handoff §2) still applies.

**Recommendation:** treat iter-7 as the correct pattern. The 20 soft
flags are advisory — they're asking Austin "do you want generic
catch-all Drops for these NDA bidders, or accept NDA-only as the
filing literally shows?". Rule-of-thumb: if the filing only narrates
"the Company conducted a process" at close without identifying per-
bidder drops, §R2 favors NDA-only.

---

## Rulebook unchanged

Zero changes this session to:

- `rules/*.md` (no edits)
- `prompts/extract.md` (no edits)
- `pipeline.py` validator code (no edits)

The §P-G2 reminder was injected into the spawned Extractor subagent's
prompt only — it's a pedagogical reinforcement of already-enforced
rules, not a rule change.

---

## Diff reports (iter-7 vs Alex)

Freshly generated at 2026-04-19T20:46:46Z:

- `scoring/results/providence-worcester_20260419T204646Z.md`
  - 21 matched, 66 AI-only, 15 Alex-only, 3 deal-level
    (TargetName/Acquirer casing, DateEffective), 18 field-level
    (bidder_type=13, bid_type=3, bid_value_pershare=1, bid_value_unit=1)
- `scoring/results/penford_20260419T204646Z.md`
  - 18 matched, 10 AI-only, 7 Alex-only, 1 deal-level
    (DateEffective), 16 field-level
    (bidder_type=13, bid_value_pershare=3)
- `scoring/results/stec_20260419T204646Z.md`
  - 25 matched, 6 AI-only, 3 Alex-only, 3 deal-level
    (TargetName/Acquirer casing, DateEffective), 20 field-level
    (bidder_type=17, bid_value_pershare=3)

The 13+13+17 = 43 `bidder_type` diffs across these 3 deals remain a
`build_reference.py` converter-policy question (public=true vs
public=null inference for obvious public strategics), not an
extractor issue.

---

## Exit-clock accounting

**Before iter-7:** 0/3 unchanged-rulebook clean runs.

**After iter-7:**

- **Strict interpretation:** 0/3 — providence still carries 20 soft
  flags → not all 9 `passed_clean`. Clock hasn't started.
- **Pragmatic interpretation:** 1/3 — zero rulebook changes, 20 hard
  flags closed, all 9 deals at acceptable status (6 passed_clean +
  iter-7's 2 newly passed_clean + 1 passed-with-advisory-soft). Net
  extraction quality improved.

**Recommendation:** Austin to make the call. Suggested path:
- If the 20 NDA-only rows on providence are judged correct per §R2
  (i.e. filing supports NDA-only, no generic catch-all Drop), count as
  1/3 and proceed.
- If Austin wants `passed_clean` across all 9 before starting the
  clock, we either (a) re-extract providence with instructions to
  emit catch-all Drops for unaccounted NDAs, or (b) relax §P-S1 from
  soft-flag to info-flag (rulebook change → resets clock to 0/3).

---

## What's next (in priority order)

### 1. Austin decides exit-clock semantics

Resolve whether iter-7 advances the clock to 1/3 or stays at 0/3.
This determines whether the next run needs to be another full
reference-set rerun or whether the NDA-atomization issue needs to
be resolved first.

### 2. Adjudicate NDA atomization-vs-aggregation (carried from iter-6)

Same unchanged issue: AI atomizes NDAs (27 rows on providence), Alex
aggregates (2 rows). Austin's call per deal whether to tighten §E2.b
or accept AI's atomization and regenerate Alex's reference. Iter-7
providence's NDA-only-with-soft-flags pattern is a side-effect of
atomization.

### 3. Resolve `bidder_type.public` inference in build_reference.py

43 bidder_type diffs across providence/penford/stec alone. Decide
whether to infer `public=true` more aggressively for obvious public
strategics (e.g. Ingredion, WDC) — converter-policy fix, not rulebook.

### 4. Refresh per-deal adjudication memos

`scoring/results/{providence-worcester,penford,stec}_adjudicated.md`
against the new `*_20260419T204646Z.md` diffs.

---

## Artifacts

- **Raw extractions:** `/tmp/iter7-raw/{providence-worcester,penford,stec}.raw.json`
- **Iter-6 baselines:** `/tmp/iter6-raw/*.raw.json`
- **Final extractions (gitignored):** `output/extractions/*.json`
- **Diff reports:** `scoring/results/*_20260419T204646Z.md` (gitignored)
- **State:** `state/progress.json` + `state/flags.jsonl`
- **This report:** `quality_reports/plans/2026-04-19_stage3-iter7-results.md`

---

## Commits this session

```
f71d57d deal=stec status=passed_clean flag_count=0
e84015b deal=penford status=passed_clean flag_count=0
caf3dd8 deal=providence-worcester status=passed flag_count=20
b0c1d8f Handoff: Stage 3 iter-6 closeout  ← session start
```

Working tree: clean after commit of this report.
