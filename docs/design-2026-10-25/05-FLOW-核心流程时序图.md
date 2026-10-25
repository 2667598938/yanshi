# 05 · 核心流程时序图

> 所有跨端流程都在这里。写代码前先对着图确认一遍，能省掉一半返工。

---

## 1. 邮箱验证码登录 + JWT 无感续期

```mermaid
sequenceDiagram
    autonumber
    participant U as 用户
    participant W as 前端
    participant A as API
    participant S as SMTP

    U->>W: 输入 QQ 邮箱，点击获取验证码
    W->>A: POST /auth/code {email, scene}
    A->>A: 邮箱格式校验（QQ 正则）
    A->>A: 限流校验（邮箱 5min/3次，IP 1h/20次）
    A->>A: 生成 6 位码 → SHA256 落库（5min 有效）
    A-->>W: 200 {sent:true, cooldown:60}
    A->>S: 异步发送邮件
    Note over A,S: SMTP_ENABLED=false 时降级打印日志

    U->>W: 输入验证码，登录
    W->>A: POST /auth/login {email, code}
    A->>A: 校验 hash / 过期 / fail_count<5
    alt 新邮箱
        A->>A: 创建 user（nickname=研友xxxx）
    end
    A-->>W: {access_token(30min), user}
    Note over A,W: refresh_token 通过 httpOnly Cookie 下发

    rect rgb(240,248,255)
    Note over W,A: 无感续期（30 分钟后首次请求）
    W->>A: GET /xxx 带过期 token
    A-->>W: 401 {code:TOKEN_EXPIRED}
    W->>W: 挂起请求队列
    W->>A: POST /auth/refresh（Cookie 自动携带）
    A-->>W: 新 access_token
    W->>A: 重放原请求
    A-->>W: 200 正常数据
    end
```

**要点**
- 刷新期间并发请求必须**排队**，不能直接丢弃或并发触发多个 refresh
- refresh 失败（超过 7 天）→ 清本地态 → 跳登录页
- 单设备的多次登录不互踢（一期允许多端）

---

## 2. 番茄生命周期（含暂停 / 超时 / 休息）

```mermaid
stateDiagram-v2
    [*] --> Idle: 待开始
    Idle --> Focusing: 点击开始（写 start_at=serverNow）
    Focusing --> Paused: 暂停
    Paused --> Focusing: 继续（累加 pause_total）
    Paused --> Ended: 单次暂停 >30min
    Focusing --> Break: 到达计划时长 → done
    Focusing --> Ended: 主动放弃 → quit(manual_quit)
    Focusing --> Ended: 有效时长 ≥180min → quit(timeout)
    Break --> Idle: 休息结束，**必须手动点开始**
    Ended --> Idle: 记录已落盘
```

```mermaid
sequenceDiagram
    autonumber
    participant U as 用户
    participant T as Timer Worker
    participant D as Dexie
    participant A as API

    U->>T: 点击开始
    T->>T: start_at = serverNow()
    T->>D: 写入 tomato{uuid, planned, start_at, status:running, _dirty:1}
    loop 每 1s
        T->>T: elapsed = serverNow() - start_at - pause_total
        T->>T: elapsed >= planned ? 提示完成
        T->>T: elapsed >= 180min ? 触发 timeout
    end
    Note over T: 页面隐藏时 tick 被节流 → 重新可见或重载时补算

    alt 正常完成
        T->>D: status=done, actual=round(elapsed)
        T->>T: 进入休息倒计时
    else 超时
        T->>D: status=quit, end_reason=timeout, actual=180
    else 主动放弃
        T->>D: status=quit, end_reason=manual_quit, actual=elapsed
    end
    D->>D: outbox.add(op) → 等待 SyncEngine

    Note over D,A: 联网时
    D->>A: POST /tomato/end {uuid, start_at, end_at, pause_total, ...}
    A->>A: **后端重算 actual = min(end-start-pause, 180)**
    A-->>D: {ok, rev}
```

**三处必须一致**：前端 tick 判定 / 页面唤醒补算 / 后端兜底重算，用同一个常量 `MAX_TOMATO_MINUTES=180`。

