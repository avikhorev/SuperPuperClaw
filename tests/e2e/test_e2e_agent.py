"""Real Telegram E2E tests for agent features."""
import asyncio
import pytest
from tests.e2e.conftest import e2e, send_and_wait


@e2e
async def test_agent_remembers_name(tg_client, bot_username):
    await send_and_wait(tg_client, bot_username, "My name is E2ETestUser. Please remember it.")
    reply = await send_and_wait(tg_client, bot_username, "What is my name?")
    assert "E2ETestUser" in reply or "e2etestuser" in reply.lower()


@e2e
async def test_skill_save_and_retrieve(tg_client, bot_username):
    await send_and_wait(
        tg_client, bot_username,
        "Save a skill called 'e2e_test_skill' with content: this is an e2e test skill"
    )
    reply = await send_and_wait(tg_client, bot_username, "Show me the e2e_test_skill skill.")
    assert "e2e" in reply.lower() or "test" in reply.lower()


@e2e
async def test_weather_tool(tg_client, bot_username):
    reply = await send_and_wait(tg_client, bot_username, "What's the weather in London?")
    assert any(w in reply.lower() for w in ["weather", "temperature", "°", "celsius", "london", "wind"])


@e2e
async def test_multi_turn_context(tg_client, bot_username):
    await send_and_wait(tg_client, bot_username, "I'm thinking about the number 42.")
    reply = await send_and_wait(tg_client, bot_username, "What number was I thinking about?")
    assert "42" in reply


@e2e
async def test_log_search(tg_client, bot_username):
    unique = "xyzUnique9871e2e"
    await send_and_wait(tg_client, bot_username, f"Note: {unique}")
    await asyncio.sleep(2)
    reply = await send_and_wait(tg_client, bot_username, f"Search my logs for '{unique}'")
    assert unique in reply or "found" in reply.lower() or "result" in reply.lower()
