from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models import Permission
from app.schemas.permission import PermissionCreate, PermissionRead

router = APIRouter(
    prefix="/permissions", tags=["permissions"], dependencies=[Depends(get_current_user)]
)


@router.get("", response_model=list[PermissionRead])
async def list_permissions(db: AsyncSession = Depends(get_db)) -> list[Permission]:
    result = await db.scalars(select(Permission).order_by(Permission.id))
    return list(result)


@router.post("", response_model=PermissionRead, status_code=status.HTTP_201_CREATED)
async def create_permission(
    payload: PermissionCreate, db: AsyncSession = Depends(get_db)
) -> Permission:
    existing = await db.scalar(select(Permission).where(Permission.code == payload.code))
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "permission code is already taken")

    permission = Permission(code=payload.code, description=payload.description)
    db.add(permission)
    await db.commit()
    await db.refresh(permission)
    return permission
