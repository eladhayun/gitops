# Public ingress: Traefik

Traefik v3.7.16 is pinned by digest and managed by Argo CD through this directory.
The maintained Kubernetes Ingress NGINX compatibility provider handles the
existing `nginx` IngressClass and annotations. No NGINX controller binary or
admission webhook is needed. Application-owned Ingress resources and
cert-manager's HTTP-01 solver configuration retain their existing class.

## Stable public endpoint

The Argo Application is still named `nginx-ingress-controller` to preserve
resource ownership. The namespace and LoadBalancer Service retain the names
`ingress-nginx` and `ingress-nginx-controller`. These are compatibility names,
not the running controller implementation. **Do not delete or recreate the
Service or namespace during upgrades:** that could release the public IP and
break DNS and SSH.

The Service preserves `externalTrafficPolicy: Local`, its existing Azure public
IP, and ports 80, 443, and 22. Named target ports send HTTP/HTTPS to Traefik's
unprivileged ports 8080/8443 and SSH to 2222. The TCP router in `routes.yaml`
forwards SSH directly to `jshipster-bastion.default.svc.cluster.local:22` without
TLS interception or PROXY protocol. `debug.jshipster.io` remains managed from
the Service's ExternalDNS annotation.

## Routing and security

- Existing Ingress resources own hostnames, paths, TLS Secret references,
  redirect behavior, upload limits, and upstream timeouts.
- The compatibility provider preserves per-Ingress NGINX annotations, including
  streaming settings. Only that provider is enabled for Kubernetes Ingress;
  enabling the native provider too would create duplicate routers.
- Request buffering is enabled, with a default 1 MiB body limit and existing
  per-Ingress overrides. Response buffering is not enabled globally.
- Forwarded headers are trusted only from Cloudflare's published IPv4/IPv6
  ranges, verified on 2026-10-29. Update both entrypoints when those ranges change.
- Header names containing alias characters such as underscores or dots are
  removed before routing. Snippet annotations, cross-namespace annotation
  references, and ExternalName services are disabled.
- TLS has a minimum version of 1.2; HTTPS responses retain HSTS. Certificate
  issuance and renewal remain owned by cert-manager.
- The dashboard/API is not enabled. Port 8082 serves the internal readiness
  endpoint and is not exposed by the public Service.

## Availability and resource budget

Two replicas require distinct nodes. Each requests 100m CPU and 64Mi memory,
with a 256Mi memory limit and 192MiB Go memory target. The disruption budget
keeps one replica available. Rolling updates use one unavailable replica and
no surge, so a two-node cluster can update without adding a node to satisfy
anti-affinity. The controller accepts traffic for five seconds after termination
starts and allows 60 seconds for connections to drain; longer-lived sessions
must reconnect when their serving pod exits.

Kustomize generates hashed ConfigMaps. Static or dynamic configuration changes
therefore roll the pods. Dynamic file watching is disabled because the entire
configuration is deployed as a versioned ConfigMap.

## Validation and recovery

Before switching traffic, test every hostname directly against the candidate
controller with the original Host header and TLS SNI, then test public URLs.
Compare redirects, certificate validation, and the SSH host key. Exercise
WebSockets, SSE, upload limits, forwarded-header handling, and an HTTP-01 solver
path using a temporary test backend. Remove the backend after validation.

Keep the previous controller available until candidate checks pass and the
Service selector cutover is verified. For emergency rollback, restore the
previous controller manifests from Git while keeping the Service on Traefik;
wait for readiness before changing the selector and SSH target port back. Never
roll back by deleting the LoadBalancer Service. Retired NGINX is only an emergency
migration rollback, not a supported long-term configuration.

References:

- [Traefik's supported migration path](https://doc.traefik.io/traefik/migrate/nginx-to-traefik/)
- [Ingress annotation compatibility](https://doc.traefik.io/traefik/reference/routing-configuration/kubernetes/ingress-nginx/)
- [Cloudflare IP ranges](https://www.cloudflare.com/ips/)

## Migration verification (2026-10-29)

Both candidate replicas passed checks before cutover. After the Service
selected only Traefik and NGINX was pruned, all 10 production hostnames passed
27 HTTP/HTTPS checks against the original baseline, including redirects and
origin certificate validation. The SSH ED25519 host key matched before and
after cutover. A temporary backend verified WebSocket upgrade and data,
unbuffered SSE, accepted/rejected upload sizes, legacy-class HTTP-01 routing,
and rejection of spoofed forwarded/alias headers through the public IP.
The temporary backend was removed after validation. These are routing and
protocol checks, not authenticated application workflows or an authenticated
SSH session.
