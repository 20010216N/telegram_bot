@echo off
cd /d "%~dp0"
start "" /b ".\.venv\Scripts\python.exe" "%~dp0bot.py" --codex-managed-bot=telegram_bot--_2
