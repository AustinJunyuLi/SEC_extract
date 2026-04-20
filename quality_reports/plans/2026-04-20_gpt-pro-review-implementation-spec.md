# Implementation Spec — GPT Pro Review Round 1

**Date:** 2026-04-20
**Source review:** `diagnosis/gptpro/2026-04-20/round_1/PROMPT.md` (snapshot `aae59af`)
**Reply (pasted into parent conversation):** see pre-spec transcript; formal copy should be saved to `diagnosis/gptpro/2026-04-20/round_1_reply.md` before execution.
**Verification:** 4 parallel read-only agents audited 25 claims. **25 VERIFIED**, 2 PARTIAL clarifications, 0 REFUTED. Full verification transcript in parent conversation.
**Status:** READY for execution. No changes landed yet.

---

## Prerequisites

- Current state: 8 `passed_clean` + 1 `passed` (providence, 20 soft). HEAD = `aae59af`.
- Do **not** start a new reference rerun until TIER 1 lands; current `passed_clean` readings are unreliable (T1-A).
- Exit clock is held at whatever interpretation Austin chooses. Neither strict 0/3 nor pragmatic 1/3 applies — the rulebook is about to change materially.

---

## Priority tiers

- **TIER 1 — CRITICAL** (fix before any rerun counts toward the exit clock).
- **TIER 2 — MAJOR** (rulebook↔validator contract reconciliation; unblocks safe promotion to 392).
- **TIER 3 — MEDIUM** (reference-data + diff tooling correctness; affects human review quality).
- **TIER 4 — MINOR** (cleanup; no correctness impact).

Each item: **Problem**, **Fix** (code or doc), **Acceptance**, **Effort**.

---

## TIER 1 — CRITICAL

### T1-A. Combined flag accounting (the exit clock is measuring the wrong thing)

**Problem.** `ValidatorResult` stores only flags returned by `validate()`. `summarize()` counts only those. Extractor-embedded `flags[]` on event rows (e.g. `date_inferred_from_context` soft, `implicit_drop` info, `pre_nda_informal_bid` info, `unnamed_count_placeholder` info) are invisible to status computation. Empirically:
- `state/progress.json` reports `zep: passed_clean, flag_count=0` while `output/extractions/zep.json` contains **75 soft + 53 info** severity occurrences.
- `medivation: passed_clean, flag_count=0` while its output has **14 soft + 7 info**.
Exit-clock logic (`passed_clean` across 3 runs) is measuring a subset of flags only.

Evidence: `pipeline.py:203-230`, `pipeline.py:994-1012`, `state/progress.json:3610-3855`, `output/extractions/{medivation,zep}.json`.

**Fix.**
1. Add a `count_flags(final_extraction: dict) -> dict[str, int]` helper in `pipeline.py` that walks `final["deal"]["deal_flags"]` + `final["events"][i]["flags"]` and returns `{"hard": N, "soft": M, "info": K}` combining extractor + validator sources.
2. Change `summarize()` to accept the final (post-merge) extraction and use `count_flags(final)`.
3. Update `finalize()` to call `summarize(final)` not `summarize(result)`.
4. Remove the now-redundant `hard_count/soft_count/info_count` properties on `ValidatorResult` (or retain only as private helpers with a comment).

**Acceptance.**
- Re-finalize all 9 deals. `state/progress.json` flag_counts should move from 0→(14+ for medivation, 128+ for zep, etc.).
- `passed_clean` should now mean "zero hard AND zero soft AND zero info across combined sources."
- `passed` should mean "only soft/info in combined sources."
- If too many deals flip out of `passed_clean` due to info-level `implicit_drop` / `pre_nda_informal_bid` annotations, **and** those are purely informational, consider redefining `passed_clean` to mean "zero hard AND zero soft" (exclude info). Decide explicitly in commit message; don't leave ambiguous.

**Effort.** 30–60 minutes. Priority: ship this first.

---

### T1-B. §P-G2 trigger directionality (validator accepts wrong formal/informal labels)

