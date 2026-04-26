#!/usr/bin/env bash
#
# Hermes WebUI - macOS Setup Script
# 自动检测 Mac 配置，安装 Ollama，推荐合适的模型
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
echo -e "${CYAN}${BOLD}  ║    马鞍 Saddle — macOS 安装向导      ║${NC}"
echo -e "${CYAN}${BOLD}  ╚══════════════════════════════════════╝${NC}"
echo ""

# ── Detect macOS hardware ───────────────────────────────────────

echo -e "${BOLD}正在检测 Mac 配置...${NC}"
echo ""

# 检测内存
RAM_BYTES=$(sysctl -n hw.memsize)
RAM_GB=$((RAM_BYTES / 1024 / 1024 / 1024))
echo -e "  ${GREEN}✓${NC} 内存: ${RAM_GB}GB"

# 检测芯片
CPU_BRAND=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo "Unknown")
if [[ "$CPU_BRAND" == *"Apple"* ]]; then
    CHIP_TYPE="apple_silicon"
    CHIP_NAME=$(sysctl -n machdep.cpu.brand_string)
    echo -e "  ${GREEN}✓${NC} 芯片: ${CHIP_NAME}"
elif [[ $(uname -m) == "arm64" ]]; then
    CHIP_TYPE="apple_silicon"
    CHIP_NAME="Apple Silicon"
    echo -e "  ${GREEN}✓${NC} 芯片: ${CHIP_NAME}"
else
    CHIP_TYPE="intel"
    CHIP_NAME="Intel ${CPU_BRAND}"
    echo -e "  ${GREEN}✓${NC} 芯片: ${CHIP_NAME}"
fi

# 检测 GPU/Metal 支持
if system_profiler SPDisplaysDataType 2>/dev/null | grep -q "Metal"; then
    METAL_SUPPORTED=true
    echo -e "  ${GREEN}✓${NC} GPU: Metal 支持"
else
    METAL_SUPPORTED=false
    echo -e "  ${YELLOW}!${NC} GPU: 无 Metal 支持"
fi

# 计算性能评分
PERFORMANCE_SCORE=0
if [[ "$CHIP_TYPE" == "apple_silicon" ]]; then
    PERFORMANCE_SCORE=$((PERFORMANCE_SCORE + 50))
fi
if [[ $RAM_GB -ge 16 ]]; then
    PERFORMANCE_SCORE=$((PERFORMANCE_SCORE + 30))
elif [[ $RAM_GB -ge 8 ]]; then
    PERFORMANCE_SCORE=$((PERFORMANCE_SCORE + 20))
else
    PERFORMANCE_SCORE=$((PERFORMANCE_SCORE + 10))
fi
if [[ "$METAL_SUPPORTED" == "true" ]]; then
    PERFORMANCE_SCORE=$((PERFORMANCE_SCORE + 20))
fi

echo ""

# ── Check prerequisites ─────────────────────────────────────────

check_command() {
    if command -v "$1" &> /dev/null; then
        echo -e "  ${GREEN}✓${NC} $1"
        return 0
    else
        return 1
    fi
}

echo -e "${BOLD}检查依赖...${NC}"
echo ""

# Python
if ! check_command python3; then
    echo -e "  ${RED}✗${NC} Python3 未安装"
    echo ""
    echo -e "${CYAN}请安装 Python 3.10+:${NC}"
    echo "  brew install python@3.11"
    echo "  或从 https://python.org 下载安装"
    exit 1
fi

# 检查 Python 版本
PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo -e "  ${GREEN}✓${NC} Python ${PY_VERSION}"

# pip
if ! python3 -m pip --version &> /dev/null; then
    echo -e "  ${YELLOW}!${NC} pip 未找到，尝试安装..."
    python3 -m ensurepip --upgrade 2>/dev/null || {
        echo -e "${RED}请手动安装 pip${NC}"
        exit 1
    }
fi
echo -e "  ${GREEN}✓${NC} pip"

# ── Check/Install Ollama ────────────────────────────────────────

echo ""
echo -e "${BOLD}检查 Ollama...${NC}"
echo ""

OLLAMA_INSTALLED=false
if check_command ollama; then
    OLLAMA_INSTALLED=true
    echo -e "  ${GREEN}✓${NC} Ollama 已安装"