**统计口径**
| 指标 | 口径 |
|---|---|
| 今日专注时长 | `sum(actual_minutes)`，含超时封顶的 180 |
| 今日完成番茄数 | `count(status=done)`，**不含** quit |
| 归属日期 | 按 `start_at` 转为**用户本地时区**后的日期 |

---

## 3. 功能申请 → 审批 → 双通道通知

```mermaid
sequenceDiagram
    autonumber
    participant U as 普通用户
    participant A as API
    participant AD as 管理员后台
    participant DB as DB
    participant M as SMTP

    U->>A: POST /apply {item_key, reason}
    A->>DB: insert apply_record(status=pending)
    A-->>U: 200 ok
    Note over U: pending 状态可撤回 DELETE /apply/{id}

    AD->>A: GET /admin/apply?status=pending
    A-->>AD: 列表（申请人/项/时间/理由）

    alt 通过
        AD->>A: POST /admin/apply/{id}/approve
        A->>DB: 乐观锁 UPDATE ... WHERE status='pending'
        alt 影响行数=0
            A-->>AD: 409 已被处理
        end
        A->>DB: **同一事务** insert message(type=apply_result)
        A->>DB: **同一事务** upsert user_feature_grant{user_id, item_key, source_apply_id}
        A->>DB: **同一事务** insert admin_operation_log(apply_approve)
        A-->>AD: 200
        A->>M: 【异步】发送通过邮件
    else 驳回（必填原因）
        AD->>A: POST /admin/apply/{id}/reject {reason}
        A->>DB: 同上 + message(content 含原因)
        A->>M: 【异步】发送驳回邮件（含原因）
    end

    U->>A: GET /message/unread-count（60s 轮询 / 打开铃铛）
    A-->>U: {count:1}
    U->>A: GET /message/list
    A-->>U: 消息列表
```

**幂等保障**：`message` 表 `(user_id, biz_type='apply', biz_id)` 唯一索引 → 重复点击审批不会重复通知。
**邮件失败**：写 `email_log(status=fail)`，后台可手动重发，不影响站内消息与主流程。

**⚠️ 权限落地（原稿写的是「`user.item_grant` 生效（或 vip 权限位）」，但 `user` 表没有这个字段，也没有授权表 —— 等于审批只能通知、不能授权）**
- 授权写独立表 `user_feature_grant`（`03-DB` §3.1），`apply_record` 只管流程状态，**不代表用户拥有该权限**
- 鉴权统一走 `is_vip() or grant_exists(item_key)`，**禁止**读 `apply_record.status='approved'` 判权限（否则撤销/到期无法生效）
- 撤销（`revoked_at`）与到期（`expire_at`）都只改授权表，不回写申请记录；`revoked` 申请状态只表示流程被终结

---

## 4. 同步流程（正常 + 冲突）

```mermaid
sequenceDiagram
    autonumber
    participant T as 触发源<br/>(online/visible/手动)
    participant E as SyncEngine
    participant D as Dexie
    participant A as API

    T->>E: requestSync()
    E->>E: 全局互斥锁（已在同步则忽略）
    E->>A: GET /sync/time → 校正 clock_offset

    rect rgb(245,255,245)
    Note over E,A: Phase 1 · Push
    E->>D: 取 outbox 前 50 条（FIFO）
    E->>A: POST /sync/push {ops:[...]}
    A-->>E: results:[{op_id, ok/conflict, rev, server?}]
    E->>D: ok → 出队 + 更新 _rev
    end

    alt 存在 conflict
        E->>E: **暂停队列**，弹出冲突对比框
        E-->>U: 用户选择
        U->>E: 保留本地 → 以 server.rev 为 base 重推
        U->>E: 用云端 → 本地覆盖并清该 uuid 队列
    end

    rect rgb(245,250,255)
    Note over E,A: Phase 2 · Pull
    E->>D: 读 meta.cursor
    E->>A: GET /sync/pull?tables=...&cursor=...
    A-->>E: {changes, next_cursor, has_more, server_time}
    loop 直到 has_more=false
        E->>D: 写入 mirror（含 sync_deleted 墓碑）
    end
    E->>D: 保存 next_cursor / last_sync_at
    end

    E->>E: 解锁，UI 状态 → synced
```

