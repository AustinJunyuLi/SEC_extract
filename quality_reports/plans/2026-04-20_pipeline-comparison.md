# Pipeline Comparison: `bids_try` vs `bids_pipeline`

**Date:** 2026-04-20
**Status:** ANALYSIS (not a plan — comparison memo for adjudication)
**Scope:** Systematic apples-to-apples comparison of two sibling M&A-extraction
pipelines, both targeting SEC filings → structured event table at Alex
Gorbenko's research-grade schema.

**Method.** Two Explore subagents each produced a 14-section structured report
against an identical template. Reports were cross-checked against the code
(not just docs) by the subagents. Synthesis below.

---

## 0. TL;DR

| Axis | `bids_try` | `bids_pipeline` |
|---|---|---|
| **Orchestration model** | External Claude Code conversation drives the loop; repo is prompts + Python helpers | Python `orchestrator.py` drives the loop; calls Anthropic/OpenAI SDK directly |
| **LLM invocation** | Claude Code subagent (filesystem-based, no API key) | Direct SDK (`anthropic` / `openai`) with streaming + watchdog + heartbeats |
| **Passes** | 1 extractor + optional scoped Adjudicator (soft-flag only) | Pass 1 (extract) + conditional Pass 2 (evidence repair, no label ownership) |
| **Validator philosophy** | **Flag-only.** Never mutates extraction. 20 deterministic invariants | **Auto-repair.** Synthesizes NDA cohorts, gap-fill Drops, recomputes formality |
| **Ground truth for cells** | Filing text (via mandatory `source_quote` NFKC-substring check) | Regex price scan of raw text (for $ amounts only) |
| **Evidence requirement** | **Hard invariant.** Every row has `source_quote` + `source_page`. No exceptions. | Free-text `comments_*` fields; no per-row citation |
| **Rules artefact** | 6 markdown files (3,125 loc), consumed by LLM via Read tool at runtime | 1 prompt template (~400 lines) concatenated into API call + code constants |
| **Reference-deal handling** | Converted to canonical JSON; `scoring/diff.py` (566 loc) produces human-review diffs | Raw xlsx only; **no diff tool**; comparison is external/manual |
| **No-peeking discipline** | Pipeline code freely reads `reference/alex/` (it's the diff target, not training) | **Enforced by `test_no_peeking.py`**: pipeline may NOT import reference/ |
| **Output** | Per-deal JSON (evidence-rich) | Per-deal JSON ×3 (raw, pass2_input, final) + 35-column xlsx for Alex |
| **Progress tracking** | `state/progress.json` ledger (pending/validated/passed/passed_clean/verified) | None; each run independent; success = file existence |
| **Python LOC** | ~11,400 | ~5,900 |
| **Rulebook LOC (markdown)** | 3,125 | ~400 (single prompt template) |
| **Test LOC** | ~17,700 (9,240 in test_invariants alone) | ~5,371 |
| **Maturity** | Stage 3 active; 8/9 reference deals `passed_clean`; gate-locked on 392 | Phase A complete; no end-to-end pass/fail tally; actively evolving |
| **Domain scope** | Economics research → hand-off to human adjudicator | Economics research → hand-off to human comparator (xlsx-to-xlsx) |

**One-line verdict:** these are two legitimate, defensible architectures for the
same research problem, with **orthogonal bets on where determinism goes**.
`bids_try` puts determinism in the validator's refusals (flag, never fix);
`bids_pipeline` puts determinism in the validator's corrections (fix, never
block semantically). Neither is wrong. Each has load-bearing weaknesses the
other lacks.

---

## 1. The fundamental architectural bet

This is the single most important divergence. Everything else follows.

### `bids_try`: "LLM extracts, Python refuses"

- Extractor emits JSON.
- Python validator runs 20 invariants. If any hard invariant fails, the deal
  is stamped `validated` (human-review required) and the raw extraction is
  **preserved unchanged** as source-of-truth.
- Adjudicator subagent only exists for **soft** flags, and only makes
  verdicts — it does not rewrite rows.
- Row ordering and BidderID renumbering happen at finalization in a narrow,
  well-specified transform (`_canonicalize_order`, §A2/§A3). Aside from that
  and a hint-based "unnamed NDA promotion" pass, the extraction is immutable.

