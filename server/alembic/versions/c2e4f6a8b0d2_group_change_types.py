"""Typed group change cursor; no private-record tombstone IDs are exposed."""

from alembic import op
import sqlalchemy as sa

revision = "c2e4f6a8b0d2"
down_revision = "b1d3f5a7c9e1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "learning_changes", sa.Column("record_type", sa.String(24), nullable=True)
    )
    # Historical deletions have no body/type. New clients start with a full snapshot;
    # never guess a private tombstone's type from its identifier.
    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT user_id, id, body FROM learning_records WHERE deleted=0")
    ).all()
    import json

    for uid, rid, body in rows:
        kind = json.loads(body).get("type")
        connection.execute(
            sa.text(
                "UPDATE learning_changes SET record_type=:kind WHERE user_id=:uid AND record_id=:rid"
            ),
            {"kind": kind, "uid": uid, "rid": rid},
        )


def downgrade():
    op.drop_column("learning_changes", "record_type")
