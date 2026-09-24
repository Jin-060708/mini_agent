# miniagent

一个用于学习与实践 **大语言模型 (LLM) 智能体** 的实验性项目。基于 DeepSeek 的 OpenAI 兼容 API，演示三种递进式的智能体实现思路：从基础的 Function Calling，到 MCP (Model Context Protocol)，再到带断点续跑的 ReAct 智能体。

## 项目结构

```
miniagent/
├── function_call_v/        # 进阶版：基于本地工具的 Function Calling 对话
│   ├── main.py             #   对话主循环 + 工具注册/分发
│   ├── tool.py             #   本地工具实现（计算 / 时间 / 天气 / 用户信息 MySQL 存取）
│   └── .env                #   环境变量（API Key、MySQL 配置）
├── mcp_server_pyv/         # Python 版 MCP Server + 客户端示例
│   ├── server.py           #   MCP Server：文件、目录、命令执行等工具
│   ├── client_test.py      #   MCP 客户端：连接 LLM 并调用 MCP 工具
│   └── .env
├── ReAct_v/                # 核心：ReAct 智能体 + MCP + Checkpoint 断点续跑
│   ├── main.py             #   入口：MCP 会话、话题新建/恢复、运行循环
│   ├── react_agent.py      #   THINK/ACT/OBSERVE 循环调度
│   ├── agent.py            #   MCP Server 工具实现（计算、时间、文件管理、命令）
│   ├── status.py           #   Agent 状态模型（可序列化/从 checkpoint 恢复）
│   ├── checkpoint.py       #   断点存储（./checkpoint/{task_id}.json）
│   ├── .env
│   └── tests/
│       └── test_checkpoint_resume.py   # 断点续跑单元测试（随机故障注入）
├── mcp-server/             # Node.js 版 MCP Server（JS 实现，另一套方案）
├── test.py                 # 临时测试脚本（当前为空）
└── README.md
```

## 三个子项目由浅入深

图例：`用户输入 → LLM(DeepSeek) → 是否要工具 → 执行 → 回到 LLM → 回答`

### 1. Function Calling（function_call_v/）
最简单的一种：在调用 LLM 时把本地工具的 JSON Schema 一并传入，模型决定是否调用工具，再由本地代码执行并回填结果。

- 本地工具：`calculator`（计算）、`get_time`（时间）、`get_weather`（天气，可接高德）、`save_user_info` / `get_user_info`（MySQL 存取用户信息）
- 技术要点：`messages` 中按 `tool` 角色回填结果；参数用 `json.loads` 解析模型返回的 JSON 字符串

### 2. MCP（mcp_server_pyv/）
用 **MCP (Model Context Protocol)** 把工具能力做成独立 Server，客户端通过 stdin/stdout 与 Server 通信，动态发现并调用工具，工具不写死在客户端里。

- `server.py`：暴露计算、时间、文件/目录管理、搜索、命令执行等工具
- `client_test.py`：连接 Server → 拉取工具列表 → 让 LLM 决定调用 → 执行并回填

### 3. ReAct 智能体（ReAct_v/）
把上面两者组合成真正的 **ReAct (Reasoning + Acting)** 循环，并加上 **Checkpoint 断点续跑**：Agent 按 `THINK → ACT → OBSERVE` 循环，每一步把状态落盘；若中途崩溃，可从最近的 checkpoint 恢复继续执行。

- `think`：让 LLM（DeepSeek）决定下一步（直接回答 或 调用工具）
- `act`：通过 MCP 执行模型要求的工具调用，收集结果、利用asyncio异步执行读写并发操作
- `observe`：把工具结果作为 `tool` 消息回填，回到 `think`
- `checkpoint.py`：每步把消息、状态、步数等序列化到 `./checkpoint/{task_id}.json`
- 恢复：启动时可选择继续旧话题（读取并重建 `AgentStatus`）
- 测试：`tests/test_checkpoint_resume.py` 模拟随机故障，证明断点续跑能把任务从失败中恢复完成

## 环境要求

