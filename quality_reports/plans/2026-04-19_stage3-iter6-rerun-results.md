# Iter-6 Reference-Set Rerun — Aggregate Report

**Date:** 2026-04-19
**Branch:** `claude/sharp-sutherland-8d60d7`
**HEAD before rerun:** `88339dd` (rerun handoff)
**HEAD after rerun:** `c491772` (stec final commit)
**Commits added:** 9 (one per deal, via `run.py` auto-commit)

---

## Per-deal results

| Deal | Events | Status | Hard flags | Matched | AI-only | Alex-only | Field |
|---|---:|---|---:|---:|---:|---:|---:|
| medivation | 21 | passed_clean | 0 | 14 | 7 | 5 | 13 |
| imprivata | 28 | passed_clean | 0 | 27 | 1 | 2 | 14 |
| zep | 72 | passed_clean | 0 | 14 | 58 | 13 | 7 |
| providence-worcester | 84 | **validated** | **13** | 24 | 60 | 12 | 22 |
| penford | 28 | **validated** | **6** | 18 | 10 | 7 | 16 |
| mac-gray | 62 | passed_clean | 0 | 28 | 34 | 6 | 26 |
| petsmart-inc | 54 | passed_clean | 0 | 19 | 35 | 31 | 11 |
| stec | 31 | **validated** | **2** | 25 | 6 | 3 | 20 |
| saks | 26 | passed_clean | 0 | 17 | 9 | 6 | 7 |
| **totals** | **406** | 6pc/3v | **21** | 186 | 220 | 85 | 136 |

Clean runs: 6 of 9. Three deals carry hard flags.

---

## Hard-flag breakdown (21 total)

| Code | Count | Deals | Nature |
|---|---:|---|---|
| `bid_type_unsupported` (§P-G2) | 20 | providence (13), penford (5), stec (2) | Extractor missed `bid_type_trigger` phrase or `bid_type_inference_note`. **Extractor-side fix, not rule change.** |
| `phase_termination_missing` | 1 | penford | Last event `bid_note="Drop"` instead of `{Executed, Terminated, Auction Closed}`. **Extractor-side fix.** |

Handoff predicted ~33 `bid_type_unsupported`; observed 20. Prompt reminder in batch-3 appears to have helped (petsmart/stec/saks totalled 2 vs no-reminder deals in batch-2 totalling 18 across providence+penford).

**Zero rule-change triggers.** All hard flags are extractor-side evidence gaps.

---

## Diff patterns (for Austin's adjudication)

### Pattern 1: NDA atomization vs aggregation

AI extracted far more NDA/Drop rows than Alex on:
- **zep** (27 NDAs + 26 Drops vs 27 total in Alex)
- **mac-gray** (20 NDAs + 16 Drops vs 34 total in Alex)
- **providence-worcester** (26 NDAs + 20 Drops vs 36 total in Alex)
- **petsmart-inc** (likely similar given 15-NDAs-same-day archetype; 35 AI-only)

Current §E2.b says atomize unless filing narrates joint/consortium activity.
Alex's workbook aggregates. **Legitimate "both correct, different interpretation" per
CLAUDE.md ground-truth framework.** Austin decides per deal whether §E2.b should
tighten (aggregate more) or whether Alex's reference should be regenerated.

### Pattern 2: `bidder_type` disagreements dominate field diffs

`bidder_type=17` on mac-gray, `=13` on imprivata, `=13` on penford, `=17` on stec.
This is the **known pre-existing follow-up** in CLAUDE.md line 445: "Decide whether
residual Medivation `bidder_type.public` diffs should be treated as acceptable
workbook-information loss or whether `scripts/build_reference.py` should infer
`public=true` more aggressively." **Not a new issue — converter-policy question.**

### Pattern 3: Deal-level disagreements (≤3 per deal)

Consistent across all 9 deals at 3 diffs each (except penford at 1). Likely
`TargetName` / `Acquirer` casing + `DateEffective` inference. Same as iter-5
post-pin state.

---

## Exit-clock accounting

**Before rerun:** 0/3 unchanged-rulebook clean runs.
**After rerun:** Still **0/3** — 3 deals carry hard flags (not clean).

Note on interpretation: the handoff said "clock → 1/3 if all 9 pass and no rule
changes needed." Only 6 of 9 passed clean. The 3 validated deals carry only
extractor-side evidence gaps, not rule failures. If Austin's stance is "a
validated deal with only extractor-fix flags doesn't reset the clock," we could
count this as 1/3 — but that's an Austin call, not an orchestrator call.

Conservative interpretation: stays at 0/3 until all 9 pass clean simultaneously.

---

## Suggested next actions (Austin's call)

1. **Re-run extractors on providence / penford / stec** with the same §P-G2
   reminder that batch-3 used. Quick fix, likely brings hard flags to 0.
2. **Adjudicate zep / mac-gray / providence NDA over-atomization.** Either
   tighten §E2.b (aggregate more) or accept AI's atomization as
   filing-correct and flag Alex reference for regeneration.
3. **Resolve `bidder_type.public` inference policy** in
   `scripts/build_reference.py` (CLAUDE.md follow-up #2). Would collapse
   ~65 bidder_type field diffs in one sweep.
4. **Then TIER 3** (dead-code sweep in pipeline.py, ~−50 lines).

---

## Artifacts

- **Raw extractions:** `/tmp/iter6-raw/*.raw.json` (9 files)
- **iter-5 baseline backup:** `/tmp/iter6-raw/iter5-baseline/` (9 files)
- **Final extractions:** `output/extractions/*.json` (committed)
- **Diff reports:** `scoring/results/{deal}_20260419T*.md` (9 files)
- **Flag log:** `state/flags.jsonl` (appended)
