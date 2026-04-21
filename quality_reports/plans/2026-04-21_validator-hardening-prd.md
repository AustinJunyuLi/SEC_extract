---
date: 2026-04-21
status: DRAFT
owner: Austin + Claude (implementer)
related:
  - quality_reports/plans/2026-04-20_pipeline-comparison.md
  - quality_reports/plans/2026-04-21_three-way-comparison.md
supersedes_source_repo: /Users/austinli/Projects/bids_pipeline (frozen 2026-04-21; remote github.com/AustinJunyuLi/bids_pipeline)
target_repo: /Users/austinli/bids_try (remote github.com/AustinJunyuLi/SEC_extract, created 2026-04-21)
---

# PRD: Validator Hardening — Cherry-picks from `bids_pipeline`

## 1. Introduction

`bids_pipeline` is being frozen. Before it goes dormant, we transplant six specific capabilities into `bids_try` (now the `SEC_extract` repo) to fortify the pipeline before the 392-deal target push. Each capability is hard-earned in `bids_pipeline` — recent atomic commits (especially the 2026-04-17 boundary-map sprint) encode decisions we do not want to rediscover.

The eight user stories below are ordered by **ascending risk and effort**. The first four are pure wins with zero behavioral change. Stories 5–8 accept a controlled philosophical compromise: `bids_try` keeps its flag-only stance for `source == "llm"` rows while allowing explicit code-synthesized rows (`source == "code_gap_fill"` / `"code_cohort_expansion"`) that are transparent, auditable, and traceable in `flags.jsonl`.

> **POLICY: ZERO BACKWARD COMPATIBILITY.** See **NG-10** in §5. No shims, no auto-migration, no legacy codepaths, no `@deprecated` stubs, no fallback reads of pre-PRD output. When a schema or rule changes, old data is regenerated, stale files are deleted in the same commit, and replaced code is removed — not commented out. Git history is the only compatibility record we keep. Every US below is written against this policy.

**This PRD is not a plan.** Each user story will spawn its own plan document under `quality_reports/plans/` when implementation begins.

## 2. Goals

- **G1.** Preserve the exact Extractor JSON for every deal by saving it before any canonicalization. (US-001)
- **G2.** Catch LLM-hallucinated merger prices at zero LLM cost via an independent regex cross-check, closing a gap our `source_quote` NFKC invariant cannot cover. (US-002)
- **G3.** Ship an xlsx projector so extractions land in Alex's 35-column workbook format without a manual CSV step. (US-003)
- **G4.** Name the invariant-vs-semantic authority rule as first-class doctrine in `rules/invariants.md` so future rule additions declare which side they're on. (US-004)
- **G5.** Close the rule gaps discovered in `bids_pipeline`'s 2026-04-17 boundary-map sprint (Clusters 1/2/3/4/5/6/7/8) — five adjustments to extraction / cueing / prompt behavior. (US-005)
- **G6.** Introduce an event-level `source` field (`llm` | `code_gap_fill` | `code_cohort_expansion` | `code_promotion`) so code-synthesized rows are transparent, and relax §P-R2 (`source_quote` NFKC substring) to fire only on `source == "llm"` rows. (US-006)
- **G7.** Port cohort expansion logic: detect aggregate NDA rows ("15 financial buyers") and expand to atomic `bidder_1..N` rows, with named-bidder promotion into cohort slots. (US-007)
- **G8.** Port NDA gap-fill: synthesize a `Drop` row with `source = "code_gap_fill"` for every NDA signer whose final segment has no closure event by end of Background section. Goal: collapse `providence-worcester`'s 20 open soft flags to 0. (US-008)

## 3. User Stories

### US-001: Save raw Extractor JSON before any processing

**Description:** As a researcher, I want the Extractor's original JSON preserved on disk before any canonicalization or flag merging runs, so that if a bug in `_canonicalize_order` or `_apply_unnamed_nda_promotions` corrupts a row, I can reconstruct what the LLM actually emitted.

**Context:** `bids_pipeline` writes `{slug}_raw.json`, `{slug}_pass2_input.json`, and `{slug}.json` per deal. `bids_try` writes only the canonicalized final. Cheapest insurance policy in the entire PRD.

