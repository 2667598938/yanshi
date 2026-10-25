> 版本说明：本文件保留原始设计记录。2026-10-25后续用户确认的小组隐私、个人梦校/倒计时及AI V1规则已更新，以[当前验收清单](../acceptance-checklist.md)和[AI V1说明](../ai-capabilities.md)为准；旧匿名占位、隐私计入在线人数及通用工具规则已被替代。

# 研时 yanshi · 一期规则锁定（决策落地细则）

> 本文件是 `checklist.md` 的配套落地版：把 5 个关键决策写成**可直接照着写代码**的规则。
> 凡此处与开发中的直觉冲突，以本文件为准。

---

## 决策 1 · 审核结果通知：站内消息 + QQ邮件（双通道）

### 规则
管理员在后台点击「通过 / 驳回」的**同一事务**里落站内消息；邮件**异步发送**，失败不影响主流程。

```
创建消息记录 (message 表)  ← 同步，必须成功
      ↓ commit
投递邮件任务              ← 异步 Celery/BackgroundTasks，失败重试 3 次
```

### 冲突时的取舍
| 场景 | 处理 |
|---|---|
| 邮件服务挂了 | 站内消息已送达，申请状态正常流转；邮件失败写 `email_log`，后台可重发 |
| 用户从未上线 | 邮件兜底触达，站内消息下次登录即见红点 |
| 同一申请重复触发 | `apply_record.status` 做乐观锁，非 `pending` 直接拒绝，防重复通知 |

### 邮件模板

**通过**
```
主题：【研时】你的「{item_name}」功能申请已通过
正文：
  你好，{nickname}：
  你于 {apply_time} 提交的「{item_name}」使用申请已通过审批。
  即刻起可在 {entry_route} 中直接使用。
  —— 研时 yanshi · duzhi.xin
```

**驳回**
```
主题：【研时】你的「{item_name}」功能申请未通过
正文：
  你好，{nickname}：
  很遗憾，你的申请未通过审批。
  驳回原因：{reject_reason}
  补充材料后可再次提交申请。
```

### 落地要求
- 邮箱即账号，**100% 可达**，不需要额外绑定流程
- 开发环境 `SMTP_ENABLED=false` → 不发真实邮件，邮件正文打印到日志，验证码直接输出到日志（便于本地调试登录流程）
- 同一申请必须保证**通知恰好一次**：`message` 表对 `(user_id, biz_type, biz_id)` 建唯一索引

---

## 决策 2 · 隐私模式：隐藏学习数据 + 匿名占位

### ⚠️ 连带修正（重要）
原清单里写的「隐私模式本地记忆」**不够用**。房间后台要给其他人返回成员列表，**服务端必须知道谁开了隐私**，否则一旦其他人拉取列表就会泄露。因此：

- `user.privacy_mode` **服务端持久化**，并纳入「用户基础信息」同步范围
- `localStorage` 只做 UI 即时响应的**缓存**，不是数据源

### 名单显示对照表

| 展示项 | 普通成员 | 隐私模式成员 |
|---|---|---|
| 昵称 | 真实昵称 | `隐身学习中` |
| 头像 | 真实头像 | 灰色默认占位头像 |
| 当前番茄状态（专注/休息/空闲） | 显示 | **隐藏** |
| 今日累计时长 | 显示 | **隐藏** |
| 房间排行榜 | 参与排名 | **不参与**（过滤掉，不占位） |
| 是否计入在线人数 | 是 | 是（占位，避免人数忽上忽下） |
| 房间留言署名 | 真实昵称 | 真实昵称（留言是主动行为，不适用隐身） |

### 接口层约定
房间成员列表接口在 **serializer 层**统一过滤，禁止在前端 `v-if` 里遮，任何新接口返回成员数据都必须走同一个 `_serialize_member()`。

---

## 决策 3 · 番茄超时：记录真实时长，封顶 180 分钟

### 字段定义（`tomato_record`）
```
planned_minutes   计划时长（用户设定）
actual_minutes    有效专注时长 = min(真实流逝 - 累计暂停, 180)
pause_total_sec   累计暂停秒数
status            done | quit
end_reason        manual_done | manual_quit | timeout | pause_timeout
start_at          服务端时间戳
end_at
```

### 计算公式
```python
elapsed = (end_at - start_at) - pause_total_sec
actual_minutes = min(elapsed_seconds / 60, MAX_TOMATO_MINUTES)   # MAX = 180
```

### 三类场景对照
| 场景 | actual | status | end_reason |
|---|---|---|---|
| 25min 计划，准时点结束 | 25 | done | manual_done |
| 25min 计划，实际跑了 40min 才点结束 | **40** | done | manual_done |
| 忘记关闭，跑了 5 小时 | **180**（封顶） | **quit** | timeout |
| 主动中途放弃 | 真实已专注时长 | quit | manual_quit |
| 单次暂停超过 30min | 真实已专注时长 | quit | pause_timeout |

