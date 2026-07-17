from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.course import Course, CourseCategory, CourseChapter, CourseStatus


class CourseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_course(self, course_id: int) -> Course | None:
        return await self.session.scalar(
            select(Course)
            .where(Course.id == course_id, Course.deleted_at.is_(None))
            .options(selectinload(Course.chapters).selectinload(CourseChapter.lessons))
        )

    async def get_public_course(self, course_id: int) -> Course | None:
        return await self.session.scalar(
            select(Course)
            .where(
                Course.id == course_id,
                Course.status == CourseStatus.PUBLISHED,
                Course.deleted_at.is_(None),
            )
            .options(selectinload(Course.chapters).selectinload(CourseChapter.lessons))
        )

    async def list_public(
        self, page: int, page_size: int, keyword: str | None, category_id: int | None
    ) -> tuple[list[Course], int]:
        filters = [Course.status == CourseStatus.PUBLISHED, Course.deleted_at.is_(None)]
        if keyword:
            filters.append(
                or_(Course.title.contains(keyword), Course.description.contains(keyword))
            )
        if category_id:
            filters.append(Course.category_id == category_id)
        total = await self.session.scalar(select(func.count(Course.id)).where(*filters)) or 0
        statement = (
            select(Course)
            .where(*filters)
            .order_by(Course.published_at.desc(), Course.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .options(selectinload(Course.chapters).selectinload(CourseChapter.lessons))
        )
        return list((await self.session.scalars(statement)).unique()), total

    async def list_teacher_courses(self, teacher_id: int) -> list[Course]:
        result = await self.session.scalars(
            select(Course)
            .where(Course.teacher_id == teacher_id, Course.deleted_at.is_(None))
            .order_by(Course.updated_at.desc())
            .options(selectinload(Course.chapters).selectinload(CourseChapter.lessons))
        )
        return list(result.unique())

    async def list_categories(self) -> list[CourseCategory]:
        return list(
            await self.session.scalars(
                select(CourseCategory)
                .where(CourseCategory.is_enabled.is_(True))
                .order_by(CourseCategory.sort_order, CourseCategory.id)
            )
        )

