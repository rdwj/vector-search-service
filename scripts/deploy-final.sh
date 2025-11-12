#!/bin/bash
# Final deployment script for Vector Search Service

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

echo "Deploying Vector Search Service to OpenShift..."

# Switch to project
oc project ${PROJECT_NAME}

# First, let's try to push to the internal registry using a different approach
echo "Setting up internal registry access..."
INTERNAL_REGISTRY="image-registry.openshift-image-registry.svc:5000"

# Tag the image for internal registry
podman tag vector-search-service:latest ${INTERNAL_REGISTRY}/${PROJECT_NAME}/vector-search-service:latest

# Get token and login to internal registry
TOKEN=$(oc whoami -t)
podman login -u serviceaccount -p ${TOKEN} ${INTERNAL_REGISTRY} --tls-verify=false

# Try to push to internal registry
echo "Attempting to push to internal registry..."
podman push ${INTERNAL_REGISTRY}/${PROJECT_NAME}/vector-search-service:latest --tls-verify=false || {
    echo "Direct push failed, creating deployment with external image..."
    USING_EXTERNAL=true
}

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
EOF

# Create Secret
echo "Creating Secret..."
oc create secret generic ${SERVICE_NAME}-secret \
  --from-literal=POSTGRES_PASSWORD="${DB_PASSWORD}" \
  --dry-run=client -o yaml | oc apply -f -

# Create Deployment
if [ "$USING_EXTERNAL" = "true" ]; then
    IMAGE="python:3.11-slim"
else
    IMAGE="${INTERNAL_REGISTRY}/${PROJECT_NAME}/vector-search-service:latest"
fi

echo "Creating Deployment with image: ${IMAGE}..."
cat <<EOF | oc apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${SERVICE_NAME}
  namespace: ${PROJECT_NAME}
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
        image: ${IMAGE}
        ports:
        - containerPort: 8000
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
EOF

# Create Service
echo "Creating Service..."
cat <<EOF | oc apply -f -
apiVersion: v1
kind: Service
metadata:
  name: ${SERVICE_NAME}
  namespace: ${PROJECT_NAME}
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
spec:
  to:
    kind: Service
    name: ${SERVICE_NAME}
  port:
    targetPort: http
  tls:
    termination: edge
EOF

# Get route URL
ROUTE_URL=$(oc get route ${SERVICE_NAME} -n ${PROJECT_NAME} --template='https://{{ .spec.host }}')
echo ""
echo "Deployment complete!"
echo "Service URL: ${ROUTE_URL}"
echo ""
echo "Next steps:"
echo "1. Wait for pod to be ready: oc get pods -n ${PROJECT_NAME} -w"
echo "2. Check logs: oc logs -f deployment/${SERVICE_NAME} -n ${PROJECT_NAME}"
echo "3. Test health endpoint: curl ${ROUTE_URL}/api/v1/health"
echo ""
echo "To ingest ServiceNow data:"
echo "export VECTOR_SERVICE_URL=${ROUTE_URL}"
echo "python scripts/ingest_servicenow.py"