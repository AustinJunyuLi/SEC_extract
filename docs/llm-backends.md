# LLM Backends

This repo has two live extraction backends. Backend choice changes only the
provider transport; the prompt, rules, claim schema, quote binding,
canonical graph, validation, and review projection remain the same.

## Default: Claude Agent SDK

```bash
LLM_BACKEND=claude_agent_sdk
python run.py --slug mac-gray --re-extract
python -m pipeline.run_pool --filter reference --workers 1 --re-extract
```

Python calls `pipeline/llm/claude_agent_bridge.mjs`, which imports the
repo-local `@anthropic-ai/claude-agent-sdk` package. The bridge requests strict
structured output, disables project settings, blocks ordinary tools, and allows
only the SDK's structured-output tool.

Authentication is runtime-only:

- existing Claude Max login, when available;
- or `ANTHROPIC_API_KEY`, when set.

Do not write credentials into tracked files, audit reports, prompts, or docs.

## Optional: Direct OpenAI

```bash
LLM_BACKEND=openai
OPENAI_API_KEY=...
python run.py --slug mac-gray --re-extract --llm-backend openai
python -m pipeline.run_pool --filter reference --workers 1 --llm-backend openai --re-extract
```

The OpenAI backend uses the first-party OpenAI Responses API directly. It
requires `OPENAI_API_KEY`. Compatible-base-url configuration is not supported.

## Runtime Knobs

- `EXTRACT_MODEL`: optional for Claude Agent SDK; defaults to `gpt-5.5` for
  direct OpenAI when unset.
- `EXTRACT_REASONING_EFFORT`: defaults to `high`.
- Claude Agent SDK supports `none`, `low`, `medium`, `high`, and `xhigh`.
- Direct OpenAI supports `none`, `minimal`, `low`, `medium`, and `high`.

Unsupported backend/effort combinations fail before any provider call.

## Contract Invariants

Every backend must return exactly this strict claim payload:

```json
{
  "actor_claims": [],
  "event_claims": [],
  "bid_claims": [],
  "participation_count_claims": [],
  "actor_relation_claims": []
}
```

Python owns source spans, canonical IDs, claim dispositions, coverage results,
graph rows, validation, and review output. Do not add fallback readers,
provider correction paths, or compatibility shims.
