# Repair turn prompt

You produced a draft extraction that failed Python validation with the hard
flags listed below. Emit a complete revised extraction that addresses every
hard flag. Do not emit patches or partial output. Re-emit the full
`{{deal, events}}` JSON body matching SCHEMA_R1.

## Validator report

{validator_report}

## Affected event rows from your previous draft

{affected_rows}

## Filing snippets for affected rows

{filing_snippets}

## Repair turn modes

Repair turn 1 has no tools. Use the validator report, affected rows, and filing
snippets in this prompt to emit the complete revised `{{deal, events}}` JSON.

Repair turn 2 may use targeted repair tools if hard flags remain after repair
turn 1:

- `check_row` only for hard-flagged rows, directly revised rows, and rows whose
  validity depends on those revisions.
- `search_filing` for targeted evidence lookup.
- `get_pages` for page context after targeted search or when a cited page needs
  surrounding context.

The same SCHEMA_R1 contract applies in both repair turns. After any repair-2
tool calls, emit the complete revised `{{deal, events}}` JSON.

If a flag describes genuine filing ambiguity rather than an extraction error,
emit the best supported row with an explicit flag explaining the ambiguity.
Do not fabricate evidence or bidder identities.
