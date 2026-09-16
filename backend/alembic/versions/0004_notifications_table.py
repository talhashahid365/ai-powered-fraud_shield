"""add notifications table

Fraud Alerts spec requires that the relevant user be notified when a
high-risk alert is created. This adds the notifications table backing that:
one row per (user, alert), created alongside the alert for whichever
analyst it gets auto-assigned to (see app.services.alert_service).

Revision ID: 0004_notifications_table
Revises: 0003_transaction_triggered_rules
Create Date: 2026-09-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0004_notifications_table"
down_revision = "0003_transaction_triggered_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "notifications" in inspector.get_table_names():
        # Fresh databases created via Base.metadata.create_all() (main.py's dev
        # startup path, or 0001_baseline for a brand-new DB) already have this
        # table since Notification is now registered in app.models. Only
        # pre-existing databases that ran 0001-0003 before this revision need
        # the table created here.
        return

    op.create_table(
        "notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("alert_id", sa.String(36), sa.ForeignKey("alerts.id"), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")
