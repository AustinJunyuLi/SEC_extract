# For Alex Gorbenko: how to read what's in this folder

Two self-contained, **interactive** HTML reports about the M&A bidding
extraction pipeline and the consolidated review CSV. Hand-rolled HTML/CSS/JS,
no framework, no build server — open them in any modern browser and they
work, including from `file://`, email, or a USB stick.

## Open these in a browser

| File | What it is | Read this when |
|---|---|---|
| **`pipeline_overview.html`** | A jargon-free walkthrough of the extraction pipeline — what each component does, how validation works, what the verification gate guarantees, and where every artefact lives. Sticky outline that tracks scroll, hover-card glossary on every term, full-text search, three expandable sample artefacts (`pages.json`, `flags.jsonl`, a canonical-graph node). | You want to understand *how* the rows in the CSV were produced and what the project's trust posture is. |
| **`csv_user_manual.html`** | A column-by-column and code-by-code reference for `output/review_csv/alex_event_ledger_ref9_plus_targets5.csv`, with the entire CSV embedded inline. Two-pane layout: manual on the left, live filterable table on the right. Click any column → see live distribution and sample rows. Click any `event_code` → see the worked example, then "show all rows in the data pane" to filter the table. Click a cell → manual scrolls to that column's definition. | You want to *read the CSV* and need a definitive gloss for any column or code, with the underlying rows one click away. Ends with a section on the AI-assisted review path (Claude Desktop / Claude Code / DuckDB). |

Both files are standalone — every diagram, stylesheet, script, and the
entire CSV are embedded — so you can email them or move them anywhere and
they will still render. **`pipeline_overview.html`** is ~150 KB;
**`csv_user_manual.html`** is ~340 KB (most of it is the CSV).

## Suggested reading order

1. Skim **`pipeline_overview.html`**: use the sticky outline (left) to jump
   to "Executive summary" and "Architecture: three layers". 10 minutes.
2. Open **`csv_user_manual.html`** alongside. The right pane has the full
   CSV pre-loaded; sort by `deal_slug` + `event_order`, pick a deal you know
   — `mac-gray` or `petsmart-inc` are good starts (37 and 33 rows).
3. Click into the column reference (left pane) for any unfamiliar column;
   click into an `event_code` chip to see its worked example and pull every
   matching row into the right pane.
4. When something looks off, type the suspect value into the search bar in
   either report — the manual's search highlights matching prose; the
   right-pane "quote / party / value substring" filter narrows the table.
5. For structural questions a spreadsheet can't answer, the manual's §"AI-
   assisted review path" walks through Claude Desktop on the JSONL,
   Claude Code on the repo, and the DuckDB CLI.

## What's authoritative

The hierarchy from the project's working contract (`AGENTS.md`):

> **SEC filing > canonical extraction graph > Alex CSV > legacy 2026
> workbook (calibration only)**

When the CSV and your 2026 workbook disagree, the filing decides; the
workbook is calibration material, not an oracle.

## Source layout

```
quality_reports/for-alex/
├── prose/                              prose narrative — plain Markdown
│   ├── pipeline_overview.md
│   └── csv_user_manual.md
├── data/                               structured content for interactive panels
│   ├── glossary.yaml                   ~38 terms, hover-card definitions
│   ├── columns.yaml                    28 CSV columns + 12 enum value tables
│   ├── event_codes.yaml                24 event_codes with worked examples
│   └── figures.yaml                    figure metadata + section back-links
├── fixtures/                           sample artefacts for inline expansion
│   ├── pages_json_sample.json
│   ├── flags_jsonl_sample.json
│   └── canonical_graph_node.json
├── assets/                             SVG flowcharts (deterministic from script)
│   └── *.svg
├── static/                             CSS + JS, inlined into the HTMLs at build
│   ├── styles.css
│   ├── overview.js
│   └── manual.js
├── templates/                          Jinja2 shells
│   ├── pipeline_overview.html.j2
│   └── csv_user_manual.html.j2
├── scripts/
│   ├── build_alex_reports.py           build the two HTML files
│   └── build_flowcharts.py             regenerate the SVG flowcharts
├── pipeline_overview.html              (built artefact, gitted)
├── csv_user_manual.html                (built artefact, gitted)
└── README.md                           (this file)
```

## Rebuild

```bash
# 1. Generate the consolidated CSV from the latest extractions:
cd <repo root>
python scripts/export_alex_event_ledger.py --scope all \
    --output output/review_csv/alex_event_ledger_ref9_plus_targets5.csv

# 2. (Optional) regenerate the SVG flowcharts:
python quality_reports/for-alex/scripts/build_flowcharts.py

# 3. Rebuild the HTML reports:
python quality_reports/for-alex/scripts/build_alex_reports.py
```

The build script reads inputs deterministically — same inputs in, byte-identical
HTML out. Build time is under 2 seconds. No network, no Quarto, no Node.

Python deps used (all already in the project's `requirements.txt`):
`mistune`, `jinja2`, `PyYAML`.

## What to edit when

- **Prose typo or rewrite:** edit `prose/pipeline_overview.md` or
  `prose/csv_user_manual.md`, then rebuild.
- **New jargon term to add to the hover glossary:** add an entry to
  `data/glossary.yaml`. Every occurrence in the prose gets wrapped automatically.
- **New CSV column or coded value:** edit `data/columns.yaml` (column
  metadata + enum value blocks) and `data/event_codes.yaml`. The manual's
  interactive panels rebuild from these.
- **New SVG flowchart:** add to `quality_reports/for-alex/scripts/build_flowcharts.py`,
  rerun it, then add an entry to `data/figures.yaml` with the section back-link.
- **Layout / styling:** edit `static/styles.css`. CSS is hand-rolled — no
  framework, no build pipeline, full control.
- **New interactive behavior:** edit `static/overview.js` or
  `static/manual.js`. Vanilla JS — no Alpine, no React, no transpilation.
