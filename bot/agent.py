import asyncio
from datetime import datetime, timezone
from functools import partial
import anthropic
from bot.storage import UserStorage

SYSTEM_TEMPLATE = """You are a helpful personal AI assistant on Telegram.

Today's date and time: {datetime}

What you know about this user:
{memory}

Be concise. Use bullet points when listing things. Respond in the same language the user writes in.

You have access to tools — use them when they help answer the user's request.
To remember something important about the user long-term, call the update_memory tool with the complete updated memory content.
"""


def build_system_prompt(storage: UserStorage) -> str:
    memory = storage.read_memory() or "Nothing known yet."
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return SYSTEM_TEMPLATE.format(datetime=now, memory=memory)


class AgentRunner:
    def __init__(self, anthropic_api_key: str, storage: UserStorage, tools: list):
        self._api_key = anthropic_api_key
        self._client = None
        self.storage = storage
        self.tools = tools
        self._tool_map = {fn.__name__: fn for fn in tools}

    @property
    def client(self):
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    async def run(self, user_message: str) -> str:
        history = self.storage.db.get_recent_messages(20)
        messages = [{"role": m["role"], "content": m["content"]} for m in history]
        messages.append({"role": "user", "content": user_message})

        system = build_system_prompt(self.storage)
        anthropic_tools = self._build_anthropic_tools()

        loop = asyncio.get_event_loop()
        kwargs = dict(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=system,
            messages=messages,
        )
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        response = await loop.run_in_executor(
            None, partial(self.client.messages.create, **kwargs)
        )

        while response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = self._call_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result),
                    })
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
            response = await loop.run_in_executor(
                None, partial(self.client.messages.create, **kwargs | {"messages": messages})
            )

        return next((b.text for b in response.content if hasattr(b, "text")), "")

    def _call_tool(self, name: str, inputs: dict) -> str:
        fn = self._tool_map.get(name)
        if not fn:
            return f"Unknown tool: {name}"
        if name == "update_memory":
            inputs = {**inputs, "storage": self.storage}
        try:
            return fn(**inputs)
        except Exception as e:
            return f"Tool error: {e}"

    def _build_anthropic_tools(self) -> list:
        import inspect
        tools = []
        for fn in self.tools:
            sig = inspect.signature(fn)
            props = {}
            required = []
            for pname, param in sig.parameters.items():
                if pname == "storage":
                    continue
                ptype = "string"
                if param.annotation in (int, float):
                    ptype = "number"
                props[pname] = {"type": ptype, "description": pname}
                if param.default is inspect.Parameter.empty:
                    required.append(pname)
            tools.append({
                "name": fn.__name__,
                "description": fn.__doc__ or fn.__name__,
                "input_schema": {
                    "type": "object",
                    "properties": props,
                    "required": required,
                }
            })
        return tools
