from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://funnel:funnel@localhost:5432/funnel"
    # "free" costs nothing and needs no key: regex extraction + keyword scoring.
    # "gemini" uses Google's permanent free tier (no credit card, ~10 req/min).
    # "ollama" runs a local model on your own machine.
    # "anthropic" is the paid path.
    llm_provider: str = "free"

    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    gemini_model: str = "gemini-2.5-flash"

    # Models are pinned per agent: extraction is cheap and high volume, scoring
    # and writing are low volume and worth the spend.
    model_normalizer: str = "claude-haiku-4-5-20251001"
    model_scorer: str = "claude-sonnet-5"
    model_writer: str = "claude-sonnet-5"

    # Hard filters. Change these here, never inside a prompt.
    comp_floor_usd_year: int = 85_000
    require_remote: bool = True
    languages: str = "en,es,pt"

    # Desde donde se puede trabajar. "Remote" y "remote desde donde" son dos
    # preguntas distintas: una parte enorme de los avisos remotos son "US Remote"
    # y exigen estar en Estados Unidos.
    #   global = contrata desde cualquier lado
    #   latam  = menciona LatAm / Brasil / Argentina explicitamente
    # Un aviso que no dice nada ('unknown') NUNCA se rechaza por esto. Si algun
    # dia hay visa o residencia, se agrega el pais aca: "global,latam,us".
    eligible_regions: str = "global,latam"

    obsidian_vault: str = ""   # e.g. /Users/you/Vault
    obsidian_folder: str = "01 - Projects/Job Search"

    daily_llm_budget_usd: float = 2.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def settings() -> Settings:
    return Settings()
