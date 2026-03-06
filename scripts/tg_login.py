#!/usr/bin/env python3
"""One-time Telethon login — run this interactively to create session file."""
import asyncio
import os
import sys
from pathlib import Path
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from dotenv import load_dotenv

load_dotenv()

API_ID   = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
PHONE    = os.environ["TELEGRAM_PHONE"]
SESSION  = str(Path(__file__).parent.parent / "files" / "telethon_test_session")

async def main():
    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"Already logged in as @{me.username}")
        await client.disconnect()
        return

    sent = await client.send_code_request(PHONE)
    code = input("Enter the Telegram code you received: ").strip()

    try:
        await client.sign_in(PHONE, code, phone_code_hash=sent.phone_code_hash)
    except SessionPasswordNeededError:
        pw = input("2FA password: ").strip()
        await client.sign_in(password=pw)

    me = await client.get_me()
    print(f"Logged in as @{me.username} ({me.first_name}). Session saved.")
    await client.disconnect()

asyncio.run(main())
