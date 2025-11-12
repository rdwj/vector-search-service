"""
Test embedding endpoint functionality
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient
from src.main import app
from src.api.models import DocumentIngestRequest, DocumentIngestResponse
from src.core.document_processor import DocumentChunk


class TestEmbeddingEndpoints:
    """Test embedding-related endpoints"""
    
    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)
    
    @pytest.fixture
    def mock_vector_store(self):
        """Mock vector store"""
        mock = AsyncMock()
        mock.get_collection.return_value = {"id": "test-collection", "name": "test-collection"}
        mock.add_documents.return_value = {"status": "success"}
        return mock
    
    @pytest.fixture
    def mock_embedding_client(self):
        """Mock embedding client"""
        mock = AsyncMock()
        mock.generate_embeddings.return_value = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
        mock.health_check.return_value = {"status": "healthy", "service": "local"}
        return mock
    
    @pytest.fixture
    def mock_document_processor(self):
        """Mock document processor"""
        mock = MagicMock()
        mock.validate_document.return_value = (True, None)
        mock.generate_document_id.return_value = "doc-123"
        mock.preprocess_content.return_value = "processed content"
        mock.extract_metadata.return_value = {"title": "Test Document"}
        mock.chunk_document.return_value = [
            DocumentChunk(
                content="chunk 1",
                chunk_index=0,
                start_char=0,
                end_char=7,
                metadata={"title": "Test Document"}
            ),
            DocumentChunk(
                content="chunk 2",
                chunk_index=1,
                start_char=7,
                end_char=14,
                metadata={"title": "Test Document"}
            )
        ]
        mock.get_chunk_texts.return_value = ["chunk 1", "chunk 2"]
        return mock
    
    @pytest.fixture
    def mock_job_manager(self):
        """Mock job manager"""
        mock = MagicMock()
        mock.create_batch_job.return_value = "job-123"
        mock.get_job_status.return_value = {
            "id": "job-123",
            "status": "queued",
            "total_documents": 2,
            "processed_documents": 0
        }
        return mock
    
    def test_health_endpoint(self, client):
        """Test health endpoint is accessible"""
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
    
    @patch('src.api.documents.get_vector_store')
    @patch('src.api.documents.get_embedding_client')
    @patch('src.api.documents.get_document_processor')
    def test_embedding_health_check(
        self, 
        mock_doc_processor,
        mock_embedding_client_func,
        mock_vector_store_func,
        client, 
        mock_embedding_client
    ):
        """Test embedding health check endpoint"""
        mock_embedding_client_func.return_value = mock_embedding_client
        
        response = client.get("/api/v1/embedding-health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        mock_embedding_client.health_check.assert_called_once()
    
    @patch('src.api.documents.get_vector_store')
    @patch('src.api.documents.get_embedding_client')
    @patch('src.api.documents.get_document_processor')
    def test_ingest_document_success(
        self,
        mock_doc_processor_func,
        mock_embedding_client_func,
        mock_vector_store_func,
        client,
        mock_vector_store,
        mock_embedding_client,
        mock_document_processor
    ):
        """Test successful document ingestion"""
        mock_vector_store_func.return_value = mock_vector_store
        mock_embedding_client_func.return_value = mock_embedding_client
        mock_doc_processor_func.return_value = mock_document_processor
        
        # Test data
        request_data = {
            "content": "This is a test document",
            "metadata": {"title": "Test Document"},
            "chunk_size": 100,
            "chunk_overlap": 20
        }
        
        response = client.post("/api/v1/collections/test-collection/documents", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        assert "document_id" in data
        assert "chunks_created" in data
        assert "embedding_count" in data
        assert data["status"] == "completed"
        
        # Verify the mocks were called
        mock_vector_store.get_collection.assert_called_once_with("test-collection")
        mock_document_processor.validate_document.assert_called_once()
        mock_embedding_client.generate_embeddings.assert_called_once()
        mock_vector_store.add_documents.assert_called_once()
    
    @patch('src.api.documents.get_vector_store')
    def test_ingest_document_collection_not_found(
        self,
        mock_vector_store_func,
        client,
        mock_vector_store
    ):
        """Test document ingestion with non-existent collection"""
        mock_vector_store.get_collection.return_value = None
        mock_vector_store_func.return_value = mock_vector_store
        
        request_data = {
            "content": "This is a test document",
            "metadata": {"title": "Test Document"}
        }
        
        response = client.post("/api/v1/collections/nonexistent/documents", json=request_data)
        assert response.status_code == 404
        assert "Collection 'nonexistent' not found" in response.json()["detail"]
    
    @patch('src.api.documents.get_vector_store')
    @patch('src.api.documents.get_document_processor')
    def test_ingest_document_validation_error(
        self,
        mock_doc_processor_func,
        mock_vector_store_func,
        client,
        mock_vector_store,
        mock_document_processor
    ):
        """Test document ingestion with validation error"""
        mock_vector_store_func.return_value = mock_vector_store
        mock_document_processor.validate_document.return_value = (False, "Content is empty")
        mock_doc_processor_func.return_value = mock_document_processor
        
        request_data = {
            "content": "",
            "metadata": {"title": "Test Document"}
        }
        
        response = client.post("/api/v1/collections/test-collection/documents", json=request_data)
        assert response.status_code == 400
        assert "Content is empty" in response.json()["detail"]
    
    @patch('src.api.documents.get_job_manager')
    def test_get_job_status(
        self,
        mock_job_manager_func,
        client,
        mock_job_manager
    ):
        """Test getting job status"""
        mock_job_manager_func.return_value = mock_job_manager
        
        response = client.get("/api/v1/jobs/job-123")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == "job-123"
        assert data["status"] == "queued"
        assert data["total_documents"] == 2
        
        mock_job_manager.get_job_status.assert_called_once_with("job-123")
    
    @patch('src.api.documents.get_job_manager')
    def test_get_job_status_not_found(
        self,
        mock_job_manager_func,
        client,
        mock_job_manager
    ):
        """Test getting status of non-existent job"""
        mock_job_manager.get_job_status.return_value = None
        mock_job_manager_func.return_value = mock_job_manager
        
        response = client.get("/api/v1/jobs/nonexistent")
        assert response.status_code == 404
        assert "Job nonexistent not found" in response.json()["detail"]
    
    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "version" in data
        assert "status" in data
        assert data["status"] == "running"