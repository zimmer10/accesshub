from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models import AuditLog
from app.schemas.audit_log import AuditLogRead

router = APIRouter(
    prefix="/audit-log", tags=["audit-log"], dependencies=[Depends(get_current_user)]
)


@router.get("", response_model=list[AuditLogRead])
async def list_audit_log(
    user_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = Query(default=50, gt=0, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[AuditLog]:
    query = select(AuditLog).order_by(AuditLog.created_at.desc())
    if user_id is not None:
        query = query.where(AuditLog.actor_id == user_id)
    if date_from is not None:
        query = query.where(AuditLog.created_at >= date_from)
    if date_to is not None:
        query = query.where(AuditLog.created_at <= date_to)
    query = query.limit(limit).offset(offset)

    result = await db.scalars(query)
    return list(result)
