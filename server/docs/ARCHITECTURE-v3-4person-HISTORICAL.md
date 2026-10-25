> ⚠️ **历史文档（已作废）**：本文件描述的是 2026-10-23 的「4 人私密版」v3.0 基线，已被
> 《研时-开发文档-完整版-2026-10-25》替代。当前生效架构见 [ARCHITECTURE.md](ARCHITECTURE.md)，
> 设计原文见 `docs/design-2026-10-25/`。下文仅保留为技术沉淀与演进记录，**不得再按本文实现新功能**。

# 研时 v0.3 后端架构（4 人私密版 · 本地优先）

> 版本：v3.0（后端开发基线） · 2026-10-23
> 对齐：前端 `yanshi-web` v0.2（已交付的四大核心本地版）
> 裁剪自：历史《研时 PRD & 技术架构 v2.4》——v2.4 是「开放注册社区」方案（105 接口 / 35 表 / VIP / 广场 / 资料墙 / BYOK / 视频 / 内容审核），**本期全部不适用**，仅复用其番茄状态机、安全、部署等技术沉淀。
>
> **本文档是后端开发的唯一蓝图，后续每写一个模块都对照本文。**

---

## 0. 一句话定位

研时是你和另外 3 个研友**自己用**的考研学习工具，不开放注册、不公开、不收费、不做视频。前端 v0.2 已经把「番茄增强 / 任务 / 错题 / 热力图仪表盘」四大核心跑在浏览器本地（IndexedDB）；后端要解决三件事：

1. **多设备数据同步**（手机、电脑、换浏览器数据不丢，个人账号隔离）；
2. **四人自习室陪伴**（在线状态、谁在学、今日时长、排行榜、留言、目标墙——**只有状态，没有摄像头**）；
3. **云能力**（头像 / 错题图 / 梦校相册上云、AI 助教、跨设备的梦校与对话）。

---

## 1. 产品范围与边界

### 1.1 v0.3（后端上线版）要做

| 域 | 模块 | 说明 |
|---|---|---|
| 账号 | 登录 / 注册 / 找回 | 4 个账号，管理员创建为主 + 邀请码；邮箱验证码（QQ SMTP）；不开放注册 |
| 账号 | 个人资料 | 昵称、**头像上传**（v0.2 没做的头像自定义）、目标院校、考研年份、每日目标 |
| 同步 | 学习数据云同步 | 科目 / 番茄 / 任务 / 错题 / 设置，多设备双向增量同步、软删除、离线可用 |
| 图片 | 七牛对象存储 | 错题图、头像、梦校相册；后端中转上传、签名访问 |
| 自习室 | 固定四人房间 | 在线状态、当前专注状态、今日 / 累计时长、排行榜、连续光环、留言板、目标墙；无视频 |
| 梦校 | 梦校墙云端化 | 不限制数量、状态标签（意向/备选/冲刺/保底）、自定义标语、**多图相册**、半自动院校信息 |
| AI | AI 助教 | 独立 Tab；平台火山方舟 key（doubao-seed-2-1-pro）；SSE 流式；历史对话云存；考研专项场景 |
| 后台 | 极简管理后台 | 成员管理、数据概览、公告 / 考研日期、留言管理、备份、日志 |
| 公共 | 倒数日 / 官方节点 | 考研日期、官方节点由管理员维护；每日励志短句（前端内置，后端可配） |

### 1.2 明确不做（本期砍掉，需要时再开）

| 砍掉 | 原因 |
|---|---|
| 开放注册 / VIP / 功能申请审批（feature_grants） | 只 4 人，管理员直接建号 |
| 动态广场、帖子、评论、点赞、收藏、关注 | 4 人私密，不需要社区，也避免分心（你明确要求功能克制） |
| 资料链接墙（resources）、网盘打码 | 4 人不需要版权墙；后期要资料共享再单独做 |
| 视频自习室（WebRTC / TRTC / 摄像头）、打卡照 | 你明确「不做摄像头」；个人备案也不允许实时音视频 |
| 多个自习室 / 公开房间列表 | 固定一个四人房间即可 |
| BYOK（用户自带 AI Key） | 4 人直接用平台 key，无需每人配 |
| 内容审核 / 敏感词 / 举报队列 / 配额 | 私密熟人、无公开 UGC，无此义务（但仍守法，日志留存） |
| 手机短信实名、图形验证码、严格封禁体系 | 不开放、4 人；只保留基础限流 + 登录日志 |
| 服务端权威番茄计时（start/pause/heartbeat/超时裁定） | 前端 v0.2 已是**本地权威计时**，后端只接收已完成记录做同步；不重造 |
| 笔记 / 模考 / 背诵 / 分数追踪 / 轻社区 | 顺延 v0.4 之后 |

### 1.3 合规红线（长期）

- **个人 ICP 备案审核中**，审核通过前：公网服务器 `<SERVER_IP>` 保持关闭、Nginx/FastAPI 不启动、阿里云 DNS 全暂停；**后端开发全部在本地（SQLite）进行，不碰公网**。
- 备案通过、域名可访问后，才部署上线；上线后 30 日内做公安联网备案；网站底部挂 ICP 号 + 公安备案号。
- 个人备案定位为「学习工具 / 计时器」，不出现「平台 / 社区 / 论坛」字样；不开放注册、不开放发言式 UGC，正好符合。
- 要有《用户协议》《隐私政策》（4 人也要，注册时勾选）；登录 / 操作日志留存 ≥ 6 个月。
- 无视频、无直播、无公开内容，规避绝大多数内容审核义务。

---

## 2. 技术栈与关键取舍

### 2.1 技术选型

| 层 | 选型 | 说明 |
|---|---|---|
| 前端 | Vue3 + Vite + Pinia + Vue Router（已有，纯 JS） | 不换栈；新增 `src/api`、`src/sync`、登录页、AI 页 |
| 后端 | Python 3.13 + **FastAPI** + Uvicorn | 本机已有 Python 3.13.16 / pip 26 |
| ORM | SQLAlchemy 2（声明式）+ Pydantic v2 | 全部参数化，不拼 SQL |
| 迁移 | Alembic | 本地 SQLite 与生产 MySQL 各一套迁移；模型改一次、迁移跟上 |
| 数据库 · 开发 | **SQLite（单文件，零安装）** | 本地开发不装任何数据库服务 |
| 数据库 · 生产 | **MySQL 8（utf8mb4）** | 部署到服务器时切换，连接串走环境变量 |
| 缓存 / 队列 | **不引入 Redis** | 见取舍 2；4 人版用 MySQL + 内存即可 |
| 图片 | 七牛云 Kodo（空间 `sharearea`，私有，华南 cn-south-1） | boto3（S3 兼容）/ qiniu SDK；后端中转上传 + 签名 URL；正式期绑 `img.duzhi.xin` |
| 邮件 | aiosmtplib + QQ SMTP（smtp.qq.com:465 SSL） | 注册验证码、找回密码 |
| AI | httpx + 火山方舟 Ark（OpenAI 兼容，SSE） | 平台 key 存服务器 `.env`，绝不进前端 |
| 定时任务 | APScheduler（SQLAlchemyJobStore 落库） | 复习提醒、验证码清理、在线状态过期、备份 |
| 认证 | JWT 双 token（access 2h / refresh 14d）+ bcrypt | token 存 localStorage，Bearer 头，免疫 CSRF |
| 图片处理 | Pillow | 头像中心裁剪、错题图压缩、真实尺寸校验 |
| 生产部署 | Nginx + Uvicorn（systemd 或 docker compose 二选一） | 见 §16；前端 dist 由 Nginx 托管 |

### 2.2 四个关键取舍（为什么这么定）

**取舍 1 · 本地开发用 SQLite，生产用 MySQL。**
你本机没有 Docker、没有 MySQL/Redis，装这些在 Windows 上又重又容易卡。SQLite 是 Python 自带的单文件数据库，开箱即用。SQLAlchemy 屏蔽了 95% 的方言差异，同一份模型、同一套 Alembic 迁移可以在两边跑。**唯一注意**：字段类型尽量用通用类型（`String/Integer/Boolean/DateTime/Text`，JSON 用 `JSON`（MySQL 8 支持、SQLite 存 TEXT），布尔用 `Integer` 0/1），不写 MySQL 专有 DDL；后端代码里不出现裸 SQL 方言函数。生产切 MySQL 只改 `DATABASE_URL`。

