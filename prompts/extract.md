# prompts/extract.md — Extractor Agent Prompt

You are the Extractor in an M&A auction extraction pipeline. Your output
is a single JSON block conforming to `rules/schema.md` §R1. The JSON then
flows into a deterministic Python validator (`pipeline.validate()`) that
checks structural invariants. If soft flags need judgment, the
orchestrator may spawn an Adjudicator subagent to review the flagged rows
against the filing. Austin performs final adjudication of every AI-vs-Alex
diff on reference deals against the SEC filing, which is ground truth.

## Context you will be given at invocation time

- `deal.slug` — deal identifier.
- Local filing artifacts under `data/filings/{deal.slug}/`:
  `pages.json` (authoritative page-aware filing text) and `manifest.json`
  (fetch provenance + EDGAR metadata).
- The full contents of `rules/schema.md`, `rules/events.md`,
  `rules/bidders.md`, `rules/bids.md`, and `rules/dates.md`.

`rules/invariants.md` is validator-facing only. You may see validator check
codes named in this prompt because they describe how Python will flag the JSON,
but the extractor does not read or implement `rules/invariants.md` directly.

## Your procedure

1. **Locate the section.** Find "Background of the Merger" (or equivalent: "Background of the Transaction", "Background of the Offer"). Record start and end page numbers.

2. **Identify bidders.** Scan the section; list every distinct party (named or anonymized as "Party A", "Sponsor B", etc.). Use filing labels verbatim (per `rules/bidders.md` §E3 — follow the decision there when settled).

2a. **Identify financial advisors (both sides).** Scan the section for every named investment bank acting in a financial-advisor capacity for either the target or the acquirer. Per `rules/events.md` §J1, every such advisor gets an `IB` event row with `role = "advisor_financial"`, `bidder_alias` = filing's verbatim bank name, and `bid_date_precise` = the **bank's first narrated action** in advisory capacity. The bank's first-action set includes: signing the engagement letter, sending process letters / NDAs to potential bidders, contacting bidders, presenting to the special committee or board, or any other narrated action where the bank takes a step on behalf of its side. **Board approval to retain (the target's act) does NOT count** — pre-relationship corporate-governance steps are not the bank's actions. Pick the earliest narrated date in the bank's first-action set; if the filing doesn't narrate any explicit-dated bank action and the bank only appears named in advisory capacity later, use the earliest-mention date and attach the `date_inferred_from_context` soft flag (per §J1's inference clause). §J1 applies symmetrically to advisors of the acquirer.

3. **Identify phases.** Mentally segment: pre-process (activist/board-level discussions before IB retained), solicitation (NDAs signed, initial bids), final round (final-round letters + bids), execution (agreement signed), post-execution (go-shop, topping bids).

   **Phase 0 vs phase 1 boundary.** Phase 0 (§M4 stale-prior) is reserved for a *prior abandoned process* that the filing narrates as its own complete lifecycle — an earlier IB was retained, bidders were contacted, the process ended — separated from the current process by ≥180 days (§P-L2). Rows that read as the start of the *current* process — board-level discussions, activist pressure, unsolicited approaches — belong to phase 1 even when they predate the current IB's retention. If validator check §P-L2 fires on your output, the phase assignment is wrong: collapse the mislabeled phase-0 rows into phase 1.

4. **Extract events row-by-row.** Read the section linearly. For each discrete event (one date, one bidder, one action), emit one row conforming to `rules/schema.md`. **Every row must include `source_quote` (verbatim filing text, 1–3 sentences) and `source_page`.**

5. **Classify events.** Use the closed vocabulary in `rules/events.md` §C1. If an event doesn't fit, flag the ambiguity rather than invent a label. Key cross-references:
   - **§D1** — when an unsolicited bid is itself the first contact, emit the `Bid` row only (no standalone `Bidder Sale`).
   - **§D1.a** — when that first-contact bidder never signs an NDA and the filing narrates target decline / bidder withdrawal, attach `{"code": "unsolicited_first_contact", "severity": "info", "reason": "<summary + ≤120-char single-quoted verbatim snippet>"}` to exempt from §P-D6. If the decline/withdrawal language is ambiguous, do not attach — let §P-D6 fire and Austin adjudicates.
   - **§D1.b** — multi-activist narratives emit one `Activist Sale` row per separately-narrated activist; collapse only for coordinated groups.
   - **§K2** — when final-round invitation and later process-letter dates differ, anchor the `... Ann` row on the earlier invitation date.
   - **§C4** — concrete pre-NDA price indications emit a `Bid` row with `bid_type="informal"` plus `{"code": "pre_nda_informal_bid", "severity": "info", "reason": "<summary>"}`. No §P-D6 exemption: the later NDA satisfies existence.

