from typing import Any, Dict, Optional

class DeepVaultError(Exception):
    """
    Base exception class for all DeepVault errors.
    Inheriting from this allows us to catch any custom app error in one block.
    """
    def __init__(self, message: str, detail: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.detail = detail or {}

class ConfigurationError(DeepVaultError):
    """Raised when environment variables or settings are invalid."""
    pass

class IngestionError(DeepVaultError):
    """Raised when document parsing, chunking, or storage fails during ingestion."""
    pass

class DuplicateDocumentError(DeepVaultError):
    """Raised when a document hash already exists in the system."""
    pass

class EmbeddingError(DeepVaultError):
    """Raised when the vector representation generation fails."""
    pass

class RetrievalError(DeepVaultError):
    """Raised when searching the vector or metadata stores fails."""
    pass

class LLMGenerationError(DeepVaultError):
    """Raised when the Groq API fails to generate a response."""
    pass

class DocumentNotFoundError(DeepVaultError):
    """Raised when an operation is attempted on a non-existent document ID."""
    pass

class ValidationError(DeepVaultError):
    """Raised when input data fails internal validation checks."""
    pass
