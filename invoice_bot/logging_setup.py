import os
import sys
from datetime import datetime
from pathlib import Path

from loguru import logger
from rich.console import Console
from rich.logging import RichHandler


def bootstrap():
    """Configure Loguru sinks for console and file output."""
    # Clear any existing handlers
    logger.remove()

    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Generate timestamp for this run
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_file = log_dir / f"invoice_bot-{timestamp}.log"

    # Configure console sink with Rich
    console = Console(highlight=True)
    logger.add(
        RichHandler(console=console, markup=True, rich_tracebacks=True),
        level="INFO",
        format="{message}",
    )

    # Configure JSON lines file sink with rotation
    logger.add(
        log_file,
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {message}",
        rotation="1 day",
        retention="7 days",
        serialize=True,  # Output as JSON
    )

    # Intercept exceptions for better error handling
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            # Don't intercept keyboard interrupt
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logger.opt(exception=(exc_type, exc_value, exc_traceback)).error(
            "Uncaught exception: {0}", exc_value
        )

    sys.excepthook = handle_exception

    # Log environment info
    logger.info("[INIT] invoice_bot starting up")
    logger.info(f"[INIT] Python {sys.version}")
    logger.info(f"[INIT] Log file: {log_file}")

    return logger