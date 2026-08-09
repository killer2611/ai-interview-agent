"""Application configuration loaded from environment variables using pydantic-settings."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with defaults and environment variable overrides."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- LLM Configuration ---
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_temperature_question: float = 0.7
    llm_temperature_evaluation: float = 0.2
    llm_temperature_feedback: float = 0.3
    llm_max_retries: int = 2
    llm_timeout_seconds: int = 30

    # --- Interview Constraints ---
    min_questions: int = 8
    max_questions: int = 15
    min_covered_days: int = 4
    min_covered_modules: int = 2
    target_questions: int = 10
    max_followups_per_topic: int = 2
    plan_coverage_threshold: float = 0.7

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # --- Paths ---
    curriculum_path: str = "curriculum.json"


settings = Settings()
