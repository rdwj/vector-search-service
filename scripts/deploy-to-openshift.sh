#!/bin/bash
# Deploy Vector Search Service to OpenShift with existing PGVector

set -e

# Configuration
PROJECT_NAME="pgvector"
SERVICE_NAME="vector-search-service"
IMAGE_NAME="${SERVICE_NAME}:latest"

# Database configuration from provided details
DB_HOST="postgres-pgvector.pgvector.svc.cluster.local"
DB_PORT="5432"
DB_NAME="vectordb"
DB_USER="vectoruser"
DB_PASSWORD="vectorpass"

echo "Deploying Vector Search Service to OpenShift..."

# Check if logged in
if ! oc whoami &> /dev/null; then
    echo "Error: Not logged into OpenShift"
    exit 1
fi

# Switch to project
echo "Switching to project: ${PROJECT_NAME}"
oc project ${PROJECT_NAME} || oc new-project ${PROJECT_NAME}

# Change to service directory
cd /Users/wjackson/Developer/LLNL/vector-search-service

# Create BuildConfig and ImageStream instead of using podman
echo "Creating ImageStream..."
oc create imagestream ${SERVICE_NAME} -n ${PROJECT_NAME} --dry-run=client -o yaml | oc apply -f -

echo "Creating BuildConfig..."
cat <<EOF | oc apply -f -
apiVersion: build.openshift.io/v1
kind: BuildConfig
metadata:
  name: ${SERVICE_NAME}
  namespace: ${PROJECT_NAME}
spec:
  output:
    to:
      kind: ImageStreamTag
      name: ${SERVICE_NAME}:latest
  source:
    type: Binary
    binary: {}
  strategy:
    type: Docker
    dockerStrategy:
      dockerfilePath: Containerfile
EOF

# Start build from local directory
echo "Starting build..."
oc start-build ${SERVICE_NAME} --from-dir=. --follow -n ${PROJECT_NAME}

# Create ConfigMap for service configuration
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
  LOG_LEVEL: "INFO"
  MAX_BATCH_SIZE: "100"
  SIMILARITY_SEARCH_LIMIT: "100"
EOF

# Create Secret for database password
echo "Creating Secret..."
oc create secret generic ${SERVICE_NAME}-secret \
  --from-literal=POSTGRES_PASSWORD="${DB_PASSWORD}" \
  --dry-run=client -o yaml | oc apply -f -

# Deploy the service
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
        image: image-registry.openshift-image-registry.svc:5000/${PROJECT_NAME}/${SERVICE_NAME}:latest
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
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "1Gi"
            cpu: "500m"
        readinessProbe:
          httpGet:
            path: /api/v1/health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /api/v1/health
            port: 8000
          initialDelaySeconds: 30
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
oc rollout status deployment/${SERVICE_NAME} -n ${PROJECT_NAME}

# Get route URL
ROUTE_URL=$(oc get route ${SERVICE_NAME} -n ${PROJECT_NAME} --template='https://{{ .spec.host }}')
echo ""
echo "Vector Search Service deployed successfully!"
echo "Service URL: ${ROUTE_URL}"
echo ""
echo "To ingest ServiceNow data, run:"
echo "export VECTOR_SERVICE_URL=${ROUTE_URL}"
echo "python scripts/ingest_servicenow.py"
echo ""
echo "API Documentation: ${ROUTE_URL}/docs"