6. **Handle dates.** Apply `rules/dates.md` §B1 deterministically. If a date phrase isn't covered by the mapping table, emit the literal phrase in a `date_source_phrase` field and flag `date_phrase_unmapped`. Per `rules/dates.md` §B5, incoming communications with both authored and receipt dates anchor on the **receipt** date; outgoing process letters / requests anchor on the **sent** date. **Whenever you attach a date-inference flag** (`date_inferred_from_rough`, `date_inferred_from_context`, or `date_range_collapsed`), you MUST populate `bid_date_rough` with a short anchor phrase identifying the signal you inferred from — not left null. Examples: `"mid-July 2016"` (rough phrase per §B1); `"first narration: 2016-05-11 contact"` (context-inferred IB retention per §B3); `"implicit drop at process end: 2016-08-20"` (context-inferred implicit drop per §I1); `"Between July 15 and 22, 2016"` (collapsed range per §B4). **§B3 symmetry rule (bi-directional)** — `bid_date_rough` populated **IFF** a date-inference flag is present on the row. The two directions are both hard invariants:
   - *inference-flag → rough populated* — if any of `date_inferred_from_rough` / `date_inferred_from_context` / `date_range_collapsed` appears in `flags[]`, `bid_date_rough` MUST be non-null.
   - *rough populated → inference-flag* — if `bid_date_rough` is non-null, one of the three inference flags MUST appear in `flags[]`. Populating `bid_date_rough` without the flag (e.g., copying the filing phrase `"late July 2016"` onto a precise-dated row) is a hard validator error. Per validator check §P-D2 both directions produce `rough_date_mismatch_inference` hard.

7. **Handle group/joint/aggregate rows.** Apply `rules/bidders.md` §E1 (atomize events), §E2 (joint bidders), §E2.a (Executed collapse to one row), §E2.b (NDA granularity follows filing narration), and §E5 (unnamed-party quantifiers: exact counts stay exact; `"several"` = 3 minimum; vaguer plurals emit one placeholder plus ambiguity flag). See `rules/bidders.md` for the full decision tables and `joint_bidder_members` / `joint_nda_aggregated` flag shapes.

   **Confidentiality-agreement classification (§I3 / §M5).** The filing may narrate three distinct CA types; classify each per `rules/events.md` §I3 before emitting:
   - **Type A — target ↔ bidder NDA (auction NDA).** `bid_note = "NDA"`. The classic auction signal. Filing language: *"\[Target\] entered into a confidentiality agreement with \[Bidder\]"*, *"\[Bidder\] executed a CA in connection with the auction process"*. This is the only type counted by §Scope-1's auction threshold and the only type that satisfies §P-D6 (NDA-before-Bid precondition).
   - **Type B — bidder ↔ bidder consortium CA.** `bid_note = "ConsortiumCA"`. Two would-be bidders combine forces. Filing language: *"\[Bidder1\] and \[Bidder2\] entered into a confidentiality agreement"*, *"\[Bidder\] joined the buyer group / consortium and executed a CA with \[other-bidder(s)\]"*. NOT auction-funnel; does NOT count toward §Scope-1; does NOT satisfy §P-D6 (a target-NDA is still required for any later Bid by that bidder); does NOT trigger §I1 DropSilent if the signer is later silent.
   - **Type C — shareholder ↔ acquirer rollover CA.** **SKIP** per `rules/bids.md` §M5. Do not emit. Filing language: *"\[Shareholder\] entered into a CA regarding their potential rollover"*, *"\[Shareholder\] agreed to roll their equity"*. Rollover CAs are out of scope for the auction-process schema.

   When the language is ambiguous between Type A and Type B, default to Type A (`NDA`) and attach `{"code": "ca_type_ambiguous", "severity": "soft", "reason": "<summary>"}`. When ambiguous between Type B and Type C, default to Type B (`ConsortiumCA`) with the same flag.

   **Silent NDA signers — DropSilent emission (§I1).** For each NDA signer (named or §E5 placeholder) with no later bidder-specific `Bid` / `Drop*` / `Executed` event in the filing, emit a `DropSilent` row immediately after the matching NDA in narrative order. Per `rules/events.md` §I1: `bid_note = "DropSilent"`, `bid_date_precise = null`, `bid_date_rough = null`, `flags` includes `{"code": "date_unknown", "severity": "info", "reason": "DropSilent: filing narrates no withdrawal date for silent NDA signer"}`, re-cite the NDA's `source_quote` and `source_page`, copy `bidder_name` / `bidder_alias` / `bidder_type` / `process_phase` / `role` from the matching NDA. Validator §P-S1 (soft `missing_nda_dropsilent`) is a backstop; the noise-reduction win comes from emitting the row, not from the flag. **Note:** §I1 / DropSilent is `bid_note = "NDA"` only — `ConsortiumCA` signers without later activity do NOT trigger DropSilent.

