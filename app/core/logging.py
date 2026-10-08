import logging
import sys

from app.core.config import get_settings


def setup_logging() -> logging.Logger:
    """Configure and return root logger with structured formatting."""
    settings = get_settings()
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    )
    date_format = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )

    logger = logging.getLogger("aereo_geospatial")
    logger.setLevel(log_level)
    return logger


logger = setup_logging()
