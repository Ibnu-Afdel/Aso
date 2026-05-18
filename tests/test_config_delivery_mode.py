import pytest

from app.core.config import Settings


def test_polling_mode_does_not_require_webhook_url() -> None:
    settings = Settings(
        bot_enabled=True,
        telegram_bot_token="token",
        telegram_delivery_mode="polling",
        telegram_webhook_url=None,
    )
    assert settings.telegram_delivery_mode == "polling"


def test_webhook_mode_requires_webhook_url() -> None:
    with pytest.raises(ValueError, match="TELEGRAM_WEBHOOK_URL"):
        Settings(
            bot_enabled=True,
            telegram_bot_token="token",
            telegram_delivery_mode="webhook",
            telegram_webhook_url=None,
        )


def test_webhook_mode_accepts_webhook_url() -> None:
    settings = Settings(
        bot_enabled=True,
        telegram_bot_token="token",
        telegram_delivery_mode="webhook",
        telegram_webhook_url="https://example.com/bot/webhook",
    )
    assert settings.telegram_delivery_mode == "webhook"