**Acceptance Criteria:**
- [ ] `pipeline.finalize()` writes `output/extractions/{slug}_raw.json` as its first disk-touching action, before any mutation of `raw_extraction`.
- [ ] The file contains the literal JSON the Extractor emitted, not the canonicalized or flag-merged form.
- [ ] A new test `tests/test_pipeline_runtime.py::test_raw_extraction_preserved` asserts the file exists after `finalize()` and that its content matches the input to `finalize()`.
- [ ] `.gitignore` already excludes `output/extractions/*.json`; no change needed.
- [ ] `pytest tests/` passes green.

**Effort:** ~15 minutes.
**Risk:** Zero.

---

### US-002: Regex merger-price cross-check as hard invariant §P-R6

**Description:** As a validator, I want every `bid_note == "Executed"` row's price to appear in an independent regex scan of the filing text, so that LLM-hallucinated prices are caught even when the `source_quote` NFKC check passes (e.g., LLM quotes a real sentence but attaches a wrong number).

**Context:** `bids_pipeline/pipeline/preprocess.py::extract_prices_regex` at line 699, with `_LOCAL_PRICE_PATTERNS` at line 630 (9 patterns covering ranges, per-share, cash trailers). Threshold rejection via `_LOCAL_PRICE_THRESHOLD_CONTEXT` (line 619); component-tail rejection via `_LOCAL_PRICE_COMPONENT_TAIL` (line 623). Recently broadened in Cluster 3 of the 2026-04-17 boundary-map sprint.

**Acceptance Criteria:**
- [ ] New module `pipeline_price_scan.py` (or extension of `pipeline.py`) contains ported `extract_prices_regex(text) -> set[float]` and the 9 patterns.
- [ ] Threshold rejectors (`at least`, `minimum of`, `no less than`, `floor of`) and component-tail rejectors (`$X plus $Y in stock`) are preserved.
- [ ] New invariant `§P-R6` added to `rules/invariants.md`: "For every `bid_note == 'Executed'` row with a populated price, the price must appear in `extract_prices_regex(filing_raw_text)`. Hard-fail otherwise."
- [ ] Validator emits `§P-R6` hard flag when check fails; logged to `flags.jsonl` with `{code: "P-R6", severity: "hard", extracted_price: X, regex_prices: [...]}`.
- [ ] For non-Executed priced rows, mismatch fires a **soft** `§P-R6-soft` flag (advisory; narrative vs. regex prices can legitimately diverge mid-process).
- [ ] New fixture tests in `tests/test_invariants.py` covering: (a) Executed price present in regex → pass; (b) Executed price absent → hard fail; (c) threshold phrase "at least $X" → not matched; (d) component tail "$X in cash plus $Y in stock" → not matched.
- [ ] All 9 reference deals re-run clean after the invariant lands.

**Effort:** 1–2 days.
**Risk:** Low. If a reference deal regresses, we've caught an actual LLM price error (feature, not bug).

---

### US-003: xlsx projector for Alex's 35-column workbook format

**Description:** As a researcher, I want a single command to project validated extractions into Alex's xlsx layout so that the handoff to him is one file, styled, frozen-pane'd, and column-aligned with `deal_details_Alex_2026.xlsx`.

**Context:** `bids_pipeline/pipeline/compile.py` (225 LOC total, fully self-contained). 35 column definitions at lines 26–62. Projector `extraction_to_rows()` at line 76. Main entry `compile_to_xlsx()` at line 122. Uses `openpyxl`. Fails closed via `_require_projection_ready()` (line 65).

**Key adaptation:** `bids_pipeline` uses flat booleans (`bidder_type_financial`, `bidder_type_strategic`, `bidder_type_mixed`, `bidder_type_nonUS`), `bids_try` uses nested `bidder_type: {base: "s" | "f" | "mixed", non_us: bool, public: bool}`. Write a flattener.