**Problem.** `_invariant_p_g2` line 709 matches any trigger from `ALL_G1_TRIGGERS = FORMAL_TRIGGERS + INFORMAL_TRIGGERS`. A row with `bid_type="formal"` whose `source_quote` contains `"expression of interest"` (informal trigger) passes the hard validator. §G1's classification intent (formal triggers support formal bids; informal triggers support informal bids) is not enforced. `bid_type` — the core research variable — has only a proxy evidence check, not a directional one.

Evidence: `pipeline.py:672-720` (line 705-709 uses `ALL_G1_TRIGGERS`), docstring at 707-708 explicitly acknowledges "existence-only."

**Fix.** In `_invariant_p_g2`:
```python
if bid_type == "formal":
    required = FORMAL_TRIGGERS
elif bid_type == "informal":
    required = INFORMAL_TRIGGERS
else:
    continue  # unexpected bid_type — caught by §P-R3 separately
if any(t in quote_text.lower() for t in required):
    continue  # direction-matched trigger
# range-bid and inference-note paths remain as before
```
Update `rules/invariants.md` §P-G2 condition (1) and `rules/bids.md` §G2 condition (1) to explicitly say "formal trigger for formal, informal trigger for informal."

**Acceptance.**
- Fixture test: row with `bid_type="formal"` + quote `"Party X submitted an expression of interest"` → HARD FLAG `bid_type_unsupported`.
- Fixture test: row with `bid_type="formal"` + quote `"Party X submitted a binding offer"` → passes.
- Rerun all 9 deals; document any rows newly flagged (these were wrongly classified under the old rule).

**Effort.** 45 minutes code + fixtures; 30 minutes to re-review any flips from the rerun.

---

### T1-C. §P-G2 range check uses != not < (validator accepts inverted ranges)

**Problem.** `pipeline.py:696` uses `lower != upper`, allowing `lower=30, upper=25` to count as a "true range bid." Both `rules/invariants.md:223-224` and `rules/bids.md:170-172` require `lower < upper`. Also non-numeric strings comparing unequal (e.g. `"30"` vs `"twenty-five"`) trigger range-pass.

Evidence: `pipeline.py:689-700`, code comment at line 696 itself admits intended `lower < upper`.

**Fix.**
```python
try:
    lo_num = float(lower)
    hi_num = float(upper)
except (TypeError, ValueError):
    pass  # not numeric — fall through to trigger/note checks
else:
    if lo_num < hi_num:
        continue
```
Emit hard flag `bid_range_inverted` when both are numeric and `lower >= upper`.

**Acceptance.**
- Fixture: `lower=25, upper=30, bid_type="informal"` → passes §P-G2.
- Fixture: `lower=30, upper=25, bid_type="informal"` → HARD `bid_range_inverted`.
- Fixture: `lower="$25", upper="$30"` → does NOT pass path (b); must fall to trigger or note.

**Effort.** 30 minutes.

---

### T1-D. Providence policy: delete the implicit-Drop mandates (§I1 + §M2 + stale flag)

**Problem.** Two rulebook sections demand the extractor emit "implicit Drop" rows for NDA signers with no later narrated activity:
- `rules/events.md:263-275` (§I1) — "the extractor MUST emit an implicit `Drop` row at the end of the main process phase."
- `rules/bids.md:492-503` (§M2) — "Folded into §I1's implicit-drop rule."
Iter-7 extraction declined this (per §R2 evidence-specificity) and emitted 20 soft `nda_without_bid_or_drop` flags on providence instead. Project decision per iter-7 results report: **accept iter-7's behavior (Path A)**. Rulebook must be updated to match.

Also: `phase_boundary_inferred` soft flag promised in `rules/events.md:578-579` (§L2) is unused in `pipeline.py`. Flag vocabulary must match what actually fires.

Evidence: `rules/events.md:263-275`, `rules/bids.md:492-503`, `quality_reports/plans/2026-04-19_stage3-iter7-results.md:102-135`.

**Fix.**
1. Rewrite `rules/events.md §I1` to say: "NDA-signing bidders with no later narrated Bid/Drop/Executed remain as NDA-only rows. §P-S1 raises a soft `nda_without_bid_or_drop` flag for human review. Do NOT fabricate catch-all Drops with generic shared `source_quote`."
2. Rewrite `rules/bids.md §M2` similarly — "no skip, no synthetic emission; NDA-only is permitted."
3. Update `rules/invariants.md §P-S1` rationale to reference Path A decision.
4. Delete the `phase_boundary_inferred` soft-flag mention in §L2 if not implementing it (see T2-D).

