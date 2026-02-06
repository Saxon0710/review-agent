"""Custom Middleware"""
import logging
import time
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class LoggingMiddleware(MiddlewareMixin):
    """请求日志中间件"""

    def process_request(self, request):
        """记录请求开始时间"""
        request.start_time = time.time()

    def process_response(self, request, response):
        """记录请求处理时间"""
        if hasattr(request, 'start_time'):
            duration = time.time() - request.start_time
            logger.info(
                f"{request.method} {request.path} - "
                f"Status: {response.status_code} - "
                f"Duration: {duration:.3f}s"
            )
        return response
