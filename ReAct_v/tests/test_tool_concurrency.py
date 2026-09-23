import asyncio
import json
import unittest
from types import SimpleNamespace

from react_agent import act
from status import AgentStatus


class FakeToolCall:
    def __init__(self, call_id, name, arguments=None):
        self.id = call_id
        self.type = "function"
        self.function = SimpleNamespace(
            name=name,
            arguments=json.dumps(arguments or {}),
        )

    def model_dump(self):
        return {
            "id": self.id,
            "type": self.type,
            "function": {
                "name": self.function.name,
                "arguments": self.function.arguments,
            },
        }


class FakeMessage:
    def __init__(self, tool_calls):
        self.content = None
        self.tool_calls = tool_calls

    def model_dump(self):
        return {
            "role": "assistant",
            "content": self.content,
            "tool_calls": [
                tool_call.model_dump()
                for tool_call in self.tool_calls
            ],
        }


class TrackingSession:
    def __init__(self, delays=None):
        self.delays = delays or {}
        self.active_calls = 0
        self.max_active_calls = 0
        self.events = []

    async def call_tool(self, tool_name, arguments):
        call_id = arguments["call_id"]
        self.active_calls += 1
        self.max_active_calls = max(
            self.max_active_calls,
            self.active_calls,
        )
        self.events.append(f"{call_id}:start")

        try:
            await asyncio.sleep(self.delays.get(call_id, 0))
            return f"{call_id}:done"
        finally:
            self.events.append(f"{call_id}:end")
            self.active_calls -= 1


class ToolConcurrencyTest(unittest.IsolatedAsyncioTestCase):
    async def test_consecutive_reads_run_concurrently(self):
        tool_calls = [
            FakeToolCall("read-1", "read_file", {"call_id": "read-1"}),
            FakeToolCall("read-2", "list_files", {"call_id": "read-2"}),
            FakeToolCall("read-3", "read_file", {"call_id": "read-3"}),
        ]
        session = TrackingSession(
            {
                "read-1": 0.03,
                "read-2": 0.02,
                "read-3": 0.01,
            }
        )
        state = AgentStatus(
            messages=[],
            status="ACT",
            last_message=FakeMessage(tool_calls),
        )

        await act(state, session)

        self.assertEqual(session.max_active_calls, 3)
        self.assertEqual(
            [item["tool_call_id"] for item in state.pending_results],
            ["read-1", "read-2", "read-3"],
        )

    async def test_writes_stay_serial_and_keep_original_order(self):
        tool_calls = [
            FakeToolCall("read-before", "read_file", {"call_id": "read-before"}),
            FakeToolCall("write-1", "edit_file", {"call_id": "write-1"}),
            FakeToolCall("write-2", "create_file", {"call_id": "write-2"}),
            FakeToolCall("read-after", "read_file", {"call_id": "read-after"}),
        ]
        session = TrackingSession(
            {
                "read-before": 0.03,
                "write-1": 0.02,
                "write-2": 0.02,
                "read-after": 0.01,
            }
        )
        state = AgentStatus(
            messages=[],
            status="ACT",
            last_message=FakeMessage(tool_calls),
        )

        await act(state, session)

        self.assertEqual(session.max_active_calls, 1)
        self.assertLess(
            session.events.index("read-before:end"),
            session.events.index("write-1:start"),
        )
        self.assertLess(
            session.events.index("write-1:end"),
            session.events.index("write-2:start"),
        )
        self.assertLess(
            session.events.index("write-2:end"),
            session.events.index("read-after:start"),
        )
        self.assertEqual(
            [item["tool_call_id"] for item in state.pending_results],
            ["read-before", "write-1", "write-2", "read-after"],
        )


if __name__ == "__main__":
    unittest.main()