**Implicit theory of error:** if an LLM makes a mistake, don't paper over it
— surface the mistake and change the prompt/rulebook. Auto-repair is a bug
factory because it masks root causes.

### `bids_pipeline`: "LLM drafts, Python repairs"

- Pass 1 emits JSON.
- Python validator **mutates the extraction**:
  - Expands aggregate NDA rows ("15 financial buyers") into `bidder_1..N`
    cohorts (`cohorts.py`, 599 loc).
  - Synthesizes `Drop` rows for NDA signers whose process-segment has no
    closure (`gapfill_nda_signers`, `source="code_gap_fill"`).
  - **Recomputes** `bid_type` (Informal/Formal) from a 7-rule decision ladder
    — overwriting whatever the LLM emitted (`apply_formality_classification`,
    442 loc).
  - Classifies Drop subtypes (DropAtInf / DropBelowInf / DropBelowM) from
    terminal-price evidence.
  - Deduplicates identical Executed rows.
  - Nulls prices on Executed rows.
- Pass 2 is conditionally triggered for **evidence repair only** — it is
  explicitly prompted not to own labels. Labels survive validator
  recomputation even across Pass 2.

**Implicit theory of error:** LLMs are unreliable at consistent taxonomy but
passable at evidence extraction. Move as much labeling as possible into
deterministic code, feed the LLM sparse evidence fields
(`marked_up_MA_received`, `drop_has_terminal_price`), and let Python decide.

### Why both are coherent

- `bids_try`'s flag-only discipline is defensible because it **assumes the
  rulebook is the artefact** — errors come from rulebook gaps, which manifest
  as flagged extractions, which triggers rulebook edits. The 3-unchanged-run
  gate is the stability check.
- `bids_pipeline`'s auto-repair is defensible because it **assumes the LLM
  output is the artefact** — errors come from LLM inconsistency, which
  manifests as row-level defects, which code fixes deterministically. No
  prompt change needed.

### Why each is vulnerable

- `bids_try`'s weakness: **manual adjudication is the bottleneck**, and it is
  not actually happening yet. 8 deals pass clean but 0 are `verified`.
  Providence has 20 open soft flags that will either force a rulebook change
  (reset the clock) or a policy decision to accept soft-flag-as-advisory.
  The gate could loop.
