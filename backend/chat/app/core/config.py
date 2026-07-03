from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    REDIS_URL: str

    JWT_SECRET_KEY: str
    jwt_algorithm: str = "HS256"

    MESSAGE_MAX_LENGTH: int = 4000
    DEFAULT_PAGE_SIZE: int = 50
    MAX_PAGE_SIZE: int = 100


settings = Settings()
