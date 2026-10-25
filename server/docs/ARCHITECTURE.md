# 研时系统架构（v4.0 · 2026-10-25 基线）

> 本文是当前生效的后端架构基线，取代 2026-10-23 的「4 人私密版」v3.0。
> 产品与验收依据：《研时-开发文档-完整版-2026-10-25》，原文已归档到 `docs/design-2026-10-25/`。
> 旧文保留在 [ARCHITECTURE-v3-4person-HISTORICAL.md](ARCHITECTURE-v3-4person-HISTORICAL.md)，仅作历史参考。

## 0. 定位与范围

研时是面向考研学生、**本地优先**的学习工具：番茄专注、任务、艾宾浩斯错题、多房间自习室、资料库、研友动态、励志区、梦校墙、AI 助教与后台管理。一期验收以 PRD §6 的 47 个功能点为准。

技术栈：Vue 3 + Vite + Pinia + Dexie（前端）；FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2（后端）；SQLite（开发）/ MySQL 8（生产）；图片本地或七牛 Kodo；AI 走 OpenAI 兼容适配层（VIP BYOK + 可选服务端兜底 Key）。

## 1. 账号与会话（F-01/F-02/F-30~F-33）

- 一期开放**邮箱验证码登录**：验证码 6 位、**5 分钟有效、最多输错 5 次**；默认仅允许 QQ 邮箱域名，可通过 `AUTH_EMAIL_DOMAINS` 配置（留空=不限制）。
- 密码登录保留为后台/开发用途；注册开放，邀请码只用于 VIP 开通。
- **access token 常驻前端内存**（Pinia），不写 localStorage；**refresh token 仅存 httpOnly + SameSite=Lax Cookie**（生产加 Secure），路径限定 `/api/v1/auth`。
- 刷新时旋转 refresh token 并吊销旧凭证；退出登录吊销并清除 Cookie；改密/重置密码使 `token_version + 1` 并吊销全部 refresh。
- 微信 / QQ / 手机号登录代码保留，由 `AUTH_CHANNELS` 开关控制；未启用渠道返回 403。
- 前端启动先调用 `/auth/refresh` 恢复会话，再加载该账号本地数据；离线时允许用本地缓存资料进入，联网后自动续期。

## 2. 本地优先与账号隔离（F-45）

- 每个账号使用**独立 IndexedDB**（`yanshi_db_u<userId>`），游客使用 `yanshi_db`；首次登录把游客库业务数据整体迁移进账号库，登出不删除账号库中的未同步数据。
- 学习域同步契约：`learning_records` + `learning_operations`，`expectedRevision` 乐观并发、`operationId` 幂等、软删墓碑、账号配额。
- 同步顺序：账号切换 → 校验/刷新会话 → push 学习数据与社区离线队列 → pull 合并；冲突保持「保留本机 / 采用云端」二选一。
- 离线能力：番茄、任务、错题、资料收藏、动态草稿均可离线写入，联网后自动上传；评论、房间留言、心跳等在线动作不排队。
- 图片：离线拍照先保存 Blob；联网后先补传附件拿到 key，再更新错题记录并同步（目标契约，见 04-SYNC）。
- 番茄记录进入服务端时由服务端重算时长：真实时长封顶 **180 分钟**，超时/暂停超时记为 `quit`。

## 3. 番茄规则（F-09/F-11/F-13）

- 倒计时与正向计时并存；倒计时到点自动 `done`。
- 单颗专注 **180 分钟上限**：达到即自动 `quit(timeout)`，时长封顶 180 分钟，不计完成颗数。
- **单次暂停上限 30 分钟**：达到即 `quit(pause_timeout)`，暂停时间从总时长扣除。
- 主动放弃记为 `quit(abandoned)`，**保留实际专注时长**，不丢弃记录。
- 统计：时长聚合包含 `done + quit`；完成颗数、连续天数只统计 `done`。
- 页面挂起/息屏恢复时立即校正超时状态；服务端对同步上来的 session 再次校验并归一化。

## 4. 权限、审批与隐私（F-06/F-07/F-22/F-24）

- VIP：`vip_until`（空=未开通，可设永久）、邀请码核销、后台开通/续期/撤销并通知。
- 功能申请：`feature_request` 状态 `pending/approved/rejected/revoked`；审批通过同事务写 `user_feature_grant`，鉴权优先读 VIP 或有效 grant；撤销后立即失效。
- 受限能力通过统一鉴权函数判断，禁止只靠前端置灰：资料完整链接、资料发布、AI BYOK 等。
- 隐私模式：用户级 `privacy_mode` 持久化；开启后房间成员列表匿名占位（隐藏昵称/头像/状态/时长），**排行榜排除**，在线人数仍计入。

## 5. 自习室（F-20/F-21/F-23/F-25）

- 多房间：公开 / 私密；6 位房间码；房主可改名、改简介、换码、踢人、解散。
- 私密房间凭码免审加入；陌生人可提交加入申请，房主审批（目标契约）。
- 心跳 30 秒/次，连续 90 秒无心跳判离线；成员展示虚拟形象、状态、今日时长（隐私模式除外）。
- 留言板仅在线发布，不入同步队列；排行榜按当前房间成员当日专注时长排序，并排除隐私用户。

## 6. 内容与 AI（F-27~F-29/F-34~F-42）

- 资料库：仅 VIP 发布；非 VIP 后端脱敏（路径中间 6 位 + 提取码）；点赞在线；收藏支持离线最终状态幂等同步。
- 动态：支持离线草稿、`client_id` 幂等上传；二级评论；管理员删除需填原因并站内信通知作者。
- 励志区：所有用户可投稿，管理员审核通过后轮播，驳回填原因并通知。
- AI：VIP 自填 Key（AES-256-GCM）或服务端兜底 Key；SSE 流式；模型列表实时拉取（24h 缓存，失败可手填）；历史按条数截断；记录 token 用量与延迟。
- 站内消息 + 邮件双通道；邮件应在业务提交后异步发送，失败记录并可重试（目标契约）。

## 7. 数据模型映射（当前实现）

| 域 | 主要表 |
|---|---|
| 账号 | `users`、`user_auth`、`refresh_tokens`、`login_logs`、`audit_logs` |
| 学习同步 | `learning_records`、`learning_operations` |
| 自习室 | `rooms`、`room_members`、`room_presence`、`room_messages`、`room_goals` |
| 资料 | `resources`、`resource_likes`、`resource_favorites` |
| 社区 | `posts`、`comments`、`inspirations` |
| 消息/审批 | `messages`、`feature_requests`、`invites`（目标新增 `user_feature_grants`） |
| AI | `ai_conversations`、`ai_messages`、`user_ai_keys` |
| 存储 | `attachments`、`schools`、`configs`、`announcements` |

表名与 03-DB 不完全一致时，以业务语义和迁移脚本为准，不为凑表数重建数据。

## 8. 工程与验收

- 分支：`main` 稳定、`dev` 日常开发；功能分支 → PR → 检查通过后合并。
- CI：后端 `alembic upgrade head` + `pytest`；前端 `npm ci` + `npm run build`。
- 验收证据：47 功能点逐项记录代码位置、接口、测试与人工验收结果；已知差距单列，不以「有页面」替代验收。
- 部署：`server/deploy/`（systemd + Nginx + HTTPS + 备份）。

## 9. 基线变更记录

| 日期 | 变更 |
|---|---|
| 2026-10-23 | v3.0 四人私密版（已归档） |
| 2026-10-25 | v4.0：多房间、VIP、审批授权、隐私模式、离线发帖/收藏、AI 流式、Cookie 会话、账号分库 |