**取舍 2 · 不引入 Redis。**
v2.4 自己也写了「4 人版不需要 Redis」。Redis 在开放版用于排行榜、在线状态、验证码、限流、缓存：
- 在线状态 → 一张 `room_presence` 表（`last_heartbeat_at`，查询时过滤 45 秒内），4 人毫无压力；
- 邮箱验证码 → `email_codes` 表（带过期时间、一次性标记）；
- 限流 → 进程内内存滑动窗口（单进程足够）；
- 统计缓存 → 4 人数据量极小，直接实时聚合，不缓存。
- 这样生产只跑 `Nginx + FastAPI + MySQL` 三个组件，2 核 4G 服务器更轻松，少一个容器少一份运维。

**取舍 3 · 本地优先 + 增量同步，不做服务端权威计时。**
v2.4 设想番茄由服务端计时（开始/暂停/心跳/超时全在服务端），那是为了「开放平台防刷时长」。但你前端 v0.2 已经把完整计时（含正向计时、跨零点、到点自动完成、暂停）写在本地了，体验上离线也能学。4 人版没有防刷作弊动机，所以：
- **番茄记录在本地产生、本地是事实源**，完成后通过同步引擎批量上行；
- 服务端不做 `start/pause/complete/heartbeat` 计时接口，不做超时裁定，只做「接收、存储、冲突合并、聚合展示」；
- 自习室需要的「谁正在学」是**临时状态**，由一个轻量心跳接口单独上报（不落为番茄记录），与数据同步解耦。
- 这样后端大幅简化，且前端四大核心逻辑一行不用推翻。

**取舍 4 · AI 用平台 key，不做 BYOK。**
4 个人共用一个火山方舟 key（你已在 `Fudan450/js/ai.js` 里配过 `doubao-seed-2-1-pro`），key 只存在服务器 `.env`，前端调你自己的后端 `/api/v1/ai/chat/stream`，浏览器永远看不到 key。省去 aes 加密存 Key、连接测试、多 Base URL 那一整套。

---

## 3. 系统架构

### 3.1 本地开发拓扑（备案期，全程本地）

```
浏览器（yanshi-web，vite dev :5173 或现用 27341）
   │  /api/v1/*、/uploads/* 由 Vite proxy 转发
   ▼
FastAPI（uvicorn --reload :8000，Python venv）
   │
   ├── SQLite 单文件（backend/dev.db，Alembic 建表）
   ├── 七牛云（可选：本地默认走「本地磁盘存储」，不真实传七牛，见 §9.5）
   ├── QQ SMTP（真发邮件；也可在 .env 关闭，验证码打印到控制台）
   └── 火山方舟 Ark（AI 开发时真调；没有 key 时走 mock 开关）
```

### 3.2 生产拓扑（备案通过后）

```
手机/电脑浏览器
   │  HTTPS 443
   ▼
Nginx（duzhi.xin，TLS 终止）
   ├── 静态：前端 dist（gzip、hash 长缓存、index no-cache、安全头）
   ├── /api/v1/* 反代 FastAPI（SSE 路径关 buffering）
   └── 图片：浏览器直连 img.duzhi.xin（七牛 CDN CNAME）

FastAPI（127.0.0.1:8000，uvicorn，systemd 守护，可多 worker）
   ├── MySQL 8（127.0.0.1，不暴露公网，Volume 持久化，Alembic 迁移）
   ├── 七牛云 Kodo（图片 / 备份）
   ├── QQ SMTP（邮件）
   └── 火山方舟（AI）
```

> 生产部署方式二选一：① Docker Compose（nginx + backend + mysql 三容器，最省事，届时若你愿意装 Docker）；② 裸机 systemd（apt 装 mysql、nginx，uvicorn 做成 service）。本文 §16 给两套命令，默认推荐 Docker Compose，装 Docker 有困难就用裸机。

---

## 4. 目录结构

### 4.1 后端 `D:\KAOYAN\yanshi\server`

