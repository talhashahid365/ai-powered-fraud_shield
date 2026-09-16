"""add api_keys table

Backs the External Business API (POST /api/transactions, POST /api/risk-check,
GET /api/transactions/{id}, GET /api/risk/{transaction_id}, POST
/api/alerts/{id}/review): external e-commerce/payment systems authenticate with
an `X-API-Key` header instead of a dashboard user login. Only a bcrypt hash of
the key is stored; see app.models.api_key.ApiKey and
app.services.api_key_service for details.

Revision ID: 0007_api_keys_table
Revises: 0006_feedback_unique_alert
Create Date: 2026-09-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0007_api_keys_table"
down_revision = "0006_feedback_unique_alert"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "api_keys" in inspector.get_table_names():
        # Fresh databases created via Base.metadata.create_all() already have this
        # table since ApiKey is now registered in app.models.
        return

    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("business_name", sa.String(120), nullable=False),
        sa.Column("key_prefix", sa.String(16), nullable=False),
        sa.Column("key_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_api_keys_key_prefix", "api_keys", ["key_prefix"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_api_keys_key_prefix", table_name="api_keys")
    op.drop_table("api_keys")
