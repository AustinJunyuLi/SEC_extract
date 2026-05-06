> Pre-redesign document archived on 2026-05-06. This report is superseded by `docs/superpowers/plans/2026-05-06-deal-graph-review-gate-redesign-implementation.md` and is not active operating guidance.

# Gate Redesign Impact Map

**Date:** 2026-05-06
**Author:** Claude (synthesis of 5 parallel agent scans)
**Purpose:** Map every layer that would be affected by replacing the byte-level stability gate with a human-in-the-loop (HITL) gate, so the gate-philosophy interview lands on a concrete spec.

This doc is the reference for the `/grill-me` interview. Each branch below cites the file:line evidence backing each option.

---

## Executive findings (read first)

**1. Variance is bounded, not pervasive.**
Across 3 clean zep runs the team review observed `review_rows` count 28/34/20, but `estimation_bidder_rows` was identical: admitted=New Mountain Capital, bI=19.25, bF=20.05. Canonical IDs (`actor_id`, `event_id`, `cycle_id`) are content-addressed via `_stable_id` (`pipeline/deal_graph/canonicalize.py:208-216, 86, 242, 279`) and survive re-extraction when claim text matches. The science payload is a stable function of the bidder set. Narration drifts; the bidder ledger doesn't.

**2. 7 of 10 hard flags should not be hard.**
Validation emits 10 flag types (`pipeline/deal_graph/validate.py`):
- **Genuine graph-integrity invariants (keep blocking):** `DG_SCHEMA_VERSION` (line 38-42), `DG_EVENT_LINK_ORPHAN` (125-127), `DG_COVERAGE_RESULT_MISSING` (96-102, only when `coverage_obligations` populated — currently empty in production).
- **Single-claim defects (should be queue items, not blockers):** `evidence_ref_binding_failed` (`orchestrate.py:246-258`, promoted to hard at `validate.py:138-144`), `DG_CLAIM_DISPOSITION_MISSING` (52-58), `DG_CLAIM_EVIDENCE_MISSING` (64-70), `DG_CLAIM_COVERAGE_LINK_MISSING` (72-78), `DG_ROW_EVIDENCE_MISSING` (113-119), `DG_PROJECTION_BLOCKED` (147-151).

Today any single hard flag triggers `orchestrate.py:81-83` to skip both projections — one bad quote → zero review rows for the deal. This is the patching-treadmill source.

**3. The stability proof has a hole that lets fingerprint drift through silently.**
`pipeline/stability.py:756-769` records drift in `compared_attrs` (row_fingerprints, graph_table_counts, claim_type_counts, estimation_fingerprints, bid_value_representation, etc.) but only flips classification on `config_identity` / hard-flag identity / soft-flag presence (lines 682-727). All other recorded drift falls through to `STABLE_FOR_REFERENCE_REVIEW`. The "9 deals happy → second run trips a hard flag" symptom isn't surprising — the proof was always permissive about non-flag drift; the metrics were free-text annotations only.

**4. HITL plumbing is half-built and dormant.**
`judgments` (`pipeline/deal_graph/schema.py:547-551`) and `projection_judgments` (`schema.py:567-571`) tables exist with reasonable column shapes (`subject_table`, `subject_id`, `judgment_type`, `value`, `reason`). Zero writers (`grep -rn "INSERT INTO judgments"` returns nothing). No `judgment_kinds` enum. No CRUD helper in `store.py`. Bones are there — wiring cost only.

**Corrections to the prior team review:**
- `pipeline/core.py` is **326 LOC**, not ~1900. The row-event regime appears already deleted; line numbers cited in the prior synthesis are stale.
- **290 run dirs** across 9 reference slugs (not 23): petsmart-inc 50, mac-gray 39, zep 38, providence-worcester 28, medivation 23, imprivata 26, penford 26, saks 31, stec 29. Zero reaper script.
- `mark_reference_verified.py:73-82` **does** pin `extraction_run_id` to `progress.last_run_id`. The prior "M14: doesn't pin report ↔ extraction" claim is stale.
- `verified` status **is** preserved on re-extract via `core.py:262-272` when new run is `passed`/`passed_clean` and prior record has `verification_report` + `last_verified_by`. This was right in the prior synthesis.

