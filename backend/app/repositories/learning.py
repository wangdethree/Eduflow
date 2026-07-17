from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.course import CourseLesson
from app.models.learning import CourseEnrollment, CourseFavorite, EnrollmentStatus, LessonProgress


class LearningRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_enrollment(self, user_id: int, course_id: int) -> CourseEnrollment | None:
        return await self.session.scalar(
            select(CourseEnrollment).where(
                CourseEnrollment.user_id == user_id,
                CourseEnrollment.course_id == course_id,
            )
        )

    async def get_active_enrollment(
        self, user_id: int, course_id: int
    ) -> CourseEnrollment | None:
        return await self.session.scalar(
            select(CourseEnrollment).where(
                CourseEnrollment.user_id == user_id,
                CourseEnrollment.course_id == course_id,
                CourseEnrollment.status.in_([EnrollmentStatus.ACTIVE, EnrollmentStatus.COMPLETED]),
            )
        )

    async def list_enrollments(self, user_id: int) -> list[CourseEnrollment]:
        return list(
            await self.session.scalars(
                select(CourseEnrollment)
                .where(CourseEnrollment.user_id == user_id)
                .order_by(CourseEnrollment.updated_at.desc())
            )
        )

    async def get_lesson(self, lesson_id: int) -> CourseLesson | None:
        return await self.session.scalar(
            select(CourseLesson)
            .where(CourseLesson.id == lesson_id)
            .options(joinedload(CourseLesson.chapter))
        )

    async def get_progress(self, user_id: int, lesson_id: int) -> LessonProgress | None:
        return await self.session.scalar(
            select(LessonProgress).where(
                LessonProgress.user_id == user_id, LessonProgress.lesson_id == lesson_id
            )
        )

    async def get_favorite(self, user_id: int, course_id: int) -> CourseFavorite | None:
        return await self.session.scalar(
            select(CourseFavorite).where(
                CourseFavorite.user_id == user_id, CourseFavorite.course_id == course_id
            )
        )

    async def course_completion(self, user_id: int, course_id: int) -> tuple[int, int]:
        total = await self.session.scalar(
            select(func.count(CourseLesson.id))
            .join(CourseLesson.chapter)
            .where(
                CourseLesson.is_required.is_(True),
                CourseLesson.chapter.has(course_id=course_id),
            )
        ) or 0
        completed = await self.session.scalar(
            select(func.count(LessonProgress.id)).where(
                LessonProgress.user_id == user_id,
                LessonProgress.course_id == course_id,
                LessonProgress.is_completed.is_(True),
            )
        ) or 0
        return completed, total
