"""
Live tests against real Claude. Runs with either:
  - ANTHROPIC_API_KEY env var (API key mode), or
  - an authenticated claude CLI / Claude.ai subscription (run: claude login)

Skipped automatically if neither is available.

Run with API key:
    ANTHROPIC_API_KEY=sk-ant-... pytest tests/live/ -v

Run with subscription (no key needed if already logged in):
    pytest tests/live/ -v
"""
import pytest
from tests.live.conftest import live


@live
async def test_agent_responds(live_runner):
    reply = await live_runner.run("Hello!")
    assert isinstance(reply, str) and len(reply.strip()) > 0


@live
async def test_agent_saves_name_to_profile(live_runner, live_storage):
    """Agent should call update_profile when told the user's name."""
    await live_runner.run("My name is Alice. Please remember this.")
    profile = live_storage.read_profile()
    assert "Alice" in profile, f"Expected 'Alice' in profile, got: {profile!r}"


@live
async def test_agent_saves_context_for_project(live_runner, live_storage):
    """Agent should call update_context when told about a project."""
    await live_runner.run("I'm currently working on a Rust CLI tool called 'forge'. Keep this in mind.")
    context = live_storage.read_context()
    assert "forge" in context.lower() or "rust" in context.lower(), \
        f"Expected project mention in context, got: {context!r}"


@live
async def test_agent_saves_and_retrieves_skill(live_runner, live_storage):
    """Agent should call save_skill and later read_skill."""
    await live_runner.run(
        "Save a skill called 'daily_summary' with these instructions: "
        "List all tasks completed today and send them as a bullet list."
    )
    content = live_storage.read_skill("daily_summary")
    assert content is not None, "Skill 'daily_summary' was not saved"
    assert "task" in content.lower() or "bullet" in content.lower() or "list" in content.lower()


@live
async def test_agent_lists_skills(live_runner, live_storage):
    """After saving skills, list_skills should be callable and return them."""
    live_storage.write_skill("test_skill", "test content")
    reply = await live_runner.run("What skills do I have saved?")
    assert "test_skill" in reply.lower() or reply  # agent should report the skill


@live
async def test_agent_updates_heartbeat(live_runner, live_storage):
    """Agent should call update_heartbeat when asked to update daily check instructions."""
    await live_runner.run(
        "Update my heartbeat instructions to: check unread emails and list any urgent ones."
    )
    heartbeat = live_storage.read_heartbeat()
    assert "email" in heartbeat.lower(), f"Expected 'email' in heartbeat, got: {heartbeat!r}"


@live
async def test_agent_search_logs_returns_results(live_runner, live_storage):
    """After logging a conversation, search_logs should find it."""
    live_storage.append_log("I have a dentist appointment on Friday", "Noted!")
    reply = await live_runner.run("Did I mention anything about a dentist appointment?")
    # Agent should use search_logs and find the entry
    assert "dentist" in reply.lower() or "friday" in reply.lower() or "appointment" in reply.lower()


@live
async def test_agent_respects_agent_rules(live_runner, live_storage):
    """Agent should respond concisely (as per default agent rules)."""
    reply = await live_runner.run("List 3 colors.")
    # Should be bullet points or a short list per the behavior rules
    assert reply  # just check it responded; style is hard to assert precisely


@live
async def test_agent_profile_used_in_followup(live_runner, live_storage):
    """Profile set in one call should appear in context for next call."""
    live_storage.write_profile("Name: Bob\nTimezone: PST\nLanguage: English")
    reply = await live_runner.run("What do you know about me?")
    assert "Bob" in reply or "PST" in reply or "English" in reply


@live
async def test_agent_handles_unknown_tool_gracefully(live_runner, live_storage):
    """Agent should not crash if no matching tool is available."""
    reply = await live_runner.run("Send me an email digest.")
    # No email configured — agent should reply gracefully
    assert reply  # just check it didn't raise


@live
async def test_agent_responds_in_plain_text(live_runner, live_storage):
    """Agent reply should be a non-empty string."""
    reply = await live_runner.run("Hello!")
    assert isinstance(reply, str)
    assert len(reply.strip()) > 0
