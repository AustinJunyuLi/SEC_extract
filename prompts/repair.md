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

## Rules and tools

The same SCHEMA_R1 contract applies. The same three tools are available:
`check_row`, `search_filing`, and `get_pages`. You may call them as needed.
After tool calls, emit the complete revised `{{deal, events}}` JSON.

If a flag describes genuine filing ambiguity rather than an extraction error,
emit the best supported row with an explicit flag explaining the ambiguity.
Do not fabricate evidence or bidder identities.
