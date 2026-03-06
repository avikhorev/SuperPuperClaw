import logging
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

HEARTBEAT_PROMPT = (
    "You are running a scheduled proactive check. Read the user's heartbeat instructions "
    "and use available tools to fulfil them. Send a summary message only if there is "
    "something worth reporting. Do not send a message if there is nothing to report."
)


class HeartbeatRunner:
    def __init__(self, telegram_id: int, storage, bot, tools_factory):
        self.telegram_id = telegram_id
        self.storage = storage
        self.bot = bot
        self.tools_factory = tools_factory

    async def run(self):
        from bot.agent import AgentRunner
        tools = self.tools_factory(self.storage, self.telegram_id)
        runner = AgentRunner(storage=self.storage, tools=tools)
        try:
            result = await runner.run(HEARTBEAT_PROMPT)
            if result and result.strip():
                # Don't send if Claude just says there's nothing to report
                lower = result.strip().lower()
                silence_phrases = [
                    "nothing to report", "no saved profile", "nothing worth reporting",
                    "nothing to send", "no heartbeat", "no active context",
                    "there is nothing", "nothing defined", "no instructions",
                ]
                if not any(p in lower for p in silence_phrases):
                    await self.bot.send_message(chat_id=self.telegram_id, text=result)
        except Exception as e:
            logger.error("Heartbeat failed for user %s: %s", self.telegram_id, e)


def schedule_heartbeat(scheduler, telegram_id: int, storage, bot, tools_factory, interval_minutes: int = 30):
    runner = HeartbeatRunner(
        telegram_id=telegram_id,
        storage=storage,
        bot=bot,
        tools_factory=tools_factory,
    )
    trigger = IntervalTrigger(minutes=interval_minutes)
    scheduler.scheduler.add_job(
        runner.run,
        trigger=trigger,
        id=f"heartbeat_{telegram_id}",
        replace_existing=True,
    )
