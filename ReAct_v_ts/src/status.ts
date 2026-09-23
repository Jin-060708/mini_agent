import type OpenAI from "openai";

export type AgentPhase = "THINK" | "ACT" | "OBSERVE" | "END";

export type ChatMessage =
  OpenAI.Chat.Completions.ChatCompletionMessageParam;

export type AssistantMessage =
  OpenAI.Chat.Completions.ChatCompletionMessage;

export interface PendingToolResult {
  tool_call_id: string;
  result: string;
}

export interface CheckpointData {
  task_id: string;
  step: number;
  status: AgentPhase;
  max_steps: number;
  messages: ChatMessage[];
  pending?: PendingToolResult[];
  pending_results?: PendingToolResult[];
  last_message: AssistantMessage | null;
  _updated_at?: number;
}

export class AgentStatus {
  constructor(
    public messages: ChatMessage[],
    public status: AgentPhase = "THINK",
    public step = 0,
    public maxSteps = 50,
    public lastMessage: AssistantMessage | null = null,
    public pendingResults: PendingToolResult[] = [],
  ) {}

  static fromCheckpoint(data: CheckpointData): AgentStatus {
    return new AgentStatus(
      data.messages ?? [],
      data.status ?? "THINK",
      data.step ?? 0,
      data.max_steps ?? 50,
      data.last_message ?? null,
      data.pending_results ?? data.pending ?? [],
    );
  }
}
