from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gnews_api_key: SecretStr
    openai_api_key: SecretStr
    database_url: SecretStr


settings = Settings()