**Acceptance.**
- Rerun providence-worcester — 27 NDA rows + no catch-all Drops + 20 soft `nda_without_bid_or_drop` (unchanged from iter-7). Status = `passed` (not `passed_clean`).
- If `passed_clean` semantics are redefined (T1-A) to exclude info flags only, decide whether §P-S1 soft still blocks `passed_clean`. Recommendation: **yes**, keep `passed_clean` = zero hard + zero soft. Providence remains `passed`.
- Rulebook delta is doc-only, no code changes. Clock interpretation: rulebook changed (conservative 0/3) OR Path A is the already-intended state and this is doc cleanup (pragmatic clock-resets neutral). Austin decides.

**Effort.** 1 hour rulebook rewrite + careful cross-check for dangling refs.

---

### T1-E. `scoring/diff.py` rstrip bug (silently mangling bidder aliases)

**Problem.** `scoring/diff.py:85-89` uses `s.rstrip(suffix)` where `suffix` is a multi-char string like `" inc"`. Python's `str.rstrip(chars)` treats `chars` as a **set of characters to strip**, not a suffix string.

Empirical misfire: `normalize_bidder("Penford Inc")` → `"penfor"` (the "d" is stripped because `d` ∈ `" ltd"`). `"Alco"` → `"a"` (`c`, `o`, `l` ∈ `" llc"`). Any bidder alias ending in characters from the combined set `{' ', '.', ',', 'i', 'n', 'c', 'o', 'r', 'p', 'l', 't', 'd'}` gets truncated into gibberish.

Impact: AI-vs-Alex diff reports have been matching rows by garbled aliases. Many of the field-disagreement counts may be artifacts of collision on truncated keys.

Evidence: `scoring/diff.py:75-95`, verified behavior.

**Fix.**
```python
for suffix in (" inc.", " corp.", " ltd.", " inc", " corp", " ltd",
               " llc", " plc", ","):
    if s.endswith(suffix):
        s = s[:-len(suffix)]
        break  # strip at most one suffix per pass
```
Or use `s.removesuffix(suffix)` (Python 3.9+).

**Acceptance.**
- Fixture: `normalize_bidder("Penford Inc")` → `"penford"` (not `"penfor"`).
- Fixture: `normalize_bidder("SomeCo, Inc.")` → `"someco"` (sequential strips: `", Inc."` then `"Inc"`).
- Regenerate all 9 diff reports. Field-disagreement counts likely change materially.
- Suffix ordering: longest-first to avoid `" inc"` stripping before `" inc."`.

**Effort.** 15 minutes code + 15 minutes re-review of diff reports.

---

### T1-F. Fetcher accepts excluded form type 425

**Problem.** `scripts/fetch_filings.py:69-75` lists `"425"` in `PRIMARY_FORM_TYPES`. `rules/schema.md:91-105` §Scope-2 explicitly excludes 425 (merger communications, press-release-style, no Background section). A 425 filing will pass the form-type gate, get extracted, and fail silently against non-Background content.

Evidence: `rules/schema.md:91-105`, `scripts/fetch_filings.py:69-75`.

**Fix.**
1. Remove `"425"` from `PRIMARY_FORM_TYPES`.
2. Add a "fail-loud" check: if a seed's `form_type` is 425 or other §Scope-2-excluded value, emit a `state/progress.json` entry with `status="failed"` and `notes="excluded form type"`. Do not fetch.

**Acceptance.** `fetch_filings.py --dry-run` on a hypothetical 425 seed fails loudly rather than silently downloading.

**Effort.** 20 minutes.

---

## TIER 2 — MAJOR (rulebook↔validator contract reconciliation)

### T2-A. §P-D5: "earlier row" vs "any row except self"

**Problem.** Spec at `rules/invariants.md:108-136` says Drop needs an **earlier** same-phase engagement row. Code at `pipeline.py:498-574` checks "any witness except self" — a later NDA or later Drop can satisfy a prior Drop. Docstring at line 507-509 explicitly acknowledges the relaxation.

