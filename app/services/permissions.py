from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Permission
from app.models.associations import group_roles, role_permissions, user_groups, user_roles
from app.services.group_hierarchy import (
    ancestor_closure,
    children_map_from_parent_map,
    descendant_closure,
    fetch_parent_map,
)


@dataclass
class EffectivePermissions:
    direct_group_ids: set[int]
    all_group_ids: set[int]
    role_ids: set[int]
    permission_codes: set[str]


async def resolve_effective_permissions(db: AsyncSession, user_id: int) -> EffectivePermissions:
    direct_group_ids = set(
        await db.scalars(select(user_groups.c.group_id).where(user_groups.c.user_id == user_id))
    )

    parent_map = await fetch_parent_map(db)
    all_group_ids = ancestor_closure(direct_group_ids, parent_map)

    direct_role_ids = set(
        await db.scalars(select(user_roles.c.role_id).where(user_roles.c.user_id == user_id))
    )
    group_role_ids: set[int] = set()
    if all_group_ids:
        group_role_ids = set(
            await db.scalars(
                select(group_roles.c.role_id).where(group_roles.c.group_id.in_(all_group_ids))
            )
        )
    role_ids = direct_role_ids | group_role_ids

    permission_codes: set[str] = set()
    if role_ids:
        permission_codes = set(
            await db.scalars(
                select(Permission.code)
                .join(role_permissions, role_permissions.c.permission_id == Permission.id)
                .where(role_permissions.c.role_id.in_(role_ids))
            )
        )

    return EffectivePermissions(
        direct_group_ids=direct_group_ids,
        all_group_ids=all_group_ids,
        role_ids=role_ids,
        permission_codes=permission_codes,
    )


def permission_matches(granted_codes: set[str], requested_code: str) -> bool:
    if requested_code in granted_codes:
        return True
    return any(
        code.endswith(":*") and requested_code.startswith(code[:-1]) for code in granted_codes
    )


async def user_has_permission(db: AsyncSession, user_id: int, permission_code: str) -> bool:
    resolved = await resolve_effective_permissions(db, user_id)
    return permission_matches(resolved.permission_codes, permission_code)


async def find_affected_users_for_groups(db: AsyncSession, group_ids: set[int]) -> set[int]:
    """Пользователи, у которых может измениться резолв прав из-за изменения в
    любой из group_ids: сама группа + все её потомки (они наследуют роли группы
    через ancestor_closure), плюс все члены этих групп."""
    if not group_ids:
        return set()

    parent_map = await fetch_parent_map(db)
    children_map = children_map_from_parent_map(parent_map)
    affected_group_ids = descendant_closure(group_ids, children_map)

    return set(
        await db.scalars(
            select(user_groups.c.user_id).where(user_groups.c.group_id.in_(affected_group_ids))
        )
    )


async def find_affected_users_for_role(db: AsyncSession, role_id: int) -> set[int]:
    """Пользователи, у которых сейчас есть эта роль — напрямую или через
    членство в группе (включая любую вложенную группу-потомок группы,
    которой роль выдана)."""
    direct_user_ids = set(
        await db.scalars(select(user_roles.c.user_id).where(user_roles.c.role_id == role_id))
    )
    granting_group_ids = set(
        await db.scalars(select(group_roles.c.group_id).where(group_roles.c.role_id == role_id))
    )
    group_user_ids = await find_affected_users_for_groups(db, granting_group_ids)
    return direct_user_ids | group_user_ids
