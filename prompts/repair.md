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

Tool discipline:

- Call `check_obligations` at most once, only after assembling a complete
  candidate extraction. Do not call it on row subsets or partial
  `{{deal, events}}` sketches.
- Call `check_row` on every revised row whose `source_quote`, `source_page`,
  event type, date roughness, bid value fields, or conditional fields changed.
- If `check_row` returns any violation, correct that row before the final
  response.
