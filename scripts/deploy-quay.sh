#!/bin/bash
# Deploy Vector Search Service using Quay.io image

set -e

# Configuration
PROJECT_NAME="pgvector"
SERVICE_NAME="vector-search-service"
IMAGE="quay.io/wjackson/servicenow-vector-rag:latest"

# Database configuration
DB_HOST="postgres-pgvector.pgvector.svc.cluster.local"
DB_PORT="5432"
DB_NAME="vectordb"
DB_USER="vectoruser"
DB_PASSWORD="vectorpass"

echo "Deploying Vector Search Service from Quay.io..."

# Switch to project
echo "Switching to project: ${PROJECT_NAME}"
oc project ${PROJECT_NAME}

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
        image: ${IMAGE}
        imagePullPolicy: Always
        ports:
        - containerPort: 8000
          name: http
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
          initialDelaySeconds: 30
          periodSeconds: 10
          timeoutSeconds: 5
        livenessProbe:
          httpGet:
            path: /api/v1/health
            port: 8000
          initialDelaySeconds: 60
          periodSeconds: 30
          timeoutSeconds: 5
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
oc rollout status deployment/${SERVICE_NAME} -n ${PROJECT_NAME} --timeout=300s || echo "Deployment is taking longer than expected"

# Get route URL
ROUTE_URL=$(oc get route ${SERVICE_NAME} -n ${PROJECT_NAME} --template='https://{{ .spec.host }}')
echo ""
echo "Vector Search Service deployed successfully!"
echo "Service URL: ${ROUTE_URL}"
echo ""
echo "Check deployment status:"
echo "  oc get pods -n ${PROJECT_NAME} -l app=${SERVICE_NAME}"
echo ""
echo "View logs:"
echo "  oc logs -f deployment/${SERVICE_NAME} -n ${PROJECT_NAME}"
echo ""
echo "Test the service:"
echo "  curl ${ROUTE_URL}/api/v1/health"
echo ""
echo "To ingest ServiceNow data:"
echo "  export VECTOR_SERVICE_URL=${ROUTE_URL}"
echo "  python scripts/ingest_servicenow.py"
echo ""
echo "API Documentation: ${ROUTE_URL}/docs"