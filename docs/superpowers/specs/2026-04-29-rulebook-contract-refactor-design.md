# Rulebook Contract Refactor Design

## Purpose

This refactor makes the extraction system stricter, simpler, and less patch-like.
The goal is not to add more process around the rulebook. The goal is to make
one live contract govern the prompt, validator, reference JSONs, review exports,
and documentation.

The design follows the current no-backward-compatibility doctrine: when the
schema, prompt, rulebook, output format, state format, or artifact contract
changes, stale formats are deleted or regenerated. There are no compatibility
readers, fallback paths, deprecated aliases, or hidden migrations.

## Scope

In scope:

- Rulebook consolidation across `rules/*.md`.
- Prompt slimming in `prompts/extract.md`.
- Validator/schema hardening in Python.
- Reference JSON regeneration through `scripts/build_reference.py`.
- Generated artifact cleanup after contract changes.
- Minimal Alex-facing review CSV rendering.
- Documentation cleanup in `AGENTS.md`, `CLAUDE.md`, `SKILL.md`, and the
  Linkflow guide.

Out of scope:

- Running the 392 target deals.
- Adding a new rule engine.
- Adding a compatibility framework.
- Adding pre-commit rule inlining machinery.
- Adding structured flag payloads in this refactor.
- Turning the review CSV into a full spreadsheet product.

## Design Principles

1. **One owner per behavior.** Each recurring extraction behavior has one owning
   rule section. Other files may point to that section but may not restate it.
2. **Prompt is operational.** The extractor prompt tells the model how to
   produce output and where to look. It is not a second rulebook.
3. **Python enforces structure.** The model owns reading and judgment. Python
   owns schema, enum, nullability, stale-field, flag-vocabulary, and deterministic
   invariant enforcement.
4. **No fallback compatibility.** Stale labels, stale fields, stale artifacts,
   and old placeholder behavior fail or are deleted.
5. **Reference data is regenerated projection.** Alex's raw workbook and PDF are
   source artifacts. `reference/alex/*.json` is generated under the current
   schema and rulebook.
6. **Review output is display-only.** Alex-facing CSVs help humans review rows;
   they do not introduce new extraction semantics or identities.

## Rule Owner Map

The refactor uses owning sections, not merely owning files:

| Pathway | Owner section |
|---|---|
| No-NDA / unsolicited / inquiry-skip | `rules/events.md` §D1 |
| NDA / CA classification | `rules/events.md` §I3 |
| Advisor and legal-counsel role handling | `rules/events.md` §J1 and §J2, consolidated |
| Bid classification | `rules/bids.md` §G1 and §G2, consolidated |
| Drop / DropSilent | `rules/events.md` §I1 |
| Consortium / unnamed-party identity | `rules/bidders.md` §E2 and §E5 |
| Final-round status | `rules/events.md` §K1 and §K2 |
| Evidence and citation | `rules/schema.md` §R3 |
| Validator behavior | `rules/invariants.md` |
| AI-vs-Alex comparison suppression | `scoring/diff.py` |

Once a behavior has an owner, other docs use cross-references only. They do not
paraphrase the rule.

## Core Doctrine Choices

### Exact-Count Unnamed Parties

Exact-count unnamed parties use `bidder_name = null` until revealed or promoted.
They are count-bound placeholders, not persistent canonical bidder identities.

Example: if a filing says "fifteen financial sponsors executed confidentiality
agreements," the extraction emits fifteen placeholder NDA rows. Those rows may
use aliases such as `Financial 1`, `Financial 2`, and so on, but they do not
receive fake `bidder_XX` identities unless a later filing passage supports
promotion to a named bidder.

If a later named bidder should inherit an earlier unnamed NDA placeholder, the
model uses `unnamed_nda_promotion`. Successful promotion leaves visible audit
residue in the finalized output as an info flag named
`nda_promoted_from_placeholder`, so Alex can see the linkage.

