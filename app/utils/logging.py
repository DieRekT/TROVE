"""Structured logging configuration for the Trove application."""

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import uuid4


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra context if present
        if hasattr(record, "extra"):
            log_data.update(record.extra)
        
        # Add request context if present
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "endpoint"):
            log_data["endpoint"] = record.endpoint
        if hasattr(record, "method"):
            log_data["method"] = record.method
        if hasattr(record, "status_code"):
            log_data["status_code"] = record.status_code
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        if hasattr(record, "client_ip"):
            log_data["client_ip"] = record.client_ip
        if hasattr(record, "user_agent"):
            log_data["user_agent"] = record.user_agent
        
        return json.dumps(log_data, ensure_ascii=False)


class StructuredLogger:
    """Wrapper for structured logging with context."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self._request_id: Optional[str] = None
    
    def set_request_id(self, request_id: str) -> None:
        """Set request ID for this logger instance."""
        self._request_id = request_id
    
    def _log_with_context(
        self,
        level: int,
        message: str,
        *args,
        extra: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> None:
        """Log with request context."""
        log_extra = extra or {}
        if self._request_id:
            log_extra["request_id"] = self._request_id
        self.logger.log(level, message, *args, extra=log_extra, **kwargs)
    
    def debug(self, message: str, *args, **kwargs) -> None:
        """Log debug message."""
        extra = kwargs.pop("extra", {})
        self._log_with_context(logging.DEBUG, message, *args, extra=extra, **kwargs)
    
    def info(self, message: str, *args, **kwargs) -> None:
        """Log info message."""
        extra = kwargs.pop("extra", {})
        self._log_with_context(logging.INFO, message, *args, extra=extra, **kwargs)
    
    def warning(self, message: str, *args, **kwargs) -> None:
        """Log warning message."""
        extra = kwargs.pop("extra", {})
        self._log_with_context(logging.WARNING, message, *args, extra=extra, **kwargs)
    
    def error(self, message: str, *args, **kwargs) -> None:
        """Log error message."""
        extra = kwargs.pop("extra", {})
        self._log_with_context(logging.ERROR, message, *args, extra=extra, **kwargs)
    
    def log(self, level: int, message: str, *args, **kwargs) -> None:
        """Log message at specified level."""
        extra = kwargs.pop("extra", {})
        self._log_with_context(level, message, *args, extra=extra, **kwargs)
    
    def exception(self, message: str, *args, **kwargs) -> None:
        """Log exception with traceback."""
        extra = kwargs.pop("extra", {})
        self.logger.exception(message, *args, extra=extra, **kwargs)


def setup_logging(
    level: str = "INFO",
    json_format: bool = True,
    log_file: Optional[str] = None
) -> None:
    """
    Set up structured logging for the application.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_format: Use JSON formatting (True) or plain text (False)
        log_file: Optional file path to write logs to
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Clear existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(log_level)
    
    # Create formatter
    if json_format:
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Set levels for third-party loggers
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance."""
    return StructuredLogger(name)

