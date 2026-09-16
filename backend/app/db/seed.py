"""
Seed the database with an initial admin user and default fraud rules.

Run with:
    python -m app.db.seed
"""
from app.db.database import Base, SessionLocal, engine
from app.models.enums import UserRole
from app.models.rule import Rule
from app.models.user import User
from app.core.security import hash_password
from app.ai.rules_engine import DEFAULT_RULES
import app.models  # noqa: F401


def run():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.email == "admin@fraudshield.ai").first():
            admin = User(
                name="Admin User",
                email="admin@fraudshield.ai",
                password_hash=hash_password("ChangeMe123!"),
                role=UserRole.ADMIN,
            )
            db.add(admin)
            print("Created default admin: admin@fraudshield.ai / ChangeMe123!  (change this immediately)")

        if not db.query(User).filter(User.email == "analyst@fraudshield.ai").first():
            analyst = User(
                name="Analyst User",
                email="analyst@fraudshield.ai",
                password_hash=hash_password("ChangeMe123!"),
                role=UserRole.ANALYST,
            )
            db.add(analyst)

        if not db.query(User).filter(User.email == "manager@fraudshield.ai").first():
            manager = User(
                name="Business Manager",
                email="manager@fraudshield.ai",
                password_hash=hash_password("ChangeMe123!"),
                role=UserRole.BUSINESS_MANAGER,
            )
            db.add(manager)

        if db.query(Rule).count() == 0:
            for rule_def in DEFAULT_RULES:
                db.add(Rule(**rule_def))
            print(f"Seeded {len(DEFAULT_RULES)} default rules.")

        db.commit()
        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    run()
