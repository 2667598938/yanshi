# 内测功能检查与修复 · 2026-10-29

基于 GitHub 功能分支 `bdea69e`，保留其 AI 手机布局及无障碍修复。此次固定内测登录策略，并检查现有全部功能域的接口与组件回归。

## 已修复问题

| 问题 | 现在的行为 |
|---|---|
| 验证码登录仍可用 | 默认 `AUTH_PASSWORD_ONLY=true`：前端直接显示账号密码；后端拒绝登录验证码发送/验证、自助注册、短信、OAuth及旧登录票据 |
| 后台注册开关与内测规则矛盾 | 后台禁用开放注册，接口拒绝开启，概览与公共配置返回实际生效状态；管理员仍可创建账号 |
| 配置失败仍显示“正在检查” | 加载/失败分开，失败时密码入口仍可用，并提供重试 |
| 管理员创建的邮箱账号受注册域名限制而无法找回密码 | 重置密码只校验既有账号和验证码，不受自助注册域名限制；限流和旧会话撤销保留 |
| AI回答完成删除下一问草稿 | 输入区已有新草稿/图片时保留，不再无条件删除 |
| AI生成结束抢滚动位置 | 向上阅读时保持位置，留在底部才继续跟随 |
| AI用量接口失败导致模型配置不回填 | 已保存服务商、地址、模型独立回填，用量失败单独提示 |
| 删除Key后在途请求回填旧模型 | 删除使在途目录失效并清理输入；保存/删除期间锁定关联表单 |

此前本地像素 favicon 与缓存版本、响应式插画独立降级也纳入交付。

## 逐功能检查

下表的通过是接口/业务或组件自动验证，不能等同于每个按钮已在真实手机上点击。

| 功能域 | 验证范围 | 主要回归文件 |
|---|---|---|
| 登录/账号 | 密码、错误锁定、重置、Cookie恢复、过期身份、换号、禁用旧登录、管理员创建 | `test_auth.py`、`test_password_only.py`；`auth-view`、`auth-restore`、`auth-switch` |
| AI配置 | 加密/脱敏Key、本人隔离、目录拉取、缓存、权限/额度错误、手填、服务商切换、删除竞态 | `test_ai_protocol.py`、`test_model_catalog_current.py`；`ai-models-search`、`ai-settings-owner` |
| AI对话 | 多会话私有历史、流式、停止/重试、图片、输入法、主题、草稿与阅读滚动 | `test_ai.py`、`test_ai_vision_tools.py`；`ai-view`、`http-stream` |
| AI学习与任务 | 本人摘要、隐私开启仍能分析、排除组员、确认导入、幂等、安全撤销 | `test_beta_end_to_end.py`、`test_current_workflows.py`、`test_ai_budget.py` |
| 自习室 | 公私房、凭码、审批、满员、并发抢最后席位、管理、留言、隐私、过期状态、离开后的权限 | `test_room*.py`、`test_current_workflows.py`、`test_beta_end_to_end.py`；`room-lifecycle` |
| 计时/统计 | 账号全局主设备、离线、重叠人工裁决、180分钟、暂停、非法记录、冲突不计汇总 | `test_integrity_workflows.py`；`timer`、`timer-lease`、`learning-cycle` |
| 任务/错题/复习 | 任务完成、错题编辑/题图/解析图、复习进度、巩固回退、到期更新 | `test_sync.py`、`test_attachment.py`；`mistakes`、`mistake-edit`、`reactive-clock` |
| 小组/隐私 | 独立审批、同组共享、无管理员隐私绕过、增量更新/删除、失权清理、多设备状态 | `test_group_*.py`；`group-incremental`、`group-presence`、`presence-identity` |
| 梦校/时间节点 | 自定义院校、多图、排序、账号隔离、节点增删、示例日期、弹幕审核 | `test_group_v1.py`、`test_preferences_contract.py`；`school-management`、`schools-account-scope`、`school-hero` |
| 资料/动态/投稿 | 审后公开、审核版本、私有备注、搜索、收藏离线、动态/评论及删除原因 | `test_community*.py`、`test_global_audit.py`；`resource-review`、`community-sync` |
| VIP/消息/后台 | 邀请码、授权审批/撤销、批量码、配置版本冲突、信箱分页、邮件任务、日志权限 | `test_vip.py`、`test_admin*.py`、`test_entitlements_jobs.py`；`messages-pagination`、`admin-desktop` |
| 同步/备份/布局 | 幂等、增量、冲突、账号隔离、附件鉴权、备份、迁移、桌面/手机媒体规则 | `test_sync*.py`、`test_backup_restore.py`、`test_migration_consistency.py`；`sync-boundaries`、`responsive-shell`、`auth-layout` |

## 本轮证据

- 前端263项/51文件通过，生产构建成功。
- 后端195项全量回归通过；密码重置域名边界变更后另跑账号相关22项，全部通过。最终提交还需核对CI。
- 旧自习室用例在午夜附近失败：25分钟前开始的记录可能属于昨天，但用例固定要求今天1500秒。已按现有“开始日归属”修正测试预期，未改变业务统计口径。
- 本地预览：管理员密码登录成功；24个已登录功能读取接口均200；4个旧登录路径均403。
- 真实AI：经网站后端及账号已保存的Key完成一次最小流式调用，HTTP200、6个delta、done事件、9个回答字符、无错误，约1.73秒。没有读取/导出Key明文或新建测试会话。
- 真实链路业务测试仅在供应商HTTP传输处使用隔离响应：保存Key→拉模型→本人摘要→流式→持久历史→确认导入→幂等→撤销；自习室申请审批→心跳→留言→隐私→双设备独占→退出，均已通过。
- 联调前已备份验收库；读取检查前后45条学习记录逐行哈希一致，未重置账号或附件。

## 实机与部署

本轮Tabbit稳定启动器返回退出码1且无输出，未建立浏览器连接，没有新增真实页面点击、手机软键盘/触控、125%缩放及帧率证据。响应式组件测试不替代这些检查。七牛生产存储与真实SMTP不在本轮外部联调结果内。真实AI成功只覆盖当前账号当前模型，不代表所有供应商/模型。

无需数据库迁移。发布前端并重启后端，保持 `AUTH_PASSWORD_ONLY=true`；已有数据库的注册开关不能绕过该部署策略。邮箱验证仅用于找回密码，不再用于登录。
