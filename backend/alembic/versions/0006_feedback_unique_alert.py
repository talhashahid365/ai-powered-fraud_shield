"""feedback.alert_id unique (one label per alert)

Feedback rows are used as ground-truth labels for training/evaluating the
fraud model (see ml/training/export_feedback_dataset.py). Allowing more than
one Feedback row per alert would let an alert end up with contradictory
labels (e.g. both CONFIRMED_FRAUD and FALSE_POSITIVE), silently corrupting
that training data. This enforces one feedback record per alert at the DB
level, matching the application-level check added to
app.services.alert_service.record_feedback.

Revision ID: 0006_feedback_unique_alert
Revises: 0005_customer_risk_profile_fields
Create Date: 2026-09-08

"""
from alembic import op
import sqlalchemy as sa

revision = "0006_feedback_unique_alert"
down_revision = "0005_customer_risk_profile_fields"
branch_labels = None
depends_on = None

CONSTRAINT_NAME = "uq_feedback_alert_id"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_uniques = {uc["name"] for uc in inspector.get_unique_constraints("feedback")}
    if CONSTRAINT_NAME in existing_uniques:
        # Fresh DBs created via Base.metadata.create_all() (Feedback.alert_id is now
        # declared unique=True) already have this; only pre-0006 databases need it added.
        return

    # Guard against pre-existing duplicate feedback rows blocking the constraint: keep
    # only the most recent feedback per alert. This should be a no-op on any database that
    # was only ever written through the single-feedback API, but protects the upgrade from
    # failing on data that predates this constraint.
    op.execute(
        """
        DELETE FROM feedback
        WHERE id NOT IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY alert_id ORDER BY created_at DESC
                ) AS rn
                FROM feedback
            ) ranked
            WHERE rn = 1
        )
        """
    )

    with op.batch_alter_table("feedback") as batch_op:
        batch_op.create_unique_constraint(CONSTRAINT_NAME, ["alert_id"])


def downgrade() -> None:
    with op.batch_alter_table("feedback") as batch_op:
        batch_op.drop_constraint(CONSTRAINT_NAME, type_="unique")
