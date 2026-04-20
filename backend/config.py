from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str

    # LLM — primary is Claude API, fallbacks are Ollama and Groq
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-20250514"
    llm_provider: str = "anthropic"  # "anthropic" | "ollama" | "groq"
    llm_max_tokens: int = 1024
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:1b"
    groq_api_key: str = ""

    # External APIs
    open_meteo_base_url: str = "https://api.open-meteo.com/v1"

    # Scheduling
    briefing_interval_min: int = 15
    data_refresh_interval_sec: int = 60
    # Cooldown for POST /briefing/generate — should be <= briefing_interval_min * 60
    force_generate_cooldown_sec: int = 120

    # Simulation
    simulation_mode: bool = False

    # LLM reliability
    llm_fallback_to_templates: bool = True
    llm_max_retries: int = 2
    llm_timeout_sec: int = 60

    log_level: str = "INFO"
    cors_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
