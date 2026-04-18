# Stage 3 Iteration 2 Handoff — Read This First

**Intended reader.** A fresh Claude (or Austin) opening this repo after a
context clear. Read this file, then `CLAUDE.md`, then re-verify the commit
graph with `git log --oneline -15` before acting.

**Date:** 2026-04-18
**Prior handoff:** `2026-04-18_stage3-iter1-handoff.md` (closed).
**Prior state:** Stage 3 iter 1 complete; this iter 2 handoff captures
the Imprivata / Zep / Penford / Providence batch + prompt patch + a
one-shot linkflow pivot that has since been reverted.

---

## TL;DR

- Ran 4 additional reference deals through the Claude Code subagent
  pathway after Imprivata: **Zep** (clean), **Penford** (1 AI defect),
  **Providence-Worcester** (2 AI defects).
- Surfaced the **first 3 genuine AI defects** of the project. All are
  atomization-count gaps (D1, D2, D3 below).
- **Patched the Extractor prompt** (`prompts/extract.md` + `pipeline.build_extractor_prompt()`, commit `3af5ecf`) with two new non-negotiables and three new self-check items to close D1/D2/D3.
- **Attempted to pivot to the linkflow OpenAI-compatible API backend**
  (`gpt-5.4` reasoning=high, 5-parallel) per Austin's instruction.
  Medivation and Providence completed properly (24 / 76 events). Imprivata,
  Zep, and Penford **regressed hard** — skeletal 3-5 event extractions,
  some with hallucinated quotes. Cause unclear; likely parallelism-induced
  reasoning truncation or model inconsistency under the large prompt
  size (73-94k input tokens).
- **Decision:** revert to Claude Code Opus 4.7 subagents for extraction.
  Keep the patched prompt. Keep `api_extractor.py` on disk as a preserved
  option for future investigation.

---

## Commit graph since the prior handoff

```
3af5ecf Patch Extractor prompt: count audit + same-date multi-communication
1e192e4 Providence first-pass extraction: 2 AI defects (atomization count gaps)
9681776 Penford first-pass extraction: 1 AI defect (same-day bid atomization)
7761c5c Zep first-pass extraction: clean run, zero AI defects
d9b3a2a Imprivata first-pass extraction: clean run, zero AI defects
e996e62 (PRIOR HANDOFF) Stage 3 iter 1 complete, recommend Imprivata next
```

Each extraction commit only touches `state/progress.json`; the commit
message is the durable record (outputs + diff reports are gitignored).
The Providence commit (`1e192e4`) is `--allow-empty` because its state
transition bundled into the Penford commit (`9681776`).

---

## The 3 genuine AI defects (to verify closed under the patched prompt)

### D1 — Penford same-day verbal-then-letter bid atomization

**Filing (p.36):** *"Mr. Fortnum then stated that Ingredion was prepared to
move forward based on a proposed price of $18.50 per share on a fully
diluted basis."* — verbal on 2014-10-02. Later same day: *"Penford received
a letter from Ingredion... increasing the proposed price to $19.00 per
share."*

**AI emitted:** only the $19 letter (one Bid row on 10/02).
**Alex's reference:** both rows (verbal + letter) on 10/02.
**Adjudication:** `ai-right` on most factual calls, but `alex-right` on
this atomization.

### D2 — Providence Party E + Party F missing NDA rows

**Filing (p.35):** *"11 potential strategic buyers... Each... subsequently
executed confidentiality agreements."* AI names 5 strategic (A, B, E, F,
G&W) + 6 unnamed = 11 strategic bidders. AI emitted 3 named NDAs (A, B,
G&W) + 6 unnamed NDAs = 9 strategic NDA rows. Missing: Party E, Party F.

AI later emits Party E and Party F **Bid** rows on 5/25 with no preceding
NDA rows. Violates §E1 atomization + §P-D6 NDA-before-bid precondition.

### D3 — Providence IOI count mismatch

