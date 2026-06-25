from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
  model_config = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    extra="ignore")

  jwt_secret: str
  jwt_issuer: str
  jwt_algorithm: str

  mongodb_url: str
  mongodb_db_name: str

  redis_url: str

  cors_origins: list[str] = []


settings = Settings()