```
yanshi-server/
├── docs/
│   └── ARCHITECTURE.md            # 本文档
├── app/
│   ├── main.py                    # FastAPI 入口、路由挂载、CORS、异常处理、定时任务启动
│   ├── config.py                  # 环境变量配置（pydantic-settings）
│   ├── database.py                # engine / SessionLocal / Base / get_db
│   ├── deps.py                    # 依赖：当前用户、管理员、限流、DB
│   ├── security.py                # JWT 签发/校验、bcrypt、token 版本
│   ├── response.py                # 统一响应信封 ok()/fail()、错误码、分页
│   ├── exceptions.py              # 业务异常 + 全局异常处理器
│   ├── models/                    # SQLAlchemy 模型（按域拆文件）
│   │   ├── __init__.py
│   │   ├── account.py             # users / invite_codes / email_codes / login_logs
│   │   ├── study.py               # subjects / sessions / tasks / mistakes
│   │   ├── attachment.py          # attachments
│   │   ├── school.py              # schools / user_schools / school_albums
│   │   ├── room.py                # rooms / room_members / room_presence / room_messages / room_goals
│   │   ├── ai.py                  # ai_conversations / ai_messages
│   │   └── system.py              # announcements / official_events / system_config / audit_logs
│   ├── schemas/                   # Pydantic 请求/响应模型
│   │   ├── auth.py · study.py · sync.py · room.py · school.py · ai.py · admin.py
│   ├── routers/
│   │   ├── auth.py                # 注册/登录/刷新/验证码/找回/当前用户
│   │   ├── users.py               # 资料/头像/密码/设置
│   │   ├── sync.py                # 同步 push/pull（核心）
│   │   ├── uploads.py             # 图片上传（七牛/本地）
│   │   ├── room.py                # 房间状态/心跳/留言/目标墙/排行
│   │   ├── schools.py             # 院校内置信息/梦校墙/相册
│   │   ├── ai.py                  # 会话/流式对话
│   │   ├── public.py              # 倒数日/官方节点/公告/健康检查
│   │   └── admin/                 # 后台（users · room · schools · config · backup · logs）
│   ├── services/
│   │   ├── sync_engine.py         # LWW 合并、tombstone、游标、幂等
│   │   ├── storage.py            # 存储抽象：本地磁盘 / 七牛（按 .env 切换）
│   │   ├── qiniu_client.py        # 七牛上传、签名 URL
│   │   ├── ai_client.py           # 火山方舟 SSE 流式转发、场景 prompt
│   │   ├── mail.py                # 验证码/找回邮件（可控制台降级）
│   │   ├── stats.py               # 时长/打卡/排行聚合（实时算，不建日聚合表）
│   │   ├── presence.py            # 在线状态（DB last_heartbeat）
│   │   └── scheduler.py           # APScheduler：清理/提醒/备份
│   └── tests/                     # pytest
│       ├── test_sync.py           # 同步合并 / 幂等 / 软删除
│       ├── test_auth.py           # 注册登录 token
│       └── test_room.py           # 在线状态与排行
├── alembic/                       # 迁移
├── scripts/
│   ├── seed.py                    # 初始管理员、7 校、固定房间、官方节点
│   └── backup.sh                  # 生产备份（mysqldump → 七牛）
├── storage_local/                 # 开发期图片落盘（.gitignore）
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

### 4.2 前端 `yanshi-web` 新增/改造

```
src/
├── api/
│   ├── http.js          # fetch 封装：baseURL、Bearer、刷新 token、统一信封/错误码
│   ├── auth.js · sync.js · upload.js · room.js · school.js · ai.js
├── sync/
│   ├── engine.js        # 同步引擎：push/pull、游标(localStorage)、失败重试
│   ├── queue.js         # 待发动作队列（弱网补发）
│   └── bootstrap.js     # 登录后全量拉取 → 合并进 Dexie
├── db/index.js          # 改造：各表加 updatedAt/deletedAt/同步字段，删除改软删
├── stores/...           # 写本地时同时打 updatedAt；登录后触发同步
├── views/
│   ├── auth/Login.vue · Register.vue · Reset.vue
│   ├── AiView.vue       # 从占位改为真实对话
│   ├── RoomView.vue     # 真实四人状态
│   ├── school/...       # 梦校墙相册、自定义梦校
│   └── admin/...        # 极简后台（桌面布局）
└── router/index.js      # 登录守卫、二级页
```

---

## 5. 数据模型（约 20 张表，严格对齐前端 v0.2）

> **【2026-10-23 定稿·必读】** 学习数据的同步存储已升级为「通用记录 + revision + outbox」方案，**以文末附录 A 的 A.4 / A.5 为准**；本章 5.3 的「四表各建列」仅作为与前端字段的对照保留，实际不再按四表建列。账号 / 附件 / 梦校 / 自习室 / AI / 系统各域（5.2、5.4–5.8）维持不变。

### 5.1 设计约定（非常重要）

1. **同步表与前端字段 1:1。** 前端 `subjects/sessions/tasks/mistakes` 已有什么字段，后端就有什么列，不增不减语义，降低双向转换成本。
2. **两套时间表示：**
   - 学习数据域（同步表）所有时间戳用 **BIGINT 存 epoch 毫秒**（和前端 `Date.now()` 完全一致，如 `started_at/ended_at/created_at/updated_at/done_at`）；
   - 「日期」字段用 **VARCHAR(10) 存 `YYYY-MM-DD`**（`date/due_date/source_date/next_review_at`），不做时区换算；
   - 账号 / 系统域（登录、公告等）用标准 `DATETIME(UTC)`。
3. **复合主键策略：** 同步表用自增 `id BIGINT PK`（内部）+ **`UNIQUE(user_id, client_id)`**。`client_id` 就是前端 `uid()` 生成的字符串（`sub_xxx/s_xxx/task_xxx/mk_xxx`），内置科目是固定 `math/cs408/...`，因此不能用 client_id 全局当主键（4 个人都有 `math`）。
4. **跨表引用一律存 client_id（字符串）**：`subject_client_id`、`session_client_id`，只在同一用户内引用，不引用服务端自增 id。
5. **布尔用 `INT 0/1`**（兼容 SQLite / MySQL）；**数组 / 小对象用 `JSON`**（MySQL 8 原生、SQLite 存 TEXT）。
6. **软删除：** 同步表都有 `deleted_at BIGINT NULL`，删除=打时间戳（tombstone），用于同步删除；保留 30 天后由定时任务物理清理。
7. **最后写入胜出（LWW）：** 同步表都有 `updated_at BIGINT`，同步时谁的 `updated_at` 大谁覆盖。前端需给目前没有 `updatedAt` 的 `subjects/sessions/tasks` 补上（创建时等于 createdAt，每次修改 / 删除都刷新）。

### 5.2 账号域

**users**
| 列 | 类型 | 说明 |
|---|---|---|
| id | BIGINT PK | |
| email | VARCHAR(190) UQ | 登录邮箱 |
| password_hash | VARCHAR(128) | bcrypt |
| nickname | VARCHAR(40) | 昵称 |
| avatar_key | VARCHAR(255) NULL | 七牛/本地头像 key |
| role | VARCHAR(16) | `admin` / `member`，首个账号=admin |
| status | VARCHAR(16) | `active` / `banned` / `pending_delete` / `deleted` |
| target_school | VARCHAR(32) NULL | 主梦校 code（冗余，也可只看 user_schools） |
| exam_year | VARCHAR(8) NULL | 如 2028 |
| daily_goal_min | INT | 每日目标分钟，默认 300 |
| exam_date | VARCHAR(10) NULL | 空则用系统配置 2027-12-25 |
| notify_enabled | INT | 0/1 |
| token_version | INT | 改密 / 注销 +1，使旧 token 失效 |
| last_login_at | BIGINT NULL | |
| last_seen_at | BIGINT NULL | 在线判定 |
| delete_requested_at | BIGINT NULL | 注销冷静期起点 |
| created_at | BIGINT | |
| deleted_at | BIGINT NULL | |

**invite_codes**：`id PK`、`code UQ`、`created_by→users`、`used_by NULL`、`used_at NULL`、`expires_at NULL`、`remark`、`created_at`。
**email_codes**：`id PK`、`email`、`code(6)`、`purpose(register|reset)`、`consumed INT`、`expires_at BIGINT`、`ip`、`created_at`；索引 `(email, purpose)`。
**login_logs**：`id PK`、`user_id NULL`、`email`、`result(success|bad_password|banned)`、`ip`、`ua`、`created_at BIGINT`；合规留存 ≥6 个月。

> 个人资料里的「学习设置」（nickname / daily_goal_min / exam_date / notify_enabled）直接落在 users 表，随同步接口保存；主梦校走 user_schools，不另建设置表。

### 5.3 学习数据域（同步四表）

**subjects**（对应前端 `db.subjects`）
`id PK`、`user_id`、`client_id`、`name`、`color`、`icon`、`tags JSON`、`sort_order INT`、`archived INT`、`builtin INT`、`created_at BIGINT`、`updated_at BIGINT`、`deleted_at BIGINT NULL`
唯一键 `UQ(user_id, client_id)`。

**sessions（番茄）**（对应前端 `db.sessions`）
`id PK`、`user_id`、`client_id`、`subject_client_id`、`mode(timer|stopwatch)`、`activity_type(listen|practice|review|recite|'')`、`planned_min INT`、`actual_sec INT`、`status(done)`、`started_at BIGINT`、`ended_at BIGINT`、`date VARCHAR(10)`、`note VARCHAR(200)`、`created_at BIGINT`、`updated_at BIGINT`、`deleted_at BIGINT NULL`
索引 `UQ(user_id,client_id)`、`IX(user_id,date)`、`IX(user_id,subject_client_id,started_at)`。

**tasks（任务）**（对应前端 `db.tasks`）
`id PK`、`user_id`、`client_id`、`title`、`subject_client_id`、`phase(base|intensive|pastpaper|sprint|custom)`、`accept_criteria TEXT`、`due_date VARCHAR(10)`、`done INT`、`done_at BIGINT NULL`、`created_at BIGINT`、`updated_at BIGINT`、`deleted_at BIGINT NULL`
索引 `UQ(user_id,client_id)`、`IX(user_id,due_date)`。

**mistakes（错题）**（对应前端 `db.mistakes`）
`id PK`、`user_id`、`client_id`、`subject_client_id`、`chapter`、`reason(calc|concept|review|method|careless|other)`、`tags JSON`、`content TEXT`、`image_keys JSON`（七牛/本地 key 有序数组）、`session_client_id NULL`、`source_date VARCHAR(10)`、`stage INT`、`mastered INT`、`next_review_at VARCHAR(10) NULL`、`review_history JSON`（`[{date,remembered,at}]`）、`created_at BIGINT`、`updated_at BIGINT`、`deleted_at BIGINT NULL`
索引 `UQ(user_id,client_id)`、`IX(user_id,next_review_at)`。

### 5.4 附件域

**attachments**（头像 / 错题图 / 梦校相册统一事实源，4 人版不做审核）
`id PK`、`uploader_id→users`、`biz_type(mistake|avatar|school)`、`biz_client_id VARCHAR NULL`（错题 client_id / 学校 code，先传图后回填时为空）、`object_key`（七牛 key 或本地相对路径）、`size_bytes INT`、`mime`、`width INT`、`height INT`、`sha1 VARCHAR(40) NULL`、`created_at BIGINT`
索引 `IX(biz_type,biz_client_id)`。

### 5.5 梦校域

**schools（院校库，全局公共，7 校内置 + 可加）**
`id PK`、`code UQ(tsinghua/pku/nju/fudan/sjtu/ustc/zju)`、`name`、`short`、`city`、`color`、`motto`、`logo_key NULL`、`view_key NULL`、`intro TEXT`、`score_lines JSON`（复试线 / 报录比 / 录取均分等，半自动维护）、`ref_books JSON`（专业课参考书目）、`official INT`、`sort_order INT`、`created_at BIGINT`、`updated_at BIGINT`。
> 7 校的校徽和主雪景图**仍由前端打包提供**（`src/assets/schools`，离线可用、省流量），这两列留空即可；用户上传的额外图片才走 school_albums。

**user_schools（用户梦校墙，数量不限）**
`id PK`、`user_id`、`school_code`、`status(wish 意向|backup 备选|reach 冲刺|safe 保底)`、`slogan VARCHAR(自定义标语)`、`sort_order INT`、`created_at BIGINT`、`updated_at BIGINT`
唯一键 `UQ(user_id, school_code)`。

**school_albums（单校多图相册）**
`id PK`、`school_code`、`uploader_id`、`album_type(logo|campus|gate|library|dorm|other)`、`caption`、`object_key`、`sort_order INT`、`created_at BIGINT`
索引 `IX(school_code, sort_order)`。

### 5.6 自习室域（无视频）

**rooms**：`id PK`、`code`、`name`、`intro`、`owner_id`、`created_at BIGINT`、`dissolved_at BIGINT NULL`。seed 固定一个「研时·四人自习室」。
**room_members**：`id PK`、`room_id`、`user_id`、`role(owner|member)`、`joined_at BIGINT`；`UQ(room_id,user_id)`。
**room_presence（在线 / 专注状态，心跳驱动）**
`id PK`、`room_id`、`user_id`、`status(offline|online|focusing)`、`subject_client_id NULL`、`activity_type`、`mode`、`focus_started_at BIGINT NULL`、`last_heartbeat_at BIGINT`；`UQ(room_id,user_id)`。
> 在线判定：`last_heartbeat_at > 服务器当前 - 45 秒`。focusing 时用 `focus_started_at` 显示「已专注 mm 分」。
**room_messages（留言板 / 打气）**：`id PK`、`room_id`、`user_id`、`content VARCHAR(500)`、`deleted_at BIGINT NULL`、`created_at BIGINT`；`IX(room_id,created_at)`。
**room_goals（目标墙，每人一条）**：`id PK`、`room_id`、`user_id`、`target_school`、`target_score VARCHAR`、`words VARCHAR`、`updated_at BIGINT`；`UQ(room_id,user_id)`。

### 5.7 AI 域

**ai_conversations**：`id PK`、`user_id`、`title`、`scenario(chat|mistake|essay|plan|review)`、`mistake_client_id NULL`、`created_at BIGINT`、`deleted_at BIGINT NULL`。
**ai_messages**：`id PK`、`conversation_id`、`user_id`、`role(user|assistant|system)`、`content TEXT`、`tokens INT NULL`、`created_at BIGINT`；`IX(conversation_id,created_at)`。

### 5.8 系统域

**announcements**：`id PK`、`content TEXT`、`is_active INT`、`created_by`、`created_at BIGINT`。
**official_events**：`id PK`、`title`、`event_date VARCHAR(10)`、`year VARCHAR(8)`、`sort_order INT`、`created_at BIGINT`。
**system_config**：`config_key VARCHAR PK`、`config_value TEXT`、`updated_at BIGINT`。初始键：`exam_date=2027-12-25`、`room_code`、`signup_open=0`（始终关闭开放注册）、`daily_quote`。
**audit_logs**：`id PK`、`user_id NULL`、`action VARCHAR`（如 `admin.ban_user`、`auth.login`）、`ip`、`ua`、`detail TEXT`、`created_at BIGINT`；`IX(created_at)`。

> 不建 `daily_stats` 日聚合表：4 人数据量极小，统计 / 排行榜直接对 sessions 实时聚合（SQL 带 `date` / `started_at` 索引），避免维护物化视图。

---

## 6. 数据同步协议（v0.3 最核心）

> **【2026-10-23 定稿·必读】** 同步机制已从「LWW + 时间戳游标」升级为参考项目已验证的「**revision 单调号 + 发件箱 outbox + expectedRevision 乐观并发 + 操作幂等 + 显式冲突**」，**以文末附录 A 的 A.4 为准**。本章的 LWW 游标方案仅作对照，不采用。

### 6.1 模型：本地优先 + 双向增量 + LWW

- 前端 IndexedDB 始终是**本地事实源**，无网也能正常学习；后端是**云端副本 + 多设备汇聚点**。
- 同步单位是「行」，每张表四个同步表（subjects / sessions / tasks / mistakes）独立同步。
- 每个账号在每台设备有一个**拉取游标** `last_pull_at`（epoch ms，存 localStorage，按服务端返回时间推进）；服务端只下发 `server_updated_at > last_pull_at` 的行（含 tombstone）。
- 冲突策略：**最后写入胜出（Last-Write-Wins）**，比较 `updated_at`（epoch ms）；同毫秒再比 `client_id` 字典序保证确定性。对「同一用户多设备」足够（一个人极少在两台设备同时改同一条）。
- 番茄记录（sessions）本质是**只追加、几乎不改**，冲突概率为 0；任务 / 错题的修改走 LWW。

### 6.2 前端数据层改造（必须）

1. 四个表的每条记录补 `updatedAt`（ms）；新建时 `updatedAt = createdAt`，`update/remove` 时刷新。
2. 删除从物理删除改为**软删除**：`deletedAt = Date.now()` 并刷新 `updatedAt`，记录保留在本地（Dexie 查询统一过滤 `deletedAt` 为空）。Dexie schema 不变（软删记录仍按 id 存）。
3. 新增一个同步状态表 `sync_meta`（用现有 `kv` 表即可）：存 `last_pull_at`、`last_push_at`、`pending_image_uploads`。
4. 所有写操作（store 的 add/update/remove/toggle/review）在本地落库后，标记 `dirty`（可直接用「`updatedAt > last_push_at`」推导，不必额外标记）。
5. 错题图片：`images` 本地仍是 Blob 数组（离线可看）；同步前先把未上传的 Blob 调 `/uploads/image` 换 `object_key`；同步上行的 `image_keys` 是字符串数组；下行拿到别人设备的记录时，用 `object_key` 调 `/uploads/sign` 换签名 URL，再缓存回 IndexedDB（本地可另存 `image_url_cache` 字段，不参与同步）。

### 6.3 同步接口

**`POST /api/v1/sync/pull`** — 下行
```jsonc
// 请求
{
  "tables": {
    "subjects": 1729000000000,   // 各表上次拉取游标（server_updated_at）；首次传 0
    "sessions": 0,
    "tasks": 0,
    "mistakes": 0
  }
}
// 响应 data
{
  "changes": {
    "subjects": [ { "client_id":"math", "name":"数学", ..., "updated_at":.. ,"deleted_at":null },
                  { "client_id":"sub_old", ..., "updated_at":.. ,"deleted_at":1729999999999 } ],
    "sessions": [ ... ],
    "tasks":   [ ... ],
    "mistakes":[ ... ]
  },
  "server_time": 1730000000000,
  "next_cursors": { "subjects": 1730000000000, "sessions": ..., "tasks": ..., "mistakes": ... }
}
```
- 只返回**当前登录用户**的行；每行包含完整字段（不是只 diff），便于前端直接 upsert。
- `deleted_at` 非空即墓碑，前端收到后把本地对应记录置为软删。
- 为避免单次过大，支持 `limit`（默认 500/表），若该表还有更多，`next_cursors` 不推进，前端循环拉取。

**`POST /api/v1/sync/push`** — 上行
```jsonc
// 请求
{
  "changes": {
    "subjects": [ {行完整字段, 含 client_id/updated_at/deleted_at} ],
    "sessions": [ ... ],
    "tasks":   [ ... ],
    "mistakes":[ ... ]
  }
}
// 响应 data
{
  "accepted": { "subjects": 12, "sessions": 38, "tasks": 5, "mistakes": 3 },
  "conflicts": [ { "table":"tasks","client_id":"task_xxx","server_updated_at":..., "reason":"newer_on_server" } ],
  "server_time": 1730000000000
}
```
- 服务端逐行处理：以 `(user_id, client_id)` 查库；不存在则插入；存在则比较 `updated_at`——上行的更新则覆盖，否则放进 `conflicts`（不覆盖，下次 pull 会把服务端较新版本下发）。
- **幂等**：重复 push 同一行结果一致（同 updated_at 直接视为 accepted）。网络重试不会产生重复行。
- 服务端给每行写入自己的 `server_updated_at`（不覆盖客户端 `updated_at`，另存一列用于下行游标）。

### 6.4 同步时机与弱网

- **登录后**：先 `pull` 全量（游标 0），合并进本地，再 `push` 本地存量（首次登录把这台设备的本地数据归属到账号）。
- **运行中**：App 启动、每次番茄完成、任务勾选、错题复习、每隔 2 分钟、切回前台时，执行一次 `push → pull`。
- **弱网**：动作照常写本地（不阻塞学习）；同步失败进队列，指数退避重试；联网恢复后先 push 再 pull。
- **登出**：停止同步，可选择保留本地数据（4 人共用设备时提示）。
- **不做的事**：不做字段级三方合并（LWW 整行）、不做操作日志（oplog）、不做实时推送（不 WebSocket/SSE 同步；同步走 HTTP 轮询/触发即可）。

### 6.5 边界与冲突处理

| 场景 | 处理 |
|---|---|
| 手机、电脑同时改同一条任务 | 后保存的 `updated_at` 大，覆盖；另一台下次 pull 拿到新版本。属于预期 |
| A 设备删除、B 设备同时编辑 | 删除与编辑都带 `updated_at`，LWW 决定最终状态（多数情况删除先发生） |
| 科目被归档 / 改名 | 科目是软删+归档，历史 session 的 `subject_client_id` 仍指向它，统计照常显示（按记录快照） |
| 内置科目（math 等） | 每人各有一份，互不影响；可改名换色，只改自己的副本 |
| 错题图片跨设备 | 先上传得 key，再同步；换设备按 key 换签名 URL |
| 时钟不准 | 不采信客户端「当前时间」做服务端判定，但 `updated_at` 由客户端给（用于 LWW 排序，误差可接受）；服务端另存 `server_updated_at` 作为游标 |
| 重复登录 / 清缓存 | 全量 pull 幂等重建，不会产生重复记录 |

---

## 7. 认证与账号

### 7.1 账号怎么来（4 人，不开放注册）

- **方式 A（主）：管理员在后台直接建号**——填邮箱、昵称、初始密码（或生成随机密码），成员首次登录强制改密。最简单、最可控。
- **方式 B（辅）：一次性邀请码**——管理员在后台生成码（如 `YANSHI-XXXX`），同学打开注册页，填邮箱 + 邮箱验证码 + 密码 + 邀请码，码被消费一次即失效。
- `system_config.signup_open` 恒为 0：没有有效邀请码 / 不是管理员，注册接口直接拒绝。
- 首个账号（你）由 `seed.py` 用 `.env` 里的初始邮箱 + 随机密码创建为 admin，启动日志打印一次密码，首登强制改密。

### 7.2 认证机制

- 密码 **bcrypt** 哈希（passlib/bcrypt），不存明文。
- 登录返回 **access_token（2 小时）+ refresh_token（14 天）**，均 JWT；前端存 localStorage，请求头 `Authorization: Bearer <access>`。
- access 过期 → 前端拦截器用 refresh 调 `POST /api/v1/auth/refresh` 无感换新；refresh 过期才重新登录。
- 不用 cookie，天然免疫 CSRF。
- 改密 / 注销 / 封禁：`users.token_version += 1`，JWT 里带 token_version，校验时不一致即拒绝（踢掉旧设备）。
- 登出：前端清 token；refresh 可写 Redis 黑名单——**本期无 Redis，改为在内存维护一个短命 jti 黑名单（重启后 refresh 自然过期，可接受）**。

### 7.3 邮箱验证码 / 找回

- 注册 / 找回：`POST /api/v1/auth/email-code` 发 6 位数字，10 分钟有效、一次性、存 `email_codes`；发码限流（同邮箱 60s 一次、每天 10 次）。
- QQ SMTP `smtp.qq.com:465` SSL（授权码已在你手上，写 `.env`）。
- 开发期 `.env` 设 `MAIL_CONSOLE=1` 时不真发，验证码直接打印到后端控制台（方便调试）。
- 找回密码：邮箱发一次性重置 token（30 分钟，可复用 email_codes 的 reset 类型或单独 token），重置后所有旧 token 失效。

### 7.4 安全与限流（轻量版，4 人）

- 进程内内存滑动窗口限流：登录 / 发码 / 注册 / 上传收紧（如同 IP 1 次/秒 + 突发），其余宽松；触发返回 429。
- 连续登录失败 5 次锁账号 15 分钟（计数可存内存或 DB）——保留，成本低。
- 登录日志 `login_logs`（success/bad_password/banned、IP、UA），留存 ≥6 个月。
- 全站 HTTPS（生产）、ORM 参数化、上传白名单、XSS 由 Vue 默认转义 + AI Markdown 走 DOMPurify、Nginx 安全头。

---

## 8. 自习室（在线状态，无视频）

### 8.1 房间模型

固定一个四人房间（seed），成员由管理员添加（或注册后自动加入）。不做房间列表 / 创建 / 申请 / 公开。

### 8.2 状态上报（心跳）

- 前端在「进入自习室页面」或「正在专注且 App 前台」时，每 **20 秒** `POST /api/v1/room/heartbeat`：
```jsonc
{ "status": "focusing",            // online | focusing
  "subject_client_id": "math",
  "activity_type": "practice",
  "mode": "timer",
  "focus_started_at": 1730000000000 }  // 开始本次专注的本地时刻；idle 时 status=online
