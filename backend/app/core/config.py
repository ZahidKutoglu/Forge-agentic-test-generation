"""Runtime configuration."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Forge — Agentic Test Automation"
    llm_provider: str = Field(default="local")
    llm_model: str = Field(default="gpt-4o")
    openai_api_key: str = Field(default="")
    anthropic_api_key: str = Field(default="")
    pytest_timeout_seconds: int = Field(default=45, ge=5, le=180)
    max_repair_loops: int = Field(default=3, ge=0, le=8)
    cors_origins: str = Field(default="http://localhost:3000,http://127.0.0.1:3000")
    data_dir: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parents[2] / "data" / "reports"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def has_llm_key(self) -> bool:
        provider = self.llm_provider.lower().strip()
        if provider == "openai":
            return bool(self.openai_api_key)
        if provider == "anthropic":
            return bool(self.anthropic_api_key)
        if provider == "auto":
            return bool(self.openai_api_key or self.anthropic_api_key)
        return False

    @property
    def resolved_provider(self) -> str:
        provider = self.llm_provider.lower().strip()
        if provider in {"openai", "anthropic"} and self.has_llm_key:
            return provider
        if provider == "auto":
            if self.openai_api_key:
                return "openai"
            if self.anthropic_api_key:
                return "anthropic"
        return "local"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings
