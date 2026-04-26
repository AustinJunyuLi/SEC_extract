---
date: 2026-04-26
status: ACTIVE — re-extraction pending on other machine
owner: Austin
predecessor: cb37e2d (handoff: clean reference rerun and adjudication, 2026-04-24)
successor: TBD (after re-extraction validates the 6 decisions)
---

# Handoff: Six Policy Decisions + Cleanup Sweep

This is the working state of `SEC_extract` after a 2026-04-26 session
that landed six cross-deal policy decisions and a cleanup pass. Everything
is committed and pushed to `origin/main`. The next step is to **re-extract
all 9 reference deals** on whichever machine you choose, then verify the
expected diffs below.

---

## What was done

### Six policy decisions (all 🟩 IMPLEMENTED at policy + code level)

Tracker: `quality_reports/decisions/2026-04-26_six-policy-decisions.md`.

| # | Decision | Where it lives in code | What changes for the AI |
|---|---|---|---|
| 1 | Silent NDA signers → emit `DropSilent` (§I1) | `pipeline.py` (`EVENT_VOCABULARY`, `EVENT_RANK`, `BID_NOTE_FOLLOWUPS`, `_invariant_p_s1`); `rules/events.md` §I1; `rules/invariants.md` §P-S1; `prompts/extract.md` Step 7 | Each silent NDA signer gets a follow-up `DropSilent` row (null date, `date_unknown` info flag, re-cited NDA quote). Validator's old `nda_without_bid_or_drop` flag is renamed `missing_nda_dropsilent` (soft safety net only). |
| 2 | `bidder_type.public` is tri-state (`bool \| null`) (§F1/§F2) | `rules/bidders.md` §F1/§F2; `rules/schema.md` §R1; `prompts/extract.md` Non-negotiable constraints; `scripts/build_reference.py` `_bidder_type_note_signals()` | Strict-filing-only: `true` only on explicit "publicly traded"; `false` only on explicit "private company"; `null` otherwise (including silent PE-sponsor rows — KKR / Blackstone / Apollo etc. are listed sponsor firms; "private equity firm" describes fund vehicle, not firm listing). The pre-2026 PE-firm carve-out (`public = false` for every PE-sponsor row) is removed. |
| 3 | `Acquirer` = operating; new `Acquirer_legal` sidecar (§N4) | `rules/schema.md` §R1 + new §N4; `prompts/extract.md` Non-negotiable constraints; `scripts/build_reference.py` §Q6 override + `Acquirer_legal: null` seed; `scoring/diff.py` `COMPARE_DEAL_FIELDS` | `Acquirer` is the operating acquirer (not the Delaware shell). New `Acquirer_legal: string \| null` carries the shell when it differs. For PE consortia, `Acquirer` is the lead sponsor. The 4 sponsor-backed reference deals (petsmart-inc, mac-gray, zep, saks) carry the legal shell separately. |
| 4 | `ConsortiumCA` event type for Type B CAs; skip Type C rollover (§I3, §M5) | `pipeline.py` (`EVENT_VOCABULARY`, `EVENT_RANK`); `rules/events.md` §C1 + new §I3; `rules/bids.md` §M5; `prompts/extract.md` Steps 7 + 9 + self-check; `scripts/build_reference.py` `A3_RANK` | New `bid_note = "ConsortiumCA"` for bidder ↔ bidder consortium-formation CAs (Type B). Type A NDA (target ↔ bidder) unchanged. Type C rollover CAs skipped (no row). ConsortiumCA does not count toward §Scope-1 auction threshold and does not satisfy §P-D6. |
| 5 | Same-price reaffirmations as note-or-row by trigger language (§C5) | `rules/bids.md` new §C5; `prompts/extract.md` Step 8 + self-check | Same-price reaffirmation gets a new `Bid` row ONLY when the filing language describes a substantive response to a narrated process step (e.g., "best and final" deadline, formal final-round letter). Otherwise append to prior bid's `additional_note` (or fold into `Executed` row for pre-signing confirmations). No new vocabulary or flag — the trigger language lives in `additional_note`. |
| 6 | IB date = bank's first action; board approval excluded (§J1) | `rules/events.md` §J1; `prompts/extract.md` Step 2a | IB row's `bid_date_precise` is the bank's earliest narrated action (engagement letter signing, sending process letters, contacting bidders, presenting to committee). Board approval to retain (the target's act, not the bank's) does NOT count. No fallback chain — single rule, observability-driven. |

