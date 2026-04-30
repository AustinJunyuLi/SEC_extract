# SCHEMA_R1 Strict-Mode Baseline — 2026-04-30

Schema commit: `52ceaa7`

Live provider: Linkflow Responses proxy at `https://www.linkflow.run/v1`
with `gpt-5.5`, `reasoning.effort=medium`, and strict
`text.format=json_schema`.

## Probe Artifacts

| Slug | Artifact | Input tokens | Output tokens | Reasoning tokens | Result |
|---|---|---:|---:|---:|---|
| `medivation` | `2026-04-30_schema_r1_baseline_medivation.json` | 41691 | 10199 | 3164 | `status=ok`, `parses=true` |
| `providence-worcester` | `2026-04-30_schema_r1_baseline_providence-worcester.json` | 44700 | 3565 | 3368 | `status=ok`, `parses=true` |
| `petsmart-inc` | `2026-04-30_schema_r1_baseline_petsmart-inc.json` | 44493 | 2257 | 2070 | `status=ok`, `parses=true` |

## Linkflow Field Softenings

Initial probes against the pre-hardened `SCHEMA_R1` produced repeatable
Cloudflare 502s. Isolation probes showed these schema constructs were the
provider-hostile pieces:

- `oneOf` for `source_quote` / `source_page`.
- Schema-valued or open `additionalProperties` for dynamic objects.
- Fixed canonical registry keys such as `bidder_01` under a strict object.

The accepted baseline therefore:

- Replaces `oneOf` quote/page fields with JSON Schema type unions
  (`string | array`, `integer | array`) and item constraints.
- Adds `maxLength: 1500` to quote strings and quote-list items.
- Tightens enums for `bid_value_unit` and `consideration_components`.
- Makes `unnamed_nda_promotion` a required nullable slot.
- Leaves `deal.bidder_registry` as an empty strict object in the provider
  schema. Python must rebuild/enforce the live registry contract before
  validation/finalization.

The failed live attempts are preserved in:

- `2026-04-30_schema_r1_baseline_medivation_attempt1_502.json`
- `2026-04-30_schema_r1_baseline_medivation_attempt2_502.json`
