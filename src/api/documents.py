"""
Document ingestion and management endpoints
"""
import logging
import gc
import psutil
import os
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends

from .models import (
    DocumentIngestRequest, DocumentIngestResponse,
    BatchIngestRequest, BatchIngestResponse,
    DocumentInfo, ErrorResponse
)
from ..core.vector_store import PostgreSQLVectorStore
from ..core.document_processor import DocumentProcessor
# REMOVED: EmbeddingClient (no longer needed with TF-IDF)
from ..core.job_manager import JobManager
from ..db.connection import DatabaseManager
from ..config.settings import Settings

logger = logging.getLogger(__name__)

router = APIRouter()

# Global instances - in production, these would be properly injected
_settings = None
_db_manager = None
_vector_store = None
_document_processor = None
# _embedding_client = None  # REMOVED: No longer needed with TF-IDF
_job_manager = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

async def get_db_manager() -> DatabaseManager:
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(get_settings())
        await _db_manager.initialize()
    return _db_manager

async def get_vector_store() -> PostgreSQLVectorStore:
    global _vector_store
    if _vector_store is None:
        db_manager = await get_db_manager()
        _vector_store = PostgreSQLVectorStore(db_manager)
    return _vector_store

def get_document_processor() -> DocumentProcessor:
    global _document_processor
    if _document_processor is None:
        _document_processor = DocumentProcessor(get_settings())
    return _document_processor

# REMOVED: No longer needed with TF-IDF full-text search
# async def get_embedding_client() -> EmbeddingClient:
#     global _embedding_client
#     if _embedding_client is None:
#         _embedding_client = EmbeddingClient(get_settings())
#         await _embedding_client.initialize()
#     return _embedding_client

def get_job_manager() -> JobManager:
    global _job_manager
    if _job_manager is None:
        _job_manager = JobManager()
    return _job_manager

def log_memory_usage(stage: str):
    """Log current memory usage for profiling"""
    try:
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        mem_mb = mem_info.rss / 1024 / 1024
        logger.info(f"[MEMORY] {stage}: {mem_mb:.2f} MB RSS")
    except Exception as e:
        logger.error(f"[MEMORY] Failed to log memory at {stage}: {e}")