**Fix.** Pick one and align both. Recommendation: **keep code behavior** (existence check, not chronological), because canonicalization has already sorted rows by `(process_phase, bid_date, §A3 rank)` and "earlier" has no unambiguous meaning after order normalization in same-date cases. Rewrite `rules/invariants.md §P-D5` condition to "there exists at least one OTHER row (any row_index) in the same `process_phase` with `bid_note` ∈ {NDA, Bidder Interest, IB} or another Drop-family row."

**Acceptance.** Fixture: Drop at row i=5, NDA at row i=7 (later), same phase, same bidder → passes §P-D5 (existence). No flag.

**Effort.** 20 minutes rulebook update.

---

### T2-B. §P-S3: "last row terminates" vs "any row in phase terminates"

**Problem.** Spec `rules/invariants.md:197-205` says chronologically last event in each phase must be a terminator. Code `pipeline.py:854-915` checks "any terminator anywhere in phase." Code docstring at 858-886 admits the iter-5 relaxation.

**Fix.** **Keep code behavior.** Update spec to "each `process_phase` contains at least one terminator (Executed / Terminated / Auction Closed); position within phase is not enforced." Document the rationale: go-shop trailing activity and §A3 rank inversions make strict last-position enforcement brittle.

**Acceptance.** No code change. Rulebook updated.

**Effort.** 15 minutes.

---

### T2-C. §E2 joint-bidder BidderID vs §P-D3 unique/monotone

**Problem.** `rules/bidders.md:9-40` says joint Bid/Drop rows share the same BidderID; `rules/invariants.md:92-104` + `_canonicalize_order` enforce unique 1..N event-sequence BidderIDs. The extractor's shared IDs are silently overwritten during canonicalization — §E2's promise never survives to finalized output.

**Fix.** Keep canonicalization. Update §E2 to say: "Joint-bidder constituents share `joint_bidder_members` (canonical `bidder_NN` ids); each joint-bidder row still has its own unique event-sequence `BidderID`." Explicitly state that `BidderID` is event-sequence, not bidder-identity. Delete the "All N rows share the same BidderID" claim from §E2.

**Acceptance.** No code change. `rules/bidders.md §E2` updated. Existing joint-bidder data (e.g. mac-gray CSC/Pamplona) should display via `joint_bidder_members=["bidder_06","bidder_07"]` on the shared row, with `BidderID` = that row's event position.

**Effort.** 20 minutes.

---

### T2-D. §L2 phase-boundary validations (implement or delete)

**Problem.** `rules/events.md:569-600` §L2 promises 4 checks: (a) empty gap between Terminated and Restarted, (b) single Executed in highest phase, (c) no phase 2 without Terminated+Restarted, (d) no phase 0 within 6 months of phase 1/2. Only (b) is implemented (`_invariant_p_s4`). Three checks are promised but silent. The `phase_boundary_inferred` soft flag is also never emitted.

**Fix.** Decision: **implement (c) and (d); delete (a) and the `phase_boundary_inferred` promise.**
- (c) is cheap: scan events, assert `any(bid_note=="Restarted" and phase==1 for e in events_with_phase_2_predecessor)`.
- (d) requires date arithmetic: for each `process_phase=0` row, assert min(date delta to any phase ≥ 1 row) ≥ 6 months. Emit hard `stale_prior_too_recent`.
- (a) is ill-defined ("empty gap expected" is ambiguous — gap = zero events? or non-trivial gap allowed if no bidder activity?) — delete.
- Delete `phase_boundary_inferred` soft promise from §L2.

Update `rules/invariants.md` with §P-L1 and §P-L2 invariants, add table rows, wire into `validate()`.

**Acceptance.**
- Fixture: phase 2 row exists without preceding Terminated+Restarted pair → hard `orphan_phase_2`.
- Fixture: phase 0 row 2013-01-01 + phase 1 row 2013-03-15 (<6 months) → hard `stale_prior_too_recent`.
- Rerun reference set. Only zep has phase 2; only penford has phase 0 — verify both still pass.

**Effort.** 90 minutes (2 new invariants + tests + §L2 rewrite).

---

### T2-E. §E4 alias-registry validation (implement or delete)

