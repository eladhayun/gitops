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

### Copy-only preload

The temporary `shared-postgres-preload-*-20260901` Jobs take consistent custom-
format dumps from the six live source databases, validate each archive, upload
it to `pg-backups/consolidation/preload/20260901T054603Z/`, and only then restore
it into the empty shared target. Argo CD sync waves serialize the Jobs from the
smallest database to the largest so they do not compete for source I/O, target
I/O, or node memory.

Preload dumps use `--no-owner --no-acl`; restores run as each database's
non-superuser owner in one transaction. Every restore refuses to run if the
target already contains user relations, and it fails on any restore error or
invalid index. The source databases remain authoritative and writable during
this preload, so these copies are validation candidates only—not cutover copies.

`migration-secrets.yaml` is a temporary SOPS-encrypted copy of the active source
backup and Azure credentials. Remove it, the migration ConfigMap, and completed
preload Jobs from Git after the preload evidence has been collected. Final
cutover dumps use a separate immutable prefix and are taken only after stopping
the corresponding writers.

## Rollback

Before a legacy server is scaled down, rollback is only a connection-secret
revert followed by an application restart. After a legacy server is scaled to
zero, first restore its StatefulSet replica to one through GitOps, wait for the
original PVC to attach and PostgreSQL to become ready, then revert the consumer's
connection settings. Never write to both copies during rollback; stop the
application first and choose one authoritative database.