@router.post("/collections/{collection_name}/documents", response_model=DocumentIngestResponse)
async def ingest_document(
    collection_name: str,
    request: DocumentIngestRequest
):
    """
    Ingest a single document (using full-text search, no embeddings generated).
    """
    try:
        log_memory_usage("START ingestion")

        # Get dependencies
        vector_store = await get_vector_store()
        document_processor = get_document_processor()
        # embedding_client = await get_embedding_client()  # NO LONGER NEEDED

        log_memory_usage("After get_vector_store")

        # Validate collection exists; create if missing for first-run convenience
        collection = await vector_store.get_collection(collection_name)
        log_memory_usage("After get_collection")

        logger.info(f"[DEBUG] Collection result type: {type(collection)}, value: {collection is not None}")
        log_memory_usage("Before validation check")

        logger.info(f"[DEBUG] About to check collection truthiness")
        if not collection:
            log_memory_usage("Collection not found, creating")
            settings = get_settings()
            try:
                collection = await vector_store.create_collection(
                    name=collection_name,
                    description=f"Collection for {collection_name}",
                    embedding_dimension=None,  # No embeddings
                    distance_function="cosine",
                    metadata={"created_by": "documents.ingest", "search_type": "fulltext"}
                )
                logger.info(f"Created collection '{collection_name}' with full-text search")
                log_memory_usage("After create_collection")
            except Exception as ce:
                logger.error(f"Failed to create collection '{collection_name}': {ce}")
                raise HTTPException(status_code=500, detail=f"Failed to create collection '{collection_name}'")

        # Validate document
        logger.info(f"[DEBUG] About to validate document: content_len={len(request.content) if request.content else 0}")
        log_memory_usage("Before validate_document call")
        is_valid, error_msg = document_processor.validate_document(request.content, request.metadata)
        logger.info(f"[DEBUG] Validation result: is_valid={is_valid}")
        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        # Generate document ID if not provided
        logger.info(f"[DEBUG] About to generate document ID")
        log_memory_usage("Before generate_document_id")
        document_id = request.document_id or document_processor.generate_document_id(
            request.content, request.metadata
        )
        logger.info(f"[DEBUG] Document ID: {document_id}")

        # Preprocess content
        logger.info(f"[DEBUG] About to preprocess content")
        log_memory_usage("Before preprocess_content")
        processed_content = document_processor.preprocess_content(request.content)
        logger.info(f"[DEBUG] Preprocessed content length: {len(processed_content)}")

        # Extract and merge metadata
        logger.info(f"[DEBUG] About to extract metadata")
        log_memory_usage("Before extract_metadata")
        extracted_metadata = document_processor.extract_metadata(processed_content, request.metadata)
        logger.info(f"[DEBUG] Metadata extracted: {len(extracted_metadata)} fields")

        # Process document and generate chunks
        logger.info(f"[DEBUG] About to chunk document")
        log_memory_usage("Before chunk_document")
        chunks = document_processor.chunk_document(
            processed_content,
            chunk_size=request.chunk_size,
            overlap=request.chunk_overlap,
            metadata=extracted_metadata
        )
        logger.info(f"[DEBUG] Document chunked: {len(chunks)} chunks created")

        if not chunks:
            raise HTTPException(status_code=400, detail="No valid chunks generated from document")

        # Get chunk texts (NO embedding generation)
        chunk_texts = document_processor.get_chunk_texts(chunks)

        # Prepare document metadata for each chunk
        chunk_metadata = []
        for i, chunk in enumerate(chunks):
            chunk_meta = {
                **chunk.metadata,
                'document_id': document_id,
                'chunk_index': chunk.chunk_index,
                'start_char': chunk.start_char,
                'end_char': chunk.end_char,
                'total_chunks': len(chunks)
            }
            chunk_metadata.append(chunk_meta)

        # Generate chunk IDs
        chunk_ids = [f"{document_id}_chunk_{i}" for i in range(len(chunks))]

        log_memory_usage("Before database insert")

        # Store in PostgreSQL (no embeddings, tsvector generated by trigger)
        # Use batch commit size from settings to prevent OOM
        settings = get_settings()
        result = await vector_store.add_documents(
            collection_name=collection_name,
            documents=chunk_texts,
            embeddings=None,  # No embeddings
            metadata=chunk_metadata,
            document_ids=chunk_ids,
            batch_size=settings.batch_commit_size
        )

        log_memory_usage("After database insert")

        # Explicit cleanup
        del chunks, chunk_texts, chunk_metadata, chunk_ids
        gc.collect()
        log_memory_usage("After gc.collect()")

        logger.info(f"Successfully ingested document {document_id} into collection {collection_name} (FTS mode)")

        return DocumentIngestResponse(
            document_id=document_id,
            chunks_created=len(result) if result else 0,
            embedding_count=0,  # No embeddings generated
            status="completed",
            processing_time_ms=0  # Could track actual processing time
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/collections/{collection_name}/documents/batch", response_model=BatchIngestResponse)
async def batch_ingest_documents(
    collection_name: str,
    request: BatchIngestRequest,
    background_tasks: BackgroundTasks
):
    """
    Process multiple documents asynchronously or synchronously
    """
    try:
        # Get dependencies
        vector_store = await get_vector_store()
        job_manager = get_job_manager()
        settings = get_settings()

        # Validate batch size to prevent OOM
        if len(request.documents) > settings.max_batch_documents:
            raise HTTPException(
                status_code=400,
                detail=f"Batch too large: {len(request.documents)} documents (max {settings.max_batch_documents}). "
                       f"Use async processing mode for large batches."
            )

        # Validate collection exists
        collection = await vector_store.get_collection(collection_name)
        if not collection:
            raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")
        
        if request.processing_mode == "async":
            # Queue background processing
            job_id = await job_manager.create_batch_job(request.documents, collection_name)
            
            # Add background task
            background_tasks.add_task(
                process_batch_job,
                job_id,
                request.documents,
                collection_name,
                job_manager
            )
            
            return BatchIngestResponse(
                job_id=job_id,
                documents_queued=len(request.documents),
                estimated_completion_time=None,
                status_endpoint=f"/api/v1/jobs/{job_id}/status",
                status="queued"
            )
        else:
            # Process synchronously
            results = []
            errors = []
            
            for i, doc_request in enumerate(request.documents):
                try:
                    result = await ingest_document(collection_name, doc_request)
                    results.append(result)
                except Exception as e:
                    error_info = {
                        "document_index": i,
                        "document_id": doc_request.document_id,
                        "error": str(e)
                    }
                    errors.append(error_info)
                    logger.error(f"Failed to process document {i}: {e}")
            
            return BatchIngestResponse(
                job_id=None,
                documents_queued=len(request.documents),
                estimated_completion_time=None,
                status_endpoint=None,
                status="completed"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch document ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/collections/{collection_name}/documents", response_model=List[Dict[str, Any]])
async def list_documents(
    collection_name: str,
    limit: int = 100,
    offset: int = 0
):
    """
    List documents in a collection
    """
    try:
        vector_store = await get_vector_store()
        
        # Validate collection exists
        collection = await vector_store.get_collection(collection_name)
        if not collection:
            raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")
        
        # Get documents from collection
        documents = await vector_store.get_documents(
            collection_name=collection_name,
            limit=limit,
            offset=offset
        )
        
        return documents
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/collections/{collection_name}/documents", response_model=Dict[str, Any])
async def delete_documents(
    collection_name: str,
    document_ids: List[str]
):
    """
    Delete documents from a collection
    """
    try:
        vector_store = await get_vector_store()
        
        # Validate collection exists
        collection = await vector_store.get_collection(collection_name)
        if not collection:
            raise HTTPException(status_code=404, detail=f"Collection '{collection_name}' not found")
        
        # Delete documents
        deleted_count = await vector_store.delete_documents(
            collection_name=collection_name,
            document_ids=document_ids
        )
        
        return {
            "collection_name": collection_name,
            "documents_deleted": deleted_count,
            "requested_deletions": len(document_ids)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# REMOVED: No longer needed with TF-IDF full-text search
# @router.get("/embedding-health", response_model=Dict[str, Any])
# async def check_embedding_health():
#     """
#     Check health of embedding service (vLLM or local)
#     """
#     try:
#         embedding_client = await get_embedding_client()
#         health_status = await embedding_client.health_check()
#         return health_status
#     except Exception as e:
#         logger.error(f"Embedding health check failed: {e}")
#         raise HTTPException(status_code=500, detail=f"Embedding service unhealthy: {str(e)}")

@router.get("/jobs/{job_id}", response_model=Dict[str, Any])
async def get_job_status(job_id: str):
    """
    Get status and results of a batch processing job
    """
    try:
        job_manager = get_job_manager()
        job_status = await job_manager.get_job_status(job_id)
        
        if job_status is None:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        return job_status
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status for {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/jobs", response_model=List[Dict[str, Any]])
async def list_jobs(
    limit: int = 100,
    status: Optional[str] = None
):
    """
    List batch processing jobs with optional filtering
    """
    try:
        job_manager = get_job_manager()
        jobs = await job_manager.get_all_jobs(limit=limit, status=status)
        return jobs
    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/jobs/{job_id}", response_model=Dict[str, Any])
async def cancel_job(job_id: str):
    """
    Cancel a running or queued batch processing job
    """
    try:
        job_manager = get_job_manager()
        cancelled = await job_manager.cancel_job(job_id)
        
        if not cancelled:
            raise HTTPException(status_code=400, detail=f"Job {job_id} cannot be cancelled")
        
        return {"job_id": job_id, "status": "cancelled"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Background task function
async def process_batch_job(
    job_id: str,
    documents: List[DocumentIngestRequest],
    collection_name: str,
    job_manager: JobManager
):
    """
    Process batch job in background
    """
    try:
        # Update job status
        await job_manager.update_job_status(job_id, "processing")
        
        results = []
        errors = []
        
        for i, doc_request in enumerate(documents):
            try:
                result = await ingest_document(collection_name, doc_request)
                results.append(result)
                
                # Update progress
                await job_manager.update_job_progress(job_id, i + 1, len(documents))
                
            except Exception as e:
                error_info = {
                    "document_index": i,
                    "document_id": doc_request.document_id,
                    "error": str(e)
                }
                errors.append(error_info)
                logger.error(f"Failed to process document {i} in job {job_id}: {e}")
        
        # Update job completion
        await job_manager.complete_job(job_id, results, errors)
        
        logger.info(f"Batch job {job_id} completed: {len(results)} success, {len(errors)} errors")
        
    except Exception as e:
        logger.error(f"Batch job {job_id} failed: {e}")
        await job_manager.fail_job(job_id, str(e))