else
    echo -e "  ${YELLOW}!${NC} Ollama 未安装"
    echo ""

    # 根据性能评分给出建议
    if [[ $PERFORMANCE_SCORE -lt 40 ]]; then
        echo -e "${YELLOW}⚠️  您的 Mac 配置较低（性能评分: ${PERFORMANCE_SCORE}/100）${NC}"
        echo ""
        echo "推荐选项："
        echo "  1) 安装轻量模型（本地运行，适合简单任务）"
        echo "  2) 连接到局域网 Ollama 服务器（推荐）"
        echo "  3) 跳过，稍后手动配置"
        echo ""
        read -p "请选择 [1-3]: " choice

        case $choice in
            1)
                install_ollama_macos
                ;;
            2)
                setup_remote_ollama
                ;;
            3)
                echo "跳过 Ollama 安装"
                ;;
        esac
    else
        echo -e "${GREEN}✓${NC} 您的 Mac 配置良好（性能评分: ${PERFORMANCE_SCORE}/100）"
        echo ""
        read -p "是否安装 Ollama? [Y/n] " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            install_ollama_macos
        fi
    fi
fi

install_ollama_macos() {
    echo ""
    echo -e "${CYAN}→ 正在安装 Ollama...${NC}"
    echo ""

    # 下载 Ollama
    if [[ "$CHIP_TYPE" == "apple_silicon" ]]; then
        OLLAMA_URL="https://ollama.com/download/Ollama-darwin-arm64.zip"
    else
        OLLAMA_URL="https://ollama.com/download/Ollama-darwin-amd64.zip"
    fi

    echo "下载 Ollama..."
    curl -L -o /tmp/ollama.zip "$OLLAMA_URL" --progress-bar

    echo "解压安装包..."
    unzip -q /tmp/ollama.zip -d /tmp/

    echo "安装到 Applications..."
    mv /tmp/Ollama.app /Applications/

    echo "启动 Ollama..."
    open -a Ollama

    # 等待服务启动
    echo "等待 Ollama 服务启动..."
    for i in {1..30}; do
        if curl -s http://localhost:11434/api/tags &>/dev/null; then
            echo -e "  ${GREEN}✓${NC} Ollama 已就绪"
            OLLAMA_INSTALLED=true
            return 0
        fi
        sleep 1
    done

    echo -e "  ${YELLOW}!${NC} Ollama 启动超时，请手动启动 Ollama.app"
    return 1
}

setup_remote_ollama() {
    echo ""
    echo -e "${CYAN}→ 配置远程 Ollama${NC}"
    echo ""

    # 尝试自动发现
    echo "正在搜索局域网内的 Ollama 服务..."
    FOUND_IP=""

    # 获取本机 IP 段
    LOCAL_IP=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | head -1 | awk '{print $2}')
    if [[ "$LOCAL_IP" =~ ^([0-9]+\.[0-9]+\.[0-9]+)\.[0-9]+$ ]]; then
        NETWORK="${BASH_REMATCH[1]}"

        # 扫描同网段
        for i in {1..254}; do
            IP="${NETWORK}.${i}"
            if curl -s "http://${IP}:11434/api/tags" --connect-timeout 0.5 &>/dev/null; then
                FOUND_IP="${IP}:11434"
                break
            fi
        done
    fi

    if [[ -n "$FOUND_IP" ]]; then
        echo -e "  ${GREEN}✓${NC} 发现 Ollama 服务: ${FOUND_IP}"
        read -p "是否使用此地址? [Y/n] " -n 1 -r
        echo ""
        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            save_ollama_config "$FOUND_IP"
            return 0
        fi
    fi

    # 手动输入
    echo ""
    read -p "请输入 Ollama 服务器地址 (如 192.168.1.100:11434): " remote_url
    if [[ -n "$remote_url" ]]; then
        # 测试连接
        if curl -s "http://${remote_url}/api/tags" --connect-timeout 5 &>/dev/null; then
            echo -e "  ${GREEN}✓${NC} 连接成功!"
            save_ollama_config "$remote_url"
        else
            echo -e "  ${YELLOW}!${NC} 无法连接到 ${remote_url}"
            echo "      请检查服务器是否运行，以及防火墙设置"
        fi
    fi
}

