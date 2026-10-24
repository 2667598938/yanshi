# 研时后端（yanshi-server）

考研学习平台「研时」的 FastAPI 后端。4 人私密邀请版：**不开放注册、无摄像头、无公开社交、不收费**。
当前版本：**v0.3 后端已全部完成，并与前端完成全栈联调（账号 / 数据同步 / 自习室 / 附件图片 / AI / 后台 / 收尾）**；后端 27 项 pytest 全绿，全链路 HTTP 冒烟 18 项全绿（`scripts/e2e_smoke.py`）。

## 技术栈

FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2 + PyJWT + bcrypt + httpx + Pillow + boto3。
本地开发用 **SQLite（WAL）**，零外部依赖（无 MySQL/Redis/Docker）；限流、验证码、登录锁定走进程内存。
生产可平滑切 MySQL（SQLAlchemy 屏蔽方言）；图片本地存储或七牛 Kodo；AI 走火山方舟豆包（Key 仅在服务端）。

## 功能模块

| 模块 | 说明 |
|---|---|
| 账号 | 邀请码注册、邮箱验证码、bcrypt、access/refresh JWT 可旋转、登录失败锁定、审计/登录日志 |
| 数据同步 | 本地优先：`learning_records` + `learning_operations`，expectedRevision 乐观并发、操作幂等、软删、配额 |
| 四人自习室 | 固定 1 个房间（code YANSHI，容量 4），心跳在线、排行榜/今日/本周/累计、连续打卡、留言板、目标墙；**无视频** |
| 附件图片 | 头像/错题/梦校图，统一转 JPEG，本地或七牛 S3 签名 URL，访问统一鉴权，每用户 200MB 配额 |
| 院校库 | 内置 7 校基础信息，管理员半自动维护；个人梦校关系走同步记录 |
| AI | 火山方舟豆包，5 场景（通用/考研答疑/作文批改/计划/复盘），会话历史落库，限流 20/分 |
| 后台 | 概览大盘、成员封禁/改名/重置密码/删除、邀请码、公告、审计日志、站点配置、全量数据导出 |

## 目录结构

```
yanshi-server/
├─ app/
│  ├─ main.py / config.py / database.py / deps.py / errors.py
│  ├─ time.py（naive UTC）/ serializers.py / seed.py / legal_text.py（协议+隐私）
│  ├─ models/      account, system, learning, room, attachment, ai
│  ├─ schemas/     account, sync, room, school, ai
│  ├─ routers/     public, auth, admin, sync, room, attachments, schools, ai
│  ├─ services/    transient, security, sync, room, attachments, image_storage, ai
│  └─ tests/       27 个端到端测试（auth/sync/room/attachment/ai/admin）
├─ alembic/versions/  5 个迁移（账号→同步→自习室→附件院校→AI）
├─ scripts/          http_check.py / smoke_ai.py / e2e_smoke.py / cleanup_dev.py / backup.py
├─ deploy/           yanshi.service / yanshi.nginx.conf / 部署步骤.md（备案后用）
├─ docs/ARCHITECTURE.md（架构基线 v3.0）
├─ requirements.txt / .env.example / start-dev.bat / init-db.bat
```

## 本地启动

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
init-db.bat                      # alembic upgrade head + seed（或手动跑这两条）
start-dev.bat                    # uvicorn --reload，端口 8000
```
- Swagger：http://127.0.0.1:8000/docs ；健康检查 `/health`
- 初始管理员：在 `.env` 的 `ADMIN_EMAIL` / `ADMIN_PASSWORD` 中配置（**仅本地，上线前改**）
- 开发模式邮箱验证码打印在后端黑窗口并落 `data/mail/*.txt`

## 接口一览（统一前缀 `/api/v1`，统一响应 `{code,message,data}`）

- 公共：`GET /config/public`、`GET /announcements`、`GET /legal`
- 认证：`/auth/email-code|register|login|refresh|logout|reset-password|me`
- 用户：`PUT /users/me`、`PUT /users/me/password`
- 同步：`GET /sync/records`、`POST /sync/commands`
- 自习室：`GET /room`、`POST /room/heartbeat`、`GET /room/ranking`、`POST|DELETE /room/messages`、`PUT /room/goal`
- 附件：`POST /attachments/avatar`、`POST /attachments/image`、`GET /attachments/view`、`DELETE /attachments`
- 院校：`GET /schools`、`GET /schools/{key}`、`POST|PUT /admin/schools`
- AI：`POST /ai/chat`、`GET /ai/scenes`、`GET /ai/enabled`、`/ai/conversations` CRUD
- 后台：`/admin/overview|members|invites|announcements|audit-logs|config|export`

认证：除公共接口外，请求头带 `Authorization: Bearer <access_token>`。

## 常用命令

```
.venv\Scripts\python.exe -m pytest app/tests -q          # 全量测试
$env:YANSHI_ADMIN_EMAIL='<管理员邮箱>'; $env:YANSHI_ADMIN_PASSWORD='<管理员密码>'   # 下面三个冒烟脚本读取这两个变量
.venv\Scripts\python.exe scripts\http_check.py           # 账号/后台冒烟
.venv\Scripts\python.exe scripts\smoke_ai.py             # 真实火山 AI 冒烟
.venv\Scripts\python.exe scripts\e2e_smoke.py            # 全链路 HTTP 冒烟（登录/邀请码/注册/同步/自习室/AI/头像/后台，自动清理临时成员）
.venv\Scripts\python.exe scripts\cleanup_dev.py          # 仅本地开发库：清理 e2e 冒烟残留（先停服务）
.venv\Scripts\python.exe scripts\backup.py              # SQLite+图片打包备份（data/backups）
.venv\Scripts\python.exe -m alembic revision --autogenerate -m "说明"   # 表结构变更
```

## 上线（备案通过后）

见 `deploy/部署步骤.md`：服务器环境、生产 `.env`、systemd、Nginx、前端 dist、HTTPS、七牛 CNAME、每日备份、公安备案与底部备案号。

> 合规红线：个人 ICP 备案通过前，后端只在本地 `127.0.0.1` 运行，**不部署公网、不恢复域名解析、服务器保持关机**；产品定位「学习工具/计时器」，不出现平台/社区/论坛字样。
