from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DOC_TYPE_RULES: dict[str, list[str]] = {
    "faq": ["faq"],
    "manual": ["manual"],
    "troubleshooting": ["troubleshooting", "resolucion", "guia"],
}


class Settings(BaseSettings):
    """Application runtime configuration validated at startup."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="Helpdesk Tickets App")
    app_env: Literal["development", "testing", "production"] = Field(default="development")
    app_host: str = Field(default="0.0.0.0")
    app_port: int = Field(default=8000, ge=1, le=65535)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(default="INFO")
    openai_api_key: SecretStr | None = Field(default=None)

    chromadb_path: Path = Field(default=Path("./chroma_db"))
    docs_path: Path = Field(default=Path("./docs"))
    embeddings_model: str = Field(default="text-embedding-3-large")
    chroma_collection_name: str = Field(default="helpdesk_knowledge")
    rag_chunk_size: int = Field(default=1000, gt=0)
    rag_chunk_overlap: int = Field(default=200, ge=0)
    rag_search_k: int = Field(default=3, gt=0)
    rag_default_doc_type: str = Field(default="general")
    rag_doc_type_rules: dict[str, list[str]] = Field(
        default_factory=lambda: {
            doc_type: list(keywords) for doc_type, keywords in DEFAULT_DOC_TYPE_RULES.items()
        }
    )

    @model_validator(mode="after")
    def validate_rag_chunking(self) -> Self:
        """Ensure chunk overlap is strictly smaller than chunk size."""
        if self.rag_chunk_overlap >= self.rag_chunk_size:
            raise ValueError("rag_chunk_overlap must be smaller than rag_chunk_size")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
