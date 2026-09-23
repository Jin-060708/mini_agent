import {
  mkdir,
  readFile,
  readdir,
  stat,
  unlink,
  writeFile,
} from "node:fs/promises";
import path from "node:path";

import type { AgentStatus, CheckpointData } from "./status.js";

export const CHECKPOINT_DIR = path.resolve(process.cwd(), "checkpoint");

export class CheckpointStore {
  readonly directory: string;

  constructor(directory = CHECKPOINT_DIR) {
    this.directory = path.resolve(directory);
  }

  private async ensureDirectory(): Promise<void> {
    await mkdir(this.directory, { recursive: true });
  }

  private getPath(taskId: string): string {
    return path.join(this.directory, `${taskId}.json`);
  }

  async save(taskId: string, status: AgentStatus): Promise<void> {
    const data: CheckpointData = {
      task_id: taskId,
      step: status.step,
      status: status.status,
      max_steps: status.maxSteps,
      messages: status.messages,
      pending: status.pendingResults,
      last_message: status.lastMessage,
    };

    await this.ensureDirectory();
    await writeFile(
      this.getPath(taskId),
      JSON.stringify(data, null, 4),
      "utf8",
    );
  }

  async load(taskId: string): Promise<CheckpointData | null> {
    try {
      const content = await readFile(this.getPath(taskId), "utf8");
      return JSON.parse(content) as CheckpointData;
    } catch (error) {
      if (isNodeError(error) && error.code === "ENOENT") {
        return null;
      }
      throw error;
    }
  }

  async delete(taskId: string): Promise<void> {
    try {
      await unlink(this.getPath(taskId));
    } catch (error) {
      if (!isNodeError(error) || error.code !== "ENOENT") {
        throw error;
      }
    }
  }

  async listAll(): Promise<CheckpointData[]> {
    await this.ensureDirectory();

    const records: CheckpointData[] = [];
    const entries = await readdir(this.directory, { withFileTypes: true });

    for (const entry of entries) {
      if (!entry.isFile() || !entry.name.endsWith(".json")) {
        continue;
      }

      const filePath = path.join(this.directory, entry.name);

      try {
        const [content, fileStat] = await Promise.all([
          readFile(filePath, "utf8"),
          stat(filePath),
        ]);
        const data = JSON.parse(content) as CheckpointData;
        data._updated_at = fileStat.mtimeMs / 1000;
        records.push(data);
      } catch {
        // Ignore files that are incomplete or invalid.
      }
    }

    records.sort(
      (left, right) =>
        (right._updated_at ?? 0) - (left._updated_at ?? 0),
    );

    return records;
  }
}

function isNodeError(error: unknown): error is NodeJS.ErrnoException {
  return error instanceof Error && "code" in error;
}
