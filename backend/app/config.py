from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://settlement:settlement@localhost:5432/settlement_ai"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3-flash-preview"
    cors_origins: str = "http://localhost:3000"
    jwt_secret: str = "settlement-ai-dev-secret-change-me"
    jwt_expire_minutes: int = 480

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


settings = Settings()