- `bids_pipeline`'s weakness: **validator mutations hide LLM defects.** When
  `apply_formality_classification` reclassifies `Formal` → `Informal` based
  on missing marked-up-MA evidence, the researcher sees only the final label.
  If the LLM systematically under-reports that evidence, the pipeline
  systematically mislabels and no reviewer sees why. The 7-rule ladder is
  intricate and brittle (agent's words).

---

## 2. Extractor invocation: Claude Code subagent vs direct SDK

### `bids_try`: Subagent via filesystem

- Prompt builder (`pipeline.build_extractor_prompt`) returns a **pointer
  prompt**: "read `prompts/extract.md`, `rules/*.md`, `data/filings/{slug}/
  pages.json`, emit one JSON block." No filing text stuffed into the prompt.
- Subagent uses its own Read tool to pull in files.
- **Model is not pinned in code** — it's whatever the orchestrating Claude
  Code session is running.
- Single-pass. No streaming. No watchdog.
- Pro: zero API key management, zero SDK dependency, no token-limit
  gymnastics (subagent reads files lazily).
- Con: not callable from `cron`, not callable from a Python loop, not
  reproducible without the Claude Code environment.

### `bids_pipeline`: Direct SDK

- `orchestrator.py` calls `anthropic.Messages.stream()` or
  `openai.responses.stream()` directly.
- Filing text stuffed into prompt (100KB cap enforced in preprocessing).
- Watchdog thread emits heartbeats during long generations; idle timeouts
  trigger error path.
- Model selected via `--pass1-model` / `--pass2-model` CLI flags. Known
  models: `claude-opus-4-6`, `claude-sonnet-4-6`, `claude-haiku-4-5`,
  `gpt-5.4` family. OpenAI-compatible third-party backends supported via
  `OPENAI_BASE_URL`.
- Pro: fully automatable. One shell invocation extracts any subset of deals
  in parallel (`--workers N`).
- Con: token costs and rate limits are real. Streaming + watchdog adds
  ~300 loc of plumbing that must be maintained. Recent OpenAI Responses API
  migration is "not battle-tested across all backends" (agent's words).

### Implication
These make very different statements about who the *user* is. `bids_try`
assumes the user is *me sitting in Claude Code running the orchestrator by
hand*. `bids_pipeline` assumes the user is *a cron job on a server*. Neither
is wrong but they cannot co-exist without abstraction work.

---

## 3. Evidence & citability

This is the axis where `bids_try` has a decisive structural advantage for
the stated use case.

### `bids_try`: mandatory per-row citation
- `source_quote` (≤1000 chars) and `source_page` are **required** fields.
- Validator enforces `source_quote` is an NFKC substring of `pages[source_page-1].content`. No paraphrase, no lies.
- Multi-quote form supported (list[str] + list[int] paired).
- Makes manual verification *tractable*: Austin reads one quote, confirms
  one row. No deep filing re-reading per row.

### `bids_pipeline`: free-text comments, no citation
- No `source_quote` / `source_page` fields in the schema.
- Evidence lives in `comments_1..3` as natural language.
- Regex price scan is the **only** per-value anchor, and only for dollar
  amounts.
- Manual verification requires reading the filing again per deal.

### Why this matters here
The pipeline exists because Alex wants research-grade data where every row
can be defended to a referee. `bids_try`'s design makes that verifiable at
row granularity without rereading the filing. `bids_pipeline`'s design
requires the researcher to trust the LLM+validator pair and/or re-read for
any given row. For the same deal, `bids_try` is ~10× faster to audit.

This feature would be expensive to retrofit into `bids_pipeline`: the prompt
template, the validator, the pass-2 payload schema, the xlsx compiler, and
the test fixtures all assume no citation fields.

---

## 4. Reference-deal workflow

### `bids_try`: converted reference + diff tool
- `scripts/build_reference.py` (947 loc) converts Alex's xlsx to canonical
  JSON, applying the §Q1–§Q5 structural fixes (delete wrong Saks rows, expand
  Zep's compressed row, renumber duplicate BidderIDs, atomize "Several
  parties"). Provenance preserved in `alex_flagged_rows.json`.
- `scoring/diff.py` (566 loc) produces per-deal divergence reports:
  row-level field diffs, cardinality mismatches, deal-level diffs.
- Diff is NOT a grade. It's a human-review aid. Austin adjudicates each
  divergence against the filing.

### `bids_pipeline`: no-peeking + manual comparison
- `tests/test_no_peeking.py` **enforces** that pipeline code never imports
  from `reference/`. This is a principled decision that the extractor must
  not be informed by the answer key.
- No diff tool exists. No automated comparison. The researcher is expected
  to open both `deal_details_Alex_2026.xlsx` and the pipeline's
  `deal_details_extracted.xlsx` and compare by eye (or build their own tool
  externally).

### Implication
Both positions are intellectually consistent. `bids_try` treats the 9 Alex
deals as a *calibration set* (look, but adjudicate against filing). `bids_pipeline`
treats them as a *hold-out set* (never look; evaluate externally). Given
that the project's explicit epistemology (from `bids_try/CLAUDE.md`) is
"filing is ground truth, Alex is reference not oracle," the calibration-set
framing fits that spirit better — but the hold-out-set framing is also
defensible as a cleaner experimental design.

---

## 5. Validator philosophy in detail

### `bids_try`: 20 named invariants, hard/soft/info tiers

| Code | Check |
|---|---|
| §P-R1..5 | Schema shape, vocabulary, evidence NFKC-substring, role enum, bidder-registry alignment |
| §P-D1..3, D5, D6 | Date ISO, rough-date bidirectionality, BidderID structural + chronological, Drop-needs-engagement, Bid-needs-NDA |
| §P-G2 | bid_type evidence (range or ≤300-char inference note) |
| §P-H5 | Final Round Ann ordering (§K1) |
| §P-S1 (soft) | NDA without subsequent bid/drop |
| §P-S3, S4 | Phase termination; exactly one Executed |
| §P-L1, L2 | ... |

Every invariant is a named Python function in `pipeline.py` with file:line
traceability. Closed-form refusal. No semantic classification by the validator.

### `bids_pipeline`: hybrid enforcement + auto-repair

- **Fail-closed invariants** (block save):
  - Schema shape + required fields
  - `bid_note` / `bid_type` / `bidder_type` in closed vocabularies
  - Single Executed row (with safe-dedup on identical fingerprints)
  - `merger_price` present in regex scan of raw text
  - Unresolved `must_repair` repair targets
- **Auto-repairs** (mutate extraction):
  - NDA cohort expansion (aggregate → atomic)
  - Joint closure projection
  - NDA signer gap-fill (synthesize `Drop` with `source=code_gap_fill`)
  - Executed row dedup
  - Executed price nulling
  - Formality recomputation (7-rule ladder)
  - Drop subtype derivation from terminal-price / comparator evidence
- **Review-only findings** (surface, don't block):
  - Non-canonical `bid_note` labels
  - Bid price mismatches vs regex scan
  - Cue-backed structural obligations (`resolution_policy="review_only"`)
  - Formality raw-vs-derived conflicts

The **Phase A authority rule** is explicit: "code may block on *invariants*
(structural properties of the JSON itself), but may not block on *semantic
interpretation of prose*." Cue-backed repair targets default to
`review_only`, not `must_repair`. This is a genuinely elegant distinction
that `bids_try` does not articulate.

---

## 6. Output format & downstream compatibility

### `bids_try`: researcher-extraction JSON
- `output/extractions/{slug}.json` with `{deal: {...}, events: [...]}` structure.
- Evidence-rich (source_quote, source_page on every event).
- No xlsx export.
- If Alex wants the final data in his workbook format, someone must build
  the JSON→xlsx projector. That hasn't been done yet.

### `bids_pipeline`: xlsx matches Alex's schema
- `compile.py` (224 loc) projects the canonical JSON to a 35-column xlsx
  matching `deal_details_Alex_2026.xlsx` exactly. Alex can diff-by-eye.
- Schema contract enforced pre-projection: `schema_version=1` required.
- Raw Pass 1 JSON + Pass 2 audit JSON also written for audit trail.

### Implication
`bids_pipeline` has the shorter distance to Alex's desk. `bids_try` has the
better provenance but a missing last-mile step.

---

## 7. Test strategy

### `bids_try`
- 51 parametric JSON fixtures, one or two per invariant (pass/fail).
- `test_invariants.py` is 9,240 loc — mostly fixture data inlined.
- Pipeline runtime + diff reporter also tested.
- Doesn't mock the LLM (because the validator is the entire boundary).

### `bids_pipeline`
- 5,371 test loc across 8 files.
- Includes `FakeResponseStream` / `FakeResponseStreamManager` to mock the
  Anthropic streaming API for orchestrator state-machine tests.
- `test_no_peeking.py` is a grep-based enforcement test.
- Less fixture-heavy, more unit-test-per-function.

### Observation
`bids_try`'s test strategy reflects validator-as-the-API. `bids_pipeline`'s
reflects orchestrator-as-the-API. Neither is wrong. `bids_try` would
struggle to add LLM-layer testing without contradicting the Claude Code
subagent model. `bids_pipeline` already has it.

---

## 8. What each repo could learn from the other

### Things `bids_try` should steal
1. **Phase A authority rule.** The invariant-vs-semantic distinction is
   crisply useful and would help `bids_try` articulate which flags block
   (hard) vs surface (soft) — currently stated but not as cleanly.
2. **Raw extraction always saved separately.** `bids_pipeline` writes
   `{slug}_raw.json` before any processing. `bids_try` writes only the
   canonicalized-and-validated output; if a bug in `_canonicalize_order`
   corrupts a row, the original Extractor JSON is lost. Cheap fix.
3. **xlsx projection layer.** Eventually Alex wants the data in his
   workbook. Building this once, cleanly, is easier than every researcher
   rolling their own.
4. **Regex price cross-check.** `bids_pipeline`'s independent regex scan
   catches LLM hallucinated prices at zero LLM cost. `bids_try` has no
   analogous independent check.

### Things `bids_pipeline` should steal
1. **Per-row `source_quote` + `source_page`.** The single biggest structural
   advantage of `bids_try`. Makes audit tractable.
2. **Named-invariant rulebook.** `bids_try`'s `rules/invariants.md` is
   a specification document. `bids_pipeline`'s invariants are only
   discoverable by reading 2,596 loc of `validate.py`.
3. **`state/progress.json` ledger.** Lets the pipeline know what's done,
   what's pending, what's failed. `bids_pipeline` currently has to
   re-extract any deal whose JSON exists (or build per-run manifests
   externally).
4. **`scoring/diff.py`.** Even if `bids_pipeline` wants to keep no-peeking
   in the *pipeline*, a diff tool used *post-hoc* by the researcher is
   orthogonal to that.

---

## 9. Which is "better"?

The question is ill-posed until we name the optimization target.

| Optimization target | Winner |
|---|---|
| Research-grade auditability (per-row provenance) | `bids_try` |
| Automation / reproducibility / throughput | `bids_pipeline` |
| Handling of LLM labeling inconsistency | `bids_pipeline` |
| Handling of LLM hallucination | `bids_try` (NFKC substring check) |
| Getting data into Alex's xlsx | `bids_pipeline` |
| Rulebook as artefact (publishable as methodology) | `bids_try` |
| Test coverage per line of code | `bids_try` (≈1.5×) |
| Cost efficiency (token budget) | `bids_pipeline` (validator does what LLM would) |
| Onboarding a new researcher | `bids_pipeline` (one CLI command) |
| Robustness when the extractor gets a hard case | `bids_try` (flags; forces rulebook evolution) vs `bids_pipeline` (auto-repairs; may mask) |

**For this project's stated goal** — producing a research-grade dataset of
392 deals with every row defensible to a journal referee — `bids_try`'s
evidence-mandatory + flag-only + manual-adjudication design is the better
fit. But `bids_pipeline`'s validator-owned formality + cohort expansion
solves real extractor failure modes that `bids_try` currently leaves as
open soft-flag backlog (see `providence-worcester` 20 NDA cohort issue —
exactly the problem `bids_pipeline` auto-repairs).

---

## 10. Synthesis: what a merged design could look like

If I had to reconcile these for a v2, here's the sketch:

1. **Keep `bids_try`'s orchestration model** (subagent Extractor + Python
   validator + scoped Adjudicator for soft flags). It's simpler and
   composable with Claude Code workflows.
2. **Keep `bids_try`'s mandatory `source_quote` / `source_page`**. Non-
   negotiable for this project.
3. **Adopt `bids_pipeline`'s Phase A authority rule** verbatim: invariants
   may block, semantics may not. Rewrite `rules/invariants.md` to make this
   explicit (it's implicit today).
4. **Adopt `bids_pipeline`'s cohort expansion + NDA gap-fill** as
   *opt-in Python transforms* that run in `finalize()` before validation.
   Add a `source` field per event (`llm` / `code_gap_fill` / `code_cohort_expansion`)
   so flags.jsonl can track where rows came from. Keeps auditability.
   Solves providence.
5. **Adopt `bids_pipeline`'s regex price cross-check** as an additional
   invariant §P-R6.
6. **Adopt `bids_pipeline`'s raw-extraction-save-before-processing**:
   write `output/extractions/{slug}_raw.json` before `_canonicalize_order`
   runs, so the Extractor JSON is always recoverable.
7. **Build an xlsx projector** (one-time, ~200 loc) so reference deals can
   go to Alex in his preferred format.
8. **Keep `bids_try`'s diff tool** but extend it to consume the cohort-
   expansion metadata from (4) so aggregation-vs-atomization diffs are
   readable.

Net effect: ~800 loc added to `bids_try`, ~0 loc removed from the
philosophical core, gains the best of both.

---

## 11. What I am NOT claiming

- I have not run either pipeline end-to-end. All evidence is code-level.
- I have not evaluated output quality on any filing. Neither agent did.
- I have not benchmarked tokens, runtime, or API cost.
- `bids_pipeline` may have undocumented tooling I missed in 40 tool calls.
- `bids_try`'s CLAUDE.md is exceptionally clear and may have biased the
  reviewing subagent to be more generous to it. `bids_pipeline`'s
  CLAUDE.md also exists and is nearly as clear, per agent's notes.

---

## 12. Next actions (not a plan, just follow-ups)

1. Decide whether xlsx projection should live in `bids_try` or stay split.
2. Decide whether to adopt cohort expansion + gap-fill as Python transforms
   — if yes, this collapses providence's 20 soft flags and unblocks the
   exit clock.
3. Decide whether to add regex price cross-check as §P-R6.
4. Decide whether the two repos should merge or stay as independent
   experiments. Current split is defensible if they're serving as A/B
   architectures.

End of comparison memo.
