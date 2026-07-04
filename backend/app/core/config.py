from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError, field_validator


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


class Settings(BaseModel):
    app_env: str = "development"
    database_url: str = "sqlite:///./interview_agent.db"
    upload_dir: str = "uploads"
    backend_cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    llm_provider: str = "mock"
    openai_api_url: str = "https://api.openai.com/v1/chat/completions"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    elevenlabs_api_key: str | None = None
    elevenlabs_api_url: str = "https://api.elevenlabs.io/v1"
    elevenlabs_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"
    elevenlabs_tts_model: str = "eleven_multilingual_v2"
    elevenlabs_stt_model: str = "scribe_v2"
    azure_openai_api_url: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_api_version: str = "2024-02-15-preview"
    azure_openai_deployment: str | None = None
    claude_api_url: str | None = None
    claude_api_key: str | None = None
    claude_model: str = "claude-3-haiku"
    llm_timeout_seconds: float = 30.0
    admin_username: str = "admin"
    admin_password: str | None = None
    admin_password_hash: str | None = None
    auth_secret_key: str | None = None
    auth_token_minutes: int = 480
    candidate_token_hours: int = 24
    max_resume_upload_bytes: int = 5 * 1024 * 1024

    @field_validator("app_env", "llm_provider", mode="before")
    @classmethod
    def normalize_lowercase(cls, value: str) -> str:
        return str(value or "").strip().lower()

    @field_validator("backend_cors_origins")
    @classmethod
    def validate_cors_origins(cls, origins: list[str]) -> list[str]:
        cleaned = [origin.rstrip("/") for origin in origins if origin.strip()]
        if "*" in cleaned and len(cleaned) > 1:
            raise ValueError("Wildcard CORS origin cannot be combined with explicit origins")
        return cleaned

    @property
    def llm_enabled(self) -> bool:
        provider = self.llm_provider.lower()
        if provider == "openai":
            return bool(self.openai_api_key)
        if provider == "azure_openai":
            return bool(
                self.azure_openai_api_url
                and self.azure_openai_api_key
                and self.azure_openai_deployment
            )
        if provider == "claude":
            return bool(self.claude_api_url and self.claude_api_key)
        return False

    @property
    def claude_enabled(self) -> bool:
        return self.llm_provider.lower() == "claude" and bool(self.claude_api_url and self.claude_api_key)

    @property
    def admin_auth_configured(self) -> bool:
        return bool(self.auth_secret_key and (self.admin_password_hash or self.admin_password))

    @property
    def is_production(self) -> bool:
        return self.app_env in {"production", "prod"}

    def validate_runtime(self) -> None:
        if self.max_resume_upload_bytes < 1:
            raise ValueError("MAX_RESUME_UPLOAD_BYTES must be greater than zero")
        if self.candidate_token_hours < 1:
            raise ValueError("CANDIDATE_TOKEN_HOURS must be greater than zero")
        if self.auth_token_minutes < 1:
            raise ValueError("AUTH_TOKEN_MINUTES must be greater than zero")
        if self.auth_secret_key and len(self.auth_secret_key) < 32:
            raise ValueError("AUTH_SECRET_KEY must be at least 32 characters")
        if self.is_production:
            if "*" in self.backend_cors_origins:
                raise ValueError("Wildcard CORS is not allowed in production")
            if not self.admin_auth_configured:
                raise ValueError("Admin authentication must be configured in production")


def _csv(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    try:
        settings = Settings(
            app_env=os.getenv("APP_ENV", "development"),
            database_url=os.getenv("DATABASE_URL", "sqlite:///./interview_agent.db"),
            upload_dir=os.getenv("UPLOAD_DIR", "uploads"),
            backend_cors_origins=_csv(
                os.getenv("BACKEND_CORS_ORIGINS"),
                ["http://localhost:5173", "http://127.0.0.1:5173"],
            ),
            llm_provider=os.getenv("LLM_PROVIDER", "mock"),
            openai_api_url=os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            elevenlabs_api_key=os.getenv("ELEVENLABS_API_KEY"),
            elevenlabs_api_url=os.getenv("ELEVENLABS_API_URL", "https://api.elevenlabs.io/v1"),
            elevenlabs_voice_id=os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb"),
            elevenlabs_tts_model=os.getenv("ELEVENLABS_TTS_MODEL", "eleven_multilingual_v2"),
            elevenlabs_stt_model=os.getenv("ELEVENLABS_STT_MODEL", "scribe_v2"),
            azure_openai_api_url=os.getenv("AZURE_OPENAI_API_URL"),
            azure_openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
            azure_openai_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
            claude_api_url=os.getenv("CLAUDE_API_URL"),
            claude_api_key=os.getenv("CLAUDE_API_KEY"),
            claude_model=os.getenv("CLAUDE_MODEL", "claude-3-haiku"),
            llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "30")),
            admin_username=os.getenv("ADMIN_USERNAME", "admin"),
            admin_password=os.getenv("ADMIN_PASSWORD"),
            admin_password_hash=os.getenv("ADMIN_PASSWORD_HASH"),
            auth_secret_key=os.getenv("AUTH_SECRET_KEY"),
            auth_token_minutes=int(os.getenv("AUTH_TOKEN_MINUTES", "480")),
            candidate_token_hours=int(os.getenv("CANDIDATE_TOKEN_HOURS", "24")),
            max_resume_upload_bytes=int(os.getenv("MAX_RESUME_UPLOAD_BYTES", str(5 * 1024 * 1024))),
        )
        settings.validate_runtime()
        return settings
    except (TypeError, ValueError, ValidationError) as exc:
        raise RuntimeError(f"Invalid backend configuration: {exc}") from exc
