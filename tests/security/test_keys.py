import base64

import pytest

from fastogram.security.keys import derive_key, fernet_key, generate_key, parse_app_key


def test_generate_key_format() -> None:
    key = generate_key()
    assert key.startswith("base64:")
    raw = base64.b64decode(key.removeprefix("base64:"))
    assert len(raw) == 32


def test_generate_key_is_random() -> None:
    assert generate_key() != generate_key()


def test_parse_app_key_strips_prefix() -> None:
    key = generate_key()
    raw_b64 = key.removeprefix("base64:")
    assert parse_app_key(key) == parse_app_key(raw_b64)


def test_parse_app_key_empty_raises() -> None:
    with pytest.raises(RuntimeError):
        parse_app_key("")


def test_parse_app_key_bad_base64_raises() -> None:
    with pytest.raises(RuntimeError):
        parse_app_key("base64:not-valid-base64!!")


def test_derive_key_is_deterministic_and_purpose_scoped() -> None:
    key = parse_app_key(generate_key())
    a = derive_key(key, b"purpose-a")
    b = derive_key(key, b"purpose-b")
    assert derive_key(key, b"purpose-a") == a
    assert a != b
    assert len(a) == 32


def test_fernet_key_is_usable() -> None:
    from cryptography.fernet import Fernet

    key = parse_app_key(generate_key())
    token = Fernet(fernet_key(key, b"test-purpose"))
    message = token.encrypt(b"hello")
    assert token.decrypt(message) == b"hello"
