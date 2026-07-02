import asyncio

from sqlalchemy import select

from app.core.db import async_session_factory
from app.core.security import hash_password
from app.models import Group, Permission, Role, User


async def seed() -> None:
    async with async_session_factory() as session:
        existing = await session.scalar(select(User).where(User.username == "admin"))
        if existing:
            print("Seed data already present, skipping.")
            return

        admin = User(
            username="admin",
            email="admin@example.com",
            hashed_password=hash_password("admin123"),
        )
        viewer = User(
            username="viewer",
            email="viewer@example.com",
            hashed_password=hash_password("viewer123"),
        )

        engineering = Group(name="Engineering")
        backend_team = Group(name="Backend Team", parent=engineering)

        admin_role = Role(name="admin", description="Полный доступ")
        viewer_role = Role(name="viewer", description="Только чтение")

        invoice_read = Permission(code="invoice:read", description="Чтение счетов")
        invoice_all = Permission(code="invoice:*", description="Управление счетами")
        user_manage = Permission(code="user:manage", description="Управление пользователями")

        admin_role.permissions = [invoice_all, user_manage]
        viewer_role.permissions = [invoice_read]

        backend_team.roles = [admin_role]
        admin.groups = [backend_team]
        viewer.roles = [viewer_role]

        session.add_all(
            [
                admin,
                viewer,
                engineering,
                backend_team,
                admin_role,
                viewer_role,
                invoice_read,
                invoice_all,
                user_manage,
            ]
        )
        await session.commit()
        print(
            "Seed data created: users admin/viewer, "
            "groups Engineering > Backend Team, roles admin/viewer."
        )


if __name__ == "__main__":
    asyncio.run(seed())
