import pytest
from fastapi.testclient import TestClient
from datetime import datetime
import json

from ..main import app

client = TestClient(app)


def test_root_endpoint():
    """Test the root endpoint returns service information"""
    response = client.get("/")
    assert response.status_code == 200
    
    data = response.json()
    assert data["service"] == "Vector Search Service"
    assert data["version"] == "1.0.0"
    assert data["status"] == "running"
    assert "docs_url" in data
    assert "health_url" in data


def test_health_endpoint():
    """Test the health endpoint returns proper health status"""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    
    data = response.json()
    assert "status" in data
    assert "timestamp" in data
    assert "version" in data
    assert "service" in data
    assert "uptime" in data
    assert "components" in data
    
    # Verify the structure
    assert data["service"] == "vector-search-service"
    assert data["version"] == "1.0.0"
    assert data["status"] in ["healthy", "unhealthy"]
    
    # Verify components exist
    components = data["components"]
    assert "database" in components
    # REMOVED: No longer needed with TF-IDF
    # assert "embedding_service" in components
    assert "response_time_seconds" in components

    # Verify component structure
    assert "status" in components["database"]
    assert "message" in components["database"]
    assert "response_time_ms" in components["database"]

    # REMOVED: No longer needed with TF-IDF
    # assert "status" in components["embedding_service"]
    # assert "message" in components["embedding_service"]
    # assert "response_time_ms" in components["embedding_service"]


def test_health_endpoint_performance():
    """Test that health endpoint responds quickly"""
    import time
    
    start_time = time.time()
    response = client.get("/api/v1/health")
    end_time = time.time()
    
    assert response.status_code == 200
    assert (end_time - start_time) < 0.1  # Should respond in under 100ms


@pytest.mark.asyncio
async def test_health_components_structure():
    """Test that health components return expected structure"""
    from ..api.health import check_database_health
    # REMOVED: No longer needed with TF-IDF
    # from ..api.health import check_embedding_service_health

    # Test database health check
    db_health = await check_database_health()
    assert isinstance(db_health, dict)
    assert "status" in db_health
    assert "message" in db_health
    assert "response_time_ms" in db_health

    # REMOVED: No longer needed with TF-IDF
    # # Test embedding service health check
    # embedding_health = await check_embedding_service_health()
    # assert isinstance(embedding_health, dict)
    # assert "status" in embedding_health
    # assert "message" in embedding_health
    # assert "response_time_ms" in embedding_health


def test_openapi_docs():
    """Test that OpenAPI documentation is available"""
    response = client.get("/docs")
    assert response.status_code == 200
    
    response = client.get("/openapi.json")
    assert response.status_code == 200
    
    openapi_data = response.json()
    assert "info" in openapi_data
    assert openapi_data["info"]["title"] == "Vector Search Service"
    assert openapi_data["info"]["version"] == "1.0.0"