**Acceptance Criteria:**
- [ ] New module `scoring/compile_xlsx.py` with ported + adapted projector.
- [ ] 35 `COLUMNS` list matching Alex's exact order and widths.
- [ ] `flatten_bidder_type(event) -> dict` maps nested → flat.
- [ ] Projector outputs `None` / empty string for downstream-merge columns (`gvkeyT`, `gvkeyA`, `DealNumber`) — not fabricated values.
- [ ] `compile_to_xlsx(extractions: list[dict], output_path: str, urls: dict | None) -> int` returns row count.
- [ ] Rejects raw / partial JSON via a projection-readiness check equivalent to `bids_pipeline/pipeline/schema.py::projection_readiness_errors`.
- [ ] Smoke test `tests/test_compile_xlsx.py`: load one reference deal's `{slug}.json`, project, assert output xlsx has expected row count and first row's `TargetName` / `BidderID` columns populated.
- [ ] 9-deal smoke run: produces one `output/all_9_reference.xlsx` matching Alex's column order (visual eyeball comparison acceptable for this PRD).
- [ ] Optional columns for `source_quote` / `source_page` — **deferred to open question** (see §9).

**Effort:** 1–2 days.
**Risk:** Low.

---

### US-004: Phase A authority rule articulated in `rules/invariants.md`

**Description:** As a rulebook author, I want the invariant-vs-semantic distinction named and codified as the organizing principle of `rules/invariants.md`, so that future contributors (human or LLM subagent) declare which side each new check falls on.

**Context:** `bids_pipeline/CLAUDE.md` "Authority rule (invariant vs semantic)" subsection articulates this. Hard-earned after the imprivata "ten of the 11 parties declined" false-positive forced the authority-rule PRD in `bids_pipeline`. `bids_try`'s severity tiers (hard/soft/info) implicitly embody it but do not name it.

**Acceptance Criteria:**
- [ ] New section prepended to `rules/invariants.md` titled "Authority rule: invariant vs semantic".
- [ ] Body includes the literal rule statement: "Code may block on invariants. Code may not block on semantic interpretation of prose."
- [ ] Defines *invariant* as a JSON-structural property verifiable without re-reading filing prose.
- [ ] Defines *semantic* as any check requiring prose interpretation (entity counts, phase-boundary inference, cue matching on narrative language).
- [ ] Lists every existing §P-* check and declares which side: invariant (hard-blocking) vs semantic (soft-flagging).
- [ ] Commits that any new §P-* addition must declare its side explicitly.
- [ ] Same paragraph mirrored into `SKILL.md` under "Validator philosophy" so Extractor and Adjudicator subagents see it on every run.
- [ ] No code change in this US.

**Effort:** Half day (reading + writing).
**Risk:** Zero.

---

### US-005: Rules audit from `bids_pipeline`'s 2026-04-17 boundary-map sprint

**Description:** As a rulebook maintainer, I want to adopt the five rule changes from `bids_pipeline`'s boundary-map implementation (Clusters 1/2/3/4/5/6/7/8) that apply to our rulebook, so we close gaps discovered against a 30-deal stratified sample without rerunning that study.

**Context:** `bids_pipeline/docs/boundary_map_implementation_amendment.md` (landed 2026-04-17, commits `929de8f`..`cea23bb`). The per-change acceptance rationale is in `bids_pipeline/debug/2026-04-17/boundary-map-implementation/ACCEPTANCE_LOG.md`. Cluster 3 (merger-price regex) is already covered by US-002; this US covers the other four clusters.

**Acceptance Criteria:**
- [ ] Read `bids_pipeline/docs/boundary_map_implementation_amendment.md` and `.../ACCEPTANCE_LOG.md`. Summary notes filed at `quality_reports/plans/2026-04-21_boundary-map-audit-notes.md`.
- [ ] **(5a) Bare "best and final" does not fire phase-extension:** Update `rules/events.md` §K (phase labels) to state that `Final Round Ext` / `Final Round Ext Ann` requires explicit deadline language (`deadline ... extended`, `requested additional time`). Bare "best and final" is pressure rhetoric, not a process step. Add fixture to `test_invariants.py` or similar.
- [ ] **(5b) `DropTarget` with comparator clue → review signal:** `rules/events.md` §C (cessation lanes) clarifies that a `DropTarget` row carrying comparator evidence (below-merger / below-informal / at-informal terminal price) must surface a `comparator_on_droptarget` review flag rather than auto-flipping to a Drop subtype. Add to §P-* as new soft invariant.
- [ ] **(5c) Soft-resolution cue patterns:** Add to `rules/events.md` §C: the phrases `would not be moving forward`, `not interested in pursuing`, `ceased working on the transaction`, `will not be submitting a bid`, `elected not to proceed` are **soft resolution cues** — review-only routing, never auto-type an exit row. Extractor prompt updated accordingly.
- [ ] **(5d) Partial / PIPE / status-only pivots do NOT auto-type exit:** Update `prompts/extract.md` with negative examples (partial-business pivot, PIPE pivot, thin status/exclusivity fence) and the one positive example (soft resolution + explicit acquisition-path abandonment → typed exit).
- [ ] For each of (5a)–(5d), regression test against all 9 reference deals. Extraction counts should not change (by design these are negative-rule clarifications that prevent over-extraction).

