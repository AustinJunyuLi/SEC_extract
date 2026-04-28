# rules/schema.md — Output Schema

**Purpose.** Defines what the extractor emits: the exact columns, their types, and which are deal-level vs event-level.

---

## Resolved rules

### §Scope-1 — Research scope: corporate takeover auctions (🟩 RESOLVED, 2026-04-18)

The research target is **corporate takeover auctions**, per Alex's collection
guide (`reference/CollectionInstructions_Alex_2026.pdf`) §1–§2.1:

> "Collect detailed bidding data on corporate takeover auctions … Criterion:
> multiple bidders have signed/executed confidentiality agreements."

**Definition of an auction (deal-level classification).** A deal qualifies as
an auction when **≥ 2 non-advisor bidders signed confidentiality agreements
during the current sale process**. Formally:

```
count({row ∈ events :
         row.bid_note == "NDA"
         AND row.role == "bidder"
         AND row.process_phase >= 1}) >= 2
```

Exclusions, per Alex:
- `role == "advisor_financial"` or `"advisor_legal"` rows do NOT count
  toward the threshold (per `rules/bids.md` §M3).
- `process_phase == 0` (stale prior) rows do NOT count toward the
  threshold (per `rules/events.md` §L1 / §L2).

**Pipeline behavior — Option B (extract-then-classify).** The extractor runs
on **every** deal with a valid filing type (see §Scope-2). No pre-gate. Each
deal emits a deal-level boolean `auction` computed from the extracted NDA
events. Non-auction deals receive full extractions; the research dataset is
filtered downstream on `auction == true`.

**Why Option B, not a pre-gate.**
1. The auction criterion is an *output* of the extraction (it depends on the
   extracted NDA count), so pre-gating would require a second pass.
2. Non-auction extractions cost the same per-deal budget and may be useful as
   negative controls, diagnostics, or for future research questions.
3. `auction` becomes a validator-checkable deal-level invariant (did the
   classifier see ≥2 qualifying NDAs?) — harder to do if the gate sits
   outside the pipeline.

**Schema implication.** `auction: bool` is a deal-level field (see §N1 when
that resolves — `deal` object either way).

**Validator implication.** A deal-level invariant checks that `auction`
agrees with "≥2 non-advisor bidder NDAs in the current process." Implemented
as `rules/invariants.md` §P-S2.

**Cross-references.**
- `rules/events.md` §L1 — definition of "stale prior process."
- `rules/bidders.md` §F1 — `bidder_type` classification needed to exclude
  financial-advisor NDAs from the auction count.
- `rules/invariants.md` §P-S2 (deal-level auction check).

---

### §Scope-2 — Accepted filing types (🟩 RESOLVED, 2026-04-18)

The skill accepts four **primary substantive form types**, per Alex's
collection guide §1:

| Form | Filed by | Background section title | Notes |
|---|---|---|---|
| **DEFM14A** | Target | "Background of the Merger" | Definitive merger proxy — the workhorse. |
| **PREM14A** | Target | "Background of the Merger" | Preliminary merger proxy. Accepted iff a matching DEFM14A is NOT available; if both exist, prefer DEFM14A. |
| **SC TO-T** | Acquirer | "Background of the Offer" | Tender-offer cover form. The narrative is in the **Offer to Purchase** exhibit (`EX-99.(A)(1)(A)`), which `scripts/fetch_filings.py` auto-resolves. |
| **S-4** | Acquirer | "Background of the Merger" | Stock-consideration mergers; Background often appears in the target's proxy section incorporated by reference. |

**Amendments** (`/A` suffix) are accepted **only when they supersede** a primary
filing — i.e., when the amendment itself contains a full restatement of the
Background. A bare amendment that only modifies a schedule or disclosure is
ignored (no Background to extract). Operationally: the fetcher prefers the
latest `/A` when its size is comparable to the primary; otherwise it falls
back to the primary.

**Target-side tender-offer companions** (`SC 14D9`, `SC 14D9/A`) are accepted
as a **secondary** source for a deal already covered by an `SC TO-T`. The
target often tells its side of the story in 14D9, complementing the
acquirer's narrative in the TO-T / Offer to Purchase. When both are present
for the same deal, extract each into its own `output/extractions/{slug}.json`
run and reconcile downstream. The current pipeline extracts the richer of the
two and flags `paired_filing_not_extracted` on the deal.

