import asyncio
import os
from status import AgentStatus

from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from react_agent import convert_mcp_tools, run_agent
from checkpoint import CheckpointStore

load_dotenv(Path(__file__).parent / ".env")

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

server_params = StdioServerParameters(
    command="D:/anaconda/envs/mini_agent/python.exe",
    args=["agent.py"]
)

def choose_initial_task(checkpoint_store):
    records = checkpoint_store.list_all()

    if records:
        print("\n===== 已保存的话题 =====")

        for index, data in enumerate(records, start=1):
            status = data.get("status", "THINK")
            status_name = "已完成" if status == "END" else "进行中"

            print(
                f"{index}. {data.get('task_id', '未命名话题')} "
                f"[{status_name}, step={data.get('step', 0)}]"
            )

        print("输入编号恢复该话题，或直接输入新的需求。")

    else:
        print("没有已保存的话题，请输入新的需求。")

    while True:
        user_input = input("\nuser: ").strip()

        if user_input == "exit":
            return None, None

        # 输入的是编号：恢复话题
        if records and user_input.isdigit():
            index = int(user_input)

            if 1 <= index <= len(records):
                data = records[index - 1]
                task_id = data["task_id"]

                print(f"[resume] 恢复话题：{task_id}")
                status = AgentStatus.from_checkpoint(data)

                return task_id, status

            print("编号不存在，请重新输入。")
            continue

        messages = [{
            "role": "user",
            "content": user_input,
        }]

        task_id = user_input.split(" ")[0].lower().replace(" ", "_")
        status = AgentStatus(messages)

        print(f"[new] 新建话题：{task_id}")
        return task_id, status

async def main():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            
            await session.initialize()
            
            response = await session.list_tools()
            # print("MCP Server tool:")
            # print(response)
            # for tool in response.tools:
            #     print(tool.name,"-",tool.description)
            
            # print()
            
            tools = convert_mcp_tools(response)

            checkpoint_store = CheckpointStore()

            task_id, status = choose_initial_task(checkpoint_store)

            if status is None:
                return

            # messages = []

            while True:

                # user_input = input("user: ")

                # if user_input == "exit":
                #     break

                # messages.append(
                #     {
                #         "role": "user",
                #         "content": user_input
                #     }
                # )

                # first_response = client.chat.completions.create(
                #     model="deepseek-flash",
                #     messages=messages,
                #     tools=tools
                # )

                # message = first_response.choices[0].message

                # if not message.tool_calls:
                #     print("deepseek-flash:", message.content)
                #     messages.append(
                #         {
                #             "role": "assistant",
                #             "content": message.content
                #         }
                #     )
                #     continue

                # messages.append(message)

                # for tool_call in message.tool_calls:
                #     result = await call_mcp_tool(session, tool_call)

                #     print(f"[工具结果] {result}\n")

                #     result_text = str(result)

                #     messages.append(
                #         {
                #             "role": "tool",
                #             "tool_call_id": tool_call.id,
                #             "content": result_text
                #         }
                #     )

                # final_response = client.chat.completions.create(
                #     model="deepseek-flash",
                #     messages=messages,
                #     tools=tools
                # )
                # print(
                #     final_response.choices[0].message.content
                # )
                # final_message = final_response.choices[0].message
                # print("deepseek-flash:", final_message.content)
                # messages.append(
                #     {
                #         "role": "assistant",
                #         "content": final_message.content
                #     }
                # )

                # status = AgentStatus(messages)

                status = await run_agent(
                    status,
                    client,
                    session,
                    tools,
                    checkpoint_store,
                    # task_id=messages[0]["content"].split(" ")[0].lower().replace(
                    #     " ", "_"
                    task_id=task_id
                )

                # messages = status.messages

                if status.last_message:
                    print(
                        "deepseek-flash:",
                        status.last_message.content
                    )

                user_input = input("user: ").strip()

                if user_input == "exit":
                    break

                status.messages.append({
                    "role": "user",
                    "content": user_input,
                })

                # 重新进入 THINK，而不是沿用上一轮的 END
                status = AgentStatus(status.messages)

if __name__ == "__main__":
    asyncio.run(main())
