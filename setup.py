#!/usr/bin/env python3
"""Interactive setup script — run once after cloning the repo.

Optional args (skip prompts, still show settings):
  --token TOKEN
  --admin-id ID
  --google-client-id ID --google-client-secret SECRET
  --no-google
"""
import argparse
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.request
import urllib.error

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# When piped (e.g. curl | bash), stdin is the pipe not the terminal.
# Reopen /dev/tty so interactive prompts work correctly.
if not sys.stdin.isatty():
    try:
        sys.stdin = open("/dev/tty", "r")
    except OSError:
        pass


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
    with urllib.request.urlopen(url, timeout=8, context=_SSL_CTX) as r:
        data = json.loads(r.read())
    assert data["ok"], "Invalid token"
    return "@" + data["result"]["username"]


def load_existing_env():
    """Load existing .env file into a dict if it exists."""
    env = {}
    if os.path.exists(".env"):
        with open(".env") as f:
            for line in f:
                line = line.strip()
                if line and "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip()
    return env


def prompt_keep_or_change(label, current_value, secret=False):
    """Show current value and ask to keep or replace. Returns final value."""
    display = ("*" * 8 + current_value[-4:]) if secret and len(current_value) > 4 else current_value
    answer = input(f"  {label} [{display}] (Enter to keep, or type new value): ").strip()
    return answer if answer else current_value


def get_admin_telegram_id(token):
    print("\n  Send any message to your bot on Telegram, then press Enter here...")
    input("  Press Enter when done: ")
    url = f"https://api.telegram.org/bot{token}/getUpdates?limit=1&offset=-1"
    with urllib.request.urlopen(url, timeout=8, context=_SSL_CTX) as r:
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


def parse_args():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("--token")
    p.add_argument("--admin-id")
    p.add_argument("--google-client-id")
    p.add_argument("--google-client-secret")
    p.add_argument("--no-google", action="store_true")
    return p.parse_known_args()[0]


def main():
    args = parse_args()

    print("\n=== Bot Setup ===\n")

    existing = load_existing_env()
    if existing and not any(vars(args).values()):
        print("  Existing configuration found. Press Enter to keep each value, or type a new one.\n")

    env = dict(existing)

    # Step 1: Telegram
    print("Step 1: Telegram Bot Token")
    if args.token:
        token = args.token
        check("Validating token", lambda: validate_telegram_token(token))
        env["TELEGRAM_TOKEN"] = token
        display = "*" * 8 + token[-4:]
        print(f"  Token: {display}")
    elif existing.get("TELEGRAM_TOKEN"):
        token = prompt_keep_or_change("Token", existing["TELEGRAM_TOKEN"], secret=True)
        if token != existing["TELEGRAM_TOKEN"]:
            if not check("Validating token", lambda: validate_telegram_token(token)):
                print("  Invalid token — keeping existing one.")
                token = existing["TELEGRAM_TOKEN"]
        else:
            check("Validating token", lambda: validate_telegram_token(token))
        env["TELEGRAM_TOKEN"] = token
    else:
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
        print("  Not authenticated.")
        print("  Run the following command to log in:")
        print("    claude auth login")
        input("  Press Enter once authenticated to continue: ")

    # Step 3: Google (optional)
    print("\nStep 3: Google Integration (optional)")
    print("  Enables Gmail, Google Calendar, and Google Drive for your users.")
    if args.no_google:
        print("  Skipped (--no-google)")
        env.pop("GOOGLE_CLIENT_ID", None)
        env.pop("GOOGLE_CLIENT_SECRET", None)
    elif args.google_client_id:
        env["GOOGLE_CLIENT_ID"] = args.google_client_id
        env["GOOGLE_CLIENT_SECRET"] = args.google_client_secret or existing.get("GOOGLE_CLIENT_SECRET", "")
        print(f"  ✓ Google Client ID: {args.google_client_id}")
    elif existing.get("GOOGLE_CLIENT_ID"):
        keep = input("  Google integration is configured. Keep it? [Y/n]: ").strip().lower()
        if keep == "n":
            want_google = input("  Reconfigure Google integration? [y/n]: ").strip().lower() == "y"
            if want_google:
                print("  Paste your Google OAuth credentials from Google Cloud Console.")
                env["GOOGLE_CLIENT_ID"] = input("  Client ID: ").strip()
                env["GOOGLE_CLIENT_SECRET"] = input("  Client Secret: ").strip()
            else:
                env.pop("GOOGLE_CLIENT_ID", None)
                env.pop("GOOGLE_CLIENT_SECRET", None)
    else:
        want_google = input("  Enable Google integration? [y/n]: ").strip().lower() == "y"
        if want_google:
            print("  Paste your Google OAuth credentials from Google Cloud Console.")
            env["GOOGLE_CLIENT_ID"] = input("  Client ID: ").strip()
            env["GOOGLE_CLIENT_SECRET"] = input("  Client Secret: ").strip()

    write_env(env)

    # Step 4: Admin Telegram ID
    print("\nStep 4: Admin account")
    if args.admin_id:
        try:
            env["ADMIN_TELEGRAM_ID"] = str(int(args.admin_id))
            write_env(env)
            print(f"  ✓ Admin ID: {env['ADMIN_TELEGRAM_ID']}")
        except ValueError:
            print(f"  Invalid --admin-id value: {args.admin_id}")
    elif existing.get("ADMIN_TELEGRAM_ID"):
        admin_id_str = prompt_keep_or_change("Admin Telegram ID", existing["ADMIN_TELEGRAM_ID"])
        try:
            env["ADMIN_TELEGRAM_ID"] = str(int(admin_id_str))
            write_env(env)
            print(f"  ✓ Admin ID: {env['ADMIN_TELEGRAM_ID']}")
        except ValueError:
            env["ADMIN_TELEGRAM_ID"] = existing["ADMIN_TELEGRAM_ID"]
    else:
        print("  The first user to send /start to the bot will become admin.")
        print("  Start the bot, then open Telegram and send /start to your bot.")

    print("\n✓ Setup complete!")
    print("\nStart the bot:     docker compose up -d")
    print("Admin CLI:         docker compose exec bot python admin.py")
    print("                   (or use the 'botadmin' alias after reloading your shell)\n")


if __name__ == "__main__":
    main()
