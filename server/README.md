# 研时后端（yanshi-server）

「研时」考研学习平台的 FastAPI 后端：账号、离线同步、番茄 / 任务 / 错题、资料库、社区、多房间自习室、站内消息、VIP 与后台管理、AI 助教（含 SSE 流式输出）。

完整安装、前端启动与仓库规范见根目录 [README.md](../README.md)。

## 技术栈

FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2 + PyJWT + bcrypt + httpx + Pillow + boto3。
开发默认 SQLite（零外部依赖）；生产可切 MySQL 8。限流、验证码、登录锁定走进程内存。

## 功能模块

| 模块 | 说明 |
|---|---|
| 账号 | 邮箱验证码注册 / 登录、密码登录、忘记密码、JWT access/refresh 可旋转、登录失败锁定、审计日志；微信 / QQ / 手机号登录代码完整，`AUTH_CHANNELS` 开关控制 |
| 数据同步 | 本地优先：`learning_records` + `learning_operations`；expectedRevision 乐观并发、operationId 幂等、软删、配额 |
| 学习数据 | 科目、番茄记录、任务、错题（艾宾浩斯）、错误类型、梦校关系 |
| 自习室 | 公开 / 私密房间、6 位房间码、房主改名 / 换码 / 踢人 / 解散、心跳在线、留言板、目标墙、房间排行 |
| 资料库 | VIP 发布、非 VIP 链接脱敏、点赞、收藏（支持离线同步） |
| 社区 | 动态、二级评论、管理员删除并通知、励志区投稿 / 审核、梦校墙数据 |
| 站内消息 | 列表 / 未读数 / 已读；审批与审核结果站内信 + 邮件双通道 |
| AI | VIP 自填 Key（AES-256-GCM 加密）为唯一主路径；旧平台 Key 配置仅兼容读取，不参与聊天；OpenAI 兼容适配、模型列表拉取、SSE 流式对话、用量记录 |
| 后台 | 概览、成员与封禁、邀请码、功能申请审核、公告、内容审核、审计日志、站点配置、数据导出 |

## 目录结构

```text
server/
├─ app/
│  ├─ main.py / config.py / database.py / deps.py / errors.py
│  ├─ models/     账号、系统、同步、自习室、内容、附件、AI
│  ├─ schemas/    入参校验
│  ├─ routers/    auth / public / sync / rooms / resources / posts / inspirations / messages / ai / admin …
│  ├─ services/   同步、自习室、AI、邮件、附件、消息
│  └─ tests/      pytest 端到端测试（独立临时 SQLite，mock 外部服务）
├─ alembic/versions/  数据库迁移
├─ scripts/          冒烟、备份、清理脚本
├─ deploy/           yanshi.service / Nginx / 部署步骤
├─ docs/ARCHITECTURE.md
├─ requirements.txt / .env.example
├─ init-db.bat / start-dev.bat
```

## 本地启动

```powershell
cd server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python -m alembic upgrade head
python -m app.seed
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

也可直接运行 `init-db.bat` 与 `start-dev.bat`。

- Swagger：http://127.0.0.1:8000/docs
- 初始管理员：`.env` 的 `ADMIN_EMAIL` / `ADMIN_PASSWORD`（仅首次 seed 生效；密码留空会随机生成并打印一次）
- 开发验证码：打印到控制台并落 `data/mail/`

## 接口一览（前缀 `/api/v1`，统一响应 `{code,message,data}`）

- 公共：`GET /config/public`、`/announcements`、`/legal`
- 认证：`/auth/email-code|email-login|register|login|refresh|logout|reset-password|me`、`/auth/oauth/*`、`/auth/phone/*`
- 用户：`PUT /users/me`、`PUT /users/me/password`
- 同步：`GET /sync/records`、`POST /sync/commands`
- 自习室：`/rooms` 列表 / 创建、`/rooms/{id}` 详情 / 加入 / 退出 / 管理、`/rooms/join-by-code`、心跳、留言、目标、排行；兼容旧 `/room`
- 资料：`/resources` CRUD、点赞、收藏（`PUT` 为幂等收藏）
- 社区：`/posts`、`/posts/{id}/comments`、`/inspirations`、`/admin/inspirations`
- 消息：`GET /messages`、`/messages/unread-count`、已读操作
- AI：`POST /ai/chat`、`POST /ai/chat/stream`（SSE）、`/ai/scenes`、`/ai/enabled`、`/ai/key`、`/ai/models`、`/ai/conversations` CRUD
- 后台：`/admin/overview|members|requests|invites|announcements|audit-logs|config|export`

除公共接口外，请求头需带 `Authorization: Bearer <access_token>`。

## 常用命令

```powershell
.venv\Scripts\python.exe -m pytest -q                    # 全量测试
.venv\Scripts\python.exe -m alembic upgrade head         # 应用迁移
.venv\Scripts\python.exe -m alembic revision --autogenerate -m "说明"
.venv\Scripts\python.exe scripts\e2e_smoke.py            # 全链路 HTTP 冒烟（需本地服务）
.venv\Scripts\python.exe scripts\backup.py               # SQLite + 图片备份
```

测试会自建临时数据库并 mock AI，不会访问真实网络。

## 上线

见 `deploy/部署步骤.md`：生产 `.env`、systemd、Nginx、前端 dist、HTTPS、图片存储、每日备份。
