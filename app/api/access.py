from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models import User
from app.schemas.access import AccessCheckResponse
from app.services.permissions import permission_matches, resolve_effective_permissions

router = APIRouter(prefix="/access", tags=["access"], dependencies=[Depends(get_current_user)])


@router.get("/check", response_model=AccessCheckResponse)
async def check_access(
    user_id: int, permission: str, db: AsyncSession = Depends(get_db)
) -> AccessCheckResponse:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")

    resolved = await resolve_effective_permissions(db, user_id)
    allowed = permission_matches(resolved.permission_codes, permission)
    return AccessCheckResponse(user_id=user_id, permission=permission, allowed=allowed)
