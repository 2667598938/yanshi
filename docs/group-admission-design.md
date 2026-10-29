# 学习小组邀请与审批：当前实现合同

更新2026-10-26。小组、房间准入独立，以及账号全局主计时规则已由用户确认。新邀请/申请/撤回/审批/撤销及前后端入口已实现待验收，不再是未接线草稿。

- 当前仅管理默认受邀小组；管理者为本组内的平台管理员，不引入多圈子或子管理员体系。
- 注册码、VIP码与小组邀请独立。0天注册码不赠送VIP；永久VIP由现有独立管理操作授予，0不代表永久。combine组合码不开放。
- 小组邀请使用group_invites，仅保存令牌摘要、有效期、创建者和可选指定账号；原始码只在创建响应显示。
- 单份邀请绑定一个申请账号，必须审批。拒绝、撤回或重复申请不会偷偷入组；过期/撤销的邀请不能批准。
- group_applies保存申请状态、revision、处理人/时间/原因；审计表以group.*动作区分VIP日志。批准、成员写入、站内通知、邮件队列和审计同事务提交。
- 用户接口：GET /group-admission/mine；POST /group-admission/applications；POST /group-admission/applications/{id}/withdraw。
- 管理接口：GET/POST /group-admission/invites、POST /group-admission/invites/{id}/revoke、GET /group-admission/applications、POST /group-admission/applications/{id}/review。
- 页面：用户/group/admission，管理员/admin/group。普通注册不自动进组或加入默认房间；已有成员保留。管理员建号的既有受邀语义保留。
- 审批仅授予小组学习共享资格，绝不同时授予VIP或房间准入。隐私、私图、AI会话/Key、资料私人备注的原权限边界不变。

真实设备验收、生产并发与外部邮件联调仍须按清单验证。
