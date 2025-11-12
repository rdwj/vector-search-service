# Vector Search Service

Production-ready FastAPI service providing semantic search capabilities using PostgreSQL + pgvector. Designed for RAG (Retrieval-Augmented Generation) applications and AI-powered document search.

## Overview

A full-text search service that sits on top of PostgreSQL with pgvector, providing:
- **Document ingestion** with automatic text processing
- **Full-text search** using PostgreSQL's native FTS capabilities
- **Collection management** for organizing documents
- **RESTful API** for easy integration
- **Async operations** for high performance
- **OpenShift/Kubernetes ready** with manifests included

### Key Features

- ✅ **Production-ready**: Tested with large document collections
- ✅ **Scalable**: Async architecture with connection pooling
- ✅ **Flexible**: Works with any PostgreSQL + pgvector backend
- ✅ **Well-documented**: OpenAPI/Swagger docs included
- ✅ **Easy deployment**: One-command deployment to OpenShift
- ✅ **No external dependencies**: Uses PostgreSQL's built-in full-text search

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Applications (UI, Pipelines, APIs)                 │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│  Vector Search Service (FastAPI)                    │
│  • Document Ingestion API                           │
│  • Full-Text Search API                             │
│  • Collection Management                            │
│  • Async Job Processing                             │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│  PostgreSQL + pgvector Backend                      │
│  • embeddings table                                 │
│  • documentation table                              │
│  • Full-text search indexes                         │
└─────────────────────────────────────────────────────┘
```

## Prerequisites

### 1. PostgreSQL + pgvector Backend

Deploy the pgvector backend first. We provide a ready-to-use backend at:
- Repository: `../pgvector-poc-backend`
- Deployment: `./scripts/deploy-backend.sh servicenow-ai-poc`

Or use any PostgreSQL database with:
- ✅ `vector` extension enabled
- ✅ `pg_trgm` extension enabled (for full-text search)
- ✅ `btree_gin` extension enabled (for indexing)

### 2. Database Schema

The service expects these tables to exist (created automatically by pgvector backend):

```sql
-- Document embeddings and full-text search
CREATE TABLE IF NOT EXISTS embeddings (
    id SERIAL PRIMARY KEY,
    doc_id VARCHAR(255) UNIQUE NOT NULL,
    source VARCHAR(100) NOT NULL,
    doc_type VARCHAR(50),
    title TEXT,
    content TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Technical documentation
CREATE TABLE IF NOT EXISTS documentation (
    id SERIAL PRIMARY KEY,
    doc_id VARCHAR(255) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    doc_type VARCHAR(50),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Quick Start

### Local Development

```bash
# 1. Create virtual environment
python -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure database connection (use your actual credentials)
export POSTGRES_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_USER=raguser
export POSTGRES_PASSWORD=YOUR_ACTUAL_PASSWORD
export POSTGRES_DB=ragdb

# 4. Run the service
python -m src.main

# Service starts at http://localhost:8000
# API docs at http://localhost:8000/docs
```

### OpenShift Deployment

```bash
# Deploy to OpenShift (requires pgvector backend already deployed)
./deploy.sh servicenow-ai-poc

# Monitor deployment
oc get pods -n servicenow-ai-poc -l app=vector-search-service -w

# Get route URL
oc get route vector-search-service -n servicenow-ai-poc

# Test health endpoint
ROUTE=$(oc get route vector-search-service -n servicenow-ai-poc -o jsonpath='{.spec.host}')
curl https://$ROUTE/api/v1/health
```

## Configuration

### Environment Variables

All configuration via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_HOST` | `postgres-pgvector` | PostgreSQL hostname |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_USER` | `raguser` | Database user |
| `POSTGRES_PASSWORD` | `ragpass123` (local) | Database password. **OpenShift:** Sourced from `postgres-pgvector-secret` (overrides default) |
| `POSTGRES_DB` | `ragdb` | Database name |
| `PORT` | `8000` | Service port |
| `LOG_LEVEL` | `INFO` | Logging level |
| `FTS_LANGUAGE` | `english` | Full-text search language |

### ConfigMap (OpenShift)

Configuration is managed via `manifests/configmap.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: vector-search-service-config
data:
  POSTGRES_HOST: "postgres-pgvector"
  POSTGRES_PORT: "5432"
  POSTGRES_USER: "raguser"
  POSTGRES_DB: "ragdb"
  LOG_LEVEL: "INFO"
```

### Database Password

**The vector-search-service uses the existing `postgres-pgvector-secret` from the backend deployment.**

This means:
- ✅ **Single source of truth** for database credentials
- ✅ **No duplicate secrets** to manage
- ✅ **Passwords automatically match** between services

When you update the password in `pgvector-poc-backend/openshift/secrets.yaml` and redeploy the backend, the vector-search-service automatically uses the updated password.

The deployment manifest references the secret:
```yaml
env:
- name: POSTGRES_PASSWORD
  valueFrom:
    secretKeyRef:
      name: postgres-pgvector-secret
      key: POSTGRES_PASSWORD
```

## API Usage

### Health Check

```bash
curl http://localhost:8000/api/v1/health
```

### Create Collection

```bash
curl -X POST http://localhost:8000/api/v1/collections \
  -H "Content-Type: application/json" \
  -d '{"name": "my_docs", "description": "My document collection"}'
```

### Ingest Documents

```bash
curl -X POST http://localhost:8000/api/v1/collections/my_docs/documents \
  -H "Content-Type: application/json" \
  -d '{
    "documents": [
      {
        "doc_id": "doc1",
        "content": "This is a sample document about vector search.",
        "metadata": {"source": "manual", "category": "example"}
      }
    ]
  }'
```

### Search Documents

```bash
curl -X POST http://localhost:8000/api/v1/collections/my_docs/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "vector search",
    "limit": 10
  }'
```

## API Documentation

Interactive API documentation available at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI Spec**: `http://localhost:8000/openapi.json`

## Project Structure

```
vector-search-service/
├── src/
│   ├── main.py                 # FastAPI application
│   ├── config/
│   │   └── settings.py         # Configuration management
│   ├── api/
│   │   ├── health.py           # Health check endpoints
│   │   ├── documents.py        # Document ingestion
│   │   ├── search.py           # Search endpoints
│   │   └── collections.py      # Collection management
│   ├── core/
│   │   ├── vector_store.py     # PostgreSQL vector store
│   │   └── document_processor.py  # Document processing
│   ├── db/
│   │   ├── connection.py       # Database connection pool
│   │   └── models.py           # SQLAlchemy models
│   └── tests/
│       └── test_*.py           # Unit tests
├── manifests/
│   ├── deployment.yaml         # OpenShift Deployment
│   ├── service.yaml            # Kubernetes Service
│   ├── route.yaml              # OpenShift Route
│   ├── configmap.yaml          # Configuration
│   └── kustomization.yaml      # Kustomize config
├── scripts/
│   ├── ingest_servicenow.py    # ServiceNow data ingestion
│   └── search_client.py        # Example search client
├── Containerfile               # Container build
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Use Cases

### 1. ServiceNow Knowledge Base RAG

```python
# Ingest ServiceNow articles
python scripts/ingest_servicenow.py \
  --data-path ./data/servicenow \
  --collection-name servicenow_kb

# Search for solutions
curl -X POST http://localhost:8000/api/v1/collections/servicenow_kb/search \
  -d '{"query": "password reset procedure", "limit": 5}'
```

### 2. Technical Documentation Search

```python
# Ingest docs from directory
import requests

docs = load_documentation_files("./docs")
response = requests.post(
    "http://localhost:8000/api/v1/collections/tech_docs/documents",
    json={"documents": docs}
)
```

### 3. Pipeline Integration (Elyra/KubeFlow)

The service includes Elyra components for pipeline integration:
- `elyra-components/ingest-documents.yaml`
- `elyra-components/search-documents.yaml`

## Testing

```bash
# Install dev dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test
pytest src/tests/test_health.py
```

## Performance Tuning

### Connection Pooling

Adjust pool size based on load:

```bash
export DB_POOL_SIZE=10
export DB_MAX_OVERFLOW=20
```

### Batch Processing

For large ingestion jobs:

```bash
export MAX_BATCH_DOCUMENTS=100
export BATCH_COMMIT_SIZE=20
```

## Troubleshooting

### Service Won't Start

```bash
# Check database connectivity
oc exec deployment/vector-search-service -n servicenow-ai-poc -- \
  curl -v http://postgres-pgvector:5432

# Check logs
oc logs -f deployment/vector-search-service -n servicenow-ai-poc
```

### Search Returns No Results

```bash
# Verify documents were ingested
oc exec postgres-pgvector-0 -n servicenow-ai-poc -- \
  psql -U raguser -d ragdb -c "SELECT COUNT(*) FROM embeddings;"

# Check full-text search indexes
oc exec postgres-pgvector-0 -n servicenow-ai-poc -- \
  psql -U raguser -d ragdb -c "\d embeddings"
```

## Integration with Other Projects

This service is designed to work with:
- ✅ **pgvector-poc-backend**: Our PostgreSQL + pgvector backend
- ✅ **ServiceNow AI PoC**: ServiceNow + KB RAG system
- ✅ **Any RAG application**: Standard REST API
- ✅ **KubeFlow/Elyra pipelines**: Elyra components included
- ✅ **LangChain**: Compatible with retriever interface

## Migration from Standalone Embedding

This service uses PostgreSQL's native full-text search instead of external embedding services, providing:
- ✅ **Simpler architecture**: No external dependencies
- ✅ **Better performance**: Native database indexes
- ✅ **Lower cost**: No external API calls
- ✅ **Same interface**: Drop-in replacement

## License

MIT License - See LICENSE file for details

## Support

For issues, questions, or contributions:
- GitHub Issues: Create an issue in the repository
- Documentation: See `/docs` directory for detailed guides
- API Docs: Available at `/docs` endpoint when service is running

---

**Version**: 2.0.0
**Compatible with**: PostgreSQL 14+, pgvector 0.5.0+
**Tested on**: OpenShift 4.14+, Kubernetes 1.27+
