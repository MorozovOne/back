# app/config.py (фрагмент)
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str = Field(default="postgresql+asyncpg://postgres:postgres@db:5432/storycraft")
    OPENAI_API_KEY: str = Field(default="")
    JWT_SECRET: str = Field(default="change-me")
    JWT_ALG: str = Field(default="HS256")
    JWT_EXPIRES_MINUTES: int = Field(default=7*24*60)

    WELCOME_CREDITS: int = Field(default=100)
    CREDITS_PER_SECOND: int = Field(default=20)

    FRONTEND_ORIGINS: str = Field(default="*")

    STORAGE_BACKEND: str = Field(default="local")
    STORAGE_LOCAL_PATH: str = Field(default="./data/videos")

    S3_BUCKET: Optional[str] = None
    S3_REGION: Optional[str] = None
    S3_ENDPOINT_URL: Optional[str] = None
    S3_ACCESS_KEY: Optional[str] = None
    S3_SECRET_KEY: Optional[str] = None

    # SSL-настройки для БД (теперь поддерживаем disable)
    DB_SSLMODE: Optional[str] = None          # 'disable' | 'require' | 'verify-ca' | 'verify-full'
    DB_SSLROOTCERT: Optional[str] = None

    DEBUG: bool = Field(default=True)

    class Config:
        env_file = ".env"

settings = Settings()