---

## 5. 自习室进入 / 心跳 / 离线判定

```mermaid
sequenceDiagram
    autonumber
    participant U as 用户A
    participant W as 前端
    participant A as API
    participant J as Scheduler
    participant B as 用户B端

    U->>W: 进入打卡自习室
    W->>A: POST /room/{id}/join
    A->>A: 公开房间直接入；私密→写 join_apply，建房主待审
    A-->>W: {member_list, joined}

    loop 每 30s
        W->>A: POST /room/{id}/heartbeat
        A->>A: last_heartbeat_at = now
    end

    par 巡检
        J->>A: 每 30s 扫描 room_member
        A->>A: now - last_heartbeat_at > 90s → online=0
    end

    Note over W: 页面隐藏 → 暂停心跳；关闭 → beforeunload 发最后一次离线标记
    W->>A: POST /room/{id}/leave（best effort）

    B->>A: GET /room/{id}/members
    A->>A: **序列化统一过滤 privacy_mode**
    A-->>B: [{nickname:'隐身学习中', avatar:default, ...}]
```

**番茄独立性**：心跳离线不改变任何番茄记录的状态。番茄结束由自身完成条件触发，即使此刻判定为"离线"也照常记录。

**在线人数口径**：`count(online=1)`，隐私用户计入人数但匿名展示。

---

## 6. 图片上传（头像 / 错题配图）

```mermaid
sequenceDiagram
    autonumber
    participant W as 前端
    participant A as 后端
    participant Q as 七牛
    W->>W: 本地校验 类型+大小(≤5MB)
    W->>A: POST /upload/token {scene: avatar|mistake}
    A->>A: 校验登录态 + 频率限制（10次/分钟）
    A-->>W: {token, key, expires:600}
    W->>Q: 直传 FormData（token + file）
    Q-->>W: {hash, key}
    W->>A: POST /upload/callback {key, scene}
    A->>A: 校验 key 归属 + magic bytes 二次确认
    A-->>W: {url: https://img.duzhi.xin/<key>}
    Note over A,Q: OSS_ENABLED=false 时走本地临时目录 mock
```

---

## 7. AI Key 配置与调用（方案 B · 用户自填）

```mermaid
sequenceDiagram
    autonumber
    participant U as VIP用户
    participant W as 前端
    participant A as 后端
    participant DB as DB
    participant L as 第三方大模型

    Note over U,W: 配置阶段
    U->>W: 选服务商(DeepSeek/Kimi/GLM/硅基/OpenAI/自定义) + 粘贴 Key
    W->>A: PUT /ai/key {provider, api_base, key}
    A->>A: 校验 VIP（非 VIP 直接 403）
    A->>A: AES-256-GCM 加密（nonce 随机）
    A->>DB: upsert user_ai_key{key_cipher, key_mask:'sk-...abcd'}
    A-->>W: 200 {masked:'sk-...abcd', created_at}  ← **绝不回传明文**
    W->>W: 销毁内存中的 Key（不落 localStorage/Dexie）

    Note over U,L: 拉取可用模型（实时，避免模型名过期）
    W->>A: GET /ai/models
    A->>L: GET {base_url}/models（带用户 Key）
    L-->>A: [model_id, ...]
    A->>DB: 写 models_cache（缓存 24h）
    A-->>W: {models:[...]}    ← 前端二级下拉
    U->>W: 选择模型 → PUT /ai/key/model {model}
    Note over A,L: 拉取失败 → 降级为「手动填写模型名」，不阻断使用

    Note over U,W: 查看时
    U->>W: 打开 AI 设置页
    W->>A: GET /ai/key
    A-->>W: {masked, model, last_used_at}   ← 只有掩码

    Note over U,L: 调用阶段
    U->>W: 提问
    W->>A: POST /ai/chat {message, session_id}
    A->>A: 限流校验（10次/分，200次/天）
    A->>DB: 取 key_cipher → 解密（仅内存）
    A->>DB: 取最近 N 条历史作为上下文（超出按条数截断）
    A->>L: 服务端代发（stream:true, 超时 60s）
    L-->>A: SSE 数据流
    A-->>W: StreamingResponse **逐字流式返回**
    A->>DB: 流结束后落 ai_messages（user/assistant 各一条 + token 用量）
    A->>A: 用完立即从内存清除明文
```

