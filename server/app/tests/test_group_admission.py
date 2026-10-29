"""Retired global-group grants cannot be used to bypass room consent."""

from app.models import StudyGroupMember, RoomMember
from sqlalchemy import select
from app.tests.test_sync import headers


def test_old_global_group_routes_are_retired_without_membership_changes(client):
    h = headers(client)
    for method, path, body in [
        ("get", "/api/v1/group-admission/mine", None),
        ("post", "/api/v1/group-admission/invites", {}),
        ("post", "/api/v1/group-admission/applications", {"code": "LEGACY"}),
        ("post", "/api/v1/group-admission/applications/1/review", {"approve": True}),
        ("post", "/api/v1/admin/group-members/1", {}),
        ("delete", "/api/v1/admin/group-members/1", None),
    ]:
        r = getattr(client, method)(
            path, headers=h, **({"json": body} if body is not None else {})
        )
        assert r.status_code == 410, r.text
    with client.app.state.session_factory() as db:
        assert db.scalars(select(StudyGroupMember)).all() == []
        assert len(db.scalars(select(RoomMember)).all()) == 1
