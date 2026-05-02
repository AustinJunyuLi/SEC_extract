# Obligation-gated repair prompt

You produced a complete draft extraction that failed deterministic Python
checks. Emit one complete revised extraction. Do not emit patches or partial output.
Return the strict repair response object with `deal`, `events`, and
`obligation_assertions`.

## Validator report

{validator_report}

## Obligation report

{obligation_report}

## Protected row conservation anchors

{conservation_report}

## Previous complete extraction

{previous_extraction}

## Deterministic filing pages

{filing_pages}

## Tool access

This is the only repair round: one repair round with access to all four tools.
Repair has access to all four tools:

- `check_row(row)`
- `search_filing(query, page_range, max_hits)`
- `get_pages(start_page, end_page)`
- `check_obligations(candidate_extraction)`

Use tools when needed, then emit the full corrected extraction. Do not
fabricate evidence, bidder identities, or obligation waivers. Do not revisit
clean rows or optional fields unless a deterministic report requires the
change. Python reruns validation, obligations, and row-conservation checks
after this response.

Conservation discipline:

- Treat every protected row-conservation anchor as a row that must survive
  unless the validator report specifically says that anchored row is invalid.
- When fixing aggregate buyer-group rows, split only the offending aggregate
  row(s). Preserve unrelated bidder rows, dates, source pages, and quote
  anchors exactly where possible.
- Do not delete or rewrite an unrelated protected `Bid`, `Drop`, `NDA`,
  `ConsortiumCA`, or `Executed` row while repairing buyer-group atomization.

Anonymous-handle discipline:

- Do not create an unnamed lifecycle row for a numbered alias that lacks a
  prior same-phase `NDA` handle.
- If buyer-group atomization or filing party counts make the anonymous balance
  unclear, reuse compatible open NDA handles first. If any remaining row is
  genuinely ambiguous, attach `anonymous_cohort_identity_ambiguous`; otherwise
  omit unsupported extra anonymous lifecycle rows.
- Advisor language saying representatives spoke with all parties, including
  non-submitters, is not by itself an extra exact-count `Drop` obligation.

Conditional-field discipline:

- On every non-`Bid` row, including `Executed`, `NDA`, `Drop`, `DropSilent`,
  `Final Round`, `ConsortiumCA`, `Target Sale`, `Target Sale Public`, and
  `Press Release`, set `bid_value`, `bid_value_pershare`, `bid_value_lower`,
  `bid_value_upper`, `bid_value_unit`, and `consideration_components` to
  `null`.
- Do not copy the signed merger price into an `Executed` row's bid-economics
  fields. Preserve the price in `source_quote` or `additional_note` only.
- Before emitting the final repair JSON, scan every revised non-`Bid` row for
  these six fields and null them.

Tool discipline:

- Call `check_obligations` at most once, only after assembling a complete
  candidate extraction. Do not call it on row subsets or partial
  `{{deal, events}}` sketches.
- Call `check_row` on every revised row whose `source_quote`, `source_page`,
  event type, date roughness, bid value fields, or conditional fields changed.
- If `check_row` returns any violation, correct that row before the final
  response.
