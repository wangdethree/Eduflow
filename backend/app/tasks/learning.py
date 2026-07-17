import asyncio
import json
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.redis import get_redis_client
from app.db.session import AsyncSessionLocal
from app.models.learning import CourseEnrollment, EnrollmentStatus, LessonProgress
from app.repositories.learning import LearningRepository
from app.services.learning import ProgressCache
from app.tasks.celery_app import celery_app


async def flush_progress_batch() -> int:
    """把 Redis 最新进度批量落库，并用比较删除避免覆盖并发新上报。"""

    redis = get_redis_client()
    cache = ProgressCache(redis)
    processed: list[tuple[str, str]] = []
    async with AsyncSessionLocal() as session:
        async for key in redis.scan_iter(match="learning:progress:*", count=200):
            raw = await redis.get(key)
            if not raw:
                continue
            data = json.loads(raw)
            progress = await session.scalar(
                select(LessonProgress).where(
                    LessonProgress.user_id == data["user_id"],
                    LessonProgress.lesson_id == data["lesson_id"],
                )
            )
            if progress is None:
                progress = LessonProgress(
                    user_id=data["user_id"],
                    course_id=data["course_id"],
                    lesson_id=data["lesson_id"],
                    last_learned_at=datetime.now(UTC),
                )
                session.add(progress)
            if data["updated_at"] >= (progress.client_updated_at or 0):
                progress.last_position = data["position"]
                progress.learned_seconds = data["learned_seconds"]
                progress.progress_percent = data["progress_percent"]
                progress.is_completed = data["is_completed"]
                progress.client_updated_at = data["updated_at"]
                progress.last_learned_at = datetime.now(UTC)
                if data["is_completed"] and progress.completed_at is None:
                    progress.completed_at = datetime.now(UTC)
            processed.append((key, raw))
        await session.flush()
        affected = {
            (json.loads(raw)["user_id"], json.loads(raw)["course_id"])
            for _, raw in processed
        }
        repository = LearningRepository(session)
        for user_id, course_id in affected:
            completed, total = await repository.course_completion(user_id, course_id)
            enrollment = await session.scalar(
                select(CourseEnrollment).where(
                    CourseEnrollment.user_id == user_id,
                    CourseEnrollment.course_id == course_id,
                )
            )
            if enrollment and total:
                enrollment.progress = round(completed / total * 100, 2)
                if completed == total:
                    enrollment.status = EnrollmentStatus.COMPLETED
                    enrollment.completed_at = datetime.now(UTC)
        await session.commit()
    for key, raw in processed:
        await cache.compare_delete(key, raw)
    return len(processed)


@celery_app.task(name="learning.flush_progress", bind=True, max_retries=3)
def flush_learning_progress(self) -> int:
    try:
        return asyncio.run(flush_progress_batch())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=10) from exc
