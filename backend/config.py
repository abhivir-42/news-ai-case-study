from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gnews_api_key: SecretStr
    openai_api_key: SecretStr
    database_url: SecretStr

    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"


settings = Settings()
