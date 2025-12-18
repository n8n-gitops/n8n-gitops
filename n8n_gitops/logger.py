"""Simple logging utility for n8n-gitops CLI."""

import sys
from typing import Any


class Logger:
    """Simple logger that respects verbosity settings."""

    def __init__(self, silent: bool = False, break_on_error: bool = False):
        """Initialize logger.

        Args:
            silent: If True, suppress info messages
            break_on_error: If True, raise SystemExit on error
        """
        self.silent = silent
        self.break_on_error = break_on_error

    def info(self, message: str, **kwargs: Any) -> None:
        """Print info message (suppressed in silent mode).

        Args:
            message: Message to print
            **kwargs: Additional arguments for print()
        """
        if not self.silent:
            print(message, **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Print warning message (always shown).

        Args:
            message: Warning message to print
            **kwargs: Additional arguments for print()
        """
        print(message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Print error message (always shown).

        Args:
            message: Error message to print
            **kwargs: Additional arguments for print()
        """
        # Always print to stderr unless file is explicitly specified
        if "file" not in kwargs:
            kwargs["file"] = sys.stderr

        print(message, **kwargs)

        # Respect break_on_error flag
        if self.break_on_error:
            raise SystemExit(1)

    def critical(self, message: str, **kwargs: Any) -> None:
        """Print critical error message and always exit.

        Args:
            message: Critical error message to print
            **kwargs: Additional arguments for print()
        """
        # Always print to stderr unless file is explicitly specified
        if "file" not in kwargs:
            kwargs["file"] = sys.stderr

        print(message, **kwargs)

        # Always exit on critical errors
        raise SystemExit(1)


# Global logger instance (will be configured by CLI)
_logger: Logger | None = None


def configure(silent: bool = False, break_on_error: bool = False) -> None:
    """Configure the global logger instance.

    Args:
        silent: If True, suppress info messages
        break_on_error: If True, raise SystemExit on error
    """
    global _logger
    _logger = Logger(silent=silent, break_on_error=break_on_error)


def get_logger() -> Logger:
    """Get the global logger instance.

    Returns:
        Logger instance

    Raises:
        RuntimeError: If logger not configured
    """
    if _logger is None:
        # Default logger if not configured
        return Logger()
    return _logger


def info(message: str, **kwargs: Any) -> None:
    """Print info message (suppressed in silent mode).

    Args:
        message: Message to print
        **kwargs: Additional arguments for print()
    """
    get_logger().info(message, **kwargs)


def warning(message: str, **kwargs: Any) -> None:
    """Print warning message (always shown).

    Args:
        message: Warning message to print
        **kwargs: Additional arguments for print()
    """
    get_logger().warning(message, **kwargs)


def error(message: str, **kwargs: Any) -> None:
    """Print error message (always shown).

    Args:
        message: Error message to print
        **kwargs: Additional arguments for print()
    """
    get_logger().error(message, **kwargs)


def critical(message: str, **kwargs: Any) -> None:
    """Print critical error message and always exit.

    Args:
        message: Critical error message to print
        **kwargs: Additional arguments for print()
    """
    get_logger().critical(message, **kwargs)