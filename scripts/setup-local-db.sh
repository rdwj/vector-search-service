#!/bin/bash

set -e

# Configuration
DB_NAME="vector_search"
DB_USER="vector_user"
DB_PASSWORD="vector_password"
DB_PORT="5432"
CONTAINER_NAME="vector-postgres"

echo "Setting up PostgreSQL with pgvector for local development..."

# Stop and remove existing container if it exists
podman stop $CONTAINER_NAME 2>/dev/null || true
podman rm $CONTAINER_NAME 2>/dev/null || true

# Run PostgreSQL with pgvector extension
podman run -d \
  --name $CONTAINER_NAME \
  -e POSTGRES_DB=$DB_NAME \
  -e POSTGRES_USER=$DB_USER \
  -e POSTGRES_PASSWORD=$DB_PASSWORD \
  -p $DB_PORT:5432 \
  -v vector-postgres-data:/var/lib/postgresql/data \
  pgvector/pgvector:pg15

# Wait for database to be ready
echo "Waiting for database to be ready..."
sleep 10

# Run initialization script
podman exec -i $CONTAINER_NAME psql -U $DB_USER -d $DB_NAME < scripts/init-db.sql

echo "PostgreSQL with pgvector is ready!"
echo "Connection string: postgresql://$DB_USER:$DB_PASSWORD@localhost:$DB_PORT/$DB_NAME"