"""
Django Development Settings
"""
from .base import *

# ========== 开发环境特定配置 ==========
DEBUG = True

# 数据库
DATABASES['default']['NAME'] = 'review_agent_dev'

# 允许所有主机（开发环境）
ALLOWED_HOSTS = ['*']
CORS_ALLOW_ALL_ORIGINS = True

# 显示调试工具栏
try:
    import debug_toolbar
    INSTALLED_APPS.append('debug_toolbar')
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
    INTERNAL_IPS = ['127.0.0.1', 'localhost']
except ImportError:
    pass

# 日志级别
LOGGING['loggers']['django']['level'] = 'DEBUG'
LOGGING['loggers']['review_agent']['level'] = 'DEBUG'

# ========== Email 配置 (开发环境使用控制台) ==========
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
