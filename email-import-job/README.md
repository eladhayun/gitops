# Email Import Job

Kubernetes Job infrastructure for importing emails from Azure Blob Storage.

## Overview

This directory contains Kubernetes manifests for running email import jobs that:
1. Download `.eml` and `.mbox` files from Azure Blob Storage
2. Parse and extract email metadata and content
3. Generate OpenAI embeddings for semantic search
4. Upsert data to MariaDB database

## Files

- `job.yaml` - Job definition (template, not applied directly)
- `serviceaccount.yaml` - RBAC permissions for the job
- `secrets.yaml` - Azure storage credentials (encrypted with SOPS)
- `secrets-generator.yaml` - KSOPS generator configuration
- `kustomization.yaml` - Kustomize configuration

## Setup

### 1. Deploy Azure Blob Storage

```bash
cd ../../terraform
terraform apply

# Get credentials
terraform output storage_account_name
terraform output -raw storage_primary_access_key
```

### 2. Update Secrets

Edit `secrets.yaml` with the actual values:

```bash
# Decrypt (if using SOPS)
sops secrets.yaml

# Or edit directly
vim secrets.yaml
```

Update these fields:
```yaml
stringData:
  storage-account-name: "YOUR_STORAGE_ACCOUNT_NAME"
  storage-account-key: "YOUR_STORAGE_KEY_FROM_TERRAFORM"
```

### 3. Encrypt Secrets (if using SOPS)

```bash
# Encrypt the file
sops -e -i secrets.yaml
```

### 4. Deploy to Cluster

```bash
# Apply ServiceAccount and RBAC
kubectl apply -f serviceaccount.yaml --context=jshipster

# Apply secrets (Kustomize with KSOPS)
kubectl apply -k . --context=jshipster
```

### 5. Verify Deployment

```bash
# Check ServiceAccount
kubectl get sa email-import-sa --context=jshipster

# Check Secret
kubectl get secret azure-storage-secret --context=jshipster

# Verify RBAC
kubectl get role email-import-role --context=jshipster
kubectl get rolebinding email-import-rolebinding --context=jshipster
```

## Usage

### Trigger Job via API

Jobs are created dynamically by the backend API:

```bash
# Trigger import
curl -X POST http://your-backend-url/api/admin/trigger-email-import \
  -H "Content-Type: application/json"
```

### Manual Job Creation (for testing)

```bash
# Generate unique job name
JOB_NAME="email-import-$(date +%s)"

# Copy and modify job.yaml with the new name
cat job.yaml | sed "s/name: email-import/name: $JOB_NAME/" | \
  kubectl apply -f - --context=jshipster

# Monitor
kubectl get job $JOB_NAME -w --context=jshipster
kubectl logs -l job-name=$JOB_NAME -f --context=jshipster
```

## Monitoring

### Get Job Status

```bash
# List all email import jobs
kubectl get jobs -l app=email-import --context=jshipster

# Get specific job details
kubectl describe job email-import-1701267890 --context=jshipster

# Watch job progress
kubectl get pods -l app=email-import -w --context=jshipster
```

### View Logs

```bash
# Get logs from running job
kubectl logs -l job-name=email-import-1701267890 --context=jshipster -f

# Get logs from both containers
kubectl logs -l job-name=email-import-1701267890 --context=jshipster --all-containers

# Get init container logs (download phase)
kubectl logs -l job-name=email-import-1701267890 -c download-emails --context=jshipster

# Get main container logs (import phase)
kubectl logs -l job-name=email-import-1701267890 -c import-emails --context=jshipster
```

## Job Configuration

### Resource Limits

Default resources:
- **Memory**: 512Mi request, 2Gi limit
- **CPU**: 250m request, 1000m limit
- **Storage**: 5Gi ephemeral volume

To adjust for large imports, edit `job.yaml`:

```yaml
resources:
  requests:
    memory: "1Gi"
    cpu: "500m"
  limits:
    memory: "4Gi"
    cpu: "2000m"

volumes:
- name: email-data
  emptyDir:
    sizeLimit: 10Gi  # Increase if needed
```

### Job Parameters

