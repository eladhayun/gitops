#!/bin/bash
# Setup script for Loki Azure Blob Storage

set -e

STORAGE_ACCOUNT="jshipsterprod410479"
RESOURCE_GROUP="prod-rg"
CONTAINER_NAME="loki-logs"
NAMESPACE="loki"
CONTEXT="jshipster"

echo "Setting up Loki Azure Blob Storage..."

# Check if container exists, create if not
echo "Checking for container: $CONTAINER_NAME"
if az storage container show \
  --name "$CONTAINER_NAME" \
  --account-name "$STORAGE_ACCOUNT" \
  --auth-mode login \
  >/dev/null 2>&1; then
  echo "✓ Container $CONTAINER_NAME already exists"
else
  echo "Creating container: $CONTAINER_NAME"
  az storage container create \
    --name "$CONTAINER_NAME" \
    --account-name "$STORAGE_ACCOUNT" \
    --auth-mode login
  echo "✓ Container created"
fi

# Get storage account key
echo "Getting storage account key..."
STORAGE_KEY=$(az storage account keys list \
  --resource-group "$RESOURCE_GROUP" \
  --account-name "$STORAGE_ACCOUNT" \
  --query "[0].value" -o tsv)

if [ -z "$STORAGE_KEY" ]; then
  echo "❌ Failed to get storage account key"
  exit 1
fi

# Create or update secret
echo "Creating Kubernetes secret..."
kubectl create secret generic loki-azure-storage \
  --from-literal=account-name="$STORAGE_ACCOUNT" \
  --from-literal=account-key="$STORAGE_KEY" \
  -n "$NAMESPACE" \
  --context="$CONTEXT" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "✓ Secret created/updated"
echo ""
echo "Next steps:"
echo "1. Deploy Loki via ArgoCD (add loki.yaml to apps/kustomization.yaml)"
echo "2. Or apply manually: kubectl apply -k gitops/loki --context=$CONTEXT"
echo ""
echo "Storage account: $STORAGE_ACCOUNT"
echo "Container: $CONTAINER_NAME"
echo "Cost: ~\$0.0184/GB/month"
