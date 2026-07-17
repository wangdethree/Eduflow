import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.exam import Exam
from app.models.learning import CourseEnrollment
from app.models.notification import Notification, NotificationType, UserNotification
from app.tasks.celery_app import celery_app


async def create_exam_reminders() -> int:
    now = datetime.now(UTC)
    upcoming = now + timedelta(minutes=5)
    created = 0
    async with AsyncSessionLocal() as session:
        exams = list(
            await session.scalars(
                select(Exam).where(
                    Exam.is_published.is_(True),
                    Exam.starts_at > now,
                    Exam.starts_at <= upcoming,
                )
            )
        )
        for exam in exams:
            source_key = f"exam_start_reminder:{exam.id}"
            exists = await session.scalar(
                select(Notification.id).where(Notification.source_key == source_key)
            )
            if exists:
                continue
            user_ids = list(
                await session.scalars(
                    select(CourseEnrollment.user_id).where(
                        CourseEnrollment.course_id == exam.course_id,
                        CourseEnrollment.status.in_(["active", "completed"]),
                    )
                )
            )
            if not user_ids:
                continue
            notification = Notification(
                title=f"考试即将开始：{exam.title}",
                content="考试将在 5 分钟内开始，请提前进入考试页面。",
                notification_type=NotificationType.EXAM,
                source_key=source_key,
            )
            notification.recipients = [
                UserNotification(user_id=user_id) for user_id in user_ids
            ]
            session.add(notification)
            created += 1
        await session.commit()
    return created


@celery_app.task(name="notifications.send_exam_reminders")
def send_exam_reminders() -> int:
    return asyncio.run(create_exam_reminders())

