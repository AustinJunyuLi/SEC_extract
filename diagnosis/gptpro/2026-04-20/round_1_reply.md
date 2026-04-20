# GPT Pro Review — Round 1 Reply

**Date received:** 2026-04-20
**Reviewer:** GPT Pro
**Project:** bids_try — M&A extraction pipeline
**Commit reviewed:** aae59af
**Status:** Raw reply as pasted by Austin. Verification findings + implementation spec live in `quality_reports/plans/2026-04-20_gpt-pro-review-implementation-spec.md`.

---

## 1. Executive summary

* **Critical**: the exit clock is not trustworthy yet. `passed_clean` is computed from `ValidatorResult` only, so extractor-generated soft/info flags already present in `output/extractions/*.json` are ignored by state/progress. Example: Zep is marked `passed_clean` with `flag_count: 0`, while its extraction contains soft/info flags on event rows. Fix flag accounting before using any clean-run gate. Evidence: `repo/pipeline.py:203-230`, `repo/pipeline.py:994-1012`, `repo/state/progress.json:3844-3855`, `repo/output/extractions/zep.json:357-367`.
* **Critical**: formal/informal bid classification is under-validated. §P-G2 is the core research variable, but the code accepts any formal or informal trigger for either `bid_type`, and treats `lower != upper` as a range even though the rulebook requires `lower < upper`. This can silently pass wrong formal/informal labels at 392-deal scale. Evidence: `repo/pipeline.py:689-708`, `repo/rules/invariants.md:219-225`, `repo/rules/bids.md:163-181`.
* **Top 3 actions**: first, fix status/flag semantics and make extractor-generated hard/soft flags count; second, resolve the Providence implicit-drop policy by choosing Path A and deleting the contradictory implicit-Drop mandates; third, close rulebook/validator contradictions with small invariant tests before another reference rerun. Evidence for the Providence contradiction: `repo/quality_reports/plans/2026-04-19_stage3-iter7-results.md:20-24`, `repo/rules/events.md:263-275`, `repo/rules/bids.md:492-503`, `repo/rules/schema.md:377-390`.

---

## 2. Answers to the 8 questions

### 1. Architecture fit

**Verified findings.** The broad shape is right: one LLM Extractor for semantic reading, deterministic Python Validator for mechanical invariants, and Austin's manual diff review as the truth-maintenance loop. The project's own epistemology says the SEC filing is ground truth, Alex is calibration not oracle, and `scoring/diff.py` is a human-review aid rather than a grade. That supports this split. Evidence: `PROJECT_NOTES_EXTRACTS.md:17-30`, `PROJECT_NOTES_EXTRACTS.md:32-81`.

The part that is not right is the deferred Adjudicator. It is documented as a scoped LLM subagent in both `SKILL.md` and `pipeline.py`, but `pipeline.finalize()` explicitly does not spawn it. Evidence: `repo/SKILL.md:28-43`, `repo/SKILL.md:66-92`, `repo/pipeline.py:1-23`, `repo/pipeline.py:1213-1228`.

> **Austin's correction post-review:** The Adjudicator is **intentionally**
> orchestrator-spawned (LLM-driven, not Python-driven) and has been used
> throughout iter-6/iter-7 work. GPT Pro saw "no Python spawn path" and
> mislabeled the pattern "ghost code." The implementation spec reframes this
> as T2-H doc-clarity, not deletion.

There is no missing large abstraction. The missing pieces are smaller and more important: a single authoritative flag-accounting/status function, a rulebook/validator contract test suite, and a tiny set of fixture tests for each invariant. The package itself says no tests exist. Evidence: `MANIFEST.md:111`.

**Inference / judgment.** Do not add Planner, Canonicalizer-as-agent, or LLM Validator abstractions. The current deterministic canonicalization in Python is enough; the rulebook already says ordering is Python-enforced, and `_canonicalize_order()` implements that. Evidence: `repo/prompts/extract.md:54`, `repo/pipeline.py:1166-1211`. The simpler design for 9→392 is: Extractor emits raw rows with evidence; Python canonicalizes/order-normalizes; Python validates; Austin manually adjudicates reference diffs and new soft-flag categories.

### 2. Rulebook design

**Verified findings.** The rulebook is appropriately scoped in ambition but too internally inconsistent to serve as a clean validator contract. The core invariant set is sensible: structural evidence checks, date/BidderID discipline, bid-type evidence, and process-level checks. Evidence: `repo/rules/invariants.md:31-71`, `repo/rules/invariants.md:80-169`, `repo/rules/invariants.md:178-229`.

The current contract has concrete gaps and overlaps:

