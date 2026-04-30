# Code review: 2026-04-29-robust-extraction-redesign.md

Reviewer: Claude (Opus 4.7, 1M ctx)
Date: 2026-04-29
Method: 5 parallel agent passes over `pipeline/`, `rules/`, `tests/`,
`output/extractions/`, `state/flags.jsonl`, `quality_reports/session_logs/`,
`docs/linkflow-extraction-guide.md`. All agent findings spot-verified against
source.

---

## Bottom line

The design is right that the model is doing too much bookkeeping. The
diagnosis is broadly correct. **The proposed remedy is overfitted to limited
evidence and is, in roughly half its scope, redundant with the pipeline as it
exists today.** Three structural problems:

1. **Half of "What Moves To Python" is already in Python.** Canonical
   ordering, `BidderID` reassignment, quote-substring validation, rough-date
   symmetry, the `unnamed_nda_promotion` consumer, and Background-section
   slicing all live in `pipeline/core.py` and `pipeline/llm/extract.py`. The
   redesign moves at most ~5 of the 16 listed items.
2. **The taxonomy expansion (7 new enum/field families) is mostly
   unjustified by data.** Of 5 stated instabilities, only 2 are concretely
   on disk (zep cohort double-count, mac-gray §P-G3 same-day). 3 are
   speculative. None of the proposed enum changes mechanically fix the 2
   that are real; both require a rulebook or validator change.
3. **Phase 2 (candidate-fact extraction) is the largest, riskiest phase
   and is being added before its premise is verified.** It rewrites the
   intermediate representation, breaks 65 tests, requires regenerating 63
   fixtures, and adds 800–1000 LOC — on the basis of 2 hard-flag swaps over
   9 deals. The user's stated rule was *"watch the pipeline fail before
   adding new functionality."* Phase 2 violates that rule.

The design is salvageable. **Do Phase 0 first, alone, and let it generate
the cross-run evidence the rest of the design currently lacks.** Then
re-evaluate.

---

## Verified findings (with citations)

### What's already in Python (design appears not to know this)

| Design says "Python should own" | Where it lives today | Status |
|---|---|---|
| Final row order | `pipeline/core.py:2169` `_canonicalize_order()` sorts on `(bid_date_precise, §A3 rank, narrative_index)` | DONE |
| `BidderID` assignment | `pipeline/core.py:2201–2203` reassigns `BidderID = 1..N` | DONE |
| Quote length enforcement | `pipeline/core.py:528–623` §P-R2 (1500-char hard) | DONE |
| Rough-date rules | `pipeline/core.py:1140–1164` §P-D2 (XOR symmetry) | DONE |
| `unnamed_nda_promotion` consumer | `pipeline/core.py:2057–2156` | DONE |
| Hard invariant checking | 26 `_invariant_*` functions, ~28 hard codes | DONE |
| Background section slicing | `pipeline/llm/extract.py:142–249` `_find_background_start/_end`, `_background_section_payload` | DONE |
| Linkflow prompt-only JSON | `pipeline/llm/client.py:60` `supports_structured_output = not _is_newapi_base_url(base_url)` | DONE |

### What's genuinely new

- Paragraph-ID indexing (no analog today).
- Source quote/page **generation** from paragraph IDs (today the model
  emits them; Python only validates).
- `auction` Python-computed (today the model emits, Python only checks).
- DropSilent **generation** (today the model emits, §P-S1 only flags
  misses).
- Exact-count anonymous **expansion** (today validation-only).
- A stability harness (no precedent at all).

That is the real Phase scope. The other items are nominal renames.

### What the design is wrong about

**Phase 0 premise is correct: runs ARE overwritten.** `pipeline/run_pool.py:232–238`
unlinks `raw_response.json`, deletes `prompts/`, clears `calls.jsonl` on
fresh extract. There is no run-id namespacing in `output/audit/{slug}/`.
Confirmed: `output/audit/zep/` contains exactly one `raw_response.json`
(312 KB), one `manifest.json`, no run-id directory. The "high vs xhigh"
comparison in the session logs was reconstructible only because the high
run finished before the xhigh run was launched and the session log
narrated the deltas. **The design is right to put this first.** It is
also the simplest, lowest-risk piece.

**Background-section slicing is already implemented.** Phase 1 as
described (lines 386–389) is largely a no-op. What Phase 1 actually adds
beyond current code is paragraph-ID *granularity* — splitting the
already-sliced section into stable paragraph IDs. That is genuinely new
work, but the design's framing makes it sound like the section slicing
itself is missing. It isn't.

