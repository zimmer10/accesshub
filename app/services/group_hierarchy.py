from collections import deque
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Group


async def fetch_parent_map(db: AsyncSession, *, for_update: bool = False) -> dict[int, int | None]:
    query = select(Group.id, Group.parent_group_id)
    if for_update:
        query = query.with_for_update()
    rows = await db.execute(query)
    return {row.id: row.parent_group_id for row in rows}


def ancestor_closure(start_ids: Iterable[int], parent_map: dict[int, int | None]) -> set[int]:
    """BFS вверх по parent_group_id от каждой стартовой группы: возвращает сами
    стартовые группы и всех их предков. visited защищает от зацикливания, даже
    если в данных каким-то образом окажется цикл."""
    visited: set[int] = set()
    queue: deque[int] = deque(start_ids)
    while queue:
        group_id = queue.popleft()
        if group_id in visited:
            continue
        visited.add(group_id)
        parent_id = parent_map.get(group_id)
        if parent_id is not None and parent_id not in visited:
            queue.append(parent_id)
    return visited


def children_map_from_parent_map(parent_map: dict[int, int | None]) -> dict[int, list[int]]:
    children: dict[int, list[int]] = {}
    for group_id, parent_id in parent_map.items():
        if parent_id is not None:
            children.setdefault(parent_id, []).append(group_id)
    return children


def descendant_closure(start_ids: Iterable[int], children_map: dict[int, list[int]]) -> set[int]:
    """BFS вниз по дереву: те же стартовые группы плюс все их потомки. Нужен для
    обратной задачи — не 'какие права видит пользователь', а 'кого затронет
    изменение вот этой группы/роли', при инвалидации кэша и назначении ролей."""
    visited: set[int] = set()
    queue: deque[int] = deque(start_ids)
    while queue:
        group_id = queue.popleft()
        if group_id in visited:
            continue
        visited.add(group_id)
        for child_id in children_map.get(group_id, []):
            if child_id not in visited:
                queue.append(child_id)
    return visited
