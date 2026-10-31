# Automatic deployment validation

Service CI and the WhatsApp manager continue writing to `main`. Argo CD reads
`production`, including the root Application and WhatsApp ApplicationSet generator.
The GitOps validation workflow validates each intake commit and fast-forwards
`production` only when the commit passes and is still the head of `main`.
There is no required human approval or pull request for service promotions.

`production` requires the `gitops-validation` check from GitHub Actions, including
for administrators. Force pushes and branch deletion are disabled. `main` also
rejects force pushes and deletion, but accepts existing CI writers. Repository
writers remain trusted: they can change manifests and workflow code. This gate
prevents unchecked deployment and common configuration errors; it does not turn
arbitrary write access into an untrusted privilege.

Validation uses read-only repository permissions and no production credentials:

- Parse tracked YAML and reject committed private age/OpenSSH keys.
- Require every GitOps Application and account generator to read `production`.
- Check KSOPS payload encryption and integrity-metadata presence without decrypting.
- Build active Kustomize directories in a disposable tracked-files-only copy,
  with KSOPS generators removed; executable plugins are never enabled.
- Strictly validate standard Kubernetes resources with Kubernetes 1.35 schemas.
  Known custom resource kinds receive structural checks, not full CRD validation.
- Lint the worker Helm chart and render each configured WhatsApp account.
- Exercise negative tests for plaintext Secrets, invalid resource fields, unknown
  kinds, and accidental references to `main`.

Secret decryption/MAC verification stays in Argo CD; an encrypted payload can pass
CI yet fail decryption. Run `make kustomize-check SERVICE=<directory>` locally
when changing encrypted secrets. CI does not prove application runtime behavior.

Tool downloads and Actions are pinned, binary downloads are checksum-verified.
The promotion job has write access but only advances a validated SHA; it does not
execute repository scripts. Concurrent intake commits are handled by skipping
stale runs and validating the newer head. Failed validation leaves production
unchanged. Correct the problem on `main` and push again; do not bypass protection.

For a rollback, revert the relevant change on `main`; the revert follows the same
validation path. Existing service CI success means the image update reached intake;
deployment follows the separate GitOps validation/promotion run and Argo sync.

Local checks (Python with PyYAML 6.0.3, Kustomize 5.8.3, kubeconform 0.8.0,
Helm 4.3.1):

```sh
python3 scripts/test-validate-gitops.py
python3 scripts/validate-gitops.py
```
