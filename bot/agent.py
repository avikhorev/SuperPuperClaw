import asyncio
import inspect
import os
from datetime import datetime, timezone

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    ResultMessage,
    create_sdk_mcp_server,
    tool as sdk_tool,
)
from bot.storage import UserStorage

SYSTEM_TEMPLATE = """You are a helpful personal AI assistant on Telegram.

Today's date and time: {datetime}

{agent_rules}

## What you know about this user

### Profile
{profile}

### Current context
{context}

You have access to tools — use them when they help answer the user's request.
{history}"""


def _build_tool_schema(fn) -> dict:
    """Build a {param: PythonType} schema dict from a function's signature."""
    sig = inspect.signature(fn)
    schema = {}
    for pname, param in sig.parameters.items():
        if pname == "storage":
            continue
        if param.annotation is int:
            schema[pname] = int
        elif param.annotation is float:
            schema[pname] = float
        else:
            schema[pname] = str
    return schema


def _wrap_tools_for_mcp(tools: list, storage: UserStorage) -> list:
    """Wrap existing tool functions as MCP-compatible tools for the Agent SDK."""
    mcp_tools = []
    for fn in tools:
        schema = _build_tool_schema(fn)
        needs_storage = getattr(fn, "_needs_storage", False)

        def make_wrapper(tool_fn, _needs_storage, _storage):
            async def wrapper(args):
                kwargs = dict(args)
                if _needs_storage:
                    kwargs["storage"] = _storage
                loop = asyncio.get_running_loop()
                try:
                    result = await loop.run_in_executor(None, lambda: tool_fn(**kwargs))
                    return {"content": [{"type": "text", "text": str(result)}]}
                except Exception as e:
                    return {"content": [{"type": "text", "text": f"Tool error: {e}"}]}
            return wrapper

        wrapper_fn = make_wrapper(fn, needs_storage, storage)
        decorated = sdk_tool(fn.__name__, fn.__doc__ or fn.__name__, schema)(wrapper_fn)
        mcp_tools.append(decorated)
    return mcp_tools


def _format_history(history: list) -> str:
    if not history:
        return ""
    lines = [f"{m['role'].capitalize()}: {m['content']}" for m in history]
    return "\n\nRecent conversation:\n" + "\n".join(lines)


def build_system_prompt(storage: UserStorage, history: list) -> str:
    profile = storage.read_profile() or "Nothing known yet."
    context = storage.read_context() or "No active context."
    agent_rules = storage.read_agent_rules()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return SYSTEM_TEMPLATE.format(
        datetime=now,
        agent_rules=agent_rules,
        profile=profile,
        context=context,
        history=_format_history(history),
    )


class AgentRunner:
    def __init__(self, storage: UserStorage, tools: list):
        self.storage = storage
        self.tools = tools
        # Cache MCP server — tools don't change between messages for the same user session
        mcp_tools = _wrap_tools_for_mcp(self.tools, self.storage)
        self._server = create_sdk_mcp_server("bot-tools", tools=mcp_tools)

    async def run(self, user_message: str) -> str:
        history = self.storage.db.get_recent_messages(20)
        system = build_system_prompt(self.storage, history)
        server = self._server
        
        # Get model from environment variable
        model = os.getenv("ANTHROPIC_DEFAULT_MODEL")

        options = ClaudeAgentOptions(
            system_prompt=system,
            allowed_tools=[],
            mcp_servers={"tools": server},
            permission_mode="bypassPermissions",
            max_turns=10,
            model=model,
        )

        text_blocks = []
        result_text = ""
        async with ClaudeSDKClient(options=options) as client:
            await client.query(user_message)
            async for message in client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock) and block.text:
                            text_blocks.append(block.text)
                elif isinstance(message, ResultMessage):
                    if message.result:
                        result_text = message.result

        return result_text or "\n".join(text_blocks) or "Sorry, I couldn't generate a response."
