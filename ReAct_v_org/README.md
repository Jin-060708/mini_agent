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

`main.py` 使用当前 Python 解释器启动 MCP 子进程，不再依赖机器上的固定路径。

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

复制 `.env.example` 为 `.env`，然后配置：

```dotenv
DEEPSEEK_API_KEY=your-deepseek-api-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
AGENT_ROOT=.
AGENT_ALLOW_COMMANDS=false
```

`AGENT_ROOT` 默认为当前项目目录。`run_command` 默认关闭；只有在可信的本地环境中
明确设置 `AGENT_ALLOW_COMMANDS=true` 才会启用。

## 运行

可以从任意目录启动：

```powershell
cd E:\agent_project\miniagent\ReAct_v_org
python main.py
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

使用已安装依赖运行 `python -m unittest discover -s tests -v`，当前 4 项测试全部通过。

## 安全边界

这里有一个必须明确的区别：

- `_safe_path()` 会把路径限制在 `agent.py` 中配置的 `ROOT` 内。
- `ROOT` 默认是当前项目目录，也可以通过 `AGENT_ROOT` 配置。
- `read_file`、`edit_file`、`create_file`、`delete_file`、
  `create_directory`、`delete_directory`、`list_*` 和 `search_file`
  使用了该限制。
- `move_file`、`copy_file` 和 `rename_file` 的源和目标都会调用 `_safe_path()`。
- `run_command` 默认禁用；启用后仍应只在可信本地环境使用，因为 shell 本身没有完整沙箱。

不要对不可信提示词启用 `run_command`。文件工具仍然只允许访问 `AGENT_ROOT` 内的路径。

## 常见问题

### `ModuleNotFoundError`

说明当前 Python 环境没有安装项目依赖。请先安装：

```powershell
pip install openai python-dotenv mcp simpleeval
```

或先激活 `mini_agent` 环境。

### `DEEPSEEK_API_KEY` 缺失或鉴权失败

检查 `.env` 是否位于本项目目录，并确认 Key 有效。

### MCP `Connection closed`

通常是子进程启动失败。检查：

- 当前 Python 环境是否安装 `mcp`。
- `agent.py` 是否位于本项目目录。
- `mcp` 和 `simpleeval` 是否已安装。

### 文件工具报“路径越界”

文件访问被限制在 `agent.py` 的 `ROOT` 中。需要访问其他项目时，修改
`ROOT`，不要把路径直接写成 `..`。

### 找不到历史 checkpoint

确认 `checkpoint` 目录可写，并检查 `AGENT_ROOT` 是否指向预期目录。

### Windows 命令输出乱码

`run_command` 已使用 UTF-8 和 `errors="replace"` 读取输出，但部分 Windows
命令仍可能返回 GBK 字节，导致显示异常。这不影响命令退出码和正常 ASCII 输出。

## 已知限制

- checkpoint 使用临时文件加原子替换，降低写入中断造成损坏的概率。
- `task_id` 只允许安全的文件名字符，并由输入内容生成可读名称和哈希后缀。
- 工具副作用不保证恰好一次。
- `run_command` 在显式启用后仍不具备完整沙箱隔离。
- 没有做token限制，可能超出模型能力。