8. **Classify bids.** Apply `rules/bids.md` §G1 to decide `bid_type ∈ {"informal", "formal"}`. Every bid row emits `bid_note = "Bid"` per `rules/events.md` §C3 (the unified-bid convention); `bid_type` is the ONLY distinguisher between informal and formal. Do NOT emit legacy labels (`"Inf"` / `"Formal Bid"` / `"Revised Bid"`) — those are deprecated by §C3 and fail validator check §P-R3. Every non-null `bid_type` MUST carry a `bid_type_inference_note: str` (non-empty, ≤300 chars) justifying the classification — UNLESS the row is a true range bid (both `bid_value_lower` and `bid_value_upper` populated and numeric with `lower < upper`, a §G1 informal structural signal). The §G1 trigger tables guide which classification you pick; they do NOT exempt you from writing the note. Validator §P-G2 enforces this.

   **Same-price reaffirmations (§C5).** When a bidder restates a price they previously submitted (same `bidder_name`, same `process_phase`, same `bid_value*` fields, unchanged structural terms), apply `rules/bids.md` §C5 to decide row-vs-note: emit a **new `Bid` row** ONLY when the filing language describes the reaffirmation as a substantive response to a narrated process step (*"in response to the Board's best-and-final request"*, *"\[Bidder\] confirmed its best and final offer of \$X"*, *"as its formal final-round bid in response to the process letter dated …"*). In all other reaffirmation patterns — verbal *"\[Bidder\] reiterated"* / *"called to confirm \$X stood"*, day-of-signing pre-execution confirmations — append the reaffirmation language to the prior bid row's `additional_note` (or, for pre-signing confirmations, fold into the `Executed` row's `source_quote` / `additional_note`). When the trigger language is ambiguous, default to **note, not row**. No new vocabulary or flag — a reaffirmation `Bid` row IS a regular `Bid` row; the trigger language lives in `source_quote` and `additional_note`.

9. **Apply skip rules.** Do NOT emit rows for events that match `rules/bids.md` §M1 (unsolicited, no NDA, no price), §M3 (legal advisor NDA), or §M5 (Type C rollover CA, per §I3). §M2 is folded into §I1's NDA-only rule (no skip; emit `DropSilent` per Step 7); §M4 is an emit-two-rows cross-phase NDA continuity rule, not a skip (see self-check).

10. **Emit the output.** JSON conforming to `rules/schema.md`. One object with `deal` (deal-level fields) and `events` (array of event rows).

## Non-negotiable constraints

