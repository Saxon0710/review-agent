"""
FastAPI 依赖注入
"""
from fastapi import Depends, Header, HTTPException, status
from typing import Optional
import jwt
from datetime import datetime, timedelta

from config.settings import config


# ========== JWT Token 管理 ==========
class TokenManager:
    """JWT Token 管理"""

    SECRET_KEY = config.secret_key
    ALGORITHM = "HS256"

    @classmethod
    def create_token(cls, user_id: int, extra_data: dict = None) -> str:
        """创建访问 Token"""
        payload = {
            "user_id": user_id,
            "exp": datetime.utcnow() + timedelta(days=7),
            "iat": datetime.utcnow(),
        }
        if extra_data:
            payload.update(extra_data)
        return jwt.encode(payload, cls.SECRET_KEY, algorithm=cls.ALGORITHM)

    @classmethod
    def verify_token(cls, token: str) -> dict:
        """验证 Token"""
        try:
            payload = jwt.decode(token, cls.SECRET_KEY, algorithms=[cls.ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )


# ========== Webhook 认证 ==========
async def verify_gitlab_webhook(
    x_gitlab_token: Optional[str] = Header(None, alias="X-Gitlab-Token"),
) -> bool:
    """验证 GitLab Webhook 请求"""
    if not config.gitlab["webhook_secret"]:
        # 如果没有配置密钥，跳过验证
        return True

    if not x_gitlab_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Gitlab-Token header",
        )

    # TODO: 实际项目中应该使用 HMAC 验证
    # 现在简单比较
    if x_gitlab_token != config.gitlab["webhook_secret"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook token",
        )

    return True


# ========== 认证依赖 ==========
async def get_current_user(
    authorization: Optional[str] = Header(None),
) -> dict:
    """获取当前用户"""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )

    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme",
            )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format",
        )

    payload = TokenManager.verify_token(token)
    return payload


# ========== 可选认证 ==========
async def get_current_user_optional(
    authorization: Optional[str] = Header(None),
) -> Optional[dict]:
    """获取当前用户 (可选)"""
    if not authorization:
        return None

    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            return None
        return TokenManager.verify_token(token)
    except (ValueError, HTTPException):
        return None
