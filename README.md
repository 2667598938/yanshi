# 研时（yanshi）

面向考研人的本地优先学习工具：番茄专注、任务清单、艾宾浩斯错题本、自习室、资料库、研友动态与 AI 助教。

前端 Vue 3 + Vite，后端 FastAPI + SQLAlchemy + Alembic。学习数据先写本机 IndexedDB，再通过同步引擎增量上云；断网也能继续计时、记错题、发草稿动态和收藏资料。

> 本项目为个人学习作品，非商用；不承诺数据安全，请自行做好备份。

## 功能概览

- **番茄钟**：倒计时 / 正向计时、暂停与超时保护、自定义长休、按学习内容统计与年度热力图
- **任务与错题本**：任务计划 / 验收；错题拍照、自定义错误类型、艾宾浩斯复习
- **离线同步**：番茄记录、任务、错题、收藏、动态草稿走本地队列，联网自动同步，冲突可手动裁决
- **自习室**：公开 / 私密房间、6 位房间码、房主改名 / 换码 / 踢人 / 解散、心跳在线、留言板、目标墙、房间排行
- **资料库**：VIP 发布、非 VIP 链接脱敏、点赞与收藏
- **社区**：动态与二级评论、励志区投稿审核、梦校墙
- **AI 助教**：考研答疑 / 作文批改 / 计划 / 复盘；VIP或审批授权可用BYOK；图片输入、SSE、日预算、上下文设置、模型目录缓存及受限只读工具/联网搜索
- **账号与会话**：邮箱验证码登录（5 分钟有效、5 次输错作废）；access token 仅驻内存，refresh token 只放 httpOnly Cookie；每个账号使用独立本地库，换号不串数据
- **账号与后台**：忘记密码、站内消息、VIP / 邀请码、功能申请、内容审核、审计日志
- **预留开关**：微信 / QQ / 手机号登录代码已实现，通过 `AUTH_CHANNELS` 控制，默认仅邮箱
- **开放与运维**：首次初始化默认关闭注册、账号上限4人；房间类型由后端开关控制；手机号绑定、持久邮件重试、迁移就绪检查、校验备份与恢复到新目录

完整功能范围、统一测试步骤及真实服务待验项见[统一验收清单](docs/acceptance-checklist.md)和[开发进度](docs/implementation-status.md)。视频小房间/云端自习室默认关闭，按PRD F-26不包含视频推流。

## 目录结构

```text
yanshi/
├─ server/                  FastAPI 后端
│  ├─ app/
│  │  ├─ models/            数据模型（账号、同步、自习室、内容、AI…）
│  │  ├─ schemas/           Pydantic 入参
│  │  ├─ routers/           接口路由
│  │  ├─ services/          业务与同步 / AI / 邮件 / 附件
│  │  └─ tests/             pytest 端到端测试
│  ├─ alembic/versions/     数据库迁移
│  ├─ scripts/              冒烟、备份、清理脚本
│  ├─ deploy/               systemd / Nginx 部署参考
│  ├─ requirements.txt
│  ├─ .env.example
│  ├─ init-db.bat           Windows 一键迁移 + 初始化
│  └─ start-dev.bat         Windows 一键启动后端
├─ web/                     Vue 3 前端
│  ├─ src/{views,components,stores,sync,api,db,utils}
│  ├─ vite.config.js        开发端口 27341，/api 代理到 8000
│  └─ package-lock.json
├─ .github/workflows/ci.yml 后端测试 + 前端构建
└─ .gitignore               前后端统一忽略规则
```

## 快速开始

### 前置要求

- Python **3.12+**
- Node.js **22+**（Vite 8 要求 Node 20.19+ / 22.12+）
- Git

### 1. 启动后端

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

macOS / Linux 把激活命令换成 `source .venv/bin/activate`，复制换成 `cp .env.example .env`。

- 接口文档：http://127.0.0.1:8000/docs
- 管理员账号取自 `.env` 的 `ADMIN_EMAIL` / `ADMIN_PASSWORD`；`ADMIN_PASSWORD` 留空时首次 seed 会随机生成并只打印一次，请在该次输出中查看
- 开发模式验证码不会发邮件，而是打印到后端控制台并落到 `server/data/mail/`

Windows 也可以用 `server\init-db.bat`（迁移 + seed）和 `server\start-dev.bat`（启动）。

### 2. 启动前端

```bash
cd web
npm ci
npm run dev
```

打开 http://localhost:27341 。开发环境下 `/api` 会由 Vite 代理到 `http://127.0.0.1:8000`，无需额外配置跨域。

## 配置说明（server/.env）

`.env` 已被统一忽略，仓库只保留 `.env.example`。常用项：

