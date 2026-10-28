# Tailscale access to AKS

The `tailscale` Argo CD app installs the official operator chart pinned to
**1.104.2**, plus one `jshipster-aks` Connector advertising **10.0.0.0/16**.
The operator joins as `jshipster-aks-operator`; the router hostname starts with
`jshipster-aks`. Existing ClusterIP Services do not need changes. No exit node,
pod/node subnet routes, public load balancer, or API-server proxy is enabled.
The operator itself also appears as a device; services do not become devices.

## Initial state and activation

The app is registered in the app-of-apps but **automatic sync is disabled** until
real encrypted credentials are committed. Do not manually sync it before setup.
The local Kustomization initially omits the credential generator, so it can render
without credentials. The helper below enables that generator only after encryption.

1. In Tailscale [Access controls](https://login.tailscale.com/admin/acls), merge
   these entries into your existing `tagOwners` (preserve existing entries):

   ```json
   "tagOwners": {
     "tag:k8s-operator": [],
     "tag:k8s": ["tag:k8s-operator"]
   }
   ```

2. In [Trust credentials](https://login.tailscale.com/admin/settings/oauth),
   create an OAuth client with **write** access to **General / Services**,
   **Devices / Core**, and **Keys / Auth Keys**, restricted to
   `tag:k8s-operator`. Save its ID and secret locally; do not paste them into chat,
   command-line arguments, Helm values, or Git. See the
   [official installation instructions](https://tailscale.com/docs/kubernetes-operator/install-operator).

3. From the repository root, run:

   ```sh
   python3 tailscale/configure-credentials.py
   ```

   Both prompts hide input. The helper passes plaintext directly to SOPS in memory
   and writes only encrypted `tailscale/secrets.yaml`, using `.sops.yaml` and its
   age recipient. It also enables `secrets-generator.yaml` in the Kustomization.
   The generated Secret is `tailscale/operator-oauth`, with `client_id` and
   `client_secret`, matching the chart's existing-Secret interface. Never set the
   chart's `oauth.clientId` or `oauth.clientSecret` values. For later rotation use
   `SOPS_AGE_KEY_FILE="$PWD/keys.txt" sops tailscale/secrets.yaml`.

4. Change `spec.syncPolicy.automated.enabled` to `true` in `apps/tailscale.yaml`.
   Commit the encrypted Secret, updated Kustomization, and app activation together;
   push through the normal GitOps workflow. Do not commit plaintext or dummy keys.

The Secret uses sync wave -1; chart resources, including CRDs and the operator,
use wave 0; the Connector uses wave 1. Argo CD waits for earlier waves before
creating the Connector. The app uses server-side apply for the CRDs, retries,
automatic pruning and self-healing. The namespace must allow the operator-managed
router's networking capabilities; do not apply the restricted Pod Security profile
used by `padel-booking` to the `tailscale` namespace.

## Tailnet route and access policy

In [Machines](https://login.tailscale.com/admin/machines), locate the router and
approve **10.0.0.0/16** under its subnet routes. Route approval and access grants
are separate requirements. Merge a grant like this into the existing policy,
replacing the source with the owner's real Tailscale login:

```json
"grants": [
  {
    "src": ["OWNER_TAILSCALE_LOGIN"],
    "dst": ["10.0.0.0/16"],
    "ip": ["*"]
  }
]
```

This intentionally permits the owner to reach all ports in the Service CIDR,
including DNS over TCP/UDP 53. Audit existing broad grants/ACLs: adding this rule
does not remove access already granted to other users. Add policy tests for the
owner's permitted access and another user's denied access before saving.
Do not grant the whole tailnet access unless intended. Subnet routing does not
bypass application authentication. Kubernetes network policies still apply where
enforced; inspection on 2026-10-28 showed AKS `networkPolicy: none`, so the existing
NetworkPolicy objects must not be treated as an enforced access boundary.

## Split DNS and clients

In [DNS](https://login.tailscale.com/admin/dns), add **10.0.255.53** as a custom
nameserver and enable **Restrict to domain / Split DNS**, using **cluster.local**.
This address belongs to the additional `kube-system/tailscale-cluster-dns` Service,
which selects the existing CoreDNS pods. It avoids the owner’s local
`10.0.0.0/24` network; the original cluster DNS Service remains unchanged.
Do not add it as an unrestricted global resolver. Enable Tailscale DNS on clients.
This tailnet setting is configured in Tailscale, not by the GitOps manifests.

Use fully qualified names, for example:
`shared-postgres.postgres.svc.cluster.local`. Short in-pod names such as
`shared-postgres` do not automatically gain Kubernetes search domains. Headless
Services return Pod IPs and are outside this Service-CIDR-only setup.

Linux clients must accept subnet routes:

```sh
tailscale set --accept-routes=true --accept-dns=true
```

macOS and Windows normally accept subnet routes automatically; ensure Tailscale
DNS is enabled in their settings. Check for conflicting local/VPN routes before
using the cluster subnet. On macOS inspect `route -n get 10.0.22.210`; on Linux
inspect `ip route get 10.0.22.210` and `ip rule`. Another cluster advertising the
same CIDR also needs a separate overlap design; do not advertise additional ranges
to work around an overlap.

## Validation

Use the project kubeconfig and context for every cluster command:

```sh
export KUBECONFIG=/Users/elad/Development/jshipster/.kube/config
kubectl --context jshipster -n argocd get application tailscale
kubectl --context jshipster -n tailscale rollout status deployment/operator --timeout=180s
kubectl --context jshipster get connector jshipster-aks -o yaml
kubectl --context jshipster -n tailscale get pods
```

Confirm the app is Synced/Healthy, the Connector is ready and advertises only
`10.0.0.0/16`, and the router is online with its route approved in Machines.
From the owner's connected Tailscale client:

```sh
# Direct DNS queries exercise UDP and TCP through the router.
dig @10.0.255.53 shared-postgres.postgres.svc.cluster.local A
dig +tcp @10.0.255.53 shared-postgres.postgres.svc.cluster.local A
# Exercise the system resolver (macOS) to verify split DNS.
dscacheutil -q host -a name shared-postgres.postgres.svc.cluster.local
# HTTP service and read-only TCP connection; these do not write application data.
curl --connect-timeout 10 --max-time 20 -I http://10.0.43.134/
nc -vz -w 5 10.0.22.210 5432
nc -vz -w 5 shared-postgres.postgres.svc.cluster.local 5432
```

On Linux use `getent hosts shared-postgres.postgres.svc.cluster.local` for the
system-resolver check. On macOS a plain `dig` does not reliably exercise scoped
system DNS. HTTP status depends on the application; an HTTP response still proves
connectivity. Example IPs were observed on 2026-10-28; rediscover them with
`kubectl --context jshipster get svc -A` if a Service is recreated.
Verify an ungranted tailnet identity cannot reach the same service.

One replica means a router restart can briefly interrupt connections. To disable
access, revoke the tailnet grant/route first; disabling automatic sync alone does
not stop the running router. Do not delete shared operator CRDs while other
Tailscale resources depend on them.

References: [Subnet routers](https://tailscale.com/docs/kubernetes-operator/connector/deploy-subnet-router),
[DNS](https://tailscale.com/docs/reference/dns).
