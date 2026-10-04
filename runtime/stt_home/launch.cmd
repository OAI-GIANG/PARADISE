@echo off
cd /d F:\OAI\PARADISE
start "PARADISE STT HOME" python runtime\stt_home\server.py
timeout /t 2 /nobreak >nul
start "" http://127.0.0.1:8787