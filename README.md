# GitOps Repository for Johnson Application

This repository contains Kubernetes manifests for the Johnson application, managed by ArgoCD.

## Structure

```
.
├── apps/                      # ArgoCD Application definitions
│   ├── apps.yaml             # App-of-apps pattern
│   ├── johnson-frontend.yaml # Frontend application
│   ├── johnson-backend.yaml  # Backend application
│   ├── linux-shell.yaml      # Linux shell example
│   └── kustomization.yaml    # Kustomize config
├── johnson-frontend/          # Frontend Kubernetes manifests
│   ├── deployment.yaml       # Deployment and Service
│   └── kustomization.yaml
├── johnson-backend/           # Backend Kubernetes manifests
│   ├── deployment.yaml       # Deployment and Service
│   └── kustomization.yaml
└── linux-shell/               # Example application
    ├── deployment.yaml
    └── kustomization.yaml
```

## Applications

### Johnson Frontend
- **Namespace**: `default`
- **Service**: `johnson-frontend` (ClusterIP on port 80)
- **Replicas**: 1
- **Auto-sync**: Enabled

### Johnson Backend
- **Namespace**: `default`
- **Service**: `johnson-backend` (ClusterIP on port 8000)
- **Replicas**: 1
- **Auto-sync**: Enabled
- **Health checks**: Liveness and readiness probes on `/health`

## Prerequisites

1. Kubernetes cluster with ArgoCD installed
2. Azure Container Registry credentials configured
3. Kubernetes secrets created manually (see below)

## Setup

### 1. Create Kubernetes Secrets

⚠️ **Important**: Secrets are NOT stored in git due to GitHub push protection. You must create them manually.

See [`johnson-backend/CREATE-SECRETS.md`](johnson-backend/CREATE-SECRETS.md) for detailed instructions.

Quick command:

```bash
kubectl create secret generic johnson-backend-secrets \
  --from-literal=JOHNSON_DATABASE_URL='your-database-url' \
  --from-literal=JOHNSON_AUTH_SECRET='your-auth-secret' \
  --from-literal=JOHNSON_RESET_SECRET='your-reset-secret' \
  --from-literal=WHATSAPP_TWILIO_ACCOUNT_SID='your-twilio-sid' \
  --from-literal=WHATSAPP_TWILIO_AUTH_TOKEN='your-twilio-token' \
  --namespace default
```

### 2. Configure Image Pull Secrets

```bash
# Create image pull secret for Azure Container Registry
kubectl create secret docker-registry acr-secret \
  --docker-server=<registry>.azurecr.io \
  --docker-username=<username> \
  --docker-password=<password> \
  -n default

# Update deployments to use the secret (if needed)
# Add to spec.template.spec in deployment.yaml:
#   imagePullSecrets:
#   - name: acr-secret
```

### 3. Deploy ArgoCD Applications

```bash
# Apply app-of-apps (will create all applications)
kubectl apply -f apps/apps.yaml

# Or apply individual applications
kubectl apply -f apps/johnson-frontend.yaml
kubectl apply -f apps/johnson-backend.yaml
```

### 4. Verify Deployment

```bash
# Check ArgoCD applications
kubectl get applications -n argocd

# Check pods
kubectl get pods -n default

# Check services
kubectl get services -n default
```

## Automated Updates

This repository is automatically updated by GitHub Actions workflows in the [johnson repository](https://github.com/eladhayun/johnson).

When code is pushed to the `main` branch:
1. GitHub Actions builds and pushes Docker images to Azure Container Registry
2. The workflow updates `deployment.yaml` files with new image tags
3. ArgoCD detects the changes and syncs them to the cluster

**Do not manually edit `image:` lines in deployment files** - they will be overwritten by automation.

## Manual Operations

### Sync Applications

```bash
# Sync all applications
argocd app sync --async johnson-frontend johnson-backend

# Sync specific application
argocd app sync johnson-frontend
```

### View Application Status

```bash
# List all applications
argocd app list

# Get application details
argocd app get johnson-frontend

# View sync history
argocd app history johnson-frontend
```

### Rollback

```bash
# Rollback to previous version
argocd app rollback johnson-frontend <history-id>

# View history to get history-id
argocd app history johnson-frontend
```

## Making Changes

### Updating Resources

1. Create a new branch
2. Edit the manifest files (deployment.yaml, etc.)
3. Test locally: `kubectl apply --dry-run=client -f <file>`
4. Commit and push
5. Create a pull request
6. After merge, ArgoCD will automatically sync the changes

### Adding New Services

1. Create a new directory (e.g., `johnson-api/`)
2. Add `deployment.yaml` and `kustomization.yaml`
3. Create ArgoCD application in `apps/<service-name>.yaml`
4. Add to `apps/kustomization.yaml`
5. Commit and push

## Troubleshooting

### Application Out of Sync

```bash
# Check diff
argocd app diff johnson-frontend

# Force sync
argocd app sync johnson-frontend --force
```

### Pods Not Starting

```bash
# Check pod status
kubectl get pods -n default

# View pod logs
kubectl logs <pod-name> -n default

# Describe pod for events
kubectl describe pod <pod-name> -n default
```

### Image Pull Errors

```bash
# Check if image exists in registry
docker pull <registry>/<image>:<tag>

# Verify image pull secrets
kubectl get secrets -n default
kubectl describe secret acr-secret -n default
```

## Security Notes

✅ **Secrets are NOT stored in git** - GitHub push protection prevents committing secrets, which is good!

### Current Approach
- ✅ Secrets are created manually in the cluster
- ✅ GitHub push protection prevents accidental commits
- ✅ Secrets never appear in git history
- ⚠️ Requires manual creation on each cluster

### Secret Management Options

#### 1. Manual Creation (Current)
- Create secrets with `kubectl create secret`
- See `johnson-backend/CREATE-SECRETS.md` for instructions
- Pros: Simple, secure
- Cons: Manual process for each cluster

#### 2. Sealed Secrets (Recommended for GitOps)
- Encrypts secrets so they can be stored in git
- ArgoCD decrypts automatically in cluster
- Pros: True GitOps, version controlled
- Cons: Requires Sealed Secrets controller

```bash
# Install and use Sealed Secrets
brew install kubeseal
kubectl create secret generic johnson-backend-secrets ... \
  --dry-run=client -o yaml | kubeseal -o yaml > sealed-secrets.yaml
git add sealed-secrets.yaml
```

#### 3. External Secrets Operator
- Syncs secrets from Azure Key Vault, AWS Secrets Manager, etc.
- Pros: Centralized secret management
- Cons: Requires external secret storage setup

### Best Practices
- ✅ Never commit plain text secrets to git
- ✅ Use different secrets for each environment
- ✅ Rotate secrets regularly
- ✅ Implement RBAC for secret access
- ✅ Use Sealed Secrets for proper GitOps workflow

## Related Documentation

- [Johnson Application Repository](https://github.com/eladhayun/johnson)
- [GitOps CI/CD Documentation](https://github.com/eladhayun/johnson/blob/main/docs/gitops-cicd.md)
- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)

