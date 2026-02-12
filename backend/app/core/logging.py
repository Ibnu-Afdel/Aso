from app.bootstrap.logging import configure_logging
from app.core.config import get_settings


def setup_logging() -> None:
    configure_logging(get_settings())