---

## Decision tree (9 branches; → = dependency)

```
1. Acceptance unit         ──┬─→ 4. Correction persistence schema
                             ├─→ 3. Reviewer queue surface
                             └─→ (binds 5, 6)

2. Critical-vs-queue tier  ──┬─→ 6. Severity grading
                             ├─→ 7. Stability-proof redesign
                             └─→ 8. Status taxonomy

5. Confidence flow         (independent — UX/ranking improvement)
9. Retention               (independent — operational hygiene)
```

Branches 1 and 2 are the load-bearing decisions. Everything else cascades.

---

## Layer 1 — Schema (DuckDB + provider JSON)

### Stable IDs that exist today
- `claims.claim_id` (`schema.py:431`); per-family `actor_claims.claim_id`/`event_claims.claim_id`/`bid_claims.claim_id`/`participation_count_claims.claim_id`/`actor_relation_claims.claim_id` (`schema.py:446-475`).
- Canonical row IDs: `actors.actor_id` (`schema.py:503`), `events.event_id` (`schema.py:521`), `actor_relations.relation_id` (`schema.py:512`), `participation_counts.participation_count_id` (`schema.py:535`), `cycles.cycle_id` — all content-addressed via `_stable_id`.
- `row_evidence(row_table, row_id, evidence_id)` join table (`schema.py:541-544`).

### IDs that are NOT stable
- `review_rows.review_row_id` (`schema.py:574`) — derived as `make_id("review_row", slug, run_id, index, row)` at `orchestrate.py:339`. **`run_id` is in the hash**, plus `index` (position-dependent). Rebuilds each run.
- `estimation_bidder_rows.estimation_row_id` — same problem at `orchestrate.py:348`.

### Confidence flow drop points
- Provider emits `confidence: high|medium|low` enum, required on every claim (`response_format.py:139, 173-181, 202-213, 242-255, 278-288, 308-318`).
- Stored on: `claims.confidence` (`schema.py:433`, written `canonicalize.py:124`), `actor_relations.confidence` (`schema.py:516`, written `canonicalize.py:231`).
- **Dropped on:** `actors` (no column), `events` (no column — `canonicalize.py:325` writes onto dict but `store.py:138` filters by table columns and drops it), `participation_counts` (no column).
- **Not in projection:** `project_review.py:14-37` never reads confidence; `project_estimation.py:128-136` hardcodes `"high"` whenever evidence exists.

### Severity is structurally permissive but operationally boolean
- `review_flags.severity TEXT NOT NULL` (`schema.py:556`) — no CHECK constraint, no enum.
- AGENTS.md tier `{hard, soft, info}` is documented but **only `hard` is ever stored.**
- `validate.py:40, 54, 66, 74, 98, 115, 140, 149` emits `severity="hard"` exclusively.
- `orchestrate.py:246-250` writes synthetic `severity="blocking"` for evidence-binding failures; `core.py:151-152` collapses `blocking → hard`.

### Dormant correction-store tables
- `judgments` (`schema.py:546-551`): `judgment_id PK, run_id, deal_id, subject_table, subject_id, judgment_type, value, reason` — all TEXT, no enum.
- `projection_judgments` (`schema.py:566-571`): `projection_judgment_id PK, run_id, projection_unit_id, rule_id, included INTEGER, reason`.
- `projection_units` (`schema.py:560-564`): empty companion table — would need population.
- Zero writers anywhere.

### Top 3 schema choke points
1. **`review_rows` is a JSON blob, not a queryable surface (`schema.py:573-577`).** Per-row acceptance, criticality filtering, confidence-aware ranking, and queue state all want columns. Binds Branches 1, 2, 3, 5.
2. **Confidence drops at the canonical-row boundary (`schema.py:502-538`).** No `confidence` column on `actors`, `events`, `participation_counts`. Any gate using confidence to ration reviewer attention has to thread through three columns.
3. **Severity is structurally free-text but operationally boolean.** Schema is not the binding constraint; the emitters are.

