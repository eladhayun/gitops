# GitOps Repository for Argo Rollouts Demo

This repository contains Kubernetes manifests managed using the GitOps methodology with Argo CD and Kustomize. It is organized for clarity and scalability, supporting multiple applications with Argo Rollouts.

## Repository Structure

```
gitops/
├── apps/                       # Argo CD Application manifests (one per app, plus kustomization)
│   ├── argo-rollouts-demo-fe.yaml
│   ├── argo-rollouts-demo-be.yaml
│   ├── apps.yaml
│   └── kustomization.yaml
├── argo-rollouts-demo-be/      # Backend app manifests and kustomization
│   ├── analysis-template.yaml
│   ├── kustomization.yaml
│   ├── rollout.yaml
│   └── service.yaml
├── argo-rollouts-demo-fe/      # Frontend app manifests and kustomization
│   ├── deployment.yaml
│   ├── ingress.yaml
│   ├── kustomization.yaml
│   └── service.yaml
├── .gitignore
├── README.md
└── .git
```

## Usage

1. **Install Argo CD in your cluster:**
   ```bash
   kubectl create namespace argocd
   kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
   ```

2. **Install Argo Rollouts in your cluster:**
   ```bash
   kubectl create namespace argo-rollouts
   kubectl apply -n argo-rollouts -f https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml
   ```
   For more details, see the [official Argo Rollouts installation guide](https://argo-rollouts.readthedocs.io/en/stable/getting-started/).

3. **Apply the Argo CD applications:**
   ```bash
   kubectl apply -f apps/
   ```
   This will create the Argo CD Application resources for each app defined in the `apps/` directory.

## Adding New Applications

1. Create a new directory at the root of `gitops/` for your application (e.g., `my-new-app/`).
2. Add your Kubernetes manifests and a `kustomization.yaml` in that directory.
3. Create a new Argo CD Application manifest in `apps/` (e.g., `my-new-app.yaml`).
4. Update `apps/kustomization.yaml` to include your new application manifest if needed.

## Best Practices

1. Use Kustomize for environment-specific or reusable configurations.
2. Store sensitive information in Sealed Secrets or an external secret manager.
3. Use semantic versioning for application versions.
4. Document all major changes in commit messages.

## Prerequisites

- Kubernetes cluster
- Argo CD installed
- Argo Rollouts installed
- `kubectl` configured with cluster access
- `kustomize` installed for local development

## Contributing

1. Create a feature branch
2. Make your changes
3. Test changes in a development environment
4. Submit a pull request

## License

MIT License

## Obtaining AZURE_CREDENTIALS for GitHub Actions

To set up the AZURE_CREDENTIALS for your GitHub Actions workflow, follow these steps:

1. Open your terminal and run the following command:

   ```bash
   az ad sp create-for-rbac --name "GitHubActions" --role contributor --scopes /subscriptions/$(az account show --query id -o tsv) --sdk-auth
   ```

2. This command will output a JSON object containing the credentials. It will look something like this:

   ```json
   {
     "clientId": "your-client-id",
     "clientSecret": "your-client-secret",
     "subscriptionId": "your-subscription-id",
     "tenantId": "your-tenant-id",
     "activeDirectoryEndpointUrl": "https://login.microsoftonline.com",
     "resourceManagerEndpointUrl": "https://management.azure.com/",
     "activeDirectoryGraphResourceId": "https://graph.windows.net/",
     "sqlManagementEndpointUrl": "https://management.core.windows.net:8443/",
     "galleryEndpointUrl": "https://gallery.azure.com/",
     "managementEndpointUrl": "https://management.core.windows.net/"
   }
   ```

3. Copy the entire JSON output and set it as a secret in your GitHub repository under the name `AZURE_CREDENTIALS`.