There is no hidden compatibility with old canonical-placeholder behavior. Deals
that currently over-register exact-count placeholders, such as prior imprivata,
zep, or petsmart-inc outputs, must be re-extracted under the new contract.

### Alex-Facing Display

The internal null-placeholder doctrine should not create confusing blanks in
review CSVs. The renderer computes display-only labels such as:

- `Unnamed financial sponsor 3`
- `Unnamed strategic bidder 2`
- `Unnamed party`
- `Party A - promoted from unnamed placeholder`

These labels are not canonical identities and must not be written back into the
extraction JSON.

## Prompt Contract

`prompts/extract.md` becomes an operating prompt. It keeps instructions needed
at generation time:

- produce one JSON object with `deal`, `events`, and `bidder_registry`;
- follow the rulebook sections included in the SDK system message;
- cite every event with `source_quote` and `source_page`;
- keep quotes within the 1500-character hard cap;
- use null placeholders for exact-count unnamed parties;
- use `unnamed_nda_promotion` only when support exists;
- emit only documented fields and documented flag codes;
- do not invent dates, bid values, bidder identities, or legacy labels.

The current SDK call already concatenates `prompts/extract.md` with:

- `rules/schema.md`
- `rules/events.md`
- `rules/bidders.md`
- `rules/bids.md`
- `rules/dates.md`

`rules/invariants.md` remains validator-facing and is not included in the
extractor prompt. The refactor should add or preserve tests that assert this
prompt assembly contract.

The prompt should not restate long-form doctrine for consortiums, DropSilent,
formal-stage status, drop classification, comparator noise, or reference-deal
examples. If a compact checklist is necessary, it should point to the owning
section rather than become a second canonical tree.

## Validator and Code Contract

Python becomes the deterministic enforcement layer for the live rulebook.

Required enforcement:

- full event schema validation because Linkflow uses prompt-only JSON;
- required fields, allowed enum values, nullability, and unknown-field rejection;
- closed extractor and validator flag vocabulary;
- strict `bid_type` validation;
- bid-value shape validation;
- `bid_value_unit` validation;
- DropSilent row-shape validation;
- advisor / legal-counsel role validation under the consolidated §J1/§J2
  doctrine;
- hard failure for canonical IDs on pure exact-count placeholder rows;
- successful `unnamed_nda_promotion` behavior with visible final-output trace;
- narrowed adjudicator routing to true semantic soft flags only.

The validator must not contain AI-vs-Alex comparator behavior. Comparator
suppression belongs in `scoring/diff.py`.

No compatibility tests should be added for old formats. Tests should assert that
old formats fail loudly.

## Reference and Artifact Contract

After contract changes, reference JSONs and generated artifacts must be handled
in order:

1. Update rules, schema, prompt, validator, and tests atomically.
2. Regenerate `reference/alex/*.json` from `scripts/build_reference.py`.
3. Delete stale generated extraction, audit, state, scoring, and review outputs.
4. Re-extract the nine reference deals under the new contract.
5. Generate AI-vs-Alex diff reports.
6. Render Alex-facing review CSVs.

This order matters. Re-extracting under the new contract while comparing against
old reference JSONs produces misleading diff output.

Keep:

- `seeds.csv`
- `data/filings/`
- `reference/CollectionInstructions_Alex_2026.pdf`
- `reference/deal_details_Alex_2026.xlsx`
- `reference/alex/alex_flagged_rows.json`
- source code, rule files, prompts, scripts, tests, and `.env`

Delete or regenerate:

- `reference/alex/*.json` other than `alex_flagged_rows.json`
- `output/extractions/*.json`
- `output/audit/*`
- `state/progress.json`
- `state/flags.jsonl`
- `logs/*`
- `scoring/results/*`
- `output/review_csv/*`

`--re-validate` must refuse stale audit cache entries whose recorded
`rulebook_version` does not match the current rulebook. Audit cache invalidation
after a contract change is mandatory, not optional.

## Minimal Review CSV Contract

Add a deterministic renderer:

```text
scripts/render_review_csv.py
```

