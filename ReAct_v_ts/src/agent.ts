import { exec } from "node:child_process";
import {
  mkdir,
  readFile,
  readdir,
  rename,
  rmdir,
  unlink,
  writeFile,
} from "node:fs/promises";
import path from "node:path";
import { promisify } from "node:util";

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { Parser } from "expr-eval";
import { z } from "zod";

const execAsync = promisify(exec);
const parser = new Parser();
const server = new McpServer({
  name: "my-tools",
  version: "1.0.0",
});

const ROOT = path.resolve(
  process.env.AGENT_ROOT ?? path.resolve(process.cwd(), ".."),
);

function safePath(filePath: string): string {
  const resolved = path.resolve(ROOT, filePath);
  const relative = path.relative(ROOT, resolved);

  if (
    relative.startsWith("..") ||
    path.isAbsolute(relative)
  ) {
    throw new Error("路径越界");
  }

  return resolved;
}

function textResult(text: string) {
  return {
    content: [
      {
        type: "text" as const,
        text,
      },
    ],
  };
}

server.registerTool(
  "calculator",
  {
    description: "计算表达式",
    inputSchema: {
      expression: z.string(),
    },
    annotations: {
      readOnlyHint: true,
    },
  },
  async ({ expression }) =>
    textResult(String(parser.evaluate(expression))),
);

server.registerTool(
  "get_time",
  {
    description: "获取当前时间",
    annotations: {
      readOnlyHint: true,
    },
  },
  async () =>
    textResult(
      new Date()
        .toLocaleString("sv-SE", {
          hour12: false,
        })
        .replace("T", " "),
    ),
);

server.registerTool(
  "read_file",
  {
    description: "读取文件",
    inputSchema: {
      file_path: z.string(),
    },
    annotations: {
      readOnlyHint: true,
    },
  },
  async ({ file_path }) =>
    textResult(await readFile(safePath(file_path), "utf8")),
);

server.registerTool(
  "edit_file",
  {
    description: "把文件中的 old_text 替换为 new_text",
    inputSchema: {
      file_path: z.string(),
      old_text: z.string(),
      new_text: z.string(),
    },
  },
  async ({ file_path, old_text, new_text }) => {
    const filePath = safePath(file_path);
    const content = await readFile(filePath, "utf8");

    if (!content.includes(old_text)) {
      return textResult("未找到要替换的内容");
    }

    if (content.split(old_text).length - 1 > 1) {
      return textResult("匹配到多处，请提供更精确的 old_text");
    }

    await writeFile(
      filePath,
      content.replace(old_text, new_text),
      "utf8",
    );
    return textResult("替换成功");
  },
);

server.registerTool(
  "create_directory",
  {
    description: "创建目录",
    inputSchema: {
      dir_path: z.string(),
    },
  },
  async ({ dir_path }) => {
    const directory = safePath(dir_path);
    await mkdir(directory, { recursive: true });
    return textResult(`目录已创建: ${directory}`);
  },
);

server.registerTool(
  "delete_directory",
  {
    description: "删除目录",
    inputSchema: {
      dir_path: z.string(),
    },
  },
  async ({ dir_path }) => {
    const directory = safePath(dir_path);
    await rmdir(directory);
    return textResult(`目录已删除: ${directory}`);
  },
);

server.registerTool(
  "create_file",
  {
    description: "创建文件",
    inputSchema: {
      file_path: z.string(),
    },
  },
  async ({ file_path }) => {
    const filePath = safePath(file_path);
    await writeFile(filePath, "", "utf8");
    return textResult(`文件已创建: ${filePath}`);
  },
);

server.registerTool(
  "delete_file",
  {
    description: "删除文件",
    inputSchema: {
      file_path: z.string(),
    },
  },
  async ({ file_path }) => {
    const filePath = safePath(file_path);
    await unlink(filePath);
    return textResult(`文件已删除: ${filePath}`);
  },
);

server.registerTool(
  "move_file",
  {
    description: "移动文件",
    inputSchema: {
      src: z.string(),
      dst: z.string(),
    },
  },
  async ({ src, dst }) => {
    const source = safePath(src);
    const destination = safePath(dst);
    await movePath(source, destination);
    return textResult(`文件已移动: ${src} -> ${dst}`);
  },
);

