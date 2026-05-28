import logging
import time

from django.utils.deprecation import MiddlewareMixin

from apps.core.logging_utils import get_client_ip


security_logger = logging.getLogger("apps.security")
performance_logger = logging.getLogger("apps.performance")


def should_log_request(request):
    return request.path.startswith("/api/")


class PerformanceLoggingMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if should_log_request(request):
            request.fitsync_start_time = time.perf_counter()
        return None

    def process_response(self, request, response):
        start_time = getattr(request, "fitsync_start_time", None)
        if start_time is not None:
            duration_ms = (time.perf_counter() - start_time) * 1000
            performance_logger.info(
                "[Method:%s - Path:%s - StatusCode:%s - Duration:%.2fms]",
                request.method,
                request.path,
                response.status_code,
                duration_ms,
            )
        return response


class SecurityLoggingMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        if should_log_request(request) and response.status_code in [401, 403]:
            user = getattr(request, "user", None)
            user_id = str(getattr(user, "id", "")) if user and user.is_authenticated else "anonymous"
            security_logger.warning(
                "[User:%s - Method:%s - Path:%s - StatusCode:%s - IP:%s]",
                user_id,
                request.method,
                request.path,
                response.status_code,
                get_client_ip(request),
            )
        return response
