"""
Django Production Settings
"""
from .base import *

# ========== 生产环境特定配置 ==========
DEBUG = False

# ========== 安全配置 ==========
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# ========== 白噪声静态文件服务 ==========
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# ========== 错误报告 ==========
# Sentry 配置 (如果可用)
try:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from config.settings import config

    sentry_dsn = config.get('sentry.dsn')
    if sentry_dsn:
        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[DjangoIntegration()],
            environment=config.env,
            traces_sample_rate=0.1,
        )
except ImportError:
    pass