**Filing (p.36):** *"nine written indications of interest"* submitted at
the informal round. AI emitted 5 IOI Bid rows + 2 DropBelowInf rows. But
the 2 low bidders have no preceding Bid row, and 2 LOI-decliners per p.37
aren't captured. §E3 exact-count rule violated.

### Common cause

The prompt had §E1 atomization guidance (for anonymous-party counts) and
§C3 bid-row unification, but neither section explicitly audited
(a) every numeric count the filing stated against the emitted row count,
nor (b) multi-communication same-date atomization.

---

## The prompt patch (commit `3af5ecf`)

Added to BOTH `prompts/extract.md` AND `pipeline.build_extractor_prompt()`:

**Non-negotiable 1 — "Numeric counts are row-count commitments."**
When the filing states *"N potential buyers executed confidentiality
agreements"* / *"M indications of interest"* / *"K bidders submitted final
proposals"*, the extraction MUST contain exactly N/M/K atomized rows
(named where known; §E3 placeholders for unnamed balance). §P-D6
NDA-before-bid precondition is mandatory.

**Non-negotiable 2 — "Same-date multi-communication atomization."**
When the filing narrates multiple distinct bid communications from the
same bidder on the same date (verbal call + later letter; two letters),
emit a separate `Bid` row per §C3 for each. Do NOT merge.

**Three new self-check items** (before emission):
- Count audit (every "N parties" / "N IOIs" / "N bids" phrase has N rows)
- NDA-before-bid verification
- Same-date multi-communication verification

The commit also landed Austin's prior in-progress prompt consolidations
that were sitting in the working tree: deal-identity-verbatim, §D1
unsolicited-first-contact, §B5 receipt-vs-sent anchor, §E3 placeholder
count, §K2 invitation-vs-process-letter anchor, post-execution Sale Press
Release fold, and §A2/§A3 BidderID ordering clarification. The rulebook
(`rules/*.md`) was NOT touched.

---

## The linkflow pivot attempt (see `api_extractor.py`)

**Instruction.** Austin asked to switch extractor from Claude Code
subagents to a linkflow OpenAI-compatible backend: URL
`https://www.linkflow.run/v1`, model `gpt-5.4`, reasoning=high, 5-parallel,
with heartbeat + running log. Reference backend: `/Users/austinli/Projects/bids_pipeline`.

**What landed on disk (uncommitted):**
- `api_extractor.py` — new Python module (~350 lines). `APIWatchdog` thread
  per call for heartbeats; `OpenAI.responses.stream(...)` with
  `reasoning.effort="high"`; `ThreadPoolExecutor(max_workers=5)`; per-deal
  runlog at `runlog/{slug}.log`.
- `.env.linkflow` — credentials (gitignored; `.env*` added to .gitignore).
- `.gitignore` — added `.env*`, `runlog/`, `logs/`, `*.log`.
- `runlog/*.log` — heartbeat logs from the aborted pivot (gitignored).

**Prompt design.** Self-contained — full `prompts/extract.md`, all 6
`rules/*.md` files, and the filing's pages-from-Background-onward (cap 60
pages) all inlined. Prompt sizes: medivation 294k chars (~73k tokens),
zep 366k, providence-worcester 375k.

**Run results (2026-04-18 ~21:45-22:10 UTC):**

| slug | time | events | validator | note |
|---|---|---|---|---|
| medivation | 521s | 24 | `passed_clean` | Normal extraction. Diffed cleanly (convention pins + §B3 date anchors only). |
| imprivata | 199s | **3** | `passed_clean` | **Skeletal** — only IB + Executed. Regression. |
| zep | 206s | **4** | `validated` (2 hard) | **Skeletal + hallucinated quotes** — "page 139" merger-agreement text cited as source but not in the page content. |
| penford | 170s | **5** | `passed_clean` | **Skeletal** — 2 NDAs + IB + Drop + Executed only. |
| providence-worcester | 876s | 76 | `passed_clean` | Normal extraction. Matched 18 / 58 AI-only. Count-audit appears to have worked (heavy §E1 atomization). |

