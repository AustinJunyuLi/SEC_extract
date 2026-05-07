# For Alex Gorbenko: how to read what's in this folder

Two self-contained HTML reports about the M&A bidding extraction
pipeline and the consolidated review CSV.

## Open these in a browser

| File | What it is | Read this when |
|---|---|---|
| **`pipeline_overview.html`** | A jargon-free walkthrough of the extraction pipeline — what each component does, how validation works, what the verification gate guarantees, and where every artefact lives. | You want to understand *how* the rows in the CSV were produced and what the project's trust posture is. |
| **`csv_user_manual.html`** | A column-by-column and code-by-code reference for `output/review_csv/alex_event_ledger_ref9_plus_targets5.csv`, with at least one worked-example row from the actual file for every coded value. | You want to *read the CSV* and need a definitive gloss for any column or code. Ends with a section on the AI-assisted review path (Claude Desktop / Claude Code / DuckDB). |

Both files are standalone — every diagram and stylesheet is embedded —
so you can email or move them anywhere and they will still render.
Each is roughly 4.7 MB.

## Suggested reading order

1. Skim **`pipeline_overview.html`** §1 (executive summary) and §2
   (architecture). 10 minutes.
2. Open the CSV in Excel/Numbers, sort by `deal_slug`+`event_order`,
   and pick a deal you know — `mac-gray` or `petsmart-inc` are good
   starting points (37 and 33 rows respectively).
3. Switch to **`csv_user_manual.html`** §3 (worked row) and §4
   (column reference). Use it as the gloss while you scan the CSV.
4. When something looks off, jump to §5 (`event_code` reference)
   for the definition + the worked example for that code.
5. For structural questions a spreadsheet can't answer, see §7 (AI-
   assisted review path) for how to use Claude Desktop / Claude Code
   on the JSONL or DuckDB artefacts.

## What's authoritative

The hierarchy from the project's working contract (`AGENTS.md`):

> **SEC filing > canonical extraction graph > Alex CSV > legacy 2026
> workbook (calibration only)**

When the CSV and your 2026 workbook disagree, the filing decides;
the workbook is calibration material, not an oracle.

## Source files (in this folder)

- `pipeline_overview.qmd` — Quarto source for the pipeline overview.
- `csv_user_manual.qmd` — Quarto source for the user manual.
- `assets/*.svg` — polished flowcharts embedded into the standalone
  HTML reports.
- `scripts/build_flowcharts.py` — deterministic SVG generator for the
  report diagrams.

To regenerate the HTML files after editing the QMDs:

```bash
cd quality_reports/for-alex
python scripts/build_flowcharts.py
quarto render pipeline_overview.qmd
quarto render csv_user_manual.qmd
```
