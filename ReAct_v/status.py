from openai.types.chat import ChatCompletionMessage

class AgentStatus:

    def __init__(self,
        messages,
        status="THINK",
        step=0,
        max_steps=50,
        last_message=None,
        pending_results=None,
        ):
        self.messages = messages
        self.status = status
        self.step = step
        self.max_steps = max_steps
        self.last_message = last_message
        self.pending_results = pending_results or []

    @classmethod
    def from_dict(cls, data):
        raw_last_message = data.get("last_message")
        last_message = (
            ChatCompletionMessage.model_validate(raw_last_message)
            if raw_last_message is not None
            else None
        )

        return cls(
            messages=data.get("messages", []),
            status=data.get("status", "THINK"),
            step=data.get("step", 0),
            max_steps=data.get("max_steps", 50),
            last_message=last_message,
            pending_results=data.get("pending_results", []),
        )