# Vector Search Service - Quick Start

## Prerequisites

1. **PostgreSQL + pgvector backend deployed** (from `../pgvector-poc-backend`)
   - The vector-search-service uses the `postgres-pgvector-secret` from the backend
   - No separate password configuration needed
2. **OpenShift CLI (`oc`)** installed and logged in

## Deploy in 3 Steps

### Step 1: Verify Backend is Running

```bash
oc get pods -n servicenow-ai-poc | grep postgres-pgvector
# Should show: postgres-pgvector-0   1/1   Running
```

### Step 2: Deploy Vector Search Service

```bash
./deploy.sh servicenow-ai-poc
```

### Step 3: Verify Deployment

```bash
# Check pod status
oc get pods -n servicenow-ai-poc -l app=vector-search-service

# Get route URL
ROUTE=$(oc get route vector-search-service -n servicenow-ai-poc -o jsonpath='{.spec.host}')

# Test health endpoint
curl https://$ROUTE/api/v1/health
```

## Quick API Test

```bash
# Create a collection
curl -X POST https://$ROUTE/api/v1/collections \
  -H "Content-Type: application/json" \
  -d '{"name": "test_docs", "description": "Test collection"}'

# Ingest a document
curl -X POST https://$ROUTE/api/v1/collections/test_docs/documents \
  -H "Content-Type: application/json" \
  -d '{
    "documents": [{
      "doc_id": "doc1",
      "content": "This is a test document about vector search.",
      "metadata": {"source": "test"}
    }]
  }'

# Search
curl -X POST https://$ROUTE/api/v1/collections/test_docs/search \
  -H "Content-Type: application/json" \
  -d '{"query": "vector search", "limit": 5}'
```

## API Documentation

Access Swagger UI at: `https://$ROUTE/docs`

## Troubleshooting

### Service won't start
```bash
# Check logs
oc logs -f deployment/vector-search-service -n servicenow-ai-poc

# Check database connectivity
oc exec deployment/vector-search-service -n servicenow-ai-poc -- \
  curl -v http://postgres-pgvector:5432
```

### No search results
```bash
# Verify documents were ingested
oc exec postgres-pgvector-0 -n servicenow-ai-poc -- \
  psql -U raguser -d ragdb -c "SELECT COUNT(*) FROM embeddings;"
```

## What's Next?

- See [README.md](README.md) for full documentation
- Check [examples/](examples/) for integration examples
- Review [api/openapi.yaml](api/openapi.yaml) for complete API spec
