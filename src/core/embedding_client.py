"""
Embedding client with Nomic Embed API integration and local fallback
"""
import asyncio
import logging
from typing import List, Dict, Any, Optional
import httpx
from sentence_transformers import SentenceTransformer
from src.config.settings import Settings

logger = logging.getLogger(__name__)

class EmbeddingClient:
    """
    Unified embedding client supporting Nomic API and local models
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        # Nomic API
        self.nomic_api_url = settings.nomic_api_url
        self.nomic_api_key = settings.nomic_api_key
        self.nomic_model = settings.embedding_model  # expect 'nomic-embed-text-v1.5'
        self.nomic_long_text_mode = settings.nomic_long_text_mode
        self.nomic_dimensionality = settings.nomic_dimensionality

        # Local fallback
        self.local_model_name = getattr(settings, 'local_model_name', 'sentence-transformers/all-MiniLM-L6-v2')
        
        self._local_model = None
        self._vllm_available = None
        
    async def initialize(self):
        """Initialize the embedding client"""
        # Prefer Nomic if configured
        if not await self._check_nomic_ready():
            logger.warning("Nomic API not configured/available, using local model fallback")
            await self._initialize_local_model()
    
    async def _initialize_local_model(self):
        """Initialize local sentence transformer model"""
        try:
            logger.info(f"Loading local embedding model: {self.local_model_name}")
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            self._local_model = await loop.run_in_executor(
                None, 
                lambda: SentenceTransformer(self.local_model_name)
            )
            logger.info("Local embedding model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load local embedding model: {e}")
            raise
    
    async def _check_nomic_ready(self) -> bool:
        """Check Nomic API configuration presence (no ping endpoint)."""
        return bool(self.nomic_api_url and self.nomic_api_key)
    
    async def generate_embeddings(self, texts: List[str], task_type: str = "search_document") -> List[List[float]]:
        """
        Generate embeddings for a list of texts
        """
        if not texts:
            return []
        
        # Try Nomic first if configured
        if await self._check_nomic_ready():
            try:
                return await self._generate_nomic_embeddings(texts, task_type=task_type)
            except Exception as e:
                logger.warning(f"Nomic embedding failed, falling back to local model: {e}")
                return await self._generate_local_embeddings(texts)
        # Otherwise local
        return await self._generate_local_embeddings(texts)
    
    async def _generate_nomic_embeddings(self, texts: List[str], task_type: str = "search_document") -> List[List[float]]:
        """Generate embeddings using Nomic Embed API"""
        try:
            headers = {"Authorization": f"Bearer {self.nomic_api_key}"}
            payload: Dict[str, Any] = {
                "texts": texts,
                "model": self.nomic_model,
                "task_type": task_type,
            }
            if self.nomic_long_text_mode:
                payload["long_text_mode"] = self.nomic_long_text_mode
            if self.nomic_dimensionality:
                payload["dimensionality"] = self.nomic_dimensionality
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.nomic_api_url.rstrip('/')}/v1/embedding/text",
                    headers=headers,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                embeddings = data.get("embeddings") or []
                return embeddings
        except Exception as e:
            logger.error(f"Nomic embedding generation failed: {e}")
            raise
    
    async def _generate_local_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using local model"""
        try:
            if self._local_model is None:
                await self._initialize_local_model()
            
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None,
                lambda: self._local_model.encode(texts, convert_to_tensor=False)
            )
            
            # Convert to list of lists
            embeddings_list = [embedding.tolist() for embedding in embeddings]
            
            logger.debug(f"Generated {len(embeddings_list)} embeddings via local model")
            return embeddings_list
            
        except Exception as e:
            logger.error(f"Local embedding generation failed: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check health of embedding services
        """
        vllm_health = False
        local_health = False
        nomic_ready = await self._check_nomic_ready()

        # Check local model health
        try:
            if self._local_model is None:
                await self._initialize_local_model()
            local_health = self._local_model is not None
        except Exception:
            local_health = False
        
        return {
            "nomic_configured": nomic_ready,
            "nomic_url": self.nomic_api_url,
            "local_available": local_health,
            "local_model": self.local_model_name,
            "primary_service": "nomic" if nomic_ready else "local"
        }
    
    async def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings"""
        # For Nomic v1.5, default full dimension is 768 unless reduced
        if await self._check_nomic_ready():
            return self.nomic_dimensionality or 768
        
        # For local model, we can get the actual dimension
        if self._local_model is None:
            await self._initialize_local_model()
        
        return self._local_model.get_sentence_embedding_dimension()
    
    async def close(self):
        """Clean up resources"""
        # No explicit cleanup needed for local model
        # httpx clients are automatically closed
        pass