**Effort:** 1 day (reading + doc edits + regression verification).
**Risk:** Low-medium. May cause small shifts in reference-deal counts; any shift must be adjudicated before landing.

---

### US-006: Add `source` field to event schema (provenance plumbing)

**Description:** As a validator, I need every event to carry a `source` field declaring whether it came from the LLM or was synthesized by code, so that `bids_try` can accept code-synthesized rows (US-007 and US-008) without breaking flag-only auditability.

**Context:** Prerequisite for US-007 and US-008. Also independently useful: the Adjudicator's dismissals, the named-bidder promotion pass, and any future code transforms all gain an auditable label.

**Acceptance Criteria:**
- [ ] `rules/schema.md` §R1 adds `source: "llm" | "code_gap_fill" | "code_cohort_expansion" | "code_promotion" | "adjudicator_verdict"` as a **required** event-level field.
- [ ] Extractor MUST emit `source: "llm"` on every event (`prompts/extract.md` updated to require it). Validator hard-rejects events missing the field (no backfill, no shim — per NG-10).
- [ ] Validator invariant §P-R2 (`source_quote` NFKC substring check) relaxed: fires only when `source == "llm"`. Rows with `source != "llm"` may carry a synthesized quote like `"[synthesized: <brief reason>]"` that is NOT subject to the NFKC check.
- [ ] `flags.jsonl` schema extended: each flag row includes `event_source` field alongside existing `deal_slug`, `row_index`, `code`, `severity`.
- [ ] New test in `test_invariants.py`: event with `source = "code_gap_fill"` and a bracketed synthesized quote passes validation.
- [ ] **Pre-PRD extractions are regenerated, not grandfathered.** All 9 reference deals are re-run after this US lands; their JSON is replaced. No auto-backfill path in `validate()`. Any stale extraction file in `output/extractions/` is deleted in this commit.
- [ ] Extractor prompt updated; smoke-run one reference deal confirms `source: "llm"` appears on every emitted event.

**Effort:** 1 day.
**Risk:** Medium — schema change touches every event. All downstream consumers (diff tool, xlsx projector, flags.jsonl reader) must be updated in the same commit. No legacy path.

---

### US-007: Cohort expansion (aggregate NDA → atomic rows)

**Description:** As a validator, I want aggregate NDA rows like "15 financial buyers signed confidentiality agreements" to be expanded into 15 atomic rows (`bidder_1`..`bidder_15` or a similar naming scheme), with named-bidder promotion when a specific name later appears, so that deals with cohort-style NDAs are closed-out correctly without LLM over-emission.

**Context:** `bids_pipeline/pipeline/cohorts.py` (599 LOC). Core entry points: `detect_cohort_anchors(events) -> list[Cohort]` at line 211, `expand_cohort_to_atomic_rows(events, cohorts) -> (new_events, log)` at line 265. `Cohort` dataclass at line 91. `_is_aggregate_name` at line 140. Bidder-type compatibility check at `_bidder_type_compatible` line 179.

**Depends on:** US-006 (needs `source = "code_cohort_expansion"`).

