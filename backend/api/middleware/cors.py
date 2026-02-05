"""FastAPI 中间件 - CORS 配置"""
from fastapi.middleware.cors import CORSMiddleware
from config.settings import config


cors_config = {
    "allow_origins": config.cors_origins,
    "allow_credentials": True,
    "allow_methods": ["*"],
    "allow_headers": ["*"],
}
