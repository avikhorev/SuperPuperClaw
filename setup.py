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

    # Step 2: Claude Code authentication
    print("\nStep 2: Claude Code authentication")
    print("  The bot uses Claude via Claude Code CLI (no separate API key needed).")
    auth_ok = subprocess.run(
        ["claude", "auth", "status"], capture_output=True
    ).returncode == 0
    if auth_ok:
        print("  ✓ Claude Code already authenticated")
    else:
        print("  Not authenticated. Running 'claude login'...")
        try:
            subprocess.run(["claude", "login"], check=True)
            print("  ✓ Claude Code authenticated")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("  ✗ Could not authenticate automatically.")
            print("    Install Claude Code: npm install -g @anthropic-ai/claude-code")
            print("    Then run: claude login")
            input("  Press Enter once authenticated to continue: ")

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
