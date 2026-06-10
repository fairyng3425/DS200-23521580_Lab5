@echo off
cd /d "%~dp0\.."
if exist .venv\Scripts\activate call .venv\Scripts\activate
python src\run_all_videos.py --frames 150 --fps 5 --save-annotated
pause
