from fastapi import APIRouter, HTTPException, status
from typing import List, Dict, Any
import uuid
import time
import logging
from datetime import datetime

from .models import (
    SimilaritySearchRequest,
    SimilaritySearchResponse,
    SearchResult,
    BatchSearchRequest,
    BatchSearchResponse,
    CollectionListResponse,
    CollectionInfo,
    ErrorResponse
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/search/similarity",
             response_model=SimilaritySearchResponse,
             responses={
                 422: {"model": ErrorResponse, "description": "Validation error"},
                 500: {"model": ErrorResponse, "description": "Internal server error"}
             })
async def similarity_search(request: SimilaritySearchRequest) -> SimilaritySearchResponse:
    """
    Perform full-text search with TF-IDF ranking (replaces semantic similarity).

    This endpoint takes a query string and searches using PostgreSQL
    full-text search with TF-IDF relevance ranking. No embeddings are generated.
    """
    try:
        start_time = time.time()
        logger.info(f"Performing full-text search for query: '{request.query[:50]}...'")

        # Get dependencies from app state (using globals for now)
        from ..core.vector_store import PostgreSQLVectorStore
        from ..db.connection import DatabaseManager
        from ..config.settings import Settings

        settings = Settings()
        dbm = DatabaseManager(settings)
        await dbm.initialize()
        store = PostgreSQLVectorStore(dbm)

        # Perform full-text search (no embedding generation needed)
        results = await store.fulltext_search(
            collection_name=request.collection_id,
            query_text=request.query,
            limit=request.limit,
            metadata_filter=request.metadata_filter,
            language=getattr(settings, 'fts_language', 'english')
        )

        processing_time_ms = int((time.time() - start_time) * 1000)

        # Map to response model
        api_results = [
            SearchResult(
                document_id=item.get("document_id", ""),
                content=item.get("content", ""),
                score=float(item.get("score", 0.0)),  # TF-IDF rank
                metadata=item.get("metadata", {}),
                chunk_index=item.get("metadata", {}).get("chunk_index", 0)
            ) for item in results
        ]

        await dbm.close()

        return SimilaritySearchResponse(
            query=request.query,
            results=api_results,
            total_found=len(api_results),
            processing_time_ms=processing_time_ms
        )

    except Exception as e:
        logger.error(f"Full-text search failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Full-text search failed: {str(e)}"
        )


@router.post("/search/batch",
             response_model=BatchSearchResponse,
             responses={
                 422: {"model": ErrorResponse, "description": "Validation error"},
                 500: {"model": ErrorResponse, "description": "Internal server error"}
             })
async def batch_search(request: BatchSearchRequest) -> BatchSearchResponse:
    """
    Perform batch similarity searches for multiple queries.
    
    This endpoint processes multiple search queries in a single request,
    useful for pipeline operations that need to search for multiple terms.
    """
    try:
        start_time = time.time()
        job_id = str(uuid.uuid4())
        
        logger.info(f"Starting batch search job {job_id} with {len(request.queries)} queries")
        
        # TODO: Implement actual batch search logic
        # For now, simulate processing each query
        
        results = []
        for i, query in enumerate(request.queries):
            # Create mock search response for each query
            mock_results = []
            for j in range(min(request.limit, 3)):  # 3 results per query
                mock_result = SearchResult(
                    document_id=str(uuid.uuid4()),
                    content=f"Mock result {j+1} for query: {query}",
                    score=0.8 - (j * 0.1),
                    metadata={
                        "source": f"batch_document_{i}_{j}.txt",
                        "type": "text",
                        "batch_query_index": i
                    },
                    chunk_index=j
                )
                mock_results.append(mock_result)
            
            search_response = SimilaritySearchResponse(
                query=query,
                results=mock_results,
                total_found=len(mock_results),
                processing_time_ms=50  # Mock processing time per query
            )
            results.append(search_response)
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        return BatchSearchResponse(
            job_id=job_id,
            queries_processed=len(request.queries),
            results=results,
            processing_time_ms=processing_time_ms,
            status="completed"
        )
        
    except Exception as e:
        logger.error(f"Batch search failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch search failed: {str(e)}"
        )


@router.get("/search/collections",
            response_model=CollectionListResponse,
            responses={
                500: {"model": ErrorResponse, "description": "Internal server error"}
            })
async def list_collections() -> CollectionListResponse:
    """
    List all available collections for searching.
    
    Returns information about all collections including document counts
    and metadata.
    """
    try:
        logger.info("Listing all collections")
        
        # TODO: Implement actual collection listing logic
        # For now, return mock collections
        
        mock_collections = [
            CollectionInfo(
                id="default",
                name="Default Collection",
                description="Default collection for general documents",
                document_count=25,
                embedding_count=150,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                metadata={"type": "general", "public": True}
            ),
            CollectionInfo(
                id="technical_docs",
                name="Technical Documentation",
                description="Collection for technical documentation and guides",
                document_count=12,
                embedding_count=84,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                metadata={"type": "technical", "category": "documentation"}
            )
        ]
        
        return CollectionListResponse(
            collections=mock_collections,
            total_count=len(mock_collections)
        )
        
    except Exception as e:
        logger.error(f"Collection listing failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Collection listing failed: {str(e)}"
        )