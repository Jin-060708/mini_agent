# ReAct_v

一个基于 **DeepSeek + MCP + Checkpoint** 的 ReAct 智能体示例。

项目通过 MCP 动态发现工具，按照
`THINK -> ACT -> OBSERVE` 循环调用模型和工具；每一步结束后把运行状态写入
JSON checkpoint，支持下次启动时恢复未完成的话题。

## 核心能力

- 使用 DeepSeek 的 OpenAI 兼容接口进行推理。
- 通过 MCP stdio Server 动态发现并调用本地工具。
- 按 `THINK -> ACT -> OBSERVE` 状态机执行多轮工具调用。
- 连续只读工具并发执行，写工具保持串行和原始调用顺序。
- 每个状态步骤后保存 checkpoint。
- 启动时列出历史话题，并按编号恢复到最近状态。
- 提供随机故障恢复测试和工具并发测试。

## 执行流程

```text
用户输入
  |
  v
选择新话题或恢复 checkpoint
  |
  v
run_agent
  |
  +--> THINK   调用 DeepSeek，判断直接回答还是调用工具
  |
  +--> ACT     通过 MCP 执行工具
  |             连续只读工具并发
  |             写工具和 run_command 串行
  |
  +--> OBSERVE 把工具结果作为 tool 消息写回 messages
  |
  +--> save checkpoint
  |
  +--> 回到 THINK，直到 END 或达到 max_steps
```

## 目录结构

```text
ReAct_v/
|-- main.py                 # 入口：MCP 会话、话题选择、运行循环
|-- react_agent.py          # THINK / ACT / OBSERVE 调度和只读并发
|-- agent.py                # MCP Server 与本地工具
|-- status.py               # Agent 运行状态与 checkpoint 反序列化
|-- checkpoint.py           # checkpoint 的保存、读取、删除和列表
|-- .env                    # API Key
|-- checkpoint/             # 运行时生成的 checkpoint JSON
`-- tests/
    |-- test_checkpoint_resume.py
    `-- test_tool_concurrency.py
```

## 环境要求

- Python 3.11
- Conda 环境：`mini_agent`
- DeepSeek API Key
- Python 包：
  - `openai`
  - `python-dotenv`
  - `mcp`
  - `simpleeval`

当前 `main.py` 默认使用：

```text
D:/anaconda/envs/mini_agent/python.exe
```

如果解释器路径不同，需要修改 [main.py](main.py) 中的
`StdioServerParameters.command`。

安装 ReAct_v 直接需要的依赖：

```bash
conda activate mini_agent
pip install openai python-dotenv mcp simpleeval
```

也可以安装上一级目录的完整依赖：

```bash
pip install -r ../requirements.txt
```

## 配置

在 `ReAct_v/.env` 中配置：

```dotenv
DEEPSEEK_API_KEY=your-deepseek-api-key
```

ReAct_v 当前只读取 `DEEPSEEK_API_KEY`。如果 `.env` 中同时存在
`MYSQL_*` 配置，它们不会在本子项目中生效。

## 运行

必须在 `ReAct_v` 目录中启动，因为 checkpoint 目录使用的是相对路径
`./checkpoint`：

```powershell
cd E:\agent_project\miniagent\ReAct_v
D:/anaconda/envs/mini_agent/python.exe main.py
```

启动后会显示最近修改过的已保存话题：

```text
===== 已保存的话题 =====
1. 话题名称 [进行中, step=4]

输入编号恢复该话题，或直接输入新的需求。
```

交互规则：

- 输入列表编号：恢复对应 checkpoint。
- 输入其他文本：创建新话题。
- 输入 `exit`：退出。
- 模型完成任务后，可以继续输入消息；消息会追加到当前会话。

新话题的 `task_id` 取第一段以空格分隔的输入，并转换为小写；因此相同
开头的多个新话题可能覆盖同一个 checkpoint 文件。

## 状态模型

| 状态 | 含义 |
|---|---|
| `THINK` | 等待 DeepSeek 决定下一步 |
| `ACT` | 执行 assistant 请求的 MCP 工具 |
| `OBSERVE` | 把工具结果写入 `messages` |
| `END` | 模型返回最终回答，无需继续调用工具 |

达到 `max_steps` 时循环会停止，但状态不一定会变成 `END`；此时最后保存的
checkpoint 仍可用于下次恢复。

## MCP 工具

| 工具 | 类别 | 说明 |
|---|---|---|
| `calculator` | 只读 | 使用 `simpleeval` 计算表达式 |
| `get_time` | 只读 | 获取当前时间 |
| `read_file` | 只读 | 读取文件 |
| `list_files` | 只读 | 列出目录中的文件 |
| `list_directories` | 只读 | 列出目录中的子目录 |
| `list_directory` | 只读 | 列出目录内容 |
| `search_file` | 只读 | 检查并返回文件路径 |
| `edit_file` | 写入 | 替换文件中的唯一匹配文本 |
| `create_directory` | 写入 | 创建目录 |
| `delete_directory` | 写入 | 删除空目录 |
| `create_file` | 写入 | 创建空文件 |
| `delete_file` | 写入 | 删除文件 |
| `move_file` | 写入 | 移动文件 |
| `copy_file` | 写入 | 复制文件 |
| `rename_directory` | 写入 | 重命名目录 |
| `rename_file` | 写入 | 重命名文件 |
| `run_command` | 命令 | 在项目根目录执行 shell 命令 |

