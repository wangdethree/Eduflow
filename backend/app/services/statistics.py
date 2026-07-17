from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import PermissionDeniedException, ResourceNotFoundException
from app.models.course import Course, CourseChapter, CourseLesson, CourseStatus
from app.models.exam import AttemptStatus, Exam, ExamAttempt
from app.models.learning import CourseEnrollment, EnrollmentStatus, LessonProgress
from app.models.user import User, UserStatus


class StatisticsService:
    def __init__(self, session: AsyncSession, current_user: User) -> None:
        self.session = session
        self.current_user = current_user

    async def teacher_course_statistics(self, course_id: int) -> dict:
        course = await self.session.get(Course, course_id)
        if course is None:
            raise ResourceNotFoundException("课程不存在", 40001)
        if course.teacher_id != self.current_user.id:
            raise PermissionDeniedException("只能查看自己课程的统计数据")
        enrollment_row = (
            await self.session.execute(
                select(
                    func.count(CourseEnrollment.id),
                    func.sum(
                        case(
                            (CourseEnrollment.status == EnrollmentStatus.COMPLETED, 1), else_=0
                        )
                    ),
                    func.avg(CourseEnrollment.progress),
                ).where(
                    CourseEnrollment.course_id == course_id,
                    CourseEnrollment.status != EnrollmentStatus.WITHDRAWN,
                )
            )
        ).one()
        student_count = int(enrollment_row[0] or 0)
        completed_count = int(enrollment_row[1] or 0)
        average_progress = round(float(enrollment_row[2] or 0), 2)
        total_learning = await self.session.scalar(
            select(func.sum(LessonProgress.learned_seconds)).where(
                LessonProgress.course_id == course_id
            )
        ) or 0
        chapters = list(
            await self.session.scalars(
                select(CourseChapter)
                .where(CourseChapter.course_id == course_id)
                .order_by(CourseChapter.sort_order)
            )
        )
        chapter_rates = []
        for chapter in chapters:
            lesson_ids = list(
                await self.session.scalars(
                    select(CourseLesson.id).where(
                        CourseLesson.chapter_id == chapter.id,
                        CourseLesson.is_required.is_(True),
                    )
                )
            )
            completed = 0
            if lesson_ids:
                completed = await self.session.scalar(
                    select(func.count(LessonProgress.id)).where(
                        LessonProgress.lesson_id.in_(lesson_ids),
                        LessonProgress.is_completed.is_(True),
                    )
                ) or 0
            denominator = student_count * len(lesson_ids)
            chapter_rates.append(
                {
                    "chapter_id": chapter.id,
                    "title": chapter.title,
                    "completion_rate": round(completed / denominator * 100, 2)
                    if denominator
                    else 0,
                }
            )
        exam_ids = list(
            await self.session.scalars(select(Exam.id).where(Exam.course_id == course_id))
        )
        attempts = []
        if exam_ids:
            attempts = list(
                await self.session.scalars(
                    select(ExamAttempt).where(
                        ExamAttempt.exam_id.in_(exam_ids),
                        ExamAttempt.status == AttemptStatus.GRADED,
                    )
                )
            )
        scores = [float(item.objective_score) for item in attempts]
        return {
            "course_id": course_id,
            "student_count": student_count,
            "completed_count": completed_count,
            "completion_rate": round(completed_count / student_count * 100, 2)
            if student_count
            else 0,
            "average_progress": average_progress,
            "average_learning_seconds": round(total_learning / student_count, 2)
            if student_count
            else 0,
            "chapter_completion": chapter_rates,
            "exam_participation_rate": round(len(attempts) / student_count * 100, 2)
            if student_count
            else 0,
            "exam_average_score": round(sum(scores) / len(scores), 2) if scores else 0,
            "score_distribution": self._score_distribution(scores),
        }

    async def admin_overview(self) -> dict:
        user_total = await self.session.scalar(select(func.count(User.id))) or 0
        active_users = await self.session.scalar(
            select(func.count(User.id)).where(User.status == UserStatus.ACTIVE)
        ) or 0
        course_total = await self.session.scalar(select(func.count(Course.id))) or 0
        published_courses = await self.session.scalar(
            select(func.count(Course.id)).where(Course.status == CourseStatus.PUBLISHED)
        ) or 0
        exam_total = await self.session.scalar(select(func.count(Exam.id))) or 0
        learning_seconds = await self.session.scalar(
            select(func.sum(LessonProgress.learned_seconds))
        ) or 0
        average_completion = await self.session.scalar(
            select(func.avg(CourseEnrollment.progress)).where(
                CourseEnrollment.status != EnrollmentStatus.WITHDRAWN
            )
        ) or 0
        return {
            "user_total": user_total,
            "active_users": active_users,
            "course_total": course_total,
            "published_courses": published_courses,
            "exam_total": exam_total,
            "learning_seconds": learning_seconds,
            "average_course_progress": round(float(average_completion), 2),
        }

    @staticmethod
    def _score_distribution(scores: list[float]) -> dict[str, int]:
        distribution = {"0-59": 0, "60-69": 0, "70-79": 0, "80-89": 0, "90-100": 0}
        for score in scores:
            if score < 60:
                distribution["0-59"] += 1
            elif score < 70:
                distribution["60-69"] += 1
            elif score < 80:
                distribution["70-79"] += 1
            elif score < 90:
                distribution["80-89"] += 1
            else:
                distribution["90-100"] += 1
        return distribution

