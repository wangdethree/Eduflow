from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from app.models.exam import Exam, ExamAttempt, Paper, PaperQuestion, Question, WrongQuestion


class ExamRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_question(self, question_id: int) -> Question | None:
        return await self.session.scalar(
            select(Question)
            .where(Question.id == question_id)
            .options(selectinload(Question.options))
        )

    async def get_paper(self, paper_id: int) -> Paper | None:
        return await self.session.scalar(
            select(Paper)
            .where(Paper.id == paper_id)
            .options(selectinload(Paper.questions).joinedload(PaperQuestion.question))
        )

    async def get_exam(self, exam_id: int) -> Exam | None:
        return await self.session.scalar(
            select(Exam)
            .where(Exam.id == exam_id)
            .options(
                joinedload(Exam.paper)
                .selectinload(Paper.questions)
                .joinedload(PaperQuestion.question)
                .selectinload(Question.options)
            )
        )

    async def get_attempt(self, exam_id: int, user_id: int) -> ExamAttempt | None:
        return await self.session.scalar(
            select(ExamAttempt)
            .where(ExamAttempt.exam_id == exam_id, ExamAttempt.user_id == user_id)
            .options(selectinload(ExamAttempt.answers))
        )

    async def get_attempt_by_id(self, attempt_id: int, user_id: int) -> ExamAttempt | None:
        return await self.session.scalar(
            select(ExamAttempt)
            .where(ExamAttempt.id == attempt_id, ExamAttempt.user_id == user_id)
            .options(selectinload(ExamAttempt.answers))
        )

    async def list_wrong_questions(self, user_id: int) -> list[WrongQuestion]:
        return list(
            await self.session.scalars(
                select(WrongQuestion)
                .where(WrongQuestion.user_id == user_id)
                .order_by(WrongQuestion.last_wrong_at.desc())
            )
        )

