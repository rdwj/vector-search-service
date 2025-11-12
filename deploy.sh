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

echo "📦 Deploying Vector Search Service..."
oc apply -k manifests/ -n "$NAMESPACE"

echo ""
echo "=============================================================="
echo "✅ Vector Search Service deployed successfully!"
echo ""
echo "Monitor deployment:"
echo "  oc get pods -n $NAMESPACE -l app=vector-search-service -w"
echo ""
echo "Check logs:"
echo "  oc logs -f deployment/vector-search-service -n $NAMESPACE"
echo ""
echo "Get route URL:"
echo "  oc get route vector-search-service -n $NAMESPACE"
echo ""
echo "Test health endpoint:"
echo "  ROUTE=\$(oc get route vector-search-service -n $NAMESPACE -o jsonpath='{.spec.host}')"
echo "  curl https://\$ROUTE/api/v1/health"
echo ""
echo "API Documentation:"
echo "  https://\$ROUTE/docs"
