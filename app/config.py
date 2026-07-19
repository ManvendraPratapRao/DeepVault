from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # -------------------------------------------------------------------------
    # App identity
    # -------------------------------------------------------------------------
    APP_NAME: str = "DeepVault"
    VERSION: str = "4.0.0"  # Kept in sync with pyproject.toml — bump both together
    DEBUG: bool = False

    # -------------------------------------------------------------------------
    # Groq LLM
    # The system uses two Groq models via the LLMRouter:
    #   - llama-3.1-8b-instant  → simple/factual queries  (cheap, fast)
    #   - llama-3.3-70b-versatile → complex/semantic queries (quality, costs more)
    # GROQ_MODEL_NAME is the fallback when the router is not available.
    # -------------------------------------------------------------------------
    GROQ_API_KEY: str = ""
    GROQ_MODEL_NAME: str = "llama-3.1-8b-instant"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 2048

    # -------------------------------------------------------------------------
    # API Authentication
    # No default — must be set in .env (or env var API_KEY=...).
    # Rotate by updating the value and restarting the service.
    # JWT / multi-key auth is planned for a future phase.
    # -------------------------------------------------------------------------
    API_KEY: str

    @field_validator("API_KEY")
    @classmethod
    def api_key_must_not_be_default(cls, v: str) -> str:
        """Prevent accidental startup with a well-known placeholder key."""
        blocked = {"deepvault_secret_key", "changeme", "secret", ""}
        if v.strip().lower() in blocked:
            raise ValueError("API_KEY is set to an insecure placeholder. Set a strong secret in your .env file.")
        return v

    # -------------------------------------------------------------------------
    # CORS
    # Permits the Streamlit dashboard (8501) and local browser requests.
    # In production, restrict this to your frontend's actual domain.
    # -------------------------------------------------------------------------
    CORS_ALLOWED_ORIGINS: list[str] = [
        "http://localhost:8501",  # Streamlit dashboard
        "http://localhost:3000",  # Reserved for future integrations
        "http://localhost:8000",  # API itself (for Swagger UI)
    ]

    # -------------------------------------------------------------------------
    # Retrieval confidence threshold
    # If the top retrieved chunk scores below this, we refuse to answer rather
    # than risk hallucinating. Prevents "confident wrong answer" failure mode.
    # -------------------------------------------------------------------------
    CONTEXT_CONFIDENCE_THRESHOLD: float = 0.15

    # -------------------------------------------------------------------------
    # Vector Database (Qdrant)
    # Set QDRANT_HOST="local" to use an on-disk Qdrant instance at
    # qdrant_storage/ — useful for development without Docker.
    # -------------------------------------------------------------------------
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "deepvault_knowledge"

    # -------------------------------------------------------------------------
    # Redis (Caching + Rate Limiting)
    # Used for: semantic query cache, embedding cache, async job tracking,
    # and per-API-key sliding-window rate limiting.
    # CACHE_ENABLED / EMBEDDING_CACHE_ENABLED are feature flags so you can
    # turn off caching in benchmarks to measure raw pipeline latency.
    # -------------------------------------------------------------------------
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_TTL_SECONDS: int = 3600  # 1 hour default TTL for query cache
    CACHE_ENABLED: bool = True
    EMBEDDING_CACHE_ENABLED: bool = True

    # -------------------------------------------------------------------------
    # Embedding Model
    # BAAI/bge-small-en-v1.5 — 384-dimensional, runs on CPU, Apache 2.0 license.
    # See ADR-001 for the vector DB choice and ADR-004 for the interface design
    # that makes swapping this model a one-line change.
    # -------------------------------------------------------------------------
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-small-en-v1.5"

    # -------------------------------------------------------------------------
    # Chunking
    # Strategy is the default used for ingestion when not specified per-request.
    # Each strategy gets its own Qdrant collection (deepvault_{strategy})
    # so all four can be benchmarked side-by-side without interference.
    # -------------------------------------------------------------------------
    CHUNKER_SIZE: int = 600
    CHUNKER_OVERLAP: int = 120
    CHUNKER_STRATEGY: str = "fixed"  # "fixed" | "sliding" | "semantic" | "structure"
    SEMANTIC_SIMILARITY_THRESHOLD: float = 0.85

    # -------------------------------------------------------------------------
    # Retrieval
    # "auto" enables the QueryRouter to pick the best strategy per query type.
    # See ADR-009 and docs/query_pipeline.md for the routing logic.
    # -------------------------------------------------------------------------
    RETRIEVAL_STRATEGY: str = "hybrid"  # "vector" | "hybrid" | "hybrid_rerank" | "auto"

    # -------------------------------------------------------------------------
    # Metadata Store (SQLite)
    # Stores document hashes, source filenames, and ingestion timestamps.
    # SQLite is single-writer only — do NOT run with UVICORN_WORKERS > 1.
    # PostgreSQL migration is planned once multi-worker deployment is needed.
    # See ADR-003 for the rationale.
    # -------------------------------------------------------------------------
    SQLITE_DB_PATH: str = "deepvault.db"

    # -------------------------------------------------------------------------
    # Deployment
    # UVICORN_WORKERS > 1 requires a multi-writer backend (PostgreSQL, not SQLite).
    # The validator below will fail fast at startup to prevent silent corruption.
    # -------------------------------------------------------------------------
    UVICORN_WORKERS: int = 1

    @field_validator("UVICORN_WORKERS")
    @classmethod
    def workers_require_postgres(cls, v: int) -> int:
        """Block multi-worker startup when SQLite is the metadata store."""
        # We check SQLITE_DB_PATH indirectly by looking at UVICORN_WORKERS.
        # Importing settings inside a validator would be circular, so we check
        # purely on worker count.  A follow-up migration to PostgreSQL will
        # remove this guard.
        if v > 1:
            raise ValueError(
                f"UVICORN_WORKERS={v} requires a multi-writer database (PostgreSQL). "
                "SQLite is single-writer and will corrupt under concurrent writes. "
                "Either set UVICORN_WORKERS=1 or migrate to PostgreSQL first."
            )
        return v

    # -------------------------------------------------------------------------
    # Document ingestion
    # -------------------------------------------------------------------------
    DATA_DIRS: list[str] = ["synthetic_data_v2"]
    SUPPORTED_FILE_EXTENSIONS: list[str] = [".md", ".txt", ".pdf"]
    MAX_UPLOAD_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB

    # -------------------------------------------------------------------------
    # Logging
    # All log output is structured JSON (see app/infrastructure/logging/structured.py).
    # Each request gets a unique X-Request-ID correlation header so you can
    # grep logs for an entire request trace: jq '.request_id == "abc-123"'
    # -------------------------------------------------------------------------
    LOG_LEVEL: str = "INFO"

    # -------------------------------------------------------------------------
    # Observability & Tracing (Arize Phoenix)
    # -------------------------------------------------------------------------
    PHOENIX_ENABLED: bool = True
    PHOENIX_ENDPOINT: str = "http://localhost:6006/v1/traces"
    PHOENIX_PROJECT_NAME: str = "deepvault"

    # -------------------------------------------------------------------------
    # Evaluation Models
    # -------------------------------------------------------------------------
    EVAL_JUDGE_MODEL: str = "groq/llama-3.1-8b-instant"
    EVAL_QUALITY_MODEL: str = "groq/llama-3.3-70b-versatile"

    # Pydantic-settings: read from .env file, silently ignore unknown keys
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Global settings singleton — import this everywhere
settings = Settings()
