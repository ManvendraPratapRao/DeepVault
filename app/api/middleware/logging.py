import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.infrastructure.logging.structured import logger


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to inject a unique Request ID into every call and log
    the performance/status of the response.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # 1. Generate a unique Correlation ID for this request
        request_id = str(uuid.uuid4())

        # 2. Attach it to request state so routes/services can access it if needed
        request.state.request_id = request_id

        start_time = time.perf_counter()

        try:
            # 3. Process the actual request
            response = await call_next(request)

            # 4. Measure latency (fix: added parentheses for correct math)
            process_time = (time.perf_counter() - start_time) * 1000

            # 5. Log the outcome with the request ID
            logger.info(
                f"{request.method} {request.url.path} -> {response.status_code} in {process_time:.2f}ms",
                extra={
                    "extra_fields": {
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": response.status_code,
                        "latency_ms": process_time,
                    }
                },
            )

            # 6. Return the request ID to the client in headers
            response.headers["X-Request-ID"] = request_id
            return response

        except Exception as e:
            process_time = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"Unhandled error: {str(e)}",
                extra={"extra_fields": {"request_id": request_id, "latency_ms": process_time}},
            )
            raise
