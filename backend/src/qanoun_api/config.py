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
    cors_origins: tuple[str, ...] = ("http://localhost:3000", "http://127.0.0.1:3000")
    rewrite_cache: Path = Path("data/processed/rewrites.json")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            db_url=os.environ.get("QANOUN_DB_URL", DEFAULT_DB),
            embed_model=os.environ.get("QANOUN_EMBED_MODEL", DEFAULT_EMBED_MODEL),
            device=os.environ.get("QANOUN_DEVICE", "cpu"),
            reranker=os.environ.get("QANOUN_RERANKER", "").strip(),
            allow_signup=_flag("QANOUN_ALLOW_SIGNUP", True),
            cookie_secure=_flag("QANOUN_COOKIE_SECURE", False),
            cors_origins=tuple(
                o.strip().rstrip("/")
                for o in os.environ.get(
                    "QANOUN_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
                ).split(",")
                if o.strip()
            ),
        )


SETTINGS = Settings.from_env()