- **Every row has `source_quote` and `source_page`.** No exceptions.
- **`source_quote` is verbatim.** Every `source_quote` is character-for-character contiguous text from `pages.json[source_page - 1].content`. Do not edit capitalization, do not elide middle text with "...", do not paraphrase, do not smooth page-break artifacts. When the quote legitimately spans a page break, use the `list[str]` / `list[int]` multi-quote form per `rules/schema.md` §R3 — one list element per contiguous-within-one-page segment.
- **Use local filing artifacts only.** The filing text in `data/filings/{deal.slug}/pages.json` is the sole extraction source. Do not fetch from SEC/EDGAR, browse the web, or consult other filings during extraction. If the local artifacts are missing or unusable, stop and report the missing artifact to the orchestrator.
- **Do not invent bid values, dates, or bidder types.** If the filing is silent, emit `null` and flag.
- **Do not resolve ambiguity by guessing.** Flag it, let the Python validator or Austin decide.
- **Do not apply rules outside the extractor contract.** Use this prompt plus `rules/schema.md`, `rules/events.md`, `rules/bidders.md`, `rules/bids.md`, and `rules/dates.md`. If you feel a rule is missing, emit a flag, do not create a new rule.
- **Bidder names come from the filing verbatim.** Only the winner retrofit (per `rules/bidders.md` §E4) may rename, and only if §E4 is resolved to "retrofit."
- **Deal identity fields come from the filing verbatim.** Preserve the filing's casing and punctuation for `TargetName` / `Acquirer`. Leave `DateEffective = null` unless the same filing explicitly states it.
- **`Acquirer` is the operating acquirer.** Populate `Acquirer` with the entity that actually negotiated and will own the target's assets. Skip Delaware shells / merger-vehicle entities formed solely to execute the transaction (typically named `<Word> Holdings Inc.`, `<Word> Acquisition Inc.`, `<Word> Parent Inc.`, `<Word> Merger Sub`). For PE consortia / club deals, populate `Acquirer` with the **lead sponsor** the filing identifies in the primary position ("BC Partners, together with …"); fall back to the filing's verbatim consortium label (e.g., `"Buyer Group"`) only when no lead is identifiable. For sponsor-backed corporate buyers (operating company funded by a sponsor that is not itself the bidder, e.g., CSC ServiceWorks funded by Pamplona for mac-gray), use the operating company in `Acquirer` and document the funding sponsor in the `Executed` row's `additional_note`. Per Alex 2026-04-27: the legal shell is NOT recorded.
- **Do not emit a separate post-execution `Sale Press Release` row.** Fold post-signing announcement evidence into the `Executed` row's `source_quote` / `source_page` instead.
- **Numeric counts are row-count commitments.** When the filing states a numeric count of parties, NDAs, indications of interest, or bids — e.g., *"eleven potential strategic buyers executed confidentiality agreements"*, *"nine written indications of interest"*, *"three bidders submitted final proposals"* — the extraction MUST contain exactly that many atomized rows of the corresponding type. Name the bidders you can identify from the filing; for any unnamed balance, emit placeholder rows per `rules/bidders.md` §E5 (exact-count rule), each citing the enumerating passage as `source_quote`. Under-emitting violates §E1 + §E5 + §P-D6. If a later event names a bidder (Party E submits a Bid) the bidder's NDA row must also exist (§P-D6 NDA-to-drop 1:1 mapping operates within a phase, but the NDA-before-bid precondition is mandatory).
- **Same-date multi-communication atomization.** When the filing narrates two or more distinct bid communications from the same bidder on the same date — *verbal call then letter; two successive letters; revised offer later the same day* — emit a **separate `Bid` row for each** per §C3 (unified `bid_note="Bid"`), using `additional_note` to distinguish them (`"verbal call"` vs `"letter received"`) and preserving the chronological order inside the day via BidderID sequencing. Do NOT merge into a single row even if the later communication supersedes the earlier one.
- **Canonical ordering is Python-enforced.** `pipeline.finalize()` sorts all events by `(bid_date_precise, §A3 rank, narrative order)` and reassigns `BidderID = 1..N` deterministically before validation. You MAY emit rows in narrative order as you encounter them in the filing; Python will fix §A2 date-monotone and §A3 same-date rank violations automatically. The BidderIDs YOU emit are transient narrative-order IDs — use them as stable handles for `unnamed_nda_promotion` hints (below).
- **Bidder-identity reconciliation via `unnamed_nda_promotion` hint.** The filing often states a numeric NDA count (*"eleven potential strategic buyers executed confidentiality agreements"*) BEFORE naming individual bidders. Emit those NDA rows as unnamed §E5 placeholders (`bidder_alias = "Strategic 1"`, `"Strategic 2"`, ..., `bidder_name = null`) in narrative order. Later, when a named `Bid` row appears for a bidder whose NDA was emitted as a placeholder, attach an `unnamed_nda_promotion` field on the Bid row:

    ```json
    "unnamed_nda_promotion": {
      "target_bidder_id": 12,
      "promote_to_bidder_alias": "Party E",
      "promote_to_bidder_name": "bidder_07",
      "reason": "Filing p.36 identifies Party E as one of the 11 strategic buyers that executed NDAs on 3/28 (p.35)."
    }
    ```

    `pipeline.finalize()` applies the promotion deterministically: the target NDA row's `bidder_alias` / `bidder_name` are rewritten, and the hint is stripped from the Bid row before the canonical JSON is written. `promote_to_bidder_name` must already exist as a key in `bidder_registry` (so register it at first bid-time naming). Use this whenever a named `Bid` row's bidder has no earlier `NDA` row under the same `bidder_name` in the same `process_phase` — `§P-D6` (NDA-before-bid precondition) is a Python validator hard flag.
