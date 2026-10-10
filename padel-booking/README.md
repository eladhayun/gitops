# Wednesday Club GitOps

These artifacts are promoted into the existing `eladhayun/gitops` repository.
GitHub Actions alone changes the immutable application image tag. Argo CD reconciles
the Application; do not deploy an alternate imperative manifest.

The initial replica count is zero. This is not an empty replacement database and
does not grant purchase permission. PostgreSQL is the existing service at
`shared-postgres.postgres.svc.cluster.local:5432`, with dedicated booking and
WhatsApp databases/roles. Configure verified PostgreSQL TLS in private DSN files.
Never put credentials in command arguments or tracked plaintext files.

The KSOPS generator expects a real SOPS-encrypted `cloud-runtime-secret.yaml`
containing a Secret named `padel-private-source`. No fake encrypted placeholder is
provided: builds fail until commissioning supplies the actual encrypted file.
Required file keys are `runtime.json`, `booking-dsn`, `whatsapp-dsn`, and the
preserved `native-account-hmac.key`. Captured templates and manifests use `.json`
keys. Optional private file keys are `slack-token`, `google-token`,
`google-credentials`, `azure-sas`, and `postgres-ca.crt`.

Private config uses `data_dir: /private/state`, DSN file paths under that directory,
loopback API/MCP addresses `127.0.0.1:8000` and `127.0.0.1:8765`,
`allow_live_purchases: false`, and `observe_enabled: false` for commissioning.
Rewrite absolute manifest/template file references to `/private/state` before
encrypting; preserve captured request bytes and account key bytes. Every container
also pins `PADEL_LAZUZ_ALLOW_LIVE_PURCHASES=false`. Persisted settings must remain
paused. Keep WhatsApp and Google delivery disabled until separate owner setup.

Five independent processes share one private PVC, local compatibility lock and Unix
socket. A PostgreSQL session lock additionally excludes workers across machines.
UID1001 owns private files (0600) and directories (0700). Restart refuses a changed
account key. The PVC is protected from Argo pruning and deletion.

There is no Service, ingress or untrusted proxy. API and MCP are loopback only;
use explicit operator-controlled pod exec/port forwarding for private access.
Readiness runs inside the pod. No liveness probe may kill an in-flight worker.
Recreate and the 600-second graceful stop reduce overlap, but are not a substitute
for auditing pause, checking unresolved/in-flight operations, stopping the watchdog
first and draining the Mac services before migrating the final verified backup.

Before changing replicas to one through GitOps: verify the source backup and private
state, restore into an empty cloud application database, grant/check restricted
runtime roles, verify migration and historical evidence, and ensure no old worker
can restart. Never restore an old database over newer external-action evidence.
Then check loopback health, fresh worker heartbeat, MCP discovery/status, persisted
pause and both disabled purchase gates. Deployment performs no account discovery,
pairing, test message, booking or calendar write.
