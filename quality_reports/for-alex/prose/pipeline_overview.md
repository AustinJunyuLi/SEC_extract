<!--
Source narrative for pipeline_overview.html. Plain Markdown.
Figure placeholders: {{figure:figure_id}}  — substituted by build_alex_reports.py
Glossary terms get auto-wrapped in <span class="term"> by the builder.
Section IDs are derived from heading text via slugify.
-->

> **How to read this document.** This is a complete walkthrough of the pipeline that converts an SEC merger filing into the rows of `alex_event_ledger_ref9_plus_targets5.csv`. It is written for a finance/legal expert who is fluent in the substance of bidding processes but does not write Python. Every technical term is either common (JSON, CSV, regex, SQL) or defined on first use. A companion document, **`csv_user_manual.html`**, is the reference for every column and every coded value in the CSV itself.

# Executive summary

The pipeline is a three-layer system whose only purpose is to convert the **Background section** of an SEC merger proxy into a structured, source-backed ledger of who-did-what-when in the auction.

1. A **Large Language Model (LLM)** backend reads the Background section and proposes typed claims (actors, events, bids, counts, relations). Each claim quotes the exact filing text it relies on. The default backend is Claude Agent SDK; direct first-party OpenAI Responses is available only when selected explicitly.
2. A **Python layer** verifies that every quote is genuinely present in the filing (byte-for-byte), assigns canonical IDs, builds the relational graph, runs hard validation checks, and projects review rows.
3. A **human review layer** (you, Alex, optionally with AI assistance) reads the resulting CSV — or for richer queries, the JSONL or DuckDB artefacts — and adjudicates anything that looks wrong against the filing.

The strict ordering of authority is:

> **SEC filing > canonical extraction graph > Alex CSV > Alex's legacy 2026 workbook (calibration only)**.

The legacy workbook is *not* an oracle: when the workbook and the filing disagree, the filing wins. That is why every claim must cite an exact filing quote: there is no other way to make the system auditable.

The figures, code paths, file paths, and rule definitions in this document are pulled directly from the live repository at the run that produced `alex_event_ledger_ref9_plus_targets5.csv` (run timestamp 2026-05-07, schema `deal_graph_v2`, all 9 reference deals verified, all 5 target deals trusted).

# Architecture: three layers

{{figure:architecture_layers}}

## What lives in each layer

**Layer 1 — LLM backend extraction** (`pipeline/llm/extract.py`, `pipeline/llm/client.py`). The selected backend is asked to read one filing and emit one strict JSON object with five claim families. It cites exact substrings of paragraphs from the Background section. It is forbidden from emitting anything else: no canonical IDs, no offsets, no judgements about admission or dropout, no projection rows. The LLM is a *proposer*, not a finaliser.

**Layer 2 — Python canonicalisation, validation, projection** (`pipeline/deal_graph/`). Python does five jobs in sequence: bind every quote to its paragraph, build canonical actors and events, mark each claim as supported or rejected based on whether its quote bound, run hard integrity checks on the resulting graph, and project review rows. None of this involves the LLM.

**Layer 3 — Human review.** Three artefacts are produced for review, in increasing structural richness:

| Artefact | Format | Best for |
|---|---|---|
| `output/review_csv/{slug}.csv` *and* the consolidated `alex_event_ledger_ref9_plus_targets5.csv` | flat CSV, 28 columns | spreadsheet skim, sorting, filtering |
| `output/review_rows/{slug}.jsonl` | one JSON object per line | AI conversation; richer fields than the CSV |
| `output/audit/{slug}/runs/{run_id}/deal_graph.duckdb` | embedded SQL database with ~25 tables | structural queries, joins across actors/events/relations |

A short user-manual section on the CSV columns is in **`csv_user_manual.html`**. The AI-assisted review path (Claude Desktop / Claude Code) is documented at the end of the manual.

## Boundaries that the design enforces

Two boundaries do most of the load-bearing work:

