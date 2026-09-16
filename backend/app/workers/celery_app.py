"""
Celery application stub for background processing (large CSV imports,
risk analysis at scale, report generation, notifications).

To activate:
    pip install celery redis   (already in requirements.txt)
    celery -A app.workers.celery_app worker --loglevel=info

Then move heavy work (e.g. transaction_service.import_csv for large files)
into a @celery_app.task-decorated function and call `.delay(...)` from the
API route instead of running it inline.
"""
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "fraudshield",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.task_routes = {
    "app.workers.tasks.*": {"queue": "fraudshield"},
}