**Acceptance Criteria:**
- [ ] New module `pipeline_cohorts.py` with ported subset: `Cohort` dataclass, `detect_cohort_anchors`, `expand_cohort_to_atomic_rows`, `_is_aggregate_name`, `_parse_count`, `_parse_type`, `_bidder_type_compatible`.
- [ ] Aggregate phrase regex from `bids_pipeline/pipeline/cohorts.py` line 53 ported literally (ensures parity on patterns like "fifteen financial buyers", "the 15 parties", etc.).
- [ ] Expansion runs after Extractor emits, before `validate()`. Each synthesized atomic row carries `source = "code_cohort_expansion"`, `bidder_name = "bidder_N"` (or equivalent naming), `source_quote = "[synthesized: atomic slot of <cohort_id> with count=<N>]"`, `source_page` inherited from the anchor row.
- [ ] Named-bidder promotion: if a later `role == "bidder"` event matches by type/date to an existing cohort slot, promote the named bidder into that slot (update `bidder_name`, keep `source = "code_cohort_expansion"` with a promotion timestamp in `normalization_log`).
- [ ] `normalization_log` records every expansion and promotion with `{type: "cohort_expansion", cohort_id, count, anchor_event_index}` / `{type: "cohort_promotion", cohort_id, slot_index, from_name, to_name}`.
- [ ] New test fixture: aggregate NDA row → N atomic rows, each with correct `source`, synthesized quote, and `bidder_type` inheritance.
- [ ] New test fixture: aggregate NDA + later named bidder → promotion fills a slot correctly.
- [ ] 9-deal regression: no reference deal should have a net change in *final* bidder count (atomic expansion is internally visible but the final `state/progress.json` flag count should only drop, not rise).

**Effort:** 2–3 days.
**Risk:** Medium. Expansion timing matters — must run before cues mine `bidder_name` patterns, else cues fire on the aggregate text, not the atomics.

---

### US-008: NDA gap-fill for unclosed final segments

**Description:** As a validator, I want every NDA signer whose final process segment has no closure event (Drop, DropTarget, Executed) to receive a synthesized Drop row with `source = "code_gap_fill"`, so that `providence-worcester`'s 20 open `nda_without_bid_or_drop` soft flags collapse to 0 while remaining fully auditable.

**Context:** `bids_pipeline/pipeline/validate.py::gapfill_nda_signers` at line 1651 (~60 LOC). The gap-fill runs after cohort expansion so atomic rows are the unit of closure, not aggregates. `source = "code_gap_fill"` appears at line 1703 and is referenced at line 2021 for downstream filtering.

**Depends on:** US-006 (needs `source` field), US-007 (cohort expansion must run first so gap-fill sees atomics).

**Acceptance Criteria:**
- [ ] New function `gapfill_nda_signers(events) -> events` in `pipeline.py` or a new module.
- [ ] For each event with `role == "bidder"` and `bid_note == "NDA"` (or equivalent), if no subsequent closure event (`Drop`, `DropTarget`, `Executed`) exists in the same process phase before end of events list, synthesize a `Drop` row with: `source = "code_gap_fill"`, `bid_note = "Drop"`, `bidder_id` / `bidder_name` inherited, `bid_date_precise = null`, `bid_date_rough = "end of process"` or equivalent, `source_quote = "[synthesized: NDA signer with no explicit closure by end of Background section]"`, `source_page = null` or inherited from NDA anchor.
- [ ] Gap-fill runs after cohort expansion (US-007) and named-bidder promotion, before final validation.
- [ ] `normalization_log` records each gap-fill: `{type: "gap_fill", bidder_id, nda_row_index, synthesized_drop_row_index}`.
- [ ] `flags.jsonl` records an **info-level** `§P-S1-gap-fill-synthesized` flag for each synthesized row so researcher sees count without treating them as errors.
- [ ] `§P-S1` (`nda_without_bid_or_drop` soft flag) no longer fires on rows that have a synthesized closure — because they now have a closure.
- [ ] `providence-worcester` regression: soft-flag count drops from 20 to 0; deal moves from `passed` to `passed_clean`.
- [ ] All other 8 reference deals re-run green (no new hard flags introduced).
- [ ] New test fixture: synthetic deal with NDA + no closure → gap-fill synthesizes a Drop with correct `source`.
- [ ] New test fixture: synthetic deal with NDA + explicit Drop → gap-fill does nothing.
- [ ] New test fixture: cohort aggregate NDA + joint aggregate Drop → gap-fill does nothing (joint closure covered). Cohort-expanded atomics + no closure on 3 of 15 → gap-fill synthesizes 3 Drops.

