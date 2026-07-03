from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    # bcrypt игнорирует байты пароля после 72-го — ограничиваем на входе,
    # чтобы не создавать иллюзию, что более длинный хвост пароля на что-то влияет
    password: str = Field(min_length=8, max_length=72)


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=3, max_length=64)
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8, max_length=72)
    is_active: bool | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    is_active: bool
    created_at: datetime