```
- 服务端 upsert `room_presence` 的 `last_heartbeat_at`；超过 45 秒没心跳视为离线（查询时判定，不需要定时下线）。
- 这是「此刻状态」，不写番茄记录、与 §6 数据同步完全解耦。

### 8.3 房间拉取（轮询）

`GET /api/v1/room` 每 20~30 秒返回：
- 4 个成员（含空座位）：头像、昵称、梦校、在线状态、是否专注中、当前科目 / 类型、本次已专注分钟（`now - focus_started_at`）；
- 今日各人专注时长、今日番茄数（实时聚合 sessions）；
- 本周 / 累计排行榜、连续打卡天数；
- 留言板最新若干条、目标墙（每人目标院校 + 目标分 + 一句话）。

### 8.4 其它接口

- `GET/POST /api/v1/room/messages` 留言（content ≤500 字，可删自己的）；
- `PUT /api/v1/room/goal` 设置/更新我的目标墙；
- `GET /api/v1/room/ranking?range=today|week|all` 排行榜。

> 不做：摄像头、麦克风、屏幕共享、WebRTC、信令、打卡照片、多房间、资料区。

---

## 9. 七牛图片

### 9.1 上传链路（后端中转，Key 不出后端）

- 前端 `POST /api/v1/upload/image`（multipart/form-data）：`file` + `biz_type`（mistake/avatar/school）+ 可选 `biz_client_id`。
- 后端：登录鉴权 → 白名单（jpg/jpeg/png/webp，≤5MB）→ Pillow 读真实尺寸（≤4096）→ 头像中心裁剪 512×512 / 错题图压缩（最长边 1280，质量 82）→ **流式**上传七牛（`UploadFile` 边读边推，不整读进内存）→ 随机 key 落 `attachments`，返回 `{ object_key, url, width, height }`。
- 上传频率内存限流（≤10 张/分钟）。

### 9.2 key 与桶规划（空间 `sharearea`，私有，华南 cn-south-1）

- `avatars/{user_id}/{时间戳随机}.jpg`
- `mistakes/{user_id}/{yyyyMM}/{随机}.jpg`
- `schools/{code}/{album_type}/{随机}.jpg`
- `backups/...`（数据库备份）

### 9.3 访问

- 私有空间通过**签名 URL**访问（有效期 1 小时）；前端展示图片时调 `GET /api/v1/upload/sign?key=...` 换取临时 URL 并缓存。
- 备案通过后，在七牛绑定 `img.duzhi.xin` 并在阿里云 DNS 加 CNAME（指向七牛），签名 URL 走该域名。

### 9.4 客户端

- 用 `boto3`（S3 兼容，endpoint `https://s3.cn-south-1.qiniucs.com`）或 `qiniu` SDK 二选一；AK/SK 只写 `.env`。