* §P-D5 says a Drop row needs an earlier same-phase engagement row. The implementation does not enforce earlier; it builds an engagement set from all rows and then checks "any witness except self." A later NDA or later Drop can satisfy a prior Drop. Evidence: `repo/rules/invariants.md:108-136`, `repo/pipeline.py:498-574`.
* §P-S3 says the chronologically last event in each phase must be a terminator. The code intentionally implements a different rule: any terminator anywhere in the phase is enough. Evidence: `repo/rules/invariants.md:197-205`, `repo/pipeline.py:854-915`.
* §P-G2 says true range means `bid_value_lower < bid_value_upper`; the code uses `lower != upper`. Evidence: `repo/rules/invariants.md:219-225`, `repo/pipeline.py:689-696`.
* §P-G2 also does not verify that the trigger supports the specific `bid_type`. A row marked formal can pass because its quote contains an informal trigger, and vice versa. Evidence: `repo/pipeline.py:705-708`, `repo/rules/bids.md:106-127`.
* §P-S1 is undermined by mandatory implicit-Drop rules elsewhere. §P-S1 is soft because filings can go silent after NDA, but `rules/events.md` and `rules/bids.md` still say the extractor MUST emit implicit Drop rows for NDA signers with no later activity. Evidence: `repo/rules/invariants.md:178-187`, `repo/rules/events.md:263-275`, `repo/rules/bids.md:492-503`.
* §E2 says joint Bid/Drop rows share the same BidderID; §P-D3 and `_canonicalize_order()` require unique, gap-free, strictly increasing BidderID per row. Both cannot be true. Evidence: `repo/rules/bidders.md:9-31`, `repo/rules/invariants.md:92-104`, `repo/pipeline.py:731-771`, `repo/pipeline.py:1193-1197`.
* §L2 promises phase-boundary rechecks that the validator does not run: no phase 2 without a Terminated/Restarted pair, no phase 0 within six months, and gap checks. Evidence: `repo/rules/events.md:569-600`, `repo/pipeline.py:312-355`.
* §E4 promises alias-registry validation; the implemented §P-R5 only checks that `bidder_name` exists in the registry. Evidence: `repo/rules/bidders.md:173-181`, `repo/pipeline.py:464-477`.
* §H5 says the validator adds `bid_revision_out_of_order`; no such invariant is implemented in `validate()`. Evidence: `repo/rules/bids.md:350-379`, `repo/pipeline.py:312-355`.
* §Scope-2 excludes 425, but the fetcher treats 425 as a primary form type. Evidence: `repo/rules/schema.md:91-105`, `repo/scripts/fetch_filings.py:68-75`.

**Inference / judgment.** The rulebook is not too tight; it is too sprawling in the wrong places. It contains live policy, case-specific migration notes, intended future validator behavior, and implemented invariants mixed together. The fix is to delete contradictory rules, move one-off reference-converter notes out of the live extraction rule path, and add minimal invariant fixtures.

### 3. Overfitting risk

**Verified findings.** The formal/informal trigger table is already too narrow inside the 9-deal set. The iter-7 report says Providence used inference-note path for 15 of 24 bid rows, Penford had zero trigger-path rows, and Stec was the only rerun deal with literal trigger matches. Evidence: `repo/quality_reports/plans/2026-04-19_stage3-iter7-results.md:76-98`. The rulebook itself calls §G1 an MVP baseline and expects more trigger phrases/refined heuristics after a 25-deal language study. Evidence: `repo/rules/bids.md:95-104`, `repo/rules/bids.md:144-147`. The project notes say that 25-deal study is deferred indefinitely. Evidence: `PROJECT_NOTES_EXTRACTS.md:129-131`.

The implementation is riskier than the rulebook because it treats the trigger list as bid-type evidence but not bid-type direction. Evidence: `repo/pipeline.py:705-708`. This is not only long-tail recall risk; it is precision risk.

§D1.a is not overfit. §D1.b is case-derived but acceptable (operative rule is general). §B1 date mapping is underpowered for 392.

The `scripts/build_reference.py` §Q1–§Q5 overrides are fine as one-off reference repairs. The exception is "several = 3 minimum": the prompt claims this is in `rules/bidders.md` §E3, but §E3 defines canonical IDs/aliases/registry, not count semantics. Evidence: `repo/prompts/extract.md:35`, `repo/rules/bidders.md:96-143`.

**Inference / judgment.** The demonstrable failure mode at 392 is not that the LLM cannot handle novel language; it is that the validator may certify weak or wrong classifications as clean. Fix §P-G2 directionality and range logic, then run a small 25-deal language pilot before promoting the full target set.

