from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="BOKIO_")

    api_token: str
    base_url: str = "https://api.bokio.se/v1"
    company_id: str | None = None


settings = Settings()
