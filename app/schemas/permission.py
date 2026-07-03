from pydantic import BaseModel, ConfigDict, Field


class PermissionCreate(BaseModel):
    code: str = Field(min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=255)


class PermissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    description: str | None
