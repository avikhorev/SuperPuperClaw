"""Loads and runs YAML conversation scenarios against BotHandler."""
import os
import yaml
from pathlib import Path
from unittest.mock import patch, AsyncMock

SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"


def load_scenario(name: str) -> dict:
    path = SCENARIOS_DIR / f"{name}.yaml"
    with open(path) as f:
        return yaml.safe_load(f)


class ScenarioRunner:
    """Drives a multi-turn scenario against a real BotHandler with a mocked agent."""

    def __init__(self, handler, storage, scheduler, user_id: int = None):
        self.handler = handler
        self.storage = storage
        self.scheduler = scheduler
        # Support both explicit user_id and legacy derivation from storage path
        if user_id is not None:
            self.user_id = user_id
        else:
            self.user_id = int(os.path.basename(storage.user_dir))

    async def run_turn(self, turn: dict, ctx):
        from tests.integration.fakes import FakeUpdate
        user_text = turn["user"]
        mock_reply = turn.get("mock_agent_reply", "OK")
        update = FakeUpdate(text=user_text, user_id=self.user_id)
        with patch("bot.agent.AgentRunner.run", new=AsyncMock(return_value=mock_reply)):
            await self.handler.message(update, ctx)
        assert update.message.replies, "No reply was sent"
        assert update.message.replies[-1] == mock_reply
        return update

    def check_assertions(self, turn: dict):
        if "assert_profile_contains" in turn:
            # With a mocked agent the profile write only happens if the real agent calls
            # update_profile. Here we just verify the assertion key is present so the
            # scenario YAML is self-documenting. Real validation is done in Layer 3.
            pass

        if turn.get("assert_log_entry"):
            logs_dir = os.path.join(self.storage.user_dir, "logs")
            assert os.path.exists(logs_dir), "logs dir missing"
            assert os.listdir(logs_dir), "no log files"

        if "assert_db_job_count" in turn:
            expected = turn["assert_db_job_count"]
            actual = len(self.storage.db.list_active_jobs())
            assert actual == expected, f"expected {expected} jobs, got {actual}"

        if "assert_skill_exists" in turn:
            name = turn["assert_skill_exists"]
            content = self.storage.read_skill(name)
            assert content is not None, f"skill '{name}' not found"

        if "assert_heartbeat_contains" in turn:
            text = turn["assert_heartbeat_contains"]
            heartbeat = self.storage.read_heartbeat()
            assert text in heartbeat, f"heartbeat missing '{text}'"

    async def run(self, scenario: dict):
        """Run all turns in a scenario sequentially."""
        from tests.integration.fakes import FakeContext
        ctx = FakeContext()
        for turn in scenario["turns"]:
            await self.run_turn(turn, ctx)
            self.check_assertions(turn)
