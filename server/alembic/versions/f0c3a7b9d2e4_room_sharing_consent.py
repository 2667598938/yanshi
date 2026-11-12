"""Friend rooms replace the global group; legacy sharing remains opt-in."""

from alembic import op
import sqlalchemy as sa

revision = "f0c3a7b9d2e4"
down_revision = "c2e4f6a8b0d2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "room_members",
        sa.Column(
            "sharing_confirmed", sa.Boolean(), server_default="0", nullable=False
        ),
    )
    op.add_column(
        "room_join_applies",
        sa.Column("accept_sharing", sa.Boolean(), server_default="0", nullable=False),
    )
    with op.batch_alter_table("rooms") as batch:
        batch.alter_column(
            "capacity",
            existing_type=sa.Integer(),
            server_default="0",
            existing_nullable=False,
        )
        batch.alter_column(
            "visibility",
            existing_type=sa.String(12),
            server_default="private",
            existing_nullable=False,
        )
    op.execute("UPDATE rooms SET capacity=0")
    # Old auto-enrolled room members may have seen old codes. Re-invitation must
    # use a fresh owner-only secret; no old bearer token grants new sharing.
    import secrets
    import string

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, code, dissolved_at FROM rooms")).all()
    taken = {row.code for row in rows}
    alphabet = string.ascii_uppercase + string.digits
    for row in rows:
        if row.dissolved_at is not None:
            continue
        while True:
            code = "".join(secrets.choice(alphabet) for _ in range(6))
            if code not in taken:
                break
        taken.add(code)
        bind.execute(
            sa.text("UPDATE rooms SET code=:code WHERE id=:id"),
            {"code": code, "id": row.id},
        )


def downgrade():
    op.drop_column("room_join_applies", "accept_sharing")
    op.drop_column("room_members", "sharing_confirmed")
    with op.batch_alter_table("rooms") as batch:
        batch.alter_column(
            "capacity",
            existing_type=sa.Integer(),
            server_default="4",
            existing_nullable=False,
        )
        batch.alter_column(
            "visibility",
            existing_type=sa.String(12),
            server_default="public",
            existing_nullable=False,
        )
    # Retain unlimited capacities/data; downgrade must not evict members.
