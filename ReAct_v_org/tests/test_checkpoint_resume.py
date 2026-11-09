import asyncio
import json
import random
import tempfile
import unittest
from types import SimpleNamespace

from checkpoint import CheckpointStore
from react_agent import run_agent
from status import AgentStatus


class InjectedError(RuntimeError):
    pass


class RandomFaultInjector:
    """Raise a bounded number of failures at deterministic random intervals."""

    def __init__(self, seed, failure_budget=8, min_gap=2, max_gap=4):
        self.random = random.Random(seed)
        self.failure_budget = failure_budget
        self.min_gap = min_gap
        self.max_gap = max_gap
        self.gap = self.random.randint(min_gap, max_gap)
        self.failures = 0

    def hit(self, point):
        if self.failure_budget == 0:
            return

        self.gap -= 1
        if self.gap > 0:
            return

        self.failure_budget -= 1
        self.failures += 1
        self.gap = self.random.randint(self.min_gap, self.max_gap)
        raise InjectedError(f"injected failure at {point}")


class FakeToolCall:
    def __init__(self, call_id, value):
        self.id = call_id
        self.type = "function"
        self.function = SimpleNamespace(
            name="record_value",
            arguments=json.dumps({"value": value}),
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
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls

    def model_dump(self):
        return {
            "role": "assistant",
            "content": self.content,
            "tool_calls": [
                tool_call.model_dump()
                for tool_call in (self.tool_calls or [])
            ],
        }


class FakeCompletions:
    def __init__(self, target_steps, injector):
        self.target_steps = target_steps
        self.injector = injector

    def create(self, model, messages, tools):
        self.injector.hit("think")

        completed_steps = sum(
            1
            for message in messages
            if message.get("role") == "assistant"
            and message.get("tool_calls")
        )

        if completed_steps >= self.target_steps:
            message = FakeMessage(content="finished")
        else:
            next_value = completed_steps + 1
            message = FakeMessage(
                tool_calls=[
                    FakeToolCall(
                        call_id=f"call-{next_value}",
                        value=next_value,
                    )
                ]
            )

        return SimpleNamespace(
            choices=[
                SimpleNamespace(message=message)
            ]
        )


class FakeClient:
    def __init__(self, target_steps, injector):
        self.chat = SimpleNamespace(
            completions=FakeCompletions(target_steps, injector)
        )


class FakeSession:
    def __init__(self, injector):
        self.injector = injector
        self.executed_values = []

    async def call_tool(self, tool_name, arguments):
        if tool_name != "record_value":
            raise AssertionError(f"unexpected tool: {tool_name}")

        self.injector.hit("tool")
        self.executed_values.append(arguments["value"])
        return f"recorded {arguments['value']}"


class CheckpointResumeTest(unittest.TestCase):
    def test_random_failures_resume_from_latest_checkpoint(self):
        target_steps = 7
        task_id = "random-failure-resume"
        messages = [{"role": "user", "content": "run all steps"}]
        injector = RandomFaultInjector(seed=20260922)

        with tempfile.TemporaryDirectory() as temp_dir:
            store = CheckpointStore(temp_dir)
            session = FakeSession(injector)
            client = FakeClient(target_steps, injector)
            state = AgentStatus(list(messages), max_steps=30)

            attempts = 0
            while state.status != "END":
                attempts += 1
                self.assertLess(attempts, 50)

                try:
                    state = asyncio.run(
                        run_agent(
                            state,
                            client,
                            session,
                            tools=[],
                            checkpoint_store=store,
                            task_id=task_id,
                        )
                    )
                except InjectedError:
                    checkpoint = store.load(task_id)
                    self.assertIsNotNone(checkpoint)
                    self.assertIn(
                        checkpoint["status"],
                        {"THINK", "ACT", "OBSERVE"},
                    )
                    state = AgentStatus.from_dict(checkpoint)

            checkpoint = store.load(task_id)

        self.assertGreater(injector.failures, 0)
        self.assertGreater(attempts, 1)
        self.assertEqual(state.status, "END")
        self.assertEqual(checkpoint["status"], "END")
        self.assertEqual(checkpoint["step"], state.step)
        self.assertEqual(checkpoint["messages"], state.messages)

        assistant_calls = [
            message
            for message in state.messages
            if message.get("role") == "assistant"
            and message.get("tool_calls")
        ]
        tool_results = [
            message
            for message in state.messages
            if message.get("role") == "tool"
        ]

        self.assertEqual(len(assistant_calls), target_steps)
        self.assertEqual(len(tool_results), target_steps)

        result_ids = [message["tool_call_id"] for message in tool_results]
        call_ids = [
            tool_call["id"]
            for message in assistant_calls
            for tool_call in message["tool_calls"]
        ]
        self.assertEqual(result_ids, call_ids)
        self.assertEqual(sorted(set(session.executed_values)), list(range(1, target_steps + 1)))

    def test_checkpoint_keeps_last_message_for_act_resume(self):
        task_id = "act-checkpoint"

        with tempfile.TemporaryDirectory() as temp_dir:
            store = CheckpointStore(temp_dir)
            message = FakeMessage(
                tool_calls=[
                    FakeToolCall(call_id="call-1", value=1)
                ]
            )
            state = AgentStatus(
                messages=[{"role": "user", "content": "run"}],
                status="ACT",
                step=1,
                last_message=message,
            )

            store.save(task_id, state)
            restored = AgentStatus.from_dict(store.load(task_id))

        self.assertEqual(restored.status, "ACT")
        self.assertEqual(restored.last_message.tool_calls[0].id, "call-1")


if __name__ == "__main__":
    unittest.main()
