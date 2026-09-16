"""baseline schema

The alembic/versions directory shipped empty, so there was no migration history
at all - the app only ever worked via Base.metadata.create_all() on startup
(main.py), which is fine for local dev but leaves production deployments with
no repeatable/auditable way to create or upgrade the schema.

This baseline creates every table currently defined by the SQLAlchemy models
(idempotently - checkfirst=True - so running it against a dev DB that was
already created via create_all() is safe and a no-op). Revision 0002 then adds
the new risk_factors/explanation columns on top of this baseline.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-09-08

"""
from alembic import op

from app.db.database import Base
import app.models  # noqa: F401  (registers every model on Base.metadata)

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    # Intentionally a no-op: this baseline represents "whatever schema already
    # exists"; dropping every table here would be destructive for a database
    # that was created via create_all() before Alembic was introduced.
    pass