**Problem.** `rules/bidders.md:173-200` §E4 promises alias checks: every `bidder_alias` must be in `aliases_observed` for its `bidder_name`; `resolved_name` (if non-null) should appear in `aliases_observed`. `pipeline.py:464-480` §P-R5 only checks `bidder_name` exists as registry key.

**Fix.** Implement both checks:
```python
# In _invariant_p_r5:
registry = deal.get("bidder_registry", {})
for i, ev in enumerate(events):
    name = ev.get("bidder_name")
    alias = ev.get("bidder_alias")
    if name is None:
        continue
    if name not in registry:
        flags.append({"row_index": i, "code": "bidder_not_in_registry", "severity": "hard", ...})
        continue
    aliases = set(registry[name].get("aliases_observed", []))
    resolved = registry[name].get("resolved_name")
    if alias and alias not in aliases:
        flags.append({"row_index": i, "code": "bidder_alias_not_observed", "severity": "hard",
                      "reason": f"bidder_alias={alias!r} not in registry's aliases_observed for {name!r}"})
    if resolved and resolved not in aliases:
        flags.append({"row_index": i, "code": "resolved_name_not_observed", "severity": "soft", ...})
```

**Acceptance.** Fixture: row with `bidder_alias="Party Z"` but registry has `aliases_observed=["Party A","Party B"]` → hard flag.

**Effort.** 45 minutes code + fixtures.

---

### T2-F. §H5 bid_revision_out_of_order (implement)

**Problem.** `rules/bids.md:350-379` §H5 promises a soft check: "for any bidder with >1 bid row, bids are chronologically ordered by `bid_date_precise`." No such invariant exists in `pipeline.py`. Also `rules/invariants.md` has no §P-H5 section.

**Fix.** Add `_invariant_p_h5`:
```python
def _invariant_p_h5(events):
    by_name = defaultdict(list)
    for i, ev in enumerate(events):
        if ev.get("bid_note") == "Bid" and ev.get("bidder_name"):
            by_name[ev["bidder_name"]].append((i, ev))
    flags = []
    for name, rows in by_name.items():
        dates = [r[1].get("bid_date_precise") for r in rows if r[1].get("bid_date_precise")]
        if dates != sorted(dates):
            flags.append({"row_index": rows[-1][0], "code": "bid_revision_out_of_order",
                          "severity": "soft", ...})
    return flags
```
Add §P-H5 to `rules/invariants.md`. Wire into `validate()`.

**Acceptance.** Fixture: bidder X has bid at 2016-05-10 then bid at 2016-04-20 (out of order) → soft flag.

**Effort.** 30 minutes.

---

### T2-G. `_invariant_p_r3` null-permission too broad

**Problem.** `pipeline.py:436-447`: `if bn is None or bn in EVENT_VOCABULARY: continue` — null allowed for any row. §P-R3 spec at `rules/invariants.md:55-58`: "null permitted only on bid rows per §C3" (a narrow legacy window). Current §C1/§C3 say bid rows use `bid_note="Bid"` (no null). The permissive code defeats the spec.

**Fix.**
```python
if bn is None:
    # Under §C3, bid_note="Bid" is required on bid rows. null is a legacy
    # artifact from migration. Reject in production.
    flags.append({"row_index": i, "code": "bid_note_null", "severity": "hard",
                  "reason": "§P-R3: bid_note=None; §C3 requires 'Bid' on bid rows."})
    continue
if bn not in EVENT_VOCABULARY:
    flags.append({...})
```
OR: if legacy null rows actually exist and must be tolerated, narrow the permission to rows with `bid_value` / `bid_value_pershare` populated AND emit soft flag `bid_note_missing_legacy`.

**Acceptance.** Rerun reference set — report any new flags. Decide tolerance policy.

**Effort.** 30 minutes.

---

### T2-H. Clarify that the Adjudicator is orchestrator-spawned, not Python-spawned

