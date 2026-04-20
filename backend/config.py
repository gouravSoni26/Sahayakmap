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
    # CORS: Vite dev server (5173) and potential alternate port (3000)
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
