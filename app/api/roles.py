import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import Select, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.core.cache import get_redis
from app.core.db import get_db
from app.models import Permission, Role, User
from app.models.associations import role_permissions
from app.schemas.role import RoleCreate, RolePermissionAdd, RoleRead, RoleUpdate
from app.services.audit import record_audit_log, role_snapshot
from app.services.permission_cache import invalidate_users_cache
from app.services.permissions import find_affected_users_for_role

router = APIRouter(prefix="/roles", tags=["roles"], dependencies=[Depends(get_current_user)])


def _roles_query() -> Select[tuple[Role]]:
    return select(Role).options(selectinload(Role.permissions))


@router.get("", response_model=list[RoleRead])
async def list_roles(db: AsyncSession = Depends(get_db)) -> list[Role]:
    result = await db.scalars(_roles_query().order_by(Role.id))
    return list(result)


@router.post("", response_model=RoleRead, status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: RoleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Role:
    existing = await db.scalar(select(Role).where(Role.name == payload.name))
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "role name is already taken")

    role = Role(name=payload.name, description=payload.description)
    db.add(role)
    await db.flush()
    await record_audit_log(
        db,
        actor_id=current_user.id,
        action="role.create",
        target_type="role",
        target_id=role.id,
        after=role_snapshot(role),
    )
    await db.commit()

    created = await db.scalar(_roles_query().where(Role.id == role.id))
    assert created is not None
    return created


@router.get("/{role_id}", response_model=RoleRead)
async def get_role(role_id: int, db: AsyncSession = Depends(get_db)) -> Role:
    role = await db.scalar(_roles_query().where(Role.id == role_id))
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "role not found")
    return role


@router.patch("/{role_id}", response_model=RoleRead)
async def update_role(
    role_id: int,
    payload: RoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Role:
    role = await db.get(Role, role_id)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "role not found")

    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates:
        existing = await db.scalar(
            select(Role).where(Role.id != role_id, Role.name == updates["name"])
        )
        if existing is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "role name is already taken")

    before = role_snapshot(role)
    for field, value in updates.items():
        setattr(role, field, value)

    if updates:
        await record_audit_log(
            db,
            actor_id=current_user.id,
            action="role.update",
            target_type="role",
            target_id=role_id,
            before=before,
            after=role_snapshot(role),
        )

    await db.commit()

    updated = await db.scalar(_roles_query().where(Role.id == role_id))
    assert updated is not None
    return updated


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis),
) -> None:
    role = await db.get(Role, role_id)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "role not found")

    # затронутых считаем ДО удаления — после каскада user_roles/group_roles
    # для этой роли уже не найти
    affected_user_ids = await find_affected_users_for_role(db, role_id)

    await record_audit_log(
        db,
        actor_id=current_user.id,
        action="role.delete",
        target_type="role",
        target_id=role_id,
        before=role_snapshot(role),
    )
    await db.delete(role)
    await db.commit()

    if affected_user_ids:
        await invalidate_users_cache(redis_client, affected_user_ids)


@router.post("/{role_id}/permissions", status_code=status.HTTP_204_NO_CONTENT)
async def add_permission_to_role(
    role_id: int,
    payload: RolePermissionAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis),
) -> None:
    role = await db.get(Role, role_id)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "role not found")

    permission = await db.get(Permission, payload.permission_id)
    if permission is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "permission not found")

    already_linked = await db.scalar(
        select(role_permissions).where(
            role_permissions.c.role_id == role_id,
            role_permissions.c.permission_id == payload.permission_id,
        )
    )
    if already_linked is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "permission is already assigned to this role")

    await db.execute(
        insert(role_permissions).values(role_id=role_id, permission_id=payload.permission_id)
    )
    await record_audit_log(
        db,
        actor_id=current_user.id,
        action="role.permission.add",
        target_type="role",
        target_id=role_id,
        after={"permission_id": payload.permission_id},
    )
    await db.commit()

    affected_user_ids = await find_affected_users_for_role(db, role_id)
    if affected_user_ids:
        await invalidate_users_cache(redis_client, affected_user_ids)