- **backoffLimit**: 3 (max retries on failure)
- **ttlSecondsAfterFinished**: 86400 (24 hours, then auto-deleted)
- **restartPolicy**: Never (don't restart on failure)

### Images

- **Init Container**: `mcr.microsoft.com/azure-cli:latest`
- **Main Container**: `prodacr1234.azurecr.io/ids-backend:latest`

Update image tag for specific versions:
```yaml
image: prodacr1234.azurecr.io/ids-backend:v1.2.3
```

## Troubleshooting

### Secret Not Found

```bash
# Check if secret exists
kubectl get secret azure-storage-secret --context=jshipster

# If missing, create it manually
kubectl create secret generic azure-storage-secret \
  --from-literal=storage-account-name=prodstorage1234 \
  --from-literal=storage-account-key=YOUR_KEY \
  --context=jshipster
```

### Image Pull Errors

```bash
# Check events
kubectl get events --context=jshipster | grep email-import

# Common issue: ACR authentication
# Verify AKS has AcrPull role on the registry
az role assignment list --scope /subscriptions/.../Microsoft.ContainerRegistry/registries/prodacr1234
```

### Job Fails with Download Error

```bash
# Check init container logs
kubectl logs -l job-name=email-import-TIMESTAMP -c download-emails --context=jshipster

# Common causes:
# - Invalid storage credentials
# - Container name mismatch
# - No files in blob storage
```

### Job Fails with Database Error

```bash
# Check main container logs
kubectl logs -l job-name=email-import-TIMESTAMP -c import-emails --context=jshipster

# Verify database secret
kubectl get secret ids-secrets --context=jshipster -o yaml

# Test database connection
kubectl run -it --rm mariadb-test --image=mariadb:latest --context=jshipster -- \
  mariadb -h DATABASE_HOST -u DATABASE_USER -p
```

### OOMKilled (Out of Memory)

If the pod is killed due to memory limits:

```bash
# Check pod status
kubectl describe pod -l job-name=email-import-TIMESTAMP --context=jshipster

# Increase memory limits in job.yaml
# Then recreate the job
```

## Cleanup

### Delete Specific Job

```bash
kubectl delete job email-import-1701267890 --context=jshipster
```

### Delete All Email Import Jobs

```bash
# Delete completed jobs
kubectl delete jobs -l app=email-import,job-type=data-import --context=jshipster

# Force delete stuck jobs
kubectl delete jobs -l app=email-import --grace-period=0 --force --context=jshipster
```

### Clean Up Old Jobs Automatically

Jobs are automatically deleted 24 hours after completion thanks to `ttlSecondsAfterFinished`.

To change this:
```yaml
spec:
  ttlSecondsAfterFinished: 3600  # 1 hour
```

## ArgoCD Integration

This directory is not directly managed by ArgoCD since jobs are created dynamically via API.

However, the supporting resources (ServiceAccount, Secrets) can be synced:

```bash
# Create ArgoCD Application (optional)
kubectl apply -f - <<EOF
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: email-import-job
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/YOUR_ORG/gitops
    path: email-import-job
    targetRevision: main
  destination:
    server: https://kubernetes.default.svc
    namespace: default
  syncPolicy:
    automated:
      prune: false  # Don't auto-prune Jobs
      selfHeal: true
EOF
```

## Security

### Secrets Management

**Option 1: SOPS** (Recommended)
```bash
# Encrypt
sops -e -i secrets.yaml

# Decrypt for editing
sops secrets.yaml
```

**Option 2: Azure Key Vault**
```bash
# Install CSI driver
kubectl apply -f https://raw.githubusercontent.com/Azure/secrets-store-csi-driver-provider-azure/master/deployment/provider-azure-installer.yaml

# Use SecretProviderClass instead of Secret
```

### RBAC Permissions

The ServiceAccount has minimal permissions:
- Read secrets in default namespace
- Read configmaps in default namespace
- No cluster-wide permissions

To grant additional permissions, edit `serviceaccount.yaml`:
```yaml
rules:
- apiGroups: [""]
  resources: ["secrets", "configmaps"]
  verbs: ["get", "list"]
```

## Performance Tuning

### For Large Imports

**Increase resources:**
```yaml
resources:
  limits:
    memory: "8Gi"
    cpu: "4000m"
```

**Use faster storage:**
```yaml
volumes:
- name: email-data
  emptyDir:
    medium: Memory  # Use RAM instead of disk (faster but limited)
    sizeLimit: 10Gi
```

**Increase timeout:**
```yaml
spec:
  activeDeadlineSeconds: 43200  # 12 hours max
```

### Parallel Processing

To process multiple MBOX files in parallel, create multiple jobs:

```bash
# Create a job for each file
for file in file1.mbox file2.mbox file3.mbox; do
  JOB_NAME="email-import-$(echo $file | sed 's/\.mbox//')-$(date +%s)"
  # Create job with specific file pattern
done
```

## Monitoring with Prometheus

Add metrics annotations to the job:

```yaml
metadata:
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "8080"
```

## Related Documentation

- [Azure Blob Email Import Guide](../../ids/docs/AZURE_BLOB_EMAIL_IMPORT.md)
- [Quick Start Guide](../../ids/docs/AZURE_EMAIL_QUICK_START.md)
- [Terraform Storage Setup](../../terraform/STORAGE_SETUP.md)
- [Main GitOps README](../README.md)

