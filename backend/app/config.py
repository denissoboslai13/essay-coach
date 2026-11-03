from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables (or backend/.env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-5-5"
    anthropic_effort: str = "medium"

    database_url: str = "sqlite:///./essay_coach.db"
    cors_origins: str = "http://localhost:5173"

    # Limits enforced by the API before anything reaches the AI
    min_words_for_feedback: int = 50
    max_essay_chars: int = 20_000
    max_issues_per_round: int = 5

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
