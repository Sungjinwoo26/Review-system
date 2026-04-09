@echo off
REM Start Streamlit app
cd /d "d:\0 to 1cr\Pratice\Review system"
call .\.venv\Scripts\activate.bat
cd project
start cmd /k "streamlit run app.py --server.port 8502"