## 工具并发规则

`react_agent.py` 中的 `READ_ONLY_TOOLS` 包含：

```text
calculator
get_time
read_file
list_files
list_directories
list_directory
search_file
```

同一轮 ACT 中：

1. 连续只读调用使用 `asyncio.gather` 并发执行。
2. 遇到写工具时，先等待前面的只读批次完成。
3. 写工具仍按顺序逐个执行。
4. 后续只读调用再形成一个新批次。
5. `pending_results` 始终保持模型原始 `tool_calls` 的顺序。

`run_command` 不会并发执行，因为它可能读写文件、启动进程或产生其他副作用。

## Checkpoint

每个状态步骤结束后，`CheckpointStore.save()` 会写入：

```text
./checkpoint/{task_id}.json
```

主要字段：

| 字段 | 说明 |
|---|---|
| `task_id` | 话题标识 |
| `step` | 当前执行步数 |
| `status` | `THINK`、`ACT`、`OBSERVE` 或 `END` |
| `max_steps` | 最大执行步数 |
| `messages` | 完整对话和工具消息 |
| `pending_results` | 已执行但尚未写入 `messages` 的工具结果 |
| `last_message` | assistant 最后一条消息，用于从 `ACT` 恢复 |

`list_all()` 还会临时附加 `_updated_at`，用于按修改时间倒序排列话题。

### 恢复语义

- checkpoint 在完整执行完一个状态节点后保存。
- 如果程序在节点执行到一半时崩溃，会从该节点之前的 checkpoint 恢复。
- 因此工具调用属于“至少一次”语义。
- 写入类工具应尽量保证幂等，否则崩溃恢复时可能重复产生副作用。

## 测试

工具并发测试：

```bash
D:/anaconda/envs/mini_agent/python.exe -m unittest tests.test_tool_concurrency -v
```

checkpoint 恢复测试：

```bash
D:/anaconda/envs/mini_agent/python.exe -m unittest tests.test_checkpoint_resume -v
```

或者运行全部测试：

```bash
D:/anaconda/envs/mini_agent/python.exe -m unittest discover -s tests -v
```

测试内容：

- `test_tool_concurrency.py`
  - 连续只读工具是否并发。
  - 写工具是否串行。
  - 工具结果是否保持原始顺序。
- `test_checkpoint_resume.py`
  - 注入随机异常后，是否能从最近 checkpoint 继续。
  - 从 `ACT` 恢复时，`last_message` 是否可用。

### 当前测试状态

`test_tool_concurrency.py` 当前通过。

`test_checkpoint_resume.py` 当前有两处失败：

```text
TypeError: CheckpointStore() takes no arguments
```

原因是测试使用 `CheckpointStore(temp_dir)` 指定临时目录，而当前
`checkpoint.py` 的 `CheckpointStore` 还没有构造函数参数，始终使用固定的
`./checkpoint`。修复该类后才能让恢复测试通过。

## 安全边界

这里有一个必须明确的区别：

- `_safe_path()` 会把路径限制在 `agent.py` 中配置的 `ROOT` 内。
- `ROOT` 当前硬编码为 `E:/agent_project/miniagent`。
- `read_file`、`edit_file`、`create_file`、`delete_file`、
  `create_directory`、`delete_directory`、`list_*` 和 `search_file`
  使用了该限制。
- `move_file` 和 `copy_file` 当前没有调用 `_safe_path()`。
- `rename_file` 只检查源路径，没有检查目标路径。
- `run_command` 使用 `shell=True`，没有文件系统沙箱，理论上可以访问整台机器。

因此，当前版本中的 `run_command`、`move_file`、`copy_file` 和
`rename_file` 不能视为安全沙箱工具。若运行不可信提示词，应优先收紧这些
实现或移除工具。

## 常见问题

### `ModuleNotFoundError`

说明使用了错误的 Python 解释器。请使用：

```powershell
D:/anaconda/envs/mini_agent/python.exe main.py
```

或先激活 `mini_agent` 环境。

### `DEEPSEEK_API_KEY` 缺失或鉴权失败

检查 `.env` 是否位于 `ReAct_v` 目录，并确认 Key 有效。

### MCP `Connection closed`

通常是子进程启动失败。检查：

- `main.py` 中的 Python 路径是否正确。
- `agent.py` 是否位于 `ReAct_v` 目录。
- `mcp` 和 `simpleeval` 是否已安装。

### 文件工具报“路径越界”

文件访问被限制在 `agent.py` 的 `ROOT` 中。需要访问其他项目时，修改
`ROOT`，不要把路径直接写成 `..`。

### 找不到历史 checkpoint

确认从 `ReAct_v` 目录启动，而不是从上一级目录启动。当前路径依赖工作目录。

### Windows 命令输出乱码

`run_command` 已使用 UTF-8 和 `errors="replace"` 读取输出，但部分 Windows
命令仍可能返回 GBK 字节，导致显示异常。这不影响命令退出码和正常 ASCII 输出。

## 已知限制

- checkpoint 使用普通 `write_text()`，写入过程中崩溃可能留下不完整 JSON。
- checkpoint 文件名直接使用 `task_id`，没有额外清理非法路径字符。
- 工具副作用不保证恰好一次。
- `run_command` 没有沙箱隔离。
- Python 解释器路径和文件工具根目录使用了机器相关硬编码路径。
- 没有做token限制，可能超出模型能力。