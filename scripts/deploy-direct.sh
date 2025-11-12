#!/bin/bash
# Direct deployment using pre-built container

set -e

# Configuration
PROJECT_NAME="pgvector"
SERVICE_NAME="vector-search-service"

# Database configuration
DB_HOST="postgres-pgvector.pgvector.svc.cluster.local"
DB_PORT="5432"
DB_NAME="vectordb"
DB_USER="vectoruser"
DB_PASSWORD="vectorpass"

echo "Deploying Vector Search Service directly..."

# Switch to project
oc project ${PROJECT_NAME}

# Clean up any existing resources
echo "Cleaning up existing resources..."
oc delete deployment ${SERVICE_NAME} --ignore-not-found=true
oc delete service ${SERVICE_NAME} --ignore-not-found=true
oc delete route ${SERVICE_NAME} --ignore-not-found=true
oc delete configmap ${SERVICE_NAME}-config --ignore-not-found=true
oc delete secret ${SERVICE_NAME}-secret --ignore-not-found=true

# Create ConfigMap
echo "Creating ConfigMap..."
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
  EMBEDDING_MODEL: "sentence-transformers/all-MiniLM-L6-v2"
  LOG_LEVEL: "INFO"
  MAX_BATCH_SIZE: "100"
  SIMILARITY_SEARCH_LIMIT: "100"
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
        image: quay.io/ai-heroes/fastapi-rag:latest
        command: ["/bin/bash", "-c"]
        args: 
          - |
            pip install fastapi uvicorn httpx asyncpg psycopg2-binary pgvector pydantic pydantic-settings python-multipart sentence-transformers numpy scikit-learn sqlalchemy aiohttp alembic openai
            git clone https://github.com/your-repo/vector-search-service.git /app || echo "Using local code"
            cd /app
            python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
        ports:
        - containerPort: 8000
          protocol: TCP
        envFrom:
        - configMapRef:
            name: ${SERVICE_NAME}-config
        - secretRef:
            name: ${SERVICE_NAME}-secret
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
        readinessProbe:
          httpGet:
            path: /api/v1/health
            port: 8000
          initialDelaySeconds: 60
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /api/v1/health
            port: 8000
          initialDelaySeconds: 90
          periodSeconds: 30
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
    protocol: TCP
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
    weight: 100
  port:
    targetPort: http
  tls:
    termination: edge
    insecureEdgeTerminationPolicy: Redirect
EOF

# Wait for deployment
echo "Waiting for deployment to be ready..."
oc wait --for=condition=available --timeout=300s deployment/${SERVICE_NAME} -n ${PROJECT_NAME} || echo "Deployment taking longer than expected"

# Get pod name
POD_NAME=$(oc get pods -n ${PROJECT_NAME} -l app=${SERVICE_NAME} -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")

if [ -n "$POD_NAME" ]; then
  echo "Pod created: $POD_NAME"
  echo ""
  echo "Now copy the source code to the pod:"
  echo "oc cp src ${POD_NAME}:/app/src -n ${PROJECT_NAME}"
  echo "oc cp config ${POD_NAME}:/app/config -n ${PROJECT_NAME}"
  echo "oc cp scripts ${POD_NAME}:/app/scripts -n ${PROJECT_NAME}"
  echo ""
  echo "Then restart the pod:"
  echo "oc delete pod ${POD_NAME} -n ${PROJECT_NAME}"
fi

# Get route URL
ROUTE_URL=$(oc get route ${SERVICE_NAME} -n ${PROJECT_NAME} --template='https://{{ .spec.host }}' 2>/dev/null || echo "Route not ready yet")
echo ""
echo "Service URL: ${ROUTE_URL}"
echo ""
echo "To ingest ServiceNow data:"
echo "export VECTOR_SERVICE_URL=${ROUTE_URL}"
echo "python scripts/ingest_servicenow.py"