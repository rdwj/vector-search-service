from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    app_name: str = "Vector Search Service"
    app_version: str = "2.0.0"  # Increment for major change to FTS
    debug: bool = False

    # Database configuration
    # Defaults for local development
    # OpenShift: Credentials come from postgres-pgvector-secret
    postgres_host: str = os.getenv("POSTGRES_HOST", "postgres-pgvector")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    postgres_user: str = os.getenv("POSTGRES_USER", "raguser")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "ragpass123")  # Local dev only
    postgres_db: str = os.getenv("POSTGRES_DB", "ragdb")

    # Full-text search configuration
    fts_language: str = os.getenv("FTS_LANGUAGE", "english")
    fts_ranking_normalization: int = int(os.getenv("FTS_RANKING_NORMALIZATION", "32"))

    # DEPRECATED: Embedding service configuration (kept for backward compatibility)
    # These settings are no longer used but preserved to avoid breaking existing configs
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "deprecated")
    embedding_api_url: Optional[str] = os.getenv("EMBEDDING_API_URL", None)
    embedding_api_key: Optional[str] = os.getenv("EMBEDDING_API_KEY", None)
    nomic_api_url: Optional[str] = os.getenv("NOMIC_EMBED_TEXT_1_5_URL")
    nomic_api_key: Optional[str] = os.getenv("NOMIC_EMBED_TEXT_API_KEY")
    nomic_long_text_mode: str = os.getenv("NOMIC_LONG_TEXT_MODE", "truncate")
    nomic_dimensionality: Optional[int] = (
        int(os.getenv("NOMIC_DIMENSIONALITY")) if os.getenv("NOMIC_DIMENSIONALITY") else None
    )

    # Vector database configuration (legacy)
    default_embedding_dimension: int = int(os.getenv("DEFAULT_EMBEDDING_DIMENSION", "384"))
    default_distance_function: str = os.getenv("DEFAULT_DISTANCE_FUNCTION", "cosine")
    max_batch_size: int = int(os.getenv("MAX_BATCH_SIZE", "100"))
    
    # Connection Pool Settings (reduced to prevent OOM)
    db_pool_size: int = int(os.getenv("DB_POOL_SIZE", "5"))
    db_max_overflow: int = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    db_pool_recycle: int = int(os.getenv("DB_POOL_RECYCLE", "3600"))
    db_pool_timeout: int = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    
    # Performance Settings
    similarity_search_limit: int = int(os.getenv("SIMILARITY_SEARCH_LIMIT", "100"))
    document_chunk_size: int = int(os.getenv("DOCUMENT_CHUNK_SIZE", "1000"))
    document_chunk_overlap: int = int(os.getenv("DOCUMENT_CHUNK_OVERLAP", "200"))

    # Batch Processing Settings (prevent OOM during ingestion)
    max_batch_documents: int = int(os.getenv("MAX_BATCH_DOCUMENTS", "50"))
    batch_commit_size: int = int(os.getenv("BATCH_COMMIT_SIZE", "10"))
    max_document_size_mb: int = int(os.getenv("MAX_DOCUMENT_SIZE_MB", "5"))
    
    # Legacy compatibility
    vector_dimension: int = int(os.getenv("VECTOR_DIMENSION", "384"))  # MiniLM-L6-v2 dimension
    max_connections: int = int(os.getenv("MAX_CONNECTIONS", "20"))
    
    # Service configuration
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
    
    class Config:
        env_file = ".env"


settings = Settings()