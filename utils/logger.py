"""
Centralized logging configuration for Career Agent.
Provides console and file logging.
"""

import logging
import sys

from config.settings import LOG_DIR, LOG_FILE, LOG_LEVEL


def setup_logger(name: str = "career_agent") -> logging.Logger:
    """
    Sets up and returns a configured logger instance.
    """
    logger = logging.getLogger(name)

    # Avoid duplicate handlers if logger was already created
    if logger.handlers:
        return logger

    # Ensure log directory exists
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        sys.stderr.write(f"Warning: Could not create log directory {LOG_DIR}: {e}\n")

    # Set root level
    numeric_level = getattr(logging, LOG_LEVEL, logging.INFO)
    logger.setLevel(numeric_level)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] (%(name)s) %(filename)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(numeric_level)
    logger.addHandler(console_handler)

    # File Handler
    try:
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(numeric_level)
        logger.addHandler(file_handler)
    except OSError as e:
        sys.stderr.write(f"Warning: Could not attach file handler to {LOG_FILE}: {e}\n")

    return logger


# Default logger instance
logger = setup_logger()
