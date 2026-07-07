from fastapi import FastAPI

from app.api.access import router as access_router
from app.api.auth import router as auth_router
from app.api.groups import router as groups_router
from app.api.permissions import router as permissions_router
from app.api.roles import router as roles_router
from app.api.users import router as users_router
from app.core.config import settings

app = FastAPI(title=settings.app_name, debug=settings.debug)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(groups_router)
app.include_router(roles_router)
app.include_router(permissions_router)
app.include_router(access_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": settings.app_name, "status": "ok"}