**Effort:** 2 days (after US-006 and US-007).
**Risk:** Medium-high. This is the philosophical compromise. Mitigations: `source = "code_gap_fill"` is transparent, every synthesized row is in `flags.jsonl`, every synthesized row can be opted-out by rolling back US-006 + US-008 together.

## 4. Functional Requirements

- **FR-1:** `pipeline.finalize()` MUST write `output/extractions/{slug}_raw.json` as its first disk-touching action. (US-001)
- **FR-2:** A new invariant `§P-R6` MUST be defined: for every `Executed` row, the price must appear in an independent regex scan of the filing raw text. Hard-fail on miss for Executed rows; soft-fail for non-Executed priced rows. (US-002)
- **FR-3:** A new module `scoring/compile_xlsx.py` MUST project validated extraction JSON into a 35-column xlsx matching Alex's `deal_details_Alex_2026.xlsx` layout, including a `bidder_type` flattener from the nested `bids_try` representation to the flat `bidder_type_financial` / `bidder_type_strategic` / `bidder_type_mixed` / `bidder_type_nonUS` booleans. (US-003)
- **FR-4:** `rules/invariants.md` MUST open with an "Authority rule: invariant vs semantic" section that names the rule and classifies every existing §P-* check. (US-004)
- **FR-5:** `rules/events.md` MUST be updated per Clusters 1/2 (bare "best and final"), 4 (comparator on DropTarget), 5/7 (soft-resolution cues); `prompts/extract.md` MUST be updated per Cluster 5/7/8 (partial / PIPE / status-only vs typed exit). (US-005)
- **FR-6:** The event schema MUST add a required `source` field with closed vocabulary. Validator invariant §P-R2 (`source_quote` NFKC check) MUST be relaxed to apply only when `source == "llm"`. (US-006)
- **FR-7:** Aggregate NDA rows detected by a ported `detect_cohort_anchors` function MUST be expanded into atomic rows with `source = "code_cohort_expansion"`, before validation runs. Named-bidder promotion into cohort slots MUST be supported. (US-007)
- **FR-8:** NDA signers with no closure event by end of events list MUST receive a synthesized `Drop` row with `source = "code_gap_fill"`. Gap-fill runs after cohort expansion. (US-008)
- **FR-9:** Every code-synthesized row (cohort expansion, gap-fill, future additions) MUST appear in `flags.jsonl` with an info-level entry so the researcher can audit what code added.

## 5. Non-Goals (Out of Scope)

- **NG-1:** No porting of `bids_pipeline/pipeline/orchestrator.py` direct-SDK architecture. `bids_try` keeps the Claude Code subagent orchestration model.
- **NG-2:** No porting of `bids_pipeline/pipeline/validate.py::apply_formality_classification`. Validator-owned formality recompute that *overwrites* LLM-emitted `bid_type` contradicts `bids_try`'s flag-only philosophy for LLM output.
- **NG-3:** No porting of `bids_pipeline/pipeline/validate.py::apply_drop_subtype_classification`. Same reason as NG-2.
- **NG-4:** No porting of conditional pass-2 architecture. `bids_try`'s scoped Adjudicator for soft flags is the functional equivalent done more cleanly.
- **NG-5:** No new schema fields beyond `source`. In particular, no porting of `marked_up_MA_received`, `drop_has_terminal_price`, `aggregate_nda_count`, `drop_terminal_comparator` as structured fields — the extraction prompt already captures equivalent evidence via `source_quote`.
- **NG-6:** No change to the Extractor's subagent invocation model. Filing text is still read lazily via the subagent's Read tool, not stuffed into the prompt.
- **NG-7:** No change to the reference-deal gate. The 3-unchanged-rulebook-clean-runs requirement persists; this hardening PR resets the clock by design (expected; acceptable).
- **NG-8:** No migration of `bids_pipeline` git history into `SEC_extract`. `bids_pipeline` stays at github.com/AustinJunyuLi/bids_pipeline as a frozen archive.
- **NG-9:** No batch rerun of the 392 target deals in this PRD. Reference set only.
- **NG-10: NO BACKWARD COMPATIBILITY.** No deprecation shims, no auto-migration for old extraction JSON, no fallback codepaths that read pre-PRD output, no `try: new; except: old` guards, no feature flags that gate the new behavior off. When a schema field is added (e.g., `source` in US-006), every consumer fails loudly on missing field — no silent backfill. When a rule changes (e.g., US-005 cluster adjustments), old extractions are **regenerated**, not grandfathered. When a function is replaced (e.g., new `gapfill_nda_signers` in US-008), the old code path is **deleted**, not commented out or `@deprecated`. If a stale file references removed behavior, the stale file is deleted in the same commit. Git history is the only compatibility record we keep.

