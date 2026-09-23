import type OpenAI from "openai";
import type { Tool } from "@modelcontextprotocol/sdk/types.js";

import type { CheckpointStore } from "./checkpoint.js";
import {
  type AgentStatus,
  type AssistantMessage,
  type ChatMessage,
  type PendingToolResult,
} from "./status.js";

type ChatCompletionTool =
  OpenAI.Chat.Completions.ChatCompletionTool;

type FunctionToolCall =
  OpenAI.Chat.Completions.ChatCompletionMessageFunctionToolCall;

type ToolCall =
  OpenAI.Chat.Completions.ChatCompletionMessageToolCall;

export const READ_ONLY_TOOLS = new Set([
  "calculator",
  "get_time",
  "read_file",
  "list_files",
  "list_directories",
  "list_directory",
  "search_file",
]);

export interface ToolSession {
  callTool(params: {
    name: string;
    arguments?: Record<string, unknown>;
  }): Promise<unknown>;
}

export async function think(
  state: AgentStatus,
  client: OpenAI,
  tools: ChatCompletionTool[],
): Promise<AgentStatus> {
  console.log(`\n===== STEP ${state.step} THINK =====`);

  const response = await client.chat.completions.create({
    model: "deepseek-flash",
    messages: state.messages,
    tools,
  });

  state.lastMessage = response.choices[0].message;
  state.status = state.lastMessage.tool_calls?.length
    ? "ACT"
    : "END";

  return state;
}

export async function act(
  state: AgentStatus,
  session: ToolSession,
): Promise<AgentStatus> {
  console.log(`\n===== STEP ${state.step} ACT =====`);

  const message = state.lastMessage;
  if (!message) {
    throw new Error("Cannot enter ACT without an assistant message");
  }

  state.messages.push(toAssistantMessage(message));
  state.pendingResults = [];

  const results: PendingToolResult[] = [];
  let pendingReads: FunctionToolCall[] = [];

  const flushReads = async (): Promise<void> => {
    if (pendingReads.length === 0) {
      return;
    }

    const batch = pendingReads;
    pendingReads = [];

    const batchResults = await Promise.all(
      batch.map((toolCall) =>
        callToolAndFormatResult(session, toolCall),
      ),
    );

    results.push(...batchResults);
  };

  for (const rawToolCall of message.tool_calls ?? []) {
    const toolCall = asFunctionToolCall(rawToolCall);

    if (READ_ONLY_TOOLS.has(toolCall.function.name)) {
      pendingReads.push(toolCall);
      continue;
    }

    await flushReads();
    results.push(
      await callToolAndFormatResult(session, toolCall),
    );
  }

  await flushReads();
  state.pendingResults = results;
  state.status = "OBSERVE";

  return state;
}

export function observe(state: AgentStatus): AgentStatus {
  console.log(`\n===== STEP ${state.step} OBSERVE =====`);

  for (const item of state.pendingResults) {
    console.log(`[观察结果] ${item.result}`);

    state.messages.push({
      role: "tool",
      tool_call_id: item.tool_call_id,
      content: item.result,
    });
  }

  state.pendingResults = [];
  state.status = "THINK";

  return state;
}

export function convertMcpTools(
  response: { tools: Tool[] },
): ChatCompletionTool[] {
  return response.tools.map((tool) => ({
    type: "function",
    function: {
      name: tool.name,
      description: tool.description ?? "",
      parameters: tool.inputSchema as Record<string, unknown>,
    },
  }));
}

export async function callMcpTool(
  session: ToolSession,
  toolCall: FunctionToolCall,
): Promise<unknown> {
  const toolName = toolCall.function.name;
  const argumentsObject = JSON.parse(
    toolCall.function.arguments || "{}",
  ) as Record<string, unknown>;

  console.log(`\n[调用工具] ${toolName}`);
  console.log(`[参数] ${JSON.stringify(argumentsObject)}`);

  return session.callTool({
    name: toolName,
    arguments: argumentsObject,
  });
}

async function callToolAndFormatResult(
  session: ToolSession,
  toolCall: FunctionToolCall,
): Promise<PendingToolResult> {
  const result = await callMcpTool(session, toolCall);
  const resultText = formatToolResult(result);

  console.log(`[工具调用结果] ${resultText}`);

  return {
    tool_call_id: toolCall.id,
    result: resultText,
  };
}

export async function runAgent(
  state: AgentStatus,
  client: OpenAI,
  session: ToolSession,
  tools: ChatCompletionTool[],
  checkpointStore: CheckpointStore,
  taskId: string,
): Promise<AgentStatus> {
  while (state.status !== "END") {
    if (state.step >= state.maxSteps) {
      console.log("达到最大执行步数");
      break;
    }

    state.step += 1;

    if (state.status === "THINK") {
      state = await think(state, client, tools);
    } else if (state.status === "ACT") {
      state = await act(state, session);
    } else if (state.status === "OBSERVE") {
      state = observe(state);
    }

    await checkpointStore.save(taskId, state);
    console.log(
      `[checkpoint] saved at step ${state.step} -> ${taskId}.json`,
    );
  }

  return state;
}

function asFunctionToolCall(
  toolCall: ToolCall,
): FunctionToolCall {
  if (toolCall.type !== "function") {
    throw new Error(
      `Unsupported tool call type: ${toolCall.type}`,
    );
  }

  return toolCall;
}

function toAssistantMessage(
  message: AssistantMessage,
): ChatMessage {
  return {
    ...message,
    role: "assistant",
    content: message.content,
  } as ChatMessage;
}

function formatToolResult(result: unknown): string {
  if (typeof result === "string") {
    return result;
  }

  if (
    result &&
    typeof result === "object" &&
    "content" in result
  ) {
    const content = (result as { content?: unknown }).content;

    if (Array.isArray(content)) {
      const textParts = content
        .filter(
          (item): item is { type: "text"; text: string } =>
            Boolean(
              item &&
                typeof item === "object" &&
                "type" in item &&
                item.type === "text" &&
                "text" in item &&
                typeof item.text === "string",
            ),
        )
        .map((item) => item.text);

      if (textParts.length > 0) {
        return textParts.join("\n");
      }
    }
  }

  return JSON.stringify(result);
}
