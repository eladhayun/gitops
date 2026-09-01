# Shared PostgreSQL

This application runs the cluster's shared PostgreSQL 17 server in the dedicated
`postgres` namespace. PostgreSQL is provided by the pgvector image so databases
that require the `vector` extension can share the same server without sharing
roles, database ownership, or application credentials.

## Endpoint

`shared-postgres.postgres.svc.cluster.local:5432`

## Databases and owners

| Database | Login owner | pgvector |
|---|---|---|
| `anpr` | `anpr` | No |
| `blutag` | `blutag` | No |
| `dirtbike` | `dirtbike` | Yes |
| `hasadnaa` | `hasadnaa` | No |
| `ids_embeddings` | `ids_user` | Yes |
| `trainings` | `trainings` | No |

Application roles are non-superusers and can connect only to their own database.
The `anpr_backup` role retains `pg_read_all_data`; the `anpr_reporter` role is
limited to read access in the ANPR database.

## Storage and deletion protection

- One 16 GiB `ReadWriteOnce` PVC on the cluster's default Standard SSD class.
- StatefulSet PVC retention is explicitly `Retain` when the StatefulSet is
  deleted or scaled down.
- The namespace has the Argo CD `Prune=false` sync option so deleting the Argo
  application cannot cascade through namespace deletion to the PVC.
- There is intentionally no PDB for this single-replica database because it
  would prevent supported node drains without adding availability.

Do not delete the namespace, PVC, or managed disk as part of an application
cutover. Database removal requires a separate backup verification and explicit
approval.

## Pre-consolidation recovery points

The migration started on 2026-09-01 only after creating and validating the
following recovery layers:

1. Fresh PostgreSQL logical dumps in Azure Blob Storage under
   `pg-backups/pre-consolidation/20260901T052300Z/`.
2. `gzip -t`, PostgreSQL dump-footer, and SHA-256 verification performed by the
   in-cluster `pg-backup-verify-preconsolidation-20260901` Job.
3. Successful Azure incremental snapshots of every active source database disk:
   `pg-consolidation-20260901-{anpr,blutag,dirtbike,ids,trainings}`.

Verified logical backup hashes:

| Database | SHA-256 |
|---|---|
| `anpr` | `82378e470762b1641621bc3f6e57b7aa2a57d67e4513cc7655c4c9e4a9fec220` |
| `blutag` | `781e81f50a06789bf65701bf4e68c2322f09d90a74b51b5c9b1fa19861cd6a9d` |
| `dirtbike` | `09a75e1b4cadb27f81d022083252375d7f855b7086b6a3e2a88a1bb41aeb7b29` |
| `hasadnaa` | `5b03b637ba6fe6e706070b2ad78351fb3cc9e1a71a6a1eb15b3136f4cb352e5a` |
| `ids_embeddings` | `54b0bbfaefb1ea276b46e9dc7d69f1f74b1556d9c3aee1ddff09e0e6a18786cc` |
| `trainings` | `955edbbf67be09f644210784744be7eed7532b1dc981f802fe0932588f974a8c` |

The disabled Gen-RAG and Johnson applications are not part of this migration.
Their retained Kubernetes PVC objects reference Azure disks that were deleted on
2026-08-31, and no corresponding logical backups exist in the `pg-backups`
container. Do not treat those stale PVC objects as recoverable databases.

## Completed consolidation evidence

All six active databases were cut over on 2026-09-01. For each database, its
writers were stopped, a consistent custom-format dump was uploaded, the shared
target was replaced from that dump, and exact table row counts and sequence
states were compared before the writer was resumed.

Final recovery archives are stored in Azure Blob Storage under the following
content-addressed prefixes. Each dump has a matching `.sha256` sidecar; all 12
objects were independently listed as current, versioned, and server-encrypted.