---

## Layer 2 — Prompt + Rulebook + Extraction Input

### Rulebook files (loaded into the model's system prompt)
| File | Purpose |
|---|---|
| `rules/schema.md` | deal_graph_v1 claim-payload contract — output shape, claim-level required fields, per-family fields, provider-forbidden-field blacklist |
| `rules/events.md` | Event ontology — three types (`process`/`bid`/`transaction`), 18-subtype enum, semantic guidance |
| `rules/bidders.md` | Actor units, relation-direction vocabulary, Consortium Doctrine for Mac Gray and PetSmart |
| `rules/bids.md` | Bid claim fields, `bid_stage` enum, value/consideration enums, list of Python-owned projections |
| `rules/dates.md` | ISO date discipline, null for vague phrases, relation-timing |
| `rules/invariants.md` | Python-side reference; **NOT in `EXTRACTOR_RULE_FILES`** (`extract.py:26`) |

### Today's prompt fields (`prompts/extract.md:38`)
Per claim: `claim_type`, `coverage_obligation_id`, `confidence`, `evidence_refs`. No `claim_id`, no `evidence_ref_id`, no criticality tag, no review-attention flag, no rationale field.

### Forbidden-field blacklist (`prompts/extract.md:78-81`, `rules/schema.md:42-45`)
`actor_id`, `event_id`, "canonical ids", source offsets, `BidderID`, `T`, `bI`, `bF`, admitted/dropout outcomes, coverage results, projection rows.

### Confidence semantics (`prompts/extract.md:38, 133-134`)
Closed enum `{high, medium, low}`. Single rule: "If a fact is ambiguous, emit only the supported claim and choose `confidence: low` with a precise quote." **No operational definition for high vs medium.** Whole-claim only — no per-field confidence.

### No prior-corrections channel
`build_messages` (`pipeline/llm/extract.py:240-266`) constructs the user payload from: `slug`, `manifest`, `section`, `pages`, `citation_units`. No `verified_facts`, no `prior_corrections`, no `known_actors`. `EXTRACTOR_INPUT_CONTRACT_VERSION = "citation_units_v1"` (`extract.py:27`) would bump to v2 if added.

