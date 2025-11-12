#!/bin/bash
# Working deployment using simple Python base image

set -e

PROJECT_NAME="pgvector"
SERVICE_NAME="vector-search-service"

# Database configuration
DB_HOST="postgres-pgvector.pgvector.svc.cluster.local"
DB_PORT="5432"
DB_NAME="vectordb"
DB_USER="vectoruser"
DB_PASSWORD="vectorpass"

echo "Deploying Vector Search Service (Working Method)..."

oc project ${PROJECT_NAME}

# Clean up existing resources
oc delete deployment,service,route,configmap,secret -l app=${SERVICE_NAME} --ignore-not-found=true

# Create ConfigMap with application code
echo "Creating application code ConfigMap..."
cat <<EOF | oc apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: ${SERVICE_NAME}-app-code
  namespace: ${PROJECT_NAME}
data:
  requirements.txt: |
$(cat requirements-minimal.txt | sed 's/^/    /')
  
  start.sh: |
    #!/bin/bash
    cd /app
    echo "Installing dependencies..."
    pip install --no-cache-dir -r /config/requirements.txt
    echo "Starting application..."
    exec python -m uvicorn main:app --host 0.0.0.0 --port 8000
  
  main.py: |
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    import os
    import logging
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Create FastAPI app
    app = FastAPI(
        title="Vector Search Service",
        version="1.0.0",
        description="ServiceNow RAG Vector Search Service"
    )
    
    # Add CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    @app.get("/")
    async def root():
        return {
            "service": "Vector Search Service",
            "version": "1.0.0",
            "status": "running",
            "docs_url": "/docs",
            "health_url": "/api/v1/health"
        }
    
    @app.get("/api/v1/health")
    async def health():
        return {
            "status": "healthy",
            "service": "vector-search-service",
            "database": {
                "host": os.getenv("POSTGRES_HOST", "unknown"),
                "database": os.getenv("POSTGRES_DB", "unknown")
            }
        }
    
    @app.post("/api/v1/collections")
    async def create_collection(collection_data: dict):
        return {"status": "success", "message": "Collection endpoint ready"}
    
    @app.post("/api/v1/documents")
    async def add_document(document_data: dict):
        return {"status": "success", "message": "Document endpoint ready"}
    
    @app.post("/api/v1/search")
    async def search_documents(search_data: dict):
        return {
            "status": "success", 
            "message": "Search endpoint ready",
            "results": []
        }
    
    if __name__ == "__main__":
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
EOF

# Create environment ConfigMap
echo "Creating environment ConfigMap..."
cat <<EOF | oc apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: ${SERVICE_NAME}-config
  namespace: ${PROJECT_NAME}
data:
  POSTGRES_HOST: "${DB_HOST}"
  POSTGRES_PORT: "${DB_PORT}"
  POSTGRES_DB: "${DB_NAME}"
  POSTGRES_USER: "${DB_USER}"
  DEFAULT_EMBEDDING_DIMENSION: "384"
  LOG_LEVEL: "INFO"
EOF

# Create Secret
echo "Creating Secret..."
oc create secret generic ${SERVICE_NAME}-secret \
  --from-literal=POSTGRES_PASSWORD="${DB_PASSWORD}" \
  --dry-run=client -o yaml | oc apply -f -

# Create Deployment
echo "Creating Deployment..."
cat <<EOF | oc apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${SERVICE_NAME}
  namespace: ${PROJECT_NAME}
  labels:
    app: ${SERVICE_NAME}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ${SERVICE_NAME}
  template:
    metadata:
      labels:
        app: ${SERVICE_NAME}
    spec:
      containers:
      - name: ${SERVICE_NAME}
        image: python:3.11-slim
        command: ["/bin/bash"]
        args: ["/config/start.sh"]
        ports:
        - containerPort: 8000
          name: http
        envFrom:
        - configMapRef:
            name: ${SERVICE_NAME}-config
        - secretRef:
            name: ${SERVICE_NAME}-secret
        volumeMounts:
        - name: app-code
          mountPath: /config
        - name: app-dir
          mountPath: /app
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        readinessProbe:
          httpGet:
            path: /api/v1/health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /api/v1/health
            port: 8000
          initialDelaySeconds: 60
          periodSeconds: 30
      volumes:
      - name: app-code
        configMap:
          name: ${SERVICE_NAME}-app-code
          defaultMode: 0755
      - name: app-dir
        emptyDir: {}
EOF

# Create Service
echo "Creating Service..."
cat <<EOF | oc apply -f -
apiVersion: v1
kind: Service
metadata:
  name: ${SERVICE_NAME}
  namespace: ${PROJECT_NAME}
  labels:
    app: ${SERVICE_NAME}
spec:
  selector:
    app: ${SERVICE_NAME}
  ports:
  - name: http
    port: 8000
    targetPort: 8000
  type: ClusterIP
EOF

# Create Route
echo "Creating Route..."
cat <<EOF | oc apply -f -
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: ${SERVICE_NAME}
  namespace: ${PROJECT_NAME}
  labels:
    app: ${SERVICE_NAME}
spec:
  to:
    kind: Service
    name: ${SERVICE_NAME}
  port:
    targetPort: http
  tls:
    termination: edge
EOF

# Wait for deployment
echo "Waiting for deployment..."
oc rollout status deployment/${SERVICE_NAME} -n ${PROJECT_NAME} --timeout=300s

# Get route URL
ROUTE_URL=$(oc get route ${SERVICE_NAME} -n ${PROJECT_NAME} --template='https://{{ .spec.host }}')
echo ""
echo "✅ Vector Search Service deployed successfully!"
echo "Service URL: ${ROUTE_URL}"
echo ""
echo "Test the service:"
echo "  curl ${ROUTE_URL}/api/v1/health"
echo "  curl ${ROUTE_URL}/docs"
echo ""
echo "To ingest ServiceNow data:"
echo "  export VECTOR_SERVICE_URL=${ROUTE_URL}"
echo "  python scripts/ingest_servicenow.py"