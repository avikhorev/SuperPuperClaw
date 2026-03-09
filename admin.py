#!/usr/bin/env python3
"""Admin CLI — run via: docker compose exec bot python admin.py
   Alias: botadmin
"""
import os
import sys

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = os.getenv("DATA_DIR", "/data")

from bot.db import GlobalDB

global_db = GlobalDB(os.path.join(DATA_DIR, "global.db"))


# ── Helpers ──────────────────────────────────────────────────────────────────

def clear():
    os.system("cls" if os.name == "nt" else "clear")


def pause():
    input("\nPress Enter to continue...")


def pick_user(prompt: str = "Select user") -> dict | None:
    """Show user list and let admin pick by number or type ID directly."""
    users = global_db.list_users()
    if not users:
        print("No users found.")
        return None

    print(f"\n{prompt}:")
    for i, u in enumerate(users, 1):
        admin_tag = " [admin]" if u["is_admin"] else ""
        print(f"  [{i}] @{u['username'] or '?'} ({u['telegram_id']}) — {u['status']}{admin_tag}")
    print("  [t] Type user ID directly")

    choice = input("> ").strip()
    if choice.lower() == "t":
        raw = input("  User ID: ").strip()
        try:
            return global_db.get_user(int(raw))
        except (ValueError, TypeError):
            print("  Invalid ID.")
            return None
    try:
        idx = int(choice) - 1
        if 0 <= idx < len(users):
            return users[idx]
    except ValueError:
        pass
    print("  Invalid selection.")
    return None


# ── Menu: Stats ───────────────────────────────────────────────────────────────

def menu_stats():
    clear()
    print("=== Status & Stats ===\n")

    # Bot process uptime
    import sqlite3
    from datetime import datetime, timezone, timedelta
    try:
        with open("/proc/1/stat") as f:
            fields = f.read().split()
        uptime_ticks = int(fields[21])
        with open("/proc/uptime") as f:
            system_uptime = float(f.read().split()[0])
        ticks_per_sec = os.sysconf("SC_CLK_TCK")
        proc_uptime_sec = system_uptime - uptime_ticks / ticks_per_sec
        uptime = str(timedelta(seconds=int(proc_uptime_sec)))
        print(f"Bot status:   ✓ Running  (uptime {uptime})")
    except Exception:
        print("Bot status:   ✓ Running")

    # Users
    users = global_db.list_users()
    approved = sum(1 for u in users if u["status"] == "approved")
    pending  = sum(1 for u in users if u["status"] == "pending")
    banned   = sum(1 for u in users if u["status"] == "banned")
    print(f"\nTotal users:  {len(users)}")
    print(f"  Approved:   {approved}")
    print(f"  Pending:    {pending}{'  ← waiting for approval' if pending else ''}")
    print(f"  Banned:     {banned}")

    # Messages today
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total_messages = 0
    users_dir = os.path.join(DATA_DIR, "users")
    if os.path.isdir(users_dir):
        for uid_dir in os.listdir(users_dir):
            db_path = os.path.join(users_dir, uid_dir, "conversations.db")
            if os.path.exists(db_path):
                try:
                    conn = sqlite3.connect(db_path)
                    count = conn.execute(
                        "SELECT COUNT(*) FROM messages WHERE timestamp LIKE ?", (f"{today}%",)
                    ).fetchone()[0]
                    total_messages += count
                    conn.close()
                except Exception:
                    pass

    print(f"\nMessages today: {total_messages}")

    # Last error
    errors_log = os.path.join(DATA_DIR, "logs", "errors.log")
    if os.path.exists(errors_log):
        lines = open(errors_log).readlines()
        if lines:
            print(f"\nLast error:   {lines[-1].strip()[:120]}")
    pause()


# ── Menu: Users ───────────────────────────────────────────────────────────────

