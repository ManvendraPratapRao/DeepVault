from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "DeepVault"
    VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Groq Settings
    GROQ_API_KEY: str
    GROQ_MODEL_NAME: str = "llama-3.1-8b-instant"

    # LLM Generation
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 2048

    # Vector DB
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "deepvault_knowledge"

    # Redis (Caching)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # Embedding Model
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-small-en-v1.5"

    # Chunker Defaults
    CHUNKER_SIZE: int = 500
    CHUNKER_OVERLAP: int = 100
    CHUNKER_STRATEGY: str = "fixed"  # "fixed" | "sliding" | "semantic" | "structure"
    SEMANTIC_SIMILARITY_THRESHOLD: float = 0.75

    # SQLite
    SQLITE_DB_PATH: str = "deepvault.db"

    # Logging
    LOG_LEVEL: str = "INFO"

    # Environment config
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Global settings instance
settings = Settings()
