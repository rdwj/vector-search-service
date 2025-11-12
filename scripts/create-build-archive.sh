#!/bin/bash
# Create a build archive for OpenShift binary build

set -e

echo "Creating build archive for Vector Search Service..."

# Change to service directory
cd /Users/wjackson/Developer/LLNL/vector-search-service

# Create a temporary directory
TEMP_DIR=$(mktemp -d)
echo "Using temp directory: $TEMP_DIR"

# Copy necessary files
echo "Copying files..."
cp -r src $TEMP_DIR/
cp -r config $TEMP_DIR/
cp -r scripts $TEMP_DIR/
cp requirements.txt $TEMP_DIR/
cp requirements-dev.txt $TEMP_DIR/
cp Containerfile $TEMP_DIR/

# Create the archive
echo "Creating archive..."
cd $TEMP_DIR
tar -czf /tmp/vector-search-service.tar.gz .

echo "Archive created at: /tmp/vector-search-service.tar.gz"
echo ""
echo "To use this archive:"
echo "oc start-build vector-search-service --from-archive=/tmp/vector-search-service.tar.gz -n pgvector"

# Cleanup
rm -rf $TEMP_DIR