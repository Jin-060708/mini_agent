import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import type OpenAI from "openai";

import { CheckpointStore } from "../src/checkpoint.js";
import { runAgent, type ToolSession } from "../src/reactAgent.js";
import {
  AgentStatus,
  type ChatMessage,
} from "../src/status.js";

class InjectedError extends Error {}

class RandomFaultInjector {
  private state: number;
  private gap: number;
  private failureBudget: number;
  failures = 0;

  constructor(
    seed: number,
    failureBudget = 8,
    private readonly minGap = 2,
    private readonly maxGap = 4,
  ) {
    this.state = seed;
    this.failureBudget = failureBudget;
    this.gap = this.randomInt(minGap, maxGap);
  }

  hit(point: string): void {
    if (this.failureBudget === 0) {
      return;
    }

    this.gap -= 1;
    if (this.gap > 0) {
      return;
    }

    this.failureBudget -= 1;
    this.failures += 1;
    this.gap = this.randomInt(this.minGap, this.maxGap);
    throw new InjectedError(`injected failure at ${point}`);
  }

  private randomInt(min: number, max: number): number {
    this.state =
      (this.state * 1_103_515_245 + 12_345) & 0x7fffffff;
    const ratio = this.state / 0x7fffffff;
    return Math.floor(ratio * (max - min + 1)) + min;
  }
}

class FakeToolCall {
  readonly type = "function";
  readonly function: {
    name: string;
    arguments: string;
  };

  constructor(
    readonly id: string,
    value: number,
  ) {
    this.function = {
      name: "record_value",
      arguments: JSON.stringify({ value }),
    };
  }
}

class FakeMessage {
  readonly role = "assistant";
  readonly refusal = null;

  constructor(
    readonly content: string | null = null,
    readonly tool_calls: FakeToolCall[] | null = null,
  ) {}
}

class FakeCompletions {
  constructor(
    private readonly targetSteps: number,
    private readonly injector: RandomFaultInjector,
  ) {}

  async create(params: {
    messages: ChatMessage[];
  }): Promise<OpenAI.Chat.Completions.ChatCompletion> {
    this.injector.hit("think");

    const completedSteps = params.messages.filter(
      (message) =>
        message.role === "assistant" &&
        "tool_calls" in message &&
        Boolean(message.tool_calls?.length),
    ).length;

    const message =
      completedSteps >= this.targetSteps
        ? new FakeMessage("finished")
        : new FakeMessage(null, [
            new FakeToolCall(
              `call-${completedSteps + 1}`,
              completedSteps + 1,
            ),
          ]);

    return {
      choices: [{ message }],
    } as unknown as OpenAI.Chat.Completions.ChatCompletion;
  }
}

class FakeClient {
  private readonly targetSteps: number;
  readonly chat: {
    completions: FakeCompletions;
  };

  constructor(
    targetSteps: number,
    injector: RandomFaultInjector,
  ) {
    this.targetSteps = targetSteps;
    this.chat = {
      completions: new FakeCompletions(
        targetSteps,
        injector,
      ),
    };
  }
}

class FakeSession implements ToolSession {
  readonly executedValues: number[] = [];

  constructor(
    private readonly injector: RandomFaultInjector,
  ) {}

  async callTool(params: {
    name: string;
    arguments?: Record<string, unknown>;
  }): Promise<unknown> {
    assert.equal(params.name, "record_value");
    this.injector.hit("tool");

    const value = Number(params.arguments?.value);
    this.executedValues.push(value);
    return `recorded ${value}`;
  }
}

test("random failures resume from the latest checkpoint", async () => {
  const targetSteps = 7;
  const taskId = "random-failure-resume";
  const injector = new RandomFaultInjector(20_260_922);
  const tempDirectory = await mkdtemp(
    path.join(os.tmpdir(), "react-agent-ts-"),
  );

  try {
    const store = new CheckpointStore(tempDirectory);
    const session = new FakeSession(injector);
    const client = new FakeClient(
      targetSteps,
      injector,
    ) as unknown as OpenAI;
    let state = new AgentStatus(
      [
        {
          role: "user",
          content: "run all steps",
        },
      ],
      "THINK",
      0,
      30,
    );
    let attempts = 0;

    while (state.status !== "END") {
      attempts += 1;
      assert.ok(attempts < 50);

      try {
        state = await runAgent(
          state,
          client,
          session,
          [],
          store,
          taskId,
        );
      } catch (error) {
        if (!(error instanceof InjectedError)) {
          throw error;
        }

        const checkpoint = await store.load(taskId);
        assert.ok(checkpoint);
        assert.ok(
          ["THINK", "ACT", "OBSERVE"].includes(
            checkpoint.status,
          ),
        );
        state = AgentStatus.fromCheckpoint(checkpoint);
      }
    }

    const checkpoint = await store.load(taskId);
    assert.ok(checkpoint);
    assert.ok(injector.failures > 0);
    assert.ok(attempts > 1);
    assert.equal(state.status, "END");
    assert.equal(checkpoint.status, "END");
    assert.equal(checkpoint.step, state.step);
    assert.deepEqual(checkpoint.messages, state.messages);

    const assistantCalls = state.messages.filter(
      (message) =>
        message.role === "assistant" &&
        "tool_calls" in message &&
        Boolean(message.tool_calls?.length),
    );
    const toolResults = state.messages.filter(
      (message) => message.role === "tool",
    );

    assert.equal(assistantCalls.length, targetSteps);
    assert.equal(toolResults.length, targetSteps);
    assert.deepEqual(
      toolResults.map((message) => message.tool_call_id),
      assistantCalls.flatMap((message) =>
        "tool_calls" in message
          ? (message.tool_calls ?? []).map(
              (toolCall) => toolCall.id,
            )
          : [],
      ),
    );
    assert.deepEqual(
      [...new Set(session.executedValues)].sort(
        (left, right) => left - right,
      ),
      Array.from(
        { length: targetSteps },
        (_, index) => index + 1,
      ),
    );
  } finally {
    await rm(tempDirectory, {
      recursive: true,
      force: true,
    });
  }
});

test("checkpoint keeps last_message for ACT resume", async () => {
  const taskId = "act-checkpoint";
  const tempDirectory = await mkdtemp(
    path.join(os.tmpdir(), "react-agent-ts-act-"),
  );

  try {
    const store = new CheckpointStore(tempDirectory);
    const message = new FakeMessage(null, [
      new FakeToolCall("call-1", 1),
    ]);
    const state = new AgentStatus(
      [
        {
          role: "user",
          content: "run",
        },
      ],
      "ACT",
      1,
      50,
      message as unknown as OpenAI.Chat.Completions.ChatCompletionMessage,
    );

    await store.save(taskId, state);
    const checkpoint = await store.load(taskId);
    assert.ok(checkpoint);

    const restored = AgentStatus.fromCheckpoint(checkpoint);
    assert.equal(restored.status, "ACT");
    assert.equal(
      restored.lastMessage?.tool_calls?.[0].id,
      "call-1",
    );
  } finally {
    await rm(tempDirectory, {
      recursive: true,
      force: true,
    });
  }
});
