import asyncio
import json
import os

from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


load_dotenv(Path(__file__).parent / ".env")

client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
)

server_params = StdioServerParameters(
    command="python",
    args=["server.py"]
)

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

async def main():
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            
            await session.initialize()
            
            response = await session.list_tools()
            print("MCP Server tool:")
            # print(response)
            for tool in response.tools:
                print(tool.name,"-",tool.description)
            
            print()
            
            tools = convert_mcp_tools(response)

            #未包装成函数
            # tools = []

            # for tool in response.tools:
            #     tools.append(
            #         {
            #             "type": "function",
            #             "function": {
            #                         "name": tool.name,
            #                         "description": tool.description,
            #                         "parameters": tool.input_schema
            #             }
            #         }
            #     )

            messages = []

            while True:

                user_input = input("user: ")

                if user_input == "exit":
                    break

                messages.append(
                    {
                        "role": "user",
                        "content": user_input
                    }
                )

                first_response = client.chat.completions.create(
                    model="deepseek-flash",
                    messages=messages,
                    tools=tools
                )

                message = first_response.choices[0].message

                if not message.tool_calls:
                    print("deepseek-flash:", message.content)
                    messages.append(
                        {
                            "role": "assistant",
                            "content": message.content
                        }
                    )
                    continue

                # 调用工具
                messages.append(message)
                
                #call mcp tool
                # for tool_call in message.tool_calls:

                #     tool_name = tool_call.function.name

                #     arguments = json.loads(
                #         tool_call.function.arguments or "{}"
                #     )
                                    
                #     print(f"\n[调用工具] {tool_name}")

                #     print(f"[参数] {arguments}")

                #     result = await session.call_tool(
                #         tool_name,
                #         arguments
                #     )
                for tool_call in message.tool_calls:
                    result = await call_mcp_tool(session, tool_call)

                    print(f"[工具结果] {result}\n")

                    result_text = str(result)

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": result_text
                        }
                    )

                    final_response = client.chat.completions.create(
                        model="deepseek-flash",
                        messages=messages,
                        tools=tools
                    )
                    print(
                        final_response.choices[0].message.content
                    )

                    final_message = final_response.choices[0].message

                    print("deepseek-flash:", final_message.content)

                    messages.append(
                        {
                            "role": "assistant",
                            "content": final_message.content
                        }
                    )

if __name__ == "__main__":
    asyncio.run(main())
