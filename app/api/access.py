import redis.asyncio as redis
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.cache import get_redis
from app.core.db import get_db
from app.models import User
from app.schemas.access import AccessCheckResponse
from app.services.permission_cache import get_cached_access_check, set_cached_access_check
from app.services.permissions import permission_matches, resolve_effective_permissions

router = APIRouter(prefix="/access", tags=["access"], dependencies=[Depends(get_current_user)])


@router.get("/check", response_model=AccessCheckResponse)
async def check_access(
    user_id: int,
    permission: str,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis),
) -> AccessCheckResponse:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")

    cached = await get_cached_access_check(redis_client, user_id, permission)
    if cached is not None:
        return AccessCheckResponse(user_id=user_id, permission=permission, allowed=cached)

    resolved = await resolve_effective_permissions(db, user_id)
    allowed = permission_matches(resolved.permission_codes, permission)
    await set_cached_access_check(redis_client, user_id, permission, allowed)
    return AccessCheckResponse(user_id=user_id, permission=permission, allowed=allowed)
