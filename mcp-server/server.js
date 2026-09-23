import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
    StdioServerTransport
} from "@modelcontextprotocol/sdk/transport/stdio.js";

const server = new Server(
    {
        name: "gpt_teach",
        version: "1.0.0",
    },
    {
        capabilities: {
            tools: {}
        },
    }
);

server.setRegistry(
    "tools/list",
    async () => ({
        tools: [
            {
                name: "calculator",
                description: "计算数学表达式",
                inputSchema: {
                    type: "object",
                    properties: {
                        expression: {
                            type: "string"
                        }
                    },
                    required: ["expression"]
                }
            }
        ]
    })
);

server.setRequestHandler(
    "tools/call",
    async (request) => {

        const { name, arguments: args } = request.params;

        if (name === "calculator") {

            const result = eval(args.expression);

            return {
                content: [
                    {
                        type: "text",
                        text: String(result)
                    }
                ]
            };
        }

        throw new Error("未知工具");
    }
);

const transport = new StdioServerTransport();

await server.connect(transport);