---

## The taxonomy proposals — per-enum verdict

| Proposal | Justified by observed failure? | Schema change needed? | Verdict |
|---|---|---|---|
| `date_basis` (6 values) | No — date flags dominate (485 of top 20 codes) but no documented cross-run flag flipping | No — derivable from existing `(bid_date_rough, flags)` | **Compiler-derived field, not new schema column** |
| `bid_type_basis` (10 values) | No — zero hard `bid_type` failures in either reference run | Yes (drops `bid_type_inference_note`) | **Reject. Replacing free-text with a 10-value enum multiplies decision points without an observed failure to justify it. Keep current `bid_type_inference_note`** |
| Formal-stage enum (4 values) | No — 83% of rows have both booleans null; only 7 `formal_round_status_inferred` flags total | Yes (collapses two booleans) | **Reject. Strictly less expressive: cannot represent `(invited=null, submitted=true)`.** Two booleans + the existing `formal_round_status_inconsistent` check are correct as-is. |
| `final_round_role` (4 values) | Partial — mac-gray hard flag is on missed milestone row, not on field representation | Yes | **Reject as a stability fix.** The mac-gray failure was the model omitting a milestone row when announcement and bid landed on the same day. That is a §P-G3 rulebook clarification or extractor-prompt fix, not an enum change. The enum is cosmetic re: the actual root cause. |
| Cohort fields (`cohort_id`, `cohort_size`, `cohort_basis`) | Yes — zep double-count is concretely tied to cohort identity | Compiler layer | **Accept, but as compiler-output fields.** §E5 already defines stable placeholder handles; the compiler can derive cohort identity from alias reuse. The model does not need a new emit field. |
| `drop_group_basis` (4 values) | No — current `drop_group_count_unspecified` flag already signals vagueness | Compiler layer | **Optional. Marginal audit value.** |
| Dropout provenance resolution | n/a — already mapped in `scripts/build_reference.py` | No | **Already done.** Codify the existing mapping in `rules/events.md` §I1.d for documentation; do not redo. |

**Net: 1 of 7 proposals is justified and even that one belongs in the
compiler, not the schema. The remaining 6 are either equivalent-to-current,
strictly-less-expressive, cosmetic, or already done.**

This is the clearest evidence the design is overfitted to two failures
seen in two single-attempt runs.

---

## The 5 instability claims — empirical check

| Claim | On-disk evidence | Verdict |
|---|---|---|
| 1. Anonymous bidder/cohort accounting changed substantially | zep row count delta 51→92; session log narrates double-count | **Real but bounded — one deal, one run pair** |
| 2. Date uncertainty flags substituted for each other across runs | Within-deal inconsistency present; **no cross-run snapshot exists** because the high run was overwritten | **Cannot verify; design's strongest empirical gap** |
| 3. Final-round decomposition created/removed hard flags | mac-gray xhigh §P-G3; no high snapshot | **Real but bounded — one deal, one direction** |
| 4. Formal-stage enrichment moved between inferred/inconsistent/null | 83% of rows null on both booleans; only 7 `formal_round_status_inferred` flags total | **Largely unsupported — fields are too sparse to be unstable** |
| 5. Bid-value representation and free-text bid-type notes changed phrasing and field placement | No example of bid moving between `bid_value` / `bid_value_pershare` columns; `bid_type_inference_note` samples thematically consistent | **Unsupported — phrasing variance is normal** |

Two of five claims are real (and both are fixable with a rulebook
clarification rather than an architecture rewrite). One is unverifiable
because the cross-run artifacts were overwritten — which is exactly the
problem Phase 0 is meant to solve. The remaining two are not visible in
the data.

**This is the central reason to start with Phase 0 only.** Phase 0
generates the evidence to decide whether Phases 2–5 are needed at all.

---

## Phase-by-phase review

### Phase 0 — Immutable run archive
- **Premise: correct** (verified: code does overwrite).
- **Cost: low** (~50–100 lines).
- **Risk: minimal** (3 cache-tests need updating).
- **Value: high** — every other phase claims to be justified by cross-run
  comparison that you cannot do today.
- **Recommendation: ship this alone, on its own branch, before
  committing to the rest of the design.** Then re-run the reference set
  three times at xhigh and read the actual deltas.