### 9.5 开发期不依赖七牛

- `.env` 设 `STORAGE_DRIVER=local` 时，图片落到后端 `storage_local/`，通过 `GET /api/v1/media/{key}` 静态返回；同一套上传/签名接口，仅 driver 不同。
- 这样本地开发即使没配七牛也能跑通错题图、头像、相册；生产切 `STORAGE_DRIVER=qiniu` 即可。

---

## 10. AI 助教（火山方舟，平台 key）

- Key、模型、Base URL 只在后端 `.env`：`ARK_API_KEY`、`ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3`、`ARK_MODEL=doubao-seed-2-1-pro`。
- 接口 `POST /api/v1/ai/chat/stream`（SSE），body：`{ conversation_id?, scenario, content, mistake_client_id? }`。
- 后端组装 `system prompt`（考研助教人设，写死在 `ai_client.py`），按场景注入：
  - `mistake` 错题讲解：自动带出题干、错因、科目，按「考点定位→正确思路→易错点→举一反三」；
  - `essay` 作文批改：总分档次 / 结构 / 逐句错误 / 升级表达 / 范文；
  - `plan` 计划生成：结合剩余天数、各科时长（从 sessions 聚合）、任务；
  - `review` 复盘：带入当日时长、任务完成、错题数；
  - `chat` 通用答疑。
- 只发最近 10 轮 + 系统提示 + 场景数据，防止上下文膨胀；流式逐 token 转发给前端，支持「停止生成」。
- 会话与消息落 `ai_conversations/ai_messages`，跨设备可见；可新建、重命名、删除。
- Nginx 对 AI 路径 `proxy_buffering off`、长超时。
- 开发期 `ARK_API_KEY` 为空时走 `AI_MOCK=1`，后端返回一段固定的流式假回复，前端先把交互跑通。

---

## 11. 管理后台（极简，桌面端）

固定一个管理员（你）。后台是独立桌面布局（`/admin/*`，admin 角色可访问），不占移动端 Tab：

