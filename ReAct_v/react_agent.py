import asyncio
import json


READ_ONLY_TOOLS = frozenset(
    {
        "calculator",
        "get_time",
        "read_file",
        "list_files",
        "list_directories",
        "list_directory",
        "search_file",
    }
)
# from checkpoint import CheckpointStore as checkpoint_store

def think(state, client, tools):

    print(f"\n===== STEP {state.step} THINK =====")

    response = client.chat.completions.create(
        model="deepseek-flash",
        messages=state.messages,
        tools=tools
    )

    state.last_message = response.choices[0].message

    if not state.last_message.tool_calls:
        state.status = "END"
    else:
        state.status = "ACT"
    return state

async def act(state, session):

    print(f"\n===== STEP {state.step} ACT =====")

    message = state.last_message

    # 保存 assistant 的 tool call
    state.messages.append(
        message.model_dump()
    )

    state.pending_results = []

    results = []
    pending_reads = []

    async def flush_reads():
        if not pending_reads:
            return

        batch = list(pending_reads)
        pending_reads.clear()

        batch_results = await asyncio.gather(
            *(
                call_tool_and_format_result(
                    session,
                    tool_call
                )
                for tool_call in batch
            )
        )

        results.extend(batch_results)

    for tool_call in message.tool_calls:
        if tool_call.function.name in READ_ONLY_TOOLS:
            pending_reads.append(tool_call)
            continue

        await flush_reads()
        results.append(
            await call_tool_and_format_result(
                session,
                tool_call
            )
        )

    await flush_reads()

    state.pending_results = results

    state.status = "OBSERVE"

    return state

def observe(state):
    print(f"\n===== STEP {state.step} OBSERVE =====")

    for item in state.pending_results:
        print(
            f"[观察结果] {item['result']}"
        )

        state.messages.append(
            {
                "role": "tool",
                "tool_call_id": item["tool_call_id"],
                "content": item["result"]
            }
        )
    
    state.pending_results = []
    state.status = "THINK"

    return state

def convert_mcp_tools(response):
    """将MCP工具转换为OpenAI工具"""
    tools = []

    for tool in response.tools:
        tools.append(
            {
                "type": "function",
                "function": {
                            "name": tool.name,
                            "description": tool.description,
                            "parameters": tool.input_schema
                }
            }
        )

    return tools
    
async def call_mcp_tool(session, tool_call):
    """调用MCP工具"""
    tool_name = tool_call.function.name

    arguments = json.loads(
        tool_call.function.arguments or "{}"
    )
                        
    print(f"\n[调用工具] {tool_name}")

    print(f"[参数] {arguments}")

    result = await session.call_tool(
        tool_name,
        arguments
    )
    return result

async def call_tool_and_format_result(session, tool_call):
    result = await call_mcp_tool(
        session,
        tool_call
    )

    print(
        f"[工具调用结果] {result}"
    )

    return {
        "tool_call_id": tool_call.id,
        "result": str(result)
    }

async def run_agent(state, 
                    client,
                    session, 
                    tools,
                    checkpoint_store,
                    task_id
                    ):
    while state.status != "END":
        if state.step >= state.max_steps:
            print("达到最大执行步数")
            break

        state.step += 1

        if state.status == "THINK":
            state = think(
                state,
                client,
                tools
            )
        elif state.status == "ACT":
            state = await act(
                state,
                session
            )
        elif state.status == "OBSERVE":
            state = observe(
                state
            )

        # 每一步都保存 checkpoint，方便断点续跑
        checkpoint_store.save(
            task_id,
            state
        )
        print(f"[checkpoint] saved at step {state.step} -> {task_id}.json")

    return state