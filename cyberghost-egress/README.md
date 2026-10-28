# CyberGhost Israel egress

Shared, authenticated HTTP/HTTPS forward proxy for workloads that need an Israeli
internet exit. Gluetun connects to CyberGhost using OpenVPN, with country selection
fixed to Israel. The service is private ClusterIP; it does not change node routes,
other pods, the CNI, or the cluster's default egress. It supports proxy-aware clients;
it is not a transparent gateway for arbitrary UDP or applications without proxy support.

## Endpoint and access

`cyberghost-egress.cyberghost-egress.svc.cluster.local:8888`

Consumers use standard HTTP_PROXY/HTTPS_PROXY variables or an explicit HTTP CONNECT
proxy configuration. The proxy requires a dedicated cluster username/password,
separate from CyberGhost's OpenVPN credentials. Never distribute the VPN private key
or OpenVPN password to consumer workloads. Do not put proxy credentials into tracked
URLs, manifests, command arguments, logs, or chat.

This AKS cluster currently reports `networkPolicy: none`. NetworkPolicy resources
are therefore not an access-control mechanism here. Proxy authentication is required,
and there is no public ingress, LoadBalancer, NodePort, or remote control endpoint.

For a consumer namespace, create a SOPS-encrypted Kubernetes Secret containing
HTTP_PROXY and HTTPS_PROXY with the authenticated internal proxy URL. Supply it via
secretKeyRef/envFrom. Secrets cannot be referenced across namespaces; provision the
consumer's Secret through that application's GitOps resources. Exclude localhost,
127.0.0.1, .svc, .svc.cluster.local, 10.0.0.0/16, 10.1.0.0/16 and Azure metadata from
proxying using NO_PROXY. PostgreSQL connections are independent of HTTP proxy settings.
Go's default HTTP transport supports these proxy variables, including webtop-mcp.

## Credential preparation

Use CyberGhost's account portal → VPN → Configure Device → OpenVPN → Israel.
Download and extract the configuration bundle into an owner-only local folder.
Save its generated manual OpenVPN username in username.txt and password in
password.txt there (or put username then password as two lines in password.txt). These are not necessarily the regular CyberGhost app login.
Keep client.crt and client.key from the export; ca.crt is also checked when supplied.
Do not obtain secrets from the native app's private storage or Keychain.

Example private folder on this Mac:
`/Users/elad/Development/jshipster/webtop-mcp/private/cyberghost`

Run this app's `scripts/encrypt-secrets.py --credentials-dir <private-folder>`.
It checks certificate expiry, validates the certificate/private-key pair, generates
an owner-only random proxy password, encrypts the Secret using the platform age
recipient, and verifies decryption without printing values. No plaintext Secret is
written to GitOps. Keep the local folder private and untracked. A rotation requires
an explicit --replace invocation and synchronized consumer proxy Secret updates.

Gluetun's built-in CyberGhost provider reads the certificate/key from Secret files.
It supplies the provider CA and selects only Israeli servers; the downloaded .ovpn
is retained privately for reference, not executed as an arbitrary startup script.
The pinned v3.41.3 server catalog contains two Israeli entries. There is no country
fallback. Verify the live exit country after connection; provider location and IP
geolocation databases may differ.

## Runtime and failure behavior

One replica, Recreate rollout: request 100m CPU/128Mi; limit 1 CPU/256Mi.
Updates and VPN reconnection can briefly interrupt consumers. VPN health gates
readiness. Gluetun's built-in firewall stays enabled when the tunnel is down, and
its internal health monitor retries the VPN. There is no direct-egress fallback
in the proxy. Verify this behavior at runtime before enrolling consumers.

Gluetun requires root plus NET_ADMIN and MKNOD inside its own pod network namespace
to configure OpenVPN, firewall and TUN. It is not privileged, uses no host namespaces,
hostPath mounts or service-account token, and drops other capabilities. Root UID
avoids modifying the image's /etc/passwd or adding CHOWN/SETUID capabilities.
The root filesystem is read-only, with bounded temporary mounts for OpenVPN
credentials/configuration and runtime state. Secret files are read-only, mode 0400.
Only the current AKS subnet 10.1.1.0/24 is exempted for replies to internal proxy
clients. Public destinations must traverse the VPN. Review this range if AKS subnets
change. Request/tunnel logging and the remote control listener are disabled/excluded.

## Activation and verification

Do not register the ArgoCD application until real secrets.yaml exists and its
round-trip encryption check passes. Copy application.yaml.example to
apps/cyberghost-egress.yaml and add that file to apps/kustomization.yaml only when
ready. Publish through GitOps; do not deploy with imperative kubectl apply.

Verify Synced/Healthy, VPN readiness, authenticated proxy success from another pod,
407 for missing/wrong proxy credentials, an Israeli exit country, and Webtop returning
401 anonymously or successful owner-authorized data. Test tunnel interruption before
consumer enrollment and confirm the proxy cannot fall back to the normal AKS egress.
Do not log public IPs, usernames, keys, passwords, or school response bodies.

Pinned upstream image: Gluetun v3.41.3, OCI digest in deployment.yaml. Review upgrades
and credential expiry explicitly. An account subscription permits only a bounded
number of simultaneous CyberGhost connections; this deployment uses one connection.

Sources:
- https://github.com/qdm12/gluetun-wiki/blob/main/setup/providers/cyberghost.md
- https://github.com/qdm12/gluetun-wiki/blob/main/setup/options/http-proxy.md
- https://github.com/qdm12/gluetun-wiki/blob/main/setup/options/firewall.md
- https://github.com/qdm12/gluetun-wiki/blob/main/faq/healthcheck.md
- https://support.cyberghostvpn.com/hc/en-us/articles/213190009-How-to-Set-Up-OpenVPN-on-Linux-Debian-via-Terminal
