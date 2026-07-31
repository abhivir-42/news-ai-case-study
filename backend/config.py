"""Configuration, read from the environment and validated at import.

Every value is checked when `settings = Settings()` runs, so a missing key is a
startup crash with the field name rather than a confusing failure mid-request.
Secrets are SecretStr, which renders as ********** in logs and tracebacks; call
.get_secret_value() to read them. Fields with a default are optional config;
fields without one are required.
"""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    gnews_api_key: SecretStr
    openai_api_key: SecretStr
    database_url: SecretStr

    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # POST /api/analyses spends OpenAI money, so it gets the tighter budget.
    analyse_rate_limit_per_hour: int = 20
    search_rate_limit_per_minute: int = 30
    # Only trust X-Forwarded-For when a proxy you control sets it. Render does.
    trust_forwarded_for: bool = True


settings = Settings()
