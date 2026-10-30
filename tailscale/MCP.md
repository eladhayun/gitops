# Owner MCP connections

Codex uses private Streamable HTTP through the Tailscale Service-CIDR router and
`cluster.local` split DNS described in [README.md](README.md).

| Codex name | URL |
| --- | --- |
| anpr | http://anpr-cloud.anpr.svc.cluster.local/mcp |
| tivtaam | http://tivtaam-mcp.tivtaam-mcp.svc.cluster.local:8081/mcp |
| mashov | http://mashov-mcp.mashov-mcp.svc.cluster.local:8081/mcp |
| webtop | http://webtop-mcp.webtop-mcp.svc.cluster.local:8081/mcp |
| multi-whatsapp | http://multi-whatsapp-manager.multi-whatsapp.svc.cluster.local:8080/mcp |

Run `python3 scripts/configure-mcps.py` from the GitOps checkout to install these
entries in the current owner's `~/.codex/config.toml`. It validates TOML, preserves
unrelated configuration and tool restrictions, and creates a mode-0600 backup.
Use `--server NAME` to update one entry (`--server tivtaam` for TivTaam).
Installing TivTaam migrates a legacy `tivtaam-mcp` entry to `tivtaam`; conflicting
duplicate entries are rejected for review. Reload Codex afterward.

Every entry uses `scripts/mcp-headers.py NAME`, a 30-second startup timeout and a
90-second tool timeout. The helper reads a mode-0600 owner-owned token file from
the sibling service checkout and emits headers only to Codex. Its stdout contains
credentials: never run it into terminal output. Tokens are not committed. ANPR's
file is `ANPR-Shikmim/data/private/mcp-auth-token`; the other services use their
`private/auth-token` files. Provision matching service credentials securely before
connecting another host; this installer does not copy credentials between hosts.

WhatsApp's complete owner MCP uses a separate SOPS-encrypted
`multi-whatsapp-mcp` Secret, mounted only in the manager. The former `/mcp/padel` endpoint is removed; owner and worker credentials remain separate. The obsolete stdio adapter and supervised Mac proxy/tunnels are retired. Primary
client entries need neither kubectl exec nor an Azure login. Manual loopback
port-forwards remain available for diagnostics and local development. Public/provider MCPs and local process tools retain their native transports.

Tailscale encrypts traffic to the cluster router; HTTP between that router and
ClusterIP services is not application TLS. Preserve application bearer auth and
restrict tailnet access. Do not expose these ports through public ingress.
