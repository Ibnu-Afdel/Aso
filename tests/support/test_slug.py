from fastogram.support import slug


def test_basic_slug() -> None:
    assert slug("Laravel Framework") == "laravel-framework"


def test_custom_separator() -> None:
    assert slug("Laravel Framework", "_") == "laravel_framework"


def test_at_sign_dictionary() -> None:
    assert slug("foo@bar") == "foo-at-bar"


def test_transliterates_accents() -> None:
    # NFKD + ASCII-ignore (per the task spec) decomposes precomposed accents ("é" -> "e") but
    # drops letters with no canonical decomposition ("ø" has none), unlike Laravel's full
    # transliteration dictionary.
    assert slug("Café Déjà Vu") == "cafe-deja-vu"
    assert slug("Bjørn Åsmund") == "bjrn-asmund"


def test_collapses_punctuation_and_whitespace() -> None:
    assert slug("  Hello,   World!!  ") == "hello-world"


def test_strips_leading_and_trailing_separators() -> None:
    assert slug("-Hello-") == "hello"


def test_app_name_slug_used_by_session_config() -> None:
    assert slug("FastoGram") + "-session" == "fastogram-session"
