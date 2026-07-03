from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models import Group, User
from app.models.associations import user_groups
from app.schemas.group import GroupCreate, GroupMemberAdd, GroupRead, GroupUpdate

router = APIRouter(prefix="/groups", tags=["groups"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[GroupRead])
async def list_groups(db: AsyncSession = Depends(get_db)) -> list[Group]:
    result = await db.scalars(select(Group).order_by(Group.id))
    return list(result)


@router.post("", response_model=GroupRead, status_code=status.HTTP_201_CREATED)
async def create_group(payload: GroupCreate, db: AsyncSession = Depends(get_db)) -> Group:
    if payload.parent_group_id is not None:
        parent = await db.get(Group, payload.parent_group_id)
        if parent is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "parent group not found")

    existing = await db.scalar(select(Group).where(Group.name == payload.name))
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "group name is already taken")

    group = Group(name=payload.name, parent_group_id=payload.parent_group_id)
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return group


@router.patch("/{group_id}", response_model=GroupRead)
async def update_group(
    group_id: int, payload: GroupUpdate, db: AsyncSession = Depends(get_db)
) -> Group:
    group = await db.get(Group, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "group not found")

    updates = payload.model_dump(exclude_unset=True)

    if "parent_group_id" in updates:
        new_parent_id = updates["parent_group_id"]
        if new_parent_id == group_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "a group cannot be its own parent")
        if new_parent_id is not None:
            parent = await db.get(Group, new_parent_id)
            if parent is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "parent group not found")

    if "name" in updates:
        existing = await db.scalar(
            select(Group).where(Group.id != group_id, Group.name == updates["name"])
        )
        if existing is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "group name is already taken")

    for field, value in updates.items():
        setattr(group, field, value)

    await db.commit()
    await db.refresh(group)
    return group


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(group_id: int, db: AsyncSession = Depends(get_db)) -> None:
    group = await db.get(Group, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "group not found")
    await db.delete(group)
    await db.commit()


@router.post("/{group_id}/members", status_code=status.HTTP_204_NO_CONTENT)
async def add_member(
    group_id: int, payload: GroupMemberAdd, db: AsyncSession = Depends(get_db)
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
    await db.commit()


@router.delete("/{group_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(group_id: int, user_id: int, db: AsyncSession = Depends(get_db)) -> None:
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
    await db.commit()
