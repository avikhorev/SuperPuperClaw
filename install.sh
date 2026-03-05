#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/avikhorev/SuperPuperClaw.git"
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

# --- Docker permissions ---
# Ensure docker group exists and service is running
sudo getent group docker &>/dev/null || sudo groupadd docker
sudo systemctl start docker 2>/dev/null || true
sudo usermod -aG docker "$USER" 2>/dev/null || true

# Use sudo if needed
if ! docker info &>/dev/null 2>&1; then
    if ! sudo docker info &>/dev/null 2>&1; then
        echo "Error: Cannot connect to Docker. Make sure Docker is installed and running."
        exit 1
    fi
    DC="sudo docker compose"
else
    DC="docker compose"
fi

# --- Docker Compose ---
if ! $DC version &>/dev/null 2>&1; then
    echo "Docker Compose plugin not found — installing..."
    OS="$(uname -s)"
    if [ "$OS" = "Darwin" ]; then
        if command -v brew &>/dev/null; then
            brew install docker-compose
            mkdir -p ~/.docker/cli-plugins
            ln -sfn "$(brew --prefix)/opt/docker-compose/bin/docker-compose" ~/.docker/cli-plugins/docker-compose
        else
            echo "Error: Homebrew is required to install Docker Compose on macOS."
            echo "Install Homebrew: https://brew.sh"
            exit 1
        fi
    elif [ "$OS" = "Linux" ]; then
        COMPOSE_VERSION="$(curl -fsSL https://api.github.com/repos/docker/compose/releases/latest | grep '"tag_name"' | cut -d'"' -f4)"
        COMPOSE_DEST="/usr/local/lib/docker/cli-plugins/docker-compose"
        sudo mkdir -p /usr/local/lib/docker/cli-plugins
        sudo curl -fsSL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-$(uname -m)" \
            -o "$COMPOSE_DEST"
        sudo chmod +x "$COMPOSE_DEST"
    else
        echo "Error: Unsupported OS '$OS'. Install Docker Compose manually:"
        echo "See https://docs.docker.com/compose/install/"
        exit 1
    fi
    if ! $DC version &>/dev/null 2>&1; then
        echo "Error: Docker Compose installation failed. Please install manually:"
        echo "See https://docs.docker.com/compose/install/"
        exit 1
    fi
    echo "  ✓ Docker Compose installed"
fi

# --- Claude Code CLI ---
if ! command -v claude &>/dev/null; then
    echo "Error: Claude Code CLI is not installed."
    echo "Please install it via 'curl -fsSL https://claude.ai/install.sh | bash' and re-run this script."
    echo "See https://docs.anthropic.com/en/docs/claude-code/getting-started"
    exit 1
fi

if ! claude auth status &>/dev/null 2>&1; then
    echo "Error: Claude Code is not logged in. Please run Claude Code, login and re-run this script."
    exit 1
fi

echo "  ✓ Claude Code authenticated"

# --- Clone or update ---
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "Existing installation found at $INSTALL_DIR — updating..."
    git -C "$INSTALL_DIR" pull --quiet
else
    echo "Cloning into $INSTALL_DIR ..."
    GIT_TERMINAL_PROMPT=0 git clone "$REPO_URL" "$INSTALL_DIR"
fi

cd "$INSTALL_DIR"

# --- Run interactive setup ---
python3 setup.py "$@"

# --- Add shell aliases ---
add_alias() {
    local name="$1" definition="$2" rc_file="$3"
    [ -f "$rc_file" ] || return
    # Remove old definition if present, then append fresh
    sed -i "/alias ${name}=/d" "$rc_file"
    echo "$definition" >> "$rc_file"
}

ALIAS_BOTADMIN="alias botadmin='$DC -f $INSTALL_DIR/docker-compose.yml exec bot python admin.py'"
ALIAS_BOTAUTH="alias botauth='claude auth login && VOLUME_NAME=\$(basename $INSTALL_DIR)_claude_auth && docker run --rm -v \"\${VOLUME_NAME}:/target\" -v \"\$HOME/.claude:/source:ro\" alpine sh -c \"cp -r /source/. /target/ && chown -R 1000:1000 /target\" && $DC -f $INSTALL_DIR/docker-compose.yml restart bot && echo \"  ✓ Claude credentials updated and bot restarted\"'"
ALIAS_BOTSTATUS="alias botstatus='$DC -f $INSTALL_DIR/docker-compose.yml ps && echo && $DC -f $INSTALL_DIR/docker-compose.yml logs --tail=20 bot'"

for rc_file in "$HOME/.bashrc" "$HOME/.zshrc"; do
    [ -f "$rc_file" ] || continue
    add_alias "botadmin"  "$ALIAS_BOTADMIN"  "$rc_file"
    add_alias "botauth"   "$ALIAS_BOTAUTH"   "$rc_file"
    add_alias "botstatus" "$ALIAS_BOTSTATUS" "$rc_file"
done
echo "  ✓ Shell aliases updated (botadmin, botauth, botstatus)"
# Apply to current shell if possible
# shellcheck disable=SC1090
[ -f "$HOME/.bashrc" ] && source "$HOME/.bashrc" 2>/dev/null || true

# --- Start bot ---
# Ensure data dir exists and is writable by botuser (uid 1000) inside container
mkdir -p "$INSTALL_DIR/data"
if [ "$(stat -c '%u' "$INSTALL_DIR/data" 2>/dev/null || stat -f '%u' "$INSTALL_DIR/data")" != "1000" ]; then
    sudo chown -R 1000:1000 "$INSTALL_DIR/data" 2>/dev/null || true
fi

echo "Starting bot container..."
$DC -f "$INSTALL_DIR/docker-compose.yml" up -d --build

# --- Copy Claude credentials into container volume ---
# The volume is fresh on first install; copy host credentials so the bot is authenticated.
if [ -f "$HOME/.claude/.credentials.json" ]; then
    VOLUME_NAME="$(basename "$INSTALL_DIR")_claude_auth"
    docker run --rm \
        -v "${VOLUME_NAME}:/target" \
        -v "$HOME/.claude:/source:ro" \
        alpine sh -c "cp -r /source/. /target/ && chown -R 1000:1000 /target" \
        2>/dev/null && echo "  ✓ Claude credentials copied to container"
    $DC -f "$INSTALL_DIR/docker-compose.yml" restart bot >/dev/null 2>&1
fi


echo ""
echo "Done!"
echo ""
echo "Reload your shell or run:"
echo "  source ~/.bashrc   (bash)"
echo "  source ~/.zshrc    (zsh)"
echo ""
echo "Commands:"
echo "  botadmin   — manage users, view logs, stats"
echo "  botstatus  — show container status and recent logs"
echo "  botauth    — re-authenticate Claude Code if needed"
echo ""
