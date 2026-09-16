"""
Example background tasks. Wire these up once celery_app is activated.
"""
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.process_csv_import")
def process_csv_import(file_bytes: bytes) -> dict:
    """
    Placeholder for large-CSV background processing.
    In production, read file_bytes, open a DB session, and call
    app.services.transaction_service.import_csv, then persist/notify
    the summary (e.g. via a stored job record or websocket push).
    """
    from app.db.database import SessionLocal
    from app.services.transaction_service import import_csv

    db = SessionLocal()
    try:
        summary = import_csv(db, file_bytes)
        return summary.model_dump()
    finally:
        db.close()
