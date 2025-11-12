"""
Background job management for batch document processing
"""
import asyncio
import uuid
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum

from ..api.models import DocumentIngestRequest

logger = logging.getLogger(__name__)

class JobStatus(Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class JobResult:
    """Result of processing a single document in a batch job"""
    document_id: Optional[str]
    document_index: int
    status: str
    chunks_created: int = 0
    embedding_count: int = 0
    error: Optional[str] = None
    processing_time_ms: int = 0

@dataclass
class BatchJob:
    """Represents a batch document processing job"""
    id: str
    collection_name: str
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_documents: int = 0
    processed_documents: int = 0
    successful_documents: int = 0
    failed_documents: int = 0
    results: List[JobResult] = None
    error_message: Optional[str] = None
    progress_percentage: float = 0.0
    
    def __post_init__(self):
        if self.results is None:
            self.results = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert job to dictionary for API responses"""
        return {
            "id": self.id,
            "collection_name": self.collection_name,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_documents": self.total_documents,
            "processed_documents": self.processed_documents,
            "successful_documents": self.successful_documents,
            "failed_documents": self.failed_documents,
            "progress_percentage": self.progress_percentage,
            "error_message": self.error_message,
            "results": [asdict(result) for result in self.results] if self.results else []
        }

class JobManager:
    """
    Manages background job processing for batch document operations
    """
    
    def __init__(self):
        self.jobs: Dict[str, BatchJob] = {}
        self._running_tasks: Dict[str, asyncio.Task] = {}
        
    async def create_batch_job(
        self, 
        documents: List[DocumentIngestRequest],
        collection_name: str
    ) -> str:
        """
        Create and queue a batch processing job
        """
        job_id = str(uuid.uuid4())
        
        job = BatchJob(
            id=job_id,
            collection_name=collection_name,
            status=JobStatus.QUEUED,
            created_at=datetime.utcnow(),
            total_documents=len(documents)
        )
        
        self.jobs[job_id] = job
        
        logger.info(f"Created batch job {job_id} for {len(documents)} documents in collection {collection_name}")
        
        return job_id
    
    async def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get current job status and results
        """
        if job_id not in self.jobs:
            return None
        
        job = self.jobs[job_id]
        return job.to_dict()
    
    async def get_all_jobs(self, limit: int = 100, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all jobs with optional filtering
        """
        jobs = list(self.jobs.values())
        
        # Filter by status if specified
        if status:
            try:
                status_enum = JobStatus(status)
                jobs = [job for job in jobs if job.status == status_enum]
            except ValueError:
                logger.warning(f"Invalid status filter: {status}")
                return []
        
        # Sort by created_at (newest first)
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        
        # Apply limit
        jobs = jobs[:limit]
        
        return [job.to_dict() for job in jobs]
    
    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a running or queued job
        """
        if job_id not in self.jobs:
            return False
        
        job = self.jobs[job_id]
        
        if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
            return False
        
        # Cancel the running task if it exists
        if job_id in self._running_tasks:
            task = self._running_tasks[job_id]
            task.cancel()
            del self._running_tasks[job_id]
        
        # Update job status
        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.utcnow()
        
        logger.info(f"Cancelled job {job_id}")
        return True
    
    async def update_job_status(self, job_id: str, status: str):
        """
        Update job status
        """
        if job_id not in self.jobs:
            logger.warning(f"Attempted to update non-existent job {job_id}")
            return
        
        job = self.jobs[job_id]
        
        try:
            job.status = JobStatus(status)
            
            if status == "processing" and job.started_at is None:
                job.started_at = datetime.utcnow()
            elif status in ["completed", "failed", "cancelled"]:
                job.completed_at = datetime.utcnow()
                
        except ValueError:
            logger.error(f"Invalid status update for job {job_id}: {status}")
    
    async def update_job_progress(self, job_id: str, processed: int, total: int):
        """
        Update job progress
        """
        if job_id not in self.jobs:
            logger.warning(f"Attempted to update progress for non-existent job {job_id}")
            return
        
        job = self.jobs[job_id]
        job.processed_documents = processed
        job.total_documents = total
        
        if total > 0:
            job.progress_percentage = (processed / total) * 100
        
        logger.debug(f"Job {job_id} progress: {processed}/{total} ({job.progress_percentage:.1f}%)")
    
    async def add_job_result(self, job_id: str, result: JobResult):
        """
        Add a processing result to the job
        """
        if job_id not in self.jobs:
            logger.warning(f"Attempted to add result to non-existent job {job_id}")
            return
        
        job = self.jobs[job_id]
        job.results.append(result)
        
        if result.status == "completed":
            job.successful_documents += 1
        elif result.status == "failed":
            job.failed_documents += 1
    
    async def complete_job(self, job_id: str, results: List[Dict[str, Any]], errors: List[Dict[str, Any]]):
        """
        Mark job as completed with results
        """
        if job_id not in self.jobs:
            logger.warning(f"Attempted to complete non-existent job {job_id}")
            return
        
        job = self.jobs[job_id]
        
        # Convert results to JobResult objects
        for i, result in enumerate(results):
            job_result = JobResult(
                document_id=result.get("document_id"),
                document_index=i,
                status="completed",
                chunks_created=result.get("chunks_created", 0),
                embedding_count=result.get("embedding_count", 0),
                processing_time_ms=result.get("processing_time_ms", 0)
            )
            job.results.append(job_result)
            job.successful_documents += 1
        
        # Convert errors to JobResult objects
        for error in errors:
            job_result = JobResult(
                document_id=error.get("document_id"),
                document_index=error.get("document_index", -1),
                status="failed",
                error=error.get("error")
            )
            job.results.append(job_result)
            job.failed_documents += 1
        
        # Update job status
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        job.processed_documents = len(results) + len(errors)
        job.progress_percentage = 100.0
        
        # Clean up running task
        if job_id in self._running_tasks:
            del self._running_tasks[job_id]
        
        logger.info(f"Job {job_id} completed: {job.successful_documents} successful, {job.failed_documents} failed")
    
    async def fail_job(self, job_id: str, error_message: str):
        """
        Mark job as failed with error message
        """
        if job_id not in self.jobs:
            logger.warning(f"Attempted to fail non-existent job {job_id}")
            return
        
        job = self.jobs[job_id]
        job.status = JobStatus.FAILED
        job.error_message = error_message
        job.completed_at = datetime.utcnow()
        
        # Clean up running task
        if job_id in self._running_tasks:
            del self._running_tasks[job_id]
        
        logger.error(f"Job {job_id} failed: {error_message}")
    
    async def cleanup_old_jobs(self, max_age_hours: int = 24):
        """
        Remove jobs older than specified hours
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        jobs_to_remove = []
        for job_id, job in self.jobs.items():
            if job.created_at < cutoff_time and job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                jobs_to_remove.append(job_id)
        
        for job_id in jobs_to_remove:
            del self.jobs[job_id]
            logger.debug(f"Cleaned up old job {job_id}")
        
        if jobs_to_remove:
            logger.info(f"Cleaned up {len(jobs_to_remove)} old jobs")
    
    def get_job_count(self) -> Dict[str, int]:
        """
        Get count of jobs by status
        """
        counts = {status.value: 0 for status in JobStatus}
        
        for job in self.jobs.values():
            counts[job.status.value] += 1
        
        return counts