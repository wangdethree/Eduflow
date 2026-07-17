from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictException,
    PermissionDeniedException,
    ResourceNotFoundException,
)
from app.models.course import (
    Course,
    CourseAudit,
    CourseCategory,
    CourseChapter,
    CourseLesson,
    CourseStatus,
)
from app.models.user import User
from app.repositories.course import CourseRepository
from app.schemas.course import (
    CategoryCreate,
    ChapterCreate,
    CourseCreate,
    CourseUpdate,
    LessonCreate,
)


class CourseService:
    def __init__(self, session: AsyncSession, current_user: User) -> None:
        self.session = session
        self.current_user = current_user
        self.repository = CourseRepository(session)

    async def create_category(self, payload: CategoryCreate) -> CourseCategory:
        if payload.parent_id and await self.session.get(CourseCategory, payload.parent_id) is None:
            raise ResourceNotFoundException("上级分类不存在", 40010)
        category = CourseCategory(**payload.model_dump())
        self.session.add(category)
        await self.session.commit()
        await self.session.refresh(category)
        return category

    async def create_course(self, payload: CourseCreate) -> Course:
        await self._ensure_category(payload.category_id)
        course = Course(**payload.model_dump(), teacher_id=self.current_user.id)
        self.session.add(course)
        await self.session.commit()
        return await self._reload(course.id)

    async def update_course(self, course_id: int, payload: CourseUpdate) -> Course:
        course = await self._owned_course(course_id)
        if course.status not in {CourseStatus.DRAFT, CourseStatus.REJECTED, CourseStatus.PUBLISHED}:
            raise ConflictException("当前课程状态不允许编辑", 40003)
        values = payload.model_dump(exclude_unset=True)
        if "category_id" in values:
            await self._ensure_category(values["category_id"])
        for field, value in values.items():
            setattr(course, field, value)
        if course.status == CourseStatus.PUBLISHED:
            course.status = CourseStatus.DRAFT
            course.published_at = None
        await self.session.commit()
        return await self._reload(course.id)

    async def delete_draft(self, course_id: int) -> None:
        course = await self._owned_course(course_id)
        if course.status not in {CourseStatus.DRAFT, CourseStatus.REJECTED}:
            raise ConflictException("只有草稿或已驳回课程可以删除", 40004)
        course.deleted_at = datetime.now(UTC)
        await self.session.commit()

    async def add_chapter(self, course_id: int, payload: ChapterCreate) -> CourseChapter:
        course = await self._owned_editable_course(course_id)
        maximum = await self.session.scalar(
            select(func.max(CourseChapter.sort_order)).where(CourseChapter.course_id == course.id)
        )
        chapter = CourseChapter(
            course_id=course.id, title=payload.title, sort_order=(maximum or 0) + 1
        )
        self.session.add(chapter)
        await self.session.commit()
        await self.session.refresh(chapter, ["lessons"])
        return chapter

    async def add_lesson(
        self, course_id: int, chapter_id: int, payload: LessonCreate
    ) -> CourseLesson:
        course = await self._owned_editable_course(course_id)
        chapter = await self.session.get(CourseChapter, chapter_id)
        if chapter is None or chapter.course_id != course.id:
            raise ResourceNotFoundException("章节不存在", 40011)
        maximum = await self.session.scalar(
            select(func.max(CourseLesson.sort_order)).where(CourseLesson.chapter_id == chapter_id)
        )
        lesson = CourseLesson(
            chapter_id=chapter_id, sort_order=(maximum or 0) + 1, **payload.model_dump()
        )
        self.session.add(lesson)
        course.total_duration += payload.duration_seconds
        await self.session.commit()
        await self.session.refresh(lesson)
        return lesson

    async def submit_review(self, course_id: int) -> Course:
        course = await self._owned_course(course_id)
        if course.status not in {CourseStatus.DRAFT, CourseStatus.REJECTED}:
            raise ConflictException("当前课程不能提交审核", 40005)
        if not course.chapters or not any(chapter.lessons for chapter in course.chapters):
            raise ConflictException("课程至少需要一个章节和一个课时", 40006)
        course.status = CourseStatus.PENDING_REVIEW
        await self.session.commit()
        return await self._reload(course.id)

    async def audit(self, course_id: int, approved: bool, opinion: str) -> Course:
        course = await self._reload(course_id)
        if course.status != CourseStatus.PENDING_REVIEW:
            raise ConflictException("课程不在待审核状态", 40007)
        if course.teacher_id == self.current_user.id:
            raise PermissionDeniedException("教师不能审核自己的课程")
        course.status = CourseStatus.PUBLISHED if approved else CourseStatus.REJECTED
        course.published_at = datetime.now(UTC) if approved else None
        self.session.add(
            CourseAudit(
                course_id=course.id,
                auditor_id=self.current_user.id,
                approved=approved,
                opinion=opinion,
                created_at=datetime.now(UTC),
            )
        )
        await self.session.commit()
        return await self._reload(course.id)

    async def offline(self, course_id: int) -> Course:
        course = await self._owned_course(course_id)
        if course.status != CourseStatus.PUBLISHED:
            raise ConflictException("只有已发布课程可以下架", 40008)
        course.status = CourseStatus.OFFLINE
        await self.session.commit()
        return await self._reload(course.id)

    async def _owned_course(self, course_id: int) -> Course:
        course = await self.repository.get_course(course_id)
        if course is None:
            raise ResourceNotFoundException("课程不存在", 40001)
        if course.teacher_id != self.current_user.id:
            raise PermissionDeniedException("无权操作其他教师的课程")
        return course

    async def _owned_editable_course(self, course_id: int) -> Course:
        course = await self._owned_course(course_id)
        if course.status not in {CourseStatus.DRAFT, CourseStatus.REJECTED}:
            raise ConflictException("当前状态不能修改章节或课时", 40003)
        return course

    async def _ensure_category(self, category_id: int) -> None:
        category = await self.session.get(CourseCategory, category_id)
        if category is None or not category.is_enabled:
            raise ResourceNotFoundException("课程分类不存在或已停用", 40010)

    async def _reload(self, course_id: int) -> Course:
        course = await self.repository.get_course(course_id)
        if course is None:
            raise ResourceNotFoundException("课程不存在", 40001)
        return course
