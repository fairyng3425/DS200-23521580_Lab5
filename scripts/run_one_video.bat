@echo off
cd /d "%~dp0\.."
if exist .venv\Scripts\activate call .venv\Scripts\activate
set /p VIDEO=Nhap ten file video trong data\video, vi du crowd_city.mp4: 
python src\run_demo.py --source "data\video\%VIDEO%" --frames 150 --fps 5 --save-annotated --display
pause
