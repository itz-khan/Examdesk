import os
import socket
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    # Application
    APP_NAME: str = "ExamDesk"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    WORKERS: int = 1
    # Identifies this backend process behind a load balancer.
    # Set differently per EC2/container (e.g. INSTANCE_ID=backend-1).
    # If empty, falls back to hostname so each machine is still distinct.
    INSTANCE_ID: Optional[str] = None
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/examdesk"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    # Set true for hosted Postgres (e.g. Neon). Local Docker/Homebrew Postgres: false.
    DATABASE_SSL: bool = False
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    # JWT
    SECRET_KEY: str = "change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    # NEW: how long a refresh-token family can go without being used
    # before /auth/refresh revokes it and forces a fresh login.
    REFRESH_IDLE_TIMEOUT_MINUTES: int = 20
    # Password Reset
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    # CORS
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "https://examdesk-alpha.vercel.app",
        "https://examdesk-mx4f5lked-himanshu-yadav3.vercel.app",
    ]
    # Email
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAILS_FROM_NAME: str = "ExamDesk Platform"
    # File Storage
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 10
    # Certificate
    CERT_SECRET_KEY: str = "cert-verification-secret"

    @property
    def cors_origins(self) -> List[str]:
        if isinstance(self.ALLOWED_ORIGINS, list):
            return self.ALLOWED_ORIGINS
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    @property
    def resolved_instance_id(self) -> str:
        if self.INSTANCE_ID and self.INSTANCE_ID.strip():
            return self.INSTANCE_ID.strip()
        return os.getenv("HOSTNAME") or socket.gethostname()


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()