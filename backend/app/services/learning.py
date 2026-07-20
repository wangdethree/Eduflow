import json
from datetime import UTC, datetime
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictException,
    ResourceNotFoundException,
    ServiceUnavailableException,
)
from app.core.redis import get_redis_client
from app.models.course import Course, CourseStatus
from app.models.learning import CourseEnrollment, CourseFavorite, EnrollmentStatus
from app.models.user import User
from app.repositories.learning import LearningRepository
from app.schemas.learning import ProgressReportRequest

SAVE_PROGRESS_SCRIPT = """
local current_raw = redis.call('GET', KEYS[1])
local incoming = cjson.decode(ARGV[1])
if current_raw then
  local current = cjson.decode(current_raw)
  if tonumber(incoming.updated_at) <= tonumber(current.updated_at) then
    return current_raw
  end
  incoming.position = math.max(tonumber(current.position), tonumber(incoming.position))
  incoming.learned_seconds = tonumber(current.learned_seconds) + tonumber(incoming.learned_delta)
else
  incoming.learned_seconds = tonumber(incoming.learned_delta)
end
incoming.learned_delta = nil
incoming.progress_percent = math.min(100, incoming.position / incoming.duration * 100)
incoming.is_completed = incoming.position >= incoming.duration * 0.9
  and incoming.learned_seconds >= incoming.duration * 0.8
local encoded = cjson.encode(incoming)
redis.call('SET', KEYS[1], encoded, 'EX', ARGV[2])
return encoded
"""

COMPARE_DELETE_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""


class ProgressCache:
    def __init__(self, redis: Redis) -> None:
        self.redis = redis

    @staticmethod
    def key(user_id: int, lesson_id: int) -> str:
        return f"learning:progress:{user_id}:{lesson_id}"

    async def save(self, data: dict[str, Any]) -> dict[str, Any]:
        key = self.key(data["user_id"], data["lesson_id"])
        result = await self.redis.eval(SAVE_PROGRESS_SCRIPT, 1, key, json.dumps(data), 86400)
        if isinstance(result, bytes):
            result = result.decode()
        return json.loads(result)

    async def get(self, user_id: int, lesson_id: int) -> dict[str, Any] | None:
        raw = await self.redis.get(self.key(user_id, lesson_id))
        if raw is None:
            return None
        return json.loads(raw)

    async def compare_delete(self, key: str, raw: str) -> None:
        await self.redis.eval(COMPARE_DELETE_SCRIPT, 1, key, raw)


class LearningService:
    def __init__(self, session: AsyncSession, current_user: User) -> None:
        self.session = session
        self.current_user = current_user
        self.repository = LearningRepository(session)
        self.cache = ProgressCache(get_redis_client())

    async def enroll(self, course_id: int) -> CourseEnrollment:
        course = await self.session.get(Course, course_id)
        if course is None or course.status != CourseStatus.PUBLISHED:
            raise ResourceNotFoundException("课程不存在或尚未发布", 40001)
        enrollment = await self.repository.get_enrollment(self.current_user.id, course_id)
        if enrollment and enrollment.status != EnrollmentStatus.WITHDRAWN:
            return enrollment
        now = datetime.now(UTC)
        if enrollment:
            enrollment.status = EnrollmentStatus.ACTIVE
            enrollment.enrolled_at = now
        else:
            enrollment = CourseEnrollment(
                course_id=course_id,
                user_id=self.current_user.id,
                status=EnrollmentStatus.ACTIVE,
                enrolled_at=now,
            )
            self.session.add(enrollment)
        course.student_count += 1
        await self.session.commit()
        await self.session.refresh(enrollment)
        return enrollment

    async def withdraw(self, course_id: int) -> None:
        enrollment = await self.repository.get_active_enrollment(self.current_user.id, course_id)
        if enrollment is None:
            raise ResourceNotFoundException("尚未加入该课程", 50001)
        enrollment.status = EnrollmentStatus.WITHDRAWN
        course = await self.session.get(Course, course_id)
        if course:
            course.student_count = max(0, course.student_count - 1)
        await self.session.commit()

    async def report_progress(
        self, course_id: int, payload: ProgressReportRequest
    ) -> dict[str, Any]:
        if await self.repository.get_active_enrollment(self.current_user.id, course_id) is None:
            raise ConflictException("请先加入课程", 50001)
        lesson = await self.repository.get_lesson(payload.lesson_id)
        if lesson is None or lesson.chapter.course_id != course_id:
            raise ResourceNotFoundException("课时不存在", 50002)
        duration = max(lesson.duration_seconds, 1)
        if payload.position_seconds > duration:
            raise ConflictException("播放位置不能超过课时总时长", 50003)
        data = {
            "user_id": self.current_user.id,
            "course_id": course_id,
            "lesson_id": lesson.id,
            "position": payload.position_seconds,
            "duration": duration,
            "learned_delta": payload.learned_seconds_delta,
            "updated_at": payload.client_updated_at,
        }
        try:
            return await self.cache.save(data)
        except RedisError as exc:
            # 进度乱序合并依赖 Redis Lua 原子性，故障时拒绝写入比产生倒退数据更安全。
            raise ServiceUnavailableException("学习进度服务暂时不可用，请稍后重试") from exc

    async def get_lesson_progress(self, lesson_id: int) -> dict[str, Any]:
        try:
            cached = await self.cache.get(self.current_user.id, lesson_id)
        except RedisError:
            # 读取可安全降级到最近一次落库进度。
            cached = None
        if cached:
            return cached
        progress = await self.repository.get_progress(self.current_user.id, lesson_id)
        if progress is None:
            raise ResourceNotFoundException("暂无学习进度", 50004)
        return {
            "user_id": progress.user_id,
            "course_id": progress.course_id,
            "lesson_id": progress.lesson_id,
            "position": progress.last_position,
            "duration": 0,
            "learned_seconds": progress.learned_seconds,
            "progress_percent": float(progress.progress_percent),
            "is_completed": progress.is_completed,
            "updated_at": progress.client_updated_at,
        }

    async def toggle_favorite(self, course_id: int) -> bool:
        course = await self.session.get(Course, course_id)
        if course is None or course.status != CourseStatus.PUBLISHED:
            raise ResourceNotFoundException("课程不存在", 40001)
        favorite = await self.repository.get_favorite(self.current_user.id, course_id)
        if favorite:
            await self.session.delete(favorite)
            enabled = False
        else:
            self.session.add(CourseFavorite(user_id=self.current_user.id, course_id=course_id))
            enabled = True
        await self.session.commit()
        return enabled
