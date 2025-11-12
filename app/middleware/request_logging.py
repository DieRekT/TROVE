"""Request logging middleware for structured logging."""

import logging
import time
from typing import Callable
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.utils.logging import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log HTTP requests with structured data."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log with structured data."""
        # Generate request ID
        request_id = str(uuid4())
        request.state.request_id = request_id
        
        # Set request ID on logger
        logger.set_request_id(request_id)
        
        # Extract request info
        method = request.method
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "unknown")
        
        # Start timer
        start_time = time.time()
        
        # Log request start
        logger.info(
            f"{method} {path}",
            extra={
                "endpoint": path,
                "method": method,
                "client_ip": client_ip,
                "user_agent": user_agent,
            }
        )
        
        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
            
            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000
            
            # Log response
            log_level = logging.INFO if status_code < 400 else logging.WARNING
            logger.log(
                log_level,
                f"{method} {path} {status_code}",
                extra={
                    "endpoint": path,
                    "method": method,
                    "status_code": status_code,
                    "duration_ms": round(duration_ms, 2),
                    "client_ip": client_ip,
                }
            )
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            # Calculate duration even on error
            duration_ms = (time.time() - start_time) * 1000
            
            # Log error
            logger.error(
                f"{method} {path} ERROR: {str(e)}",
                extra={
                    "endpoint": path,
                    "method": method,
                    "status_code": 500,
                    "duration_ms": round(duration_ms, 2),
                    "client_ip": client_ip,
                    "error": str(e),
                },
                exc_info=True
            )
            raise

