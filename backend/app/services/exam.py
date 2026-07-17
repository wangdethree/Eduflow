from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictException,
    PermissionDeniedException,
    ResourceNotFoundException,
)
from app.core.redis import get_redis_client
from app.models.course import Course, CourseStatus
from app.models.exam import (
    AttemptStatus,
    Exam,
    ExamAnswer,
    ExamAttempt,
    Paper,
    PaperQuestion,
    Question,
    QuestionOption,
    QuestionType,
    WrongQuestion,
)
from app.models.user import User
from app.repositories.exam import ExamRepository
from app.repositories.learning import LearningRepository
from app.schemas.exam import (
    ExamCreate,
    ExamSubmitRequest,
    PaperCreate,
    PaperQuestionCreate,
    QuestionCreate,
)

RELEASE_LOCK_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class ExamService:
    def __init__(self, session: AsyncSession, current_user: User) -> None:
        self.session = session
        self.current_user = current_user
        self.repository = ExamRepository(session)
        self.redis: Redis = get_redis_client()

    async def create_question(self, payload: QuestionCreate) -> Question:
        question = Question(
            teacher_id=self.current_user.id,
            stem=payload.stem,
            question_type=QuestionType(payload.question_type),
            correct_answers=sorted(set(payload.correct_answers)),
            analysis=payload.analysis,
            difficulty=payload.difficulty,
        )
        question.options = [
            QuestionOption(option_key=key, content=value)
            for key, value in sorted(payload.options.items())
        ]
        self.session.add(question)
        await self.session.commit()
        return await self._question(question.id)

    async def create_paper(self, payload: PaperCreate) -> Paper:
        paper = Paper(teacher_id=self.current_user.id, **payload.model_dump())
        self.session.add(paper)
        await self.session.commit()
        return await self._paper(paper.id)

    async def add_paper_question(
        self, paper_id: int, payload: PaperQuestionCreate
    ) -> Paper:
        paper = await self._paper(paper_id)
        if paper.teacher_id != self.current_user.id:
            raise PermissionDeniedException("无权编辑其他教师的试卷")
        question = await self._question(payload.question_id)
        if question.teacher_id != self.current_user.id:
            raise PermissionDeniedException("无权使用其他教师的私有题目")
        if any(item.question_id == question.id for item in paper.questions):
            raise ConflictException("试卷中已存在该题目", 60010)
        paper.questions.append(
            PaperQuestion(
                question_id=question.id,
                score=payload.score,
                sort_order=len(paper.questions) + 1,
            )
        )
        paper.total_score = Decimal(paper.total_score) + payload.score
        await self.session.commit()
        return await self._paper(paper.id)

    async def create_exam(self, payload: ExamCreate) -> Exam:
        course = await self.session.get(Course, payload.course_id)
        if course is None or course.teacher_id != self.current_user.id:
            raise PermissionDeniedException("只能为自己的课程创建考试")
        if course.status != CourseStatus.PUBLISHED:
            raise ConflictException("只有已发布课程可以创建考试", 60011)
        paper = await self._paper(payload.paper_id)
        if paper.teacher_id != self.current_user.id or not paper.questions:
            raise ConflictException("试卷不存在、无权使用或没有题目", 60012)
        exam = Exam(teacher_id=self.current_user.id, **payload.model_dump())
        self.session.add(exam)
        await self.session.commit()
        return await self._exam(exam.id)

    async def start_exam(self, exam_id: int) -> tuple[Exam, ExamAttempt]:
        exam = await self._exam(exam_id)
        self._ensure_exam_open(exam)
        enrollment = await LearningRepository(self.session).get_active_enrollment(
            self.current_user.id, exam.course_id
        )
        if enrollment is None:
            raise PermissionDeniedException("未加入课程，不能参加考试")
        attempt = await self.repository.get_attempt(exam.id, self.current_user.id)
        if attempt:
            return exam, attempt
        attempt = ExamAttempt(
            exam_id=exam.id,
            user_id=self.current_user.id,
            status=AttemptStatus.IN_PROGRESS,
            started_at=datetime.now(UTC),
            total_score=exam.paper.total_score,
        )
        self.session.add(attempt)
        await self.session.commit()
        await self.session.refresh(attempt, ["answers"])
        return exam, attempt

    async def submit_exam(self, exam_id: int, payload: ExamSubmitRequest) -> ExamAttempt:
        exam = await self._exam(exam_id)
        attempt = await self.repository.get_attempt(exam.id, self.current_user.id)
        if attempt is None:
            raise ConflictException("请先开始考试", 60013)
        if attempt.status == AttemptStatus.GRADED:
            return attempt
        self._ensure_exam_open(exam)
        lock_key = f"exam:submit_lock:{exam.id}:{self.current_user.id}"
        lock_token = uuid4().hex
        locked = await self.redis.set(lock_key, lock_token, ex=15, nx=True)
        if not locked:
            latest = await self.repository.get_attempt(exam.id, self.current_user.id)
            if latest and latest.status == AttemptStatus.GRADED:
                return latest
            raise ConflictException("答卷正在提交，请勿重复操作", 60014)
        try:
            return await self._grade(exam, attempt, payload)
        finally:
            await self.redis.eval(RELEASE_LOCK_SCRIPT, 1, lock_key, lock_token)

    async def _grade(
        self, exam: Exam, attempt: ExamAttempt, payload: ExamSubmitRequest
    ) -> ExamAttempt:
        submitted = {item.question_id: item.selected_answers for item in payload.answers}
        if len(submitted) != len(payload.answers):
            raise ConflictException("答卷包含重复题目", 60015)
        total = Decimal("0")
        now = datetime.now(UTC)
        for paper_question in exam.paper.questions:
            question = paper_question.question
            selected = sorted(set(submitted.get(question.id, [])))
            correct = selected == sorted(set(question.correct_answers))
            score = Decimal(paper_question.score) if correct else Decimal("0")
            total += score
            attempt.answers.append(
                ExamAnswer(
                    question_id=question.id,
                    selected_answers=selected,
                    is_correct=correct,
                    score=score,
                )
            )
            if not correct:
                wrong = await self.session.scalar(
                    select(WrongQuestion).where(
                        WrongQuestion.user_id == self.current_user.id,
                        WrongQuestion.question_id == question.id,
                    )
                )
                if wrong:
                    wrong.wrong_count += 1
                    wrong.last_wrong_at = now
                else:
                    self.session.add(
                        WrongQuestion(
                            user_id=self.current_user.id,
                            question_id=question.id,
                            wrong_count=1,
                            last_wrong_at=now,
                        )
                    )
        attempt.status = AttemptStatus.GRADED
        attempt.objective_score = total
        attempt.submitted_at = now
        attempt.duration_seconds = max(0, int((now - aware(attempt.started_at)).total_seconds()))
        attempt.idempotency_key = payload.idempotency_key
        await self.session.commit()
        refreshed = await self.repository.get_attempt(exam.id, self.current_user.id)
        assert refreshed is not None
        return refreshed

    @staticmethod
    def _ensure_exam_open(exam: Exam) -> None:
        now = datetime.now(UTC)
        if not exam.is_published or now < aware(exam.starts_at):
            raise ConflictException("考试尚未开始", 60001)
        if now > aware(exam.ends_at):
            raise ConflictException("考试已结束", 60002)

    async def _question(self, question_id: int) -> Question:
        item = await self.repository.get_question(question_id)
        if item is None:
            raise ResourceNotFoundException("题目不存在", 60020)
        return item

    async def _paper(self, paper_id: int) -> Paper:
        item = await self.repository.get_paper(paper_id)
        if item is None:
            raise ResourceNotFoundException("试卷不存在", 60021)
        return item

    async def _exam(self, exam_id: int) -> Exam:
        item = await self.repository.get_exam(exam_id)
        if item is None:
            raise ResourceNotFoundException("考试不存在", 60022)
        return item
