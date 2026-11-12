from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text
from app.config import Settings
from app.database import make_database
from app.models import User
from app.seed import seed
from app.time import utcnow


def test_upgrade_legacy_null_mask_preserves_ciphertext_and_schema_matches(
    tmp_path, monkeypatch
):
    server = Path(__file__).resolve().parents[2]
    url = "sqlite:///" + (tmp_path / "migration.sqlite").as_posix()
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(server / "alembic.ini"))
    config.set_main_option("script_location", str(server / "alembic"))
    command.upgrade(config, "head")
    engine, sessions = make_database(url)
    with sessions() as db:
        seed(
            db,
            Settings(
                _env_file=None,
                database_url=url,
                admin_email="migration@test.com",
                admin_password="Migration2028",
            ),
            echo=lambda *args: None,
        )
        db.commit()
    command.downgrade(config, "d7f9b1c3e5a7")
    with sessions() as db:
        uid = db.scalar(select(User.id).where(User.email == "migration@test.com"))
        db.execute(
            text(
                "INSERT INTO user_ai_keys (user_id,provider,base_url,model,key_cipher,key_mask,updated_at) "
                "VALUES (:uid,:provider,:base,:model,:cipher,NULL,:now)"
            ),
            {
                "uid": uid,
                "provider": "deepseek",
                "base": "https://api.deepseek.com/v1",
                "model": "test-model",
                "cipher": "unchanged-ciphertext-fixture",
                "now": utcnow(),
            },
        )
        db.execute(text("UPDATE users SET privacy_mode=1 WHERE id=:uid"), {"uid": uid})
        db.commit()
    command.upgrade(config, "head")
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT key_mask,key_cipher FROM user_ai_keys WHERE user_id=:uid"),
            {"uid": uid},
        ).one()
        assert row == ("", "unchanged-ciphertext-fixture")
        assert (
            connection.execute(
                text("SELECT is_private_mode FROM users WHERE id=:uid"), {"uid": uid}
            ).scalar()
            == 1
        )
        assert connection.execute(text("PRAGMA foreign_key_check")).all() == []
    command.check(config)
    command.downgrade(config, "d7f9b1c3e5a7")
    command.upgrade(config, "head")
    command.check(config)
    engine.dispose()


def test_room_upgrade_preserves_history_and_members_but_requires_new_sharing_consent(
    tmp_path, monkeypatch
):
    from app.models import Room, RoomMember, LearningRecord, SessionFact
    import json

    server = Path(__file__).resolve().parents[2]
    url = "sqlite:///" + (tmp_path / "room-migration.sqlite").as_posix()
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(server / "alembic.ini"))
    config.set_main_option("script_location", str(server / "alembic"))
    command.upgrade(config, "head")
    engine, sessions = make_database(url)
    with sessions() as db:
        seed(
            db,
            Settings(
                _env_file=None,
                database_url=url,
                admin_email="migration@test.com",
                admin_password="Migration2028",
            ),
            echo=lambda *args: None,
        )
        assert db.scalars(select(Room)).all() == []
        r = Room(
            name="既有多人房",
            code="OLD001",
            owner_id=1,
            capacity=4,
            visibility="public",
        )
        db.add(r)
        db.flush()
        db.add(
            RoomMember(room_id=r.id, user_id=1, role="owner", sharing_confirmed=True)
        )
        db.add(
            LearningRecord(
                user_id=1,
                id="history",
                body=json.dumps(
                    {"type": "task", "id": "history", "title": "既有学习记录"}
                ),
            )
        )
        db.add(
            LearningRecord(
                user_id=1,
                id="validated",
                body=json.dumps(
                    {
                        "id": "validated",
                        "type": "session",
                        "startedAt": 1767225600000,
                        "endedAt": 1767225660000,
                        "actualSec": 60,
                        "mode": "timer",
                        "plannedMin": 1,
                        "status": "done",
                        "date": "2026-01-01",
                    }
                ),
            )
        )
        db.add(
            SessionFact(
                user_id=1,
                record_id="validated",
                started_at=1767225600000,
                ended_at=1767225660000,
                actual_sec=60,
                study_date="2026-01-01",
            )
        )
        db.commit()
    command.downgrade(config, "c2e4f6a8b0d2")
    command.upgrade(config, "head")
    with sessions() as db:
        assert db.scalar(select(Room)).capacity == 50
        assert db.scalar(select(Room)).code != "OLD001"
        assert (
            db.scalar(select(Room)).visibility == "public"
        )  # Existing visibility is preserved.
        assert db.scalar(select(RoomMember)).sharing_confirmed is False
        assert (
            json.loads(db.get(LearningRecord, (1, "history")).body)["title"]
            == "既有学习记录"
        )
        assert db.get(SessionFact, (1, "validated")).actual_sec == 60
        assert db.execute(text("PRAGMA foreign_key_check")).all() == []
    command.check(config)
    engine.dispose()
