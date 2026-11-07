"""Environment configuration (QANOUN_* variables, see .env.example)."""

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DB = "postgresql+psycopg://qanoun:qanoun@localhost:5433/qanoun"
DEFAULT_LLM_URL = "http://localhost:1234/v1"
DEFAULT_EMBED_MODEL = "BAAI/bge-m3"


@dataclass(frozen=True)
class Settings:
    db_url: str = DEFAULT_DB
    llm_url: str = DEFAULT_LLM_URL
    llm_model: str = ""
    llm_key: str = ""
    embed_model: str = DEFAULT_EMBED_MODEL
    device: str = "cpu"
    rewrite_cache: Path = Path("data/processed/rewrites.json")

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            db_url=os.environ.get("QANOUN_DB_URL", DEFAULT_DB),
            llm_url=os.environ.get("QANOUN_LLM_URL", DEFAULT_LLM_URL).rstrip("/"),
            llm_model=os.environ.get("QANOUN_LLM_MODEL", ""),
            llm_key=os.environ.get("QANOUN_LLM_KEY", ""),
            embed_model=os.environ.get("QANOUN_EMBED_MODEL", DEFAULT_EMBED_MODEL),
            device=os.environ.get("QANOUN_DEVICE", "cpu"),
        )


SETTINGS = Settings.from_env()
