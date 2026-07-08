from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    REDIS_URL: str
    RABBITMQ_URL: str

    JWT_SECRET_KEY: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    verify_token_expire_hours: int = 24
    reset_token_expire_hours: int = 1

    # Frontend routes the emailed links point at; the token rides as ?token=.
    EMAIL_VERIFY_URL_BASE: str = "http://localhost:5173/verify-email"
    EMAIL_RESET_URL_BASE: str = "http://localhost:5173/reset-password"

    LOG_LEVEL: str = "INFO"


settings = Settings()