### Phase 1 — Background paragraph index
- **Premise: partly already done.** The Background section is already
  isolated in Python (`extract.py:142–249`); only paragraph-ID
  granularity is new.
- **Cost: low** if implemented as a deterministic split inside the existing
  slicer.
- **Caveat:** the prompt and validator currently rely on `pages.json`
  page numbers. Switching to paragraph IDs means changing the validator's
  §P-R2 substring check from page-content to paragraph-content. That
  change is small but invasive.
- **Recommendation: defensible, but only after Phase 0** — no point
  changing the evidence spine until you know what you're stabilizing
  against.

### Phase 2 — Candidate-fact extraction
- **Risk: high.** Test agent estimate: 65 tests broken, 63 fixtures
  regenerated, 800–1000 LOC, 5–7 days, plus hand-audit of 5 deals against
  Alex's reference.
- **Premise weakness: the failures it is responding to are 2 hard-flag
  swaps and 3 speculative claims.** The current architecture is not
  *broken*; it is *flickering at the margin*.
- **Concrete concern:** the candidate-fact format described on lines
  69–83 strips out fields the model is currently good at producing
  (`bid_note`, `bid_type`, `final_round_*` booleans, evidence quotes).
  The bet is that a downstream "scoped classifier" will rebuild them more
  stably. There is no evidence for that bet.
- **Recommendation: do not commit to Phase 2 until Phase 0 has produced
  three repeat reference runs that show systematic instability beyond
  the two known failures.** If the actual deltas across three xhigh runs
  are cohort + same-day final-round only, you should fix those two
  things in the rulebook and the prompt and *not* restructure the model
  contract.

### Phase 3 — Deterministic compiler
- Conditional on Phase 2. Same comment applies.

### Phase 4 — Scoped semantic classifiers
- The phase makes sense in principle; without Phase 2 it has nothing to
  classify.

### Phase 5 — Stability gate
- The metrics list (lines 161–172) is reasonable. **It can be
  implemented immediately on top of Phase 0**, before any architectural
  change, by computing per-run row-count / flag-count / lifecycle-balance
  stats and diffing across run IDs. Doing this in isolation would
  produce decision-quality data within days.

---

## Things the design quietly gets right

- **Linkflow contract enforcement** (lines 174–207). Every "do not"
  matches what `pipeline/llm/client.py`, `response_format.py`, `retry.py`,
  and `watchdog.py` already enforce. The design is correctly *codifying*
  current safe behavior, not changing it. Useful as an explicit doc.
- **No JSON repair calls** — verified absent.
- **Run archive premise** — verified correct.
- **Paragraph evidence as durable unit** — defensible *if* you commit
  to Phase 2.
- **Acceptance criterion #2 ("no strict structured-output payload to
  Linkflow")** — already true in code.

---

## Things the design gets wrong or under-justifies

1. **"What Moves To Python"** (lines 343–360) reads as a future-work list
   but ~half of it is already past-work. List the items by status:
   `done | new | move`. Today the design is not honest about the split.
2. **"Hidden semantics should become structured fields"** (line 46) is
   used to justify 7 enum families. Most of those 7 do not pass the test
   "is there a hidden semantic?" — the semantics are already structured
   (booleans, vocab fields, flag codes). Free-text inference notes are a
   small fraction of the schema and are not the cause of the two known
   instabilities.
3. **`final_round_role` enum** is presented as fixing same-day
   announcement-and-deadline cases. It does not. Mac-gray's failure was
   the model not emitting a row, not a row with the wrong field shape.
4. **Formal-stage enum collapse** is strictly less expressive. The two
   booleans can represent (null, true) — invitation unknown but
   submission certain. The proposed enum cannot. No observed failure
   justifies the loss.
5. **`bid_type_basis` (10 values)** without observed bid_type failures
   is the clearest piece of overengineering in the document.
6. **Phasing risk concentration**: Phase 2 is the largest scope and the
   one with the weakest empirical justification. By design principle,
   the largest piece of work should depend on the strongest evidence.

---

## Recommended simplified path

**Step 1 — ship Phase 0 by itself, in isolation.**

Concrete shape (all paths are guesses; adjust as you implement):
- New: `output/audit/{slug}/runs/{run_id}/` containing `raw_response.json`,
  `manifest.json`, `calls.jsonl`, `prompts/`.
- Convenience: `output/audit/{slug}/latest -> runs/{run_id}` symlink so
  current consumers keep working.
