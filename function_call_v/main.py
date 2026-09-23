import os
import json

from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path

from miniagent.function_call_v.tool import (
    calculator,
    get_weather,
    get_time,
    save_user_info,
    get_user_info,
    # read_file,
    # write_file,
    # edit_file
    # create_directory,
    # delete_directory,
    # create_file,
    # delete_file,
    # move_file,
    # copy_file,
    # rename_directory,
    # rename_file,
    # list_files,
    # list_directories
)

#function call example

load_dotenv(Path(__file__).parent / ".env")

client = OpenAI( 
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com"
    )

tool_map = {
    "calculator": calculator,
    "get_weather": get_weather,
    "get_time": get_time,
    "save_user_info": save_user_info,
    "get_user_info": get_user_info
}

tools = [
            {
                "type": "function",
                "function": {
                    "name": "calculator",
                    "description": "计算数学表达式",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "expression": {
                                "type": "string",
                                "description": "数学表达式，例如 23*45"
                            }
                        },
                        "required": ["expression"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "获取天气",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": "string",
                                "description": "城市名称，例如北京"
                            }
                        },
                        "required": ["city"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_time",
                    "description": "获取当前时间",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "format": {
                                "type": "string",
                                "description": "时间格式，例如 HH:mm"
                            }
                        },
                        "required": ["format"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "save_user_info",
                    "description": "保存用户信息",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {
                                "type": "string",
                                "description": "用户ID"
                            },
                            "info": {
                                "type": "object",
                                "description": "用户信息"
                                }
                            }
                        },
                    "required": ["user_id", "info"]
                }
            },
            {
                "type":"function",
                "function": {
                    "name": "get_user_info",
                    "description": "获取用户信息",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "user_id": {
                                "type": "string",
                                "description": "用户ID"
                            }
                        },
                        "required": ["user_id"]
                    }
                }

            }
        ]

#对话记忆
messages = []

while True:
    content = input("user:")
    if content.lower() == "exit":
        break

    messages = [
        {
            "role": "user",
            "content": content
        }
    ]

    response = client.chat.completions.create(
        model="deepseek-flash",
        messages=messages,
        tools=tools
    )

    # print(response.choices[0].message)
    message = response.choices[0].message

#     if message.tool_calls:
#         tool_call = message.tool_calls[0]

#         print("模型请求调用工具：")
#         print(tool_call.function.name)
#         arguments = json.loads(
#             tool_call.function.arguments.replace("\\n", "")
#         )

#         if tool_call.function.name == "calculator":
#             result = calculator(arguments["expression"])
#         elif tool_call.function.name == "get_weather":
#             result = get_weather(arguments["city"])
#         print("工具调用结果：")
#         print(result)

#     messages.append(message)
#     messages.append(
#         {
#             "role": "tool",
#             "tool_call_id": tool_call.id,
#             "content": result
#         }
#     )

#     final_response = client.chat.completions.create(
#         model="deepseek-flash",
#         messages=messages,
#         tools=tools
#     )

#     print(
#         final_response.choices[0].message.content
#     )

# messages.append(
#     {
#         "role": "user",
#         "content": content
#     }
# )
    #如果没有调用工具，直接返回内容
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

    for tool_call in message.tool_calls:
        tool_name = tool_call.function.name
        tool_id = tool_call.id
        arguments = json.loads(
            tool_call.function.arguments or "{}"
        )
        
        print(f"\n[调用工具] {tool_name}")
        print(f"[参数] {arguments}")

        tool_func = tool_map[tool_name]

        result = tool_func(**arguments)

        print(f"[工具结果] {result}\n")

        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_id,
                "content": str(result)
            }
        )

    final_response = client.chat.completions.create(
        model="deepseek-flash",
        messages=messages,
        tools=tools
    )

    final_content = final_response.choices[0].message.content
    print("deepseek-flash:", message.tool_calls)
    print("deepseek-flash:", final_content)

    messages.append(
        {
            "role": "assistant",
            "content": final_content
        }
    )