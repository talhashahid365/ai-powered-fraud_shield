"""add risk_factors / explanation columns to transactions

Persists the AI explanation feature's output (the structured risk_factors
list and the generated human-readable explanation) onto the transaction row,
so it survives past the initial risk check instead of only existing for the
lifetime of that one request.

Revision ID: 0002_transaction_explanation_fields
Revises: 0001_baseline
Create Date: 2026-09-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0002_transaction_explanation_fields"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.add_column(sa.Column("risk_factors", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("explanation", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.drop_column("explanation")
        batch_op.drop_column("risk_factors")
