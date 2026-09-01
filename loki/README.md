# Loki Logging Stack

This directory contains the GitOps configuration for Loki and Grafana Alloy log aggregation.

## Current Architecture

- **Loki** runs as a single StatefulSet and provides ingestion and LogQL query APIs.
- **Grafana Alloy** runs as a DaemonSet, one pod per node, discovers local Kubernetes pod logs, parses CRI records, and sends them directly to Loki.
- **Storage** uses a 10Gi PVC for Loki's local working data and Azure Blob Storage for persisted log chunks.
- **Retention** is 30 days.
- **Grafana UI** was removed on 2026-09-01 because it was unused. Loki and Alloy do not depend on it.
- **External Loki ingress** is disabled. Use the Kubernetes API or a local port-forward to query logs.

The log path is:

```text
/var/log/pods on each node -> Alloy -> loki.loki.svc.cluster.local:3100 -> Azure Blob
```

Alloy excludes `kube-system`, `kube-public`, and `kube-node-lease`, matching the previous Promtail behavior. The retained Loki labels are `namespace`, `pod`, `container`, `node`, and `app`.

## GitOps Resources

- `config.alloy` defines Kubernetes discovery, relabeling, CRI parsing, and the Loki writer.
- `alloy-daemonset.yaml` deploys Alloy v1.18.1 with one pod per schedulable node.
- `serviceaccount.yaml` grants read-only pod discovery permissions.
- `statefulset.yaml`, `configmap.yaml`, and `service.yaml` run Loki.
- `secrets.yaml` contains the SOPS-encrypted Azure storage credentials.

Argo CD owns this directory through `apps/loki.yaml` with automated sync, prune, and self-heal enabled.

## Resource Requests

- Loki: `100m` CPU and `256Mi` memory.
- Alloy per node: `50m` CPU and `96Mi` memory.
- On three nodes, the logging stack requests `250m` CPU and `544Mi` memory in total.
- On two nodes, it requests `200m` CPU and `448Mi` memory in total.

## Querying Loki

Loki has no external ingress. Forward the internal service locally:

```bash
kubectl --context jshipster -n loki port-forward svc/loki 3100:3100
```

Then query with LogQL through Loki's HTTP API:

```bash
curl -G -s http://localhost:3100/loki/api/v1/query_range \
  --data-urlencode 'query={namespace="ids"}' \
  --data-urlencode 'since=1h' \
  --data-urlencode 'limit=100' | jq
```

## Operations

Check rollout and health:

```bash
kubectl --context jshipster -n loki get statefulset loki
kubectl --context jshipster -n loki get daemonset alloy
kubectl --context jshipster -n loki get pods -o wide
```

Inspect logs:

```bash
kubectl --context jshipster -n loki logs -l app=loki --tail=100
kubectl --context jshipster -n loki logs -l app=alloy --tail=100
```

Inspect an Alloy instance through its local UI and health endpoints:

```bash
kubectl --context jshipster -n loki get pods -l app=alloy
kubectl --context jshipster -n loki port-forward pod/<alloy-pod> 12345:12345
curl http://localhost:12345/-/ready
curl http://localhost:12345/-/healthy
```

Verify Loki readiness and label discovery through the Kubernetes API proxy:

```bash
kubectl --context jshipster get --raw \
  '/api/v1/namespaces/loki/services/http:loki:3100/proxy/ready'

kubectl --context jshipster get --raw \
  '/api/v1/namespaces/loki/services/http:loki:3100/proxy/loki/api/v1/labels'
```

## Configuration Validation

Use the same pinned Alloy release as the DaemonSet:

```bash
alloy fmt --test loki/config.alloy
alloy validate loki/config.alloy
kubectl kustomize loki
```

The SOPS generator requires the repository's KSOPS-enabled Kustomize environment for a full local render. Argo CD performs that render during sync.

## Migration Notes

Promtail 2.9.2 was replaced because Promtail reached end of life on 2026-03-02. The Alloy configuration was produced with Alloy's official Promtail converter and reviewed to preserve the previous discovery, labels, filters, CRI parsing, and Loki endpoint.

Alloy stores file positions under `/var/lib/alloy/data` in an `emptyDir`. Positions survive process restarts but not pod replacement, matching the previous Promtail pod-lifetime persistence behavior. A collector replacement can therefore replay a small amount of existing log data.

References:

- [Migrate from Promtail to Grafana Alloy](https://grafana.com/docs/alloy/latest/set-up/migrate/from-promtail/)
- [Loki HTTP API](https://grafana.com/docs/loki/latest/reference/loki-http-api/)
- [Grafana Alloy HTTP endpoints](https://grafana.com/docs/alloy/latest/reference/http/)
