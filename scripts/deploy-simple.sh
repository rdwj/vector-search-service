#!/bin/bash
# Simple deployment script for Vector Search Service

set -e

# Configuration
PROJECT_NAME="pgvector"
SERVICE_NAME="vector-search-service"

# Database configuration from provided details
DB_HOST="postgres-pgvector.pgvector.svc.cluster.local"
DB_PORT="5432"
DB_NAME="vectordb"
DB_USER="vectoruser"
DB_PASSWORD="vectorpass"

echo "Deploying Vector Search Service to OpenShift (Simple Method)..."

# Check if logged in
if ! oc whoami &> /dev/null; then
    echo "Error: Not logged into OpenShift"
    exit 1
fi

# Switch to project
echo "Switching to project: ${PROJECT_NAME}"
oc project ${PROJECT_NAME} || oc new-project ${PROJECT_NAME}

# Create a simple deployment using a pre-built Python image
echo "Creating deployment from template..."

# Create ConfigMap
cat <<EOF | oc apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: ${SERVICE_NAME}-config
  namespace: ${PROJECT_NAME}
data:
  requirements.txt: |
$(cat requirements.txt | sed 's/^/    /')
EOF

# Create the application code ConfigMap
echo "Creating application code ConfigMap..."
cat <<EOF | oc apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: ${SERVICE_NAME}-app
  namespace: ${PROJECT_NAME}
data:
  startup.sh: |
    #!/bin/bash
    cd /app
    pip install --no-cache-dir -r /config/requirements.txt
    python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
EOF

# Create Secret
oc create secret generic ${SERVICE_NAME}-secret \
  --from-literal=POSTGRES_PASSWORD="${DB_PASSWORD}" \
  --dry-run=client -o yaml | oc apply -f -

# Create Deployment using Python base image
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
        image: python:3.11-slim
        command: ["/bin/bash", "-c"]
        args: ["pip install fastapi uvicorn httpx asyncpg psycopg2-binary pgvector pydantic pydantic-settings python-multipart sentence-transformers numpy scikit-learn sqlalchemy && cd /app && python -m uvicorn src.main:app --host 0.0.0.0 --port 8000"]
        ports:
        - containerPort: 8000
        env:
        - name: POSTGRES_HOST
          value: "${DB_HOST}"
        - name: POSTGRES_PORT
          value: "${DB_PORT}"
        - name: POSTGRES_DB
          value: "${DB_NAME}"
        - name: POSTGRES_USER
          value: "${DB_USER}"
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: ${SERVICE_NAME}-secret
              key: POSTGRES_PASSWORD
        - name: DEFAULT_EMBEDDING_DIMENSION
          value: "384"
        - name: LOG_LEVEL
          value: "INFO"
        volumeMounts:
        - name: app-code
          mountPath: /app
        - name: config
          mountPath: /config
        resources:
          requests:
            memory: "1Gi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
      volumes:
      - name: app-code
        emptyDir: {}
      - name: config
        configMap:
          name: ${SERVICE_NAME}-config
EOF

# Create Service
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

echo ""
echo "Note: This is a simplified deployment. The application code needs to be manually copied to the pod."
echo ""
echo "To copy the application code:"
echo "1. Wait for the pod to be running:"
echo "   oc get pods -n ${PROJECT_NAME} -l app=${SERVICE_NAME}"
echo ""
echo "2. Copy the source code to the pod:"
echo "   POD_NAME=\$(oc get pods -n ${PROJECT_NAME} -l app=${SERVICE_NAME} -o jsonpath='{.items[0].metadata.name}')"
echo "   oc cp src \$POD_NAME:/app/src -n ${PROJECT_NAME}"
echo "   oc cp config \$POD_NAME:/app/config -n ${PROJECT_NAME}"
echo "   oc cp scripts \$POD_NAME:/app/scripts -n ${PROJECT_NAME}"
echo ""
echo "3. Restart the pod:"
echo "   oc delete pod \$POD_NAME -n ${PROJECT_NAME}"
echo ""

# Get route URL
ROUTE_URL=$(oc get route ${SERVICE_NAME} -n ${PROJECT_NAME} --template='https://{{ .spec.host }}' 2>/dev/null || echo "Route not ready yet")
echo "Service URL: ${ROUTE_URL}"