### Cleanup sweep

- Dropped dead `False if has_private` branch in `scripts/build_reference.py:_bidder_type_note_signals` (Decision #2 follow-through; never triggered by Alex's actual notes).
- Renamed converter test `test_bidder_type_sets_public_false_only_on_private_signal` → `test_bidder_type_pe_token_keeps_public_null` and flipped expected `public` from `False` to `None`.
- Deleted `quality_reports/plans/2026-04-21_validator-hardening-prd.md` (was explicitly `HISTORICAL_DRAFT_NOT_LIVE`).
- Pruned 54 stale `nda_without_bid_or_drop` entries from `state/flags.jsonl`.
- Added scope-clarifier line to `skill_open_questions.md` pointing at `quality_reports/decisions/` for cross-deal policy decisions.

---

## Commits pushed to `origin/main`

```
2876c02 chore(cleanup): post-decision sweep — drop stale code path, PRD, and dead flags
a781567 policy(rules): IB date = bank's first action, board approval excluded (§J1)
2f85696 policy(rules): same-price reaffirmations as note-or-row by trigger language (§C5)
0159ce9 policy(rules): operating Acquirer + Acquirer_legal sidecar (§N4) + ConsortiumCA (§I3)
721a8d2 policy(rules): silent-NDA→DropSilent (§I1) + tri-state public (§F2)
```

Note: a force-push consolidated origin/main. The previous tip `cb37e2d` (handoff: clean reference rerun and adjudication) had parallel foundational work that's now incorporated in our prior commits. Git reflog on this machine retains the old tip.

---

## What to do on the other machine

```bash
cd /path/to/SEC_extract
git fetch origin
git reset --hard origin/main          # ONLY if you have no uncommitted local work
# OR: git pull --ff-only                # if your local is at cb37e2d or earlier on main

# Verify you got the expected state:
git log --oneline -6
# should show: 2876c02, a781567, 2f85696, 0159ce9, 721a8d2, 79d1772

pytest tests/                          # expect: 103 passed
python scripts/build_reference.py --all  # expect: 9 deals, no errors
```

If the test suite does not pass or the reference rebuild errors, **stop and investigate before re-extracting**. The 6 decisions all committed cleanly here, so divergence indicates a pull problem or local file state issue.

---

## Re-extract the 9 reference deals

Per `SKILL.md` and the current pipeline:

```bash
# For each reference deal, in a fresh Claude Code session per deal:
#   1. Spawn Extractor subagent with the slug
#   2. Subagent reads prompts/extract.md + rules/*.md + data/filings/{slug}/
#   3. Subagent emits raw JSON to /tmp/{slug}.raw.json
#   4. Run validator + finalize:
python run.py --slug medivation --raw-extraction /tmp/medivation.raw.json --commit
# Repeat for: imprivata, zep, providence-worcester, petsmart-inc, penford,
#             mac-gray, saks, stec
```

Reset Claude Code context per deal — no cross-deal state in the model.

---

## Expected results after re-extraction

### Validator flag counts

```bash
# Old flag code should be 0 across all 9 deals (already pruned from state/flags.jsonl):
jq -s '[.[] | select(.code=="nda_without_bid_or_drop")] | length' state/flags.jsonl
# expect: 0

# New flag code (safety-net for missing DropSilent emission):
jq -s '[.[] | select(.code=="missing_nda_dropsilent")] | length' state/flags.jsonl
# expect: 0 IF the extractor emitted DropSilent rows correctly per Decision #1.
# Any non-zero count identifies NDAs where the extractor failed to emit the
# required DropSilent row — surface for review.
```

### Per-deal expected changes

| Deal | Expected change after re-extraction |
|---|---|
| **medivation** | DropSilent rows for the silent NDA signers (Sanofi atomization continues; new DropSilent rows attached). `bidder_type.public` should flip to `null` for all unnamed PE-sponsor rows (was `false`). No Acquirer / IB / consortium / reaffirmation changes. |
| **imprivata** | DropSilent rows for the 4 financial sponsors that signed NDAs with no follow-up. `public = null` on all unnamed financial sponsors (was `false`). Acquirer stays `Thoma Bravo, LLC`. |
| **zep** | Heavy DropSilent emission (~19 silent NDA signers). `Acquirer = "New Mountain Capital"` (operating); `Acquirer_legal = "NM Z Parent Inc."` (NEW field). Reaffirmation row from April 2015 → folded into prior best-and-final's `additional_note` (loses 1 row). |
| **providence-worcester** | DropSilent rows (~15 silent signers). `public = null` on previously-`false` rows. CVR-bearing earlier bids do NOT change `all_cash` (still based on final executed deal). |
| **petsmart-inc** | DropSilent rows (small count — most NDAs have explicit follow-ups). `Acquirer = "BC Partners, Inc."` (NEW — was `Argos Holdings Inc.` legal shell); `Acquirer_legal = "Argos Holdings Inc."` (NEW field). The 2 "Longview and the Buyer Group" NDA rows (12/9, 12/12) reclassify to `bid_note = "ConsortiumCA"` — these will diff against Alex's reference (which has them as `NDA`). Adjudicate per filing. |
| **penford** | 1 DropSilent row. October 14 Ingredion confirmation row → folded into `Executed` row's `source_quote`/`additional_note` (loses 1 row). |
| **mac-gray** | DropSilent rows (~16 silent signers). `Acquirer = "CSC ServiceWorks, Inc."` (operating); `Acquirer_legal = "Spin Holdco Inc."` (NEW). Pamplona documented in `Executed` row's `additional_note`. |
| **saks** | 0 DropSilent rows (Saks deals don't show silent signers). `Acquirer = "Hudson's Bay Company"`; `Acquirer_legal = "Harry Acquisition Inc."` (NEW). `public = null` on PE sponsors A/E/G. Morgan Stanley IB date may shift (sharpened-C: pick first narrated action, not "long-time advisor" mention). |
| **stec** | 0 DropSilent rows. Companies A–H now have `public = null` (was `false`). WDC's May 30 best-and-final reaffirmation **stays as a `Bid` row** (Case 3 per §C5) but with reaffirmation context in `additional_note`. WDC IB date should be 03-28 (engagement letter), not 03-26 (board approval) per Decision #6. |

### Diff-noise reduction (vs Alex's reference)

```bash
# Full diff harness across all 9 reference deals:
python scoring/diff.py --all-reference

# Field-level mismatches you should expect to drop substantially:
# - bidder_type.public (was the largest single source — ~302 spurious public=false rows
#   across pre-policy AI extractions; should drop to near-zero after Decision #2)
# - Acquirer for petsmart (Argos Holdings → BC Partners; converges with reference)
# - Acquirer_legal new field populated on 4 sponsor-backed reference deals

# Field-level mismatches that should appear (real adjudication signal):
# - bid_note "NDA" vs "ConsortiumCA" on petsmart Longview rows (real disagreement
#   with Alex; Austin adjudicates per filing)
# - Cardinality changes from DropSilent emission (AI now has more rows than Alex
#   for silent-signer-heavy deals; the diff harness's AI_ONLY_BID_NOTES filter
#   in scoring/diff.py strips them before comparison)
```

### Reference data state

The reference JSONs (`reference/alex/*.json`) were rebuilt this session and now include `Acquirer_legal` for the 4 sponsor-backed deals plus the §Q6 deal_flags. They should be byte-identical when you run `python scripts/build_reference.py --all` on the other machine — that's a sanity check.

---

## Verification checklist

After re-extraction completes on all 9 deals:

- [ ] **Tests pass.** `pytest tests/` → 103 passed.
- [ ] **No `nda_without_bid_or_drop`.** `jq -s '[.[] | select(.code=="nda_without_bid_or_drop")] | length' state/flags.jsonl` → 0.
- [ ] **`missing_nda_dropsilent` is 0** (or you understand why each instance fired).
- [ ] **Reference rebuild bit-identical.** `python scripts/build_reference.py --all` → no `git diff reference/alex/` after.
- [ ] **All 9 deals reach `passed` or `passed_clean`** in `state/progress.json` (or you've recorded the hard flags as adjudication items).
- [ ] **Diff harness:** `bidder_type` mismatches drop substantially; petsmart `Acquirer` aligns; new ConsortiumCA mismatches appear on petsmart Longview rows (real signal, not noise).
- [ ] **Per-deal expectations** in the table above hold; if not, surface the divergence and adjudicate against the SEC filing per `CLAUDE.md`'s ground-truth-epistemology rule.

---

## Known caveats

1. **scoring/results/** is gitignored — local-only diff snapshots from prior runs. They won't transfer; you'll regenerate them on the other machine when you run `python scoring/diff.py --all-reference`.
2. **output/extractions/{slug}.json** are still the pre-policy AI outputs on the other machine before re-extraction. They'll be overwritten by `python run.py` on each re-run.
3. **state/progress.json** carries pre-policy `last_run` timestamps; these update naturally on next pipeline run.
4. **state/flags.jsonl** has been pruned of dead flag codes but otherwise carries pre-policy flag history. New runs append; the `dedup_flags_jsonl.py` script can prune orphans by deal `last_run` if needed (`python scripts/dedup_flags_jsonl.py`).
5. **Petsmart's `Buyer Group` NDA** in Alex's reference may correspond to either Type A or Type B per §I3. If the AI's re-extraction reclassifies any of these as `ConsortiumCA`, the diff will show a cardinality mismatch — this is real adjudication signal, NOT a regression. Read the petsmart filing to assign the verdict per §I3's disambiguation table.
6. **IB date shift on STec** (03-26 → 03-28): expected. Alex used 04-04 (a process date); pre-policy AI used 03-26 (board approval); post-policy AI should use 03-28 (engagement letter). All three differ; sharpened-C produces the legally-clean answer.

---

## If something doesn't match

1. **Tests fail after pull.** Likely a pull conflict or partial pull. `git status` and `git log --oneline -6` should match the SHAs above. If they don't, `git fetch origin && git reset --hard origin/main` (only if no local work to preserve).
2. **Reference rebuild produces a diff.** Likely an `openpyxl` or Python version difference between machines. Both machines should run Python 3.10+; pinned deps in `requirements.txt`.
3. **`missing_nda_dropsilent` fires non-zero on a deal.** The extractor missed emitting required DropSilent rows for that deal's silent NDA signers. Re-spawn the extractor for that deal with explicit attention to §I1; if the issue persists, the prompt's Step 7 may need reinforcement.
4. **Petsmart `Acquirer` is still `Argos Holdings Inc.` after re-extraction.** The extractor missed §N4. Re-spawn with explicit attention to the "operating acquirer not legal shell" non-negotiable in `prompts/extract.md`.
5. **`bidder_type.public` is still mostly `false` after re-extraction.** The extractor missed Decision #2 — re-spawn with explicit attention to the strict-filing-only tri-state non-negotiable.

For any case not covered here, the live contracts are `rules/*.md`, `prompts/extract.md`, `pipeline.py`, `SKILL.md`, `CLAUDE.md`, `state/progress.json`, and the decisions tracker `quality_reports/decisions/2026-04-26_six-policy-decisions.md`. Dated planning docs are snapshots; trust the live contracts over older notes per `CLAUDE.md` conventions.

---

## After re-extraction

If everything matches expectations:
- Mark the run as the start of the 3-consecutive-unchanged-rulebook stability clock (per `CLAUDE.md` exit criteria).
- Re-run `scoring/diff.py --all-reference` and compare the diff against the 04-23 adjudication report (`quality_reports/adjudication/2026-04-23_clean_ref9/`) to confirm noise reduction.
- Open the next session's handoff under `quality_reports/handoffs/` recording the post-re-extraction state.

If the re-extraction surfaces NEW cross-deal patterns not addressed by the 6 decisions, the audit at the end of this session flagged 4 candidate follow-ups (initial-IOI vs Final-Round-Ann conflation; cohort identity continuity in count-only audit rounds; `all_cash` semantics for evolving consideration; data-room-implied NDAs). Decide whether they warrant rule clarifications or adjudication-only treatment per case.
