from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "eduflow",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.learning", "app.tasks.notifications"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=True,
    beat_schedule={
        "flush-learning-progress-every-minute": {
            "task": "learning.flush_progress",
            "schedule": 60.0,
        },
        "send-exam-reminders-every-five-minutes": {
            "task": "notifications.send_exam_reminders",
            "schedule": 300.0,
        },
    },
)
