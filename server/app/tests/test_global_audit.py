"""Global audit regressions: review assets and complete, private-safe search."""

import json
from app.models import Resource
from app.tests.test_group_v1 import headers
from app.tests.test_attachment import register_friend, upload


def test_admin_can_review_pending_inspiration_image_without_private_learning_bypass(
    client,
):
    admin = headers(client)
    owner = register_friend(client, admin, "review-photo@test.com", "投稿作者")
    other = register_friend(client, admin, "reader-photo@test.com", "普通读者")
    key = upload(client, "/api/v1/attachments/image", owner, "inspiration").json()[
        "data"
    ]["key"]
    post = client.post(
        "/api/v1/inspirations",
        headers=owner,
        json={"content": "坚持就是胜利", "image_key": key},
    )
    assert post.status_code == 200
    url = "/api/v1/attachments/view"
    assert client.get(url, headers=admin, params={"key": key}).status_code == 200
    assert client.get(url, headers=owner, params={"key": key}).status_code == 200
    assert client.get(url, headers=other, params={"key": key}).status_code == 404
    private = upload(client, "/api/v1/attachments/image", owner, "mistake").json()[
        "data"
    ]["key"]
    assert client.get(url, headers=admin, params={"key": private}).status_code == 404


def test_resource_search_filters_before_limit_and_uses_approved_version(client):
    admin = headers(client)
    peer = register_friend(client, admin, "search-reader@test.com", "检索同学")
    with client.app.state.session_factory() as db:
        for i in range(105):
            snapshot = {
                "title": "最早目标资料" if i == 0 else f"资料{i}",
                "intro": "检索测试",
                "category": "数学" if i == 0 else "英语",
                "url": "https://example.com/data",
                "code": "",
            }
            db.add(
                Resource(
                    user_id=1,
                    title="未审核秘密" if i == 0 else snapshot["title"],
                    url=snapshot["url"],
                    intro=snapshot["intro"],
                    category=snapshot["category"],
                    review_status="pending" if i == 0 else "approved",
                    approved_snapshot=json.dumps(snapshot),
                    revision=1,
                )
            )
        db.commit()
    rows = client.get(
        "/api/v1/resources", headers=peer, params={"q": "最早目标"}
    ).json()["data"]
    assert len(rows) == 1 and rows[0]["title"] == "最早目标资料"
    assert (
        len(
            client.get(
                "/api/v1/resources", headers=peer, params={"category": "数学"}
            ).json()["data"]
        )
        == 1
    )
    assert (
        client.get(
            "/api/v1/resources", headers=peer, params={"q": "未审核秘密"}
        ).json()["data"]
        == []
    )
