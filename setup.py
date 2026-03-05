#!/usr/bin/env python3
"""Interactive setup script — run once after cloning the repo."""
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error


def check(label, fn):
    try:
        result = fn()
        suffix = f": {result}" if result else ""
        print(f"  ✓ {label}{suffix}")
        return True
    except Exception as e:
        print(f"  ✗ {label}: {e}")
        return False


def validate_telegram_token(token):
    url = f"https://api.telegram.org/bot{token}/getMe"
    with urllib.request.urlopen(url, timeout=8) as r:
        data = json.loads(r.read())
    assert data["ok"], "Invalid token"
    return "@" + data["result"]["username"]


def validate_anthropic_key(key):
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/models",
        headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
    )
    try:
        with urllib.request.urlopen(req, timeout=8):
            return "valid"
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise ValueError("Invalid API key")
        return "valid"  # other HTTP errors may still be valid keys


def get_admin_telegram_id(token):
    print("\n  Send any message to your bot on Telegram, then press Enter here...")
    input("  Press Enter when done: ")
    url = f"https://api.telegram.org/bot{token}/getUpdates?limit=1&offset=-1"
    with urllib.request.urlopen(url, timeout=8) as r:
        data = json.loads(r.read())
    updates = data.get("result", [])
    if not updates:
        raise ValueError("No messages received. Make sure you sent a message to the bot.")
    user = updates[-1]["message"]["from"]
    return user["id"], user.get("username", "")


def write_env(values):
    with open(".env", "w") as f:
        for k, v in values.items():
            if v:
                f.write(f"{k}={v}\n")
    print("\n  ✓ .env written")


def main():
    print("\n=== Bot Setup ===\n")
    env = {}

    # Step 1: Telegram
    print("Step 1: Telegram Bot Token")
    print("  Create a bot with @BotFather on Telegram and paste the token here.")
    while True:
        token = input("  Token: ").strip()
        if not token:
            continue
        if check("Validating token", lambda: validate_telegram_token(token)):
            env["TELEGRAM_TOKEN"] = token
            break
        print("  Please try again.")

    # Step 2: Anthropic
    print("\nStep 2: Anthropic API Key")
    print("  Get your key from https://console.anthropic.com/")
    while True:
        key = input("  API Key: ").strip()
        if not key:
            continue
        if check("Validating key", lambda: validate_anthropic_key(key)):
            env["ANTHROPIC_API_KEY"] = key
            break
        print("  Please try again.")

    # Step 3: Google (optional)
    print("\nStep 3: Google Integration (optional)")
    print("  Enables Gmail, Google Calendar, and Google Drive for your users.")
    want_google = input("  Enable Google integration? [y/n]: ").strip().lower() == "y"
    if want_google:
        print("  Paste your Google OAuth credentials from Google Cloud Console.")
        env["GOOGLE_CLIENT_ID"] = input("  Client ID: ").strip()
        env["GOOGLE_CLIENT_SECRET"] = input("  Client Secret: ").strip()

    write_env(env)

    # Step 4: Admin detection
    print("\nStep 4: Admin account setup")
    print("  Starting bot temporarily to detect your Telegram user ID...")
    try:
        proc = subprocess.Popen(
            ["docker", "compose", "up", "-d", "--build"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(8)
        admin_id, admin_username = get_admin_telegram_id(token)
        print(f"  ✓ Admin detected: @{admin_username} (id: {admin_id})")
    except Exception as e:
        print(f"  Could not auto-detect admin: {e}")
        admin_id_str = input("  Enter your Telegram user ID manually: ").strip()
        try:
            admin_id = int(admin_id_str)
        except ValueError:
            print("  Invalid ID. You can set it up later.")
            admin_id = None

    print("\n✓ Setup complete!")
    print("\nStart the bot:     docker compose up -d")
    print("Admin CLI:         docker compose exec bot python admin.py")
    print("                   (or use the 'botadmin' alias after reloading your shell)\n")


if __name__ == "__main__":
    main()