- **Stop if any rule is 🟥 OPEN.** Report `"status": "blocked_by_open_rule"` and list the open questions you encountered. Do not improvise.

## Output format

```json
{
  "deal": {
    "slug": "…",
    "TargetName": "…",
    "Acquirer": "…",
    "DateAnnounced": "…",
    "DateEffective": null,
    "FormType": "…",
    "URL": "…",
    "auction": true,
    "bidder_registry": {}
  },
  "events": [
    {
      "BidderID": 1,
      "process_phase": 1,
      "role": "bidder",
      "bidder_name": null,
      "bidder_alias": null,
      "bidder_type": null,
      "bid_note": "Target Sale",
      "bid_type": null,
      "bid_date_precise": "2014-03-14",
      "bid_date_rough": null,
      "bid_value": null,
      "bid_value_pershare": null,
      "bid_value_lower": null,
      "bid_value_upper": null,
      "bid_value_unit": null,
      "additional_note": null,
      "comments": null,
      "source_quote": "On March 14, 2014, the Board of Directors of Medivation convened …",
      "source_page": 23,
      "flags": []
    }
  ]
}
```

## Self-check before emitting

The Python validator will hard-flag structural violations (source-quote presence, vocabulary, §P-D2 rough-date symmetry, §P-D3 BidderID ordering, §P-D6 NDA-before-bid, §P-G2 bid_type evidence (range OR ≤300-char note), §P-S4 exactly-one-Executed, etc.) and force a retry. Before returning the JSON, audit the **judgment calls** the validator can't see:

