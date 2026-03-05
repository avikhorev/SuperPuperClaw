#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/OWNER/REPO.git"
INSTALL_DIR="$HOME/mybot"

echo ""
echo "=== Bot Installer ==="
echo ""

# --- Dependency check ---
for cmd in docker git python3; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "Error: '$cmd' is required but not installed."
        echo "Install it and re-run this script."
        exit 1
    fi
done

if ! docker compose version &>/dev/null 2>&1; then
    echo "Error: 'docker compose' plugin is required."
    echo "See https://docs.docker.com/compose/install/"
    exit 1
fi

# --- Clone or update ---
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "Existing installation found at $INSTALL_DIR — updating..."
    git -C "$INSTALL_DIR" pull --quiet
else
    echo "Cloning into $INSTALL_DIR ..."
    git clone "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# --- Run interactive setup ---
python3 setup.py

# --- Add botadmin alias ---
ALIAS_LINE="alias botadmin='docker compose -f $INSTALL_DIR/docker-compose.yml exec bot python admin.py'"

for rc_file in "$HOME/.bashrc" "$HOME/.zshrc"; do
    if [ -f "$rc_file" ] && ! grep -q "botadmin" "$rc_file"; then
        echo "$ALIAS_LINE" >> "$rc_file"
        echo "  ✓ Added 'botadmin' alias to $rc_file"
    fi
done

echo ""
echo "Done!"
echo ""
echo "Reload your shell or run:"
echo "  source ~/.bashrc   (bash)"
echo "  source ~/.zshrc    (zsh)"
echo ""
echo "Then type 'botadmin' to manage your bot."
echo ""
