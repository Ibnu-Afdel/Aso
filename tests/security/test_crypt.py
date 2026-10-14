import pytest

from fastogram.security import DecryptException, crypt
from fastogram.security.keys import generate_key


@pytest.fixture(autouse=True)
def _app_key(monkeypatch):
    key = generate_key()
    monkeypatch.setenv("APP_KEY", key)
    monkeypatch.setattr("fastogram.config.config", lambda k, default=None: key if k == "app.key" else default)
    monkeypatch.delenv("APP_PREVIOUS_KEYS", raising=False)
    yield key


def test_encrypt_decrypt_roundtrip() -> None:
    token = crypt.encrypt("sensitive-api-token")
    assert token != "sensitive-api-token"
    assert crypt.decrypt(token) == "sensitive-api-token"


def test_encrypt_string_decrypt_string_aliases() -> None:
    token = crypt.encrypt_string("hello")
    assert crypt.decrypt_string(token) == "hello"


def test_decrypt_tampered_token_raises() -> None:
    token = crypt.encrypt("secret")
    tampered = token[:-4] + ("A" if token[-4] != "A" else "B") + token[-3:]
    with pytest.raises(DecryptException):
        crypt.decrypt(tampered)


def test_decrypt_garbage_raises() -> None:
    with pytest.raises(DecryptException):
        crypt.decrypt("not-a-real-token")


def test_rotate_reencrypts_with_primary_key(monkeypatch, _app_key) -> None:
    old_key = _app_key
    token = crypt.encrypt("secret")

    new_key = generate_key()
    monkeypatch.setenv("APP_PREVIOUS_KEYS", old_key)
    monkeypatch.setattr("fastogram.config.config", lambda k, default=None: new_key if k == "app.key" else default)

    rotated = crypt.rotate(token)
    assert crypt.decrypt(rotated) == "secret"

    # the rotated token no longer needs the old key: drop it and decryption must still work.
    monkeypatch.delenv("APP_PREVIOUS_KEYS", raising=False)
    assert crypt.decrypt(rotated) == "secret"


def test_decrypt_with_previous_key_after_rotation(monkeypatch, _app_key) -> None:
    old_key = _app_key
    token = crypt.encrypt("secret")

    new_key = generate_key()
    monkeypatch.setenv("APP_PREVIOUS_KEYS", old_key)
    monkeypatch.setattr("fastogram.config.config", lambda k, default=None: new_key if k == "app.key" else default)

    # the old token was encrypted with the now-previous key; decrypt must still succeed.
    assert crypt.decrypt(token) == "secret"
