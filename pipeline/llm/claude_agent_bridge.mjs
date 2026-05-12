import { query } from "@anthropic-ai/claude-agent-sdk";

async function readStdin() {
  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString("utf8");
}

function usageValue(usage, name) {
  if (!usage || usage[name] == null) {
    return 0;
  }
  return Number(usage[name]) || 0;
}

function outputFormatFromTextFormat(textFormat) {
  if (!textFormat || textFormat.type !== "json_schema" || textFormat.strict !== true || !textFormat.schema) {
    throw new Error("strict json_schema text_format is required");
  }
  return {
    type: "json_schema",
    schema: textFormat.schema,
  };
}

async function main() {
  const request = JSON.parse(await readStdin());
  const options = {
    systemPrompt: request.system,
    outputFormat: outputFormatFromTextFormat(request.text_format),
    tools: [],
    allowedTools: [],
    mcpServers: {},
    permissionMode: "dontAsk",
    settingSources: [],
    canUseTool: async (toolName, input, context) => {
      if (toolName === "StructuredOutput") {
        return { behavior: "allow", updatedInput: input, toolUseID: context?.toolUseID };
      }
      return {
        behavior: "deny",
        message: "Extraction backend tools are disabled.",
        interrupt: true,
        toolUseID: context?.toolUseID,
      };
    },
  };
  if (request.model) {
    options.model = request.model;
  }
  if (request.thinking) {
    options.thinking = request.thinking;
  }
  if (request.max_output_tokens != null) {
    options.maxOutputTokens = request.max_output_tokens;
  }

  const outputItems = [];
  let resultMessage = null;
  for await (const message of query({ prompt: request.user, options })) {
    outputItems.push(message);
    if (message.type === "result") {
      resultMessage = message;
    }
  }

  if (!resultMessage) {
    throw new Error("Claude Agent SDK returned no result message");
  }
  if (resultMessage.subtype !== "success" || resultMessage.structured_output == null) {
    throw new Error(`Claude Agent SDK structured output failed: ${resultMessage.subtype || "unknown"}`);
  }

  const usage = resultMessage.usage || {};
  const structured = resultMessage.structured_output;
  process.stdout.write(JSON.stringify({
    text: JSON.stringify(structured),
    structured_output: structured,
    model: resultMessage.model || request.model || "claude_agent_sdk_default",
    input_tokens: usageValue(usage, "input_tokens"),
    output_tokens: usageValue(usage, "output_tokens"),
    reasoning_tokens: usageValue(usage, "reasoning_tokens"),
    finish_reason: resultMessage.subtype,
    output_items: outputItems,
    raw_response: resultMessage,
  }));
}

main().catch((error) => {
  process.stderr.write(`${error && error.stack ? error.stack : error}\n`);
  process.exit(1);
});
