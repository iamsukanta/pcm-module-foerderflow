"""Structured logging setup."""

import logging
import sys

from app.core.config import settings


def configure_logging() -> None:
    level = logging.DEBUG if settings.debug else logging.INFO
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)-8s %(name)s :: %(message)s")
    )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    logging.getLogger("uvicorn.access").setLevel(level)
