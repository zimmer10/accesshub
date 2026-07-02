from app.core.security import hash_password, verify_password


def test_hash_password_is_not_plaintext() -> None:
    hashed = hash_password("correct horse battery staple")

    assert hashed != "correct horse battery staple"


def test_verify_password_accepts_correct_password() -> None:
    hashed = hash_password("correct horse battery staple")

    assert verify_password("correct horse battery staple", hashed)


def test_verify_password_rejects_wrong_password() -> None:
    hashed = hash_password("correct horse battery staple")

    assert not verify_password("wrong password", hashed)


def test_hash_password_uses_random_salt() -> None:
    password = "correct horse battery staple"

    assert hash_password(password) != hash_password(password)