Inputs:

```text
output/extractions/{slug}.json
```

Outputs:

```text
output/review_csv/{slug}.csv
output/review_csv/_combined.csv
```

The renderer is a pure projection. It does not repair extraction data, infer
missing facts, or create canonical identities. If required input fields are
missing or inconsistent, it fails.

Initial column set:

```text
slug
BidderID
bid_date_precise
bid_date_rough
bidder_display
bidder_name
bidder_alias
process_phase
role
bid_note
bid_type
bid_value_pershare
bid_value_lower
bid_value_upper
bid_value
bid_value_unit
consideration_components
drop_initiator
drop_reason_class
final_round_announcement
final_round_extension
final_round_informal
invited_to_formal_round
submitted_formal_bid
press_release_subject
exclusivity_days
source_page
source_quote
flags_codes
flag_severities
```

`flags_codes` is semicolon-joined. `flag_severities` uses compact counts such as
`H=0;S=2;I=4`. Full flag reasons stay in JSON to avoid very large CSV cells.

No styling, Excel formatting, or manual notes columns are included in v1.

## Documentation Cleanup Contract

`AGENTS.md`, `CLAUDE.md`, `SKILL.md`, and `docs/linkflow-extraction-guide.md`
describe architecture, workflow, commands, safety gates, and where live
contracts live. They are not rulebooks.

Keep in docs:

- direct SDK architecture;
- Linkflow/NewAPI configuration;
- safe commands;
- reference-set gate;
- no-backward-compatibility doctrine;
- API-key safety;
- regeneration order;
- source-vs-generated artifact distinctions;
- repo layout.

Delete from docs:

- current consortium doctrine;
- current DropSilent doctrine;
- current formal-stage-status doctrine;
- current drop-classification doctrine;
- current comparison-noise doctrine;
- deal-specific extraction examples;
- old session-log rationales;
- stale architecture or output-format text;
- duplicated comparator suppression prose.

Move comparator suppression behavior into `scoring/diff.py`, with concise
comments near each suppression helper explaining why that suppression exists.

## Implementation Order

Use logical commits:

1. **Contract consolidation**
   - rules, schema, prompt;
   - owner sections;
   - duplicate doctrine deletion;
   - closed flag definitions;
   - null-placeholder doctrine.

2. **Code enforcement**
   - validator hardening;
   - schema checks;
   - closed flag vocabulary;
   - bid and DropSilent checks;
   - role checks;
   - narrowed adjudicator routing;
   - tests.

3. **Reference regeneration**
   - `scripts/build_reference.py`;
   - regenerated `reference/alex/*.json`;
   - converter tests/fixtures where needed.

4. **Review CSV and comparator docs**
   - `scripts/render_review_csv.py`;
   - persistent diff output behavior;
   - comparator suppression docs in `scoring/diff.py`;
   - tests.

5. **Documentation cleanup and artifact cleanse**
   - `AGENTS.md`;
   - `CLAUDE.md`;
   - `SKILL.md`;
   - `docs/linkflow-extraction-guide.md`;
   - generated artifact deletion/regeneration.

## Verification

Before claiming the implementation complete, run:

```bash
python -m pytest -x
python -m pipeline.run_pool --filter reference --workers 4 --dry-run
rg -n "sk-[A-Za-z0-9]{20,}|OPENAI_API_KEY=.*[A-Za-z0-9]{20,}|--raw-extraction|--print-extractor-prompt|build_extractor_prompt|Claude Code subagent|No model SDK calls" .
```

Also run these contract-specific commands after implementing the required
interfaces:

```bash
python scripts/build_reference.py --all
python scripts/render_review_csv.py --all
python scoring/diff.py --all-reference --write
```

Do not run the 392 target deals. Do not run real extraction unless Austin
explicitly asks after the refactor is committed.

The reference-set gate remains: all nine reference deals must be manually
verified, hard invariants must pass, and the rulebook must remain unchanged
across three consecutive clean full-reference runs before target-deal extraction
begins.
