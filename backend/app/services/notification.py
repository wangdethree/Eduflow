from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import ResourceNotFoundException
from app.core.redis import get_redis_client
from app.models.notification import Notification, NotificationType, UserNotification
from app.models.user import User


class NotificationService:
    def __init__(self, session: AsyncSession, current_user: User | None = None) -> None:
        self.session = session
        self.current_user = current_user
        self.redis: Redis = get_redis_client()

    async def create_for_users(
        self,
        title: str,
        content: str,
        notification_type: str,
        user_ids: list[int],
        source_key: str | None = None,
        *,
        commit: bool = True,
    ) -> Notification:
        unique_user_ids = sorted(set(user_ids))
        existing_count = await self.session.scalar(
            select(func.count(User.id)).where(User.id.in_(unique_user_ids))
        )
        if existing_count != len(unique_user_ids):
            raise ResourceNotFoundException("部分接收用户不存在", 30001)
        notification = Notification(
            title=title,
            content=content,
            notification_type=NotificationType(notification_type),
            source_key=source_key,
            created_by=self.current_user.id if self.current_user else None,
        )
        notification.recipients = [UserNotification(user_id=user_id) for user_id in unique_user_ids]
        self.session.add(notification)
        if commit:
            await self.session.commit()
            await self.session.refresh(notification)
            for user_id in unique_user_ids:
                await self.redis.delete(self._unread_key(user_id))
        return notification

    async def list_messages(
        self, user_id: int, unread_only: bool = False
    ) -> list[UserNotification]:
        conditions = [
            UserNotification.user_id == user_id,
            UserNotification.deleted_at.is_(None),
        ]
        if unread_only:
            conditions.append(UserNotification.read_at.is_(None))
        result = await self.session.scalars(
            select(UserNotification)
            .where(*conditions)
            .options(joinedload(UserNotification.notification))
            .order_by(UserNotification.created_at.desc())
        )
        return list(result.unique())

    async def unread_count(self, user_id: int) -> int:
        key = self._unread_key(user_id)
        cached = await self.redis.get(key)
        if cached is not None:
            return int(cached)
        count = await self.session.scalar(
            select(func.count(UserNotification.id)).where(
                UserNotification.user_id == user_id,
                UserNotification.read_at.is_(None),
                UserNotification.deleted_at.is_(None),
            )
        ) or 0
        await self.redis.set(key, count, ex=3600)
        return count

    async def mark_read(self, user_id: int, message_id: int) -> None:
        message = await self.session.scalar(
            select(UserNotification).where(
                UserNotification.id == message_id,
                UserNotification.user_id == user_id,
                UserNotification.deleted_at.is_(None),
            )
        )
        if message is None:
            raise ResourceNotFoundException("消息不存在", 80010)
        if message.read_at is None:
            message.read_at = datetime.now(UTC)
            await self.session.commit()
            await self.redis.delete(self._unread_key(user_id))

    async def mark_all_read(self, user_id: int) -> None:
        await self.session.execute(
            update(UserNotification)
            .where(
                UserNotification.user_id == user_id,
                UserNotification.read_at.is_(None),
                UserNotification.deleted_at.is_(None),
            )
            .values(read_at=datetime.now(UTC))
        )
        await self.session.commit()
        await self.redis.set(self._unread_key(user_id), 0, ex=3600)

    async def delete_message(self, user_id: int, message_id: int) -> None:
        message = await self.session.scalar(
            select(UserNotification).where(
                UserNotification.id == message_id, UserNotification.user_id == user_id
            )
        )
        if message is None:
            raise ResourceNotFoundException("消息不存在", 80010)
        message.deleted_at = datetime.now(UTC)
        await self.session.commit()
        await self.redis.delete(self._unread_key(user_id))

    @staticmethod
    def _unread_key(user_id: int) -> str:
        return f"notification:unread:{user_id}"
