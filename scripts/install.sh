#!/usr/bin/env bash
#
# Hermes WebUI - Install Script（马鞍安装脚本）
# Supports: Linux, macOS, WSL
#
set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'
BOLD='\033[1m'

echo ""
echo -e "${CYAN}${BOLD}  ╔══════════════════════════════════════╗${NC}"
echo -e "${CYAN}${BOLD}  ║    马鞍 Saddle — Hermes WebUI        ║${NC}"
echo -e "${CYAN}${BOLD}  ║    WebUI for Hermes Agent + Ollama   ║${NC}"
echo -e "${CYAN}${BOLD}  ╚══════════════════════════════════════╝${NC}"
echo ""

# ── Detect environment ───────────────────────────────────────────

detect_wsl() {
    # Check if running in WSL
    if [ -f /proc/version ]; then
        if grep -q "microsoft" /proc/version 2>/dev/null || grep -q "WSL" /proc/version 2>/dev/null; then
            return 0
        fi
    fi
    if [ -n "$WSL_DISTRO_NAME" ] || [ -n "$WSL_INTEROP" ]; then
        return 0
    fi
    return 1
}

detect_macos() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        return 0
    fi
    return 1
}

detect_linux() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        return 0
    fi
    return 1
}

IS_WSL=false
IS_MACOS=false
IS_LINUX=false

if detect_wsl; then
    IS_WSL=true
    echo -e "  ${GREEN}✓${NC} Environment: WSL2 (Windows Subsystem for Linux)"
elif detect_macos; then
    IS_MACOS=true
    echo -e "  ${GREEN}✓${NC} Environment: macOS"
elif detect_linux; then
    IS_LINUX=true
    echo -e "  ${GREEN}✓${NC} Environment: Linux"
else
    echo -e "  ${YELLOW}!${NC} Unknown environment, assuming Linux-compatible"
    IS_LINUX=true
fi