### 4. The iter-7 Providence soft-flag policy question

**Answer: Path A, with one mandatory cleanup.** Accept iter-7's §R2-strict behavior. Keep §P-S1 as a soft advisory signal. Do not make Providence-style `nda_without_bid_or_drop` softs block the exit clock.

**Verified findings.** Iter-7 improved evidence discipline: it stopped emitting generic catch-all Drops with a shared process quote and left 20 NDA-only bidders as soft flags. Evidence: `repo/quality_reports/plans/2026-04-19_stage3-iter7-results.md:102-135`. §R3 makes per-row source evidence the backbone of manual verification. Path C (mandate catch-all Drops) manufactures per-bidder Drop rows from a generic quote — conflicts with evidence-specificity. Path B (downgrade §P-S1 to info) discards useful signal.

**Required cleanup.** Delete the live implicit-Drop mandates in `rules/events.md` §I1 and `rules/bids.md` §M2. Evidence: `repo/rules/events.md:263-275`, `repo/rules/bids.md:492-503`, `repo/quality_reports/plans/2026-04-19_stage3-iter7-results.md:130-135`.

### 5. Exit-clock semantics

**Verified findings.** The current `passed_clean`/`passed`/`validated` threshold only counts validator-generated flags. `ValidatorResult` stores only `row_flags` and `deal_flags` returned by `validate()`. `summarize()` computes status solely from that result. Existing flags in raw extraction rows are not counted.

This produces visible false cleanliness. Zep is `passed_clean` with `flag_count: 0` while its output has 75 soft + 53 info flags. Medivation is `passed_clean` with `flag_count: 0` while its output has 14 soft + 7 info.

**Recommended semantics.** Hard flags block (extractor or validator). Soft flags should not block by default, but new soft categories or policy-ambiguous softs require Austin adjudication. Info flags never block. `passed_clean` = zero hard + zero soft across combined sources. Info-only = `passed` with notes.

**Three consecutive runs.** Not overengineered. Under-specified. Gate should be: 3 reruns with unchanged rulebook + zero hard flags combined + no unadjudicated new soft categories + Austin's manual diff adjudications complete.

### 6. The deferred Adjudicator

