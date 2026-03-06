import logging
import os
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from bot.config import Config
from bot.db import GlobalDB
from bot.handler import BotHandler
from bot.logger import setup_logging
from bot.scheduler import ReminderScheduler
from bot.storage import UserStorage

load_dotenv()


def main():
    os.makedirs("/data/logs", exist_ok=True)
    config = Config()
    setup_logging(config.data_dir)
    global_db = GlobalDB(os.path.join(config.data_dir, "global.db"))

    builder = Application.builder().token(config.telegram_token)
    if os.getenv("TELEGRAM_TEST_DC"):
        # Point to Telegram's test bot API server
        builder = builder.base_url("https://api.telegram.org/bot{token}/test/")
    app = builder.build()
    scheduler = ReminderScheduler(bot=app.bot)

    handler = BotHandler(config=config, global_db=global_db, scheduler=scheduler)

    # Restore persisted jobs for all approved users
    for user in global_db.list_users(status="approved"):
        storage = UserStorage(data_dir=config.data_dir, telegram_id=user["telegram_id"])
        for job in storage.db.list_active_jobs():
            scheduler.add_job(user["telegram_id"], job["id"], job["cron"], job["description"], db_path=storage.db.path)

    from bot.heartbeat import schedule_heartbeat
    from bot.tools.registry import build_tool_registry

    def make_tools_factory(config_ref):
        def tools_factory(storage, telegram_id):
            return build_tool_registry(storage, scheduler=scheduler, telegram_id=telegram_id)
        return tools_factory

    tools_factory = make_tools_factory(config)

    for user in global_db.list_users(status="approved"):
        storage = UserStorage(data_dir=config.data_dir, telegram_id=user["telegram_id"])
        schedule_heartbeat(scheduler, user["telegram_id"], storage, app.bot, tools_factory)

    scheduler.start()

    app.add_handler(CommandHandler("start", handler.start))
    app.add_handler(CommandHandler("help", handler.help_command))
    app.add_handler(CommandHandler("approve", handler.approve_command))
    app.add_handler(CommandHandler("ban", handler.ban_command))
    app.add_handler(CommandHandler("status", handler.status_command))
    app.add_handler(CommandHandler("connect", handler.connect_command))
    app.add_handler(CommandHandler("cancel", handler.cancel_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handler.message))
    app.add_handler(MessageHandler(filters.VOICE, handler.voice))
    app.add_handler(MessageHandler(filters.Document.PDF, handler.document))

    logging.getLogger(__name__).info("Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
