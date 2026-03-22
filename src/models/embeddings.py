"""Local text embedding using sentence-transformers (CPU-friendly)."""

import logging
from typing import List, Optional

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class LocalEmbedder:
    """Local text embedding model using sentence-transformers.

    Runs on CPU, no external API calls needed.
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-base-en-v1.5",
        normalize: bool = True,
    ):
        """Initialize the embedding model.

        Args:
            model_name: HuggingFace model name
            normalize: Whether to L2-normalize embeddings (recommended for cosine similarity)
        """
        self.model_name = model_name
        self.normalize = normalize

        logger.info(f"Loading embedding model: {model_name}")
        self.model = SentenceTransformer(model_name)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        logger.info(f"Model loaded. Embedding dimension: {self.embedding_dim}")

    def embed_texts(
        self,
        texts: List[str],
        batch_size: int = 64,
        show_progress: bool = True,
    ) -> List[List[float]]:
        """Embed a list of texts.

        Args:
            texts: List of text strings to embed
            batch_size: Batch size for encoding
            show_progress: Whether to show progress bar

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        logger.info(f"Embedding {len(texts)} texts...")

        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            normalize_embeddings=self.normalize,
        )

        return embeddings.tolist()

    def embed_query(self, query: str) -> List[float]:
        """Embed a single query text.

        For BGE models, queries should be prefixed with "Represent this sentence:"
        but sentence-transformers handles this automatically for retrieval.

        Args:
            query: Query text

        Returns:
            Embedding vector
        """
        embedding = self.model.encode(
            query,
            normalize_embeddings=self.normalize,
        )
        return embedding.tolist()


def create_embedder(
    model_name: Optional[str] = None,
    normalize: bool = True,
) -> LocalEmbedder:
    """Factory function to create embedder from settings or params.

    Args:
        model_name: Model name (uses settings if not provided)
        normalize: Whether to normalize embeddings
    """
    from config import get_settings

    settings = get_settings()

    name = model_name or settings.yaml.embedding.model_name

    return LocalEmbedder(
        model_name=name,
        normalize=normalize,
    )