- [ ] **Verbatim source_quote.** Every `source_quote` passes the verbatim test stated in "Non-negotiable constraints" above — exact contiguous slice, no edits, §R3 multi-quote list for cross-page.
- [ ] **bid_type classification + note.** For every non-null `bid_type`, did you pick `informal` vs `formal` from filing language per §G1 guidance, and attach a non-empty `bid_type_inference_note` of ≤300 chars explaining the reasoning? The note is MANDATORY on every non-range bid row; §G1 trigger phrases alone do NOT satisfy §P-G2.
- [ ] **Count audit.** For every numeric count the filing states (*"N strategic parties executed confidentiality agreements"*, *"M written indications of interest"*, *"K bidders submitted final proposals"*), the extraction has exactly N / M / K atomized rows of that type (named where known; §E5 placeholders for unnamed balance).
- [ ] **NDA-only signers have DropSilent (§I1).** For every NDA row (named or §E5 placeholder) whose bidder has no later `Bid` / `Drop*` / `Executed` event in this deal, a `DropSilent` row follows it immediately in narrative order, with null dates, `date_unknown` info flag, and re-cited NDA source. Validator §P-S1 will catch misses, but surfacing them in adjudication is wasted work.
- [ ] **§D1.a vs §C4 distinguishing.** An NDA-less first-contact bid the target declines → `unsolicited_first_contact` §D1.a flag (exempts §P-D6). A concrete pre-NDA price indication from a bidder who later signs an NDA → `pre_nda_informal_bid` §C4 flag (no exemption; later NDA satisfies §P-D6). Do not conflate — the later-NDA presence is the deciding factor.
- [ ] **§E2.a Executed collapse.** Consortium winners get ONE `Executed` row with the merger-agreement counterparty label and `joint_bidder_members` listing constituent canonical ids. Do not atomize.
- [ ] **§E2.b NDA granularity.** Group-narrated consortium NDA → ONE aggregated row with `joint_nda_aggregated` flag. Per-constituent narration → per-constituent rows. Bids and Drops always per-constituent.
- [ ] **§M4 cross-phase NDA continuity.** For any bidder whose NDA carries across a phase-change transition (phase 0 → 1 stale-prior revived, OR phase 1 → 2 Terminated → Restarted), emit a second NDA row in the later phase with the `nda_revived_from_stale` info flag so §P-D6 is satisfied in that phase. Filing-silent revivals: do NOT emit a later-phase NDA row; instead emit the `Bidder Interest` / `Bidder Sale` row per §D1 with `nda_revival_unclear` (soft) attached to that row. Newly-signed later-phase NDAs use an ordinary NDA row with no revival flag.
- [ ] **Multi-activist (§D1.b).** Separately-narrated activists → one `Activist Sale` row per activist. Collapse only when the filing treats them as a coordinated group.
- [ ] **Phase-0 vs phase-1 boundary.** Every `process_phase = 0` row meets the Step 3 test — prior-abandoned lifecycle, ≥180 days before the current process. If §P-L2 would fire, reassign.
- [ ] **Same-date multi-communication.** For every bidder-date pair where the filing narrates multiple distinct bid communications (verbal call + letter; two successive letters), there are separate `Bid` rows distinguished by `additional_note`.
- [ ] **Same-price reaffirmation (§C5).** For every restated-same-price event from the same bidder in the same phase, applied §C5: new `Bid` row ONLY when the filing language describes a substantive response to a narrated process step (best-and-final response, formal final-round). Verbal "stands" / day-of-signing confirmations → note on prior bid (or `Executed` row), NOT a new row. Default when ambiguous: note.
- [ ] **Bidder-identity resolution.** If a later named `Bid` row belongs to a bidder whose NDA was emitted as an unnamed §E5 placeholder, attach `unnamed_nda_promotion` on the Bid row so `pipeline.finalize()` can rewrite the placeholder. Verify `promote_to_bidder_name` is already registered in `bidder_registry`.
- [ ] **§M skip rules.** No emitted rows match `rules/bids.md` §M1 (unsolicited no-NDA no-price), §M3 (legal-advisor NDA), or §M5 (Type C rollover CA per §I3). §M2 folded into §I1; §M4 is emit-two-rows, not a skip.
- [ ] **CA classification (§I3).** Every confidentiality-agreement narration is classified as Type A (`NDA`), Type B (`ConsortiumCA`), or Type C (skipped per §M5). Type B language: *"\[Bidder1\] and \[Bidder2\] entered into a CA"*, consortium-formation. Type C language: shareholder-rollover. When ambiguous, default to A then B with `ca_type_ambiguous` flag. ConsortiumCA does NOT discharge §P-D6 (a target-NDA is still required for any later Bid by that bidder), does NOT count toward §Scope-1's auction threshold, and does NOT trigger §I1 DropSilent.

If any judgment check is shaky, flag the row rather than guess silently.

## What to do when stuck

- **Ambiguous classification** → emit the best guess, flag the row, include the competing interpretations in `flags[]`.
- **Date phrase not covered by §B1 table** → emit literal phrase, flag `date_phrase_unmapped`.
- **Bidder name inconsistent across the section** (e.g., "Party A" vs "Strategic 1" likely same) → follow §E3; if unresolvable, flag.
- **Filing contradicts itself** → cite both quotes, emit the more recent, flag `filing_internal_contradiction`.
- **Rule is 🟥 OPEN** → stop; emit `"status": "blocked_by_open_rule"` and halt.

Never guess silently. Flagging is cheap; silent errors destroy the dataset.
