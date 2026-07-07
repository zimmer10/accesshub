from app.services.group_hierarchy import ancestor_closure


def test_single_group_without_parent() -> None:
    parent_map = {1: None}

    assert ancestor_closure({1}, parent_map) == {1}


def test_simple_chain() -> None:
    # 1 -> 2 -> 3 (1's parent is 2, 2's parent is 3)
    parent_map = {1: 2, 2: 3, 3: None}

    assert ancestor_closure({1}, parent_map) == {1, 2, 3}


def test_multiple_start_groups_union_their_ancestors() -> None:
    # ветка A: 1 -> 2 -> 3 ;  ветка B: 4 -> 5
    parent_map = {1: 2, 2: 3, 3: None, 4: 5, 5: None}

    assert ancestor_closure({1, 4}, parent_map) == {1, 2, 3, 4, 5}


def test_overlapping_ancestors_are_not_duplicated() -> None:
    # 1 -> 3, 2 -> 3 (общий предок 3 для двух разных стартовых групп)
    parent_map = {1: 3, 2: 3, 3: None}

    assert ancestor_closure({1, 2}, parent_map) == {1, 2, 3}


def test_deep_chain() -> None:
    depth = 50
    parent_map = {i: i + 1 for i in range(depth)}
    parent_map[depth] = None

    result = ancestor_closure({0}, parent_map)

    assert result == set(range(depth + 1))


def test_cycle_does_not_cause_infinite_loop() -> None:
    # защита от циклов: если данные всё же испортились (1 -> 2 -> 1),
    # visited-set не даёт уйти в бесконечный обход
    parent_map = {1: 2, 2: 1}

    assert ancestor_closure({1}, parent_map) == {1, 2}


def test_unknown_start_group_returns_itself_only() -> None:
    # группы нет в parent_map (например, только что удалена) — просто нет предков
    assert ancestor_closure({999}, {}) == {999}


def test_empty_start_set() -> None:
    assert ancestor_closure(set(), {1: None}) == set()
