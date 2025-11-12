"""
Embedding service for generating text embeddings
Supports both local sentence-transformers and remote embedding APIs
"""

import numpy as np
from typing import List, Union, Optional
from sentence_transformers import SentenceTransformer
import httpx
import logging
from src.config.settings import Settings

logger = logging.getLogger(__name__)

class EmbeddingService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.model = None
        self.client = None

        # Check if external API is configured (Nomic or generic)
        has_nomic = settings.nomic_api_url and settings.nomic_api_key
        has_generic_api = settings.embedding_api_url

        if has_nomic or has_generic_api:
            # Use remote embedding service
            api_url = settings.nomic_api_url if has_nomic else settings.embedding_api_url
            api_key = settings.nomic_api_key if has_nomic else settings.embedding_api_key

            self.client = httpx.AsyncClient(
                base_url=api_url,
                headers={"Authorization": f"Bearer {api_key}"} if api_key else {}
            )
            logger.info(f"Using remote embedding service: {api_url}")
            self.embedding_dimension = settings.nomic_dimensionality if has_nomic else settings.default_embedding_dimension
        else:
            # Use local sentence-transformers
            self.model = SentenceTransformer(settings.embedding_model)
            self.embedding_dimension = self.model.get_sentence_embedding_dimension()
            logger.info(f"Loaded local embedding model: {settings.embedding_model}")
    
    async def embed_text(self, text: Union[str, List[str]]) -> Union[np.ndarray, List[np.ndarray]]:
        """Generate embeddings for text(s)"""
        if isinstance(text, str):
            texts = [text]
            single = True
        else:
            texts = text
            single = False
        
        if self.client:
            # Use remote service
            embeddings = await self._embed_remote(texts)
        else:
            # Use local model
            embeddings = self._embed_local(texts)
        
        return embeddings[0] if single else embeddings
    
    def _embed_local(self, texts: List[str]) -> List[np.ndarray]:
        """Generate embeddings using local model"""
        try:
            embeddings = self.model.encode(texts, convert_to_numpy=True)
            return [embedding for embedding in embeddings]
        except Exception as e:
            logger.error(f"Local embedding failed: {e}")
            raise
    
    async def _embed_remote(self, texts: List[str]) -> List[np.ndarray]:
        """Generate embeddings using remote API (Nomic or generic)"""
        try:
            # Check if using Nomic API
            is_nomic = self.settings.nomic_api_url and self.settings.nomic_api_key

            if is_nomic:
                # Nomic API format
                endpoint = "/v1/embedding/text"
                payload = {
                    "texts": texts,
                    "model": self.settings.embedding_model,
                    "task_type": "search_document"
                }
                if self.settings.nomic_dimensionality:
                    payload["dimensionality"] = self.settings.nomic_dimensionality
            else:
                # Generic API format
                endpoint = "/embeddings"
                payload = {"texts": texts}

            response = await self.client.post(endpoint, json=payload)
            response.raise_for_status()

            data = response.json()
            embeddings = [np.array(emb) for emb in data["embeddings"]]
            return embeddings
        except Exception as e:
            logger.error(f"Remote embedding failed: {e}")
            raise
    
    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings"""
        if self.model:
            return self.model.get_sentence_embedding_dimension()
        else:
            return self.settings.default_embedding_dimension
    
    async def close(self):
        """Clean up resources"""
        if self.client:
            await self.client.aclose()