"""Environment configuration (QANOUN_* variables, see .env.example). LLM providers and
their keys are read by qanoun_api.rag.providers."""

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DB = "postgresql+psycopg://qanoun:qanoun@localhost:5433/qanoun"
DEFAULT_EMBED_MODEL = "BAAI/bge-m3"


@dataclass(frozen=True)
class Settings:
    db_url: str = DEFAULT_DB
    embed_model: str = DEFAULT_EMBED_MODEL
    device: str = "cpu"
    rewrite_cache: Path = Path("data/processed/rewrites.json")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            db_url=os.environ.get("QANOUN_DB_URL", DEFAULT_DB),
            embed_model=os.environ.get("QANOUN_EMBED_MODEL", DEFAULT_EMBED_MODEL),
            device=os.environ.get("QANOUN_DEVICE", "cpu"),
        )


SETTINGS = Settings.from_env()
