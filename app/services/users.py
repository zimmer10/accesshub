from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models import User


async def create_user(db: AsyncSession, *, username: str, email: str, password: str) -> User:
    existing = await db.scalar(
        select(User).where((User.username == username) | (User.email == email))
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "username or email is already registered")

    user = User(username=username, email=email, hashed_password=hash_password(password))
    db.add(user)
    # flush (без commit) уже назначает id и created_at через RETURNING — коммит
    # делает вызывающий код, чтобы иметь возможность сохранить в той же
    # транзакции ещё и запись audit log
    await db.flush()
    return user
