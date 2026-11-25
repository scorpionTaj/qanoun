"""Environment configuration (QANOUN_* variables, see .env.example). LLM providers and
their keys are read by qanoun_api.rag.providers."""

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DB = "postgresql+psycopg://qanoun:qanoun@localhost:5433/qanoun"
DEFAULT_EMBED_MODEL = "BAAI/bge-m3"


def _flag(name: str, default: bool) -> bool:
    value = os.environ.get(name, "").strip().lower()
    return default if not value else value in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    db_url: str = DEFAULT_DB
    embed_model: str = DEFAULT_EMBED_MODEL
    device: str = "cpu"
    reranker: str = ""  # cross-encoder model id; empty = no reranking
    allow_signup: bool = True  # public server: false, and create users with `make user`
    cookie_secure: bool = False  # true behind HTTPS (production)
    trust_proxy: bool = False  # rate-limit by X-Forwarded-For (only behind a proxy that sets it)
    log_questions: bool = False  # keep question text in query_log (tell your users if on)
    cors_origins: tuple[str, ...] = ("http://localhost:3000", "http://127.0.0.1:3000")
    telegram_token: str = ""  # @BotFather token: turns the Telegram bot on
    web_url: str = ""  # the web app's address: MCP results link to its reader (empty: no links)
    rewrite_cache: Path = Path("data/processed/rewrites.json")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            db_url=os.environ.get("QANOUN_DB_URL", DEFAULT_DB),
            embed_model=os.environ.get("QANOUN_EMBED_MODEL", DEFAULT_EMBED_MODEL),
            device=os.environ.get("QANOUN_DEVICE", "cpu"),
            reranker=os.environ.get("QANOUN_RERANKER", "").strip(),
            # Serverless hosts allow writes only under /tmp.
            rewrite_cache=Path(os.environ.get("QANOUN_REWRITE_CACHE", "data/processed/rewrites.json")),
            allow_signup=_flag("QANOUN_ALLOW_SIGNUP", True),
            cookie_secure=_flag("QANOUN_COOKIE_SECURE", False),
            trust_proxy=_flag("QANOUN_TRUST_PROXY", False),
            log_questions=_flag("QANOUN_LOG_QUESTIONS", False),
            web_url=os.environ.get("QANOUN_WEB_URL", "").strip().rstrip("/"),
            telegram_token=os.environ.get("QANOUN_TELEGRAM_TOKEN", "").strip(),
            cors_origins=tuple(
                o.strip().rstrip("/")
                for o in os.environ.get(
                    "QANOUN_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
                ).split(",")
                if o.strip()
            ),
        )


SETTINGS = Settings.from_env()
