from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
  model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

  # JWT (shared with Petopia.Backend)
  jwt_secret: str
  jwt_issuer: str
  jwt_algorithm: str

  # MongoDB
  mongodb_url: str
  mongodb_db_name: str

  # Redis (reused from Petopia.Backend)
  redis_url: str

  # CORS
  cors_origins: list[str] = []


settings = Settings()
