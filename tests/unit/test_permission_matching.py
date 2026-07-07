from app.services.permissions import permission_matches


def test_exact_match() -> None:
    assert permission_matches({"invoice:read"}, "invoice:read")


def test_wildcard_matches_specific_action() -> None:
    assert permission_matches({"invoice:*"}, "invoice:read")
    assert permission_matches({"invoice:*"}, "invoice:write")


def test_wildcard_does_not_match_different_resource() -> None:
    assert not permission_matches({"invoice:*"}, "report:read")


def test_no_match_when_permission_not_granted() -> None:
    assert not permission_matches({"invoice:read"}, "invoice:write")


def test_empty_granted_set_never_matches() -> None:
    assert not permission_matches(set(), "invoice:read")


def test_unrelated_wildcard_does_not_match_by_accident() -> None:
    # "invoice:re*" не должно трактоваться как wildcard-префикс для "invoice:read" —
    # поддерживается только ровно "resource:*"
    assert not permission_matches({"invoice:re*"}, "invoice:read")