**Explicitly excluded** (not Background-bearing):
- `DEFA14A` — definitive additional materials; soliciting content only.
- `425` — merger communications; press-release-style.
- `SC 13D` / `SC 13G` — beneficial-ownership filings.
- Stand-alone `8-K` announcements — event-date only.

**Deal-level `FormType` field.** The extracted deal carries the form type that
sourced the Background, e.g. `"FormType": "SC TO-T (via EX-99.(A)(1)(A))"` for
tender offers so the validator and downstream analyst can see which substantive
document was read.

**Fail-loud rule.** If `seeds.csv` points to a URL whose form type is NOT in
the accepted list, the pipeline marks the deal `status: failed` with
`notes: "unsupported_form_type: <type>"` and moves on. The seeds file is
never silently rewritten.

**Why these four.** Alex's collection guide §1 explicitly enumerates them.
The 401 seed URLs in `seeds.csv` were drawn from the legacy Chicago dataset,
which used the same four. Expanding the form list is a research-design
decision for Alex and outside the current extraction contract.

**Cross-references.**
- `scripts/fetch_filings.py` — `PRIMARY_FORM_TYPES` and tender-offer exhibit
  chasing via `OFFER_TO_PURCHASE_EXHIBIT_PATTERN`.
- `rules/schema.md` §Scope-1 — auction classification operates *after* form
  filtering.

---

### §Scope-3 — Fields the AI deliberately does NOT produce (🟩 RESOLVED, 2026-04-18)

The AI extractor reads the filing's Background section and nothing else. It
does NOT produce:

**Category A — external-database fields (downstream merge only):**
- `cshoc` — COMPUSTAT shares outstanding. A panel field, not in the filing.
- `gvkey` / `gvkeyT` / `gvkeyA` — COMPUSTAT firm identifiers. Not in filings.

**Category B — EDGAR metadata (fetcher owns):**
- `DateFiled` — the date the document was filed with the SEC. Available from
  EDGAR's index HTML. `scripts/fetch_filings.py` will be extended to write
  this to `data/filings/{slug}/manifest.json` as `source.date_filed`. The AI
  does not re-derive it.
- `FormType` — the EDGAR form-type label. Already written by the fetcher as
  `manifest.source.form_type` (e.g., `"DEFM14A"`, `"EX-99.(A)(1)(A)"`). AI
  copies it through into the output's deal-level field but does NOT
  re-classify the document.
- `URL` / `primary_url` — filing URLs. Copied through from
  `manifest.source.index_url` and `source.primary_document_url`.
- `CIK`, `accession` — EDGAR identifiers. Already in `manifest.json`; copied
  through if needed.

**Category C — orchestration metadata (pipeline owns, not extraction):**
- `DealNumber` — Alex's legacy workbook row-group identifier. The pipeline
  keys on `slug` (from `seeds.csv`); any downstream step that needs the
  legacy `DealNumber` can join on `slug`.
- `rulebook_version` — SHA-256 content hash of the current `rules/*.md` files
  at finalize time. Written by `pipeline.finalize()` into the output's `deal`
  object, not by the AI. Mirrors `state/progress.json[deals][slug].rulebook_version`.
- `last_run` — ISO8601-Z finalize timestamp. Written by `pipeline.core.finalize()`
  into the output's `deal` object. The same timestamp is used for
  `state/progress.json[deals][slug].last_run` and for every `logged_at`
  appended to `state/flags.jsonl` during that finalize, so downstream queries
  can match the three exactly.

**Category D — behaviors the skill does not do:**
- Fetch external data (SEC EDGAR beyond the filing itself, COMPUSTAT,
  news sources, etc.).
