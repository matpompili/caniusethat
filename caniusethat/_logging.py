import logging
import sys


def getLogger(name: str, log_level=logging.INFO) -> logging.Logger:
    """Returns a logger with a default format."""

    logger = logging.getLogger(name)

    logger.handlers.clear()  # Remove any existing handlers

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setLevel(log_level)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s.%(msecs)03d | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    logger.addHandler(handler)
    logger.setLevel(log_level)

    return logger
