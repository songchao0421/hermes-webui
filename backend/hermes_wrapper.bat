@echo off
REM Hermes Wrapper for Windows - Calls WSL Ubuntu Hermes
wsl -d Ubuntu bash -c "export LC_ALL=C.UTF-8 && export LANG=C.UTF-8 && \$HOME/hermes-agent/venv/bin/hermes %*"
