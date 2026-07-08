from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Group, Permission, Role, User


async def record_audit_log(
    db: AsyncSession,
    *,
    actor_id: int | None,
    action: str,
    target_type: str,
    target_id: int,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    # commit делает вызывающий эндпоинт — запись аудита уходит в той же
    # транзакции, что и само изменение: либо оба применились, либо оба откатились
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            before=before,
            after=after,
        )
    )


def user_snapshot(user: User) -> dict[str, Any]:
    # hashed_password сюда никогда не попадает, даже в виде хэша
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "is_active": user.is_active,
    }


def group_snapshot(group: Group) -> dict[str, Any]:
    return {"id": group.id, "name": group.name, "parent_group_id": group.parent_group_id}


def role_snapshot(role: Role) -> dict[str, Any]:
    return {"id": role.id, "name": role.name, "description": role.description}


def permission_snapshot(permission: Permission) -> dict[str, Any]:
    return {"id": permission.id, "code": permission.code, "description": permission.description}
