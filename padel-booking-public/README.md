# Public OAuth Information Pages

This separate, static-only ArgoCD application publishes:

- `https://jshipster.io/wednesday-club/`
- `https://jshipster.io/wednesday-club/privacy.html`
- `https://jshipster.io/wednesday-club/terms.html`

Use these exact links in Google Auth Platform Branding. The owner must complete
Audience publishing and OAuth consent; hosting these pages grants no Google access
and does not enable Calendar delivery or purchasing.

The public deployment has no booking API routes, database connectivity, secrets,
service-account token or outbound network access. Only the ingress namespace can
reach its HTTP port. It uses a digest-pinned upstream stable unprivileged NGINX
image, read-only root filesystem and ConfigMap-generated content. Page changes
change the ConfigMap hash and roll the public pod, not the booking pod.

Copy this directory to `wednesday-club-public` in the GitOps repo and register
`deploy/gitops/apps/wednesday-club-public.yaml` in its app-of-apps list. ArgoCD,
external-dns and the existing Let's Encrypt issuer manage deployment, DNS and TLS.
Do not apply an ingress or service to the private booking application.

Validate with `kubectl kustomize deploy/gitops/wednesday-club-public`, HTML/link
checks, HTTPS checks for all three pages and responsive browser layout checks.
The pages contain only public information and the owner's approved contact email.