| 模块 | 能力 |
|---|---|
| 仪表盘 | 成员数、今日/累计番茄总时长、今日在线、错题数、图片存储用量 |
| 成员管理 | 直接建成员、重置密码、改昵称、冻结/解封（banned）、查看最后登录 |
| 邀请码 | 生成 / 查看 / 作废一次性注册码 |
| 自习室 | 查看 4 个成员、移除成员、留言删除、房间公告 |
| 梦校 | 维护院校库（半自动信息：复试线/报录比/参考书目/简介）、上传公共图 |
| 全局配置 | 考研日期、官方节点、公告、首页短句、注册开关（恒关） |
| 数据 | 手动触发数据库备份、查看备份列表、审计 / 登录日志 |

所有管理员写操作落 `audit_logs`（action 以 `admin.` 开头）。

---

## 12. API 接口清单（统一前缀 `/api/v1`）

> 下列路径省略 `/api/v1`。除 `/auth/email-code`、`/auth/register`、`/auth/login`、`/public/*`、`/health` 外均需登录。

**认证 / 账号**
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /auth/email-code | 发邮箱验证码（register/reset，限流） |
| POST | /auth/register | 注册（邮箱+验证码+密码+邀请码，需有效码） |
| POST | /auth/login | 登录（返回双 token） |
| POST | /auth/refresh | 刷新 access token |
| POST | /auth/logout | 登出 |
| GET | /auth/me | 当前用户（资料、设置、未读、房间） |
| POST | /auth/reset-password/request · /verify | 找回密码：发邮件 / 校验并重置 |
| PUT | /users/me/profile | 改昵称/目标院校/考研年份/设置 |
| PUT | /users/me/password | 改密码（验旧密码，踢旧设备） |
| POST | /users/me/avatar | 上传头像（multipart） |
| DELETE | /users/me | 注销账号（7 天冷静期）/ 撤销 |

**同步 / 图片**
| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /sync/pull | 下行增量（各表游标，含墓碑） |
| POST | /sync/push | 上行增量（LWW 合并，幂等） |
| POST | /uploads/image | 上传图片（mistake/avatar/school，流式） |
| GET | /uploads/sign | 按 key 换签名访问 URL（本地驱动返回 /media 路径） |

**自习室**
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /room | 房间状态：成员在线/专注、今日时长、排行、留言、目标墙 |
| POST | /room/heartbeat | 20s 心跳，上报在线/专注状态 |
| GET · POST | /room/messages | 留言列表 / 发留言 |
| DELETE | /room/messages/{id} | 删自己的留言（管理员可删任意） |
| PUT | /room/goal | 设置我的目标墙 |
| GET | /room/ranking?range=today\|week\|all | 排行榜 |

**梦校**
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /schools | 院校库（7 校内置 + 补充信息） |
| GET | /schools/{code} | 院校详情 + 相册 |
| GET · POST | /me/schools | 我的梦校墙列表 / 添加（不限数量） |
| PUT · DELETE | /me/schools/{code} | 改状态标签/标语/排序 · 移除 |
| POST | /schools/{code}/album | 上传相册图（biz_type=school） |
| DELETE | /schools/album/{id} | 删相册图 |

**AI**
| 方法 | 路径 | 说明 |
|---|---|---|
| GET · POST | /ai/conversations | 会话列表 / 新建 |
| DELETE | /ai/conversations/{id} | 删会话 |
| GET | /ai/conversations/{id}/messages | 历史消息 |
| POST | /ai/chat/stream | 发送消息（SSE 流式，可带 mistake_client_id） |

**公共 / 倒数日**
| 方法 | 路径 | 说明 |
|---|---|---|
| GET | /public/config | 考研日期、公告、首页短句（不鉴权） |
| GET | /public/official-events | 官方考试节点 |
| GET | /health | 健康检查（db 状态），不鉴权 |

**管理后台（admin）**
| 路径前缀 | 能力 |
|---|---|
| /admin/dashboard | 概览指标 |
| /admin/users | 建成员、列表、改资料、重置密码、冻结/解封 |
| /admin/invite-codes | 生成 / 列表 / 作废 |
| /admin/room | 成员管理、删留言、公告 |
| /admin/schools | 院校库与相册维护 |
| /admin/config | 考研日期、官方节点、公告、短句、注册开关 |
| /admin/backups | 备份列表 / 手动备份 |
| /admin/audit-logs | 审计 / 登录日志查询 |

合计约 **45 个接口**（对比开放版 105 个，大幅收敛）。

---

## 13. 统一响应、错误码、分页、安全

**成功**：`{ "code": 0, "message": "ok", "data": {...} }`
**失败**：`{ "code": 4xxxxx, "message": "可读提示", "detail": "排障信息", "data": null }`

| code | 含义 | HTTP |
|---|---|---|
| 0 | 成功 | 200 |
| 40001 | 参数校验失败 | 400 |
| 40101 | 未登录 / 缺 token | 401 |
| 40102 | access 过期（用 refresh 换新） | 401 |
| 40301 | 无权限 / 非管理员 | 403 |
| 40302 | 账号冻结 | 403 |
| 40401 | 资源不存在 | 404 |
| 40901 | 冲突（邀请码已用 / 重复加入） | 409 |
| 42901 | 触发限流 | 429 |
| 50001 | 服务器错误 | 500 |
| 50201 | 七牛 / SMTP / 火山方舟上游失败 | 502 |

- 分页：`?page=1&page_size=20`（默认 20、最大 100），返回 `{items,total,page,page_size,has_more}`。
- 时间：请求/响应里学习数据时间戳用 epoch ms，日期用 `YYYY-MM-DD`；账号类用 ISO8601。
- 安全：bcrypt、JWT、ORM 参数化、CORS 仅允许前端源、Nginx 限流、上传白名单与尺寸校验、密钥只在 `.env`、日志对密钥脱敏、XSS 转义 + AI Markdown DOMPurify、静态文件 hash 长缓存 + index no-cache + 安全响应头（X-Frame-Options / nosniff / Referrer-Policy / CSP）。

---

## 14. 定时任务（APScheduler，存 MySQL/SQLite，重启不丢）

- 每 1 分钟：`room_presence` 在线判定由查询实时完成，无需任务；但清理 5 分钟前的 focus 残留（前端异常退出）。
- 每 10 分钟：清理过期 `email_codes`、内存限流（自动）。
- 每日 00:00（北京时间）：生成当日错题复习队列（前端本地也会算，后端用于跨设备/推送红点）；更新首页短句。
- 每日 03:00：数据库备份（生产：mysqldump gzip → 七牛，本地留 3 天 / 远端 14 天）。
- 每日凌晨：清理超过 30 天的同步墓碑（tombstone）。
> 错题的艾宾浩斯复习到期计算**前端本地已实现**（离线可用）；后端这套主要给「没开 APP 的跨设备提醒」和一致性兜底，不重复制造复杂度。

---

## 15. 本地开发指南（Windows，你现在就能跑）

```powershell
# 1) 进入后端目录，建虚拟环境
cd D:\KAOYAN\yanshi\server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

# 2) 准备配置（从模板复制，按需填；默认 SQLite + 本地图片 + 邮件控制台，可零外部依赖启动）
copy .env.example .env

# 3) 初始化数据库（SQLite）+ 种子（管理员/7校/固定房间/官方节点）
alembic upgrade head
python -m scripts.seed

# 4) 启动后端（热更新）
uvicorn app.main:app --reload --port 8000
# 自动文档 http://127.0.0.1:8000/api/v1/docs（FastAPI /docs 挂在 /api/v1 下）

# 5) 前端：让 /api 代理到 8000（vite.config.js 加 proxy），另起
cd D:\KAOYAN\yanshi\web
npm run dev -- --port 27341
```

`.env` 关键开关（默认值保证不配任何外部服务也能跑）：
- `DATABASE_URL=sqlite:///./dev.db`（生产改 `mysql+pymysql://user:pass@127.0.0.1:3306/yanshi?charset=utf8mb4`）
- `STORAGE_DRIVER=local`（生产 `qiniu`）
- `MAIL_CONSOLE=1`（配好 QQ SMTP 后置 0）
- `AI_MOCK=1`（配好火山方舟 key 后置 0）

测试：`pytest`（同步 LWW/幂等/软删除、认证、房间排行必须有自动化用例）。

---

## 16. 部署（仅备案通过后执行，审核期不碰）

> 备案通过前服务器 `<SERVER_IP>` 保持关闭、DNS 全暂停。以下为通过后的步骤。

