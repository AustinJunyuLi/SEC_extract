# Reference Verification Reports

This directory stores canonical agent filing-grounded verification reports for
the nine reference deals. A reference deal may receive `verified: true`
metadata only when its report exists, cites the current extraction run, checks
calibration disagreements against filing text and the rulebook, and the report
concludes `Conclusion: VERIFIED`.

Each report must be named:

```text
quality_reports/reference_verification/{slug}.md
```

Required sections:

- `# {slug} Agent Verification`
- `## Run Metadata`
- `## Commands`
- `## Extraction And Flag Summary`
- `## Filing-Grounded Calibration Ledger`
- `## Filing Evidence Review`
- `## Contract Updates`
- `## Conclusion`

Run this check before marking any reference deal verified:

```bash
python scripts/check_reference_verification.py --slugs {slug}
```

Run this check before final release:

```bash
python scripts/check_reference_verification.py
```