def menu_users():
    while True:
        clear()
        print("=== Users ===\n")
        print("1. List all users")
        print("2. List pending approvals")
        print("3. Approve user")
        print("4. Ban user")
        print("5. Delete user + all data")
        print("6. View user memory")
        print("0. Back")
        choice = input("> ").strip()

        if choice == "1":
            users = global_db.list_users()
            if not users:
                print("No users.")
            for u in users:
                admin_tag = " [admin]" if u["is_admin"] else ""
                print(f"  @{u['username'] or '?'} ({u['telegram_id']}) — {u['status']}{admin_tag}")
            pause()

        elif choice == "2":
            pending = global_db.list_users(status="pending")
            if not pending:
                print("No pending approvals.")
                pause()
                continue
            for u in pending:
                print(f"\n  @{u['username'] or '?'} ({u['telegram_id']}) — requested {u['created_at']}")
                action = input("  [a]pprove / [b]an / [s]kip: ").strip().lower()
                if action == "a":
                    global_db.approve_user(u["telegram_id"])
                    print("  ✓ Approved.")
                elif action == "b":
                    global_db.ban_user(u["telegram_id"])
                    print("  ✓ Banned.")
            pause()

        elif choice == "3":
            u = pick_user("Approve which user")
            if u:
                global_db.approve_user(u["telegram_id"])
                print(f"  ✓ User {u['telegram_id']} approved.")
                pause()

        elif choice == "4":
            u = pick_user("Ban which user")
            if u:
                global_db.ban_user(u["telegram_id"])
                print(f"  ✓ User {u['telegram_id']} banned.")
                pause()

        elif choice == "5":
            u = pick_user("Delete which user")
            if u:
                confirm = input(
                    f"  Delete @{u['username'] or u['telegram_id']} and ALL their data? [yes/no]: "
                ).strip()
                if confirm == "yes":
                    from bot.storage import UserStorage
                    UserStorage(DATA_DIR, u["telegram_id"]).delete()
                    global_db.delete_user(u["telegram_id"])
                    print("  ✓ User and data deleted.")
                else:
                    print("  Cancelled.")
                pause()

        elif choice == "6":
            u = pick_user("View memory for")
            if u:
                from bot.storage import UserStorage
                memory = UserStorage(DATA_DIR, u["telegram_id"]).read_memory()
                username = u["username"] or str(u["telegram_id"])
                print(f"\n--- memory.md for @{username} ---")
                print(memory if memory else "(empty)")
                print("---")
                pause()

        elif choice == "0":
            break


# ── Menu: Logs ────────────────────────────────────────────────────────────────

def menu_logs():
    while True:
        clear()
        print("=== Logs ===\n")
        print("1. View recent logs (last 50 lines)")
        print("2. View errors only")
        print("3. Search logs by user")
        print("4. Clear all logs")
        print("0. Back")
        choice = input("> ").strip()

        if choice == "1":
            path = os.path.join(DATA_DIR, "logs", "bot.log")
            if os.path.exists(path):
                with open(path) as f:
                    lines = f.readlines()
                print("".join(lines[-50:]))
            else:
                print("No log file found.")
            pause()

        elif choice == "2":
            path = os.path.join(DATA_DIR, "logs", "errors.log")
            if os.path.exists(path):
                content = open(path).read()
                print(content if content else "(no errors logged)")
            else:
                print("No error log found.")
            pause()

        elif choice == "3":
            u = pick_user("Search logs for")
            if u:
                uid = str(u["telegram_id"])
                path = os.path.join(DATA_DIR, "logs", "bot.log")
                if os.path.exists(path):
                    matches = [line for line in open(path) if uid in line]
                    if matches:
                        print(f"\nLog entries for user {uid}:\n")
                        print("".join(matches[-30:]))
                    else:
                        print(f"No log entries found for user {uid}.")
                else:
                    print("No log file found.")
                pause()

        elif choice == "4":
            confirm = input("Clear ALL logs? [yes/no]: ").strip()
            if confirm == "yes":
                for fname in ("bot.log", "errors.log"):
                    fpath = os.path.join(DATA_DIR, "logs", fname)
                    if os.path.exists(fpath):
                        open(fpath, "w").close()
                print("✓ Logs cleared.")
            else:
                print("Cancelled.")
            pause()

        elif choice == "0":
            break


# ── Main menu ─────────────────────────────────────────────────────────────────

def main():
    while True:
        clear()
        print("=== Bot Admin ===\n")
        print("1. Status & Stats")
        print("2. Users")
        print("3. Logs")
        print("0. Exit")
        choice = input("> ").strip()

        if choice == "1":
            menu_stats()
        elif choice == "2":
            menu_users()
        elif choice == "3":
            menu_logs()
        elif choice == "0":
            print("Goodbye.")
            sys.exit(0)


if __name__ == "__main__":
    main()
