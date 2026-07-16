"""Configuration du logging pour le projet."""

import logging
import os

_LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"


def get_logger(name: str) -> logging.Logger:
    """Retourne un logger configuré, sans dupliquer les handlers."""
    logger = logging.getLogger(name)

    if not logger.handlers:
        level = os.getenv("LOG_LEVEL", "INFO").upper()
        logger.setLevel(level)

        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        logger.addHandler(handler)

        # Evite la propagation vers le root logger (double affichage)
        logger.propagate = False

    return logger