- Rewrite or merge with `reference/deal_details_Alex_2026.xlsx`.
- Classify the form type or resolve tender-offer exhibits (that's
  `scripts/fetch_filings.py`'s job, per §Scope-2).
- Assign new `BidderID` values across deals; `BidderID` is within-deal only.

**What the AI DOES produce from the filing (see §R1 for the full list):**
1. The event array (the main product).
2. A deal-level `auction: bool` computed from extracted NDA events (per
   §Scope-1).
3. **Confirmation** of deal-identity fields read from the filing's cover /
   proxy summary: `TargetName`, `Acquirer`, `DateAnnounced`, `DateEffective`.
   If the filing-read value disagrees with the corresponding field in
   `seeds.csv` / `manifest.json`, emit a flag `deal_identity_mismatch` on the
   deal; the output carries the **filing-read** value (filing is ground
   truth per `AGENTS.md`).
4. `all_cash` — per §N2 (AI-derived from consideration structure).

**Validator implication.** A row-level check is implied: the deal-level
identity fields emitted by the AI must either match `manifest.json` or carry
a `deal_identity_mismatch` flag.

**Cross-references.**
- `rules/schema.md` §R1 — final column set (will formalize which of the
  "does produce" items are required vs optional).
- `rules/schema.md` §N1 — deal-level vs event-level split.
- `rules/schema.md` §N2 — `all_cash` derivation.
- `scripts/fetch_filings.py` — adds `source.date_filed` to `manifest.json`
  (not yet implemented).
- `AGENTS.md` — source-of-truth section.

---

### §R1 — Final column set (🟩 RESOLVED, 2026-04-18)

Output shape: one JSON file per deal, `{deal: {...}, events: [...]}` (see §N1).

**`deal` object — AI-produced fields (reads from filing):**
- `TargetName` — string. Filing-read; flag `deal_identity_mismatch` if disagrees with seeds.
- `Acquirer` — string. The **operating acquirer** — the entity that actually negotiated and will own the target's assets. Skip Delaware shells and merger-vehicle entities formed solely to execute the transaction (typically named `<Word> Holdings Inc.`, `<Word> Acquisition Inc.`, `<Word> Merger Sub`). For consortium / club deals, the **lead sponsor** named in the primary position ("BC Partners, together with [others]"); fall back to the filing's verbatim consortium label only when no lead is identifiable. For sponsor-backed corporate buyers (operating company funded by a sponsor that is not itself the bidder), the operating company; the funding sponsor goes in the `Executed` row's `additional_note`. Per Alex 2026-04-27 directive: the legal shell is NOT recorded separately.
- `DateAnnounced` — ISO date. Same.
- `DateEffective` — ISO date OR null. Null if filing predates closing.
- `auction` — bool. Computed per §Scope-1 from extracted NDA events.
- `all_cash` — bool. Per §N2, AI-derived from consideration structure.
- `target_legal_counsel` — string OR null. Per `rules/events.md` §J2.
- `acquirer_legal_counsel` — string OR null. Per `rules/events.md` §J2.
- `bidder_registry` — object. Maps canonical `bidder_NN` → `{resolved_name, aliases_observed, first_appearance_row_index}`. Populated by extractor after events. Per `rules/bidders.md` §E3.

**`deal` object — orchestration fields (`run.py` writes, not AI):**
- `slug` — from `seeds.csv`.
- `FormType` — from `manifest.source.form_type`.
- `URL` — from `manifest.source.index_url`.
- `primary_document_url` — from `manifest.source.primary_document_url`.
- `CIK`, `accession` — from manifest.
- `DateFiled` — from `manifest.source.date_filed` (pending fetcher addition).
- `rulebook_version` — SHA-256 content hash of the current `rules/*.md` files
  at extraction time.

**Fields DROPPED from Alex's legacy 35-col workbook (per §Scope-3):**
- `gvkeyT`, `gvkeyA` — COMPUSTAT firm IDs. Downstream merge.
- `cshoc` — COMPUSTAT panel field. Out of scope (§N3).
- `DealNumber` — legacy Chicago row-group ID. Pipeline keys on `slug`.

**`events[]` — per-row columns (kept from Alex's legacy except as noted):**
- `BidderID` — int or decimal (per `rules/dates.md` §A).
- `process_phase` — int. `0` = stale prior, `1` = main, `2` = restart (per `rules/events.md` §L2).
- `role` — string. `"bidder" | "advisor_financial" | "advisor_legal"`. Defaults to `"bidder"`. Auction classifier (§Scope-1) filters `role == "bidder"`. Per `rules/bids.md` §M3.
- `exclusivity_days` — int OR null. Exclusivity period granted at this bid event. Per `rules/bids.md` §O1.
- `bidder_name` — string. **Canonical deal-local ID** (`bidder_01`, `bidder_02`, …)
  per `rules/bidders.md` §E3. Stable across all rows for the same entity.
- `bidder_alias` — string. Filing's verbatim label for this bidder on this
  row (`"Party A"`, `"Pfizer Inc."`, `"Strategic 1"`). Per `rules/bidders.md` §E3.
- `bidder_type` — string OR null. One of `"s"` / `"f"` per
  `rules/bidders.md` §F1 (rewritten 2026-04-27). Geography, listing status,
  and row-level consortium mixedness are NOT recorded.
- `bid_note` — string from closed vocabulary (§C1).
- `bid_type` — `"formal" | "informal" | null` (per §G1).
- `bid_type_inference_note` — string OR null. Required §P-G2 evidence for non-range bid rows with non-null `bid_type`, unless paired/fallback `Final Round.final_round_informal` evidence applies. Max 300 chars. Per `rules/bids.md` §G2.
- `drop_initiator` — `"bidder" | "target" | "unknown" | null`. Required on
  `bid_note = "Drop"`; null otherwise, including `DropSilent`.
- `drop_reason_class` — `"below_market" | "below_minimum" | "target_other" |
  "no_response" | "never_advanced" | "scope_mismatch" | null`. Required
  when applicable on `Drop` per `rules/events.md` §I1.
- `final_round_announcement` — bool OR null. Required on `Final Round`;
  null otherwise.
- `final_round_extension` — bool OR null. Required on `Final Round`; null
  otherwise.
- `final_round_informal` — bool OR null. Required on `Final Round`; null
  only when the filing genuinely does not classify the round.
- `press_release_subject` — `"bidder" | "sale" | "other" | null`. Required
  on `Press Release`; null otherwise.
- `invited_to_formal_round` — bool OR null. Required on each informal `Bid`
  row in a current/restarted process; encodes the target's advancement act.
- `submitted_formal_bid` — bool OR null. Required on each informal `Bid`
  row in a current/restarted process; encodes the bidder's submission act.
- `bid_date_precise` — ISO date OR null.
- `bid_date_rough` — natural-language phrase OR null.
- `bid_value` — numeric OR null. Aggregate $ amount when `bid_value_unit = "USD"`; otherwise reserved.
- `bid_value_pershare` — numeric OR null. Per-share headline value. Per `rules/bids.md` §H1.
- `bid_value_lower` — numeric OR null. Per-share range lower bound. Per `rules/bids.md` §H1.
- `bid_value_upper` — numeric OR null. Per-share range upper bound. Per `rules/bids.md` §H1.
- `bid_value_unit` — string. `"USD_per_share"` for per-share bids; `"USD"` for aggregate (§H4); currency codes (e.g., `"EUR"`) for non-USD.
- `consideration_components` — list[str]. Ordered components present (e.g., `["cash", "cvr"]`). Per `rules/bids.md` §H2.
- `additional_note` — string OR null.
- `comments` — string OR null. **Collapses** Alex's legacy `comments_1` /
  `comments_2` / `comments_3` into one free-text field.
- `source_quote` — str OR list[str] (§R3).
- `source_page` — int OR list[int] (§R3).
- `flags` — array of flag objects (§R2).

**Current scope notes.** Deal-level counsel, bid classification evidence,
consideration component labels, and exclusivity duration remain in scope
because they are useful for manual verification and informal-bidding
analysis. Other transaction economics and merger-agreement terms are
deliberately out of current AI extraction scope; add them back only by
expanding §R1 and the extractor skeleton in the same rulebook change.

**Cross-references.**
- `rules/bidders.md` §F1 — `bidder_type` canonical scalar format.
- `rules/schema.md` §R2 — `flags` structure.
- `rules/schema.md` §R3 — `source_quote` / `source_page` contract.
- `rules/schema.md` §N1 — `{deal, events}` split rationale.
- `rules/schema.md` §N2 — `all_cash` derivation.

---

### §R2 — Flags column format (🟩 RESOLVED, 2026-04-18)

Each row carries `flags: list[FlagObj]`. `FlagObj` is:

```json
{
  "code": "date_inferred_from_rough",
  "severity": "hard | soft | info",
  "reason": "phrase: 'mid-July 2015'"
}
```

- `code` — short snake_case identifier. Enumerated in `rules/invariants.md`
  (validator-generated) and in extractor procedure (extractor-generated).
- `severity` — one of `"hard"`, `"soft"`, `"info"`. Hard = blocks the deal
  from advancing past `status: validated`. Soft = logged, no block. Info =
  statistical anomaly.
- `reason` — one-line human-readable string. For extractor-generated flags,
  name the trigger (e.g., `"phrase: 'mid-July 2015'"`). For validator flags,
  name the check that failed (`"source_quote_not_in_page: cited page 34"`).

**Deal-level flags** live in a parallel `deal.deal_flags[]` array of the same
shape.

**State log.** Every flag is ALSO appended to `state/flags.jsonl` by the
pipeline, with deal slug + row index, for cross-deal analysis. Row-level
`flags[]` in the JSON output is the in-place copy for human review.
`state/flags.jsonl` is append-only history, not a current-state snapshot:
filter by `logged_at >=` the deal's most recent finalize timestamp, or read
`output/extractions/{slug}.json` `flags[]` plus `state/progress.json` `flag_count`
for the authoritative current view.

**Rejected: plain-string array.** Loses `severity` and `reason`; reviewer
has to grep the rulebook to know if a flag is blocking.

**Rejected: separate severity-indexed dict** (`hard_flags[]` / `soft_flags[]`).
Harder to serialize consistently; structured objects are trivially filterable.

---

### §N1 — Deal-level vs event-level split (🟩 RESOLVED, 2026-04-18)

Output is `{deal: {...}, events: [...]}`. Deal-level fields appear **once**
in the `deal` object, NOT repeated on every row.

Legacy Excel layout (where every row carries `TargetName`, `Acquirer`, etc.)
would be generated by a separate downstream export step if Alex's analysis
scripts need it. The current repo stops at JSON extraction and does not
provide a `run.py --rebuild-excel` entrypoint.

**Rationale.** JSON-native; avoids 16× duplication per deal; matches the
natural extraction structure (scan once for deal-level identity, then scan
linearly for events).

---

### §N2 — `all_cash` derivation (🟩 RESOLVED, 2026-04-18)

AI derives `all_cash: bool` from the merger-agreement summary paragraph
(typically on the filing cover or the "Merger" / "Summary Term Sheet"
section).

**Decision rule.**
- `all_cash = true` iff consideration is **pure cash** per share.
- `all_cash = false` for any composite, contingent, or non-cash consideration:
  cash + CVR, cash + earnout, cash + stock, pure stock, mixed cash/stock
  election, etc.
- If the filing's description is ambiguous (rare), flag
  `all_cash_ambiguous` (severity: soft) and emit the AI's best guess.

**Evidence.** Like every row, the deal-level `all_cash` carries
`source_quote` and `source_page` citing the consideration paragraph. These
go on the `Executed` row's existing quote rather than duplicating at the
deal level.

**Interaction with §H2 (composite consideration).** The composite
schema decided in §H2 determines how cash + CVR / cash + earnout is
represented in the `events[]` rows. `all_cash` is downstream of that — any
composite makes `all_cash = false`.

---

### §N3 — `cshoc` source (🟩 RESOLVED, 2026-04-18)

**Out of scope.** AI does not produce `cshoc`. Downstream merge on `gvkey`
against COMPUSTAT. Confirms and formalizes the general rule in §Scope-3.

Alex's "to be verified" note → the COMPUSTAT join is the right place to
verify; filing-read share counts (e.g., "as of the Record Date, X shares
were outstanding") can serve as a cross-check but are not emitted as
`cshoc` by the extractor.

---

### §R3 — Evidence column (🟩 RESOLVED, 2026-04-18)

Every event row carries two mandatory evidence fields that cite the filing text
it was extracted from. These are the backbone of manual verification and the
hard-fail line of the validator.

**Fields.**
- **`source_page`** — `int` OR `list[int]`. The sec2md-assigned page number(s),
  as stored in `data/filings/{slug}/pages.json[i].number`. **NOT** the filing's
  printed page number, which may disagree with sec2md's pagination; sec2md's
  numbering is what the validator can verify against.
- **`source_quote`** — `str` OR `list[str]`. Verbatim substring(s) of the
  `content` field of the cited page(s). Each string must appear byte-for-byte
  (after Unicode NFKC normalization) inside the corresponding page's `content`.

**Single-quote form** (used for ~95% of rows):
```json
{ "source_page": 34, "source_quote": "On June 29, 2016, Medivation and Pfizer entered into a customary confidentiality agreement …" }
```

**Multi-quote form** (used only when one paragraph is insufficient — typical
for `bid_note = Executed` rows that cite both the announcement and the merger
agreement):
```json
{ "source_page": [34, 127], "source_quote": ["…announcement quote…", "…execution quote…"] }
```

When multi-quote, `source_page` and `source_quote` must be lists of the same
length; element `i` of `source_quote` must appear on page `source_page[i]`.

**Length constraint.** A single `source_quote` string is one paragraph at most
— bounded by the blank-line breaks sec2md emits. Hard cap: **1000 characters
per string**. If more evidence is needed, split into a list rather than
lengthening a single quote.

**Validator check (hard error).** `rules/invariants.md` §P-R1 enforces:
1. `source_quote` non-empty.
2. `source_page` is a valid page number for the deal's `pages.json`.
3. After NFKC normalization, `source_quote` is a substring of
   `pages[source_page - 1].content`.
4. In multi-quote form, all four lists/elements align.

Violation → flag `source_quote_not_in_page`. The row is still emitted (per
SKILL.md "not rewritten, only annotated") but the deal cannot advance past
`status: validated` until resolved.

**Reproducibility.** `source_page` values are stable only within a given sec2md
version. `data/filings/{slug}/manifest.json` records `sec2md_version`. Pin
sec2md in `requirements.txt` before broad target rollout. Upgrading sec2md
requires re-fetching or accepting page-drift on old extractions.

**Rationale over rejected alternatives:**
- *Filing's printed page number.* Not every filing HTML aligns to printed
  pages; and Austin can't programmatically verify a printed page number exists.
- *Character offsets (start/end positions).* More precise, but brittle under
  whitespace normalization and hard to spot-check by eye.
- *Paragraph hashes.* Unnecessary at current scale; substring check catches both
  hallucinated and paraphrased quotes.

**Cross-references.**
- `SKILL.md` §Non-negotiable rules (evidence citation: every row carries `source_quote` and `source_page`).
- `rules/invariants.md` §P-R1 (hard validator check).
- `scripts/fetch_filings.py` (produces `pages.json` the quotes must live in).

---

## Canonical output schema (resolved)

Reflects resolved decisions §Scope-1/2/3, §R1, §R2, §R3, §N1, §N2, §N3.

```json
{
  "deal": {
    "slug": "medivation",
    "TargetName": "Medivation, Inc.",
    "Acquirer": "Pfizer Inc.",
    "DateAnnounced": "2016-08-22",
    "DateEffective": "2016-09-28",
    "auction": true,
    "all_cash": true,

    "FormType": "DEFM14A",
    "URL": "https://www.sec.gov/Archives/edgar/data/1011835/…",
    "primary_document_url": "https://www.sec.gov/Archives/edgar/data/…",
    "CIK": "1011835",
    "accession": "000119312516696889",
    "DateFiled": "2016-09-08",
    "rulebook_version": "<rules-content-sha256>",

    "deal_flags": []
  },
  "events": [
    {
      "BidderID": 1,
      "bid_date_precise": "2014-03-14",
      "bid_date_rough": null,
      "bid_note": "Target Sale",
      "bidder_name": null,
      "bidder_type": null,
      "bid_type": null,
      "bid_value": null,
      "bid_value_pershare": null,
      "bid_value_lower": null,
      "bid_value_upper": null,
      "bid_value_unit": null,
      "additional_note": null,
      "comments": null,
      "source_quote": "On March 14, 2014, the Board of Directors convened …",
      "source_page": 23,
      "flags": []
    }
  ]
}
```

Field semantics cross-references:
- `BidderID` format (int vs decimal) — `rules/dates.md` §A1.
- `bid_date_precise` vs `bid_date_rough` rules — `rules/dates.md` §B1–B4.
- `bid_note` closed vocabulary — `rules/events.md` §C1.
- `bidder_type` canonical string format — `rules/bidders.md` §F1.
- `bid_type` informal/formal decision rule — `rules/bids.md` §G1.
- `bid_value*` structure for ranges/single-bound — `rules/bids.md` §H1.
- Composite-consideration representation — `rules/bids.md` §H2.

The shape above is the contract; the items above fill in the semantics of
individual fields without changing the shape.
