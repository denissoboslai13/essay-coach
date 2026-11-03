from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables (or backend/.env)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    # Model for regular users, and for admins (empty = same as regular users)
    anthropic_model: str = "claude-sonnet-5-5"
    anthropic_admin_model: str = ""
    anthropic_effort: str = "medium"

    database_url: str = "sqlite:///./essay_coach.db"
    cors_origins: str = "http://localhost:5173"
    # Set by the Docker image: serve the built frontend from here (see app/site.py)
    frontend_dist: str = ""

    # Login
    google_client_id: str = ""
    # Comma-separated. These accounts need no invite and have no daily limits
    admin_emails: str = ""
    session_days: int = 30
    # True in production (HTTPS). Browsers also accept Secure cookies on http://localhost
    cookie_secure: bool = False
    # Running it on your own machine with your own key: no login, one local account, no daily limits.
    # Refused when cookie_secure is on, and forced off in Docker
    local_mode: bool = False

    # Limits enforced by the API before anything reaches the AI
    min_words_for_feedback: int = 50
    max_essay_chars: int = 20_000
    max_issues_per_round: int = 5

    # Cost limits. Days and months are counted in UTC
    daily_reviews_per_user: int = 10
    daily_disputes_per_user: int = 10
    monthly_budget_usd: float = 10.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def admin_email_set(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