### 7.1 拉取模型：错误分类与降级

`GET/POST /ai/models` 由后端代理，前端**永远不直接请求服务商**。上游结果必须翻译成五类，前端据此决定"禁下拉 / 开手填 / 保留上次"：

| 上游 | 服务端判定 | 返回前端 | 前端动作 |
|---|---|---|---|
| 401 / 403 | Key 无效或无权限 | `AI_KEY_INVALID` | 禁用下拉 + 开手填 |
| 402 / body 含 `insufficient` `balance` `quota` | 欠费 | `AI_NO_QUOTA` | 同上 |
| 404 / 405 | 无 `/models` 端点 | `AI_NO_MODELS_API` | 直接开手填 |
| 超时 8s | `asyncio.TimeoutError` | `AI_UPSTREAM_TIMEOUT` | 同上 |
| 5xx | 上游故障 | `AI_UPSTREAM_ERROR` | **保留上次结果** |
| 429 | 限流 | `AI_RATE_LIMITED`（带 retry_after） | 保留上次结果 |

- 上游 body **只进服务端日志且已脱敏**，不回传前端；错误对象里不得出现 Key 片段。
- 拉取成功但列表为空 → 按 `AI_NO_MODELS_API` 处理（有些兼容网关会返回 `{"data":[]}`）。

### 7.2 缓存与失效：防止跨服务商串味

- 缓存键：`(user_id, provider, base_url, key_fingerprint)`，`key_fingerprint = sha256(key)[:16]`，只存指纹不存明文。
- 命中条件：24h 内 **且** `provider` / `base_url` / `key_fingerprint` 三者都未变。
- **切换服务商或换 Key 立即作废**（不靠 TTL），否则 A 家的 `deepseek-v4-pro` 会被带到 B 家的下拉里。
- 用户主动点「重新拉取」→ 无视 TTL 重打一次。
- 并发点击 → **single-flight**：同一用户同一缓存的并发请求只打上游一次，其余复用结果。

### 7.3 上下文注入：让 AI 知道你昨天学了什么

```mermaid
sequenceDiagram
    autonumber
    participant U as 用户
    participant W as 前端
    participant A as AI 服务
    participant DB as DB
    participant L as 大模型

    U->>W: 帮我复盘今天学习情况
    W->>A: POST /ai/chat {session_id, message}
    A->>A: 限流（10 次/分 · 200 次/天）
    A->>DB: 取近 N 条会话历史（按条数截断，N=10）
    A->>DB: 构建上下文（**只读本人**）
    Note over A,DB: 待办任务≤20 条 · 7 天完成聚合<br/>今日番茄时长/颗数/是否在专注 · 30 天热力摘要
    A->>A: 摘要拼装，token 预算 ≤1200，超出按"最近优先"截断
    A->>L: system(摘要) + history + message
    L-->>A: SSE
    A-->>W: 逐字流式返回
    A->>DB: 落 ai_messages（含 token 用量、latency）
```

**三条边界**（写死，别在实现时松口）：
1. **只读本人**：`WHERE user_id = current_user.id`，不读同圈成员，也不读被移出圈子的历史数据；
2. **只给摘要**：任务最多 20 条、统计只给聚合值，绝不把原始行整表塞进 prompt；
3. **`privacy_mode` 不阻断**：隐私模式是"不让别人看"，AI 是"给自己用"；但摘要里**不得出现他人昵称**。

### 7.4 任务导入：唯一会写数据的 AI 能力

