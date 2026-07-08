import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.cache import get_redis
from app.core.db import get_db
from app.models import Group, Role, User
from app.models.associations import group_roles, user_groups
from app.schemas.group import GroupCreate, GroupMemberAdd, GroupRead, GroupUpdate
from app.schemas.role import RoleAssign
from app.services.audit import group_snapshot, record_audit_log
from app.services.group_hierarchy import (
    ancestor_closure,
    children_map_from_parent_map,
    descendant_closure,
    fetch_parent_map,
)
from app.services.permission_cache import invalidate_user_cache, invalidate_users_cache
from app.services.permissions import find_affected_users_for_groups

router = APIRouter(prefix="/groups", tags=["groups"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[GroupRead])
async def list_groups(db: AsyncSession = Depends(get_db)) -> list[Group]:
    result = await db.scalars(select(Group).order_by(Group.id))
    return list(result)


@router.post("", response_model=GroupRead, status_code=status.HTTP_201_CREATED)
async def create_group(
    payload: GroupCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Group:
    if payload.parent_group_id is not None:
        parent = await db.get(Group, payload.parent_group_id)
        if parent is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "parent group not found")

    existing = await db.scalar(select(Group).where(Group.name == payload.name))
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "group name is already taken")

    group = Group(name=payload.name, parent_group_id=payload.parent_group_id)
    db.add(group)
    await db.flush()
    await record_audit_log(
        db,
        actor_id=current_user.id,
        action="group.create",
        target_type="group",
        target_id=group.id,
        after=group_snapshot(group),
    )
    await db.commit()
    await db.refresh(group)
    return group


@router.patch("/{group_id}", response_model=GroupRead)
async def update_group(
    group_id: int,
    payload: GroupUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis),
) -> Group:
    group = await db.get(Group, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "group not found")

    updates = payload.model_dump(exclude_unset=True)
    reparenting = "parent_group_id" in updates
    affected_user_ids: set[int] = set()

    if reparenting:
        new_parent_id = updates["parent_group_id"]
        if new_parent_id == group_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "a group cannot be its own parent")
        if new_parent_id is not None:
            parent = await db.get(Group, new_parent_id)
            if parent is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "parent group not found")

        # SELECT ... FOR UPDATE на все группы держит эти строки залоченными до
        # конца транзакции (до commit ниже) — если два запроса одновременно
        # попробуют перецепить разные группы так, что вместе это создаст цикл,
        # второй запрос дождётся коммита первого и увидит уже актуальное дерево.
        parent_map = await fetch_parent_map(db, for_update=True)
        if new_parent_id is not None:
            ancestors_of_new_parent = ancestor_closure({new_parent_id}, parent_map)
            if group_id in ancestors_of_new_parent:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "this parent change would create a cycle in the group hierarchy",
                )

        # переподчинение группы меняет её предков — а значит и резолв прав для
        # всех, кто состоит в ней самой или в любой её дочерней группе
        children_map = children_map_from_parent_map(parent_map)
        affected_group_ids = descendant_closure({group_id}, children_map)
        affected_user_ids = set(
            await db.scalars(
                select(user_groups.c.user_id).where(user_groups.c.group_id.in_(affected_group_ids))
            )
        )

    if "name" in updates:
        existing = await db.scalar(
            select(Group).where(Group.id != group_id, Group.name == updates["name"])
        )
        if existing is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "group name is already taken")

    before = group_snapshot(group)
    for field, value in updates.items():
        setattr(group, field, value)

    if updates:
        await record_audit_log(
            db,
            actor_id=current_user.id,
            action="group.update",
            target_type="group",
            target_id=group_id,
            before=before,
            after=group_snapshot(group),
        )

    await db.commit()
    await db.refresh(group)

    if affected_user_ids:
        await invalidate_users_cache(redis_client, affected_user_ids)

    return group


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis),
) -> None:
    group = await db.get(Group, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "group not found")

    # считаем затронутых пользователей ДО удаления — после каскада children
    # получат parent_group_id=NULL и восстановить дерево будет нечем
    affected_user_ids = await find_affected_users_for_groups(db, {group_id})

    await record_audit_log(
        db,
        actor_id=current_user.id,
        action="group.delete",
        target_type="group",
        target_id=group_id,
        before=group_snapshot(group),
    )
    await db.delete(group)
    await db.commit()

    if affected_user_ids:
        await invalidate_users_cache(redis_client, affected_user_ids)


