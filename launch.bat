@echo off
cd /d "%~dp0"
call .venv/Scripts/activate
start http://127.0.0.1:5050
python app.py 
pause