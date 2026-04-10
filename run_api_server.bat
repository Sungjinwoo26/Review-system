@echo off
REM Start Flask API Server for Review Intelligence Engine
cd /d "d:\0 to 1cr\Pratice\Review system"
call .\.venv\Scripts\activate.bat

REM Start Flask server on port 5000
python api_server.py
