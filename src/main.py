from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
import uvicorn

from .config.settings import settings
from .api.health import router as health_router
from .api.documents import router as documents_router
from .api.search import router as search_router
from .api.collections import router as collections_router
# from .api.jobs import router as jobs_router  # Job endpoints are in documents router


# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


from .db.connection import DatabaseManager
from .core.vector_store import PostgreSQLVectorStore
# REMOVED: No longer needed with TF-IDF
# from .core.embedding_service import EmbeddingService

# Global instances
db_manager = None
vector_store = None
# REMOVED: No longer needed with TF-IDF
# embedding_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup and shutdown events
    """
    # REMOVED: No longer needed with TF-IDF - removed embedding_service from global
    global db_manager, vector_store
    
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    
    # Startup logic
    try:
        # Initialize database connection
        db_manager = DatabaseManager(settings)
        await db_manager.initialize()
        app.state.db_manager = db_manager
        
        # Initialize vector store
        vector_store = PostgreSQLVectorStore(db_manager)
        app.state.vector_store = vector_store

        # REMOVED: No longer needed with TF-IDF
        # # Initialize embedding service
        # embedding_service = EmbeddingService(settings)
        # app.state.embedding_service = embedding_service

        logger.info("Application startup complete")
        yield
    except Exception as e:
        logger.error(f"Application startup failed: {str(e)}")
        raise
    finally:
        # Shutdown logic
        logger.info("Shutting down application")
        if db_manager:
            await db_manager.close()


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="A vector search service providing semantic search capabilities using PostgreSQL + pgvector",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router, prefix="/api/v1", tags=["health"])
app.include_router(documents_router, prefix="/api/v1", tags=["documents"])
app.include_router(search_router, prefix="/api/v1", tags=["search"])
app.include_router(collections_router, prefix="/api/v1", tags=["collections"])
# app.include_router(jobs_router, prefix="/api/v1", tags=["jobs"])  # Job endpoints are in documents router

# Root endpoint
@app.get("/")
async def root():
    """
    Root endpoint providing service information
    """
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs_url": "/docs",
        "health_url": "/api/v1/health"
    }


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )