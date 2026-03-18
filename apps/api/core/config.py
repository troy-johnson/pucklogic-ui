from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    supabase_url: str = ""
    supabase_service_role_key: str = ""
    database_url: str = ""
    redis_url: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id: str = ""
    frontend_url: str = "http://localhost:3000"
    environment: str = "development"
    current_season: str = "2025-26"
    yahoo_oauth_refresh_token: str = ""
    fantrax_session_token: str = ""

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()
