import logging
import sys
from pythonjsonlogger import jsonlogger

from app.core.config import settings


def configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())

    handler = logging.StreamHandler(sys.stdout)
    formatter = jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    handler.setFormatter(formatter)

    root.handlers.clear()
    root.addHandler(handler)
