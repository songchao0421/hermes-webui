#!/bin/bash
# 生成自签 SSL 证书（Hermes WebUI 内网使用）
# 用法: bash scripts/gen-ssl.sh
# 生成文件：certs/hermes-webui.key + certs/hermes-webui.crt（有效期 365 天）

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CERTDIR="$SCRIPT_DIR/../certs"
mkdir -p "$CERTDIR"

echo ""
echo "========================================"
echo "  Hermes WebUI - 自签 SSL 证书生成"
echo "========================================"
echo ""
echo "  证书将生成在: $CERTDIR"
echo ""

if ! command -v openssl &>/dev/null; then
    echo "[错误] 未找到 openssl，请先安装:"
    echo "  macOS:  brew install openssl"
    echo "  Linux:  sudo apt install openssl / sudo yum install openssl"
    exit 1
fi

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "$CERTDIR/hermes-webui.key" \
    -out "$CERTDIR/hermes-webui.crt" \
    -subj "/CN=hermes-webui.local/O=量子智能/C=CN" \
    -addext "subjectAltName=IP:192.168.1.20,IP:127.0.0.1,DNS:localhost,DNS:hermes-webui.local"

chmod 600 "$CERTDIR/hermes-webui.key"

echo ""
echo "[OK] 证书生成成功:"
echo "  私钥: $CERTDIR/hermes-webui.key"
echo "  证书: $CERTDIR/hermes-webui.crt"
echo ""
echo "下一步: 启动 Nginx (参考 config/nginx.conf)"
