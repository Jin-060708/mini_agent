import assert from "node:assert/strict";
import test from "node:test";

import type OpenAI from "openai";

import {
  act,
  type ToolSession,
} from "../src/reactAgent.js";
import { AgentStatus } from "../src/status.js";

class FakeToolCall {
  readonly type = "function";
  readonly function: {
    name: string;
    arguments: string;
  };

  constructor(
    readonly id: string,
    name: string,
    argumentsValue: Record<string, unknown>,
  ) {
    this.function = {
      name,
      arguments: JSON.stringify(argumentsValue),
    };
  }
}

class FakeMessage {
  readonly role = "assistant";
  readonly content = null;
  readonly refusal = null;

  constructor(readonly tool_calls: FakeToolCall[]) {}
}

class TrackingSession implements ToolSession {
  activeCalls = 0;
  maxActiveCalls = 0;
  readonly events: string[] = [];

  constructor(
    private readonly delays: Record<string, number>,
  ) {}

  async callTool(params: {
    name: string;
    arguments?: Record<string, unknown>;
  }): Promise<unknown> {
    const callId = String(params.arguments?.call_id);
    this.activeCalls += 1;
    this.maxActiveCalls = Math.max(
      this.maxActiveCalls,
      this.activeCalls,
    );
    this.events.push(`${callId}:start`);

    try {
      await new Promise((resolve) =>
        setTimeout(resolve, this.delays[callId] ?? 0),
      );
      return {
        content: [
          {
            type: "text",
            text: `${callId}:done`,
          },
        ],
      };
    } finally {
      this.events.push(`${callId}:end`);
      this.activeCalls -= 1;
    }
  }
}

test("consecutive reads run concurrently", async () => {
  const toolCalls = [
    new FakeToolCall("read-1", "read_file", {
      call_id: "read-1",
    }),
    new FakeToolCall("read-2", "list_files", {
      call_id: "read-2",
    }),
    new FakeToolCall("read-3", "read_file", {
      call_id: "read-3",
    }),
  ];
  const session = new TrackingSession({
    "read-1": 30,
    "read-2": 20,
    "read-3": 10,
  });
  const state = new AgentStatus(
    [],
    "ACT",
    0,
    50,
    new FakeMessage(toolCalls) as unknown as OpenAI.Chat.Completions.ChatCompletionMessage,
  );

  await act(state, session);

  assert.equal(session.maxActiveCalls, 3);
  assert.deepEqual(
    state.pendingResults.map((item) => item.tool_call_id),
    ["read-1", "read-2", "read-3"],
  );
});

test("writes stay serial and keep the original order", async () => {
  const toolCalls = [
    new FakeToolCall("read-before", "read_file", {
      call_id: "read-before",
    }),
    new FakeToolCall("write-1", "edit_file", {
      call_id: "write-1",
    }),
    new FakeToolCall("write-2", "create_file", {
      call_id: "write-2",
    }),
    new FakeToolCall("read-after", "read_file", {
      call_id: "read-after",
    }),
  ];
  const session = new TrackingSession({
    "read-before": 30,
    "write-1": 20,
    "write-2": 20,
    "read-after": 10,
  });
  const state = new AgentStatus(
    [],
    "ACT",
    0,
    50,
    new FakeMessage(toolCalls) as unknown as OpenAI.Chat.Completions.ChatCompletionMessage,
  );

  await act(state, session);

  assert.equal(session.maxActiveCalls, 1);
  assert.ok(
    session.events.indexOf("read-before:end") <
      session.events.indexOf("write-1:start"),
  );
  assert.ok(
    session.events.indexOf("write-1:end") <
      session.events.indexOf("write-2:start"),
  );
  assert.ok(
    session.events.indexOf("write-2:end") <
      session.events.indexOf("read-after:start"),
  );
  assert.deepEqual(
    state.pendingResults.map((item) => item.tool_call_id),
    ["read-before", "write-1", "write-2", "read-after"],
  );
});
