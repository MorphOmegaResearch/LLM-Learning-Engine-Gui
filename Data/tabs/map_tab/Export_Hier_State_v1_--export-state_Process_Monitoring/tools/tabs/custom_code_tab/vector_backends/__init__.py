"""Vector backend integrations for the Custom Code tab."""

from .hcodex_client import HCodexVectorClient, VectorSearchResult, VectorSearchError
from .server_manager import EmbeddingServerManager

__all__ = ["HCodexVectorClient", "VectorSearchResult", "VectorSearchError", "EmbeddingServerManager"]
