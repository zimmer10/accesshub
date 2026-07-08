import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.cache import get_redis
from app.core.db import get_db
from app.core.security import hash_password
from app.models import Role, User
from app.models.associations import user_roles
from app.schemas.access import EffectivePermissionsResponse
from app.schemas.role import RoleAssign
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.audit import record_audit_log, user_snapshot
from app.services.permission_cache import invalidate_user_cache
from app.services.permissions import resolve_effective_permissions
from app.services.users import create_user

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[UserRead])
async def list_users(db: AsyncSession = Depends(get_db)) -> list[User]:
    result = await db.scalars(select(User).order_by(User.id))
    return list(result)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user_endpoint(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    user = await create_user(
        db, username=payload.username, email=payload.email, password=payload.password
    )
    await record_audit_log(
        db,
        actor_id=current_user.id,
        action="user.create",
        target_type="user",
        target_id=user.id,
        after=user_snapshot(user),
    )
    await db.commit()
    return user


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    return user


@router.get("/{user_id}/effective-permissions", response_model=EffectivePermissionsResponse)
async def get_effective_permissions(
    user_id: int, db: AsyncSession = Depends(get_db)
) -> EffectivePermissionsResponse:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")

    resolved = await resolve_effective_permissions(db, user_id)
    return EffectivePermissionsResponse(
        user_id=user_id,
        groups=sorted(resolved.direct_group_ids),
        ancestor_groups=sorted(resolved.all_group_ids - resolved.direct_group_ids),
        roles=sorted(resolved.role_ids),
        permissions=sorted(resolved.permission_codes),
    )


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")

    updates = payload.model_dump(exclude_unset=True)
    password = updates.pop("password", None)

    conflict_conditions = []
    if "username" in updates:
        conflict_conditions.append(User.username == updates["username"])
    if "email" in updates:
        conflict_conditions.append(User.email == updates["email"])
    if conflict_conditions:
        existing = await db.scalar(
            select(User).where(User.id != user_id, or_(*conflict_conditions))
        )
        if existing is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "username or email is already taken")

    before = user_snapshot(user)

    for field, value in updates.items():
        setattr(user, field, value)
    if password is not None:
        user.hashed_password = hash_password(password)

    if updates or password is not None:
        after = user_snapshot(user)
        if password is not None:
            after["password_changed"] = True
        await record_audit_log(
            db,
            actor_id=current_user.id,
            action="user.update",
            target_type="user",
            target_id=user_id,
            before=before,
            after=after,
        )

    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis),
) -> None:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")

    await record_audit_log(
        db,
        actor_id=current_user.id,
        action="user.delete",
        target_type="user",
        target_id=user_id,
        before=user_snapshot(user),
    )
    await db.delete(user)
    await db.commit()

    await invalidate_user_cache(redis_client, user_id)


@router.post("/{user_id}/roles", status_code=status.HTTP_204_NO_CONTENT)
async def add_role_to_user(
    user_id: int,
    payload: RoleAssign,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis),
) -> None:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")

    role = await db.get(Role, payload.role_id)
    if role is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "role not found")

    already_assigned = await db.scalar(
        select(user_roles).where(
            user_roles.c.user_id == user_id, user_roles.c.role_id == payload.role_id
        )
    )
    if already_assigned is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "role is already assigned to this user")

    await db.execute(insert(user_roles).values(user_id=user_id, role_id=payload.role_id))
    await record_audit_log(
        db,
        actor_id=current_user.id,
        action="user.role.add",
        target_type="user",
        target_id=user_id,
        after={"role_id": payload.role_id},
    )
    await db.commit()

    await invalidate_user_cache(redis_client, user_id)


@router.delete("/{user_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_role_from_user(
    user_id: int,
    role_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis),
) -> None:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")

    is_assigned = await db.scalar(
        select(user_roles).where(user_roles.c.user_id == user_id, user_roles.c.role_id == role_id)
    )
    if is_assigned is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "role is not assigned to this user")

    await db.execute(
        delete(user_roles).where(user_roles.c.user_id == user_id, user_roles.c.role_id == role_id)
    )
    await record_audit_log(
        db,
        actor_id=current_user.id,
        action="user.role.remove",
        target_type="user",
        target_id=user_id,
        before={"role_id": role_id},
    )
    await db.commit()

    await invalidate_user_cache(redis_client, user_id)