**The regression pattern.** Medivation and Providence took 520s+ and
produced full extractions; imprivata/zep/penford finished in 170-210s
with tiny outputs. The short-duration runs had minimal reasoning time
(based on log heartbeats — the output-tokens phase started early after
little reasoning). Likely the model bailed out after minimal reasoning
on the smaller/simpler deals.

**Possible causes (not diagnosed):**
1. Parallelism interaction — 5 concurrent reasoning-heavy requests may
   have triggered linkflow-side throttling that truncated reasoning on
   some responses without surfacing as an error.
2. GPT-5.4 inconsistency under reasoning=high with large (70-90k token)
   inputs; the same model that produced 76 events for Providence gave 3
   for Imprivata.
3. Prompt structure — the rulebook + procedure block is large; the model
   may have treated the filing section as "small enough to summarize"
   and short-circuited.

---

## Decision: revert to Claude Code Opus 4.7 subagents

**Rationale.**
- The Claude Code subagent pathway produced reliable full extractions on
  all 5 deals run this session (Imprivata / Zep / Penford / Providence /
  the earlier iter 1 deals). Event counts ranged 24-76 with zero unexplained
  short-outputs.
- Linkflow (gpt-5.4) gave 2/5 reliable runs in this trial. That's a
  hard floor on research quality.
- The prompt patch (commit `3af5ecf`) is backend-agnostic — the new
  non-negotiables and self-check items help the subagent equally.

**Kept for optional future use:**
- `api_extractor.py` remains on disk (not yet committed).
- `.env.linkflow` remains on disk (gitignored).
- `runlog/` directory can be cleared at any time.

**If you want to commit the linkflow infrastructure as an archived option**
before reverting, stage only `api_extractor.py` and the `.gitignore` diff
(NOT `.env.linkflow`). Message something like "Archive linkflow API
extractor (gpt-5.4) as dormant option; reverting to Claude Code subagents
for reliability."

---

## Current deal state (at handoff)

**Committed state** (`state/progress.json` at commit `3af5ecf`):

| slug | prompt run | events | validator | notes |
|---|---|---|---|---|
| medivation | CC subagent pre-patch | 26 | `passed_clean` | banked iter 1; clock at 1/3 but reset by prompt patch |
| imprivata | CC subagent pre-patch | 28 | `passed_clean` | 1/3 → reset |
| zep | CC subagent pre-patch | 73 | `passed_clean` | 1/3 → reset |
| penford | CC subagent pre-patch | 24 | `passed_clean` | D1 defect; 0/3 |
| providence-worcester | CC subagent pre-patch | 76 | `passed_clean` | D2+D3 defects; 0/3 |
| mac-gray, petsmart-inc, stec, saks | never run | — | `pending` | — |

**Uncommitted state** (current working tree):
- `state/progress.json` shows linkflow runs (imprivata=3 events, zep=4
  events, etc.) — **these should be overwritten by a fresh subagent run**.
