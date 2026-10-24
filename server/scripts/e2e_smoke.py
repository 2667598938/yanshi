"""端到端冒烟：对已运行的 uvicorn(127.0.0.1:8000) 走真实 HTTP 全链路。

覆盖：管理员登录 → 开放注册/邀请码 → 邮件验证码 → 注册第二账号 → 第二账号登录
     → 数据同步(push/pull) → 自习室心跳/状态/排行榜 → AI 对话 → 上传头像
     → 后台概览 → 清理临时成员。

用法：.venv\\Scripts\\python.exe scripts\\e2e_smoke.py
结束后会删除临时注册的成员和邀请码，不污染固定 4 人自习室。
"""
import io
import os
import re
import sys
import time
from pathlib import Path

import httpx
from PIL import Image

BASE = "http://127.0.0.1:8000/api/v1"
ADMIN_EMAIL = os.environ.get("YANSHI_ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.environ.get("YANSHI_ADMIN_PASSWORD", "")
MAIL_DIR = Path(__file__).resolve().parents[1] / "data" / "mail"

passed = []
failed = []


def check(name, ok, detail=""):
    (passed if ok else failed).append(name)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail and not ok else ""))


def must(r, label):
    try:
        j = r.json()
    except Exception:
        raise AssertionError(f"{label} 非 JSON: {r.status_code} {r.text[:200]}")
    if r.status_code != 200 or j.get("code") != 0:
        raise AssertionError(f"{label} 失败: HTTP {r.status_code} {j}")
    return j.get("data")


def read_latest_code(before):
    files = [p for p in MAIL_DIR.glob("*.txt") if p.stat().st_mtime > before]
    files.sort(key=lambda p: p.stat().st_mtime)
    assert files, "未找到新邮件文件"
    m = re.search(r"验证码是 (\d{6})", files[-1].read_text(encoding="utf-8"))
    assert m, "邮件中未找到验证码"
    return m.group(1)


