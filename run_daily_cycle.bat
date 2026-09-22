@echo off
cd /d "C:\Users\user\Desktop\新しいフォルダー\nisa_sim"
set GEMINI_API_KEY=AIzaSyD6mLhEAy2gYIkL_ju9rbRSHlZC06Tbl8Y
python gemini_trader.py >> logs\daily_run.log 2>&1
git add -A
git commit -m "daily paper trading cycle (local)" >> logs\daily_run.log 2>&1
git push >> logs\daily_run.log 2>&1
