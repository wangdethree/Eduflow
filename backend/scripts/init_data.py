import asyncio
import os

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.course import CourseCategory
from app.models.rbac import Permission, Role
from app.models.user import User

PERMISSIONS = {
    "user:manage": "用户管理",
    "role:manage": "角色权限管理",
    "course:create": "创建课程",
    "course:update": "编辑课程",
    "course:audit": "审核课程",
    "course:publish": "发布与下架课程",
    "exam:create": "创建考试",
    "exam:submit": "参加考试",
    "notification:manage": "通知管理",
    "statistics:view": "查看统计",
}
ROLE_PERMISSIONS = {
    "admin": list(PERMISSIONS),
    "teacher": [
        "course:create",
        "course:update",
        "course:publish",
        "exam:create",
        "statistics:view",
    ],
    "student": ["exam:submit"],
}


async def initialize() -> None:
    admin_password = os.getenv("INITIAL_ADMIN_PASSWORD")
    if not admin_password or len(admin_password) < 8:
        raise RuntimeError("请设置至少 8 位的 INITIAL_ADMIN_PASSWORD")
    async with AsyncSessionLocal() as session:
        permissions: dict[str, Permission] = {}
        for code, name in PERMISSIONS.items():
            item = await session.scalar(select(Permission).where(Permission.code == code))
            if item is None:
                item = Permission(code=code, name=name)
                session.add(item)
            permissions[code] = item
        await session.flush()
        roles: dict[str, Role] = {}
        names = {"admin": "管理员", "teacher": "教师", "student": "学员"}
        for code, permission_codes in ROLE_PERMISSIONS.items():
            role = await session.scalar(select(Role).where(Role.code == code))
            if role is None:
                role = Role(name=names[code], code=code, is_system=True)
                session.add(role)
            role.permissions = [permissions[item] for item in permission_codes]
            roles[code] = role
        username = os.getenv("INITIAL_ADMIN_USERNAME", "admin")
        email = os.getenv("INITIAL_ADMIN_EMAIL", "admin@eduflow.local")
        admin = await session.scalar(select(User).where(User.username == username))
        if admin is None:
            admin = User(
                username=username,
                email=email,
                nickname="系统管理员",
                password_hash=hash_password(admin_password),
            )
            session.add(admin)
        admin.roles = [roles["admin"]]
        if await session.scalar(select(CourseCategory.id).limit(1)) is None:
            session.add_all(
                [
                    CourseCategory(name="编程开发", sort_order=1),
                    CourseCategory(name="职业技能", sort_order=2),
                    CourseCategory(name="通识教育", sort_order=3),
                ]
            )
        await session.commit()
        print(f"初始化完成，管理员账号：{username}")


if __name__ == "__main__":
    asyncio.run(initialize())