**Original GPT Pro recommendation: delete.** *(Austin's correction applied in spec: keep as orchestrator-spawned pattern, fix docs only.)*

**Verified findings.** The docs describe an Adjudicator path; `pipeline.finalize()` explicitly says it does not spawn adjudicator subagents and expects the orchestrator to mutate flags before finalization. No Python entry-point exists. Per Austin: this is the intended design; the LLM orchestrator spawns Adjudicator subagents when needed, the same way it spawns Extractors.

### 7. `scripts/build_reference.py` bloat

**Verified findings.** The module is bloated as live code, but acceptable as frozen provenance. Largest bloat vectors: module docstring doing archival policy-document work; deal-specific override code inline (Saks/Zep/Medivation); legacy rank map retains deprecated vocabulary; emits `bidder_type.note` outside schema; uses `first_appearance_BidderID` instead of schema's `first_appearance_row_index`; doesn't emit `source_quote`/`source_page` (known asymmetry).

**Recommendation.** Fix the schema mismatches. Label the script explicitly as archival/reference-only. Do not let it drive live extraction rules.

### 8. Named overengineering / dead-weight

* `pipeline.py` Adjudicator references — *(Austin reframed: keep as orchestrator pattern, doc clarity only.)*
* `pipeline._apply_unnamed_nda_promotions()` — 90-line mutation system. Real documented extractor contract, but heavyweight. Needs tests.
* `pipeline._canonicalize_order()` — keep. Deterministic enforcement of §A2/§A3.
* `pipeline._invariant_p_r3()` — too permissive: allows `bid_note is None` for any row.
* `run.py --dry-run` — bypasses `_apply_unnamed_nda_promotions()` + `_canonicalize_order()`.
* `scoring/diff.py` — `rstrip` bug (character-set vs suffix-string confusion) + brittle duplicate-bucket matching.
* `scripts/fetch_filings.py` — drop 425 from `PRIMARY_FORM_TYPES`.
* `state/flags.jsonl` contract stale relative to manifest.

---

## 3. Findings table

| Severity | Status | Finding | Evidence | Action |
|---|---|---|---|---|
| Critical | Verified | `passed_clean` ignores extractor-generated flags. | `pipeline.py:203-230`, `pipeline.py:994-1012`, `state/progress.json:3844-3855`, `output/extractions/zep.json:357-367` | Count combined extractor + validator flags. |
| Critical | Verified | §P-G2 passes wrong formal/informal labels — any trigger supports either `bid_type`. | `pipeline.py:705-708`, `rules/bids.md:106-127, 163-181` | Direction-matched triggers. |
| Critical | Verified | §P-G2 range logic uses `!=` not `<`. | `pipeline.py:689-696`, `rules/invariants.md:219-225` | Numeric `lower < upper`; flag inverted. |
| Critical | Verified | Providence policy conflict: rulebook mandates implicit Drops while §R2/iter-7 discipline favors NDA-only. | `rules/events.md:263-275`, `rules/bids.md:492-503`, `plans/2026-04-19_stage3-iter7-results.md:102-135` | Path A; delete mandate. |
| Major | Verified | Fetcher accepts 425 despite rulebook excluding it. | `scripts/fetch_filings.py:68-75`, `rules/schema.md:91-105` | Remove 425; fail loud. |
| Major | Verified | Joint-bidder BidderID contradicts unique/gap-free invariant. | `rules/bidders.md:20-31`, `rules/invariants.md:92-104`, `pipeline.py:1193-1197` | Unique event IDs; `joint_bidder_members` for jointness. |
| Major | Verified | §P-S3 spec ("last row terminates") vs code ("any in phase"). | `rules/invariants.md:197-205`, `pipeline.py:854-915` | Update spec to match code. |
| Major | Verified | §P-D5 says "earlier row"; code checks any. | `rules/invariants.md:108-136`, `pipeline.py:524-565` | Align (recommend existence-only). |
| Major | Verified | §P-S1 ignores `process_phase` in follow-up search. | `pipeline.py:804-832` | Match on `(name, phase)`. |
| Major | Verified | §L2 promises phase-boundary checks that aren't implemented. | `rules/events.md:592-600`, `pipeline.py:312-355` | Implement `orphan_phase_2` + `stale_prior_too_recent`; delete ill-defined. |
| Major | Verified | §E4 promises alias-registry checks that aren't implemented. | `rules/bidders.md:173-181`, `pipeline.py:464-477` | Add alias checks. |
| Major | Verified | `build_reference.py` JSON not fully schema-conformant. | `scripts/build_reference.py:604-635`, `rules/schema.md:377-390` | Mark as reference-only subset. |
| Major | Verified | `build_reference.py` emits `bidder_type.note` outside schema. | `scripts/build_reference.py:437-469`, `rules/bidders.md:245-264` | Drop field. |
| Major | Verified | `scoring/diff.py` suffix `rstrip` bug + brittle bucket matching. | `scoring/diff.py:75-89, 167-184` | `removesuffix`; cardinality-mismatch entry. |
| Minor | Verified | `run.py --dry-run` bypasses canonicalization. | `run.py:59-75`, `pipeline.py:1232-1253` | Same transform path. |
| Minor | Verified | `state/flags.jsonl` contract under-documented. | `rules/schema.md:311-313` | Add timestamp-filter note. |
| Minor | Verified | `prompts/extract.md` says "two-agent" (stale). | `prompts/extract.md:3` | Rewrite. |
| Minor | Verified | `build_reference.py` rank map retains deprecated vocabulary. | `scripts/build_reference.py:143-173`, `rules/events.md:9-64` | Delete stale labels. |
| Minor | Inference | 25-deal language pilot should reopen before 392 promotion. | `rules/bids.md:144-147`, `PROJECT_NOTES_EXTRACTS.md:129-131` | Narrow §G1/§K2/date-phrase pilot. |

---

## 4. Suggested next-step plan

1. Fix flag/status semantics (very high impact, low-medium difficulty).
2. Resolve Providence Path A; edit rulebook (high, low).
3. Patch §P-G2 directionality + range (very high, low).
4. Reconcile §P-D5, §P-S3, §E2, §L2, §E4, §H5 rulebook↔validator (high, medium).
5. *(Austin reframed: keep Adjudicator as orchestrator pattern; just clarify docs.)*
6. Minimal invariant fixtures (high, medium).
7. Clean reference tooling (medium, low).
8. One full 9-deal reference pass AFTER fixes. Count toward 3-run gate only if hard flags = 0 + new softs adjudicated.

---

## 5. Confidence notes

* **High confidence** on static code/rulebook contradictions, status-accounting bugs, and architecture dead-weight.
* **Medium confidence** on extraction-quality claims (raw SEC filings were excluded from the package).
* **Medium confidence** on reference-converter behavior (raw xlsx/PDF excluded).
* **Low-to-medium confidence** on 392-deal language coverage (requires deferred 25-deal pilot or target-deal sample).

---

_Internal: snapshot_sha=aae59af, round=1, date=2026-04-20, prior_context_uploaded=no_
