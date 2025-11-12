#!/bin/bash
# Deploy using OpenShift BuildConfig (builds in cluster)

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

echo "Deploying Vector Search Service using BuildConfig..."

# Switch to project
oc project ${PROJECT_NAME}

# Clean up existing BuildConfig if it exists
oc delete bc ${SERVICE_NAME} --ignore-not-found=true
oc delete is ${SERVICE_NAME} --ignore-not-found=true

# Create ImageStream
echo "Creating ImageStream..."
cat <<EOF | oc apply -f -
apiVersion: image.openshift.io/v1
kind: ImageStream
metadata:
  name: ${SERVICE_NAME}
  namespace: ${PROJECT_NAME}
spec:
  lookupPolicy:
    local: false
EOF

# Create BuildConfig with Git source
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
    type: Git
    git:
      uri: https://github.com/your-username/vector-search-service.git
    contextDir: .
  strategy:
    type: Docker
    dockerStrategy:
      dockerfilePath: Containerfile
  triggers:
  - type: ConfigChange
  - type: ImageChange
EOF

echo "Note: Since we don't have a Git repository, let's use binary source instead..."

# Delete and recreate with binary source
oc delete bc ${SERVICE_NAME}

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

# Create tar file for source
echo "Creating source archive..."
tar -czf /tmp/vector-service-source.tar.gz --exclude='.git' --exclude='__pycache__' --exclude='*.pyc' .

# Start build with source
echo "Starting build..."
oc start-build ${SERVICE_NAME} --from-archive=/tmp/vector-service-source.tar.gz --follow

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
echo "Creating Deployment..."
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
        image: image-registry.openshift-image-registry.svc:5000/${PROJECT_NAME}/${SERVICE_NAME}:latest
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
EOF

# Create Service and Route
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
echo "Build and deployment started!"
echo "Service URL: ${ROUTE_URL}"
echo ""
echo "Monitor build: oc logs -f bc/${SERVICE_NAME}"
echo "Monitor deployment: oc rollout status deployment/${SERVICE_NAME}"
echo ""
echo "Once ready, test with: curl ${ROUTE_URL}/api/v1/health"