> 注意：超时的番茄虽然记为 `quit`，但 `actual_minutes=180` **仍计入统计**，只是不能点亮「完成番茄」计数。

### 三层判定防漏网
1. **前端 tick**：定时器每秒检测 `now - start_at - pause_total >= MAX` → 立即 `end(timeout)`
2. **页面唤醒校正**：`visibilitychange` / 页面重新加载 / SPA 恢复时，按上面的公式补算一次，防止息屏期间定时器被节流
3. **后端兜底**：`POST /tomato/end` 时后端**重算一遍**，前端传的值不可信；超限一律写 180 + `timeout`

### 暂停上限
单次暂停最长 30min，超时 → 该番茄自动 `quit(pause_timeout)`。多次暂停各自计时，不累加到上限判定。

---

## 决策 4 · 站内消息一期开发

### 表设计（`message`）
```
id, user_id, type, title, content, biz_type, biz_id, is_read, created_at
INDEX (user_id, is_read, created_at)
UNIQUE (user_id, biz_type, biz_id)    ← 防重复通知
```

### type 枚举（一期只做前三个）
| type | 触发 | 是否同时发邮件 |
|---|---|---|
| `apply_result` | 管理员审批通过/驳回 | ✅ 是 |
| `system` | 系统公告、违规内容删除告知 | ❌ 否 |
| `conflict` | 离线冲突待用户处理提示 | ❌ 否 |
| `content_deleted` | 帖子/资料被管理员删除 | ❌ 否 |

> **注意**：`conflict` 只是「待处理提醒」，真正的冲突解决仍走同步层的弹窗二选一，两者不重复弹。

### 拉取策略（一期不用 WebSocket，降低复杂度）
| 时机 | 动作 |
|---|---|
| 登录后 | 立即拉一次未读数 |
| 页面可见时 | 每 **60s** 轮询一次未读数 |
| 页面切后台 | **暂停**轮询（`visibilitychange`） |
| 手动点铃铛 | 立即拉取完整列表 |

理由：只用未读数轮询（返回体极小），消息正文在打开列表时才拉，带宽开销可忽略。二期再上 SSE。

### 明确不做
- ❌ 消息走离线同步（在线数据，落地即读）
- ❌ 实时推送、浏览器 Notification
- ❌ 未读消息自动清理（一期永久保留）

### UI
Header 铃铛 + 未读红点数字（>99 显示 `99+`），详情页列表项点击进入即标记已读。

---

## 决策 5 · Git 规范双分支

```
main   受保护：禁止直接 push，只能由 dev 发 PR 合并，随时可部署
  └── dev     日常开发集成分支
        ├── feat/tomato-core
        ├── feat/sync-engine
        ├── feat/study-room
        └── fix/xxx
```

### 规则
1. 主分支 `main`，开发分支 `dev`，两者**初始同步建库**
2. 所有功能分支从 `dev` 拉，完成后 PR 回 `dev`
3. `dev` 上跑通全部自测 → PR 合并 `main` → 打 tag（`v0.1.0` 起）
4. **禁止** `git push --force` 到 `main` / `dev`
5. 每个 PR 至少：跑通本地启动 + 冒烟主流程

### Commit 规范
```
feat:     新功能      feat: 番茄超时自动 quit 判定
fix:      修 bug      fix: 隐私模式下排行榜未过滤
docs:     文档        docs: 补充 Offline Sync 规则
refactor: 重构        refactor: 抽出 _serialize_member
style:    UI/动效     style: 统一 list stagger 入场
chore:    杂项        chore: 更新 .gitignore
test:     测试        test: 番茄超时边界用例
```

### 初始化命令
```bash
git init && git add . && git commit -m "chore: 初始化仓库结构"
git branch -M main
git checkout -b dev
git push -u origin main && git push -u origin dev   # main 设为默认分支，开分支保护
```

---

## 附：本次决策引发的 3 处连带调整

| # | 原计划 | 调整为 | 原因 |
|---|---|---|---|
| 1 | 隐私模式仅 localStorage 记忆 | **服务端持久化 + 纳入同步字段** | 服务端要过滤返回给其他人的数据，不然等于没隐藏 |
| 2 | SMTP 邮件是可选依赖 | **一期必需依赖** | 双通道通知锁定后，审批流依赖它 |
| 3 | `audit 结果` 单一路径 | **message + email 双写 + 唯一索引防重** | 防止重复点击导致重复通知 |

---

## 附：下一步（待你确认脚手架风格后开工）

1. 仓库骨架：`yanshi-web`（Vite + Vue3 + Pinia + Dexie）/ `yanshi-server`（FastAPI + SQLAlchemy + Alembic）/ `docs`
2. `.env.example`（含全部占位键）+ `.gitignore`
3. `docs/API.md` 初版 + `docs/数据库设计.md` 初版（先出 `user` / `tomato_record` / `apply_record` / `message` 四张表）
4. 打通「邮箱验证码登录」全链路（含 SMTP 降级开关），作为第一条可运行主线
