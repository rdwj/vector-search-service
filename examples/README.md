# Example Configurations

This directory contains reference configurations and examples for deploying and using the Vector Search RAG Service.

## 📁 Directory Structure

```
examples/
├── README.md                          # This file
├── deployment/                        # Deployment examples
│   ├── local-development/             # Local development setup
│   ├── openshift-dev/                 # OpenShift development deployment
│   └── production/                    # Production deployment examples
├── api-usage/                         # API usage examples
│   ├── python-client/                 # Python client examples
│   ├── curl-examples/                 # cURL command examples
│   └── postman/                       # Postman collection
├── configurations/                    # Configuration examples
│   ├── environment-configs/           # Environment-specific configs
│   └── integration-configs/           # Service integration configs
└── data/                             # Sample data for testing
    ├── documents/                     # Sample documents
    └── test-datasets/                 # Test datasets
```

## 🚀 Quick Start Examples

### **1. Local Development Setup**

Complete local setup with all dependencies:

```bash
# Clone the repository
git clone https://github.com/your-org/vector-search-service
cd vector-search-service

# Set up local PostgreSQL + pgvector
./scripts/setup-local-db.sh

# Install dependencies and run service
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000
```

### **2. OpenShift Production Deployment**

Deploy the complete system using ArgoCD:

```bash
# Deploy PostgreSQL + pgvector (using James Harmison's config)
oc apply -f https://raw.githubusercontent.com/jharmison-redhat/openshift-setup/250130b0391f341b5bbea5ea647bc734f30885cb/demos/vllm-pg-rag.yaml

# Deploy vLLM embedding service
oc apply -f examples/deployment/production/vllm-embedding.yaml

# Deploy RAG service via ArgoCD
oc apply -f examples/deployment/production/argocd-application.yaml
```

### **3. API Usage Example**

Basic document ingestion and search:

```bash
# Create collection
curl -X POST "http://localhost:8000/api/v1/collections" \
  -H "Content-Type: application/json" \
  -d '{"name": "my-docs", "description": "My document collection"}'

# Add documents
curl -X POST "http://localhost:8000/api/v1/collections/my-docs/documents" \
  -H "Content-Type: application/json" \
  -d '{
    "documents": [
      {"id": "doc1", "content": "Machine learning is a subset of AI"},
      {"id": "doc2", "content": "Python is a popular programming language"}
    ]
  }'

# Search documents
curl -X POST "http://localhost:8000/api/v1/collections/my-docs/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "artificial intelligence", "limit": 5}'
```

## 📖 Detailed Examples

### **Configuration Examples**

- [Environment Configurations](configurations/environment-configs/) - Environment-specific settings
- [Integration Configurations](configurations/integration-configs/) - Service integration examples

### **Deployment Examples**

- [Local Development](deployment/local-development/) - Complete local setup
- [OpenShift Development](deployment/openshift-dev/) - Development cluster deployment
- [Production](deployment/production/) - Production-ready deployment

### **API Usage Examples**

- [Python Client](api-usage/python-client/) - Python SDK usage examples
- [cURL Examples](api-usage/curl-examples/) - Command-line API usage
- [Postman Collection](api-usage/postman/) - Interactive API testing

## 🧪 Test Data

Sample data for testing and development:

- [Sample Documents](data/documents/) - Various document types for testing
- [Test Datasets](data/test-datasets/) - Curated datasets for evaluation

## 🔧 Customization

Most examples can be customized by:

1. **Environment Variables**: Modify `.env` files in each example
2. **Configuration Files**: Update YAML configurations
3. **Resource Limits**: Adjust CPU/memory allocations
4. **Model Selection**: Choose different embedding models

## 📚 Additional Resources

- [System Architecture](../docs/architecture/system-overview.md)
- [Dependencies Setup](../docs/dependencies/README.md)
- [Deployment Guide](../docs/integration/deployment-guide.md)
- [Development Guides](../swe-pm/)

## 🤝 Contributing Examples

To contribute new examples:

1. Follow the existing directory structure
2. Include comprehensive README files
3. Test all configurations before submitting
4. Document any prerequisites or assumptions
5. Include troubleshooting tips

## 📞 Support

If you encounter issues with any examples:

1. Check the [troubleshooting guides](../docs/operations/)
2. Verify all prerequisites are met
3. Review logs for error messages
4. Check resource availability
5. Consult the component-specific documentation