### Brittle stability constraints
1. **Exact-substring quote mandate** (`prompts/extract.md:42-70`, `rules/schema.md:38-39`): byte-for-byte text copying with capitalization/punctuation/spacing preserved. Citation-unit drift (multi-page binding, smart-quote handling) silently invalidates yesterday's quotes.
2. **`coverage_obligation_id` granularity** — required on every claim but the rulebook never defines a closed vocabulary. The Python `coverage_obligations` table is empty in production, so this field stabilizes nothing.
3. **Closed `event_subtype` enum** (`rules/events.md:19-38`): borderline events (e.g. exclusivity letter that's also financing) force a single pick → silent run-to-run variance.
4. **No claim_id / evidence_ref_id** → reviewer accept/reject across runs must align by content fingerprint.

### Top 3 prompt choke points
1. **Claim/evidence identity** — lift the `actor_id`/`event_id` ban to introduce a model-emitted stable `claim_id` (filing-derived hash), or keep id-free and have Python fingerprint claims.
2. **Confidence semantics** — graded scale + per-field confidence + operational definitions, or scrap the field entirely and let Python derive priority.
3. **Extractor input contract — prior-corrections channel.** Would require a new top-level user-payload key and prompt language ruling on how the model should treat reviewer-confirmed facts.

---

## Layer 3 — Validation + Stability Proof

### Complete flag inventory

| # | code | severity | emitted at | trigger | points at |
|---|---|---|---|---|---|
| 1 | `DG_SCHEMA_VERSION` | hard | `validate.py:38-42` | snapshot's `schema_version != "deal_graph_v1"` | graph root |
| 2 | `DG_CLAIM_DISPOSITION_MISSING` | hard | `validate.py:52-58` | claim lacks exactly one current disposition | `claims` row |
| 3 | `DG_CLAIM_EVIDENCE_MISSING` | hard | `validate.py:64-70` | supported claim has no `claim_evidence` row | `claims` row |
| 4 | `DG_CLAIM_COVERAGE_LINK_MISSING` | hard | `validate.py:72-78` | supported claim declares obligation but no link | `claims` row |
| 5 | `DG_COVERAGE_RESULT_MISSING` | hard | `validate.py:96-102` | obligation lacks one current `coverage_results` row | `coverage_obligations` row |
| 6 | `DG_ROW_EVIDENCE_MISSING` | hard | `validate.py:113-119` | canonical row has no `row_evidence` link | the row |
| 7 | `DG_EVENT_LINK_ORPHAN` | hard | `validate.py:125-127` | `event_actor_links` references unknown id | the link |
| 8 | promoted `<row.code>` (default `DG_BLOCKING_REVIEW_FLAG`) | hard | `validate.py:138-144` | any `graph.review_flags` with `severity="blocking"`, `current!=False`, `status!="resolved"` | inherited |
| 9 | `DG_PROJECTION_BLOCKED` | hard | `validate.py:147-151` | unresolved blocking flag exists AND projections were emitted | deal-level |
| 10 | `evidence_ref_binding_failed` | "blocking" → hard | `orchestrate.py:246-258` | claim has zero/malformed `evidence_refs` or quote not exact-substring | `claims` row |

### Stability proof (`pipeline/stability.py`)

Produces `target_gate_proof_v2` JSON, classifies each ref as `STABLE_FOR_REFERENCE_REVIEW | UNSTABLE_RULE_OR_VALIDATOR_FIX_NEEDED | UNSTABLE_ARCHITECTURE_ESCALATION_CANDIDATE | INSUFFICIENT_ARCHIVED_RUNS`. Consumes latest `--runs N` (default 3) eligible archived runs per slug.

**Reasonable invariant checks:**
- Manifest schema/identity (`stability.py:289-329`) — required keys, retired-field forbiddance.
- Eligibility — `outcome ∈ {validated, passed, passed_clean}`, `cache_eligible==True`, `cache_used!=True` (`stability.py:641-644`).
- `config_identity` drift (`stability.py:682-692`) — model + reasoning + provider + prompt_hash + schema_hash + rulebook_hash + extractor_contract_version. Strongest signal.
- Hard-flag identity (`stability.py:368-389`) — non-empty hard flags or changing identities flip classification.

**Brittle byte-level checks (the `compared_attrs` block, `stability.py:733-754`):**
Row fingerprints (180-char quote prefix), graph-table counts, event-subtype counts, actor-kind counts, relation-type counts, claim-type counts, claim-disposition counts, coverage-result counts, anonymous/cohort placeholder counts, estimation counts/fingerprints/metrics, date diagnostics, bid-value representation, quote diagnostics, structural-flag counts.

**THE BUG (`stability.py:756-769`):** every metric in `compared_attrs` adds a `reason` annotation but classification is **only** flipped to UNSTABLE for `config_identity` drift, hard flags, or soft flags. After those branches, the function falls through to `STABLE_FOR_REFERENCE_REVIEW` regardless of how much fingerprint or count drift was recorded. The "metric variability observed" line is free-text annotation only.

### Mark-reference-verified preconditions (`scripts/mark_reference_verified.py:54-86`)
- `check_reports` pass (report exists, has section structure, contains literal `Conclusion: VERIFIED`).
- `is_reference=True`.
- `extraction_run_id == progress.last_run_id` (the pin).
- Zero hard flags.

Side effects (line 87-92): writes `status="verified"`, `last_verified_by`, `last_verified_at`, `last_verified_run_id`, `verification_report`.

---

## Layer 4 — Projection + Correction Store

### `output/review_rows/{slug}.jsonl` schema
One row per `(event, event_actor_link)` pair (or one row with null actor when an event has no link). 18 fields including `event_id`, `actor_id`, `actor_label`, `actor_role`, `bid_value`, `bid_value_lower`, `bid_value_upper`, `source_quote`, `source_page`. **No confidence column. No criticality column. No severity column.**

### `output/projections/estimation_bidder_rows/{slug}.jsonl` schema
One row per actor that was a `bid_submitter`. Fields: `actor_id`, `actor_label`, `bI`, `bI_lo`, `bI_hi`, `bF`, `admitted`, `T`, `bid_value_unit`, `consideration_type`, `boundary_event_id`, `formal_boundary` (bool in JSON, int in DuckDB), `dropout_mechanism`, `confidence_min` (hardcoded "high"), `projection_rule_version` (literal `"bidder_cycle_baseline_v1"`).

### Volume per deal (real samples)
- `review_rows`: zep 28, mac-gray 24, petsmart-inc 20.
- `estimation_bidder_rows`: zep 4, mac-gray 4, petsmart-inc 4.

The science tier is a small, stable surface; the review tier is a wide, drifting one.

### Variance breakdown (zep 28-row run)
- 16 process events (advisor contacts, IOIs, NDAs)
- 11 bid events (with bid_value/range)
- 1 transaction event (merger_agreement_executed)
- 2 of those have null actor (no `actor_label` on event)

Variance source: claim-count variance from provider — every bid claim and event claim becomes one canonical event and one review row. Estimation rows collapse all per-actor bids to one row keyed by actor_id, so the bidder set drives stability.

### Correction-store schema (dormant)
Today: `judgments(judgment_id, run_id, deal_id, subject_table, subject_id, judgment_type, value, reason)` — all TEXT, no enum, no writer.

Minimum viable wiring for HITL:
- `judgment_kinds` enum: `{accept, reject, override_value, override_class, defer}`.
- `subject_table ∈ {events, actors, actor_relations, participation_counts, estimation_bidder_rows}`.
- `subject_id` = canonical content-addressed id (stable across re-extracts).
- `value` = JSON (to support typed overrides like `{"bI": 19.50, "field": "bI"}`).
- CRUD helper in `store.py`.
- Read path in `orchestrate.py` so re-extracts honor existing judgments.

### Top finding
**Variance lives entirely in the review tier; the science tier is a stable function of the bidder set.** Any HITL gate should treat these tiers as fundamentally different surfaces.

---

## Layer 5 — State + CLI + Retention

### Status taxonomy

| Status | Reachable today? | Notes |
|---|---|---|
| `pending` | ✅ Yes — 387 of 401 deals (~97%) | seed default at `core.py:251` |
| `validated` | ✅ Path exists; **0 deals currently** | one or more hard flags |
| `passed` | ❌ **NO in practice** | `validate.py` only emits `hard`; soft/info=0 always; `passed` requires `soft+info > 0 and hard==0`. Dead branch. |
| `passed_clean` | ✅ Yes — 5 deals | zero flags |
| `verified` | ✅ Yes — 9 deals (the references) | (a) `mark_reference_verified.py:87`, or (b) preserved on re-extract via `core.py:265-272` |
| `failed` | ✅ Path exists; 0 currently | runtime exception via `mark_failed` |

### Reviewer state mutators today
**Only one:** `scripts/mark_reference_verified.py`. Binary: verified or no-op. No accept/reject/override/defer. No undo path (manual `state/progress.json` edit only).

### Per-deal artifact layout
```
output/extractions/{slug}.json          latest portable graph snapshot
output/audit/{slug}/latest.json         pointer to current run
output/audit/{slug}/runs/{run_id}/      manifest, raw_response, validation, deal_graph.duckdb, deal_graph_v1.json, prompts/, calls.jsonl
output/review_rows/{slug}.jsonl         flat review rows
output/review_csv/{slug}.csv            tabular projection
output/projections/estimation_bidder_rows/{slug}.jsonl
state/progress.json                     deal-level status record
state/flags.jsonl                       append-only flag log
```

### No "deal at a glance" file
Closest is `final_output.deal` block (`orchestrate.py:114-121`): `deal_slug`, `deal_flags`, `last_run`, `last_run_id`, `rulebook_version`, `status`. **No bidder count, no admitted-bidder name, no transaction price, no flag-count breakdown.**

After a 9-deal batch the operator sees one terminal line: `Pool summary: selected=N succeeded=N skipped=N failed=N` (`run_pool.py:779-782`).

### Retention reality
| slug | run_id dirs |
|---|---|
| providence-worcester | 28 |
| medivation | 23 |
| imprivata | 26 |
| zep | 38 |
| petsmart-inc | 50 |
| penford | 26 |
| mac-gray | 39 |
| saks | 31 |
| stec | 29 |
| **total (9 ref slugs)** | **290** |

**No retention/reaper script.** Each `--re-extract` mints a fresh `run_id` directory (~tens of MB, includes `deal_graph.duckdb` plus snapshots). Plus pipeline/run_pool.py:580-714 has no `try/finally` cleanup, so aborted runs leave partial dirs.

### Verified-preservation logic (`core.py:262-272`)
```python
previous = deals[slug]
write_status = status
write_notes = notes
if (
    previous.get("is_reference") is True
    and status in {"passed", "passed_clean"}
    and isinstance(previous.get("verification_report"), str)
    and isinstance(previous.get("last_verified_by"), str)
):
    write_status = "verified"
    write_notes = f"{notes}; prior filing-grounded verification preserved"
```

**Confirmed in live state** (medivation in `state/progress.json:3701-3712`): `status="verified"`, `last_run="2026-05-06T11:22:17.448424Z"`, `last_verified_at="2026-05-05T21:32:50.826944Z"`, `notes="hard=0 soft=0 info=0; prior filing-grounded verification preserved"`.

**Genuine holes:**
1. If re-extract drops to `validated` (any hard flag), guard fails and `verified` is silently overwritten. No warn, no block.
2. Re-uses prior `last_verified_run_id` even though `last_run_id` advances → verification report no longer pinned to current run (intentional per Austin's [LEARN] memory but means a `verified` deal may have `last_run_id != last_verified_run_id`).
3. `passed` status is unreachable, so only `passed_clean` exercises this path.

---

## Top blockers and cheapest wins

**Blockers (must resolve before redesign lands):**
1. Branch 1 (acceptance unit) — binds correction-store schema, queue surface, ID stability.
2. Branch 2 (critical-vs-queue tier) — binds severity grading, stability proof, status taxonomy.

**Cheapest wins (small code change, large redesign payoff):**
- Re-key `review_row_id` and `estimation_row_id` to drop `run_id`/`index` and hash on canonical IDs only (`orchestrate.py:339, 348`). One-file change. Makes IDs stable.
- Promote `evidence_ref_binding_failed` from `severity="hard"` to `severity="soft"` and stop aborting projections in `orchestrate.py:81-83` when only soft flags exist. Makes `passed` reachable for the first time. Eliminates the "one bad quote → zero review rows" cliff.
- Add `confidence` columns to `actors`, `events`, `participation_counts` and thread through `canonicalize.py:243-258, 280-295` and `project_review.py:19-37`. Six-line change. Surfaces confidence in the CSV.

**Dormant assets (no new tables needed):**
- `judgments` and `projection_judgments` tables (`schema.py:546-571`).
- `STRUCTURAL_INFO_CODES` set (`stability.py:43-49`) — anticipates info-tier codes that no emitter currently produces.
- `review_flags.status TEXT` column (`schema.py:556`) — controlled vocabulary `{open, in_review, resolved, dismissed}` would create a queue-state surface inside the existing table.

---

## Open decisions (the grill)

The 9-branch decision tree above. Branches 1 and 2 first; rest cascade.
