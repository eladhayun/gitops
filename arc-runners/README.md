# GitHub Actions Runner Controller

ArgoCD owns `apps/arc-controller.yaml` (ARC 0.15.1 in `arc-systems`) and
`apps/arc-runners.yaml` (the namespace, encrypted credential, quota, and
ApplicationSet). The ApplicationSet creates a repository-scoped runner scale
set for every entry in its list generator. `repositories.json` records the
2026-10-30 GitHub inventory: 18 non-archived workspace repositories with active
workflows. Repositories with no workflows (`gitops`, `terraform`, `synology-nas`,
`3d-models`) have no scale set.

## Capacity and ownership

Terraform's `../terraform/arc.tf` owns a dedicated `arc` AKS User pool:
`Standard_D4as_v5`, minimum zero, maximum one node. It is labeled
`workload=github-actions` and tainted `workload=github-actions:NoSchedule`.
Runner pods require that label and tolerate that taint. The controller and
listeners can run on the existing system pool. Adding a pool does not change
the existing default pool. Azure bills build-node capacity while running;
autoscaler scale-down is not immediate after the final job.

Each repository has zero idle runners and at most one active runner. The
PriorityClass-scoped ResourceQuota admits at most two build pods across all
repositories, excluding listeners and the controller. Excess pods retry on
quota admission; there is no guarantee of fairness between repositories.
Each build pod requests 1.5 CPU and 3 GiB RAM and has a combined 6 GiB memory
limit. The non-preempting `arc-build` class cannot evict application pods.

Docker-in-Docker runs as a native sidecar, requires privileged mode, and uses
an ephemeral Docker data directory. Runner and Docker images are pinned by
digest in `values.yaml`. Kubernetes API credentials are not mounted in runner
pods. A dedicated node pool is workload separation, not a security boundary
against hostile privileged jobs: only trusted jobs should run here.

## Credentials

`secrets.yaml` is SOPS-encrypted with the repository's age recipient. KSOPS
creates `arc-github-auth` in `arc-runners`; only its name is in Helm values.
The `jshipster-arc` fine-grained PAT grants Administration read/write and
Metadata read-only to the 18 selected repositories. It expires **2027-01-28**.
Rotate before that date through GitHub, then update the encrypted Secret with
`make sops-edit FILE=arc-runners/secrets.yaml`. Do not print or commit decrypted
render output. Obtain explicit approval before publishing a production secret.

Adding a repository requires both adding a list-generator element in
`applicationset.yaml` and including that repository in the token's scope.
Keep `repositories.json` aligned with the inventory. No GitHub organization is
required. The runtime credential does not have Contents or Workflows access.

## Workflow adoption

Use `runs-on: jshipster-<name>` where `<name>` is the list-generator `name`.
For example, `eladhayun/ANPR-Shikmim` uses `jshipster-anpr-shikmim`,
`eladhayun/FindMy.py` uses `jshipster-findmy-py`, and
`eladhayun/slack-notifications` uses `jshipster-slack-notifications`.

Registration does not migrate workflows. Existing workflows remain on their
current runners until smoke tests and dependency checks pass. The upstream
runner image is not the full GitHub-hosted Ubuntu image: workflows must install
needed compilers, make, PostgreSQL, browsers, and other build tools or use a
maintained custom runner image. macOS and Windows jobs must retain their
matching platforms. Public repositories must keep untrusted pull requests on
GitHub-hosted runners; do not route arbitrary contributor code into this cluster.

## Validation and deployment

1. Validate the Terraform plan and apply only the reviewed ARC pool addition.
2. Run `make kustomize-check SERVICE=arc-runners`, `kustomize build apps`, and
   Helm-render both pinned charts. Use a private temporary file for KSOPS output.
3. After approval to publish the secret, commit and push the GitOps changes.
4. Verify the controller rollout, all 18 generated Applications, and all 18
   listeners. Confirm GitHub runner scale-set registration independently of
   ArgoCD health.
5. Run a manually dispatched smoke job on one scale set: checkout, shell
   command, `docker info`, and an ephemeral container. Verify the pool scales
   up, the pod lands on it, the job completes, and the runner is removed.
6. Verify scale-down separately after the autoscaler delay. Only then adopt
   application workflows with their required tools.

ArgoCD ApplicationSet deletion preserves generated resources. Remove a scale
set deliberately only after its jobs drain; do not delete ARC CRDs as routine
cleanup or during upgrades.

Sources: [GitHub deployment guide](https://docs.github.com/en/actions/how-tos/manage-runners/use-actions-runner-controller/deploy-runner-scale-sets)
and [GitHub authentication guide](https://docs.github.com/en/actions/how-tos/manage-runners/use-actions-runner-controller/authenticate-to-the-api).
