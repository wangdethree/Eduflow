from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps.auth import CurrentUser, DatabaseSession, require_permissions
from app.core.exceptions import ResourceNotFoundException
from app.core.response import success
from app.models.exam import ExamAttempt
from app.repositories.exam import ExamRepository
from app.schemas.exam import (
    AttemptResponse,
    ExamCreate,
    ExamSubmitRequest,
    PaperCreate,
    PaperQuestionCreate,
    QuestionCreate,
)
from app.services.exam import ExamService

router = APIRouter(tags=["考试中心"])
ExamCreator = Annotated[object, Depends(require_permissions("exam:create"))]


def serialize_attempt(attempt: ExamAttempt) -> dict:
    return AttemptResponse(
        id=attempt.id,
        exam_id=attempt.exam_id,
        status=attempt.status.value,
        objective_score=float(attempt.objective_score),
        total_score=float(attempt.total_score),
        started_at=attempt.started_at,
        submitted_at=attempt.submitted_at,
    ).model_dump(mode="json")


@router.post("/questions", status_code=201, summary="创建题目")
async def create_question(
    payload: QuestionCreate,
    _: ExamCreator,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    question = await ExamService(session, current_user).create_question(payload)
    return success(
        {
            "id": question.id,
            "stem": question.stem,
            "question_type": question.question_type.value,
            "options": {item.option_key: item.content for item in question.options},
            "correct_answers": question.correct_answers,
        }
    )


@router.post("/papers", status_code=201, summary="创建试卷")
async def create_paper(
    payload: PaperCreate,
    _: ExamCreator,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    paper = await ExamService(session, current_user).create_paper(payload)
    return success({"id": paper.id, "title": paper.title, "total_score": float(paper.total_score)})


@router.post("/papers/{paper_id}/questions", summary="向试卷添加题目")
async def add_paper_question(
    paper_id: int,
    payload: PaperQuestionCreate,
    _: ExamCreator,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    paper = await ExamService(session, current_user).add_paper_question(paper_id, payload)
    return success(
        {
            "id": paper.id,
            "total_score": float(paper.total_score),
            "question_count": len(paper.questions),
        }
    )


@router.post("/exams", status_code=201, summary="发布考试")
async def create_exam(
    payload: ExamCreate,
    _: ExamCreator,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    exam = await ExamService(session, current_user).create_exam(payload)
    return success(
        {
            "id": exam.id,
            "course_id": exam.course_id,
            "title": exam.title,
            "starts_at": exam.starts_at.isoformat(),
            "ends_at": exam.ends_at.isoformat(),
        }
    )


@router.post("/exams/{exam_id}/start", summary="开始考试")
async def start_exam(exam_id: int, current_user: CurrentUser, session: DatabaseSession) -> dict:
    exam, attempt = await ExamService(session, current_user).start_exam(exam_id)
    questions = [
        {
            "id": item.question.id,
            "stem": item.question.stem,
            "question_type": item.question.question_type.value,
            "options": {
                option.option_key: option.content for option in item.question.options
            },
            "score": float(item.score),
        }
        for item in exam.paper.questions
    ]
    return success({"attempt": serialize_attempt(attempt), "questions": questions})


@router.post("/exams/{exam_id}/submit", summary="提交并自动评分")
async def submit_exam(
    exam_id: int,
    payload: ExamSubmitRequest,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    attempt = await ExamService(session, current_user).submit_exam(exam_id, payload)
    return success(serialize_attempt(attempt), "考试已评分")


@router.get("/exam-attempts/{attempt_id}", summary="查询考试成绩")
async def get_attempt_result(
    attempt_id: int, current_user: CurrentUser, session: DatabaseSession
) -> dict:
    attempt = await ExamRepository(session).get_attempt_by_id(attempt_id, current_user.id)
    if attempt is None:
        raise ResourceNotFoundException("答卷不存在", 60023)
    return success(
        {
            **serialize_attempt(attempt),
            "answers": [
                {
                    "question_id": item.question_id,
                    "selected_answers": item.selected_answers,
                    "is_correct": item.is_correct,
                    "score": float(item.score),
                }
                for item in attempt.answers
            ],
        }
    )


@router.get("/wrong-questions", summary="错题本")
async def list_wrong_questions(current_user: CurrentUser, session: DatabaseSession) -> dict:
    items = await ExamRepository(session).list_wrong_questions(current_user.id)
    return success(
        [
            {
                "question_id": item.question_id,
                "wrong_count": item.wrong_count,
                "last_wrong_at": item.last_wrong_at.isoformat(),
            }
            for item in items
        ]
    )

