"""密码内测策略下跨模块闭环；仅替换供应商HTTP传输，应用业务逻辑全部真实运行。"""

import json
from datetime import datetime, timezone
import httpx
from app.tests.conftest import login
from app.tests.test_rooms import h, make_member
from app.tests.test_group_v1 import push


def actors(client):
    client.app.state.settings.auth_password_only = True
    admin = h(login(client, "admin@test.com", "Admin2028")["access_token"])
    row = make_member(client, admin, "beta-owner@test.com", "测试研友")
    owner = h(login(client, "beta-owner@test.com", "Friend2028")["access_token"])
    return admin, owner, row["id"]


def test_byok_models_stream_private_context_import_undo_and_history(
    client, monkeypatch
):
    admin, owner, uid = actors(client)
    assert (
        client.put(
            f"/api/v1/admin/members/{uid}",
            headers=admin,
            json={"vip_action": "grant", "vip_days": 30, "note": "完整闭环验收"},
        ).status_code
        == 200
    )
    push(
        client,
        owner,
        [
            {
                "id": "self-task",
                "type": "task",
                "title": "本人积分练习",
                "estimatedMin": 30,
            }
        ],
    )
    push(
        client,
        admin,
        [{"id": "peer-task", "type": "task", "title": "其他成员的秘密任务"}],
    )
    client.put("/api/v1/users/me", headers=owner, json={"is_private_mode": True})
    key = "sk-isolated-protocol-test-12345678"
    response = client.put(
        "/api/v1/ai/key",
        headers=owner,
        json={"provider": "deepseek", "model": "actual-model", "api_key": key},
    )
    assert response.status_code == 200, response.text
    assert key not in response.text
    original_client = httpx.AsyncClient
    captured = []
    answer = (
        "先完成积分练习。\n```yanshi_tasks\n"
        + json.dumps(
            {
                "tasks": [
                    {
                        "title": "明天复习积分",
                        "estimated_min": 30,
                        "accept_criteria": "完成5题",
                    }
                ]
            },
            ensure_ascii=False,
        )
        + "\n```"
    )

    def provider(request):
        assert request.headers["Authorization"] == "Bearer " + key
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "actual-model"}]})
        body = json.loads(request.content)
        captured.append(body)
        assert body["model"] == "actual-model"
        assert body["stream"] is True
        return httpx.Response(
            200,
            text="data: "
            + json.dumps({"choices": [{"delta": {"content": answer}}]})
            + "\n\ndata: "
            + json.dumps(
                {"usage": {"prompt_tokens": 20, "completion_tokens": 30}, "choices": []}
            )
            + "\n\ndata: [DONE]\n\n",
            headers={"content-type": "text/event-stream"},
        )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: original_client(transport=httpx.MockTransport(provider), **kw),
    )
    catalog = client.post(
        "/api/v1/ai/models", headers=owner, json={"provider": "deepseek"}
    )
    assert catalog.json()["data"]["models"] == ["actual-model"]
    cid = client.post(
        "/api/v1/ai/conversations", headers=owner, json={"scene": "plan"}
    ).json()["data"]["id"]
    response = client.post(
        "/api/v1/ai/chat/stream",
        headers=owner,
        json={
            "conversation_id": cid,
            "scene": "plan",
            "content": "基于我的任务安排明天",
        },
    )
    assert response.status_code == 200
    events = [
        json.loads(line[6:])
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert [e["type"] for e in events] == ["delta", "done"]
    mid = events[-1]["message_id"]
    assert events[-1]["suggested_tasks"][0]["title"] == "明天复习积分"
    context = json.dumps(captured[0]["messages"], ensure_ascii=False)
    assert (
        "本人积分练习" in context
        and "其他成员的秘密任务" not in context
        and key not in context
    )
    assert (
        client.get(f"/api/v1/ai/conversations/{cid}", headers=admin).status_code == 404
    )
    messages = client.get(f"/api/v1/ai/conversations/{cid}", headers=owner).json()[
        "data"
    ]["messages"]
    assert messages[-1]["content"] == answer
    url = f"/api/v1/ai/messages/{mid}"
    assert (
        client.post(
            url + "/import-tasks", headers=owner, json={"confirmed": False}
        ).status_code
        == 400
    )
    first = client.post(url + "/import-tasks", headers=owner, json={"confirmed": True})
    assert first.status_code == 200, first.text
    assert (
        client.post(
            url + "/import-tasks", headers=owner, json={"confirmed": True}
        ).json()
        == first.json()
    )
    assert (
        client.post(
            url + "/undo-tasks", headers=owner, json={"confirmed": True}
        ).json()["data"]["undo"]["deleted"]
        == 1
    )
    # 重发原请求只返回已撤销回执，不能创建新任务。
    assert (
        client.post(
            url + "/import-tasks", headers=owner, json={"confirmed": True}
        ).json()["data"]["state"]
        == "undone"
    )
    assert client.delete("/api/v1/ai/key", headers=owner).status_code == 200
    assert (
        client.get(f"/api/v1/ai/conversations/{cid}", headers=owner).status_code == 200
    )


def test_private_room_code_presence_privacy_and_global_timer(client):
    admin, owner, uid = actors(client)
    room = client.post(
        "/api/v1/rooms",
        headers=admin,
        json={
            "accept_sharing": True,
            "name": "完整闭环自习室",
            "visibility": "private",
        },
    ).json()["data"]
    path = f"/api/v1/rooms/{room['id']}"
    assert client.get(path, headers=owner).status_code == 403
    assert client.post(path+'/apply',headers=owner,json={'accept_sharing':True}).status_code==410
    assert client.post(path+'/join',headers=owner,json={'accept_sharing':True,'code':room['code']}).status_code==200
    assert (
        client.post(
            "/api/v1/group/presence",
            headers=owner,
            json={
                "device_id": "desktop",
                "room_id": room["id"],
                "status": "focusing",
                "subject_name": "数学",
            },
        ).status_code
        == 200
    )
    mine = next(
        x
        for x in client.get(path, headers=admin).json()["data"]["members"]
        if x["user_id"] == uid
    )
    assert mine["online"] and mine["presence"]["status"] == "focusing"
    assert (
        client.post(
            path + "/messages", headers=owner, json={"content": "今天完成5题"}
        ).status_code
        == 200
    )
    assert (
        client.get(path, headers=admin).json()["data"]["messages"][-1]["content"]
        == "今天完成5题"
    )
    assert (
        client.put(
            "/api/v1/users/me", headers=owner, json={"is_private_mode": True}
        ).status_code
        == 200
    )
    hidden = next(
        x
        for x in client.get(path, headers=admin).json()["data"]["members"]
        if x["user_id"] == uid
    )
    assert hidden["presence"] == {"status": "private"} and "today_sec" not in hidden
    assert (
        client.get(f"/api/v1/group/members/{uid}/learning", headers=admin).status_code
        == 404
    )
    session = {
        "session_id": "desktop-round",
        "device_id": "desktop",
        "started_at": int(datetime.now(timezone.utc).timestamp() * 1000),
    }
    assert (
        client.post("/api/v1/timer/start", headers=owner, json=session).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/timer/start",
            headers=owner,
            json={**session, "device_id": "phone", "session_id": "phone-round"},
        ).status_code
        == 409
    )
    assert (
        client.post("/api/v1/timer/release", headers=owner, json=session).status_code
        == 200
    )
    assert client.post(path + "/leave", headers=owner).status_code == 200
    assert client.get(path, headers=owner).status_code == 403
    assert (
        client.post(
            path + "/messages", headers=owner, json={"content": "不能写入"}
        ).status_code
        == 403
    )
