from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    REDIS_URL: str
    RABBITMQ_URL: str

    JWT_SECRET_KEY: str
    jwt_algorithm: str = "HS256"

    # Shared secret gating the producer-facing POST /notifications. Trusted
    # producers (chat, admin) send it as X-Service-Token. Empty = the manual
    # HTTP emit path is disabled (broker remains the only producer route).
    SERVICE_TOKEN: str = ""

    # Path to the Firebase service-account JSON file (kept out of git). Empty
    # (or a missing file) disables real FCM sends — the offline path becomes a
    # no-op until credentials are provided.
    FCM_CREDENTIALS_FILE: str = ""

    # SMTP for the email delivery channel. Host/port/TLS default to Gmail's
    # submission endpoint; only the credentials (and sender) come from .env.
    # Empty SMTP_USERNAME/SMTP_PASSWORD disables real sends — the email path
    # becomes a no-op (mirrors FCM_CREDENTIALS_FILE) so the pipeline degrades
    # gracefully until credentials are provided. SMTP_FROM falls back to the
    # username when unset.
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USE_TLS: bool = True
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""

    sse_keepalive_seconds: int = 15


settings = Settings()