**A. Docker Compose（推荐）**：`nginx + backend + mysql` 三容器（不跑 Redis）。
1. 服务器装 Docker；clone 代码；配 `.env.prod`（MySQL 密码、JWT 密钥、QQ SMTP、七牛 AK/SK、火山方舟 key、初始管理员邮箱）。
2. `docker compose up -d mysql` → `docker compose run --rm backend alembic upgrade head` → `docker compose run --rm backend python -m scripts.seed`。
3. 前端 `npm run build`，dist 经多阶段构建打进 nginx 镜像。
4. `docker compose up -d`；Certbot 申请 `duzhi.xin` HTTPS 证书。
5. 七牛绑定 `img.duzhi.xin`、阿里云 DNS 加 CNAME；恢复 A/www 解析指向服务器。
6. 健康检查 `GET /api/v1/health`；底部挂 ICP 号 + 公安备案号；30 日内公安备案。

**B. 裸机 systemd（不装 Docker 时）**：`apt install mysql-server nginx`；建 venv 跑 uvicorn，用 `fastapi-yanshi.service` 托管（你服务器上已有这个 service 文件）；Nginx 反代 8002；其余同上。

**MySQL 参数（2核4G）**：`innodb_buffer_pool_size=1G`、`max_connections=100`、慢查询日志；端口仅 127.0.0.1。
**备份**：每日 03:00 mysqldump gzip → 七牛 `backups/`，本地 3 天 / 远端 14 天；每季度恢复演练。
**监控**：UptimeRobot 每 5 分钟探 `/health`；镜像/版本用 git SHA 而非 latest；保留回滚路径。

---

## 17. 环境变量清单（`.env.example`）

```ini
# 基础
APP_ENV=dev                 # dev | prod
SECRET_KEY=change-me-to-a-long-random-string
DATABASE_URL=sqlite:///./dev.db
CORS_ORIGINS=http://localhost:27341,http://127.0.0.1:27341

# 初始管理员（seed 用）
ADMIN_EMAIL=admin@example.com

# 邮件（QQ SMTP）；MAIL_CONSOLE=1 时验证码打印到控制台
MAIL_CONSOLE=1
SMTP_HOST=smtp.qq.com
SMTP_PORT=465
SMTP_USER=admin@example.com
SMTP_PASSWORD=          # 填 QQ 邮箱 16 位授权码（只放服务器，不进 git）

# 图片存储：dev 用 local，prod 用 qiniu
STORAGE_DRIVER=local      # local | qiniu
QINIU_AK=
QINIU_SK=
QINIU_BUCKET=sharearea
QINIU_S3_ENDPOINT=https://s3.cn-south-1.qiniucs.com
QINIU_DOMAIN=             # 备案后填 img.duzhi.xin

# AI 火山方舟；AI_MOCK=1 时返回假流式
AI_MOCK=1
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
ARK_API_KEY=
ARK_MODEL=doubao-seed-2-1-pro

# 考研
EXAM_DATE=2027-12-25
```

> 所有密钥（SMTP 授权码、七牛 AK/SK、火山方舟 key、MySQL 密码）只写服务器 `.env`、加入 `.gitignore`，绝不进代码库、不截图外传。

---

## 18. 分期与开发任务（v0.3 落地顺序）

每一步都「可单独验证、可单独跑」，避免一口气写三个月没法测。

| 阶段 | 内容 | 验收 |
|---|---|---|
| **v0.3-a 骨架与账号** | 建 FastAPI 工程、config/db/异常/统一响应、Alembic、SQLite 跑通；注册（邀请码）/登录/刷新/me、邮箱验证码（控制台）、bcrypt/JWT、seed 管理员与 7 校 | 能注册登录、/docs 可看、受保护接口要 token、pytest 认证通过 |
| **v0.3-b 数据同步（核心）** | 四表模型 + push/pull + LWW + 墓碑 + 幂等；前端 Dexie 加 updatedAt/软删、同步引擎、登录后全量+增量；本地图片存储驱动错题图 | 两台浏览器/两个设备登录同一账号，番茄/任务/错题双向同步；删改能同步；离线可学、联网补齐；重复 push 不重复 |
| **v0.3-c 自习室** | 房间/成员/presence/心跳/房间拉取/排行/留言/目标墙；前端 RoomView 接真实数据 | 4 人在线状态、当前科目、今日时长、排行、留言、目标墙正常；无摄像头、无伪造数据 |
| **v0.3-d 梦校与头像** | 头像上传裁剪；梦校不限数量、状态标签、自定义标语、多图相册、半自动院校信息；七牛 driver（配好 key 后） | 头像可换；梦校可增删改、多图滑动；错题图/头像/相册在七牛可签名访问 |
| **v0.3-e AI 助教** | 火山方舟 SSE、会话/历史、5 个场景、前端 AI Tab 真实对话、停止生成 | 流式打字机、错题一键问、历史跨设备可见、key 不出现在前端/日志 |
| **v0.3-f 管理后台** | 成员/邀请码/房间/院校/配置/备份/日志（桌面端） | 建号、改考研日期、发公告、备份可用；管理员操作有审计 |
| **v0.3-g 收尾与上线准备** | 邮件真发、pytest 补齐、CSP/限流/安全头、用户协议/隐私政策、部署脚本、备份演练；**等备案通过再上线** | 主流程端到端通过；生产部署文档可照做；备案号/公安备案就位 |

顺延（不在 v0.3）：笔记模块、真题模考、背诵卡片、分数追踪、资料馆、励志馆投稿、轻社区。

---

## 19. 风险与技术壁垒（说清楚哪些能做、哪些有限制）

| 项 | 结论 |
|---|---|
| 多设备同步冲突 | LWW 整行覆盖，4 人单人多设备够用；不做 OT/CRDT（过度设计） |
| 离线刷时长 | 4 人版不防刷（本地权威）；若日后开放再改服务端计时（v2.4 那套备用） |
| 网页锁屏到点提醒 | 不可靠（iOS Safari 后台节流，iOS16.4+ 需 PWA 加主屏幕）；这是浏览器限制，靠本地计时与提示音缓解，不承诺锁屏准时 |
| 系统级锁机 | 网页做不到，后期要就上 Capacitor 套壳 / 原生 App |
| 院校复试线/报录比 | 无官方免费 API，半自动（管理员维护 + 你上传/AI 辅助），不做自动爬虫 |
| 微信内置浏览器 | 部分后台/通知能力受限，主流程保证可用；建议「添加到主屏幕」 |
| 火山方舟费用 | 平台 key 4 人共用，量小；在控制台设费用预警 |
| 本地 SQLite 与生产 MySQL 差异 | 只用通用类型、不写方言 SQL；上线前在测试库跑一遍 Alembic 迁移 |
| 七牛私有空间图片防盗链 | 签名 URL 1 小时；备案后 img.duzhi.xin CDN；开发期本地驱动免依赖 |
| 个人备案合规 | 不开放注册、不公开、不收费、无视频，定位「学习工具/计时器」；日志留存、协议、备案号齐备 |

---

## 20. 待确认（不阻塞，按默认推进即可）

1. 3 个研友的邮箱与昵称（v0.3-a 建号时需要）。
2. 火山方舟 key 是否沿用 `Fudan450` 里已有的那一个（默认沿用，填到服务器 `.env`）。
3. 生产部署选 Docker Compose 还是裸机 systemd（默认 Docker，装不了再裸机）。
4. 4 人邀请码方式：直接建号（默认）还是发码自助注册（两者都做）。

> 以上不影响先开工；本文档确认后，从 **v0.3-a 骨架与账号** 开始，先在本地用 SQLite 把账号 + 同步跑通。

---

# 附录 A · 参考实现 `study-app-source` 复用与最终技术裁决（2026-10-23，以此为准）

> 你提供的参考源码已解压到 `D:\KAOYAN\reference-study-app`（**只读参考，不改动**）。它含两套后端：
> - `server/`（Node.js + Express）：**本地优先**，含一套已经实现并带测试的「发件箱同步」；
> - `backend/`（**Python + FastAPI**）：v24 开放平台，服务端权威，含成熟的账号 / 图片 / AI / 备份 / 部署。
> 我们的技术栈与 `backend/` 完全一致（FastAPI + SQLAlchemy2 + Alembic + Pydantic v2），故**基础设施从 `backend/` 移植，同步协议从 `server/` 移植并用 Python 重写**；其前端（`src/`、`src/v24/`）不采用，继续用我们自己的 `yanshi-web`。

## A.1 直接移植（在 yanshi-server 里按本项目裁剪改写）

