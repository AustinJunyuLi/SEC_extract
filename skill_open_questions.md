# Extraction Pipeline — Open Questions to Resolve Before Building the Skill

**Purpose.** Build an AI extraction skill that reads an SEC filing's "Background of the Merger" section (from DEFM14A / PREM14A / SC-TO-T / S-4) and produces a row-per-event spreadsheet matching Alex Gorbenko's schema in `deal_details_Alex_2026.xlsx`.

**How to use this doc.** Each section lists the open questions. For each question: *Context*, *Current practice* (what Alex did in the 9 gold-standard deals), *Options*, and a **Decision** field that is empty until we resolve it. When every question has a Decision, we convert the resolved rulebook into a `SKILL.md`.

**Reference deals** (the 9 that Alex corrected by hand; these are our gold standard and stress-tests):

| Deal                    | Rows         | Archetype it tests                                            |
|-------------------------|--------------|---------------------------------------------------------------|
| Providence & Worcester  | 6024–6059    | English-auction; CVR consideration; many rough dates          |
| Medivation              | 6060–6075    | Classic Bidder Sale; Bid Press Release                        |
| Imprivata               | 6076–6104    | Bidder Interest → Bidder Sale; DropBelowInf / DropAtInf       |
| Zep                     | 6385–6407    | Terminated then Restarted (two separate auctions)             |
| Petsmart                | 6408–6457    | Activist Sale; consortium winner; 15 NDAs same day            |
| Penford                 | 6461–6485    | Two stale prior attempts (2007, 2009); quasi-single-bidder    |
| Mac Gray                | 6927–6960    | IB terminated and re-hired; target drops highest formal bid   |
| Saks                    | 6996–7020    | Chicago RA rows Alex wants deleted; go-shop                   |
| STec                    | 7144–7171    | Multiple Bidder Interest pre-IB; single-bound informals       |

Status legend: 🟥 OPEN · 🟨 TENTATIVE · 🟩 RESOLVED

---

## A. Event Sequencing & Identifiers

### A1. Do we keep `BidderID` in the AI output at all?
- **Context.** `BidderID` is Alex's event-sequence number (integers from Chicago RAs, decimals for Alex's insertions). It exists only to preserve back-compatibility with the old Chicago numbering.
- **Current practice.** Integers = Chicago event, decimals = Alex insertion.
- **Options.**
  1. Keep `BidderID` and have the AI replicate Alex's decimal-wedge logic.
  2. Drop it entirely; emit rows in strict date/narrative order with a fresh 1..N sequence.
  3. Keep it but redefine as *pure chronological sequence* (integers, monotone in date/narrative).
- **Decision.** 🟥 —

### A2. Should `BidderID` be strictly monotone in date?
- **Context.** In Medivation, row 6066 has `ID=5` on 7/19 but row 6067 has `ID=4` on 8/8. In Mac Gray, `ID=21` appears on both row 6957 (9/21) and row 6960 (10/14). In Medivation, `ID=5` appears on both row 6066 (7/19) and row 6070 (8/14). These are ordering/uniqueness violations.
- **Options.**
  1. Yes — strictly monotone; error if dates disagree with order.
  2. No — ordering follows narrative order in the filing (which usually but not always equals date order).
- **Decision.** 🟥 —

### A3. Tie-breaking for events on the same date
- **Context.** Many events share a date (e.g., Petsmart has 12 NDAs on 10/07/2014; Providence has 4 informal bids and a Final Round Inf on 7/20/2016).
- **Options.**
  1. Preserve filing narrative order.
  2. Logical order (Final Round Ann before bids before Final Round deadline before Drop, etc.).
- **Decision.** 🟥 —

---

## B. Date Handling

### B1. Natural-language dates — what numeric date do we assign?
- **Context.** Filings commonly say "mid-June 2016", "early July", "late July", "over the next few weeks", "in the second half of July". Alex's `bid_date_rough` takes a specific date but his rule isn't spelled out; his own comments ask "what should be the appropriate date? July 1?" (Providence row 6033) and "Early July 2016".
- **Options.**
  1. Deterministic mapping: early = day 5, mid = day 15, late = day 25; "over the next few weeks" = end of window; "second half" = day 22.
  2. Conservative: always use the first day of the stated window.
  3. Midpoint of the implied window.
  4. Return the literal phrase in `bid_date_rough` and let a post-processor resolve.
- **Decision.** 🟥 —

