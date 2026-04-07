import logging
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict

class JsonFormatter(logging.Formatter):
    """
    Custom formatter to output logs as JSON strings.
    Essential for professional observability and cloud monitoring.
    """
    def format(self, record: logging.LogRecord) -> str:
        log_payload: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
        }
        
        # Capture extra fields if passed (e.g., query_id, user_id)
        if hasattr(record, "extra_fields"):
            log_payload.update(record.extra_fields)
            
        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_payload, ensure_ascii=False)

def setup_logging(level: str = "INFO"):
    """Configures the root logger with the JSON formatter."""
    # Standard StreamHandler for outputting to console (stdout)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Remove existing handlers to avoid duplicate logs
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
        
    root_logger.addHandler(handler)
    return root_logger

# Initialize logger instance for the entire application
# Import settings lazily to avoid circular imports at module load time
def _get_log_level() -> str:
    try:
        from app.config import settings
        return settings.LOG_LEVEL
    except Exception:
        return "INFO"

logger = setup_logging(level=_get_log_level())

