#!/usr/bin/env bash
#
# Hermes WebUI - Start Script（马鞍启动脚本）
#
set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
NC='\033[0m'
BOLD='\033[1m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo ""
echo -e "${CYAN}${BOLD}  马鞍 Saddle — The Saddle for Hermes${NC}"
echo ""

# Activate venv
if [ -d "$PROJECT_DIR/.venv" ]; then
    source "$PROJECT_DIR/.venv/bin/activate"
else
    echo "Virtual environment not found. Run ./scripts/install.sh first."
    exit 1
fi

# Parse arguments
HOST="${HERMES_WEBUI_HOST:-0.0.0.0}"
PORT="${HERMES_WEBUI_PORT:-8080}"

while [[ "$#" -gt 0 ]]; do
    case $1 in
        --port) PORT="$2"; shift ;;
        --host) HOST="$2"; shift ;;
        *) ;;
    esac
    shift
done

echo -e "  Server: ${GREEN}http://$HOST:$PORT${NC}"
echo -e "  Press Ctrl+C to stop"
echo ""

cd "$PROJECT_DIR/backend"

# Use python3 if python is not available (common on Linux/WSL2)
PYTHON_BIN="python"
if ! command -v python &>/dev/null; then
    PYTHON_BIN="python3"
fi

# Try ports in sequence if the preferred port is busy
for TRY_PORT in "$PORT" 8081 8082 8083; do
    if lsof -iTCP:"$TRY_PORT" -sTCP:LISTEN -t &>/dev/null 2>&1; then
        echo -e "  ${YELLOW}Port $TRY_PORT is busy, trying next...${NC}"
        continue
    fi
    if [ "$TRY_PORT" != "$PORT" ]; then
        echo -e "  Using port ${GREEN}$TRY_PORT${NC}"
    fi
    "$PYTHON_BIN" app.py --host "$HOST" --port "$TRY_PORT"
    exit $?
done

echo -e "${RED}All ports ($PORT, 8081, 8082, 8083) are busy. Free a port and try again.${NC}"
exit 1
