@echo off
REM 生成自签 SSL 证书（Hermes WebUI 内网使用）
REM 用法：双击运行，或在终端中执行此脚本
REM 生成文件：certs/hermes-webui.key + certs/hermes-webui.crt（有效期 365 天）

set CURDIR=%~dp0
set CERTDIR=%CURDIR%..\certs

if not exist "%CERTDIR%" mkdir "%CERTDIR%"

echo.
echo ========================================
echo   Hermes WebUI - 自签 SSL 证书生成
echo ========================================
echo.
echo   证书将生成在: %CERTDIR%
echo.

REM 检查 OpenSSL 是否可用
where openssl >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 openssl，请先安装 OpenSSL
    echo   - Windows: https://slproweb.com/products/Win32OpenSSL.html
    echo   - 或通过 chocolatey: choco install openssl
    pause
    exit /b 1
)

openssl req -x509 -nodes -days 365 -newkey rsa:2048 ^
    -keyout "%CERTDIR%\hermes-webui.key" ^
    -out "%CERTDIR%\hermes-webui.crt" ^
    -subj "/CN=hermes-webui.local/O=量子智能/C=CN" ^
    -addext "subjectAltName=IP:192.168.1.20,IP:127.0.0.1,DNS:localhost,DNS:hermes-webui.local"

if %errorlevel% equ 0 (
    echo.
    echo [OK] 证书生成成功:
    echo   私钥: %CERTDIR%\hermes-webui.key
    echo   证书: %CERTDIR%\hermes-webui.crt
    echo.
    echo 下一步: 启动 Nginx (参考 nginx.conf)
) else (
    echo [错误] 证书生成失败
)
pause