| 参考文件 | 用途 | 本项目处理 |
|---|---|---|
| `backend/app/errors.py` | 统一信封 `ok()`/`ApiError`/分页 `page()` | 直接用 |
| `backend/app/database.py` | SQLite WAL + FK、MySQL READ COMMITTED、会话工厂 | 直接用（去掉统计失效钩子） |
| `backend/app/config.py` | pydantic-settings、SQLite 默认、生产校验 | 裁剪：删 RTC/BYOK/远端备份，注册默认关 |
| `backend/app/deps.py` | JWT 双 token、refresh family、`token_version`、当前用户/管理员 | 直接用，删 VIP `feature` 权限 |
| `backend/app/services/transient.py` | **无 Redis 自动降级内存**：限流/验证码/锁定；`deliver()` 邮件 SMTP 或本地文件 sink | 直接用（这落实了"不装 Redis"） |
| `backend/app/services/image_storage.py` | 七牛/本地双驱动、上传 token、S3 与 native 签名 URL、路径穿越防护 | 直接用，key 前缀加 `school/` |
| `backend/app/routers/auth.py` | 注册/登录/刷新/找回/改密、bcrypt、邀请码、限流锁定 | 裁剪：删图形验证码、删 VIP；注册改为"必须有效邀请码"；账号用 email+昵称 |
| `backend/app/routers/attachments.py` + `services/attachments.py` | 图片流式上传、Pillow 校验、白名单 | 移植并简化（无审核、无帖子图） |
| `backend/app/services/ai.py` + `routers/ai.py` | 平台 AI 的 SSE 流式、场景、用量 | 只保留平台 key（火山方舟），**删 BYOK/加密盒** |
| `backend/app/seed.py` | 系统配置、20 条原创励志短句 | 直接用短句；注册开关改关；补 7 校 / 固定房间 |
| `backend/app/services/backups.py` | mysqldump 备份骨架 | 简化（本地/七牛，去掉 rclone） |
| `backend/app/main.py` | 应用工厂、lifespan、Alembic head 强校验、限流/安全头/health | 移植，移除 video/social 等路由 |
| `server/repositories/learning.mjs` + `server/routes/learning.mjs` | **本地优先同步协议（本附录 A.4）** | **用 Python 重写为 `services/sync_engine.py` + `routers/sync.py`** |
| `src/infrastructure/learningSync.ts`、`localDatabase.ts` | 前端发件箱 / 同步循环 / 冲突面板 | 参照实现前端 `src/sync`（见 A.4） |
| `backend/tests/*`、`tests/conflict.test.ts`、`sync.test.ts` | 同步幂等/冲突、认证、上传的测试范式 | 用 pytest 复刻关键用例 |

## A.2 明确不移植（4 人版砍掉）

`social/interactions/follow/people`（广场/关注/点赞）、`video/roomVideo`（摄像头/WebRTC）、`teams`（多团队）、`resources`（网盘/资料墙）、`quotes 投稿`、`quotas`（网盘/AI 配额）、`moderation / sensitive_words / reports`（内容审核举报）、`ai_providers / secretBox / userAI`（BYOK 自带密钥）、`feature_grants / VIP`、**图形验证码**、`onboarding/lifecycle` 的复杂注销延长、`daily_statistics` 日聚合表（4 人实时聚合）、多房间/公开房间/容量审批、题库课表/OCR/PDF/Excel 导入（本期不做）。

## A.3 工程落地方式

- **新建干净工程** `D:\KAOYAN\yanshi\server`，**不整体复制**参考 backend（它绑了大量我们不要的路由/表/视频/社交，直接裁剪会残留耦合）。
- 按 A.1 **逐文件移植、随手裁剪**，依赖以 `backend/requirements.txt` 为准（fastapi、sqlalchemy、alembic、pydantic、pydantic-settings、bcrypt、PyJWT、httpx、boto3、pillow、APScheduler、PyMySQL、python-multipart；`redis` 列为**可选**，未配置时用内存，生产也可不装）。
- 参考源码留在 `D:\KAOYAN\reference-study-app` 只读，移植时对照，不把它当运行工程。

## A.4 同步协议定稿（取代第 6 章 LWW 游标）

采用参考项目验证过的**发件箱 + 修订号 + 乐观并发**，比 LWW 更安全（冲突可见、不会静默覆盖），且前端加字段无需后端迁移。

**后端只加 2 张表（学习数据不再按科目/番茄/任务/错题分表建列）：**
- `learning_records`：`user_id`、`id`（前端 client_id，如 `s_xxx/task_xxx/mk_xxx/math`；同用户内唯一）、`body`(JSON，整条记录)、`revision`(整型，每次改 +1)、`deleted`(0/1)、`updated_at`；主键 `(user_id,id)`。
- `learning_operations`：`user_id`、`operation_id`、`signature`(整条命令 SHA256)、`result`(JSON)、`created_at`；主键 `(user_id, operation_id)`，用于幂等重放。

**记录 `type`：** `subject / session / task / mistake / userSchool`，`body` 字段与前端 v0.2 完全一致（时间戳 epoch ms、日期 `YYYY-MM-DD`）；后端只做基础校验（type 合法、id 一致、禁止夹带 `user_id/token` 等保留字段、同一 id 不可改 type），不逐字段强约束（便于前端演进）。

**两个接口：**
- `GET /api/v1/sync/records`：返回该用户全部记录 `{id, record(删除为 null), revision}`。**先做全量**（4 人 ≤20MB 足够）；预留 `?since_revision=` 增量参数，后续数据变大再启用。
- `POST /api/v1/sync/commands`：body 为一个操作 `{operationId, changes:[{id, expectedRevision, record|null}]}`（record=null 表示删除）。
  - 逐条比对服务端当前 `revision` 与 `expectedRevision`，不符即返回 `409 RECORD_CONFLICT`（带服务端版本）；
  - 通过则 `revision+1` upsert / 软删；整批在一个事务里，SQLite 用 `BEGIN IMMEDIATE` 串行；
  - 用 `operationId + signature` 幂等：重复提交相同命令直接返回缓存结果，同 id 不同内容报 `OPERATION_REUSED`；
  - 账号限额：记录 ≤20000 条、body 总量 ≤20MB（4 人远超够用）。

**前端（yanshi-web）改造：**
- 保留现有 4 张业务表（`subjects/sessions/tasks/mistakes`，统计/查询照旧）；Dexie 升级新增 `outbox(operationId, created)`、`syncMeta(id)`（记录每条 id 的 revision、`$lastSync`、`$queueClock`）。
- 所有写操作在事务内调用 `enqueue(id, record)` 自动进发件箱（同事务的多次写打包成一个 operation，≤200 条/批）；删除发 `record=null`。
- 同步循环用 `navigator.locks` 串行：先校验 `/auth/me` 身份 → 依次发 outbox 命令（带 expectedRevision）→ 成功更新 revision、清 outbox；再全量拉 records 合并（跳过本地待发 dirty 的 id），删除墓碑。
- **冲突**：某条 expectedRevision 不符时，前端给"保留本机 / 用云端"二选一（并按 id 引用做级联检测），解决后重发；单人多设备极少冲突。
- 错题图片：先调 `/uploads/image` 换 key，`body.image_keys` 存 key 数组（本地 IndexedDB 仍存 Blob 离线查看）。

**自习室排行的数据来源：** 服务端直接从 `learning_records.body` 实时聚合 `type=session` 的时长（SQLite/MySQL 均支持 JSON 函数；按用户、日期分组），避免让前端自报、保证真实；在线/正在学仍走 `room_presence` 心跳。

## A.5 最终表清单（约 19 张）

| 域 | 表 |
|---|---|
| 学习同步 | **learning_records、learning_operations**（科目/番茄/任务/错题/用户梦校关系全在 records） |
| 账号 | users、refresh_tokens、invite_codes、login_logs |
| 附件 | attachments |
| 院校 | schools（7 校公共信息）、school_albums（多图相册） |
| 自习室 | rooms、room_members、room_presence、room_messages、room_goals |
| AI | ai_conversations、ai_messages |
| 系统 | system_config、announcements、official_events、audit_logs |

users 合并放昵称/头像 key/目标院校/每日目标/考试日期/通知开关（不再单建 profile/timer_settings）。邮箱验证码与登录锁定用 transient（内存/Redis），不单独建 email_codes 表。

## A.6 与正文的关系

附录 A 与正文第 5.3、第 6 章不一致处，**一律以附录 A 为准**；其余章节（认证、自习室、图片、AI、后台、部署、合规、分期）继续有效。v0.3 开发顺序不变：**a 骨架+账号 → b 同步（按 A.4）→ c 自习室 → d 梦校+头像 → e AI → f 后台 → g 收尾上线**。