```mermaid
sequenceDiagram
    autonumber
    participant U as 用户
    participant W as 前端
    participant A as AI 服务
    participant DB as DB

    Note over U: AI 回复里带 ```json 任务块
    W->>W: 解析 JSON（schema 校验：title / acceptance / estimate_min）
    alt 解析失败或缺字段
        W->>U: **隐藏「一键导入」按钮**（不报错、不崩）
    else 解析成功
        U->>W: 点「一键导入为系统任务」
        W->>U: 预览弹窗（逐条可取消）
        U->>W: 确认
        W->>A: POST /ai/import-tasks {message_id, tasks[]}
        A->>A: 幂等校验：该 message 已导入 → 409 直接返回已导入
        A->>DB: 批量 insert task(source='ai', source_message_id=?)
        A-->>W: {imported: n, task_ids:[...]}
        W->>U: 「已导入 n 条」+ 「撤销本次导入」
    end
```

- **禁止静默新增**：没有确认弹窗就不许写库；这是硬性验收项。
- 幂等：`source_message_id` + `imported_at` 判重，同一条回复只能导一次（重复请求返回 409 与已导入数量）。
- 撤销：按 `source_message_id` 批量软删（`deleted_at`），并写入 `admin_operation_log` 之外的**用户操作记录**（`task` 表本身的 `deleted_at` 足够追溯）。
- 导入的任务与手动任务同构：同表、同同步、同圈子聚合、同隐私规则。

### 7.5 红线汇总

- `key_cipher` 任何接口都不返回；第三方错误统一脱敏；**AI Key 与对话记录都不进离线同步**。
- 所有服务商走 OpenAI 兼容的 `/v1/chat/completions`，一个适配器通吃；非该协议一期不接。
- 模型 id **不写死在前端**：下拉内容一律来自本次拉取结果或用户手填。

---

## 8. 管理员调整 VIP

```mermaid
sequenceDiagram
    autonumber
    participant AD as 管理员后台
    participant A as API
    participant DB as DB
    participant U as 被调整用户

    AD->>A: PUT /admin/user/{id}/vip {action, expire_at, remark}
    A->>A: 校验管理员 + remark ≥5 字
    A->>DB: 事务开始
    A->>DB: UPDATE user SET vip_level, vip_expire_at, vip_updated_at
    alt action = revoke
        A->>DB: UPDATE user_ai_key SET status=0（**保留不删**）
        A->>DB: insert message(type='vip_change')   ← 仅站内
    else action = grant / renew
        A->>DB: UPDATE user_ai_key SET status=1（恢复可用）
        A->>DB: insert message(type='vip_change')
    end
    A->>DB: insert admin_operation_log{admin_id, before, after, remark, ip}
    A->>DB: 事务提交
    A-->>AD: 200
    A->>U: 【异步】邮件通知（仅开通/续期）

    Note over DB: 每天 04:00 定时任务
    DB->>DB: vip_expire_at < now → vip_level=0 + AI Key 停用 + 站内消息
```

**说明**
- 降级后用户**立即**失去完整链接与 AI 使用权；Key 不删除，恢复 VIP 后自动可用
- 管理员不能删除 `admin_operation_log`，保证可追溯
- VIP 状态属服务端权威，同步时客户端无法篡改（见 `04-SYNC` 字段白名单）

---

## 9. 圈子加入 / 审核 / 退出（二期草案）

> 对应 `01-PRD` §8 与 `03-DB` §3.8。一期不实现，此节为二期设计基线。

### 9.1 加入时序（四档合一）

```mermaid
sequenceDiagram
    autonumber
    participant U as 用户
    participant W as 前端
    participant A as API
    participant C as 圈主端

    U->>W: 探索页点进圈子 / 打开邀请链接
    W->>A: GET /circles/{id}/preview
    A-->>W: {name, intro, member_count, today_total_min, visibility}
    Note over W: 旁观态只给摘要，不给任何成员明细

    alt visibility = public
        U->>W: 点「加入」
        W->>A: POST /circles/{id}/join
        A->>A: member_count < limit ? insert circle_member(state=active) : 409 圈子已满
        A-->>W: {state: active}
    else visibility = public_review
        U->>W: 填申请理由（≥5 字）
        W->>A: POST /circles/{id}/requests
        A->>A: insert circle_join_request(pending, pending_key 唯一)
        C->>A: POST /circles/{id}/requests/{rid}/review
        A->>A: 校验 role ∈ (owner, admin) 且属于本圈 → approved 时 insert circle_member(state=active)
        A-->>C: 通过 / 驳回（驳回必填原因）
    else visibility = code
        U->>W: 输入 8 位码
        W->>A: POST /circles/join-by-code {code}
        A->>A: join_code 有效 且 code_expires_at > now ? 入圈 : 403
    else visibility = private
        Note over C: 圈主单人邀请，生成 24h 一次性链接
        C->>A: POST /circles/{id}/invites
        A-->>C: 一次性 token
        U->>A: POST /circles/join-by-invite {token}
        A->>A: token 未用 且 未过期 → 入圈并置为已用
    end

    A->>A: member_count++（同事务）
