# Secrets Setup for Azure Billing Reports

This guide shows you how to add the Azure credentials to the encrypted secrets file.

## Prerequisites

✅ SOPS installed (you have this: `/opt/homebrew/bin/sops`)  
✅ Age key configured (already set up in `.sops.yaml`)  
⏳ Azure Service Principal credentials (need to create)

## Step 1: Create Azure Service Principal

First, create the Service Principal with Cost Management Reader permissions:

```bash
# Set your subscription ID
SUBSCRIPTION_ID="b76ecd16-669b-4ca9-b797-b7786eb1b334"

# Create the service principal
az ad sp create-for-rbac \
  --name "slack-billing-reporter" \
  --role "Cost Management Reader" \
  --scopes "/subscriptions/$SUBSCRIPTION_ID" \
  --output json

# Expected output (SAVE THESE VALUES):
# {
#   "appId": "12345678-1234-1234-1234-123456789abc",      # ← This is AZURE_CLIENT_ID
#   "displayName": "slack-billing-reporter",
#   "password": "your-client-secret-here",                 # ← This is AZURE_CLIENT_SECRET
#   "tenant": "87654321-4321-4321-4321-cba987654321"     # ← This is AZURE_TENANT_ID
# }
```

**Save these three values:**
- `appId` → `AZURE_CLIENT_ID`
- `password` → `AZURE_CLIENT_SECRET` (won't be shown again!)
- `tenant` → `AZURE_TENANT_ID`

## Step 2: Edit the Encrypted Secrets File

Navigate to the slack-notifications directory in gitops:

```bash
cd /Users/elad/Development/jshipster/gitops/slack-notifications
```

Edit the secrets file with SOPS (it will decrypt, open your editor, then re-encrypt):

```bash
sops secrets.yaml
```

This will open your default editor with the decrypted content.

## Step 3: Add Azure Credentials

In the editor, you'll see a structure like this:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: slack-notifications-secrets
  namespace: jshipster
  labels:
    app: slack-notifications
type: Opaque
stringData:
  SLACK_TOKEN: "xoxb-your-existing-token"
  SLACK_WEBHOOK_URL: "https://hooks.slack.com/services/..."
  SLACK_SIGNING_SECRET: "..."
  SLACK_CLIENT_ID: "..."
  SLACK_CLIENT_SECRET: "..."
  SLACK_VERIFICATION_TOKEN: "..."
```

**Add these three new lines** to the `stringData` section:

```yaml
stringData:
  # Existing Slack credentials (don't change these)
  SLACK_TOKEN: "xoxb-your-existing-token"
  SLACK_WEBHOOK_URL: "https://hooks.slack.com/services/..."
  SLACK_SIGNING_SECRET: "..."
  SLACK_CLIENT_ID: "..."
  SLACK_CLIENT_SECRET: "..."
  SLACK_VERIFICATION_TOKEN: "..."
  
  # NEW: Add these Azure credentials
  AZURE_TENANT_ID: "87654321-4321-4321-4321-cba987654321"
  AZURE_CLIENT_ID: "12345678-1234-1234-1234-123456789abc"
  AZURE_CLIENT_SECRET: "your-client-secret-from-step-1"
```

**Important:**
- Replace the values with YOUR actual credentials from Step 1
- Keep the quotes around the values
- Don't modify any of the SOPS metadata at the bottom of the file

## Step 4: Save and Exit

1. Save the file in your editor (`:wq` in vim, `Ctrl+X` then `Y` in nano, `Cmd+S` then close in VS Code)
2. SOPS will automatically re-encrypt the file
3. You should see the file is encrypted again when you view it

Verify it's encrypted:

```bash
cat secrets.yaml | head -20
```

You should see encrypted content like:
```yaml
apiVersion: ENC[AES256_GCM,data:19Q=,iv:...]
kind: ENC[AES256_GCM,data:yHG8IC4E,iv:...]
...
```

## Step 5: Commit and Push

```bash
# Add the updated secrets file
git add secrets.yaml

# Commit
git commit -m "Add Azure credentials for billing reports"

# Push to trigger ArgoCD sync
git push origin main
```

## Step 6: Verify Deployment

After pushing, check that the secrets are deployed:

```bash
# Check if secret exists
kubectl get secret -n jshipster slack-notifications-secrets

# Verify the secret has the new keys (values will be base64 encoded)
kubectl get secret -n jshipster slack-notifications-secrets -o yaml | grep -E "AZURE_"

# Expected output:
#   AZURE_CLIENT_ID: <base64-encoded-value>
#   AZURE_CLIENT_SECRET: <base64-encoded-value>
#   AZURE_TENANT_ID: <base64-encoded-value>
```

## Step 7: Test the Billing Report

Manually trigger a test report:

```bash
# Create a test job from the CronJob
kubectl create job -n jshipster test-billing-report \
  --from=cronjob/azure-billing-report

# Watch the job status
kubectl get jobs -n jshipster -w

# Check logs
kubectl logs -n jshipster -l job-name=test-billing-report

# If successful, you should see:
# "Running in billing report mode..."
# "Billing report sent successfully"

# Clean up test job
kubectl delete job -n jshipster test-billing-report
```

## Troubleshooting

### Problem: "failed to create Azure credential"

**Solution:** Check that the Service Principal credentials are correct:

```bash
# Test authentication manually
az login --service-principal \
  -u "<AZURE_CLIENT_ID>" \
  -p "<AZURE_CLIENT_SECRET>" \
  --tenant "<AZURE_TENANT_ID>"

# If successful, the credentials are valid
az logout
```

### Problem: "SOPS command not found" when editing

**Solution:** Install SOPS:
```bash
brew install sops
```

### Problem: "failed to get master keys"

**Solution:** You need the age private key. Check if you have it:
```bash
ls -la ~/.config/sops/age/
```

If the key is missing, ask the person who set up the gitops repo for the age private key.

### Problem: Secret not updating in Kubernetes

**Solution:** Force ArgoCD to sync:
```bash
# Get the ArgoCD admin password
kubectl get secret -n argocd argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d

# Port forward to ArgoCD
kubectl port-forward -n argocd svc/argocd-server 8080:443

# Open https://localhost:8080 and login with:
# Username: admin
# Password: (from command above)

# Then click "Sync" on the slack-notifications app
```

Or via CLI:
```bash
# Install argocd CLI if needed
brew install argocd

# Login
argocd login localhost:8080 --username admin --insecure

# Sync
argocd app sync slack-notifications
```

## Security Notes

✅ **Secrets are encrypted at rest** using SOPS with Age encryption  
✅ **Service Principal has read-only access** to billing data only  
✅ **Credentials are never committed unencrypted** to git  
✅ **Only people with the Age private key** can decrypt secrets  
✅ **Kubernetes injects secrets at runtime** as environment variables

## What If I Need to Rotate Credentials?

1. Create a new Service Principal (or regenerate the existing one's secret)
2. Edit the secrets file again: `sops secrets.yaml`
3. Update the `AZURE_CLIENT_SECRET` (and/or other values)
4. Save, commit, and push
5. Restart the deployment to pick up new secrets:
   ```bash
   kubectl rollout restart -n jshipster deployment/slack-notifications
   ```

## Next Steps

After completing the secrets setup:

1. ✅ Secrets are encrypted and committed
2. ✅ ArgoCD will sync and create the secret in Kubernetes
3. ✅ CronJob will run every Monday at 9 AM
4. ✅ You'll receive weekly billing reports in Slack

**Test it now** by running Step 7 above, or wait until Monday at 9 AM for the first scheduled report!

---

**Need Help?**
- Check logs: `kubectl logs -n jshipster -l app=azure-billing-report`
- Review setup: See `SETUP.md` in this directory
- Check service: `kubectl get pods -n jshipster -l app=slack-notifications`