def main():
    ts = int(time.time())
    member_email = f"e2e_{ts}@yanshi.test"
    member_password = "Member2028x"
    created_member_id = None
    created_invite_id = None
    reg_open_was = None

    with httpx.Client(base_url=BASE, timeout=30.0) as http:
        ah = {}

        def admin_auth(t):
            ah["Authorization"] = f"Bearer {t}"

        # 1. 管理员登录
        d = must(http.post("/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}),
                 "管理员登录")
        admin_token = d["access_token"]
        admin_auth(admin_token)
        check("管理员登录", bool(d["user"]))

        # 2a. 清理上次异常可能残留的 e2e 成员 / 邀请码
        for m in must(http.get("/admin/members", headers=ah), "成员列表"):
            if str(m.get("email", "")).startswith("e2e_") and m.get("role") != "admin":
                http.delete(f"/admin/members/{m['id']}", headers=ah)
        for iv in must(http.get("/admin/invites", headers=ah), "邀请码列表"):
            if iv.get("remark") == "e2e冒烟" and not iv.get("is_used"):
                http.delete(f"/admin/invites/{iv['id']}", headers=ah)

        # 2b. 开放注册（冒烟结束统一恢复为关闭）
        must(http.put("/admin/config", headers=ah, json={"registration_open": True}), "开放注册")
        inv = must(http.post("/admin/invites", headers=ah, json={"remark": "e2e冒烟", "expires_days": 7}),
                   "建邀请码")
        created_invite_id = inv["id"]
        invite_code = inv["code"]
        check("生成邀请码", bool(invite_code), invite_code)

        # 3. 发送注册邮件验证码
        before = time.time() - 1
        must(http.post("/auth/email-code", json={"email": member_email, "scene": "register"}),
             "发邮件验证码")
        time.sleep(0.5)
        code = read_latest_code(before)
        check("读取邮件验证码", bool(code), code)

        # 4. 注册
        d = must(http.post("/auth/register", json={
            "email": member_email, "code": code, "password": member_password,
            "nickname": "冒烟研友", "invite_code": invite_code, "accepted_terms": True,
        }), "注册")
        member_token = d["access_token"]
        created_member_id = d["user"]["id"]
        check("第二账号注册", d["user"]["nickname"] == "冒烟研友")

        # 5. 第二账号登录
        d = must(http.post("/auth/login", json={"email": member_email, "password": member_password}),
                 "成员登录")
        mh = {"Authorization": f"Bearer {d['access_token']}"}
        check("第二账号登录", d["user"]["id"] == created_member_id)

        # 6. 同步：push 两条（subject + session）
        op_id = f"e2e-op-{ts}"
        now_ms = int(time.time() * 1000)
        session_id = f"e2e-sess-{ts}"
        subject_id = f"e2e-subj-{ts}"
        # CN 今日日期
        cn = time.gmtime(time.time() + 8 * 3600)
        today = time.strftime("%Y-%m-%d", cn)
        changes = [
            {"id": subject_id, "expectedRevision": 0, "record": {
                "type": "subject", "id": subject_id, "name": "冒烟数学",
                "color": "#3b82f6", "icon": "math", "tags": [], "order": 99,
                "archived": 0, "builtin": 0, "createdAt": now_ms}},
            {"id": session_id, "expectedRevision": 0, "record": {
                "type": "session", "id": session_id, "subjectId": subject_id,
                "mode": "timer", "activityType": "practice", "plannedMin": 25,
                "actualSec": 1500, "status": "done", "startedAt": now_ms - 1500 * 1000,
                "endedAt": now_ms, "date": today, "note": "e2e", "createdAt": now_ms}},
        ]
        d = must(http.post("/sync/commands", headers=mh, json={"operationId": op_id, "changes": changes}),
                 "同步推送")
        check("同步推送(2条)", len(d.get("changed", [])) == 2, str(d))

        # 幂等：相同 operationId 重放返回首次结果（code 0）
        r = http.post("/sync/commands", headers=mh, json={"operationId": op_id, "changes": changes})
        check("相同操作重放幂等(返回首次结果)", r.json().get("code") == 0)
        # 同 ID 不同内容应 40903
        diff = [{"id": subject_id, "expectedRevision": 0,
                 "record": {**changes[0]["record"], "name": "被篡改的科目"}}]
        r2 = http.post("/sync/commands", headers=mh, json={"operationId": op_id, "changes": diff})
        check("同ID不同内容拒绝(40903)", r2.json().get("code") == 40903)

        # pull
        d = must(http.get("/sync/records", headers=mh), "同步拉取")
        ids = {x["id"] for x in d.get("records", [])}
        check("同步拉取含新记录", session_id in ids and subject_id in ids)

        # 7. 自习室心跳 + 状态
        must(http.post("/room/heartbeat", headers=mh, json={
            "status": "focusing", "subject_client_id": subject_id,
            "subject_name": "冒烟数学", "activity_type": "practice",
            "mode": "timer", "focus_started_at": now_ms - 600 * 1000,
        }), "心跳")
        room = must(http.get("/room", headers=mh), "自习室")
        me = next((m for m in room["members"] if m["user_id"] == created_member_id), None)
        check("自习室含我", me is not None)
        check("心跳聚焦状态", me and me["presence"]["status"] == "focusing")
        check("排行榜聚合到时长",
              any(x.get("user_id") == created_member_id for x in room["ranking"]["today"]),
              str(room["ranking"].get("today")))

        # 留言 + 目标墙
        msg = must(http.post("/room/messages", headers=mh, json={"content": "e2e 加油"}), "留言")
        check("自习室留言", bool(msg.get("id")))
        goal = must(http.put("/room/goal", headers=mh,
                             json={"target_school": "fudan", "target_score": "400", "words": "e2e"}), "目标墙")
        check("目标墙", goal.get("target_school") == "fudan")

        # 8. AI 对话（真实火山方舟）
        try:
            ai = must(http.post("/ai/chat", headers=mh, json={
                "scene": "kaoyan", "content": "用一句话鼓励我坚持考研复习。"}, timeout=60), "AI 对话")
            check("AI 对话返回", bool(ai.get("reply")), str(ai)[:120])
            if ai.get("conversation_id"):
                created_cid = ai["conversation_id"]
                http.delete(f"/ai/conversations/{created_cid}", headers=mh)
        except AssertionError as e:
            check("AI 对话返回", False, str(e))

        # 9. 上传头像
        img = Image.new("RGB", (600, 600), (120, 90, 200))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=90)
        up = must(http.post("/attachments/avatar", headers=mh,
                            files={"file": ("avatar.jpg", buf.getvalue(), "image/jpeg")}), "上传头像")
        check("头像上传(方裁)", up.get("key", "").startswith("avatar/"))
        me2 = must(http.get("/auth/me", headers=mh), "拉取资料")
        check("头像已绑定", me2["avatar_key"] == up["key"])

        # 10. 清理：删留言（略）、删除临时成员、邀请码、恢复注册开关
        if created_member_id:
            http.delete(f"/admin/members/{created_member_id}", headers=ah)
        if created_invite_id:
            http.delete(f"/admin/invites/{created_invite_id}", headers=ah)
        must(http.put("/admin/config", headers=ah,
                      json={"registration_open": False}), "恢复注册开关")
        check("清理临时成员", True)

    print("\n================ 结果 ================")
    print(f"通过 {len(passed)} 项，失败 {len(failed)} 项")
    if failed:
        print("失败项：" + "、".join(failed))
        sys.exit(1)
    print("全链路冒烟通过")


if __name__ == "__main__":
    main()