- **The LLM can never emit a canonical ID, an offset, or a projection row.** All three are owned by Python. This means that if you ask the LLM to "produce the same row again," you get the same *quote*, not the same row. Row identity is reproducible because *Python* assigns IDs deterministically from the filing slug, claim type, sequence, and a hash of the claim's content. There is no shared state between the LLM and the row-IDing logic to drift.
- **No claim enters the graph without an exact quote.** Python compares the LLM-supplied quote text to the cited paragraph as a *byte-exact substring*. Mismatched curly quotes, off-by-one whitespace, or paraphrasing all fail the check. Failed claims are quarantined into review-row output; they cannot create canonical rows. This is the central anti-hallucination mechanism. (See [Step 5 — Hard validation](#step-5-hard-validation).)

# End-to-end run, file by file

{{figure:e2e_run_flow}}

The orchestration entry points are tiny:

```bash
# Re-extract one deal:
python run.py --slug mac-gray --re-extract
python run.py --slug mac-gray --re-extract --llm-backend claude_agent_sdk

# Re-extract a batch:
python -m pipeline.run_pool --filter reference --workers 1
python -m pipeline.run_pool --slugs mac-gray,petsmart-inc,zep --workers 3 --re-extract

# Regenerate the consolidated Alex ledger CSV:
python scripts/export_alex_event_ledger.py --scope all \
    --output output/review_csv/alex_event_ledger_ref9_plus_targets5.csv
```

The first command runs **one filing through Layers 1 and 2**. The third command runs **only the deterministic Layer 3 projection** from the saved graph snapshots — no LLM call. Re-running the third command on an unchanged set of snapshots produces a byte-identical CSV.

## Step 1 — Build the Background section and citation units

Before any LLM call, Python pulls the Background section out of the filing and slices it into paragraphs. Each paragraph gets a stable identifier like `page_35_paragraph_4`, called a **citation unit**. The full text of each citation unit is included in the LLM's input.

This pre-step exists because we want the LLM to *cite* paragraphs by ID rather than by page number alone. Two paragraphs on the same page can contain almost-identical sentences, and a quote that matches both is ambiguous; the citation unit ID disambiguates which one is the source.

## Step 2 — The LLM backend call

The system message contains six files, exactly:

- `prompts/extract.md` — the prompt itself (~110 lines)
- `rules/schema.md` — the strict claim schema
- `rules/events.md` — the closed list of 18 event subtypes
- `rules/bidders.md` — actor and relation rules
- `rules/bids.md` — bid-claim fields and projection guidance
- `rules/dates.md` — date precision rules

The user message contains the deal slug, manifest metadata, and the paragraph-numbered text of the Background section.

{{figure:llm_roundtrip}}

Backend selection is runtime configuration, not graph logic:

- Default: `LLM_BACKEND=claude_agent_sdk`. Python calls the repo-local Node bridge for `@anthropic-ai/claude-agent-sdk`, with tools disabled and project settings disabled. It can use the existing Claude Max login or `ANTHROPIC_API_KEY`.
- Optional: `LLM_BACKEND=openai`. Python calls the first-party OpenAI Responses API directly with `OPENAI_API_KEY`. It does not accept compatible base URLs.

Two implementation details matter for review:

- **The LLM cannot return free text.** The selected backend receives the same strict JSON Schema from `pipeline/llm/response_format.py`. If the model tries to invent a field — for example, putting `bidder_class: "U.S. financial"` — the call fails with a schema error and the run is marked `failed_system`. Old field names (`bidder_type`, `bid_note`, per-event row format) are not in the schema and would fail the same way.
- **Reasoning effort defaults to `high`.** Unsupported backend/effort combinations fail before a provider call. Claude Agent SDK supports `none`, `low`, `medium`, `high`, and `xhigh`; direct OpenAI supports `none`, `minimal`, `low`, `medium`, and `high`. The backend, reasoning effort, and exact model ID for any run are recorded in `output/audit/{slug}/runs/{run_id}/manifest.json` for reproducibility.

## Step 3 — Quote binding

For each evidence reference (`{citation_unit_id, quote_text}` pair) on each claim, Python checks:

1. Does the `citation_unit_id` exist in the input we sent the LLM?
2. Is the `quote_text` a byte-exact contiguous substring of that citation unit's text?

The check is implemented in `pipeline/deal_graph/evidence.py` (`bind_quote_to_citation_unit`). It is intentionally strict:

- Curly versus straight quotes do not match.
- Off-by-one whitespace does not match.
- Paraphrases — even one-word substitutions — do not match.

This is the only way for Python to distinguish a real quote from a hallucination. If you ever doubt a row in the CSV, the audit trail guarantees that the quoted text is character-for-character present in the cited paragraph; you only have to check that the *meaning* of the quote supports the claim. (See [How to review](#how-to-review) for what to look for.)

{{figure:quote_binding_flow}}

## Step 4 — Canonicalisation

`pipeline/deal_graph/canonicalize.py` walks the claim families in a fixed order — actors, then actor relations, then events, then bids, then participation counts — and builds graph rows. The actor walk happens first so that later events and bids can reference already-canonicalised actors.

The actor module enforces three substantive rules:

1. **De-duplication by case-folded label.** "Party A", "PARTY A", and "party A" become the same actor. This means the LLM does not have to normalise case or whitespace; that is Python's job.
2. **Group preservation.** A consortium ("Sponsor A and Sponsor E") is a single canonical actor. Member relations between the consortium and its individual members are recorded as `actor_relation_claims`, not as new bidder rows. This is the rule that lets the CSV preserve the filing's bidding unit instead of atomising every consortium into members.
3. **Bidder class promotion.** When the LLM emits an actor claim with `actor_class` of `financial`, `strategic`, or `mixed` (not `unknown`), the actor's class is *locked*: subsequent unknown-class claims for the same label cannot overwrite it. Group classes are refined post-hoc by walking member relations: a group with a strategic member becomes `strategic`; a group with both becomes `strategic` (this is a deliberate research convention, not an LLM judgement).

After canonicalisation, the graph contains canonical rows for actors, actor relations, events, bids (as events with `event_type=bid`), participation counts, claim records, evidence rows, dispositions, coverage links, and row-evidence links. All of these are stable: same filing, same rules, same prompt → same row IDs.

## Step 5 — Hard validation

`pipeline/deal_graph/validate.py` runs a fixed set of integrity checks *after* canonicalisation. If any of them fail, the run is marked `failed_system` and prior trusted output is preserved as `stale_after_failure`.

{{figure:claim_flow}}

{{figure:disposition_lifecycle}}

The hard-flag codes that block a run are:

| Code | Meaning |
|---|---|
| `DG_SCHEMA_VERSION` | The graph snapshot does not declare `schema_version=deal_graph_v2`. |
| `DG_CLAIM_DISPOSITION_MISSING` | A claim has zero or more than one current disposition. |
| `DG_CLAIM_EVIDENCE_MISSING` | A supported claim has no evidence binding (should be impossible by construction). |
| `DG_CLAIM_COVERAGE_LINK_MISSING` | A claim that names an obligation lacks the back-link to that obligation. |
| `DG_ROW_EVIDENCE_MISSING` | A canonical actor / event / relation / count row was created without source-evidence links. |
| `DG_EVENT_LINK_ORPHAN` | An event-actor link references an event or actor that does not exist in the graph. |

In the live snapshot used to produce `alex_event_ledger_ref9_plus_targets5.csv`, **zero hard flags** were raised across the 14 deals. Every row was constructed from a quote that bound exactly to its cited paragraph.

A more permissive class of issues — open review rows with `issue_codes`, soft-flag entries — is expected even on clean runs and is appended to `state/flags.jsonl`. The numerical *open-row count* (the "review burden") is what determines whether a run is `passed_clean` (zero), `needs_review` (1–10), or `high_burden` (>10).

> **What "review burden" means.** A "review row" is any row in `output/review_rows/{slug}.jsonl` whose `review_status` is not `clean`. In `passed_clean` runs there are *zero* open review rows; in `needs_review` runs there are 1–10; in `high_burden` runs there are more than 10. **All 14 deals in the current ledger are `passed_clean`** (review burden zero), confirmed by `state/progress.json`.

You can inspect the live `state/flags.jsonl` shape here:

{{fixture:flags_jsonl_sample}}

## Step 6 — Projection

The graph snapshot is then projected into:

- **Review rows** (`pipeline/deal_graph/project_review.py`). One row per canonical event, relation, count, plus quarantined claims. Rich fields: `bound_source_quote`, `bound_source_page`, `confidence`, `issue_codes`, `suggested_action`. Written to `output/review_rows/{slug}.jsonl` and `output/review_csv/{slug}.csv`.
- **Alex event ledger rows** (`pipeline/deal_graph/project_alex_event_ledger.py`). 28 columns designed for spreadsheet review. The ledger is a *view* of the review-row stream, with the per-event-code priority and date ordering applied. The exhaustive column-by-column reference is in the companion CSV user manual.

The Alex ledger projection is *deterministic and pure*: same input graph → byte-identical CSV. There is no LLM call here. This is what lets `scripts/export_alex_event_ledger.py` regenerate the consolidated file from saved snapshots without re-running extraction.

A canonical-graph node (one event row from the JSON snapshot) looks like this:

{{fixture:canonical_graph_node}}

# The five claim families

The LLM emits exactly one JSON object with exactly five top-level keys:

```json
{
  "actor_claims": [],
  "event_claims": [],
  "bid_claims": [],
  "participation_count_claims": [],
  "actor_relation_claims": []
}
```

The schema is enforced at the selected backend boundary (`pipeline/llm/response_format.py`). Anything else — a top-level `deal` key, a row called `BidderID`, a field named `T` or `bI` or `bF` — is rejected. The forbidden-fields list in `rules/schema.md` exists because old versions of this project sometimes accepted those fields; the strict schema is what guarantees they cannot creep back in.

{{figure:claim_family_map}}

## actor_claims

| Field | Type | Notes |
|---|---|---|
| `actor_label` | string | Filing's label for the actor. e.g. "Party C", "BC Partners, Inc.", "the Buyer Group". |
| `actor_kind` | enum | `organization`, `person`, `group`, `vehicle`, `cohort`, `committee`. |
| `observability` | enum | `named` (filing names it), `anonymous_handle` (e.g. "Party A"), `count_only` (e.g. "11 strategic buyers"). |
| `actor_class` | enum | `financial`, `strategic`, `mixed`, `unknown`. **No** geographic or public/private flags. |

The single-most important rule here: the LLM is *not* allowed to emit a target-only actor claim. The target's identity comes from the filing manifest (`data/filings/{slug}/manifest.json`) and is owned by Python. The target appears in claims only as the object of a substantive relation — for example, the *advised party* in an advisor relation. This is what prevents the LLM from spuriously creating a new "actor" for the target and double-counting.

A sample filing page (from `data/filings/{slug}/pages.json`):

{{fixture:pages_json_sample}}

## event_claims

| Field | Type | Notes |
|---|---|---|
| `event_type` | enum | `process`, `bid`, `transaction`. |
| `event_subtype` | enum | One of 18 closed values (table below). |
| `event_date` | string \| null | ISO `YYYY-MM-DD` only when filing supports it; null otherwise. |
| `description` | string | Optional free-text summary. |
| `actor_label` | string \| null | The actor performing the event. |
| `actor_role` | string \| null | Role of the actor in this event. |

The closed `event_subtype` enum is the heart of the taxonomy. Inventing a new subtype is forbidden; if a filing contains a fact outside the list, the rule (`rules/events.md`) says to emit the closest supported claim at low confidence, or to leave it for rulebook expansion.

| Subtype | Meaning |
|---|---|
| `contact_initial` | First contact between target and a potential bidder. |
| `nda_signed` | Target/bidder confidentiality agreement executed. |
| `consortium_ca_signed` | Bidder-bidder or intra-consortium confidentiality agreement (does *not* substitute for a target-side NDA). |
| `ioi_submitted` | Indication of interest submitted (typically informal, no binding terms). |
| `first_round_bid` | Bid in the first formal round. |
| `final_round_bid` | Best-and-final round bid. |
| `exclusivity_grant` | Target grants exclusive negotiation rights. |
| `merger_agreement_executed` | Merger agreement signed. Price restated here is transaction evidence, not a canonical bid. |
| `withdrawn_by_bidder` | Bidder voluntarily withdrew. |
| `excluded_by_target` | Target removed bidder from process. |
| `non_responsive` | Filing affirmatively states a bidder did not respond/proceed. |
| `cohort_closure` | An anonymous cohort ended participation (e.g. "the remaining bidders dropped out"). |
| `advancement_admitted` | Bidder advanced into the next round. |
| `advancement_declined` | Bidder excluded from the next round. |
| `rollover_executed` | Shareholder rolled equity into the surviving entity. |
| `financing_committed` | Buyer's financing sources committed. |
| `go_shop_started` | Post-signing go-shop window opened. |
| `go_shop_ended` | Go-shop window closed. |

## bid_claims

| Field | Type | Notes |
|---|---|---|
| `bidder_label` | string | Filing's label for the bidder/group. |
| `bid_date` | string \| null | ISO date when supported. |
| `bid_value` | number \| null | Point value when filing supports a single number. |
| `bid_value_lower` / `bid_value_upper` | number \| null | Range bounds when filing supports a range. |
| `bid_value_unit` | enum | `per_share`, `enterprise_value`, `equity_value`, `unspecified`. **No** `other`. |
| `consideration_type` | enum | `cash`, `stock`, `mixed`, `other`, `unspecified`. |
| `bid_stage` | enum | `initial`, `revised`, `final`, `unspecified`. |

The bid claim deliberately separates *value* from *unit*: a $25 figure on a per-share basis is `bid_value=25.0, bid_value_unit=per_share`, whereas a $2.6 billion all-cash offer is `bid_value=2600000000.0, bid_value_unit=unspecified` (or `equity_value` if the filing labels it as such). The Alex ledger preserves all three of `bid_value`, `bid_value_lower`, `bid_value_upper`, plus `bid_value_unit` — it does **not** collapse aggregate values into per-share equivalents.

The Python-owned post-review fields `bI`, `bI_lo`, `bI_hi`, `bF`, `admitted`, `formal_boundary`, `dropout_mechanism`, and `T` (`rules/bids.md`) are *not* in the live extraction artefact and are therefore not in the Alex ledger. They are reserved for downstream econometric tooling that has not yet been built.

## participation_count_claims

| Field | Type | Notes |
|---|---|---|
| `process_stage` | enum | `contacted`, `nda_signed`, `ioi_submitted`, `first_round`, `final_round`, `exclusivity`. |
| `actor_class` | enum | `financial`, `strategic`, `mixed`, `unknown`. |
| `count_min` | int | Lower bound (or exact count). |
| `count_max` | int \| null | Upper bound when bounded; null for `at_least`/`at_most` qualifiers. |
| `count_qualifier` | enum | `exact`, `at_least`, `at_most`, `range`, `approximate`. |

These rows count *unnamed* parties at well-defined stages — for example, "During the week of March 28, 2016, … representatives of GHF contacted 11 potential strategic buyers (including Party A) and 18 potential financial buyers." That sentence supports two participation-count claims and one initial-contact event for the cohort. (See the worked example in the user manual under `event_code = participation_count`.)

## actor_relation_claims

| Field | Type | Notes |
|---|---|---|
| `subject_label` / `object_label` | string | The two actors. Direction defined per relation type below. |
| `relation_type` | enum | 11 values; see `rules/bidders.md`. |
| `role_detail` | string \| null | Optional descriptor (e.g. "lead arranger"). |
| `effective_date_first` | string \| null | ISO date when filing pins down when the relation began. |

Relations are directional. The 11 types are:

| `relation_type` | Direction (subject → object) |
|---|---|
| `member_of` | member → group |
| `joins_group` | joining actor → group (with timing) |
| `exits_group` | exiting actor → group (with timing) |
| `affiliate_of` | affiliate → related actor |
| `controls` | controller → controlled |
| `acquisition_vehicle_of` | vehicle → parent / group |
| `advises` | advisor → advised party |
| `finances` | financier → financed party |
| `supports` | supporter → supported party / transaction |
| `voting_support_for` | supporting holder → buyer / agreement / proposal / transaction |
| `rollover_holder_for` | rolling holder → buyer / vehicle / surviving company / target / transaction |

This is the layer that lets the system distinguish "Sponsor A is part of Bidder 3" from "Sponsor A submitted a bid": the former is a `member_of` relation, the latter is a bid event submitted by Bidder 3 (the group). Without this distinction, the system would atomise every consortium and inflate the bidder count.

# The rulebook

A closed taxonomy is the only way to make the output comparable across deals. The rulebook lives in plain Markdown so that finance/legal reviewers can read and amend it without touching code.

| File | Length | Defines |
|---|---|---|
| `rules/schema.md` | ~130 lines | Claim shape, confidence levels, observability, count qualifiers, forbidden fields. |
| `rules/bidders.md` | ~55 lines | Actor kinds, bidder class, 11 relation types, group doctrine. |
| `rules/bids.md` | ~50 lines | Bid claim fields, value units, consideration types, stages; Python-owned post-review fields. |
| `rules/events.md` | ~60 lines | Event types, the closed list of 18 event subtypes, process semantics. |
| `rules/dates.md` | ~20 lines | When to use ISO dates vs null; relation timing rules. |
| `rules/invariants.md` | ~25 lines | Hard validation invariants Python enforces. |

Two rules are worth re-stating because they shape the CSV most:

> **Exact-or-omit.** *"If no exact substring supports the typed fields sharply, omit the claim."* — `prompts/extract.md`. This is why the CSV has fewer rows per filing than a free-text summary would suggest: the LLM is required to leave out anything it cannot pin to a quote.

> **Preserve the filing's bidding unit.** *"A buyer group, club bid, sponsor/corporate pair, or changing coalition can be one actor. Do not atomise group bids unless the filing shows separate bidding conduct."* — `rules/bidders.md`. This is why the consortium-level Buyer Group in petsmart-inc appears as a single bidder rather than five (BC Partners, Caisse, GIC, StepStone, Longview).

The full enum tables — every coded value with worked-example rows from the actual CSV — live in **`csv_user_manual.html`**. This document references them but does not duplicate them.

# The reference verification gate

The pipeline ships claims, not opinions. To stop the model from quietly drifting between runs, the project enforces a **reference verification gate**: nine deals — chosen by Alex as a calibration set — must have current filing-grounded verification metadata, an accepted `target-release-proof.json`, and an explicit `--release-targets` operator flag *before* extraction is enabled for any other deal.

{{figure:reference_gate}}

## What "verified: true" means and does not mean

`verified: true` is **metadata on a deal** in `state/progress.json`. It is not a run status. It can be set only when:

1. A filing-grounded report exists at `quality_reports/reference_verification/{slug}.md`.
2. The report cites the *current* extraction run's `run_id` and rulebook hash.
3. The report contains the eight required sections (Run Metadata, Commands, Extraction & Flag Summary, Filing-Grounded Calibration Ledger, Filing Evidence Review, Contract Updates, Conclusion) per `quality_reports/reference_verification/README.md`.
4. The verifier (Austin or an agent acting under `SKILL.md`) has read the Background pages and confirmed exact source binding for every sample claim.
5. The conclusion is `Conclusion: VERIFIED`.

`verified: true` is *not* a guarantee that every row is perfect. It is a guarantee that:

- Every canonical row has a quote that binds to the filing.
- The rulebook contract is current (no stale field names).
- A human read the filing and adjudicated the calibration ledger.

It does not guarantee that *the workbook* and the extraction agree. When they disagree, the workbook is treated as calibration material, not as ground truth — see `AGENTS.md` for the formal language.

## The four trusted-run statuses

`state/progress.json` records the per-run status of each deal:

| Status | Meaning | Open review rows |
|---|---|---|
| `passed_clean` | Trusted graph; no open review rows. | 0 |
| `needs_review` | Trusted graph; small review backlog. | 1–10 |
| `high_burden` | Trusted graph; large review backlog (likely needs rule changes or LLM tuning). | >10 |
| `failed_system` | Runtime, schema, artefact, or graph-integrity failure. | n/a (no trusted output) |
| `stale_after_failure` | Prior trusted output exists but the latest run failed. | 0 (preserved from prior run) |

In the current snapshot, **all 14 deals are `passed_clean` and all 9 reference deals are `verified: true`** (target 5 are not yet verified; see [The 5 target deals: trusted, not yet verified](#the-5-target-deals-trusted-not-yet-verified)).

## What `target-release-proof.json` certifies

The stability proof at `quality_reports/stability/target-release-proof.json` is the gate artefact that says "we have enough trusted reference runs at this rulebook and extractor-contract hash, and nothing in the contract drifted." Its key fields are:

- `classification: "STABLE_FOR_REFERENCE_REVIEW"`
- `slug_results[]` — for each reference deal: selected trusted runs, their statuses, review-row counts, and run directories.
- `llm_content_variation.allowed: true` — the proof tolerates wording variation across runs (the LLM's word choice is not a contract); what it forbids is *contract drift* (a new column appearing, a forbidden field being emitted, an evidence ref that does not bind).

When all three conditions hold, the operator may pass `--release-targets` to `pipeline.run_pool`, and the five target deals (`art-technology-group-inc`, `gen-probe-inc-new`, `m-g-c-diagnostics-corp`, `multimedia-games-holding-co-inc`, `wafergen-bio-systems-inc`) become eligible for extraction.

## The 5 target deals: trusted, not yet verified

The current Alex ledger contains 23–33 rows per target deal. Their runs are `passed_clean` (zero open review rows), but `verified` is `null` because no reference verification report has been written for any target deal yet. The operational meaning is:

- The target rows can be reviewed and used for substance.
- A `verified: true` flag on a target deal would require its own filing-grounded report — same protocol as the 9 reference deals.

This document treats the target rows as eligible for review but explicitly *not* certified to the same standard.

# Determinism and reproducibility

Every step from "raw response" to "Alex CSV" is deterministic given the graph snapshot:

- **Canonical IDs** are stable hashes of `(deal_slug, claim_type, sequence, claim contents)`. Re-running canonicalisation on the same raw response produces the same IDs.
- **Quote binding** is exact substring matching — there is no ML/fuzziness involved. Same quote, same paragraph → same span.
- **Projection** is pure Python on the graph snapshot. No randomness, no time-dependent fields except the explicit run timestamp.

What is *not* deterministic across runs is the LLM's word choice — the model may emit slightly different evidence quotes ("On July 12" vs "On July 12, 2016") or the same fact at different confidence levels in two runs. This is why the stability gate explicitly tolerates "metric variability observed: row fingerprints changed" while still requiring that the contract — the schema, the enum values, the rulebook — does not drift.

To reproduce any row exactly, look up its `source_claim_ids` in the CSV, find that claim ID in `output/audit/{slug}/runs/{run_id}/deal_graph_v2.json`, and read the quote-binding entry. The audit folder is immutable; older runs remain on disk under their `run_id`.

# Where to look for what

| Question | File / directory |
|---|---|
| What does the filing actually say at page N? | `data/filings/{slug}/pages.json` |
| What did the LLM emit on this run? | `output/audit/{slug}/runs/{run_id}/raw_response.json` |
| What is the canonical graph for this deal right now? | `output/extractions/{slug}.json` |
| What is the SQL view of the graph (joinable)? | `output/audit/{slug}/runs/{run_id}/deal_graph.duckdb` |
| What review rows did this run produce? | `output/review_rows/{slug}.jsonl` |
| What is in the Alex ledger? | `output/review_csv/alex_event_ledger_ref9_plus_targets5.csv` |
| What rules govern claim shape? | `rules/*.md` (six files) |
| What is the LLM prompt? | `prompts/extract.md` |
| What is the deal-level status? | `state/progress.json` |
| What validation flags fired? | `state/flags.jsonl` (append-only) |
| What is the verification report for a reference deal? | `quality_reports/reference_verification/{slug}.md` |
| What proof certified the target gate is open? | `quality_reports/stability/target-release-proof.json` |

# How to review

The review job is *not* "check whether the model used the right English" — that is what the schema enforces. The review job is:

> *Does the cited filing quote substantively support the claim?*

For example, a row with `event_code = bid_submitted, party_name = Party C, bid_value = 21.0` whose `evidence_quote_full` reads:

> "On July 12, 2016, Party C submitted an IOI with an offer price per share of $21.00"

… supports `bid_submitted` (yes, a bid was submitted), supports `bid_value=21.0`, supports `bid_value_unit=per_share` (the quote says "per share"), supports `event_date=2016-07-12`, but *also* fits `event_code=ioi_submitted` (the quote says "IOI"). Both rows are correctly emitted: the same quote supports both an IOI event (the indication of interest itself) and a bid event (the price embedded in the IOI), and the projection emits one row each.

Things to flag:

- A `bid_value` cited from a quote that names a different bidder.
- An `initiated_by` of `bidder` cited from a quote that says "the Company contacted …".
- A `dropout_reason` of `valuation` cited from a quote that says only "withdrew" with no economics.
- A `bidder_class` of `strategic` for an actor whose claims only describe a financial sponsor.

Two paths are recommended for the review itself:

- **CSV path.** Open the CSV in Excel/Numbers, sort by `deal_slug`+`event_order`, scan for rows where `evidence_quote_full` does not obviously support the row's classification.
- **AI-assisted path.** Open Claude Desktop or Claude Code, point it at `output/review_rows/{slug}.jsonl` (or, with shell access, at `output/audit/{slug}/runs/{run_id}/deal_graph.duckdb`), and ask structural questions like "for petsmart-inc, list every `bid_submitted` whose `bidder_class` is `unknown`." Details are in the user manual.

---

> **Companion document.** The exhaustive column-by-column and code-by-code reference for `alex_event_ledger_ref9_plus_targets5.csv`, with a worked-example row from the actual file for every coded value, is in **`csv_user_manual.html`**.
