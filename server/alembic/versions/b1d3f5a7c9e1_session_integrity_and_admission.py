"""Validated session facts, timer leases and independent group admission."""

from alembic import op
import sqlalchemy as sa
import json
from datetime import datetime, timezone, timedelta

revision = "b1d3f5a7c9e1"
down_revision = "a0c2e4f6b8d0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("invite_codes") as b:
        b.add_column(
            sa.Column(
                "kind", sa.String(20), nullable=False, server_default="register_only"
            )
        )
    op.execute("UPDATE invite_codes SET kind='vip_only' WHERE vip_days>0")
    op.create_table(
        "session_facts",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("record_id", sa.String(500), primary_key=True),
        sa.Column("started_at", sa.BigInteger(), nullable=False),
        sa.Column("ended_at", sa.BigInteger(), nullable=False),
        sa.Column("actual_sec", sa.Integer(), nullable=False),
        sa.Column("study_date", sa.String(10), nullable=False),
        sa.Column("conflict", sa.Boolean(), nullable=False, server_default="0"),
        sa.CheckConstraint("started_at >= 1767225600000", name="ck_session_start"),
        sa.CheckConstraint("ended_at >= started_at", name="ck_session_interval"),
        sa.CheckConstraint(
            "actual_sec >= 0 AND actual_sec <= 10800", name="ck_session_duration"
        ),
    )
    op.create_table(
        "timer_leases",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("session_id", sa.String(100), nullable=False),
        sa.Column("device_id", sa.String(80), nullable=False),
        sa.Column("started_at", sa.BigInteger(), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "group_invites",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "group_id", sa.Integer(), sa.ForeignKey("study_groups.id"), nullable=False
        ),
        sa.Column("token_hash", sa.String(64), unique=True, nullable=False),
        sa.Column(
            "created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
        ),
        sa.Column("target_user_id", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime()),
        sa.Column("consumed_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "group_applies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "group_id", sa.Integer(), sa.ForeignKey("study_groups.id"), nullable=False
        ),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "invite_id", sa.Integer(), sa.ForeignKey("group_invites.id"), nullable=False
        ),
        sa.Column("pending_key", sa.String(100), unique=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(300), nullable=False),
        sa.Column("remark", sa.String(300), nullable=False),
        sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column("reviewed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    # Keep raw history unchanged. Only valid intervals enter the constrained statistics ledger.
    bind = op.get_bind()
    rows = (
        bind.execute(
            sa.text(
                "SELECT user_id,id,body,revision FROM learning_records WHERE deleted=0"
            )
        )
        .mappings()
        .all()
    )
    facts = []
    for row in rows:
        try:
            r = json.loads(row["body"])
            if r.get("type") != "session":
                continue
            a = int(r["startedAt"])
            b = int(r["endedAt"])
            pause = int(r.get("pauseAccum", 0))
            if (
                a < 1767225600000
                or b < a
                or pause < 0
                or pause > b - a
                or r.get("status") not in ("done", "quit")
                or r.get("mode") not in ("timer", "stopwatch")
            ):
                continue
            seconds = min(max(0, (b - a - pause) // 1000), 10800)
            if r["mode"] == "timer" and r["status"] == "done":
                plan = int(r.get("plannedMin", 0))
                if not 1 <= plan <= 180:
                    continue
                seconds = min(seconds, plan * 60)
            if seconds < (b - a - pause) // 1000 and (
                r["status"] == "done" or r.get("end_reason") == "timeout"
            ):
                b = a + pause + seconds * 1000
            facts.append(
                dict(
                    user_id=row["user_id"],
                    record_id=row["id"],
                    started_at=a,
                    ended_at=b,
                    actual_sec=seconds,
                    study_date=datetime.fromtimestamp(
                        a / 1000, timezone(timedelta(hours=8))
                    )
                    .date()
                    .isoformat(),
                    conflict=False,
                )
            )
        except (ValueError, TypeError, KeyError, OverflowError, OSError):
            continue
    for uid in {f["user_id"] for f in facts}:
        component = []
        end = 0

        def flag():
            if len(component) > 1:
                for f in component:
                    f["conflict"] = True

        for f in sorted(
            [f for f in facts if f["user_id"] == uid and f["actual_sec"] > 0],
            key=lambda f: f["started_at"],
        ):
            if component and f["started_at"] >= end:
                flag()
                component = []
                end = 0
            component.append(f)
            end = max(end, f["ended_at"])
        flag()
    table = sa.table(
        "session_facts",
        *[
            sa.column(k)
            for k in (
                "user_id",
                "record_id",
                "started_at",
                "ended_at",
                "actual_sec",
                "study_date",
                "conflict",
            )
        ],
    )
    if facts:
        bind.execute(table.insert(), facts)
    # Revision bumps notify older clients that projected date/duration/conflict metadata changed.
    for row in rows:
        try:
            is_session = json.loads(row["body"]).get("type") == "session"
        except (ValueError, TypeError):
            is_session = False
        if is_session:
            bind.execute(
                sa.text(
                    "UPDATE learning_records SET revision=revision+1 WHERE user_id=:u AND id=:i"
                ),
                {"u": row["user_id"], "i": row["id"]},
            )
            bind.execute(
                sa.text(
                    "INSERT INTO learning_changes(user_id,record_id,revision) VALUES(:u,:i,:r)"
                ),
                {"u": row["user_id"], "i": row["id"], "r": row["revision"] + 1},
            )


def downgrade():
    with op.batch_alter_table("invite_codes") as b:
        b.drop_column("kind")
    for table in ("group_applies", "group_invites", "timer_leases", "session_facts"):
        op.drop_table(table)