## 6. Design Considerations

### 6.1 Ordering discipline
Each US lands as an **atomic commit** on a dedicated branch `hardening-from-bids-pipeline-2026-04-21` off `main`. No multi-US commits. Each commit passes `pytest tests/` green before the next begins.

### 6.2 Reference-deal re-run after each US
After every US lands, re-run the 9 reference deals and diff against the pre-US baseline. Any shift in flag counts, row counts, or `state/progress.json` status must be adjudicated and recorded in the corresponding plan doc before the next US begins.

### 6.3 Rollback plan
- US-001: revert the commit. No data migration needed.
- US-002: revert the commit. Drop the new test fixtures. Re-run references.
- US-003: revert. No schema impact.
- US-004: revert. No code impact.
- US-005: revert rule changes. Re-run references.
- US-006/007/008: revert as a block (all three tied together). Every synthesized row in stored extractions becomes the LLM's responsibility again — but synthesized rows have `source != "llm"` so they can be filtered-out cleanly if needed.

### 6.4 `source_quote` policy for synthesized rows
Synthesized rows carry a quote of the form `"[synthesized: <reason>]"` so the workbook projector and downstream consumers never hit `None` on the evidence column. The bracketed form is unambiguous and greppable.

### 6.5 Alex's workbook parity
US-003 column order must match `reference/deal_details_Alex_2026.xlsx` exactly. If any column name differs between `bids_pipeline` and Alex's actual xlsx, Alex's version wins.

## 7. Technical Considerations

### 7.1 Key bids_pipeline file anchors

| bids_pipeline path | LOC | Function / symbol | Use for |
|---|---|---|---|
| `pipeline/compile.py` | 225 | `COLUMNS`, `extraction_to_rows`, `compile_to_xlsx`, `_require_projection_ready` | US-003 |
| `pipeline/preprocess.py:619-699` | ~80 | `_LOCAL_PRICE_PATTERNS`, `_LOCAL_PRICE_THRESHOLD_CONTEXT`, `_LOCAL_PRICE_COMPONENT_TAIL`, `extract_prices_regex` | US-002 |
| `pipeline/cohorts.py` | 599 | `Cohort`, `detect_cohort_anchors`, `expand_cohort_to_atomic_rows`, `_is_aggregate_name`, `_bidder_type_compatible` | US-007 |
| `pipeline/validate.py:1651-1720` | ~70 | `gapfill_nda_signers` | US-008 |
| `pipeline/schema.py:projection_readiness_errors` | ~30 | Projection-readiness check | US-003 |
| `CLAUDE.md` "Authority rule" subsection | — | Doctrine text | US-004 |
| `docs/boundary_map_implementation_amendment.md` | 75 | Cluster descriptions | US-005 |
| `debug/2026-04-17/boundary-map-implementation/ACCEPTANCE_LOG.md` | varies | Per-cluster rationale | US-005 |

### 7.2 Dependencies between user stories

```
US-001 (raw save)           ─────────── independent
US-002 (regex price §P-R6)  ─────────── independent
US-003 (xlsx projector)     ─────────── independent
US-004 (authority rule)     ─────────── independent
US-005 (rules audit)        ─────────── independent (but reference-deal re-run after)
US-006 (source field)       ─────────── prerequisite for US-007, US-008
US-007 (cohort expansion)   ─────────── depends on US-006
US-008 (NDA gap-fill)       ─────────── depends on US-006, US-007
```

Recommended sequence: **US-001 → US-004 → US-002 → US-003 → US-005 → US-006 → US-007 → US-008**.

### 7.3 Test strategy

