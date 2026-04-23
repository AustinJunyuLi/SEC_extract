---
date: 2026-04-21
status: COMPLETE — all 9 reference deals adjudicated
owner: Codex
source_cutoff: quality_reports/adjudication/2026-04-21_rerun/CUTOFF_REPORT.md
---

# MASTER_RERUN — final rerun adjudication

## Cleanup
- The previous temporary restart packets in this folder were removed and replaced with completed adjudication reports.
- `CUTOFF_REPORT.md` was kept as historical context only.

## Per-deal dispositions
| Deal | Disposition | Current status | Hard | Soft | Info | Notes |
|---|---|---|---|---|---|---|
| providence-worcester | ship-ready / reference-refresh | passed | 0 | 2 | 60 | Ship-ready after reference refresh; the live rerun now matches the filing well. |
| medivation | ship-ready / reference-refresh | passed | 0 | 10 | 8 | Ship-ready after reference refresh; no extraction blocker remains. |
| imprivata | fix-and-rerun | passed | 0 | 3 | 15 | Fix and rerun. Two material filing-truth issues remain in the live rerun. |
| zep | fix-and-rerun | passed | 0 | 66 | 48 | Fix and rerun. The current saved extraction still misses material round-structure and final-bid formality details. |
| petsmart-inc | ship-ready / judgment-call | passed | 0 | 1 | 55 | Ship-ready with a judgment-call note on unnamed-party dropout atomization. |
| penford | blocked / fix-and-rerun | validated | 6 | 14 | 19 | Blocked. Fix and rerun before treating this deal as adjudicated-good. |
| mac-gray | targeted-fix | passed | 0 | 35 | 16 | Targeted extractor fix recommended, but the current rerun is otherwise directionally strong. |
| saks | hot-fix | passed | 0 | 13 | 24 | Hot-fix one row and rerun; otherwise the current row set is strong. |
| stec | targeted-fix | passed | 0 | 3 | 13 | Targeted extractor fix recommended before calling the deal fully clean. |

## System-wide adjudication findings
- `TargetName`/`Acquirer` casing differences and Alex-side `DateEffective` population are mostly reference/converter noise, not extraction defects.
- The live rerun materially improved the earlier snapshot on `providence-worcester`, `petsmart-inc`, and `stec` by adding missing process structure and prehistory.
- The live rerun still needs extraction-side fixes on `imprivata`, `zep`, `penford`, `mac-gray`, `stec`, and `saks` before the reference set can be called stable.
- `penford` is still the only hard-blocked deal; its blocker is real and not just diff noise.

## Next actions
1. Fix the extraction-side issues called out in `imprivata`, `zep`, `penford`, `mac-gray`, `stec`, and `saks`.
2. Refresh the reference side for the confirmed Alex/converter defects in `medivation`, `providence-worcester`, `mac-gray`, `petsmart-inc`, and `saks`.
3. Re-run the 9-reference set only after those fixes land; that is the earliest point where the 3-clean-run stability clock can restart honestly.

## Report set
- `quality_reports/adjudication/2026-04-21_rerun/providence-worcester.md` — ship-ready / reference-refresh
- `quality_reports/adjudication/2026-04-21_rerun/medivation.md` — ship-ready / reference-refresh
- `quality_reports/adjudication/2026-04-21_rerun/imprivata.md` — fix-and-rerun
- `quality_reports/adjudication/2026-04-21_rerun/zep.md` — fix-and-rerun
- `quality_reports/adjudication/2026-04-21_rerun/petsmart-inc.md` — ship-ready / judgment-call
- `quality_reports/adjudication/2026-04-21_rerun/penford.md` — blocked / fix-and-rerun
- `quality_reports/adjudication/2026-04-21_rerun/mac-gray.md` — targeted-fix
- `quality_reports/adjudication/2026-04-21_rerun/saks.md` — hot-fix
- `quality_reports/adjudication/2026-04-21_rerun/stec.md` — targeted-fix
