# GitOps Repository with App of Apps Pattern

This repository contains Kubernetes manifests managed using the GitOps methodology with Argo CD and Kustomize. It follows the App of Apps pattern for better scalability and management of multiple applications.

## Repository Structure

```
├── apps/                     # Directory containing all application manifests
│   ├── app-of-apps/         # Root application that manages other Argo CD applications
│   └── templates/           # Application templates and shared resources
├── clusters/                # Cluster-specific configurations
│   ├── development/        # Development cluster configurations
│   ├── staging/           # Staging cluster configurations
│   └── production/        # Production cluster configurations
└── base/                   # Base configurations shared across all environments
```

## Usage

1. Install Argo CD in your cluster:
```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

2. Apply the root application:
```bash
kubectl apply -f apps/app-of-apps/application.yaml
```

## Adding New Applications

1. Create a new application directory under `apps/`
2. Define your base Kubernetes manifests
3. Create environment-specific overlays using Kustomize
4. Add the application to `apps/app-of-apps/applications` directory

## Best Practices

1. Always use Kustomize for environment-specific configurations
2. Keep sensitive information in Sealed Secrets or external secret management solutions
3. Use semantic versioning for application versions
4. Document all major changes in commit messages

## Prerequisites

- Kubernetes cluster
- Argo CD installed
- `kubectl` configured with cluster access
- `kustomize` installed for local development

## Contributing

1. Create a feature branch
2. Make your changes
3. Test changes in development environment
4. Submit a pull request

## License

MIT License # gitops
