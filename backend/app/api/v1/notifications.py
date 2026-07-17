from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps.auth import CurrentUser, DatabaseSession, require_permissions
from app.core.response import success
from app.schemas.notification import NotificationCreate
from app.services.notification import NotificationService

router = APIRouter(prefix="/notifications", tags=["消息中心"])
NotificationManager = Annotated[object, Depends(require_permissions("notification:manage"))]


@router.post("/broadcast", status_code=201, summary="批量创建通知")
async def create_notification(
    payload: NotificationCreate,
    _: NotificationManager,
    current_user: CurrentUser,
    session: DatabaseSession,
) -> dict:
    item = await NotificationService(session, current_user).create_for_users(
        payload.title,
        payload.content,
        payload.notification_type,
        payload.user_ids,
    )
    return success({"id": item.id, "recipient_count": len(set(payload.user_ids))})


@router.get("", summary="消息列表")
async def list_notifications(
    current_user: CurrentUser, session: DatabaseSession, unread_only: bool = False
) -> dict:
    items = await NotificationService(session, current_user).list_messages(
        current_user.id, unread_only
    )
    return success(
        [
            {
                "id": item.id,
                "title": item.notification.title,
                "content": item.notification.content,
                "type": item.notification.notification_type.value,
                "is_read": item.read_at is not None,
                "created_at": item.created_at.isoformat(),
            }
            for item in items
        ]
    )


@router.get("/unread-count", summary="未读消息数")
async def unread_count(current_user: CurrentUser, session: DatabaseSession) -> dict:
    count = await NotificationService(session, current_user).unread_count(current_user.id)
    return success({"count": count})


@router.post("/{message_id}/read", summary="标记单条已读")
async def mark_read(
    message_id: int, current_user: CurrentUser, session: DatabaseSession
) -> dict:
    await NotificationService(session, current_user).mark_read(current_user.id, message_id)
    return success(message="已标记为已读")


@router.post("/read-all", summary="全部标记已读")
async def mark_all_read(current_user: CurrentUser, session: DatabaseSession) -> dict:
    await NotificationService(session, current_user).mark_all_read(current_user.id)
    return success(message="已全部标记为已读")


@router.delete("/{message_id}", summary="删除消息")
async def delete_message(
    message_id: int, current_user: CurrentUser, session: DatabaseSession
) -> dict:
    await NotificationService(session, current_user).delete_message(current_user.id, message_id)
    return success(message="消息已删除")

