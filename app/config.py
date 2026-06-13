"""
Phase 2: Configuration Management

Centralizes all environment-driven configuration using pydantic-settings.
Every module in the app imports `settings` from here — no direct os.environ access anywhere.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # --- AI ---
    GEMINI_API_KEY: str = ""

    # --- Jira ---
    JIRA_BASE_URL: str = ""
    JIRA_EMAIL: str = ""
    JIRA_API_TOKEN: str = ""
    JIRA_PROJECT_KEY: str = ""

    # --- Slack ---
    SLACK_BOT_TOKEN: str = ""
    SLACK_SIGNING_SECRET: str = ""
    SLACK_APPROVAL_CHANNEL_ID: str = ""
    SLACK_NOTIFY_CHANNEL_ID: str = ""

    # --- Database ---
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/pipeline.db"

    # --- API Security ---
    PIPELINE_API_KEY: str = ""

    # --- Pipeline Tuning ---
    CONFIDENCE_THRESHOLD: float = 0.80


# Singleton — import this object directly, never instantiate Settings again
settings = Settings()
