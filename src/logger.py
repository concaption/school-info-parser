"""
path: src/logger.py
author: concaption
description: This script contains the setup_logging function that configures the logging for the application.
"""

import logging
import os
import sys
from colorlog import ColoredFormatter


# Set up logging
def setup_logging():
    """Setup logging configuration with colored output and detailed formatting"""
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)

    # Create logger
    logger = logging.getLogger("school-info-parser")

    # Avoid duplicate logs
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    # Create console handler with colored formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    # Create file handler
    file_handler = logging.FileHandler("logs/app.log")
    file_handler.setLevel(logging.INFO)

    # Create formatters
    console_formatter = ColoredFormatter(
        "%(cyan)s%(asctime)s%(reset)s | "
        "%(log_color)s%(levelname)-8s%(reset)s | "
        "%(blue)s%(filename)s:%(lineno)d%(reset)s | "
        "%(log_color)s%(message)s%(reset)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        reset=True,
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        },
    )

    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler.setFormatter(console_formatter)
    file_handler.setFormatter(file_formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    # Prevent logs from being passed to parent loggers
    logger.propagate = False

    return logger
