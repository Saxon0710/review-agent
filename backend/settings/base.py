"""
Django Base Settings
使用 Dynaconf 进行集中配置管理
"""
from pathlib import Path
import sys

# 将项目根目录添加到 Python 路径
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# 导入配置系统
from config.settings import config

# ========== 安全配置 ==========
SECRET_KEY = config.secret_key
ALLOWED_HOSTS = config.allowed_hosts

# ========== 应用配置 ==========
DEBUG = config.debug
INSTALLED_APPS = [
    # Django 内置应用
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # 第三方应用
    'django_extensions',
    'rest_framework',
    'corsheaders',
    'django_filters',
    'admin_auto_filters',

    # 项目应用
    'core.apps.CoreConfig',
    'web.apps.WebConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # 静态文件服务
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',  # CORS 支持
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.LoggingMiddleware',  # 自定义日志中间件
]

ROOT_URLCONF = 'urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'web' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.config_context',  # 自定义配置上下文
            ],
        },
    },
]

WSGI_APPLICATION = 'wsgi.application'

# ========== 数据库配置 ==========
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config.database['name'],
        'USER': config.database['user'],
        'PASSWORD': config.database['password'],
        'HOST': config.database['host'],
        'PORT': config.database['port'],
        'CONN_MAX_AGE': config.database.get('conn_max_age', 600),
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}

# ========== 缓存配置 ==========
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config.redis_url(),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'PARSER_CLASS': 'redis.connection.HiredisParser',
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'CONNECTION_POOL_KWARGS': {'max_connections': 100},
            'IGNORE_EXCEPTIONS': True,  # 缓存故障不影响业务
        },
        'KEY_PREFIX': 'review_agent',
        'TIMEOUT': config.redis['cache_ttl'],
    }
}

# ========== 密码验证 ==========
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ========== 国际化 ==========
LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

# ========== 静态文件 ==========
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'web' / 'static']

# ========== 媒体文件 ==========
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ========== 默认主键类型 ==========
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ========== REST Framework 配置 ==========
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
}

# ========== CORS 配置 ==========
CORS_ALLOWED_ORIGINS = config.cors_origins
CORS_ALLOW_CREDENTIALS = True

# ========== Celery 配置 ==========
CELERY_BROKER_URL = config.celery['broker_url']
CELERY_RESULT_BACKEND = config.celery['result_backend']
CELERY_TASK_SERIALIZER = config.celery['task_serializer']
CELERY_RESULT_SERIALIZER = config.celery['result_serializer']
CELERY_ACCEPT_CONTENT = config.celery['accept_content']
CELERY_TIMEZONE = config.celery['timezone']
CELERY_ENABLE_UTC = config.celery['enable_utc']
CELERY_TASK_TRACK_STARTED = config.celery['task_track_started']
CELERY_TASK_TIME_LIMIT = config.celery['task_time_limit']
CELERY_WORKER_PREFETCH_MULTIPLIER = config.celery.get('worker_prefetch_multiplier', 1)
CELERY_WORKER_MAX_TASKS_PER_CHILD = config.celery.get('worker_max_tasks_per_child', 1000)

# ========== 日志配置 ==========
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple' if config.logging['format'] == 'text' else 'json',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'review-agent.log',
            'maxBytes': 1024 * 1024 * 100,  # 100MB
            'backupCount': 10,
            'formatter': 'json' if config.logging['format'] == 'json' else 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': config.logging['level'],
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': config.logging['level'],
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'review_agent': {
            'handlers': ['console', 'file'] if config.logging['output'] == 'file' else ['console'],
            'level': config.logging['level'],
            'propagate': False,
        },
    },
}

# ========== 自定义配置 ==========
# 将配置系统暴露给模板
def config_context(request):
    """模板上下文处理器 - 注入配置"""
    from config.settings import config
    return {
        'config': config,
        'app_name': config.app_name,
        'app_version': config.app_version,
    }

# ========== 登录/重定向配置 ==========
LOGIN_URL = '/admin/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/admin/login/'

# ========== CSRF 配置 ==========
CSRF_TRUSTED_ORIGINS = config.cors_origins

# ========== 会话配置 ==========
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_AGE = 7 * 24 * 60 * 60  # 7 天
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
