import { createInterface } from "node:readline/promises";
import { stdin as input, stdout as output } from "node:process";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import dotenv from "dotenv";
import OpenAI from "openai";

import { CheckpointStore } from "./checkpoint.js";
import {
  convertMcpTools,
  runAgent,
} from "./reactAgent.js";
import { AgentStatus } from "./status.js";

dotenv.config({
  path: path.resolve(process.cwd(), ".env"),
});

const projectRoot = process.cwd();
const apiKey = process.env.DEEPSEEK_API_KEY;

if (!apiKey) {
  throw new Error("DEEPSEEK_API_KEY is not configured");
}

const client = new OpenAI({
  apiKey,
  baseURL: "https://api.deepseek.com",
});

async function chooseInitialTask(
  checkpointStore: CheckpointStore,
  readline: ReturnType<typeof createInterface>,
): Promise<{
  taskId: string;
  status: AgentStatus;
} | null> {
  const records = await checkpointStore.listAll();

  if (records.length > 0) {
    console.log("\n===== 已保存的话题 =====");

    records.forEach((data, index) => {
      const stateName =
        data.status === "END" ? "已完成" : "进行中";
      console.log(
        `${index + 1}. ${data.task_id} [${stateName}, step=${data.step}]`,
      );
    });

    console.log("输入编号恢复该话题，或直接输入新的需求。");
  } else {
    console.log("没有已保存的话题，请输入新的需求。");
  }

  while (true) {
    const userInput = (
      await readline.question("\nuser: ")
    ).trim();

    if (userInput === "exit") {
      return null;
    }

    if (records.length > 0 && /^\d+$/.test(userInput)) {
      const index = Number(userInput);
      if (index >= 1 && index <= records.length) {
        const data = records[index - 1];
        console.log(`[resume] 恢复话题：${data.task_id}`);
        return {
          taskId: data.task_id,
          status: AgentStatus.fromCheckpoint(data),
        };
      }

      console.log("编号不存在，请重新输入。");
      continue;
    }

    const taskId = userInput
      .split(" ")[0]
      .toLowerCase()
      .replaceAll(" ", "_");
    const status = new AgentStatus([
      {
        role: "user",
        content: userInput,
      },
    ]);

    console.log(`[new] 新建话题：${taskId}`);
    return { taskId, status };
  }
}

async function main(): Promise<void> {
  const readline = createInterface({ input, output });
  const checkpointStore = new CheckpointStore();
  const agentEntry = path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    "agent.js",
  );
  const transport = new StdioClientTransport({
    command: process.execPath,
    args: [agentEntry],
    cwd: projectRoot,
    stderr: "inherit",
    env: getProcessEnv(),
  });
  const mcpClient = new Client({
    name: "react-agent-ts",
    version: "1.0.0",
  });

  try {
    await mcpClient.connect(transport);
    const response = await mcpClient.listTools();
    const tools = convertMcpTools(response);
    const initial = await chooseInitialTask(
      checkpointStore,
      readline,
    );

    if (!initial) {
      return;
    }

    let { taskId, status } = initial;

    while (true) {
      status = await runAgent(
        status,
        client,
        mcpClient,
        tools,
        checkpointStore,
        taskId,
      );

      if (status.lastMessage) {
        console.log(
          `deepseek-flash: ${status.lastMessage.content ?? ""}`,
        );
      }

      const userInput = (
        await readline.question("user: ")
      ).trim();

      if (userInput === "exit") {
        break;
      }

      status.messages.push({
        role: "user",
        content: userInput,
      });
      status = new AgentStatus(status.messages);
    }
  } finally {
    readline.close();
    await mcpClient.close();
  }
}

function getProcessEnv(): Record<string, string> {
  return Object.fromEntries(
    Object.entries(process.env).filter(
      (entry): entry is [string, string] =>
        typeof entry[1] === "string",
    ),
  );
}

await main();