| Database | Final prefix | SHA-256 | Bytes |
|---|---|---|---:|
| `trainings` | `consolidation/final/20260901T062148Z/` | `487468bf6647b78a1f78d4b9d60a1efd93c54ecdd526404f8fec62ce5803d96d` | 155,208 |
| `hasadnaa` | `consolidation/final/20260901T063112Z/` | `da0ee6e0d152c63c991e73f035a9c837380e3454b577047a657b41e2f5c51d1a` | 29,811 |
| `anpr` | `consolidation/final/20260901T063753Z/` | `bfcb672b4e0c70ebe10696ea61b051f2b518b0c3833a8fc8a7c3533a636e1620` | 868,211 |
| `blutag` | `consolidation/final/20260901T064502Z/` | `2dd7bd1c611e51682e107ff8dc8748fb7250e5e5a291af62ad3e377558905937` | 3,830,849 |
| `dirtbike` | `consolidation/final/20260901T065235Z/` | `21f863bcac8df0a153cea5683168aa6d6fbd546d87f752932909c464cc378511` | 321,174,369 |
| `ids_embeddings` | `consolidation/final/20260901T071004Z/` | `7e5241854551713c14eae2666616cf3f68d335de12ca72329ac1982ae6a94092` | 529,174,454 |

Post-cutover validation established:

- all databases have the intended owner, zero invalid indexes, and zero
  unvalidated constraints;
- Dirtbike and IDS use pgvector `0.8.6`; 3,777 Dirtbike vectors have 3,072
  dimensions and 64,086 IDS email vectors have 1,536 dimensions;
- the six application health endpoints returned HTTP 200 and all Argo CD
  applications were `Synced/Healthy`;
- all application and reporting consumers connect to the shared service, while
  every retained legacy server has zero client connections;
- the six `pg-backup-*-shared-20260901` Jobs completed against PostgreSQL 17 and
  uploaded validated, server-encrypted daily backups; and
- a manual `ids-init-embeddings-shared-20260901` run completed against shared
  PostgreSQL, finding 2,125 products and zero changed embeddings.

The shared PVC is 16 GiB and was 17% used after migration. Data checksums are
enabled, `max_connections` is 200, application roles are non-superusers, and a
cross-database CONNECT privilege audit returned zero violations.

## Legacy rollback state

The five legacy PostgreSQL StatefulSets and all of their PVCs remain running at
one replica with zero application clients. They are deliberately retained as
rollback state and must not be scaled down or deleted until the observation
period is complete and a separate change is approved. While they are retained,
their pods duplicate about 666 MiB of measured memory and can prevent the node
autoscaler from settling at the final two-node cost baseline.

## Migration sequence

1. Deploy this application and verify PostgreSQL, roles, databases, extensions,
   PVC binding, and readiness without changing any consumer.
2. Restore pre-cutover copies and compare schema fingerprints, exact table row
   counts, indexes, constraints, sequences, and representative queries.
3. Cut over one application database at a time. Stop writers, take a unique
   final logical dump, restore the final copy, update the SOPS-managed connection
   settings, then restart and verify that application before proceeding.
4. Update and manually test every PostgreSQL backup CronJob against this service.
5. Observe all applications and a full backup window before scaling legacy
   PostgreSQL StatefulSets to zero.
6. Keep every legacy StatefulSet definition and PVC intact as rollback state.

### Copy-only preload (completed)

The `shared-postgres-preload-*-20260901` Jobs took consistent custom-format dumps
from the six live source databases, validated each archive, uploaded it to
`pg-backups/consolidation/preload/20260901T054603Z/`, and only then restored it
into the empty shared target. Argo CD sync waves serialized the Jobs from the
smallest database to the largest so they did not compete for source I/O, target
I/O, or node memory.

Preload dumps used `--no-owner --no-acl`; restores ran as each database's
non-superuser owner in one transaction. These archives remain validation
copies—not cutover copies.

After final evidence was collected, the temporary SOPS migration credential
copy, migration ConfigMap, and completed preload/final Job manifests were
removed from the active Kustomization. Their immutable Azure archives and Git
history remain available; the shared database and legacy rollback resources are
not part of that cleanup.

## Rollback

Before a legacy server is scaled down, rollback is only a connection-secret
revert followed by an application restart. After a legacy server is scaled to
zero, first restore its StatefulSet replica to one through GitOps, wait for the
original PVC to attach and PostgreSQL to become ready, then revert the consumer's
connection settings. Never write to both copies during rollback; stop the
application first and choose one authoritative database.
