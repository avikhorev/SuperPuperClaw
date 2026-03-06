import logging
import os
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from bot.config import Config
from bot.db import GlobalDB
from bot.handler import BotHandler
from bot.logger import setup_logging

load_dotenv()


def main():
    os.makedirs("/data/logs", exist_ok=True)
    config = Config()
    setup_logging(config.data_dir)
    global_db = GlobalDB(os.path.join(config.data_dir, "global.db"))
    handler = BotHandler(config=config, global_db=global_db)

    app = Application.builder().token(config.telegram_token).build()
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
