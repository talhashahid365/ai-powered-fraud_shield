"""add triggered_rules column to transactions

The Risk Decision Engine's rule_score is derived from evaluate_rules(), which also
returns the list of rule *names* that fired. That list was only ever held in memory
for the duration of the original risk-check request and was never persisted, so
GET /api/transactions/{id}/risk, GET /api/risk/{id}, and POST /api/risk-check all
hardcoded triggered_rules=[] on every read after transaction creation - silently
dropping the "Rules" contribution to the combined risk score on every subsequent read.
This column persists that list the same way risk_factors/explanation already are.

Revision ID: 0003_transaction_triggered_rules
Revises: 0002_transaction_explanation_fields
Create Date: 2026-09-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0003_transaction_triggered_rules"
down_revision = "0002_transaction_explanation_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.add_column(sa.Column("triggered_rules", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("transactions") as batch_op:
        batch_op.drop_column("triggered_rules")