Each US adds fixture tests parametric-style like `bids_try`'s existing `tests/test_invariants.py`. No LLM mocking needed — validator is the entire boundary.

### 7.4 `state/progress.json` ledger impact

US-006–US-008 introduce synthesized rows. `state/progress.json` is unaffected by design: `passed` / `passed_clean` / `validated` status is computed from `flags.jsonl`'s hard-flag count, which does not change (synthesized rows reduce soft flags, never create hard ones). The ledger itself is rebuilt from scratch at first run after the PRD lands — pre-PRD entries are discarded (per NG-10).

### 7.5 OPEN: `source_quote` / `source_page` in the xlsx projector

`bids_pipeline/compile.py` has no citation columns (bids_pipeline has no citation fields). `bids_try`'s extractions carry `source_quote` and `source_page` per row. Three options:
- **(a)** Drop them at projection time so the workbook matches Alex's exact 35 columns.
- **(b)** Append as columns 36–37 so Alex can spot-check each row.
- **(c)** Emit two xlsx files: one pristine (35 cols, for Alex) and one audit (37 cols, for us).

Recommend (c); confirm with user before US-003 lands.

## 8. Success Metrics

- **M1.** `providence-worcester` soft-flag count drops from 20 to 0 after US-008 lands.
- **M2.** All 9 reference deals at `passed` or `passed_clean` after the full PRD lands (no deal regresses from `passed_clean` → `passed` or worse).
- **M3.** Zero LLM tokens spent on price cross-checks — the regex scan runs in < 50ms per deal.
- **M4.** xlsx projector produces a file that passes visual parity-check against `deal_details_Alex_2026.xlsx` on a smoke deal within 1 review round.
- **M5.** `bids_try/tests/` passes green after every US commit (241+ tests, zero regressions).
- **M6.** `rules/invariants.md` `wc -l` increases by ~50 lines (authority rule + §P-R6) but adds zero new hard `must_repair` checks beyond §P-R6.
- **M7.** Clock reset: 3-unchanged-rulebook-clean-runs gate resets once (acceptable). Clock does not reset a second time within this PRD.

## 9. Open Questions

- **OQ-1** (for US-003): Citation columns in xlsx — drop, append, or dual-file? (See §7.5.)
- **OQ-2** (for US-005): `bids_pipeline`'s Cluster 4 (`comparator_on_droptarget`) assumes a `drop_terminal_comparator` structured field which `bids_try` does not have. Do we (a) add that field to the schema, or (b) have the cue search `source_quote` text for comparator phrases directly?
- **OQ-3** (for US-005): Are any of `bids_try`'s existing rules *contradicted* by the boundary-map adjustments? If so, which version wins — Alex + research decisions in `bids_try` or the empirical finding in `bids_pipeline`?
- **OQ-4** (for US-007): Atomic naming convention. `bids_pipeline` uses `FIN-1` / `FIN-2` / `STR-1` cohort IDs internally but row-level `bidder_name = "bidder_N"` at projection time. Does `bids_try` prefer `unnamed_financial_1` / `unnamed_strategic_1` / ... to match `rules/bidders.md`'s existing naming conventions?
- **OQ-5** (for US-008): If a cohort-expanded atomic row has NO evidence at all (neither NDA signing nor subsequent closure), gap-fill still runs on the NDA anchor but synthesizes a Drop with `bid_date_rough = "end of process"`. Is that correct, or should we instead emit a special `nda_synthesized_and_closed` event type for researcher review? Current recommendation: stick with Drop for simplicity; revisit if noise emerges.
- **OQ-6** (meta): Should the 2026-04-21 three-way comparison (`quality_reports/comparisons/`) complete before any US lands, so the rule adjustments it surfaces can be folded into US-005? Current recommendation: yes, wait for the three-way results before starting US-005 specifically.
- **OQ-7** (meta): Who owns the PRD rollout — `SEC_extract` main branch directly, or a dedicated long-lived branch that merges back only after all 8 USs complete?

---

**End of PRD.**

**Next step:** Austin reviews, resolves OQ-1 through OQ-7 (at least OQ-1, OQ-4, OQ-6, OQ-7 before implementation), then authorizes Claude to begin US-001. Each US produces its own plan doc under `quality_reports/plans/` at implementation time.
