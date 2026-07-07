from pydantic import BaseModel, ConfigDict, Field

from app.schemas.permission import PermissionRead


class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=255)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=255)


class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    permissions: list[PermissionRead]


class RolePermissionAdd(BaseModel):
    permission_id: int


class RoleAssign(BaseModel):
    role_id: int
