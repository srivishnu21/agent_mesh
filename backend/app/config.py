from dataclasses import dataclass
from os import environ, getenv
from pathlib import Path


def _load_dotenv() -> None:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


@dataclass(frozen=True)
class Settings:
    DATABASE_URL: str = getenv("DATABASE_URL", "sqlite+aiosqlite:///./agent_platform.db")
    LLM_PROVIDER: str = getenv("LLM_PROVIDER", "anthropic")
    ANTHROPIC_API_KEY: str | None = getenv("ANTHROPIC_API_KEY")
    OPENAI_COMPATIBLE_API_KEY: str = getenv("OPENAI_COMPATIBLE_API_KEY", "ollama")
    OPENAI_COMPATIBLE_BASE_URL: str = getenv("OPENAI_COMPATIBLE_BASE_URL", "http://host.docker.internal:11434/v1")
    OPENAI_COMPATIBLE_MODEL: str = getenv("OPENAI_COMPATIBLE_MODEL", "qwen2.5:7b")
    INPUT_COST_PER_1K: float = float(getenv("INPUT_COST_PER_1K", "0"))
    OUTPUT_COST_PER_1K: float = float(getenv("OUTPUT_COST_PER_1K", "0"))
    TAVILY_API_KEY: str | None = getenv("TAVILY_API_KEY")
    DEFAULT_MODEL: str = getenv("DEFAULT_MODEL", "claude-sonnet-4-5-20250929")
    REQUIRE_ANTHROPIC_ON_STARTUP: bool = getenv("REQUIRE_ANTHROPIC_ON_STARTUP", "true").lower() == "true"
    TELEGRAM_BOT_TOKEN: str | None = getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_MODE: str = getenv("TELEGRAM_MODE", "polling")
    TELEGRAM_WEBHOOK_URL: str | None = getenv("TELEGRAM_WEBHOOK_URL")
    TELEGRAM_DEFAULT_WORKFLOW_ID: str | None = getenv("TELEGRAM_DEFAULT_WORKFLOW_ID")

    def validate_startup(self) -> None:
        if self.LLM_PROVIDER == "anthropic" and self.REQUIRE_ANTHROPIC_ON_STARTUP and not self.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is required. Add it to backend/.env before starting the API.")
        if self.LLM_PROVIDER not in {"anthropic", "openai_compatible"}:
            raise RuntimeError("LLM_PROVIDER must be 'anthropic' or 'openai_compatible'.")


settings = Settings()
