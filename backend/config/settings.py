"""
配置系统 - 基于 Dynaconf 集中配置管理
"""
from pathlib import Path
from dynaconf import Dynaconf
from typing import Any, Dict, List, Optional

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 创建 Dynaconf 设置实例
settings = Dynaconf(
    envvar_prefix="REVIEW_AGENT",           # 环境变量前缀
    settings_files=[
        BASE_DIR / "config" / "defaults.yaml",
        BASE_DIR / "config" / "secrets.yaml",
    ],
    merge_enabled=True,                      # 启用配置合并
    environments=True,                       # 启用环境切换
    env_switcher="ENV",                      # 环境切换变量
    encoding="utf-8",
)


class Config:
    """配置访问器"""

    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        """获取配置值"""
        return settings.get(key, default)

    @classmethod
    def set(cls, key: str, value: Any) -> None:
        """设置配置值"""
        settings.set(key, value)

    # ========== 应用配置 ==========
    @property
    def app_name(self) -> str:
        return settings.get("app.name", "Review Agent")

    @property
    def app_version(self) -> str:
        return settings.get("app.version", "1.0.0")

    @property
    def debug(self) -> bool:
        return settings.get("app.debug", False)

    @property
    def env(self) -> str:
        return settings.get("ENV", "development")

    # ========== 数据库配置 ==========
    @property
    def database(self) -> Dict[str, Any]:
        return {
            "engine": settings.get("database.engine", "postgresql"),
            "host": settings.get("database.host", "localhost"),
            "port": settings.get("database.port", 5432),
            "name": settings.get("database.name", "review_agent"),
            "user": settings.get("database.user", "review_agent"),
            "password": settings.get("database.password", ""),
            "pool_size": settings.get("database.pool_size", 20),
            "max_overflow": settings.get("database.max_overflow", 10),
        }

    def database_url(self, async_mode: bool = False) -> str:
        """获取数据库连接 URL"""
        db = self.database
        if async_mode:
            return f"postgresql+asyncpg://{db['user']}:{db['password']}@{db['host']}:{db['port']}/{db['name']}"
        return f"postgresql://{db['user']}:{db['password']}@{db['host']}:{db['port']}/{db['name']}"

    # ========== Redis 配置 ==========
    @property
    def redis(self) -> Dict[str, Any]:
        return {
            "host": settings.get("redis.host", "localhost"),
            "port": settings.get("redis.port", 6379),
            "db": settings.get("redis.db", 0),
            "password": settings.get("redis.password", None),
            "cache_ttl": settings.get("redis.cache_ttl", 3600),
        }

    def redis_url(self) -> str:
        """获取 Redis 连接 URL"""
        r = self.redis
        password_part = f":{r['password']}@" if r['password'] else ""
        return f"redis://{password_part}{r['host']}:{r['port']}/{r['db']}"

    # ========== GitLab 配置 ==========
    @property
    def gitlab(self) -> Dict[str, Any]:
        return {
            "url": settings.get("gitlab.url", "https://gitlab.com"),
            "timeout": settings.get("gitlab.timeout", 30),
            "max_retries": settings.get("gitlab.max_retries", 3),
            "ssl_verify": settings.get("gitlab.ssl_verify", True),
            "app_id": settings.get("gitlab.app_id", ""),
            "app_secret": settings.get("gitlab.app_secret", ""),
            "personal_access_token": settings.get("gitlab.personal_access_token", ""),
        }

    # ========== AI 配置 ==========
    @property
    def ai(self) -> Dict[str, Any]:
        return {
            "provider": settings.get("ai.provider", "litellm"),
            "model": settings.get("ai.model", "gpt-4o"),
            "fallback_models": settings.get("ai.fallback_models", ["gpt-4o-mini"]),
            "temperature": settings.get("ai.temperature", 0.2),
            "max_tokens": settings.get("ai.max_tokens", 16000),
            "timeout": settings.get("ai.timeout", 120),
            "openai_api_key": settings.get("ai.openai_api_key", ""),
            "anthropic_api_key": settings.get("ai.anthropic_api_key", ""),
        }

    # ========== 审查配置 ==========
    @property
    def review(self) -> Dict[str, Any]:
        return {
            "auto_review_on_open": settings.get("review.auto_review_on_open", False),
            "auto_review_commands": settings.get("review.auto_review_commands", ["/describe", "/review"]),
            "auto_review_on_push": settings.get("review.auto_review_on_push", False),
            "auto_review_push_commands": settings.get("review.auto_review_push_commands", ["/review"]),
            "ignore_draft": settings.get("review.ignore_draft", True),
            "ignore_title_patterns": settings.get("review.ignore_title_patterns", []),
            "ignore_branch_patterns": settings.get("review.ignore_branch_patterns", []),
            "ignore_label_patterns": settings.get("review.ignore_label_patterns", []),
            "max_concurrent_tasks": settings.get("review.max_concurrent_tasks", 5),
        }

    # ========== 日志配置 ==========
    @property
    def logging(self) -> Dict[str, Any]:
        return {
            "level": settings.get("logging.level", "INFO"),
            "format": settings.get("logging.format", "json"),
            "output": settings.get("logging.output", "stdout"),
        }

    # ========== Celery 配置 ==========
    @property
    def celery(self) -> Dict[str, Any]:
        return {
            "broker_url": settings.get("celery.broker_url", self.redis_url()),
            "result_backend": settings.get("celery.result_backend", self.redis_url()),
            "task_serializer": settings.get("celery.task_serializer", "json"),
            "result_serializer": settings.get("celery.result_serializer", "json"),
            "accept_content": settings.get("celery.accept_content", ["json"]),
            "timezone": settings.get("celery.timezone", "Asia/Shanghai"),
            "enable_utc": settings.get("celery.enable_utc", True),
            "task_track_started": settings.get("celery.task_track_started", True),
            "task_time_limit": settings.get("celery.task_time_limit", 3600),
        }

    # ========== 安全配置 ==========
    @property
    def secret_key(self) -> str:
        return settings.get("secret_key", "CHANGE_ME_IN_PRODUCTION")

    @property
    def allowed_hosts(self) -> List[str]:
        return settings.get("allowed_hosts", ["localhost", "127.0.0.1"])

    @property
    def cors_origins(self) -> List[str]:
        return settings.get("cors_origins", ["http://localhost:8000", "http://localhost:3000"])


# 全局配置实例
config = Config()


def get_config() -> Config:
    """获取配置实例"""
    return config
