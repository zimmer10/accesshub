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