- `state/flags.jsonl` has 2 appended hard flags from zep's linkflow run.
- `output/extractions/*.json` contains linkflow outputs (gitignored, so
  they'll get overwritten on the next subagent run; no commit consequence).
- `reference/alex/*.json`, `rules/*.md`, `CLAUDE.md`, `AGENTS.md`,
  `pipeline.py`, `scripts/build_reference.py` — Austin's ongoing
  uncommitted edits from before this session. **Do not touch unless
  Austin specifies.**

---

## Plan for the next session (after context clear)

1. **Confirm decision to revert.** Read this file and `CLAUDE.md`. The
   rulebook is fixed (`rules/*.md`); the prompt is patched
   (`prompts/extract.md` + `pipeline.build_extractor_prompt()`); the
   subagent pathway is the extractor.
2. **Re-run all 5 reference deals under the patched prompt via Claude
   Code subagents.** Batch size is Austin's call, but 2-3 parallel worked
   smoothly before. Order: `medivation`, `imprivata`, `zep`, `penford`,
   `providence-worcester`.
3. **Verify D1/D2/D3 close** on Penford + Providence. The count-audit and
   same-date multi-communication non-negotiables should cause:
   - Penford: both $18.50 verbal + $19 letter Bid rows on 2014-10-02.
   - Providence: Party E + Party F NDA rows on the right date (§B4
     midpoint) preceding their Bid rows.
   - Providence: 9 IOI Bid rows at the informal deadline (§E3 placeholders
     for unnamed bidders; §P-D6 each has a matching NDA).
4. **Verify M/I/Z stay clean.** The patched prompt should not introduce
   regressions on previously-clean deals.
5. **Adjudicate all 5 diffs** as before. Any lingering defects → patch
   again and re-run. Any persistent `both-defensible` → they're convention
   pins from the 8-pin list; flag for Austin's later decision.
6. **If all 5 clean, start the 3-run exit clock afresh.** All deals need
   3 consecutive clean runs under unchanged rulebook+prompt to bank exit.
7. **Then run `mac-gray`, `petsmart-inc`, `stec`, `saks`** — these four
   haven't been touched yet. Each tests a different archetype per
   `CLAUDE.md`. Saks last, solo, because §Q1 deleted-rows is unusual.

---

## Convention pins still deferred (unchanged from iter 1 handoff)

1. §B5 — "letter dated X / received Y" anchor
2. §K2 — Final Round Ann invite-vs-process-letter tie-break
3. §D1 — unsolicited first-contact: fold Bidder Sale or keep separate
4. §F1 — `bidder_type.note` convention
5. §R1/§N2 — whether `Executed` rows carry `bid_value_pershare` / unit /
   cash
6. §Scope-3 — `DateEffective = null` when filing predates closing
7. §Scope-3 — `TargetName` / `Acquirer` case formatting
8. §E3 — unnamed-bidder placeholder count for "several parties"

**New Zep-specific research question** (not a convention pin, just a
semantic call for Austin): Zep's `auction = False` under AI (§Scope-1 /
§P-S2 strict: phase-1 has only New Mountain's NDA) vs `True` under Alex
(legacy flat-count across both phases). The rulebook is pinned; if Zep
2015 should count as an auction for research purposes, §Scope-1 would need
amendment.

---

## Accumulated reference-builder action items (for Austin, not the Extractor)

These are ways to make Alex's reference files (`reference/alex/*.json`)
more rulebook-compliant so future diffs are less noisy:

**Imprivata:**
- Sponsor B 6/9 range-bid migration (`pershare=17` → null; `lower=17, upper=18`).
- §B4 midpoint on the 5/6–6/9 NDA window (5 NDAs currently `bid_date_precise=null`).
- Log Alex's 7/9 Executed date vs filing's explicit 7/13 (p.39) in `alex_flagged_rows.json`.

**Zep:**
- Atomize aggregated NDA/Drop rows (24 parties, 19 parties, 5 parties) per §E1.
- §H1 range-bid relabeling on Party A-E + Party X + Party Y bids.
- Drop the `"Exclusivity 30 days"` standalone row (§C3-deprecated; re-encode as `exclusivity_days=30` attribute on the related NDA row).
- Drop the `Final Round · None` phantom row.
- Upgrade Alex's `New Mountain Capital · Drop · 2014-04-14` → `DropAtInf` per §I1 (filing explicitly says NM decided not to submit an informal-round IOI).

**Penford:**
- §H1 range-bid relabeling on Party A 10/13 and Ingredion 9/17.
- Set `Ingredion · bidder_type.public = true` (NYSE:INGR is publicly traded).
- Log Alex's 10/8 "Ingredion formal bid $19" phantom in `alex_flagged_rows.json` (no filing support).
- Log Alex's 10/8 Executed date error (filing p.39 is 10/14) in `alex_flagged_rows.json`.
- Log Alex's Deutsche Bank IB 8/21 transcription error (should be 7/24 per filing) in `alex_flagged_rows.json`.

**Providence-Worcester:**
- Set `G&W · bidder_type.public = true` (NYSE:GWR is publicly traded).
- Log Alex's Party E 8/02 row as a filing misread (withdrawal confirmation, not new bid) in `alex_flagged_rows.json`.
- Log Alex's Executed date 8/15 error (filing signs 8/12, announces 8/15) in `alex_flagged_rows.json`.
- Expand aggregate NDA/Drop rows per §E1.

**Pattern across deals:** `scripts/build_reference.py` should (a) apply
§H1 legacy-migration on every range-bid row, (b) set `bidder_type.public`
based on exchange listing metadata, (c) atomize any multi-party NDA/Drop
aggregate rows per §E1/§E3.

---

## Operating notes

1. **Rulebook is frozen.** `rules/*.md` files are not to be edited.
2. **The prompt is patched.** `prompts/extract.md` and
   `pipeline.build_extractor_prompt()` carry the new count-audit and
   same-date multi-communication non-negotiables (commit `3af5ecf`).
3. **The Extractor is a Claude Code subagent.** Use the Agent tool with
   `subagent_type="general-purpose"`, fresh-context, and pass the output
   of `pipeline.build_extractor_prompt(slug)` plus a supplement that tells
   the subagent to Write to `/tmp/{slug}.raw.json` and report a short
   telemetry summary.
4. **Validate + finalize via `python run.py --slug X --raw-extraction /tmp/X.raw.json --no-commit`.**
5. **Diff via `python scoring/diff.py --slug X`** writes to
   `scoring/results/` (gitignored).
6. **Adjudicate via a fresh-context general-purpose subagent.** Its job
   is to verdict each divergence against the filing (not the rulebook).
   Templates: `scoring/results/medivation_adjudicated.md`,
   `imprivata_adjudicated.md`, `zep_adjudicated.md`,
   `penford_adjudicated.md`, `providence-worcester_adjudicated.md`.
7. **Commit state/progress.json per deal** with an informative message
   describing the diff counts, adjudication summary, and any defects.
   Use `--allow-empty` if the state change bundles into a prior commit.
8. **Don't touch Austin's uncommitted edits** on `AGENTS.md`, `CLAUDE.md`,
   `rules/*.md`, `scripts/build_reference.py`, `reference/alex/*.json`,
   or session logs unless he explicitly says so.
9. **Hook reminders lie.** The `READ-BEFORE-EDIT` hook fires even after a
   successful `Write` or `Edit`. Trust the tool's own success/failure
   response, not the hook's warning.
10. **`api_extractor.py` + `.env.linkflow` are archived on disk** as a
    dormant option. Do not run them unless Austin revisits the backend
    decision and you have new evidence that the quality regression is
    solvable.

---

## Files to read before taking action

1. This file (you're reading it).
2. `CLAUDE.md` — project context, ground-truth epistemology, stage gates.
3. `SKILL.md` — architecture contract.
4. `rules/*.md` — fixed rulebook; scan the section referenced by whatever
   task you take on. Do not edit.
5. `prompts/extract.md` + `pipeline.py` (lines 238-350 `build_extractor_prompt`)
   — the patched Extractor prompt.
6. `scoring/results/{slug}_adjudicated.md` — the 5 adjudication memos from
   this session's subagent runs (Medivation, Imprivata, Zep, Penford,
   Providence). Adjudication template.

---

**Commit graph at handoff:**

```
(uncommitted: .gitignore + api_extractor.py + Austin's other work)
3af5ecf Patch Extractor prompt: count audit + same-date multi-communication
1e192e4 Providence first-pass extraction: 2 AI defects (atomization count gaps)
9681776 Penford first-pass extraction: 1 AI defect (same-day bid atomization)
7761c5c Zep first-pass extraction: clean run, zero AI defects
d9b3a2a Imprivata first-pass extraction: clean run, zero AI defects
e996e62 Handoff: Stage 3 iter 1 complete, recommend Imprivata as next deal
ec22cbb Patch §B3 rough-anchor: inferred dates now populate bid_date_rough
a0397e1 Medivation re-extract post-patches: diff collapses 30→8 divergences
```
