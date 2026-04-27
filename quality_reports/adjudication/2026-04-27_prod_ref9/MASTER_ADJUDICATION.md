# Production Reference-9 Extraction and Adjudication

Generated: 2026-04-27

Scope: nine reference deals only. Target-deal gate remains closed.

This is a Codex/subagent adjudication package against SEC filing text. It does
not mark any deal `verified` in `state/progress.json`; the project contract
reserves `verified` for Austin's manual review.

## Extraction Status

All nine reference deals were extracted from local filing artifacts and
finalized through `run.py`. All finalized deals have `status = passed`; none
has hard validator flags.

| Deal | Events | Final status | Flags |
|---|---:|---|---|
| medivation | 21 | passed | hard=0 soft=0 info=9 |
| imprivata | 28 | passed | hard=0 soft=1 info=16 |
| zep | 71 | passed | hard=0 soft=35 info=1 |
| providence-worcester | 91 | passed | hard=0 soft=25 info=50 |
| penford | 33 | passed | hard=0 soft=0 info=10 |
| mac-gray | 60 | passed | hard=0 soft=17 info=20 |
| petsmart-inc | 61 | passed | hard=0 soft=5 info=38 |
| stec | 36 | passed | hard=0 soft=2 info=8 |
| saks | 34 | passed | hard=0 soft=10 info=23 |

## Adjudication Reports

| Deal | Report | Headline verdicts |
|---|---|---|
| medivation | `medivation.md` | AI mostly right: ai-right 19, both-defensible 4, no Alex-right or both-wrong items. |
| imprivata | `imprivata.md` | AI broadly right, but final-round announcement needs correction: ai-right 25, both-wrong 2. |
| zep | `zep.md` | Not clean: ai-right 14, alex-right 3, both-wrong 3, needs-Austin 7. |
| providence-worcester | `providence-worcester.md` | Not clean: ai-right 18, alex-right 1, both-wrong 3, needs-Austin 2. |
| penford | `penford.md` | Mostly AI/reference-update, but 3 both-wrong buckets require follow-up. |
| mac-gray | `mac-gray.md` | Cleanest after Medivation: ai-right 14, no Alex-right, both-wrong, or needs-Austin buckets. |
| petsmart-inc | `petsmart-inc.md` | Not clean: ai-right 25, alex-right 5, both-wrong 2. |
| stec | `stec.md` | Not clean: ai-right 22, alex-right 3, both-wrong 2. |
| saks | `saks.md` | Mixed: ai-right 17, alex-right 1, both-defensible 2, both-wrong 2. |

## Follow-Up Implications

No target extraction should start from this state.

Reference-update-only candidates:
- Medivation.
- Mac Gray.

Extraction or prompt/rulebook follow-up indicated by adjudication:
- Imprivata: final-round announcement should be June 24, 2016 from final bid process letters, not the June 12 second-phase advancement and not Alex's extension treatment.
- Zep: non-bid value/unit hygiene, current-process Target Sale anchor, NDA population allocation, dropout handling, BofA IB date, final-round structural row, and go-shop closure treatment need review.
- Providence & Worcester: avoid fresh `Bidder Interest` rows for later contacts with already-active bidders; carry anonymous placeholders through exact-count funnel stages; emit paired `Final Round` when a `Final Round Ann` is inferred.
- Petsmart: overuse of `ConsortiumCA`, missed pre-signing `Sale Press Release`, missed final-round marker rows, and missed Bidder 3 dropout handling.
- STec: avoid `Target Interest` for advisor outreach; classify limited/select-asset exits as `DropTarget`.
- Saks: use full operating acquirer name; clarify temporary consortium membership changes; emit `Final Round` on the submission/deadline date when a final-round announcement requests deadline bids.

Austin-decision items called out:
- Zep: allocation of one non-response among six remaining bidders, and treatment of post-execution go-shop expiry.
- Providence & Worcester: coding Party B's final-stage loss after refusing to increase against G&W's higher offer.

## Verification

Controller-side checks run after extraction/adjudication:
- `python scoring/diff.py --all-reference --no-write`
- Report-section checker over all nine adjudication reports.
- `pytest -q` -> `116 passed in 9.47s`

