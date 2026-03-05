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
DOCKER="docker"
if ! docker info &>/dev/null 2>&1; then
    # Ensure docker group exists and service is running
    sudo getent group docker &>/dev/null || sudo groupadd docker
    sudo systemctl start docker 2>/dev/null || true
    if sudo docker info &>/dev/null 2>&1; then
        DOCKER="sudo docker"
        sudo usermod -aG docker "$USER" 2>/dev/null || true
        echo "  ✓ Using sudo for Docker (re-login to use without sudo)"
    else
        echo "Error: Cannot connect to Docker. Make sure Docker is installed and running."
        exit 1
    fi
fi

if ! docker compose version &>/dev/null 2>&1; then
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
        mkdir -p ~/.docker/cli-plugins
        curl -fsSL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-$(uname -m)" \
            -o ~/.docker/cli-plugins/docker-compose
        chmod +x ~/.docker/cli-plugins/docker-compose
    else
        echo "Error: Unsupported OS '$OS'. Install Docker Compose manually:"
        echo "See https://docs.docker.com/compose/install/"
        exit 1
    fi
    if ! docker compose version &>/dev/null 2>&1; then
        echo "Error: Docker Compose installation failed. Please install manually:"
        echo "See https://docs.docker.com/compose/install/"
        exit 1
    fi
    echo "  ✓ Docker Compose installed"
fi

# --- Claude Code CLI ---
if ! command -v claude &>/dev/null; then
    echo "Error: Claude Code CLI is not installed."
    echo "See https://docs.anthropic.com/en/docs/claude-code/getting-started"
    exit 1
fi

if ! claude auth status &>/dev/null 2>&1; then
    echo "Error: Claude Code is not logged in. Please log in and re-run this script."
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
python3 setup.py < /dev/tty

# --- Add botadmin alias ---
ALIAS_LINE="alias botadmin='docker compose -f $INSTALL_DIR/docker-compose.yml exec bot python admin.py'
alias botauth='docker compose -f $INSTALL_DIR/docker-compose.yml exec -it bot claude auth login'"

for rc_file in "$HOME/.bashrc" "$HOME/.zshrc"; do
    if [ -f "$rc_file" ] && ! grep -q "botadmin" "$rc_file"; then
        echo "$ALIAS_LINE" >> "$rc_file"
        echo "  ✓ Added 'botadmin' alias to $rc_file"
    fi
done

# --- Authenticate Claude Code inside container ---
echo "Starting bot container..."
$DOCKER compose -f "$INSTALL_DIR/docker-compose.yml" up -d
echo ""
echo "Now authenticate Claude Code with your Claude account:"
$DOCKER compose -f "$INSTALL_DIR/docker-compose.yml" exec -it bot claude auth login
$DOCKER compose -f "$INSTALL_DIR/docker-compose.yml" restart

echo ""
echo "Done!"
echo ""
echo "Reload your shell or run:"
echo "  source ~/.bashrc   (bash)"
echo "  source ~/.zshrc    (zsh)"
echo ""
echo "Commands:"
echo "  botadmin  — manage users, view logs, stats"
echo "  botauth   — re-authenticate Claude Code if needed"
echo ""
