from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.associations import group_roles, user_groups
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.role import Role
    from app.models.user import User


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    parent_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("groups.id", ondelete="SET NULL")
    )

    parent: Mapped[Group | None] = relationship(remote_side=[id], back_populates="children")
    children: Mapped[list[Group]] = relationship(back_populates="parent")

    users: Mapped[list[User]] = relationship(secondary=user_groups, back_populates="groups")
    roles: Mapped[list[Role]] = relationship(secondary=group_roles, back_populates="groups")
