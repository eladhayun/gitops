# Optional TLS for the existing shared PostgreSQL

Promote these changed/new files into the existing GitOps `shared-postgres` directory;
retain its namespace, Service and existing encrypted Secret unchanged.
This staged directory is a reviewed change set, not a standalone new database.

The existing PostgreSQL image, connection/performance arguments, environment,
resources, probes, termination grace, data path, PVC and retention remain unchanged.
The StatefulSet gains a read-only server certificate mount and `fsGroup: 999`,
with `OnRootMismatch` to avoid unnecessary recursive data-volume ownership changes.
The root-owned key is group-readable only (0440), accepted by PostgreSQL's
root-owned-key exception; the certificate is 0444. TLS uses a minimum of TLS1.2.

Four cert-manager resources create a namespaced private root CA, CA Issuer and
90-day server certificate. Negative sync waves request issuance before the changed
StatefulSet. Confirm both Certificates and Issuers Ready and the server Secret's
key/certificate match before permitting the single StatefulSet restart. Do not
assume resource ordering alone proves issuance succeeded.

The restart temporarily interrupts all shared-database connections. Coordinate
the approved maintenance window, verify recovery backups first, and check each
existing consumer after restart. The existing PostSync bootstrap Job still performs
its idempotent application-role setup and now creates a dedicated TLS reload role.
That role is non-superuser, cannot create roles/databases, has no memberships or
application-database access and receives only an explicit CONNECT grant on postgres
and EXECUTE on pg_catalog.pg_reload_conf(). Existing PUBLIC privileges on the
maintenance database are not changed. Its random password has a separate SOPS Secret.

No pg_hba.conf edits, client certificates, SSL-only host rules, existing password
changes, existing database changes or client DSN changes are included. TLS and existing
non-TLS clients negotiate independently on the same port. Verify both connection
modes after rollout, plus `SHOW ssl`, certificate identity and pg_stat_ssl.

Only the public CA certificate is exported to Wednesday Club. Keep the CA private
key in its generated Secret; protect/back up that Secret separately. CA resources
and generated Secrets have Argo prune/delete protection. Do not enable cert-manager
Certificate owner-reference garbage collection without considering CA retention.
The CA key is not automatically rotated. Its ten-year validity and renewal require
an explicit trust-distribution lifecycle; do not silently replace trusted CA state.

Server SANs cover the service DNS names, localhost and 127.0.0.1. This permits
hostname-verified TLS both inside the cluster and through a private kubectl port
forward during owner-authorized restore/verification.

Projected Secret volumes receive certificate renewals automatically, but PostgreSQL
must reload configuration to use the new certificate. A reload does not interrupt
active connections or restart the server. A daily verified-TLS reload CronJob is
included with the dedicated restricted reload credential, never the administrator
password. Its schedule leaves a thirty-day renewal buffer and uses no retry loop.
Check the served certificate serial/expiry after reload; pg_reload_conf
success alone does not prove the renewed files were accepted.

Primary references:
- https://www.postgresql.org/docs/17/ssl-tcp.html
- https://cert-manager.io/docs/configuration/ca/