@router.post("/{group_id}/members", status_code=status.HTTP_204_NO_CONTENT)
async def add_member(
    group_id: int,
    payload: GroupMemberAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis),
) -> None:
    group = await db.get(Group, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "group not found")

    user = await db.get(User, payload.user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")

    already_member = await db.scalar(
        select(user_groups).where(
            user_groups.c.group_id == group_id, user_groups.c.user_id == payload.user_id
        )
    )
    if already_member is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "user is already a member of this group")

    await db.execute(insert(user_groups).values(group_id=group_id, user_id=payload.user_id))
    await record_audit_log(
        db,
        actor_id=current_user.id,
        action="group.member.add",
        target_type="group",
        target_id=group_id,
        after={"user_id": payload.user_id},
    )
    await db.commit()

    await invalidate_user_cache(redis_client, payload.user_id)


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    group_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis),
) -> None:
    group = await db.get(Group, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "group not found")

    is_member = await db.scalar(
        select(user_groups).where(
            user_groups.c.group_id == group_id, user_groups.c.user_id == user_id
        )
    )
    if is_member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user is not a member of this group")

    await db.execute(
        delete(user_groups).where(
            user_groups.c.group_id == group_id, user_groups.c.user_id == user_id
        )
    )
    await record_audit_log(
        db,
        actor_id=current_user.id,
        action="group.member.remove",
        target_type="group",
        target_id=group_id,
        before={"user_id": user_id},
    )
    await db.commit()

    await invalidate_user_cache(redis_client, user_id)


@router.post("/{group_id}/roles", status_code=status.HTTP_204_NO_CONTENT)
async def add_role_to_group(
    group_id: int,
    payload: RoleAssign,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis),
) -> None:
    group = await db.get(Group, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "group not found")

    role = await db.get(Role, payload.role_id)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "role not found")

    already_assigned = await db.scalar(
        select(group_roles).where(
            group_roles.c.group_id == group_id, group_roles.c.role_id == payload.role_id
        )
    )
    if already_assigned is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "role is already assigned to this group")

    await db.execute(insert(group_roles).values(group_id=group_id, role_id=payload.role_id))
    await record_audit_log(
        db,
        actor_id=current_user.id,
        action="group.role.add",
        target_type="group",
        target_id=group_id,
        after={"role_id": payload.role_id},
    )
    await db.commit()

    affected_user_ids = await find_affected_users_for_groups(db, {group_id})
    if affected_user_ids:
        await invalidate_users_cache(redis_client, affected_user_ids)


@router.delete("/{group_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_role_from_group(
    group_id: int,
    role_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis),
) -> None:
    group = await db.get(Group, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "group not found")

    is_assigned = await db.scalar(
        select(group_roles).where(
            group_roles.c.group_id == group_id, group_roles.c.role_id == role_id
        )
    )
    if is_assigned is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "role is not assigned to this group")

    await db.execute(
        delete(group_roles).where(
            group_roles.c.group_id == group_id, group_roles.c.role_id == role_id
        )
    )
    await record_audit_log(
        db,
        actor_id=current_user.id,
        action="group.role.remove",
        target_type="group",
        target_id=group_id,
        before={"role_id": role_id},
    )
    await db.commit()

    affected_user_ids = await find_affected_users_for_groups(db, {group_id})
    if affected_user_ids:
        await invalidate_users_cache(redis_client, affected_user_ids)