- Stop unlinking on fresh run; instead mint a new run dir.
- Rotate / cap by run count, not by overwrite. Use the existing
  `last_run_id` UUID.
- ~50–100 lines, ~3 tests to update, no schema change.

**Step 2 — implement the stability harness as a read-only consumer of
Phase 0 archives.**

- Walk `output/audit/{slug}/runs/`, compute row-count / hard-flag /
  lifecycle / final-round / cohort metrics per run, diff pairwise.
- ~200 lines, no production-path change, no test rewrite.
- This is the deliverable that tells you whether the rest of the
  redesign is needed.

**Step 3 — run the reference set 3× at xhigh and read the metrics.**

If the only systematic deltas are zep cohort and mac-gray same-day:
- Fix in `rules/bidders.md` §E5: explicit named-vs-anonymous cohort
  allocation rule.
- Fix in `rules/invariants.md` §P-G3: explicit same-day announcement
  pairing rule.
- Update the validator and prompt to match.
- Regenerate references, advance the stability clock.

If the metrics show systematic instability beyond those two: at that
point you have evidence to commit to Phase 1–4 in the order the design
proposes. Until then, Phases 1–4 are speculation.

**Step 4 — adopt one or two compiler-layer enrichments without
schema change.**

- `date_basis` derived from `(bid_date_rough, flags)` in
  `pipeline/core.py:finalize_prepared()` — pure function of existing
  fields, no model change, no validator change, no fixture regen.
- Cohort identity derived from §E5 placeholder reuse, exposed as
  `_cohort_id`/`_cohort_size` in compiler output.
- ~150 lines. Optional.

**Total before committing to Phase 2: ~400 lines, ~5 tests, no fixture
regeneration, no breaking change.** If after this you still see model
instability beyond the two known failures, the original design is
justified. If not, you have shipped the win and avoided 1500+ lines of
risk.

---

## Items to delete or rephrase in the design document

- **Lines 343–360 ("What Moves To Python"):** mark each item with
  current status (done | new | partly done). Otherwise the redesign
  understates what already exists and overstates the implementation
  cost it is buying.
- **Lines 27–34 (instability list):** retain claims 1 and 3 with
  citations to session logs. Mark claims 2, 4, 5 as "to be verified
  against Phase 0 archive." Do not let speculative claims drive
  architecture commitment.
- **Lines 246–294 (taxonomy expansion):** scope down to `cohort_*`
  (compiler-layer, derived from §E5) and `date_basis` (compiler-layer,
  derived from existing fields). Drop the rest until evidence appears.
- **Phase 2 section (lines 391–394):** mark as **conditional on Phase 0
  + stability harness producing systematic-instability evidence beyond
  the two known failures.** Otherwise this is the most expensive
  speculative work in the doc.
- **Acceptance criterion #11 ("repeated reference-set runs are archived
  instead of overwritten"):** this can and should be the **first**
  acceptance gate, satisfied entirely by Step 1 above.

---

## Risk if the design ships as-written

- ~17–26 days of implementation, 1600–2100 LOC, 65 broken tests, 63
  regenerated fixtures.
- Reference-stability clock resets on every fixture regen.
- Most of the new fields cannot be validated against Alex's reference
  (Alex's workbook has no `cohort_id`, no `bid_type_basis`, etc.) — so
  the redesign reduces, not increases, the AI-vs-Alex comparison
  surface during the period when it most needs verification.
- The two genuinely-broken cases (zep cohort, mac-gray §P-G3) get fixed
  somewhere around week 3 of the rebuild instead of in a 1-day
  rulebook+validator patch.
- Production extraction of the 392 target deals stays gated for the
  duration.

The risk-adjusted return on the design as written is poor relative to
**Phase 0 + stability harness + two rulebook patches**, which can
deliver the same observable outcomes (stable cohort accounting; correct
same-day final-round handling; archived runs you can compare) in well
under a week with effectively zero fixture regeneration.

---

## Final verdict

**Right diagnosis. Wrong dose.** The redesign is reading 2 known
hard-flag swaps and 3 unverified instability claims as evidence for a
full architecture rewrite. The codebase already does most of what the
redesign says it will start doing. The taxonomy proposals are mostly
not justified by data. Phase 0 alone delivers the evidence that would
prove or disprove the rest of the design.

Ship Phase 0. Ship the stability harness on top of it. Run the
reference set three times. Read the data. Then decide whether Phase 2
is necessary.
