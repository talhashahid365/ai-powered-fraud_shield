"""
Import every model here so that Base.metadata knows about all tables
before Alembic autogenerate / create_all() is called.
"""
from app.models.user import User             # noqa: F401
from app.models.customer import Customer      # noqa: F401
from app.models.device import Device          # noqa: F401
from app.models.ip_address import IPAddress   # noqa: F401
from app.models.transaction import Transaction  # noqa: F401
from app.models.alert import Alert            # noqa: F401
from app.models.investigation_note import InvestigationNote  # noqa: F401
from app.models.rule import Rule              # noqa: F401
from app.models.feedback import Feedback      # noqa: F401
from app.models.audit_log import AuditLog     # noqa: F401
from app.models.notification import Notification  # noqa: F401
from app.models.api_key import ApiKey            # noqa: F401