# Detect Windows home if in WSL
WINDOWS_HOME=""
if [ "$IS_WSL" = true ]; then
    if [ -n "$USERPROFILE" ]; then
        # Convert Windows path to WSL path
        WIN_PATH="${USERPROFILE//\\//}"
        if [[ "$WIN_PATH" =~ ^([a-zA-Z]):(.*) ]]; then
            DRIVE="${BASH_REMATCH[1],,}"
            REST="${BASH_REMATCH[2]}"
            WINDOWS_HOME="/mnt/${DRIVE}${REST}"
        fi
    fi

    if [ -z "$WINDOWS_HOME" ] && [ -d "/mnt/c/Users" ]; then
        # Try to find the user directory
        for user_dir in /mnt/c/Users/*/; do
            user=$(basename "$user_dir")
            if [[ "$user" != "Public" && "$user" != "Default" && "$user" != "All Users" && "$user" != "Default User" ]]; then
                WINDOWS_HOME="$user_dir"
                break
            fi
        done
    fi

    if [ -n "$WINDOWS_HOME" ]; then
        echo -e "  ${GREEN}✓${NC} Windows home detected: $WINDOWS_HOME"
    fi
fi

echo ""

# ── Check prerequisites ──────────────────────────────────────────

check_command() {
    if command -v "$1" &> /dev/null; then
        echo -e "  ${GREEN}✓${NC} $1 found: $(command -v "$1")"
        return 0
    else
        echo -e "  ${RED}✗${NC} $1 not found"
        return 1
    fi
}

echo -e "${BOLD}Checking prerequisites...${NC}"
echo ""

# Python 3
PYTHON_CMD=""
if check_command python3; then
    PYTHON_CMD="python3"
elif check_command python; then
    if python --version 2>&1 | grep -q "Python 3"; then
        PYTHON_CMD="python"
        echo -e "  ${GREEN}✓${NC} python is Python 3"
    else
        echo -e "  ${RED}✗${NC} python is not Python 3"
    fi
fi

if [ -z "$PYTHON_CMD" ]; then
    echo ""
    echo -e "${RED}Python 3 is required. Install it first:${NC}"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-pip python3-venv"
    echo "  macOS: brew install python3"
    exit 1
fi

# Check Python version >= 3.10
PY_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo -e "  ${YELLOW}!${NC} Python $PY_VERSION detected — Python 3.10+ is recommended"
    echo -e "    macOS: ${CYAN}brew install python@3.11${NC}"
    echo -e "    The install will continue, but some features may not work correctly."
else
    echo -e "  ${GREEN}✓${NC} Python $PY_VERSION"
fi

# pip
if ! $PYTHON_CMD -m pip --version &> /dev/null; then
    echo -e "  ${YELLOW}!${NC} pip not found, attempting to install..."
    $PYTHON_CMD -m ensurepip --upgrade 2>/dev/null || {
        echo -e "${RED}pip is required. Install it:${NC}"
        echo "  Ubuntu/Debian: sudo apt install python3-pip"
        exit 1
    }
fi
echo -e "  ${GREEN}✓${NC} pip available"

# Check for Hermes
echo ""
HERMES_HOME="$HOME/.hermes"
HERMES_CMD=$(command -v hermes 2>/dev/null || true)

if [ -n "$HERMES_CMD" ]; then
    echo -e "  ${GREEN}✓${NC} Hermes CLI found: $HERMES_CMD"
elif [ -d "$HERMES_HOME" ]; then
    echo -e "  ${YELLOW}!${NC} Hermes home found but CLI not in PATH"
    echo -e "    Location: $HERMES_HOME"
else
    echo -e "  ${YELLOW}!${NC} Hermes not found"
    echo -e "    Hermes is required for Agent mode (file operations, code execution)"
    echo ""

    # Auto-install Hermes if possible
    if [ "$IS_WSL" = true ] || [ "$IS_LINUX" = true ]; then
        echo -e "  ${CYAN}→${NC} Attempting to install Hermes automatically..."
        if pip3 install hermes-agent --user 2>/dev/null || pip install hermes-agent --user 2>/dev/null; then
            echo -e "  ${GREEN}✓${NC} Hermes installed successfully!"
            # Reload PATH
            export PATH="$HOME/.local/bin:$PATH"
            HERMES_CMD=$(command -v hermes 2>/dev/null || true)
        else
            echo -e "  ${YELLOW}!${NC} Automatic installation failed"
            echo -e "    Please install manually: ${CYAN}pip3 install hermes-agent${NC}"
        fi
    else
        echo -e "    Install Hermes: ${CYAN}pip3 install hermes-agent${NC}"
    fi

    if [ -z "$HERMES_CMD" ]; then
        echo ""
        read -p "  Continue without Hermes? (y/N) " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
fi

# Check for Ollama
echo ""
OLLAMA_URL="http://localhost:11434"
OLLAMA_INSTALLED=false

if check_command ollama; then
    echo -e "  ${GREEN}✓${NC} Ollama installed locally"
    OLLAMA_INSTALLED=true
else
    # Try to read Ollama URL from Hermes config
    if [ -f "$HERMES_HOME/config.yaml" ]; then
        DETECTED_URL=$(grep -E "ollama_base_url|base_url" "$HERMES_HOME/config.yaml" 2>/dev/null | head -1 | awk '{print $2}' | tr -d '"')
        if [ -n "$DETECTED_URL" ]; then
            OLLAMA_URL="$DETECTED_URL"
            echo -e "  ${GREEN}✓${NC} Ollama URL from Hermes config: $OLLAMA_URL"
            OLLAMA_INSTALLED=true
        fi
    fi

    if [ "$OLLAMA_INSTALLED" = false ]; then
        echo -e "  ${YELLOW}!${NC} Ollama not found locally"
        echo ""

        # Offer to install Ollama
        if [ "$IS_MACOS" = true ]; then
            echo -e "  ${CYAN}→${NC} Ollama can be installed on macOS:"
            echo -e "    Option 1: Download from https://ollama.com/download"
            echo -e "    Option 2: Run: ${CYAN}brew install ollama${NC} (if using Homebrew)"
        elif [ "$IS_WSL" = true ]; then
            echo -e "  ${CYAN}→${NC} To install Ollama in WSL2:"
            echo -e "    ${CYAN}curl -fsSL https://ollama.com/install.sh | sh${NC}"
        else
            echo -e "  ${CYAN}→${NC} To install Ollama:"
            echo -e "    ${CYAN}curl -fsSL https://ollama.com/install.sh | sh${NC}"
        fi

        echo ""
        echo -e "  ${YELLOW}Note:${NC} You can also use a remote Ollama server"
        echo -e "        Configure it in the WebUI settings after installation"
    fi
fi

# ── macOS specific setup ────────────────────────────────────────

if [ "$IS_MACOS" = true ]; then
    echo ""
    echo -e "${CYAN}${BOLD}Running macOS setup wizard...${NC}"
    echo ""

    # Check if install-macos.sh exists
    if [ -f "$SCRIPT_DIR/install-macos.sh" ]; then
        bash "$SCRIPT_DIR/install-macos.sh"
        exit 0
    fi
fi

# ── Install Python dependencies ──────────────────────────────────

echo ""
echo -e "${BOLD}Installing Python dependencies...${NC}"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Create virtual environment
if [ ! -d "$PROJECT_DIR/.venv" ]; then
    echo "Creating virtual environment..."
    "$PYTHON_CMD" -m venv "$PROJECT_DIR/.venv"
fi

# Activate venv
source "$PROJECT_DIR/.venv/bin/activate"

# Install requirements
pip install -r "$PROJECT_DIR/backend/requirements.txt" --quiet

echo -e "  ${GREEN}✓${NC} Dependencies installed"

# ── WSL-specific notes ───────────────────────────────────────────

if [ "$IS_WSL" = true ] && [ -n "$WINDOWS_HOME" ]; then
    echo ""
    echo -e "${CYAN}${BOLD}WSL2 Windows Integration:${NC}"
    echo -e "  Windows files are accessible via: ${CYAN}$WINDOWS_HOME${NC}"
    echo -e "  Desktop:  ${CYAN}$WINDOWS_HOME/Desktop${NC}"
    echo -e "  Documents:${CYAN}$WINDOWS_HOME/Documents${NC}"
    echo ""
fi

# ── Summary ──────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}${BOLD}Installation complete!${NC}"
echo ""

if [ "$IS_WSL" = true ]; then
    echo -e "  Start WebUI from Windows: ${CYAN}double-click start-windows.bat${NC}"
    echo -e "  Or from WSL:              ${CYAN}./scripts/start.sh${NC}"
else
    echo -e "  Start WebUI: ${CYAN}./scripts/start.sh${NC}"
fi

echo -e "  Open browser: ${CYAN}http://localhost:8080${NC}"
echo ""
echo -e "  Hermes home:  ${CYAN}$HERMES_HOME${NC}"
echo -e "  Ollama URL:   ${CYAN}$OLLAMA_URL${NC}"

if [ "$OLLAMA_INSTALLED" = false ]; then
    echo ""
    echo -e "  ${YELLOW}!${NC} Ollama not detected. You can:"
    echo -e "    1. Install Ollama locally (see instructions above)"
    echo -e "    2. Configure remote Ollama in WebUI settings"
fi

echo ""
