# ReAct Agent TypeScript

Python `ReAct_v` 项目的 TypeScript 对等实现，保留以下行为：

- MCP stdio Server 与工具发现
- DeepSeek OpenAI 兼容接口
- `THINK -> ACT -> OBSERVE` ReAct 循环
- 连续只读工具并发，写工具串行
- JSON checkpoint 与话题恢复
- 随机故障注入恢复测试

## 环境

- Node.js 20+
- npm

## 安装与运行

```bash
npm install
copy .env.example .env
npm start
```

在 `.env` 中填写：

```dotenv
DEEPSEEK_API_KEY=your-key
```

`AGENT_ROOT` 默认是项目的上一级目录，与 Python 版默认访问
`E:\agent_project\miniagent` 的行为一致。需要修改可访问目录时再设置该项。

## 测试

```bash
npm test
```

测试会先编译 TypeScript，再运行 checkpoint 恢复和工具并发测试。
