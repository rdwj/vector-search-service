from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime


class DocumentIngestRequest(BaseModel):
    """Request model for document ingestion"""
    content: str = Field(..., description="The document content to ingest")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata for the document")
    document_id: Optional[str] = Field(default=None, description="Optional document ID (will be generated if not provided)")
    chunk_size: Optional[int] = Field(default=1000, description="Size of text chunks for embedding")
    chunk_overlap: Optional[int] = Field(default=200, description="Overlap between chunks in characters")


class DocumentIngestResponse(BaseModel):
    """Response model for document ingestion"""
    document_id: str = Field(..., description="Unique identifier for the ingested document")
    chunks_created: int = Field(..., description="Number of chunks created from the document")
    embedding_count: int = Field(..., description="Number of embeddings generated")
    status: str = Field(..., description="Status of the ingestion process")
    processing_time_ms: int = Field(..., description="Time taken to process the document in milliseconds")


class SimilaritySearchRequest(BaseModel):
    """Request model for similarity search"""
    query: str = Field(..., description="The search query text")
    collection_id: str = Field(default="default", description="Collection ID to search in")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum number of results to return")
    min_score: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Minimum similarity score threshold")
    metadata_filter: Optional[Dict[str, Any]] = Field(default=None, description="Metadata filters to apply")


class SearchResult(BaseModel):
    """Individual search result model"""
    document_id: str = Field(..., description="Unique identifier of the document")
    content: str = Field(..., description="The matching content/chunk")
    score: float = Field(..., description="Similarity score (0-1)")
    metadata: Dict[str, Any] = Field(..., description="Document metadata")
    chunk_index: Optional[int] = Field(default=None, description="Index of the chunk within the document")


class SimilaritySearchResponse(BaseModel):
    """Response model for similarity search"""
    query: str = Field(..., description="The original search query")
    results: List[SearchResult] = Field(..., description="List of search results")
    total_found: int = Field(..., description="Total number of results found")
    processing_time_ms: int = Field(..., description="Time taken to process the search in milliseconds")


class BatchIngestRequest(BaseModel):
    """Request model for batch document ingestion"""
    documents: List[DocumentIngestRequest] = Field(..., description="List of documents to ingest")
    collection_id: str = Field(default="default", description="Collection ID to store all documents in")
    processing_mode: str = Field(default="async", pattern="^(sync|async)$", description="Processing mode: sync or async")


class BatchIngestResponse(BaseModel):
    """Response model for batch document ingestion"""
    job_id: str = Field(..., description="Unique identifier for the batch job")
    documents_queued: int = Field(..., description="Number of documents queued for processing")
    estimated_completion_time: Optional[str] = Field(default=None, description="Estimated completion time (ISO format)")
    status_endpoint: str = Field(..., description="Endpoint to check job status")
    status: str = Field(..., description="Current status of the batch job")


class BatchSearchRequest(BaseModel):
    """Request model for batch search operations"""
    queries: List[str] = Field(..., description="List of search queries")
    collection_id: str = Field(default="default", description="Collection ID to search in")
    limit: int = Field(default=10, ge=1, le=100, description="Maximum number of results per query")
    output_format: str = Field(default="json", pattern="^(json|csv)$", description="Output format: json or csv")
    metadata_filter: Optional[Dict[str, Any]] = Field(default=None, description="Metadata filters to apply")


class BatchSearchResponse(BaseModel):
    """Response model for batch search operations"""
    job_id: str = Field(..., description="Unique identifier for the batch job")
    queries_processed: int = Field(..., description="Number of queries processed")
    results: List[SimilaritySearchResponse] = Field(..., description="List of search results for each query")
    processing_time_ms: int = Field(..., description="Total time taken to process all queries")
    status: str = Field(..., description="Status of the batch search")


class CollectionCreateRequest(BaseModel):
    """Request model for creating a new collection"""
    name: str = Field(..., description="Name of the collection")
    description: Optional[str] = Field(default=None, description="Description of the collection")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata for the collection")


class CollectionInfo(BaseModel):
    """Model for collection information"""
    id: str = Field(..., description="Unique identifier of the collection")
    name: str = Field(..., description="Name of the collection")
    description: Optional[str] = Field(default=None, description="Description of the collection")
    document_count: int = Field(..., description="Number of documents in the collection")
    embedding_count: int = Field(..., description="Number of embeddings in the collection")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    metadata: Dict[str, Any] = Field(..., description="Collection metadata")


class CollectionCreateResponse(BaseModel):
    """Response model for collection creation"""
    collection_id: str = Field(..., description="Unique identifier of the created collection")
    name: str = Field(..., description="Name of the collection")
    status: str = Field(..., description="Status of the collection creation")
    created_at: datetime = Field(..., description="Creation timestamp")


class CollectionListResponse(BaseModel):
    """Response model for listing collections"""
    collections: List[CollectionInfo] = Field(..., description="List of collections")
    total_count: int = Field(..., description="Total number of collections")


class DocumentInfo(BaseModel):
    """Model for document information"""
    id: str = Field(..., description="Unique identifier of the document")
    collection_id: str = Field(..., description="Collection ID the document belongs to")
    content_preview: str = Field(..., description="Preview of the document content")
    metadata: Dict[str, Any] = Field(..., description="Document metadata")
    chunk_count: int = Field(..., description="Number of chunks in the document")
    embedding_count: int = Field(..., description="Number of embeddings generated")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class JobStatus(BaseModel):
    """Model for job status information"""
    job_id: str = Field(..., description="Unique identifier of the job")
    status: str = Field(..., description="Current status of the job")
    progress: float = Field(..., ge=0.0, le=1.0, description="Job progress (0-1)")
    started_at: datetime = Field(..., description="Job start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Job completion timestamp")
    error_message: Optional[str] = Field(default=None, description="Error message if job failed")
    result_url: Optional[str] = Field(default=None, description="URL to retrieve job results")


class ErrorResponse(BaseModel):
    """Standard error response model"""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error details")
    request_id: Optional[str] = Field(default=None, description="Request ID for debugging")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")