| 变量 | 说明 |
|---|---|
| `ENVIRONMENT` | `development` / `test` / `production` |
| `DATABASE_URL` | 开发默认 SQLite；生产可换 MySQL 8 |
| `JWT_SECRET` | 生产必须填写随机长串；开发留空自动生成 `data/jwt.key` |
| `AUTH_CHANNELS` | 登录渠道开关，默认 `email`；可加 `wechat,qq,phone` |
| `AUTH_EMAIL_DOMAINS` | 邮箱验证码允许的域名，默认 `qq.com`；留空表示不限制 |
| `REGISTRATION_OPEN` / `ACCOUNT_MAX_USERS` | 首次初始化注册开关与独立账号名额；已有库注册开关由后台管理 |
| `FEATURES` | 后端功能和房间类型开关，视频/云端类型默认关闭 |
| `SMS_*` | 腾讯云验证码短信；生产必须真实配置后才能启用phone渠道 |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | 初始管理员，仅在首次 seed 时生效 |
| `MAIL_CONSOLE` / `SMTP_*` | 开发打印验证码；生产配置 QQ 邮箱 SMTP |
| `IMAGE_STORAGE` / `QINIU_*` | `local` 或 `qiniu`（七牛 Kodo） |
| `VOLC_API_KEY` / `VOLC_MODEL` | 服务端兜底 AI Key（可选） |
| `AI_KEY_ENC_SECRET` | VIP 自填 Key 的 AES-256-GCM 主密钥；留空回退 JWT_SECRET 派生 |
| `AI_DAILY_LIMIT` / `AI_CUSTOM_HOSTS` | 每日请求预算与生产自定义AI网关精确域名白名单 |
| `AI_VISION_ENABLED` / `AI_TOOLS_ENABLED` / `BRAVE_SEARCH_API_KEY` | 图片、只读工具、搜索配置；模型能力需在AI设置中确认 |

## 数据库与迁移

```powershell
cd server
python -m alembic current                 # 当前版本
python -m alembic upgrade head            # 应用全部迁移
python -m alembic revision --autogenerate -m "说明"   # 修改模型后生成迁移
python -m alembic downgrade -1            # 回退一步
```

迁移前后请备份本地数据库；生产切换 MySQL 时先用同一套迁移在测试库跑通。

## 测试与构建

```powershell
cd server
python -m pytest -q

cd ..\web
npm test
npm run build
```

- 后端测试使用临时 SQLite 与 mock AI，不会访问真实网络。
- 前端回归测试使用 Vitest + fake-indexeddb，覆盖实际 Dexie 库、Pinia store、账号切换、图片补传与备份序列化。
- CI（[.github/workflows/ci.yml](.github/workflows/ci.yml)）在 push / PR 到 `main`、`dev` 时执行：后端迁移可执行性 + 全量 pytest；前端 `npm ci` + `npm test` + `npm run build`。
- 第 0 期修复范围、数据兼容规则与人工验收步骤见 [第 0 期修复说明](docs/phase0-acceptance.md)。
- 最新自动回归：后端124项、前端78项；含图片权限、工具上限、共享验证码、原子兑换、并发座位、离线队列与恢复校验。真实SMTP/短信/OAuth/七牛/AI供应商另按统一清单验收。

## 分支与提交规范

- `main`：稳定分支，只接受通过检查的合并
- `dev`：日常开发分支
- 功能 / 修复建议从 `dev` 切出独立分支，完成后发 PR 合回 `dev`
- 提交信息使用类型前缀：`feat` / `fix` / `docs` / `refactor` / `style` / `chore` / `test`

```bash
git switch dev
git switch -c feat/room-invite
# 开发、测试、提交
git push -u origin feat/room-invite
```

## 部署

部署参考见 `server/deploy/`（systemd、Nginx、步骤说明）。要点：

1. 生产 `.env` 使用独立数据库与强随机 `JWT_SECRET`，不要提交
2. 前端 `npm run build` 后将 `web/dist` 交给 Nginx 同源托管
3. 后端由 systemd 常驻，Nginx 反向代理 `/api` 与 `/health`
4. 配置 HTTPS、图片存储与每日备份后再对外提供服务

## 常见问题

- **端口被占用**：前端固定 `27341`（`strictPort`），后端默认 `8000`；先停止旧进程再启动。
- **时间显示偏差**：后端统一存 UTC，前端通过 `web/src/utils/time.js` 转本地时区，不要直接截取字符串。
- **管理员密码忘了**：`ADMIN_PASSWORD` 只在首次 seed 生效；可在数据库重置密码哈希，或用后台其他管理员账号重置。
- **离线数据不同步**：确认已登录；同步队列在 IndexedDB 的 `outbox` 表，可在「我的 → 立即同步」手动触发。

## 更多文档

- 当前架构基线（v4.0，2026-10-25）：[server/docs/ARCHITECTURE.md](server/docs/ARCHITECTURE.md)
- 产品 / 数据 / 同步设计原文：[docs/design-2026-10-25/](docs/design-2026-10-25/)
- 历史四人版架构（仅存档）：`server/docs/ARCHITECTURE-v3-4person-HISTORICAL.md`
- 部署步骤：`server/deploy/部署步骤.md`
- 前端说明：[web/README.md](web/README.md)
