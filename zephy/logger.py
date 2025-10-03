"""Logging configuration for Azure TFE Resources Toolkit."""

import logging
import re
from datetime import datetime
from pathlib import Path

# Sensitive data patterns to redact
SENSITIVE_PATTERNS = [
    # TFE tokens
    r'(token["\']?\s*[:=]\s*["\']?)([^"\']+)',
    r"(Authorization:\s*Bearer\s+)([^\s]+)",
    # Azure credentials
    r'(client_secret["\']?\s*[:=]\s*["\']?)([^"\']+)',
    r"(AZURE_CLIENT_SECRET\s*[=:]\s*)([^\s]+)",
    # Generic patterns
    r'(\bsecret["\']?\s*[:=]\s*["\']?)([^"\']+)',
    r'(\bpassword["\']?\s*[:=]\s*["\']?)([^"\']+)',
]


class RedactingFilter(logging.Filter):
    """Logging filter that redacts sensitive data."""

    def filter(self, record):
        """Redact sensitive data from log messages."""
        if hasattr(record, "msg") and record.msg:
            record.msg = redact_sensitive(str(record.msg))
            # Clean up Azure credential error messages
            if ('EnvironmentCredential.get_token failed' in record.msg or
                'ImdsCredential.get_token failed' in record.msg or
                'ManagedIdentityCredential.get_token failed' in record.msg):
                lines = record.msg.split('\n')
                record.msg = lines[0]
                record.exc_text = None
        return True


def redact_sensitive(text: str) -> str:
    """Redact sensitive data from text using regex patterns."""
    for pattern in SENSITIVE_PATTERNS:
        text = re.sub(pattern, r"\1***redacted***", text, flags=re.IGNORECASE)
    return text


def setup_logging(
        debug: bool = False,
        logfile_dir: str = ".") -> logging.Logger:
    """Setup logging configuration with redaction.

    Args:
        debug: Enable debug logging level
        logfile_dir: Directory for log files

    Returns:
        Configured logger instance
    """
    # Determine log level
    level = logging.DEBUG if debug else logging.INFO

    # Create log filename with timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    log_filename = f"zephy_{timestamp}.log"
    log_path = Path(logfile_dir) / log_filename

    # Create formatter
    if debug:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(filename)s:%(funcName)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )

    # Create redacting filter
    redacting_filter = RedactingFilter()

    # Setup file handler
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    file_handler.addFilter(redacting_filter)

    # Setup console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    console_handler.addFilter(redacting_filter)

    # Get root logger and configure
    logger = logging.getLogger()
    logger.setLevel(level)

    # Suppress verbose Azure identity debug logs
    logging.getLogger('azure.identity').setLevel(logging.WARNING)

    # Remove any existing handlers to avoid duplicates
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Add our handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the specified name."""
    return logging.getLogger(name)