save_ollama_config() {
    local url=$1
    mkdir -p "$HOME/.hermes"
    cat > "$HOME/.hermes/config.yaml" << EOF
ollama_base_url: http://${url}
EOF
    echo -e "  ${GREEN}✓${NC} 配置已保存到 ~/.hermes/config.yaml"
}

# ── Recommend/Download Model ────────────────────────────────────

if [[ "$OLLAMA_INSTALLED" == "true" ]]; then
    echo ""
    echo -e "${BOLD}推荐模型...${NC}"
    echo ""

    # 根据配置推荐模型
    if [[ "$CHIP_TYPE" == "apple_silicon" && $RAM_GB -ge 16 ]]; then
        RECOMMENDED_MODEL="gemma3:12b"
        RECOMMENDED_DESC="适合您的 M 系列芯片 + 16GB 内存"
    elif [[ "$CHIP_TYPE" == "apple_silicon" && $RAM_GB -ge 8 ]]; then
        RECOMMENDED_MODEL="gemma3:4b"
        RECOMMENDED_DESC="适合您的 M 系列芯片 + 8GB 内存"
    elif [[ $RAM_GB -ge 16 ]]; then
        RECOMMENDED_MODEL="gemma3:4b"
        RECOMMENDED_DESC="适合您的 Intel Mac + 16GB 内存"
    elif [[ $RAM_GB -ge 8 ]]; then
        RECOMMENDED_MODEL="llama3.2:3b"
        RECOMMENDED_DESC="轻量级，适合您的 8GB 内存"
    else
        RECOMMENDED_MODEL="llama3.2:1b"
        RECOMMENDED_DESC="超轻量，适合低内存配置"
    fi

    # 检查是否已有模型
    EXISTING_MODELS=$(ollama list 2>/dev/null | grep -v "NAME" | wc -l)

    if [[ $EXISTING_MODELS -eq 0 ]]; then
        echo "根据您的配置 (${CHIP_NAME}, ${RAM_GB}GB 内存)，推荐:"
        echo ""
        echo "  ${RECOMMENDED_MODEL} - ${RECOMMENDED_DESC}"
        echo ""

        read -p "是否下载此模型? [Y/n] " -n 1 -r
        echo ""

        if [[ ! $REPLY =~ ^[Nn]$ ]]; then
            echo ""
            echo -e "${CYAN}→ 正在下载 ${RECOMMENDED_MODEL}...${NC}"
            echo "    这可能需要几分钟，取决于您的网络速度"
            echo ""
            ollama pull "$RECOMMENDED_MODEL"
            echo -e "  ${GREEN}✓${NC} 模型下载完成"
        fi
    else
        echo -e "  ${GREEN}✓${NC} 已安装模型:"
        ollama list | grep -v "NAME"
    fi
fi

# ── Install Python dependencies ─────────────────────────────────

echo ""
echo -e "${BOLD}安装 Python 依赖...${NC}"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 创建虚拟环境
if [ ! -d "$PROJECT_DIR/.venv" ]; then
    echo "创建虚拟环境..."
    python3 -m venv "$PROJECT_DIR/.venv"
fi

# 激活虚拟环境
source "$PROJECT_DIR/.venv/bin/activate"

# 安装依赖
echo "安装依赖包..."
pip install -r "$PROJECT_DIR/backend/requirements.txt" --quiet

echo -e "  ${GREEN}✓${NC} 依赖安装完成"

# ── Summary ─────────────────────────────────────────────────────

echo ""
echo -e "${GREEN}${BOLD}安装完成!${NC}"
echo ""
echo -e "  启动 WebUI: ${CYAN}./scripts/start.sh${NC}"
echo -e "  打开浏览器: ${CYAN}http://localhost:8080${NC}"
echo ""

if [[ "$OLLAMA_INSTALLED" != "true" ]]; then
    echo -e "  ${YELLOW}!${NC} Ollama 未配置"
    echo "     您可以:"
    echo "       1. 安装 Ollama: https://ollama.com/download"
    echo "       2. 配置远程 Ollama: 编辑 ~/.hermes/config.yaml"
    echo ""
fi
