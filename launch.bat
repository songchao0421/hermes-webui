@echo off
:: launch.bat — shortcut for backward compatibility
:: Redirects to the main launcher in scripts\
cd /d "%~dp0"
call scripts\start-windows.bat
