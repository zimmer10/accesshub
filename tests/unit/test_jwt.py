import pytest

from app.core.security import TokenError, create_access_token, create_refresh_token, decode_token


def test_access_token_round_trip() -> None:
    token = create_access_token(user_id=42)

    assert decode_token(token, expected_type="access") == 42


def test_refresh_token_round_trip() -> None:
    token = create_refresh_token(user_id=7)

    assert decode_token(token, expected_type="refresh") == 7


def test_access_token_rejected_as_refresh() -> None:
    token = create_access_token(user_id=1)

    with pytest.raises(TokenError):
        decode_token(token, expected_type="refresh")


def test_tampered_token_is_rejected() -> None:
    token = create_access_token(user_id=1)
    header, payload, signature = token.split(".")
    # правим символ из середины подписи: крайний символ base64url иногда
    # кодирует биты, которые декодер всё равно отбрасывает как паддинг
    flipped = "a" if signature[len(signature) // 2] != "a" else "b"
    tampered_signature = (
        signature[: len(signature) // 2] + flipped + signature[len(signature) // 2 + 1 :]
    )
    tampered = f"{header}.{payload}.{tampered_signature}"

    with pytest.raises(TokenError):
        decode_token(tampered, expected_type="access")
