from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """
    All config via environment variables (.env file). Uses pydantic-settings for:
    - Type safety: missing vars crash at startup, not 10 min later on first DB call
    - Defaults: app works without LLM configured (falls back to templates)
    """
    # Supabase — REST API wrapper around Postgres + PostGIS
    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str

    # LLM — Claude API is primary. Ollama/Groq are fallbacks for offline/cost.
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    llm_provider: str = "anthropic"  # "anthropic" | "ollama" | "groq"
    llm_max_tokens: int = 1024       # briefings are short — 1024 is plenty
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:1b"  # smallest Llama — runs on laptop GPU
    groq_api_key: str = ""

    # Open-Meteo: free weather API, no key required
    open_meteo_base_url: str = "https://api.open-meteo.com/v1"

    # Scheduling — APScheduler intervals (in-process, no Redis/Celery needed)
    briefing_interval_min: int = 15      # AI briefing regeneration cycle
    data_refresh_interval_sec: int = 60  # how often ingestion jobs poll sources
    force_generate_cooldown_sec: int = 120  # rate-limit for manual "generate now" button

    # Simulation mode: enables demo scenario controls in frontend
    simulation_mode: bool = False

    # LLM reliability: if Claude is down, use Python template fallback
    llm_fallback_to_templates: bool = True  # MUST be True for production resilience
    llm_max_retries: int = 2
    llm_timeout_sec: int = 60

    log_level: str = "INFO"
    # CORS: set CORS_ORIGINS=http://localhost:5173,https://yourapp.com in production
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    def model_post_init(self, __context: object) -> None:
        import logging as _logging

        missing = []
        if not self.supabase_url:
            missing.append("SUPABASE_URL")
        if not self.supabase_anon_key:
            missing.append("SUPABASE_ANON_KEY")
        if not self.supabase_service_key:
            missing.append("SUPABASE_SERVICE_KEY")
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}. "
                "Check your .env file."
            )

        # At least one cloud LLM must be configured — Ollama alone is not
        # sufficient for deployed environments where localhost:11434 is unavailable.
        if not self.anthropic_api_key and not self.groq_api_key:
            raise ValueError(
                "At least one LLM provider must be configured: set ANTHROPIC_API_KEY "
                "or GROQ_API_KEY. Ollama is supported as a local fallback but requires "
                "one cloud provider for deployed environments."
            )

        if not self.anthropic_api_key:
            _logging.getLogger(__name__).warning(
                "ANTHROPIC_API_KEY not set — Claude is unavailable. "
                "Briefings will use Groq or Ollama fallback."
            )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings() # type: ignore
