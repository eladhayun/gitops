# jshipster GitOps

Kubernetes manifests for the `jshipster` Azure AKS cluster. Argo CD reconciles
`main` from this repository. Always select `--context jshipster`; set
`KUBECONFIG` explicitly when using a non-default credential file.

## Layout and ownership

- `apps/kustomization.yaml` is the authoritative list of active applications.
- `apps/apps.yaml` bootstraps the Argo CD app-of-apps.
- Service directories contain Kustomize resources and KSOPS secret generators.
- `multi-whatsapp/worker-chart` supplies dynamically generated account workloads.
- `argocd-ksops-values.yaml` configures the Helm-managed Argo CD installation.
  Argo CD does not manage its own installation; edit these values and run
  `make argocd-upgrade` to deploy them.
- Commented-out applications and unreferenced manifests are retained recovery
  scaffolding, not proof that a workload is running. Check Kustomize references.

Application CI owns application image tags. Do not manually change those tags.
Infrastructure versions are pinned in their Kustomizations or Helm values.

## Secrets

Secrets are encrypted with SOPS and age, and decrypted by KSOPS in Argo CD's
repo-server. The local `keys.txt` is ignored by Git; never commit or print it.
Use `make sops-edit FILE=<service>/secrets.yaml` for secret changes. Do not commit
rendered manifests containing decrypted Secrets.

## Databases and backups

The active application databases share PostgreSQL in the `postgres` namespace.
Several legacy `*-postgres` Argo applications retain connection Secrets and do
not deploy database servers. See `shared-postgres/README.md` before changing
ownership or removing any database resources. Recovery artifacts and PVCs must
not be deleted as routine cleanup.

`pg-backups` manages scheduled backups. Successful Job status is necessary but
is not a substitute for verifying uploaded archives and testing restores.

## Validation and deployment

1. Review `git diff` and render changed Kustomizations. KSOPS-based directories
   require the configured plugin and age key; keep decrypted output private.
2. Use server-side dry runs for changed resources. Existing Job pod templates
   are immutable; admission Jobs use Argo hooks with recreation policies.
3. Push reviewed changes to `main`, then check Argo sync, health, rollout status,
   restart counts, warning events, and the affected service endpoints.
4. For Helm-managed Argo CD, run `make argocd-upgrade` separately. It pins chart
   9.5.11 and application v3.3.17, retaining existing release overrides and KSOPS.

```sh
kubectl --context jshipster get applications -n argocd
kubectl --context jshipster get pods -A
kubectl --context jshipster top nodes
kubectl --context jshipster get events -A --field-selector=type=Warning
```

## Infrastructure maintenance

Ingress NGINX is pinned to its final patched v1.15.1 release. This addresses the
known vulnerabilities in the previous v1.11.1 deployment, but the upstream
project is retired. Migration to a maintained controller remains necessary;
preserve HTTP/HTTPS routes, certificate integration, forwarded-header handling,
and the SSH TCP mapping when doing so.

Argo CD v3.3.17 contains the upstream nil-list guard for the controller pager
panic observed on v3.2.0. Resource requests and limits for Argo CD and Tailscale
are version-controlled. Tailscale Connector resources select the explicit
`jshipster-resources` ProxyClass.

AKS version upgrades and node-pool capacity changes require authenticated Azure
management-plane access and belong in the infrastructure repository. Kubernetes
API access alone does not verify AKS LTS enrollment or Azure billing resources.
