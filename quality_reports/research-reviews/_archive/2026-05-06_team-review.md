> Pre-redesign document archived on 2026-05-06. This report is superseded by `docs/superpowers/plans/2026-05-06-deal-graph-review-gate-redesign-implementation.md` and is not active operating guidance.

# Codebase Team Review — 2026-05-06

Six parallel agents reviewed the `deal_graph_v1` pipeline read-only.
Domains: LLM/provider, deal graph subsystem, pipeline runtime, docs &
rulebook, CLI scripts/scoring/tests, security & supply-chain.

This is a synthesis of their findings. Cross-cutting themes are flagged.

---

## CRITICAL — gate-relevant or correctness-breaking

### C1. The reference→target gate is currently bypassable

Three independent failures combine to let target extraction open even though
the reference set has not actually stabilised:

- **Stability proof falsely accepts drift.**
  `pipeline/stability.py:727-768` `_classify_slug` records substantive
  metric drift (`row fingerprints changed; graph table counts changed;
  estimation fingerprints changed; date diagnostics changed; bid-value
  representation changed`) as text reasons but only flips classification to
  UNSTABLE on hard/soft flags or config-identity drift. The current
  `quality_reports/stability/target-release-proof.json` shows fingerprint
  drift across all 9 reference slugs yet classifies STABLE_FOR_REFERENCE_REVIEW.

- **`verified` status is silently demoted on `--re-extract`.**
  `pipeline/core.py:2116-2123` `_update_progress_locked` writes whatever
  finalize produced (`validated|passed|passed_clean`) with no guard to
  preserve `verified`. `orchestrate.py:96`'s status enum can't even produce
  `verified`. So a `python run.py --slug medivation --re-extract` clears
  the verification trail without warning.

- **`mark_reference_verified.py` does not ground-check report citations.**
  `scripts/mark_reference_verified.py:53-82` enforces report existence,
  section structure, the literal string `Conclusion: VERIFIED`, hard/blocking
  flag absence, and `is_reference=True`. It does NOT verify the report's
  filing-page citations actually appear in `data/filings/{slug}/pages.json`,
  nor does it pin the report to the extraction's `run_id`. An agent could
  produce a syntactically valid report with fabricated page citations and
  the gate would mark verified. `check_reference_verification.py:62-69`
  only string-matches `"Filing page"` or `"source_page"` somewhere in the
  markdown.