server.registerTool(
  "copy_file",
  {
    description: "复制文件",
    inputSchema: {
      src: z.string(),
      dst: z.string(),
    },
  },
  async ({ src, dst }) => {
    const source = await readFile(safePath(src));
    await writeFile(safePath(dst), source);
    return textResult(`文件已复制: ${src} -> ${dst}`);
  },
);

server.registerTool(
  "rename_directory",
  {
    description: "重命名目录",
    inputSchema: {
      src: z.string(),
      dst: z.string(),
    },
  },
  async ({ src, dst }) => {
    const source = safePath(src);
    const destination = safePath(dst);
    await movePath(source, destination);
    return textResult(`目录已重命名: ${src} -> ${dst}`);
  },
);

server.registerTool(
  "rename_file",
  {
    description: "重命名文件",
    inputSchema: {
      src: z.string(),
      dst: z.string(),
    },
  },
  async ({ src, dst }) => {
    const source = safePath(src);
    const destination = safePath(dst);
    await movePath(source, destination);
    return textResult(`文件已重命名: ${src} -> ${dst}`);
  },
);

server.registerTool(
  "list_files",
  {
    description: "列出目录下的所有文件",
    inputSchema: {
      dir_path: z.string().default("."),
    },
    annotations: {
      readOnlyHint: true,
    },
  },
  async ({ dir_path }) => {
    const directory = safePath(dir_path);
    const entries = await readdir(directory, {
      withFileTypes: true,
    });
    const files = entries
      .filter((entry) => entry.isFile())
      .map((entry) => path.join(directory, entry.name));
    return textResult(files.join("\n"));
  },
);

server.registerTool(
  "list_directories",
  {
    description: "列出目录下的所有目录",
    inputSchema: {
      dir_path: z.string().default("."),
    },
    annotations: {
      readOnlyHint: true,
    },
  },
  async ({ dir_path }) => {
    const directory = safePath(dir_path);
    const entries = await readdir(directory, {
      withFileTypes: true,
    });
    const directories = entries
      .filter((entry) => entry.isDirectory())
      .map((entry) => path.join(directory, entry.name));
    return textResult(directories.join("\n"));
  },
);

server.registerTool(
  "list_directory",
  {
    description: "列出目录内容",
    inputSchema: {
      dir_path: z.string().default("."),
    },
    annotations: {
      readOnlyHint: true,
    },
  },
  async ({ dir_path }) => {
    const directory = safePath(dir_path);
    const entries = await readdir(directory, {
      withFileTypes: true,
    });
    const lines = entries
      .sort((left, right) =>
        left.name.localeCompare(right.name),
      )
      .map(
        (entry) =>
          `${entry.isDirectory() ? "DIR " : "FILE"} ${entry.name}`,
      );
    return textResult(lines.join("\n"));
  },
);

server.registerTool(
  "search_file",
  {
    description: "搜索文件",
    inputSchema: {
      file_path: z.string(),
    },
    annotations: {
      readOnlyHint: true,
    },
  },
  async ({ file_path }) =>
    textResult(`文件路径: ${safePath(file_path)}`),
);

server.registerTool(
  "run_command",
  {
    description: "在项目目录执行 shell 命令",
    inputSchema: {
      command: z.string(),
    },
  },
  async ({ command }) => {
    try {
      const result = await execAsync(command, {
        cwd: ROOT,
        timeout: 30_000,
        maxBuffer: 10 * 1024 * 1024,
        windowsHide: true,
      });
      return textResult(
        `exit=0\n${result.stdout}\n${result.stderr}`,
      );
    } catch (error) {
      const commandError = error as {
        code?: number | string;
        stdout?: string;
        stderr?: string;
      };
      const exitCode =
        typeof commandError.code === "number"
          ? commandError.code
          : 1;
      return textResult(
        `exit=${exitCode}\n${commandError.stdout ?? ""}\n${commandError.stderr ?? ""}`,
      );
    }
  },
);

async function movePath(
  source: string,
  destination: string,
): Promise<void> {
  await rename(source, destination);
}

const transport = new StdioServerTransport();
await server.connect(transport);
