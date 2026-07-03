from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.security import hash_password
from app.models import User
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.users import create_user

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[UserRead])
async def list_users(db: AsyncSession = Depends(get_db)) -> list[User]:
    result = await db.scalars(select(User).order_by(User.id))
    return list(result)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user_endpoint(payload: UserCreate, db: AsyncSession = Depends(get_db)) -> User:
    return await create_user(
        db, username=payload.username, email=payload.email, password=payload.password
    )


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    return user


@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int, payload: UserUpdate, db: AsyncSession = Depends(get_db)
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

    for field, value in updates.items():
        setattr(user, field, value)
    if password is not None:
        user.hashed_password = hash_password(password)

    await db.commit()
    await db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db)) -> None:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    await db.delete(user)
    await db.commit()
