import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App Settings
    PROJECT_NAME: str = "Brightloop Subscription Management System"
    VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Security
    SECRET_KEY: str = "dev-secret-key-brightloop-change-in-production-12345"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours for hackathon usability
    RESET_TOKEN_EXPIRE_MINUTES: int = 30

    # Database: SQLite default for zero-setup offline judging; switchable to PostgreSQL in one line
    DATABASE_URL: str = "sqlite:///./brightloop.db"

    # Frontend / CORS
    FRONTEND_URL: str = "http://localhost:5173"

    # SMTP Configuration (Fallback to console output when empty)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    # Initial Admin Seed Credentials
    ADMIN_EMAIL: str = "admin@brightloop.com"
    ADMIN_PASSWORD: str = "Admin@12345"
    ADMIN_NAME: str = "Brightloop Administrator"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
