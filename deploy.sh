#!/bin/bash

# Vector Search Service Deployment Script
# Deploys the vector-search service to OpenShift

set -e

NAMESPACE=${1:-servicenow-ai-poc}

echo "🚀 Deploying Vector Search Service to namespace: $NAMESPACE"
echo "=============================================================="

# Check if namespace exists
if ! oc get namespace "$NAMESPACE" >/dev/null 2>&1; then
    echo "❌ ERROR: Namespace '$NAMESPACE' does not exist!"
    echo ""
    echo "Please deploy the pgvector backend first:"
    echo "  cd ../pgvector-poc-backend"
    echo "  ./scripts/deploy-backend.sh $NAMESPACE"
    exit 1
fi

# Check if postgres is running
if ! oc get statefulset postgres-pgvector -n "$NAMESPACE" >/dev/null 2>&1; then
    echo "❌ ERROR: PostgreSQL backend not found in namespace '$NAMESPACE'"
    echo ""
    echo "Please deploy the pgvector backend first:"
    echo "  cd ../pgvector-poc-backend"
    echo "  ./scripts/deploy-backend.sh $NAMESPACE"
    exit 1
fi

echo "✅ Prerequisites verified"
echo ""

echo "📦 Step 1: Creating BuildConfig and ImageStream..."
oc apply -f manifests/buildconfig.yaml -n "$NAMESPACE"

echo ""
echo "🔨 Step 2: Building container image from source..."
oc start-build vector-search-service \
  --from-dir=. \
  --follow \
  -n "$NAMESPACE"

echo ""
echo "📦 Step 3: Deploying Vector Search Service..."
oc apply -k manifests/ -n "$NAMESPACE"

echo ""
echo "⏳ Step 4: Waiting for deployment to be ready..."
oc rollout status deployment/vector-search-service -n "$NAMESPACE" --timeout=5m

echo ""
echo "🔍 Step 5: Verifying service health..."
ROUTE=$(oc get route vector-search-service -n "$NAMESPACE" -o jsonpath='{.spec.host}')
echo "Route URL: https://$ROUTE"

# Wait a moment for route to propagate
sleep 5

# Test health endpoint
if curl -sf "https://$ROUTE/api/v1/health" > /dev/null; then
    echo "✅ Health check passed!"
else
    echo "⚠️  Health check failed - service may still be initializing"
    echo "Check logs: oc logs -f deployment/vector-search-service -n $NAMESPACE"
fi

echo ""
echo "=============================================================="
echo "✅ Vector Search Service deployed successfully!"
echo ""
echo "Service URL: https://$ROUTE"
echo "Health endpoint: https://$ROUTE/api/v1/health"
echo "API Documentation: https://$ROUTE/docs"
echo ""
echo "Monitor deployment:"
echo "  oc get pods -n $NAMESPACE -l app=vector-search-service -w"
echo ""
echo "Check logs:"
echo "  oc logs -f deployment/vector-search-service -n $NAMESPACE"
