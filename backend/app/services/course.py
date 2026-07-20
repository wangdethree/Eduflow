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
from app.models.rbac import OperationLog
from app.models.user import User
from app.repositories.course import CourseRepository
from app.schemas.course import (
    CategoryCreate,
    ChapterCreate,
    ChapterUpdate,
    CourseCreate,
    CourseUpdate,
    LessonCreate,
    LessonUpdate,
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

    async def get_owned_course(self, course_id: int) -> Course:
        return await self._owned_course(course_id)

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

    async def update_chapter(
        self, course_id: int, chapter_id: int, payload: ChapterUpdate
    ) -> CourseChapter:
        course = await self._owned_editable_course(course_id)
        chapter = await self._course_chapter(course.id, chapter_id)
        values = payload.model_dump(exclude_unset=True)
        target_order = values.pop("sort_order", None)
        for field, value in values.items():
            setattr(chapter, field, value)
        if target_order is not None:
            await self._move_chapter(course.id, chapter, target_order)
        await self.session.commit()
        await self.session.refresh(chapter, ["lessons"])
        return chapter

    async def delete_chapter(self, course_id: int, chapter_id: int) -> None:
        course = await self._owned_editable_course(course_id)
        chapter = await self._course_chapter(course.id, chapter_id)
        course.total_duration = max(
            0, course.total_duration - sum(lesson.duration_seconds for lesson in chapter.lessons)
        )
        await self.session.delete(chapter)
        await self.session.flush()
        await self._normalize_chapter_orders(course.id)
        await self.session.commit()

    async def update_lesson(
        self,
        course_id: int,
        chapter_id: int,
        lesson_id: int,
        payload: LessonUpdate,
    ) -> CourseLesson:
        course = await self._owned_editable_course(course_id)
        chapter = await self._course_chapter(course.id, chapter_id)
        lesson = await self._chapter_lesson(chapter.id, lesson_id)
        previous_duration = lesson.duration_seconds
        values = payload.model_dump(exclude_unset=True)
        target_order = values.pop("sort_order", None)
        for field, value in values.items():
            setattr(lesson, field, value)
        if target_order is not None:
            await self._move_lesson(chapter.id, lesson, target_order)
        course.total_duration = max(
            0, course.total_duration - previous_duration + lesson.duration_seconds
        )
        await self.session.commit()
        await self.session.refresh(lesson)
        return lesson

    async def delete_lesson(
        self, course_id: int, chapter_id: int, lesson_id: int
    ) -> None:
        course = await self._owned_editable_course(course_id)
        chapter = await self._course_chapter(course.id, chapter_id)
        lesson = await self._chapter_lesson(chapter.id, lesson_id)
        course.total_duration = max(0, course.total_duration - lesson.duration_seconds)
        await self.session.delete(lesson)
        await self.session.flush()
        await self._normalize_lesson_orders(chapter.id)
        await self.session.commit()

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
        self.session.add(
            OperationLog(
                user_id=self.current_user.id,
                action="course:audit",
                resource_type="course",
                resource_id=str(course.id),
                detail=f"approved={approved}; opinion={opinion}",
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

    async def _course_chapter(self, course_id: int, chapter_id: int) -> CourseChapter:
        chapter = await self.session.get(CourseChapter, chapter_id)
        if chapter is None or chapter.course_id != course_id:
            raise ResourceNotFoundException("章节不存在", 40011)
        return chapter

    async def _chapter_lesson(self, chapter_id: int, lesson_id: int) -> CourseLesson:
        lesson = await self.session.get(CourseLesson, lesson_id)
        if lesson is None or lesson.chapter_id != chapter_id:
            raise ResourceNotFoundException("课时不存在", 40012)
        return lesson

    async def _move_chapter(
        self, course_id: int, target: CourseChapter, target_order: int
    ) -> None:
        chapters = list(
            await self.session.scalars(
                select(CourseChapter)
                .where(CourseChapter.course_id == course_id)
                .order_by(CourseChapter.sort_order)
            )
        )
        chapters.remove(target)
        chapters.insert(min(target_order - 1, len(chapters)), target)
        await self._replace_orders(chapters)

    async def _move_lesson(
        self, chapter_id: int, target: CourseLesson, target_order: int
    ) -> None:
        lessons = list(
            await self.session.scalars(
                select(CourseLesson)
                .where(CourseLesson.chapter_id == chapter_id)
                .order_by(CourseLesson.sort_order)
            )
        )
        lessons.remove(target)
        lessons.insert(min(target_order - 1, len(lessons)), target)
        await self._replace_orders(lessons)

    async def _normalize_chapter_orders(self, course_id: int) -> None:
        chapters = list(
            await self.session.scalars(
                select(CourseChapter)
                .where(CourseChapter.course_id == course_id)
                .order_by(CourseChapter.sort_order)
            )
        )
        await self._replace_orders(chapters)

    async def _normalize_lesson_orders(self, chapter_id: int) -> None:
        lessons = list(
            await self.session.scalars(
                select(CourseLesson)
                .where(CourseLesson.chapter_id == chapter_id)
                .order_by(CourseLesson.sort_order)
            )
        )
        await self._replace_orders(lessons)

    async def _replace_orders(self, items: list[CourseChapter] | list[CourseLesson]) -> None:
        # 先使用负数临时序号，避免 MySQL 唯一索引在交换顺序时冲突。
        for index, item in enumerate(items, start=1):
            item.sort_order = -index
        await self.session.flush()
        for index, item in enumerate(items, start=1):
            item.sort_order = index

    async def _reload(self, course_id: int) -> Course:
        course = await self.repository.get_course(course_id)
        if course is None:
            raise ResourceNotFoundException("课程不存在", 40001)
        return course