```

**四种入口共用一条落地逻辑**：`circle_member` 落一行 `state=active`，再同事务 `member_count++`。区别只在「前置校验」，不要写成四套代码。

**码的防爆破**：`code` 档 8 位大写码理论上可枚举，必须加限流——同一 IP / 同一 user 每小时最多 10 次失败，超限 403 并记 `admin_operation_log`；码本身 7 天过期、圈主可随时重置。不要只靠"码够长"。

**圈主权限边界**：审核接口校验 `role ∈ (owner, admin)` 且属于**本圈**；绝不能复用平台管理员的 `/admin/*` 前缀，否则圈主会拿到跨圈能力。

### 9.2 成员状态机

```
（无记录）
   │ 申请/邀请/自助
   ▼
pending ──圈主通过──► active ──退出──► left ──30天内重进──► 需圈主同意
   │                    │
   │ 驳回/撤回           │ 被移出
   ▼                    ▼
rejected            blocked（拉黑，探索页不可见）
```

- `left` 不删行，`left_at` 是「30 天重进需审批」的唯一依据；
- `blocked` 由圈主操作，解除也要圈主操作，没有自动过期；
- 一个人在同一圈子只有一行，状态流转就地更新，**不要 insert 新行**（唯一索引也会挡）。

### 9.3 退出 / 撤权的收敛顺序

```mermaid
sequenceDiagram
    autonumber
    participant U as 用户
    participant A as API
    participant O as 其他成员端

    U->>A: DELETE /circles/{id}/members/me
    A->>A: state=left, left_at=now, member_count--（同事务）
    A->>A: 该用户在本圈投入的错题 → revoked_at=now（M2）
    A->>A: 失效其图片签名 URL（M2）
    O->>A: GET /circles/{id}/board（60s 内轮询）
    A-->>O: 该成员已不在返回列表中
```

**验收口径**：看板是**服务端聚合**，不依赖客户端删缓存——退出后最多一个轮询周期（60s）内消失，不出现"人退了数字还在"。

### 9.4 房间与圈子的校验关系

- 一期：进房校验 `room.invite_code` / 房间申请（F-20/F-21）。
- 二期：**进圈校验一次，进圈内房间不再校验**。`POST /circles/{cid}/rooms/{rid}/join` 只看两点：① 是否 `circle_member.state=active`；② 房间是否 `open`。房间不再有自己的码。
- 这样避免"进了圈还要再找房间码"的双重门槛，也让 F-21 的语义从"房间码"干净地迁到"圈子码"。

### 9.5 与隐私模式的叠加

| 场景 | `privacy_mode=0` | `privacy_mode=1` |
|---|---|---|
| 圈内看板 | 按 `share_level` 展示 | 只显示「在线」，不显示任何数字 |
| 成员列表 | 昵称 + 形象 + 状态 + 今日时长 | 昵称 + 默认形象 + 状态，无时长 |
| 错题池 | 按投入情况展示 | 一律不展示（即使 `share_level=3`） |

**隐私模式优先级高于共享档位**，且是用户级一次设置、全圈子同时生效——不要给每个圈子各配一个"隐身开关"，那会让用户永远不确定自己现在到底隐没隐身。
