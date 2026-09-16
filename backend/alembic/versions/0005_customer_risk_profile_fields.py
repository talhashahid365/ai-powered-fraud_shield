"""add customer risk profile fields (devices_used, locations_used)

The Customer Risk Profile feature (risk level, risk score, total/suspicious
transactions, distinct devices used, distinct locations used, previous
fraud reports) needs devices_used and locations_used persisted on the
customer so the profile is a single indexed lookup instead of a full scan
of the transactions table on every read. Both columns are kept current by
services.customer_service.recompute_device_location_counts(), called after
every transaction.

Revision ID: 0005_customer_risk_profile_fields
Revises: 0004_notifications_table
Create Date: 2026-09-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0005_customer_risk_profile_fields"
down_revision = "0004_notifications_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {c["name"] for c in inspector.get_columns("customers")}

    if "devices_used" not in existing_columns:
        op.add_column("customers", sa.Column("devices_used", sa.Integer(), nullable=False, server_default="0"))
    if "locations_used" not in existing_columns:
        op.add_column("customers", sa.Column("locations_used", sa.Integer(), nullable=False, server_default="0"))

    # Backfill existing customers from their transaction history so the new
    # columns are correct immediately, not just from the next transaction on.
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE customers
            SET devices_used = (
                SELECT COUNT(DISTINCT t.device_id)
                FROM transactions t
                WHERE t.customer_id = customers.id AND t.device_id IS NOT NULL
            ),
            locations_used = (
                SELECT COUNT(DISTINCT t.location)
                FROM transactions t
                WHERE t.customer_id = customers.id AND t.location IS NOT NULL
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_column("customers", "locations_used")
    op.drop_column("customers", "devices_used")
