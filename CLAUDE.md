# CLAUDE.md — M&A Takeover Auction Extraction Project

> Context file for any Claude (or human) picking up this project. Keep this file current as the project evolves.

## What this project is

We are building an **AI extraction pipeline** that reads the "Background of the Merger" section of SEC merger filings (DEFM14A, PREM14A, SC-TO-T, S-4) and produces a structured row-per-event spreadsheet matching the schema used in Alex Gorbenko's hand-curated M&A auction dataset.

**Why.** Alex's underlying research project studies informal bidding in corporate takeover auctions. The existing dataset was collected by Chicago RAs with known inconsistencies. Alex has manually corrected 9 deals to serve as a gold standard. The long-term plan is to use those 9 deals plus Alex's written instructions to train/prompt an AI extractor that can process the remaining ~400 deals automatically.

**Who's involved.**
- **Austin** (the user of this repo) — building the pipeline.
- **Alex Gorbenko** — senior collaborator, produced the instructions and the gold-standard corrections. Not available in this session; Austin relays decisions from him.

## Project workflow

The work decomposes into three stages. We're currently in **Stage 1**.

```
┌─────────────────────────────────────────────┐
│ Stage 1: Resolve open questions             │  ◄── WE ARE HERE
│   Walk through skill_open_questions.md      │
│   Record a Decision for each question       │
│   Output: resolved rulebook                 │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│ Stage 2: Produce two design artifacts       │
│   (a) Schema — the output contract          │
│   (b) Extraction rulebook — decision logic  │
└─────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────┐
│ Stage 3: Orchestrate & build the skill      │
│   Chunking, multi-pass extraction, QC,      │
│   filing fetch, bidder canonicalization,    │
│   benchmarking against the 9 gold deals     │
└─────────────────────────────────────────────┘
```

**Critical rule:** We do **not** start building the skill until Stage 1 is complete. Every open question in `skill_open_questions.md` must have a Decision.

## Where we are right now

- **Stage 1, not yet started on the walkthrough.** The question list is drafted but no decisions have been recorded.
- The open-questions doc lives at `skill_open_questions.md` and has 19 sections (A–S).
- Suggested walkthrough order (front-loads decisions that constrain later ones): **S → R → N → C → E → F → D → H → G → I → J → K → L → M → B → A → O → P → Q**.

### Immediate next action
Start at **S1** (scope: auction-only deals vs. every M&A deal; which filing types the skill accepts) and work down the list with Austin. Record each Decision in the doc as we go.

## Files in this repo

| Path | What it is |
|---|---|
| `CLAUDE.md` | This file. |
| `skill_open_questions.md` | Working doc of unresolved design questions. Stage 1 deliverable. |
| `reference/CollectionInstructions_Alex_2026.pdf` | Alex's full data-collection rulebook. Black = original Chicago RAs, **bold red = Alex's additions** (the red additions are the most important for us). |
| `reference/deal_details_Alex_2026.xlsx` | The dataset. 9,336 rows × 35 columns. Contains Alex's 9 corrected deals and thousands of older Chicago-collected deals. Red cells = Alex's corrections in the 9 reference deals. |
| `seeds.csv` | 401 candidate deals with SEC filing URLs. 9 rows flagged `is_reference=true` are Alex's gold-standard deals (Providence & Worcester, Medivation, Imprivata, Zep, Petsmart, Penford, Mac Gray, Saks, STec). The other ~392 are the extraction target. |
| `.git/` | Git repo (no commits yet on `main`). |

## The 9 gold-standard deals

Alex hand-corrected these. They are the training/benchmark set. Each was chosen to exercise a different archetype. Rows refer to `deal_details_Alex_2026.xlsx`.

| Deal | Rows | Archetype it tests |
|---|---|---|
| Providence & Worcester | 6024–6059 | English-auction; CVR consideration; many rough dates |
| Medivation | 6060–6075 | Classic `Bidder Sale`; `Bid Press Release` |
| Imprivata | 6076–6104 | `Bidder Interest` → `Bidder Sale`; `DropBelowInf` / `DropAtInf` |
| Zep | 6385–6407 | `Terminated` then `Restarted` (two separate auctions) |
| Petsmart | 6408–6457 | `Activist Sale`; consortium winner; 15 NDAs same day |
| Penford | 6461–6485 | Two stale prior attempts (2007, 2009); near-single-bidder endgame |
| Mac Gray | 6927–6960 | IB terminated and re-hired; target drops highest formal bid |
| Saks | 6996–7020 | Rows Alex wants *deleted*; go-shop |
| STec | 7144–7171 | Multiple `Bidder Interest` pre-IB; single-bound informals |

## Key conventions in the existing data

- **`BidderID` is an event sequence number, not a bidder identifier.** Integers come from the Chicago RAs; decimals (`0.3`, `1.5`, `13.5`) are events Alex inserted between the integers. The name is an inherited misnomer.
- **A single bidder appears on many rows** — once for the NDA, again for each bid, once for a drop, once for execution.
- **`bid_note` is the event-type label.** Start-of-process events (`Target Sale`, `Bidder Sale`, `Activist Sale`, `Bidder Interest`), `NDA`, `IB`, final-round markers, dropout codes (`Drop`, `DropBelowM`, `DropBelowInf`, `DropAtInf`, `DropTarget`), `Executed`, `Terminated`, `Restarted`, press-release markers (`Bid Press Release`, `Sale Press Release`).
- **Legal counsel is currently in `comments_1` as free text**, not a structured field. Alex wants this promoted. Decision pending in §J2.
- **Composite consideration** (cash + CVR, cash + earnout) is currently in `comments_1` as free text. Decision pending in §H2.
- **Deal-level fields** (`all_cash`, `cshoc`, `TargetName`, etc.) are repeated on every row today. Decision pending in §N1 on whether to split into a deal-level sheet.

## Known defects in the gold standard (do not train on as-is)

Documented in §Q of `skill_open_questions.md`. Short list:

- Saks rows 7013 and 7015 should be deleted per Alex's own comments.
- Zep row 6390 compresses 5 bidders into one row; Alex's own comment flags it for expansion.
- Mac Gray row 6960 has `BidderID=21` duplicating row 6957.
- Medivation rows 6066 and 6070 both have `BidderID=5`.

Decision pending: do we fix the reference file before building, or treat these as known exceptions.

## Conventions for future Claude sessions working on this project

- **Don't start coding the skill until Stage 1 is fully closed.** If Austin asks for something that depends on an open question, resolve the question first.
- **Every design decision lives in `skill_open_questions.md`**, not scattered across chat transcripts. When a decision is made, write it into that file's `Decision:` field.
- **The 9 gold deals are the only validated reference data.** Earlier rows in the workbook (before row ~6000) are Chicago-collected and known to have errors Alex has not yet reviewed. Do not treat them as ground truth.
- **Alex's instructions PDF is authoritative** on anything in black-text Chicago original or bold-red Alex addition. When the PDF and the workbook disagree, the workbook reflects Alex's latest thinking and usually wins, but flag the divergence.
- **Be skeptical, cite rows, check dates.** Austin explicitly asks for accuracy over speed and is happy to be told he's wrong.
- **Use the user's folder name ("the folder you selected") when referring to file locations**, not internal sandbox paths.

## Open coordination items with Alex

- Confirm `cshoc` is the COMPUSTAT shares-outstanding field (Alex's own note says "to be verified").
- Confirm whether the pipeline should handle non-auction deals (single bidder with NDA) or only auctions (multiple NDAs).
- Confirm whether Alex wants us to fix the gold-standard defects above before we build, or document and proceed.