### B2. `bid_date_precise` vs `bid_date_rough`
- **Context.** Alex skipped the distinction in the 9 gold-standard deals and just filled `bid_date_rough`. The original intent was precise = explicit calendar date; rough = inferred.
- **Options.**
  1. Keep both; precise only when the filing gives an explicit date, else leave blank.
  2. Drop the distinction and use a single `date` column plus a `date_is_approximate` boolean.
- **Decision.** 🟥 —

### B3. Undated events
- **Context.** Saks row 7012 (Sponsor G drop) and row 7014 (Company H drop) have no date — the filing doesn't give one.
- **Options.**
  1. Leave the date blank and flag the event.
  2. Infer from context (the nearest bracketing event).
  3. Skip the event.
- **Decision.** 🟥 —

---

## C. Event Vocabulary (complete taxonomy)

### C1. Final authoritative list of `bid_note` values
- **Context.** The instructions define a set; Alex's 9 deals use a superset in practice. We need the closed list the AI is allowed to emit.
- **Draft list seen in the data:**
  - Start of process: `Bidder Interest`, `Bidder Sale`, `Target Sale`, `Target Sale Public`, `Activist Sale`, `Target Interest`
  - Publicity: `Bid Press Release`, `Sale Press Release`
  - Advisors: `IB`, `IB Terminated` *(Mac Gray only; not in Alex's instructions)*
  - Counterparty events: `NDA`, `Drop`, `DropBelowM`, `DropBelowInf`, `DropAtInf`, `DropTarget`
  - Bids: *(no note — bid details live in the value/type columns)*, `NA` also appears
  - Round structure: `Final Round Inf Ann`, `Final Round Inf`, `Final Round Ann`, `Final Round`, `Final Round Ext Ann`, `Final Round Ext`, `Final Round Inf Ext Ann`, `Final Round Inf Ext` *(Mac Gray)*, `Exclusivity 30 days` *(Zep)*
  - Closing: `Executed`
  - Prior process: `Terminated`, `Restarted`
- **Questions.**
  - Is `IB Terminated` kept, renamed, or dropped?
  - Is `Target Interest` (Mac Gray row 6928) a legitimate type, or should it be `Bidder Interest`?
  - Is `Exclusivity 30 days` (Zep row 6405) a legitimate event row, or should it sit in a column/field attached to the bid?
- **Decision.** 🟥 —

### C2. Standardize the capitalization / spelling
- **Context.** "NA" appears in many columns with many meanings (truly unknown vs not-applicable vs blank). Some event notes appear with slight variations.
- **Decision.** 🟥 — agree a canonical form for each label.

### C3. What goes in `bid_note` for an actual bid row?
- **Context.** When a bidder submits a bid, `bid_note` is typically `NA` (the event type is implied by the non-NA `bid_value_pershare` and `bid_type`). But Chicago sometimes used `NA` to mean "no value" rather than "this is a bid row."
- **Options.**
  1. Use a dedicated `Bid` tag in `bid_note` for bid rows; reserve `NA`/blank for "no event annotation."
  2. Keep Alex's convention (bid rows carry `NA` in `bid_note`).
- **Decision.** 🟥 —

---

## D. Start-of-Process Classification

### D1. Distinguishing the five start-types
- **Context.** Instructions list `Target Sale`, `Target Sale Public`, `Bidder Sale`, `Bidder Interest`, `Activist Sale`. The distinctions rest on subtle language in the filing.
- **Draft decision tree.**
  - Board meeting agreeing to sell → `Target Sale` (add `Target Sale Public` and `Sale Press Release` if publicly announced).
  - Unsolicited bid that triggers the process → `Bidder Sale` (add `Bid Press Release` if publicly announced).
  - Bidder approaches with discussions but no bid → `Bidder Interest`.
  - Activist pressure → `Activist Sale` (record separately *before* `Target Sale`).
  - Target initiates a sale but a bidder approaches first → both `Target Sale` and `Bidder Sale` as separate rows.
- **Questions.**
  - What is the evidentiary standard for `Bidder Interest` vs `Bidder Sale`? (Imprivata has both for Thoma Bravo within 5 weeks — row 6076 interest on 1/31, row 6077 sale on 3/09.)
  - How do we handle "target was already contemplating a sale but a bidder appeared first"? (Providence row 6024: Party A interest 12/31; IB not retained until 1/27; Target Sale meeting 3/14.)
- **Decision.** 🟥 —

---

## E. Bidder Identity & Aggregation

### E1. Group rows (e.g., "25 parties, including Parties A, B")
- **Context.** Providence row 6027 encodes 25 NDAs in one row with type "11S, 14F". Zep row 6390 has "5 parties, 4F and 1S" with a bid range `[20, 22]`. Petsmart has the *opposite* — 15 separate rows for "Unnamed party 1" through "Unnamed party 12" plus three named.
- **Options.**
  1. **Atomize**: every bidder gets its own row even if the filing aggregates (emit 25 NDA rows for Providence). Requires inventing placeholder names (`Party-a1`, `Party-a2`, …).
  2. **Aggregate**: preserve the filing's grouping as a single row with a count field.
  3. **Hybrid**: atomize named parties, aggregate unnamed ones.
- **Zep row 6390 specifically.** Alex's comment explicitly says "This field needs to be expanded to 5 bidders; one of them bid 20, another 22, another three [20,22]?" — a known defect. How do we want the AI to handle this shape of text?
- **Decision.** 🟥 —

### E2. Joint-bidder rows (Party E/F, Sponsor A/E, CSC/Pamplona)
- **Context.** A single bid is submitted by two parties together.
- **Options.**
  1. Single row, bidder = "Party E/F", type = "S/F".
  2. Single row, bidder = "Party E + Party F" (structured), type-primary + type-secondary.
  3. Two rows with the same `BidderID`, one per participant.
- **Decision.** 🟥 —

### E3. Anonymous bidder naming convention
- **Context.** Filings use "Party A", "Bidder B", "Sponsor C", "Company D", "Strategic 1", "Sponsor A" interchangeably. Alex's instructions say use `a1, a2, …` if unnamed, but the data actually uses whatever the filing says.
- **Options.**
  1. Use whatever the filing says (`Party A`, `Sponsor A`, `Strategic 1`) verbatim.
  2. Canonicalize to `bidder_01`, `bidder_02` in deal-local order and record the filing's label in a separate `bidder_alias` column.
- **Decision.** 🟥 —

### E4. Winning bidder name
- **Context.** The winner is named in the filing; losers are usually anonymized. The winner's name should appear on every row where the winner is the actor.
- **Question.** Do we retroactively update earlier rows once the winner is named? (E.g., if `Strategic 2` turns out to be `Pfizer`, do we rewrite earlier `Strategic 2` rows to `Pfizer`?)
- **Current practice.** Alex keeps the filing's label throughout — the winner row is the first time the real name appears.
- **Decision.** 🟥 —

---

## F. Bidder Type Classification

### F1. Canonical format
- **Instructions say.** `S`, `F`, `non-US S`, `non-US F`, `public S`, `public F`, `non-US public S`, etc.
- **Data shows.** Alex's usage is looser — "Non-US public S" (capital N), "11S, 14F" for group rows, "S and F", "S/F", "NA".
- **Options.**
  1. Strict: lowercase prefixes, single-token types.
  2. Permissive: allow free-form annotations in `bidder_type_note`, plus booleans in `bidder_type_financial`, `bidder_type_strategic`, `bidder_type_nonUS`, `bidder_type_mixed`.
  3. Use only the boolean columns (existing in the schema) and drop the note.
- **Decision.** 🟥 —

### F2. Classification rule for "Chief Executive engaged in talks"
- **Instructions say.** CEO-led talks imply strategic bidder. Financial bidders *also* engage in strategic talks, so the test is really "who signed the letters."
- **Question.** Do we need a more explicit rule list the AI can follow? (e.g., "if the filing names a CEO as the point of contact → S; if it names a partner/fund manager → F; if it names both → flag mixed.")
- **Decision.** 🟥 —

---

## G. Bid Classification: Informal vs Formal

### G1. The call rule
- **Instructions say.** A bid is **formal** if either (a) it's in response to a final-round letter, or (b) it's accompanied by a marked-up merger agreement. "Any range = informal."
- **Question.** Are those the only rules? What about:
  - Bids after `Final Round Ann` but before `Final Round` deadline — formal?
  - Bids with "committed debt and equity financing" (Saks row 7009) but no mark-up — formal?
  - Topping bids after an executed agreement (Providence row 6055 G&W's $25) — formal?
- **Decision.** 🟥 —

### G2. How the AI should reason about this
- **Context.** This is the most subjective judgement in the whole pipeline. We probably need the AI to cite the specific filing language that supports the classification.
- **Decision.** 🟥 — do we require a `formal_evidence` quote column?

---

## H. Bid Value Structure

### H1. Ranges and single-bound bids
- **Context.** Several bids are quoted as a range (`[20.00, 22.00]`). Some only give one bound: Sanofi's first bid was "at least $15.00" (Saks row 6998, only `bid_value_lower`), Company D's 5.60 was the range floor only (STec row 7153).
- **Current practice.** `bid_value_lower` and `bid_value_upper` both populated for ranges; `bid_value_pershare` = NA or set to the lower bound.
- **Question.** When only one bound is given:
  - Populate only `bid_value_lower`, leave `bid_value_upper` NA?
  - Or set both to the given bound (loses the "open-ended" signal)?
- **Decision.** 🟥 —

### H2. Composite consideration (cash + CVR, cash + stock, cash + earnout)
- **Context.** Providence row 6041 G&W bid = "20.02 cash + 1.13 CVR" (total 21.15). Mac Gray row 6954 Party B's $21.50 = "19 in cash, rest in options/earnouts". These sit only in `comments_1` today.
- **Options.**
  1. Extend schema with `cash_per_share`, `stock_per_share`, `contingent_per_share` (CVR/earnout).
  2. Single `bid_value_pershare` = headline number, with a free-text `consideration_note`.
  3. Reject non-cash bids from the dataset.
- **Decision.** 🟥 —

### H3. Entire-company vs partial bids
- **Instructions say.** Only record bids for the entire company. Segment/partial bids are ignored.
- **Question.** How should the AI recognize a partial bid? (Example excerpt in instructions: "$55 million for the Company's business in the United Kingdom and Europe" — clearly partial.) Do we want an explicit skip-rule list?
- **Decision.** 🟥 —

### H4. Aggregate-dollar bids
- **Context.** Sometimes bids are stated in aggregate ("$10 billion"), not per-share. Alex says divide by `cshoc`. But `cshoc` is populated for only 1 of the 9 deals.
- **Question.** Does the AI compute per-share? Or emit aggregate and leave per-share to downstream? Where does it get `cshoc`?
- **Decision.** 🟥 —

---

## I. Dropouts

### I1. The full set of dropout codes
- `Drop` — simply dropped out.
- `DropBelowM` — bidder said its valuation is below market.
- `DropBelowInf` — bidder said its valuation is below its earlier informal bid.
- `DropAtInf` — bidder said its valuation is at its earlier informal bid.
- `DropTarget` — target didn't invite to final round.
- **Question.** Are there other reasons we've seen and haven't encoded? Examples from the data:
  - "Not a strategic fit" (Imprivata row 6089, `Drop`).
  - "Other internal corporate priorities" (Imprivata row 6094, `Drop`).
  - "No firm financing" (Mac Gray Party B, eventually `DropTarget`).
  - "Only interested in select assets" (STec row 7154, `DropTarget`).
- **Option.** Keep the code set tight; capture the narrative reason in `drop_reason_note`.
- **Decision.** 🟥 —

### I2. Re-entering after a drop
- **Context.** Instructions: "still record the earlier dropout notice." Providence Party D drops at row 6053 then re-engages (comment: "Reengaged") but there's no separate `Reengaged` event code.
- **Option.** Add a `Reengaged` event code? Or just let the next NDA/bid row for that bidder signal re-entry?
- **Decision.** 🟥 —

---

## J. Advisors (IB and Legal)

### J1. Investment bank
- **Context.** `IB` is already in the vocabulary. Multiple IBs in large deals are both recorded per the instructions.
- **Open item.** Mac Gray has `IB Terminated` followed by a second `IB` (same bank, BofA). This shape isn't in Alex's instructions.
- **Decision.** 🟥 — keep `IB Terminated`, rename, or drop?

### J2. Legal counsel — needs its own structure
- **Context.** Alex says legal counsel "definitely should be used." Today it appears only as free text in `comments_1` ("Legal advisor: Hinckley Allen"). Counsel is retained pre-process and the date isn't always collected.
- **Options.**
  1. New event type `Legal` (like `IB`) with the counsel in the bidder column.
  2. Deal-level field `target_legal_counsel` (and `acquirer_legal_counsel`) since there's typically one.
  3. Both — a dedicated event row and a deal-level summary.
- **Decision.** 🟥 —

---

## K. Final Rounds

### K1. Vocabulary
- `Final Round Ann`, `Final Round`, `Final Round Inf Ann`, `Final Round Inf`, `Final Round Ext Ann`, `Final Round Ext`, `Final Round Inf Ext Ann`, `Final Round Inf Ext` — is this the complete list?
- **Decision.** 🟥 —

### K2. Implicit final rounds
- **Context.** Sometimes the filing doesn't announce a final round explicitly; the target just invites a subset to bid. Does the AI infer `Final Round Ann` from language like "the Board authorized [IB] to advance [subset] to the second phase"?
- **Decision.** 🟥 —

### K3. Providence row 6058 edge case
- **Context.** Alex's comment: "The deadline apparently was not announced to the bidders, this was the time when the English auction was stopped by the target." The row is labeled `Final Round` but the event is really "bidding terminated by target," not "deadline reached."
- **Options.**
  1. Accept `Final Round` for this usage.
  2. Add a new code `Auction Closed`.
- **Decision.** 🟥 —

---

## L. Terminated / Restarted Prior Processes

### L1. When to include prior attempts
- **Context.** Penford records prior attempts from 2007 and 2009 (rows 6461–6464). Zep has a clean Terminated/Restarted pair (row 6401/6402). The instructions say stale confidentiality agreements from stale processes should be *ignored* for the classification purpose, but Alex's Penford entry includes them anyway.
- **Question.** Include prior attempts only if they have material NDAs/bids? Include always? Skip?
- **Decision.** 🟥 —

### L2. Same-target, different-process boundary
- **Context.** Zep's first auction terminated 6/26/2014, restarted 2/19/2015. Events across the boundary go in the same deal file but conceptually are different processes.
- **Option.** New column `process_phase` (1, 2, …) to separate phases within a deal.
- **Decision.** 🟥 —

---

## M. Entries to Skip (Negative Rules)

### M1. Unsolicited letters with no NDA
- **Context.** Saks row 7013 (Company H) — Alex's comment: "Should be deleted: unsolicited letter, no NDA, no further contact, no price per share."
- **Rule candidate.** If a party is mentioned but never signs an NDA *and* never submits a comparable bid, skip.
- **Decision.** 🟥 —

### M2. Non-bid activity mistakenly recorded
- **Context.** Saks row 7015 (Sponsor A/E) — Alex: "Not a separate bid, should be deleted."
- **Rule candidate.** Require a stated price or clear bid-intent language.
- **Decision.** 🟥 —

### M3. Advisor NDAs
- **Instructions say.** Financial advisor NDAs are collected *in Alex's version* but legal advisor NDAs are skipped (legal counsel recorded separately without a date). Financial advisors' NDA dates: recorded.
- **Question.** Does the AI need to distinguish "financial advisor NDA" from "bidder NDA" when reading filings, or is the name lookup enough?
- **Decision.** 🟥 —

### M4. Confidentiality agreements for prior stale processes
- **Instructions say.** Ignore stale-process NDAs — but Alex included Penford's 2007 and 2009 attempts. Clarify the rule.
- **Decision.** 🟥 —

---

## N. Deal-Level Attributes

### N1. Fields that should sit once per deal, not per event
- `TargetName`, `Acquirer`, `DateAnnounced`, `DateEffective`, `DateFiled`, `FormType`, `URL`, `Auction`, `all_cash`, `cshoc`, `gvkeyT`, `gvkeyA`, `DealNumber`.
- **Context.** Today these repeat on every row. All `NA` in 8/9 gold-standard deals for `all_cash` and `cshoc`.
- **Options.**
  1. Keep repeating (matches current schema, simpler for flat analysis).
  2. Move to a separate `deals` sheet keyed by `DealNumber`.
- **Decision.** 🟥 —

### N2. `all_cash` — derive or carry?
- **Context.** In principle derivable from the composite-consideration decision (H2). In practice it's a field in the dataset today.
- **Decision.** 🟥 —

### N3. `cshoc` — source and whose responsibility
- **Alex's note.** "This is a COMPUSTAT field with the number of shares outstanding, I think (to be verified)."
- **Action.** Verify. The AI probably can't produce this from the filing alone (though many filings do state shares outstanding in the proxy — an alternative source).
- **Decision.** 🟥 —

---

## O. Process Conditions (currently all in `comments_2`)

### O1. Which of these become structured fields?
Seen in the 9 deals:
- Exclusivity period (e.g., "Exclusivity 30 days", "60 day exclusive DD + negotiation").
- Go-shop (e.g., "Go-shop 30 days", "Go-shop until Sep 6").
- Financing condition (e.g., "No financing condition", "No firm financing commitment").
- Termination fees / reverse termination fees.
- Regulatory approval required.
- No-solicitation covenants.
- Due-diligence duration.
- Highly-confident letter from a financing bank.
- **Options.**
  1. Make each a structured column on the relevant bid row.
  2. Keep them in comments; let downstream parse on demand.
  3. Structure the top 3–4 (exclusivity, go-shop, financing, DD duration); leave the rest free text.
- **Decision.** 🟥 —

---

## P. Quality Control & Validation

### P1. Cross-validation with board-meeting summaries
- **Instructions say.** Management reports to the board often summarize "how many NDAs have been signed" — use this to double-check.
- **Rule candidate.** The AI should emit a count check: "Filing states X NDAs signed by [date]; extraction produced Y. Δ = X−Y, flag if nonzero."
- **Decision.** 🟥 —

### P2. Duplicate-ID detection
- **Rule candidate.** Post-processing flags any `BidderID` that appears more than once within a deal.
- **Decision.** 🟥 —

### P3. Date monotonicity check
- **Rule candidate.** Flag any row where `BidderID` ordering disagrees with date ordering.
- **Decision.** 🟥 —

### P4. Mandatory fields
- Every deal should end with an `Executed` row.
- Every bidder who has a bid or drops out should have a prior NDA row (except those classified as `Bidder Interest` which precede the NDA).
- **Decision.** 🟥 — enumerate the invariants the AI should check.

---

## Q. Gold Standard Hygiene (before we train on it)

### Q1. Remove rows Alex said should be deleted
- Saks row 7013 (Company H, unsolicited).
- Saks row 7015 (Sponsor A/E, not a separate bid).
- **Decision.** 🟥 — do we fix the Alex spreadsheet first, or keep it as-is and document deletions separately?

### Q2. Resolve Zep row 6390 (collapsed 5-bidder row)
- Alex's own comment says the row needs expansion.
- **Decision.** 🟥 — expand now or leave pending?

### Q3. Resolve Mac Gray `BidderID=21` duplicate
- Row 6960 should probably be `BidderID=24` or similar.
- **Decision.** 🟥 —

### Q4. Resolve Medivation `BidderID=5` duplicate
- Row 6066 or 6070 needs a different ID.
- **Decision.** 🟥 —

---

## R. Output Format / Schema

### R1. Column set the AI must emit
- Start with Alex's 35 columns; decide which become deal-level, which get added (legal counsel, composite consideration), which get dropped.
- **Decision.** 🟥 —

### R2. Error/flag column
- **Rule candidate.** Add a `flags` column for the AI to record ambiguities ("date inferred from 'mid-June'", "bid range with only lower bound", "aggregate row, not atomized", "possible duplicate of row N").
- **Decision.** 🟥 —

### R3. Evidence column
- **Rule candidate.** Add a `source_quote` column with the exact sentence(s) from the filing supporting the row. Useful for audit and for Alex to verify.
- **Decision.** 🟥 —

---

## S. Scope & Out-of-Scope

### S1. What kinds of deals does the skill handle?
- Only auction deals (multiple NDAs)? Or every M&A deal in the database?
- **Decision.** 🟥 —

### S2. What filings does the skill accept as input?
- DEFM14A, PREM14A, SC-TO-T, S-4. Any others?
- **Decision.** 🟥 —

### S3. What the skill does *not* do
- Compute `cshoc`? Compute `gvkey`s? Fill prior Chicago-collected rows? Write directly into Alex's workbook or emit a fresh one?
- **Decision.** 🟥 —

---

## Working Order

Suggested sequence for our walkthrough (so earlier decisions constrain later ones):

1. S (scope) — what are we building, for what filings, for which deals.
2. R (output schema) — what columns we emit.
3. N (deal-level fields) — where they live.
4. C (event vocabulary) — the closed label set.
5. E (bidder identity & aggregation) — naming and group rules.
6. F (bidder type), D (start-of-process) — classification logic.
7. H (bid value), G (informal vs formal) — bid rows.
8. I (dropouts), J (advisors), K (final rounds), L (terminated/restarted).
9. M (skip rules).
10. B (dates).
11. A (BidderID).
12. O (process conditions).
13. P (QC), Q (gold-standard cleanup).

We can adjust. Ready to start at S1 whenever you are.
