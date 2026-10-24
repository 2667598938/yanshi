@echo off
chcp 65001 >nul
cd /d %~dp0
echo 应用数据库迁移并初始化（系统配置 / 官方节点 / 管理员）
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m app.seed
echo.
pause