- Python 3.11（本项目使用 conda 环境 `mini_agent`）
- 依赖：`openai`、`python-dotenv`、`mcp`、`simpleeval`（Node.js 版另需 Node.js/npm）

```bash
conda activate mini_agent
pip install openai python-dotenv mcp simpleeval
```

## 配置

各子项目下都有 `.env` 文件，按需配置以下项（**请勿提交真实密钥**）：

| 配置项 | 说明 |
|---|---|
| `DEEPSEEK_API_KEY` | LLM API Key（必填） |
| `MYSQL_HOST` / `MYSQL_PORT` | MySQL 地址与端口 |
| `MYSQL_USER` / `MYSQL_PASSWORD` | MySQL 账号与密码 |
| `MYSQL_DB` | MySQL 数据库名 |


## 运行

所有入口均使用 `mini_agent` 环境的 Python 显式运行，避免依赖系统 Python（未安装依赖会报 `ModuleNotFoundError`）：

```bash
# 1. Function Calling 对话
D:/anaconda/envs/mini_agent/python.exe function_call_v/main.py

# 2. MCP 客户端示例（会自行拉起 server.py）
D:/anaconda/envs/mini_agent/python.exe mcp_server_pyv/client_test.py

# 3. ReAct 智能体 + 断点续跑
D:/anaconda/envs/mini_agent/python.exe ReAct_v/main.py
```

ReAct_v 中 MCP Server 的启动命令在 [ReAct_v/main.py](ReAct_v/main.py) 中通过 `StdioServerParameters` 指定，默认指向 `agent.py`；若你的解释器路径不同，请修改其中 `command` 的值。

## 测试



该测试注入随机故障，验证 Agent 能从最近的 checkpoint 恢复并最终完成任务、工具调用结果对账一致。

## 常见问题

- **运行报 `No module named 'openai'`**：当前解释器不是 `mini_agent` 环境，请用上面给出的完整 Python 路径启动，或在 IDE 中把解释器切到 `mini_agent`。
- **`Cannot import name ...`**：多为旧 `__pycache__` 缓存与磁盘文件不一致，删除对应目录下的 `__pycache__` 后重试。
- **MCP 连接被关闭（`Connection closed`）**：Server 端启动失败，通常是 `StdioServerParameters` 里的 `command`/`args` 路径不对或依赖缺失，先单独运行 `agent.py`/`server.py` 排查。
- **`UnicodeDecodeError`（Windows 命令工具）**：`run_command` 执行 shell 时已改用 `encoding="utf-8", errors="replace"` 处理非 GBK 字节。

## 技术栈总结

- **简单context engineering**: 用 `messages` 中按 `tool` 角色回填结果；参数用 `json.loads` 解析模型返回的 JSON 字符串
- **异步读写**: 利用act状态 `asyncio` 异步执行读写操作，提高效率
- **LLM多轮工具调用**: ReAct工作原理，模型根据上下文判断是否调用工具，工具结果回填后继续思考
- **模型**：DeepSeek（`deepseek-flash`，OpenAI 兼容接口，`base_url="https://api.deepseek.com"`）
- **智能体范式**：Function Calling → MCP → ReAct
- **可靠性**：Checkpoint 断点续跑 + 随机故障注入测试
- **存储**：MySQL（用户信息）、JSON 文件（checkpoint）

## 功能说明
main.py中，这里作为短期记忆，仅单次对话的记忆，这个项目并没有做上下文压缩多次对话会消耗大量token
<img width="658" height="146" alt="image" src="https://github.com/user-attachments/assets/8458b20c-251b-4a4c-9793-b657ae21d8f8" />


<img width="514" height="493" alt="image" src="https://github.com/user-attachments/assets/a6bd114b-da8e-46f1-9328-4611c92e1d15" />
这里为话题恢复功能，保存和load都在checkpoint.py里面

## 模式参考
主要老师：GPT-5.6
工具：codex、Trae
openai 官方示例 https://github.com/openai/openai-python/tree/main/examples/agent.py
opencode 官方示例 https://opencode.ai/v2/docs/build/sdk/
langchain 官方示例 https://python.langchain.com/docs/
