# Network isolation

AKS uses the managed Azure CNI Cilium dataplane to enforce these Kubernetes
NetworkPolicies. The migration retains node-subnet IPAM, Service CIDR, public
ingress IP and Tailscale routes. Advanced Container Networking Services is not
required for these L3/L4 rules.

| Namespace | Inbound access | Outbound access |
| --- | --- | --- |
| `postgres` | TCP 5432 from named app pods, MCPs, WhatsApp workers/manager/migrations, backup jobs, summary jobs, maintenance jobs, bastion and the owner Tailscale connector | CoreDNS; maintenance connections to PostgreSQL |
| `argocd` | Cloudflared and owner connector to server 8080; named Argo components to repo-server, Redis and Dex | CoreDNS, explicit Argo dependencies, public HTTPS/Kubernetes API; Cloudflared TCP/UDP 7844 |
| `mashov-mcp`, `webtop-mcp`, `tivtaam-mcp` | Owner connector to API/MCP ports 8080/8081 | CoreDNS, PostgreSQL 5432, CyberGhost proxy 8888 and public HTTPS |
| `multi-whatsapp` | Owner connector to manager; manager to workers; health monitor to manager | CoreDNS, PostgreSQL, public HTTPS, manager/monitor Kubernetes API, Slack relay and worker dependencies |

Each namespace is isolated in both directions. Namespace and pod selectors are
combined in the same peer so an identically labelled pod in an unrelated namespace
does not get access. Tailscale allowances select only the `jshipster-aks` Connector,
not the operator or arbitrary pods in the `tailscale` namespace. Tailnet grants
and application authentication remain separate controls. Internet HTTPS is allowed
by port, not by domain; these policies primarily constrain lateral movement.

Argo's chart-provided policies are disabled with `global.networkPolicy.create:
false`. Otherwise its allow-anywhere server policy would defeat the replacement
rules because policies are additive. The replacement policies are managed by the
`argocd-network-policy` Application. Future Helm upgrades must retain this setting.

`shared-postgres-tls-reload` has an explicit pod label for its DB allowance. New
database consumers need an explicit peer in `shared-postgres/network-policy.yaml`.
Inactive applications do not automatically receive access when re-enabled.
Backup and business-summary CronJobs are included even when no pod is running.

CI runs `scripts/test-network-policy.py` to check allowed and denied pod pairs,
in addition to rendering and strict NetworkPolicy schema validation. This static
model cannot prove dataplane behavior. Verify with actual allowed/denied probes,
authenticated MCP calls, Argo hard refresh, a database connection, and private SSH
after network changes. Namespace administrators able to create pods with allowed
labels remain trusted; NetworkPolicy does not replace RBAC.

Run the disposable live probes with an explicit owner kubeconfig:

```sh
KUBECONFIG="$HOME/.kube/prod-aks-entra" python3 scripts/verify-network-isolation.py --run
```

The script requires Cilium enforcement and ready agents on every node. It tests
denied ingress from each node, allowed backup database access, and allowed/denied
egress from the three MCP deployments, then removes its diagnostic pods. Perform
authenticated service and owner-access checks separately to confirm target health.

## Migration and recovery

The managed Cilium migration reimages nodes with the node pool's surge settings.
Single-replica PostgreSQL, VPN, Tailscale and applications can briefly reconnect
while pods move and disks attach. Do not disable PDBs or force-delete database pods
to accelerate the migration. Node-subnet addresses and cluster Services are kept.

For an accidental policy denial, use the authenticated Kubernetes API to amend
the narrow rule and commit the correction through `main`. Kubernetes port-forward
is also a recovery path; its success does not prove NetworkPolicy reachability.
Do not remove the namespace default-deny rules as a permanent workaround.
Reverting from Cilium is not an ordinary policy rollback; troubleshoot the policy
or dataplane first rather than attempting to recreate the cluster.

References: [AKS migration](https://learn.microsoft.com/en-us/azure/aks/migrate-from-npm-to-cilium-network-policy),
[Cilium support and limitations](https://learn.microsoft.com/en-us/azure/aks/azure-cni-powered-by-cilium).
