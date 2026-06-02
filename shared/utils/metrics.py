import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import Response

REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP Requests", ["method", "endpoint", "http_status"]
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds", "HTTP Request Latency", ["method", "endpoint"]
)


class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            raise e
        finally:
            latency = time.time() - start_time
            endpoint = request.url.path
            REQUEST_COUNT.labels(
                method=request.method, endpoint=endpoint, http_status=status_code
            ).inc()
            REQUEST_LATENCY.labels(method=request.method, endpoint=endpoint).observe(
                latency
            )

        return response


def metrics_endpoint(request: Request):
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def setup_metrics(app):
    app.add_middleware(PrometheusMiddleware)
    app.add_route("/metrics", metrics_endpoint, methods=["GET"])