**Problem — miscalibrated in GPT Pro's review.** GPT Pro flagged "the Adjudicator is documented but never implemented, no Python spawn path." That's literally true but misreads the architecture: the Adjudicator is **intentionally** orchestrator-spawned. `pipeline.py:1224-1227` explicitly states: "Does NOT spawn adjudicator subagents — that's the orchestrator's job, performed BEFORE calling this function. If the caller has adjudicated soft flags, they should mutate raw_extraction['events'][i]['flags'] and/or raw_extraction['deal']['deal_flags'] with adjudicator verdicts before passing raw_extraction in."

This is an accurate design note, not ghost code. The orchestrator (the LLM driving the session — a Claude Code conversation) reads the validator's soft flags, spawns an Adjudicator subagent (or does adjudication inline), mutates the raw extraction with verdicts, then calls `pipeline.finalize()`. This pattern has been used repeatedly (e.g. the 4 verification agents in this very session, the 3 re-extraction agents for iter-7, the 2 dead-code audit agents).

The real problem is that SKILL.md's orchestration pseudocode (lines 74-92) doesn't make it clear enough that "spawn Adjudicator subagent" is an **LLM-orchestrator action**, not a Python call.

**Fix.** Documentation clarity, not deletion.
1. Update `SKILL.md` orchestration pseudocode to explicitly label the Adjudicator step as "orchestrator-side LLM call, not a Python entry point." Add a cross-reference to the `pipeline.finalize()` docstring.
2. Add a short note in `pipeline.py` module docstring (around line 1-23) restating the same division of concerns: Python owns the validator + finalization; the LLM orchestrator owns Extractor spawning, Adjudicator spawning, and pre-finalize flag mutation.
3. Do NOT implement an `adjudicate()` function in Python — the soft-flag workflow remains orchestrator-controlled. Volume-driven: current soft-flag load (20 on one deal) is hand-tractable.

**Acceptance.**
- SKILL.md line 74-92 contract is unambiguous about which steps are Python vs LLM-orchestrator.
- `pipeline.py` docstring does not invite readers to look for an `adjudicate()` that isn't there.
- Architecture description matches the actual operating pattern (already working in this repo).

**Effort.** 15 minutes doc clarification.

---

### T2-I. Fix `run.py --dry-run` asymmetry

**Problem.** `run.py:59-75` dry-run calls `pipeline.validate()` directly; non-dry-run goes through `pipeline.finalize()` which applies `_apply_unnamed_nda_promotions()` + `_canonicalize_order()` first. Dry-run reports flags finalize would fix and misses flags finalize introduces.

**Fix.** In dry-run, call the same pre-validate transform path as finalize:
```python
if dry_run:
    raw_copy = copy.deepcopy(raw_extraction)
    promotion_log = pipeline._apply_unnamed_nda_promotions(raw_copy)
    pipeline._canonicalize_order(raw_copy)
    # ... inject failed-promotion flags as finalize does ...
    result = pipeline.validate(raw_copy, filing)
    ...
```
Make the transform + validate block a helper used by both paths.

**Acceptance.** Dry-run of iter-7 providence reports same flag profile (0 hard, 20 soft) as finalize.

**Effort.** 30 minutes.

---

## TIER 3 — MEDIUM (build_reference + diff + docs)

### T3-A. Remove `bidder_type.note` from `scripts/build_reference.py`

**Problem.** `scripts/build_reference.py:437-469` emits `{"base", "non_us", "public", "note"}`. Schema (§F1) requires only 3 fields — no `note`.

**Fix.** Drop the `note` field. Any content that was going there should either (a) be discarded, or (b) go to a row-level `flags[]` entry with appropriate code. All 9 reference JSONs should be regenerated.

**Acceptance.** `grep -rn '"note":' reference/alex/*.json` returns zero matches for `bidder_type.note`.

**Effort.** 30 minutes (fix + regenerate + spot-check).

---

### T3-B. Fix `first_appearance_row_index` field name in registry

**Problem.** `scripts/build_reference.py:883` emits `"first_appearance_BidderID"`; schema (§E3) specifies `"first_appearance_row_index"`. All 9 reference JSONs use the wrong key.

**Fix.** Rename the field in `build_reference.py` (it should be the row-index, not the BidderID — though in practice with §A4 strict monotonicity these coincide, the schema choice is row-index for interpretability).

**Acceptance.** All 9 `reference/alex/*.json` have `first_appearance_row_index` under `bidder_registry.{bidder_XX}`.