**Combined effect:** the exit gate documented by AGENTS.md ("9 references
pass clean across 3 consecutive unchanged-rulebook runs") is presently a
soft gate, not a hard one.

### C2. `scoring/diff.py` produces silent false zeros

`scoring/diff.py:644-654` reads `ext.get("events", [])`. On every current
`deal_graph_v1` extraction this is `[]`, so `diff_deal()` reports
"19 Alex-only / 0 matched" for every reference deal — not a bug surfaced
to the user, but the answer is uniformly wrong. The medivation verification
report already documents the symptom but the broken script is still on
disk and callable.

### C3. `scripts/render_review_csv.py` is dead and broken

`render_review_csv.py:137,142` reads `extraction.events` and
`deal.bidder_registry` (no longer exist in `deal_graph_v1`); any invocation
raises. The on-disk `output/review_csv/medivation.csv` is written by
`pipeline.deal_graph` directly, not this script — confirming the script is
unused. Both C2 and C3 violate AGENTS.md "no backward compatibility" doctrine.

### C4. `pipeline/core.py` carries ~1900 LOC of retired row-event code

Live responsibilities are ~600 LOC. The remainder — `_invariant_p_r0..p_s5`,
`validate`, `validate_row_local`, `compact_validator_report`, `merge_flags`,
`prepare_for_validate`, `finalize_prepared`, `finalize`,
`_apply_unnamed_nda_promotions`, `_rebuild_bidder_registry_from_events`,
`_canonicalize_order`, `_enforce_extractor_deal_contract`,
`EVENT_VOCABULARY`, `ROLE_VOCABULARY`, `BIDDER_TYPE_VOCABULARY`,
`PHASE_TERMINATORS`, `BID_NOTE_FOLLOWUPS`, `_paired_final_round`,
`_canonicalize_pdf_artifacts`, etc. — is the row-per-event regime that
deal_graph_v1 retired. Kept alive by `tests/test_invariants.py` and
`tests/test_zep_phase_regression.py`. Direct violation of the
no-backward-compat doctrine in AGENTS.md:164-170.

### C5. `pipeline/reconcile.py` reads the dead schema

`_output_flags` (`reconcile.py:183-205`) iterates `final_output["events"]`
(always empty in deal_graph_v1). `_expected_status` calls `core.summarize`/
`core.count_flags` which assume the row-event schema. Any future row-level
review/coverage flag emitted into `graph.review_flags` is treated as zero
by the reconciliation. Today the deal-level flags happen to round-trip,
masking the bug.

### C6. Duplicate-slug pool dispatch races slug-scoped output files

`pipeline/run_pool.py:139-143` `resolve_selection` does not de-dup
`cfg.slugs`. The semaphore at line 742-757 gates by count, not by slug.
`--slugs mac-gray,mac-gray --workers 2` dispatches two parallel workers
for the same slug; both call `core.write_output(slug, ...)` and
`audit.write_latest`. State files are flock-protected, but
`output/extractions/{slug}.json` and `output/audit/{slug}/latest.json`
are last-writer-wins.

### C7. Linkflow streaming timeout layer is wrong

`pipeline/llm/watchdog.py:18` sets `total_call_seconds=600`, but the user's
own memory + the Linkflow proxy enforce `STREAMING_TIMEOUT=300s`. The
proxy will tear the stream first, surfacing as `httpx.TransportError`/
connection error rather than a clean watchdog timeout. Worse:
`asyncio.TimeoutError` (which the watchdog *does* raise locally) is not in
`is_retryable_exception`'s known set (`pipeline/llm/retry.py:35-60`) —
it falls through to `return False` and bubbles out as a permanent failure
on the very first watchdog timeout.

### C8. Class-signal heuristic silently mis-classifies bidders

`pipeline/deal_graph/canonicalize.py:444-461` `_apply_relation_class_signal`
substring-matches `role_detail` for tokens like `"strategic"`, `"operating"`,
`"financial"`, `"sponsor"`, `"capital"`. The two `if` blocks both fire, so
a `role_detail` containing "operating strategic financial sponsor" sets
`bidder_class="strategic"` then overwrites to `"financial"`. Worse:
`_propagate_member_class_signals` (`canonicalize.py:464-485`) lets a single
strategic member of PetSmart's `Buyer Group` flip the group's
classification, violating Consortium Doctrine.

### C9. JSON snapshot and DuckDB writes are not atomic

`pipeline/deal_graph/orchestrate.py:134-141` writes the JSON snapshot,
then the DuckDB store. `store.py:102-104` only commits for SQLite, not
DuckDB; DuckDB auto-commits per statement. A mid-`executemany` failure
leaves a partial DB and a fully-written JSON file on disk, in disagreement.

### C10. SQL boundary silently drops fields the JSON snapshot keeps

- `actor_relations` DDL (`schema.py:510-515`) lacks `subject_actor_label`/
  `object_actor_label`, but `canonicalize.py:221-222` writes them.
  `store.py:138` filters by table columns → labels lost in DuckDB.
- `events` DDL (`schema.py:518-523`) lacks `bid_stage`, but
  `canonicalize.py:291` writes it.

JSON and DuckDB artifacts are no longer consistent reproducers of the same
extraction.

---

## MAJOR — invariant or contract risk

### M1. Cross-document drift on the live contract

| Conflict | Where |
|---|---|
| `coverage_obligation_id` required | SKILL.md:40, prompts/extract.md:38, rules/schema.md:30 — **AGENTS.md silent** |
| `passed` status (soft/info-only) | AGENTS.md:141 — **omitted from SKILL.md:89, rules/schema.md:120** |
| `pending`/`verified`/`failed` | AGENTS.md:139-144 — **never mentioned in SKILL.md/rules** |
| Reasoning-effort tier set | AGENTS.md:85 names `high`/`xhigh` — never enumerates legal set; no env-var name |
| Forbidden-fields list | AGENTS.md, prompts/extract.md, CLAUDE.md each list **slightly different sets** |
| Buyer Group relations | AGENTS.md says "membership, rollover, voting support, financing"; SKILL.md drops "voting support"; rules/bidders.md drops both |
| Phrase: "pages" vs "page breaks" | AGENTS.md:108 vs prompts/extract.md:50 |

### M2. Rulebook timelessness violations

`rules/invariants.md:22`, `rules/schema.md:21`, `rules/events.md:3-5`
contain migration callouts ("Old row-event invariants are retained in git
history only", "Top-level `deal` / `events` row JSON is retired"). The
user's own memory (`project_rulebook_timeless`) explicitly says these
belong in session logs not the rulebook.

### M3. `passed` status is unreachable in code

`validate.py` only emits `severity="hard"` flags. `orchestrate.py:94-96`
partitions into hard/soft/info but soft+info are always 0. So the `passed`
tier documented in AGENTS.md is dead-on-arrival.

### M4. Dead schema tables

`coverage_obligations`, `judgments`, `projection_units`,
`projection_judgments` are created (`schema.py:413-419,545-549,558-562,564-568`)
but never populated. `validate.py:80-102` already loops over
`coverage_obligations` and always finds zero rows. At odds with
`rules/invariants.md` ("every current applicable obligation must have one
current coverage result").

### M5. One rejected claim blocks ALL projections for the deal

`orchestrate.py:79-88`: projections only run when `hard_count==0`. A
single `evidence_ref_binding_failed` flag from one claim suppresses every
review and estimation row for the deal. AGENTS.md is ambiguous but the
intent reads narrower than this.

### M6. `with_retry` catches `BaseException`

`pipeline/llm/retry.py:80` will pull in `KeyboardInterrupt`/`SystemExit`/
`asyncio.CancelledError`. The standard fix is `except Exception` or
explicit exclusions.

### M7. `raw_response.json` is not a complete reproducer

`pipeline/llm/audit.py:104-122` records `model`, `raw_text`, `parsed_json`
— **not** `reasoning_effort`, `max_output_tokens`, response id, or finish
reason. Two runs that flipped between `high` and `xhigh` are
indistinguishable from this artifact alone.

### M8. `--commit` races the git index under `workers > 1`

`pipeline/run_pool.py:501-528` `_commit_paths` runs `git add` + `git commit
--only` per gated task without serialization. Concurrent staging produces
lost updates and "another process running" errors. Either serialize or
hard-disable `--commit` when `workers > 1`.

### M9. `xhigh` cap is process-local

`run_pool.py:475-486` enforces `LINKFLOW_XHIGH_MAX_WORKERS` only inside one
`run_pool` invocation. Two concurrent shell-launched runs each pass the
cap individually but together exceed it. Acceptable if operator-discipline
is the contract; not enforced.

### M10. SEC fetch retry blind spot

`scripts/fetch_filings.py:136-143` catches `urllib.error.HTTPError` but
not `URLError`. Connection timeouts / DNS failures bubble immediately
without retry.

### M11. `smoke_linkflow.py` doesn't reproduce the failure modes the user has actually hit

Per the user's memory: per-token-group channel errors, 300s
STREAMING_TIMEOUT cap, structured-output strict mode validated only on
gpt-5.4. The smoke test exercises a trivial `complete()` happy path only.

### M12. Test ↔ rulebook drift invisible

`tests/test_invariants.py` exercises `_invariant_*` functions directly but
no meta-test pins implemented invariants to `rules/invariants.md`. New
invariant in code or doc → no test breaks.

### M13. Schema accepts empty strings for required ids

`pipeline/llm/response_format.py:140-320` declares `coverage_obligation_id`,
`actor_label`, `subject_label`, `object_label`, `bidder_label`,
`description`, `citation_unit_id`, `quote_text` as `{"type": "string"}`
with no `minLength`. Strict-mode accepts empty strings, which then
flow into canonicalization.

### M14. `mark_reference_verified.py` doesn't pin report ↔ extraction

Beyond C1: there is no check that `report.run_id` equals
`progress.json.last_run_id`. A stale extraction can be verified by a
fresh-looking report.

---

## MINOR — cleanliness, dead code, test gaps

- `pipeline/llm/client.py:211` `_event_delta` includes
  `response.output_text.annotation.added` in the text-delta set.
- `pipeline/llm/response_format.py:379-403` `call_json` is only called
  from tests; either delete or document as test-only.
- `tests/llm/test_client.py:6-29` `FakeStream` emits retired
  `{"deal":..., "events":...}` shape.
- `pipeline/deal_graph/export.py:17,25` non-atomic writes; everywhere
  else in the repo state writes are atomic.
- `pipeline/deal_graph/evidence.py:194-239,54-95,294-313`
  `bind_exact_quote`, `pages_to_paragraphs`, `quote_candidate_units`
  — only used by tests or failure-flag metadata.
- `tests/fixtures/` — 64 stale fixtures (legacy `BidderID`/`bid_note`/
  `process_phase`); not loaded by any current test. Delete under
  no-backward-compat.
- `pipeline/deal_graph/canonicalize.py:275`: `bid_stage in {"revised",
  "unspecified"}` collapse to `first_round_bid` event_subtype.
- `pipeline/deal_graph/canonicalize.py:266` + `_default_role_for_event`
  default `bid` events to `bid_submitter`, producing phantom estimation
  rows for actors with willingness-to-bid only.
- `canonicalize.py:338` target_actor_id always `None` — Python should
  set it from the manifest per AGENTS.md but doesn't.
- `canonicalize.py:207-214` `_stable_id` for relations collides on
  same-parties/same-date/different-`role_detail` — first wins silently.
- `requirements.txt` no lockfile / hash pinning.
- `.env.example` doesn't document `LLM_TOTAL_CALL_SECONDS` or
  `MAX_TOKENS_PER_DEAL`.
- `output/audit/.../calls.jsonl` contains a stale `"adjudicate"` phase
  entry from before adjudicator removal — audit cleanup incomplete.
- `scripts/build_reference.py:358` uses deprecated
  `datetime.datetime.utcnow()`; rest of repo uses tz-aware UTC.
- `validate.py:129-132` ignores `current=False` when promoting blocking
  review flags to hard validation flags.
- `project_estimation.py:30-32` `_first_nonfinal_bid` sorts undated bids
  to the front of dated bids.
- `project_estimation.py:123-131` `_confidence_min` hardcoded `"high"`.
- `claims.py:132-156` `assert_relation_quote_support` keyword-based; many
  filings phrase rollover differently.
- `pipeline/run_pool.py:580-714` `process_deal` has no `try/finally`
  cleanup; aborted runs leave partial `runs/{run_id}` directories.
- `target-release-proof.json` reading doesn't verify referenced
  `selected_runs` still exist on disk.
- No test for: smart-quote binding, multi-page citation_unit binding,
  `bid_stage="revised"` projection, dated `rollover_holder_for` relation,
  duplicate-relation `role_detail` collision, populated
  `coverage_obligations`, partial-write recovery.

---

## What looks solid

- **Provider/Python boundary at the schema layer is bulletproof.**
  `ProviderPayload.reject_provider_owned_fields` (`schema.py:235-253`),
  `PROVIDER_FORBIDDEN_FIELDS`, strict json_schema with
  `additionalProperties: False` everywhere, and parametrized tests in
  `tests/llm/test_response_format.py:205-241` lock retired fields out.
- **Quote binding is byte-exact and address-resolved by
  `citation_unit_id`** — avoids the multi-instance pickup bug.
- **Canonical IDs are deterministic** (`ids.py`, `_stable_id`).
- **`enforce_target_gate` is fail-closed at the dispatch boundary**
  (`run_pool.py:229-256`, invoked before SDK client construction).
- **`_state_file_lock`** does process-local threading lock + flock +
  atomic-replace correctly.
- **Cached raw-response checks are strict** — schema, identity, rulebook
  version, extractor contract version all verified before reuse.
- **No secrets in committed content.** `.env` properly gitignored;
  `.env.example` empty key; `output/audit/.../raw_response.json` audited
  for header/key echoes — clean.
- **SEC fair-access compliance** — User-Agent with email, ~6.7 req/sec
  under 10/sec, exponential backoff on 429/403.
- **Reasoning effort plumbed correctly** as `reasoning={"effort": ...}`
  separate kwarg, not a model suffix (matches the gpt-5.5 requirement
  in user's memory).
- **No subprocess shell-injection paths.**

---

## Recommended action order

The user's memory says target gate is closed until 9 reference deals
pass clean across 3 consecutive unchanged-rulebook runs. **The findings
above show the gate is currently softer than that.** Suggested ordering:

1. **Tighten the gate.** Fix C1 (verified-status preservation in
   `core.py:2116`; stability-classification downgrade on metric drift in
   `stability.py:727`; report-grounding in `mark_reference_verified.py`).
2. **Delete the dead row-event regime.** C2, C3, C4, C5 — `scoring/diff.py`,
   `scripts/render_review_csv.py`, ~1900 LOC in `pipeline/core.py`,
   `pipeline/reconcile.py`'s `events[]` paths, and the orphaned
   `tests/fixtures/` directory. Per AGENTS.md no-backward-compat doctrine,
   these should not be on disk.
3. **Reconcile docs.** Resolve M1 contradictions; remove rulebook
   migration callouts (M2). Decide whether `passed` status survives (M3).
4. **Fix LLM-layer reliability.** C7, M6, M7 — watchdog vs Linkflow 300s;
   `asyncio.TimeoutError` retryable; `with_retry` exception scope;
   `raw_response.json` reproducibility fields.
5. **Lock down the bidder-class heuristic and DDL drift.** C8, C9, C10.
6. **Address minor cleanup and test coverage gaps** as time permits.
