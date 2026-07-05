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

    sse_keepalive_seconds: int = 15


settings = Settings()
