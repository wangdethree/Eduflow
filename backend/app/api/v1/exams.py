from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps.auth import CurrentUser, DatabaseSession, require_permissions
from app.core.exceptions import ResourceNotFoundException
from app.core.response import success
from app.models.exam import ExamAttempt, Paper, Question
from app.repositories.exam import ExamRepository
from app.schemas.exam import (
    AttemptResponse,
    ExamCreate,
    ExamSubmitRequest,
    PaperCreate,
    PaperQuestionCreate,
    PaperQuestionUpdate,
    PaperUpdate,
    QuestionCreate,
    QuestionUpdate,
)
from app.services.exam import ExamService

router = APIRouter(tags=["考试中心"])
ExamCreator = Annotated[object, Depends(require_permissions("exam:create"))]


def serialize_question(question: Question) -> dict:
    return {
        "id": question.id,
        "stem": question.stem,
        "question_type": question.question_type.value,
        "options": {item.option_key: item.content for item in question.options},
        "correct_answers": question.correct_answers,
        "analysis": question.analysis,
        "difficulty": question.difficulty,
    }


def serialize_paper(paper: Paper) -> dict:
    return {
        "id": paper.id,
        "title": paper.title,
        "description": paper.description,
        "total_score": float(paper.total_score),
        "questions": [
            {
                "question_id": item.question_id,
                "score": float(item.score),
                "sort_order": item.sort_order,
                "question": serialize_question(item.question),
            }
            for item in paper.questions
        ],
    }


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
    return success(serialize_question(question))


@router.get("/questions", summary="教师题库列表")
async def list_questions(
    _: ExamCreator, current_user: CurrentUser, session: DatabaseSession
) -> dict:
    items = await ExamRepository(session).list_teacher_questions(current_user.id)
    return success([serialize_question(item) for item in items])


@router.put("/questions/{question_id}", summary="编辑题目")
async def update_question(
    question_id: int,
    payload: QuestionUpdate,
    _: ExamCreator,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    item = await ExamService(session, current_user).update_question(question_id, payload)
    return success(serialize_question(item))


@router.delete("/questions/{question_id}", summary="删除题目")
async def delete_question(
    question_id: int, _: ExamCreator, current_user: CurrentUser, session: DatabaseSession
) -> dict:
    await ExamService(session, current_user).delete_question(question_id)
    return success(message="题目已删除")


@router.post("/papers", status_code=201, summary="创建试卷")
async def create_paper(
    payload: PaperCreate,
    _: ExamCreator,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    paper = await ExamService(session, current_user).create_paper(payload)
    return success(serialize_paper(paper))


@router.get("/papers", summary="教师试卷列表")
async def list_papers(
    _: ExamCreator, current_user: CurrentUser, session: DatabaseSession
) -> dict:
    items = await ExamRepository(session).list_teacher_papers(current_user.id)
    return success([serialize_paper(item) for item in items])


@router.get("/papers/{paper_id}", summary="教师试卷详情")
async def get_paper(
    paper_id: int, _: ExamCreator, current_user: CurrentUser, session: DatabaseSession
) -> dict:
    paper = await ExamService(session, current_user).get_owned_paper(paper_id)
    return success(serialize_paper(paper))


@router.patch("/papers/{paper_id}", summary="编辑试卷")
async def update_paper(
    paper_id: int,
    payload: PaperUpdate,
    _: ExamCreator,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    paper = await ExamService(session, current_user).update_paper(paper_id, payload)
    return success(serialize_paper(paper))


@router.delete("/papers/{paper_id}", summary="删除试卷")
async def delete_paper(
    paper_id: int, _: ExamCreator, current_user: CurrentUser, session: DatabaseSession
) -> dict:
    await ExamService(session, current_user).delete_paper(paper_id)
    return success(message="试卷已删除")


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


@router.patch("/papers/{paper_id}/questions/{question_id}", summary="修改试卷题目分值")
async def update_paper_question(
    paper_id: int,
    question_id: int,
    payload: PaperQuestionUpdate,
    _: ExamCreator,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    paper = await ExamService(session, current_user).update_paper_question(
        paper_id, question_id, payload
    )
    return success(serialize_paper(paper))


@router.delete("/papers/{paper_id}/questions/{question_id}", summary="从试卷移除题目")
async def remove_paper_question(
    paper_id: int,
    question_id: int,
    _: ExamCreator,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    paper = await ExamService(session, current_user).remove_paper_question(
        paper_id, question_id
    )
    return success(serialize_paper(paper), "题目已从试卷移除")


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