**Effort.** 15 minutes.

---

### T3-C. `scoring/diff.py` duplicate-bucket matching brittleness

**Problem.** `scoring/diff.py:168-184` matches rows by `join_key = (normalize_bidder(alias), bid_note, bid_date_precise)`. When AI has N rows with the same key and Alex has M rows (e.g. AI atomizes 15 NDAs on one day, Alex aggregates 3), `zip()` pairs the first min(N,M) in insertion order with no tiebreaker. Remaining rows go to `ai_only_rows` / `alex_only_rows`. Field diffs inside paired buckets are arbitrary.

**Fix.** When `len(ai_bucket) != len(alex_bucket)`:
- Emit a single pseudo-row disagreement `cardinality_mismatch: AI={N} vs Alex={M}` for that key.
- Do NOT attempt field-level pairing inside buckets with cardinality mismatch (it's noise).
- Mark all rows as `cardinality_mismatched` in the report so Austin knows to review the whole bucket.
Alternatively, when cardinalities match, retain current zip. When they differ, collapse the whole bucket into a single diff entry.

**Acceptance.** Run diff on providence iter-7: the 27-vs-2 NDA mismatch should produce ONE cardinality-mismatch entry, not 25 ai_only rows.

**Effort.** 60 minutes (algorithm rewrite + test + regenerate reports).

---

### T3-D. Remove deprecated vocabulary from `build_reference.py` rank map

**Problem.** `scripts/build_reference.py:143-173` rank map contains `Target Initiated` (not in §C1), `DropBelowFormal` (not in §C1), `DropAtFormal`, `Final Round Formal`, `Late Bid` — 5 entries. `rules/events.md:9-63` §C1 is the closed vocabulary; these aren't in it.

**Fix.**
- Option A (safe): audit whether any Alex xlsx rows use these legacy labels. If yes, the `_migrate_bid_note()` function should convert them to current §C1 vocabulary (`Target Initiated` → `Target Interest`, `DropBelowFormal` → `DropBelowInf`, etc.). Then delete from rank map.
- Option B (loud): delete rank map entries outright. If migration missed a row, the pipeline will emit a vocabulary-violation flag.

Recommend B. Delete. Fail loud.

**Acceptance.** `reference/alex/*.json` regenerated. No entries use deprecated labels. Any new `unknown_bid_note` flags = migration gap to investigate.

**Effort.** 30 minutes + audit.

---

### T3-E. "Several = 3 minimum" cross-reference: add to §E3 or repoint

**Problem.** `prompts/extract.md:35` instructs the extractor "`several` = 3 minimum; vaguer plurals emit one placeholder plus ambiguity flag. Per rules/bidders.md §E3." But §E3 (`rules/bidders.md:96-162`) covers canonical IDs / aliases / registry — no count semantics.

**Fix.** Two options:
- **Option A:** Add the count policy as a new sub-section (e.g. `§E3.5 — Quantifier semantics`) to `rules/bidders.md` with the rule: "exact counts stay exact (e.g., 'three parties' → 3 placeholder rows); 'several' means minimum 3; 'a number of', 'a few', 'multiple' (vague plurals) → emit one placeholder row with `unnamed_count_placeholder` info flag."
- **Option B:** Move the rule to `rules/schema.md` §Scope-3 (which already discusses placeholder row emission). Repoint the prompt.

Recommend A (keep bidder concerns in bidders.md).

**Acceptance.** `rules/bidders.md §E3.5` (or §E5) contains the rule. Prompt pointer updated.

**Effort.** 20 minutes.

---

### T3-F. `prompts/extract.md` line 3 — "two-agent" is false

**Problem.** `prompts/extract.md:3`: "You are the Extractor in a two-agent M&A auction extraction pipeline." Current architecture is Extractor LLM + Python Validator (+ planned Adjudicator being deleted per T2-H). The prompt lies to the extractor about its surroundings on its first sentence.

**Fix.** Rewrite as: "You are the Extractor. Your output feeds a deterministic Python validator (`pipeline.validate()`). A human reviewer (Austin) audits every flagged row against the filing text."

Also check `prompts/extract.md:47` reference to "Validator or human decide" — "Validator" is Python, not an agent. Adjust wording.

**Acceptance.** No "two-agent" anywhere in `prompts/extract.md`.

**Effort.** 15 minutes.

---

### T3-G. Document `state/flags.jsonl` timestamp-filter requirement

**Problem.** The jsonl file is append-only. Accumulated stale entries from prior runs inflate counts unless filtered by `logged_at`. Agents and humans have been fooled by this (per project-memory). Neither SKILL.md nor rules/schema.md documents the gotcha.

**Fix.** Add a note in `rules/schema.md` flag section (around line 311-313) and in `SKILL.md` state-log bullet:
> "`state/flags.jsonl` is append-only and accumulates history. For current-state queries, filter by `logged_at` timestamp ≥ the latest finalize for the deal, OR trust `output/extractions/*.json` `flags[]` arrays (the post-finalize authoritative copy) and `state/progress.json` flag_count."

**Acceptance.** Note appears in both files.

**Effort.** 10 minutes.

---

## TIER 4 — MINOR (cleanup)

### T4-A. Reopen the deferred 25-deal language pilot

Not a code change. Project decision: before promoting to 392 target deals, pilot §G1/§K2/date-phrase coverage on ~25 varied (non-reference) deals. The 9 reference deals are probably too homogeneous for trigger-phrase coverage signals. Decide scope after T1-B (§P-G2 directionality) lands.

**Effort.** Scope decision + pilot run: 1 day.

---

### T4-B. Fixture tests for every invariant

No pytest framework exists. Add `tests/` directory with one JSON fixture + one expected-flags JSON per invariant. Use `pytest` or plain `python -m unittest`. Start with invariants changed in TIER 1–2.

Priorities: §P-G2 (T1-B, T1-C), §P-D5 (T2-A), §P-S1, §P-S3 (T2-B), §P-D3, §P-R3 (T2-G), §P-R5 (T2-E), §P-H5 (T2-F), §P-L1/L2 (T2-D).

**Effort.** 2–3 hours for initial framework + 10 fixtures.

---

## Execution order

1. **T1-A** first. (Flag accounting fixes all downstream status claims.)
2. **T1-B, T1-C, T1-E** in parallel. (Independent; all catch real bugs.)
3. **T1-D** (Providence/§I1/§M2) — doc-only, after or parallel with above.
4. **T1-F** (fetcher 425) — standalone.
5. **T2 tier** after T1 lands. Run reference set once post-T1 and re-baseline the flag profile.
6. **T3 tier** after T2 lands.
7. **T4** as available bandwidth permits.
8. **Rerun reference set** only after T1 + T2 fixes land. Treat first post-fix rerun as baseline, not clock-run #1.

---

## Exit-clock impact

All TIER 1 and TIER 2 changes **touch the rulebook** (rules/*.md + prompts/extract.md + validator code). Per the exit-clock definition, this resets the clock to **0/3**. The pre-spec "pragmatic 1/3" interpretation from iter-7 closeout is voided by this spec's changes.

After T1+T2 land and one full reference-set rerun passes with: (a) zero hard flags, (b) all soft flags adjudicated or explicitly accepted (Path A on providence nda_without_bid_or_drop), (c) all extractor-embedded annotation flags accounted for — that rerun counts as **1/3**. Run 2 & 3 follow with no further rulebook change.

---

## Out of scope

- NDA atomization-vs-aggregation adjudication (AI emits 15–27 NDAs, Alex aggregates 2–3) — per-deal human review, not a spec item.
- `bidder_type.public` converter-policy inference — separate converter-policy decision, affects `scripts/build_reference.py`.
- Target-deal rollout to 392 — blocked behind exit-clock gate.

---

## Success criteria for this spec

- All 25 VERIFIED findings from the GPT Pro review have been addressed (TIER 1–3).
- Rulebook (rules/*.md + prompts/extract.md) and validator (pipeline.py) are internally consistent. Every documented invariant is implemented; every implemented invariant is documented.
- Exit-clock semantics are explicit and measurable (combined hard+soft+info accounting from T1-A).
- Fixture tests catch each class of bug.
- Reference-set rerun under the post-spec rulebook produces zero hard flags + adjudicated softs.
