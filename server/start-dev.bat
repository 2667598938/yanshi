@echo off
chcp 65001 >nul
cd /d %~dp0
echo 启动「研时」后端（本地开发） http://127.0.0.1:8000
echo 接口文档：http://127.0.0.1:8000/docs
echo 按 Ctrl+C 停止
echo.
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
pause
