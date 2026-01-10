# Loki Logging Stack

This directory contains the GitOps configuration for Loki + Promtail log aggregation.

## Overview

- **Loki**: Log aggregation system (StatefulSet)
- **Promtail**: Log collector (DaemonSet, 1 per node)
- **Storage**: Azure Blob Storage (configured in secrets)

## Setup Instructions

### 1. Create Azure Storage Account (if not exists)

```bash
# Create storage account for logs
az storage account create \
  --name jshipsterlogs \
  --resource-group prod-rg \
  --location eastus \
  --sku Standard_LRS \
  --access-tier Hot

# Create container for logs
az storage container create \
  --name loki-logs \
  --account-name jshipsterlogs \
  --auth-mode login
```

### 2. Get Storage Account Key

```bash
# Get storage account key
STORAGE_KEY=$(az storage account keys list \
  --resource-group prod-rg \
  --account-name jshipsterlogs \
  --query "[0].value" -o tsv)

STORAGE_NAME="jshipsterlogs"
```

### 3. Update Secrets

**Option A: Using SOPS (Recommended)**

```bash
# Edit the secrets file
sops gitops/loki/secrets-generator.yaml

# Replace:
#   account-name: "REPLACE_WITH_STORAGE_ACCOUNT_NAME"
#   account-key: "REPLACE_WITH_STORAGE_ACCOUNT_KEY"
# With actual values
```

**Option B: Direct kubectl (Not recommended for production)**

```bash
kubectl create secret generic loki-azure-storage \
  --from-literal=account-name=jshipsterlogs \
  --from-literal=account-key=$STORAGE_KEY \
  -n loki \
  --context=jshipster \
  --dry-run=client -o yaml | kubectl apply -f -
```

### 4. Deploy via ArgoCD

Add to `gitops/apps/kustomization.yaml`:

```yaml
resources:
  - loki.yaml
```

Create `gitops/apps/loki.yaml`:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: loki
  namespace: argocd
spec:
  project: default
  source:
    repoURL: <your-gitops-repo-url>
    targetRevision: main
    path: gitops/loki
  destination:
    server: https://kubernetes.default.svc
    namespace: loki
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

## Cost Estimate

- **Storage**: ~$0.0184/GB/month
- **Typical usage**: 10-20 GB/month = ~$0.18-0.37/month
- **Loki/Promtail**: Runs in-cluster (no additional cost)

## Retention

- **Default**: 30 days (720h)
- **Configurable**: Edit `configmap.yaml` → `retention_period`
- **Azure Blob Lifecycle**: Can move old logs to Archive tier (even cheaper)

## Accessing Loki

### Via Internet (Ingress)

Loki is accessible via ingress at: **https://logs.jshipster.io**

- **DNS**: Automatically managed by external-dns (Cloudflare)
- **TLS**: Automatically provisioned by cert-manager (Let's Encrypt)
- **Cloudflare Proxy**: Enabled (DDoS protection)

### Querying Logs via API

```bash
# Query logs from internet
curl -G -s "https://logs.jshipster.io/loki/api/v1/query_range" \
  --data-urlencode 'query={namespace="ids"}' \
  --data-urlencode 'start='$(date -u -d '1 hour ago' +%s)'000000000' \
  --data-urlencode 'end='$(date -u +%s)'000000000' \
  --data-urlencode 'limit=100' | jq
```

### Via kubectl (Local Access)

```bash
# Port forward to Loki
kubectl port-forward -n loki svc/loki 3100:3100 --context=jshipster

# Query logs (example)
curl -G -s "http://localhost:3100/loki/api/v1/query_range" \
  --data-urlencode 'query={namespace="ids"}' \
  --data-urlencode 'start=2024-01-01T00:00:00Z' \
  --data-urlencode 'end=2024-01-01T23:59:59Z' \
  --data-urlencode 'limit=100' | jq
```

### Via Grafana (Optional)

Deploy Grafana and add Loki as data source:
- **URL**: `http://loki.loki.svc.cluster.local:3100` (internal)
- **Or**: `https://logs.jshipster.io` (external via ingress)

## Resource Usage

- **Loki**: 256Mi request, 512Mi limit
- **Promtail** (per node): 64Mi request, 128Mi limit
- **Total**: ~320Mi + (64Mi × number of nodes)

## Troubleshooting

### Check Promtail logs
```bash
kubectl logs -n loki -l app=promtail --context=jshipster
```

### Check Loki logs
```bash
kubectl logs -n loki -l app=loki --context=jshipster
```

### Verify storage connection
```bash
kubectl exec -n loki -it loki-0 --context=jshipster -- \
  env | grep AZURE_STORAGE
```

### Check if logs are being collected
```bash
# Check Promtail targets
kubectl port-forward -n loki svc/promtail 3101:3101
curl http://localhost:3101/targets
```

## Ingress Configuration

The ingress is configured with:
- **Hostname**: `logs.jshipster.io`
- **TLS**: Automatic via cert-manager (Let's Encrypt)
- **External-DNS**: Automatically creates DNS record in Cloudflare
- **Cloudflare Proxy**: Enabled for DDoS protection

After deployment, external-dns will automatically:
1. Create DNS record: `logs.jshipster.io` → Ingress IP
2. Enable Cloudflare proxy (orange cloud)
3. cert-manager will provision TLS certificate

**Verify ingress:**
```bash
# Check ingress status
kubectl get ingress -n loki --context=jshipster

# Check DNS record (should be created by external-dns)
dig logs.jshipster.io

# Check TLS certificate (should be provisioned by cert-manager)
kubectl get certificate -n loki --context=jshipster
```

## Authentication

Loki ingress is protected with **Basic Authentication**.

### Setup Authentication

**Option 1: Automated Setup (Recommended)**
```bash
cd gitops/loki
./setup-auth.sh
```

This will:
1. Prompt for username and password
2. Generate htpasswd file
3. Create Kubernetes secret

**Option 2: Manual Setup**
```bash
# Generate credentials
htpasswd -c auth loki-user

# Create secret
kubectl create secret generic loki-auth \
  --from-file=auth \
  -n loki \
  --context=jshipster
```

### Accessing Loki

When accessing https://logs.jshipster.io, you'll be prompted for:
- **Username**: (the one you set up)
- **Password**: (the one you set up)

**Example with curl:**
```bash
curl -u username:password -G -s "https://logs.jshipster.io/loki/api/v1/query_range" \
  --data-urlencode 'query={namespace="ids"}' \
  --data-urlencode 'start='$(date -u -d '1 hour ago' +%s)'000000000' \
  --data-urlencode 'end='$(date -u +%s)'000000000' \
  --data-urlencode 'limit=10' | jq
```

### Update Credentials

To change username/password:
```bash
./setup-auth.sh
# Or manually:
htpasswd auth new-username
kubectl create secret generic loki-auth --from-file=auth -n loki --context=jshipster --dry-run=client -o yaml | kubectl apply -f -
```

## Notes

- Promtail automatically discovers and collects logs from all pods
- No workload changes needed
- Logs are stored in Azure Blob Storage (persistent)
- Retention is configurable (default 30 days)
- Accessible from internet at https://logs.jshipster.io
- **Protected with Basic Authentication**
