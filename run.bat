@echo off
title ClipForge - AI Clipping Platform
cd /d "%~dp0"

echo ===================================================
echo           CLIPFORGE - $0 AI CLIPPING STUDIO
echo      Offline Ready * Low-Spec CPU * 100% Free
echo ===================================================
echo.
echo Starting local clipping platform server...

start "" http://localhost:8000
python -m uvicorn app:app --host 127.0.0.1 --port 8000
pause
