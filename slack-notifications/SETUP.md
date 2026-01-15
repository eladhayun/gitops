# Azure Billing Reports Setup Guide

This guide walks you through setting up automated weekly Azure billing reports sent to Slack.

## Overview

The slack-notifications service now includes Azure billing report functionality that:
- Runs automatically every Monday at 9:00 AM
- Fetches current Azure spending and budget information
- Shows top resources by cost
- Sends a formatted report to your specified Slack channel
- Provides visual alerts when approaching budget limits

## Prerequisites

1. **Azure Access**
   - Azure subscription with billing access
   - Permissions to create Service Principals
   - Cost Management Reader access

2. **Slack Workspace**
   - Admin access to create webhooks or apps
   - A dedicated channel for billing reports (recommended: `#billing`)

3. **Kubernetes Cluster**
   - Running AKS cluster with ArgoCD
   - SOPS configured for secret management
   - Access to kubectl and the gitops repository

## Step-by-Step Setup

### Step 1: Get Your Azure Subscription ID

```bash
# List your subscriptions
az account list --output table

# Note the Subscription ID you want to monitor
# It should look like: b76ecd16-669b-4ca9-b797-b7786eb1b334
```

### Step 2: Create Azure Service Principal

Create a Service Principal with Cost Management Reader permissions:

```bash
# Replace <YOUR_SUBSCRIPTION_ID> with your actual subscription ID
SUBSCRIPTION_ID="<YOUR_SUBSCRIPTION_ID>"

# Create the service principal
az ad sp create-for-rbac \
  --name "slack-billing-reporter" \
  --role "Cost Management Reader" \
  --scopes "/subscriptions/$SUBSCRIPTION_ID" \
  --output json

# Save the output - you'll need these values:
# {
#   "appId": "<YOUR_AZURE_CLIENT_ID>",
#   "password": "<YOUR_AZURE_CLIENT_SECRET>",
#   "tenant": "<YOUR_AZURE_TENANT_ID>"
# }
```

**Important**: Save these credentials securely. The `password` field is the client secret and won't be shown again.

### Step 3: Create or Get Slack Webhook

#### Option A: Using Incoming Webhooks (Recommended)

1. Go to https://api.slack.com/apps
2. Select your workspace's Slack app (or create one)
3. Navigate to "Incoming Webhooks"
4. Click "Add New Webhook to Workspace"
5. Select the channel (e.g., `#billing`)
6. Copy the webhook URL (looks like: `https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXX`)

#### Option B: Using Bot Token

1. Go to https://api.slack.com/apps
2. Select your app
3. Navigate to "OAuth & Permissions"
4. Copy the "Bot User OAuth Token" (starts with `xoxb-`)
5. Ensure the bot has `chat:write` permission

### Step 4: Update Kubernetes Secrets

Edit the encrypted secrets file:

```bash
# Navigate to the gitops slack-notifications directory
cd /path/to/gitops/slack-notifications

# Edit secrets with SOPS (will decrypt, open editor, re-encrypt)
sops secrets.yaml
```

Add the Azure credentials to the `stringData` section:

```yaml
stringData:
  # Existing Slack credentials
  SLACK_WEBHOOK_URL: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
  SLACK_TOKEN: "xoxb-your-token-here"
  
  # Add these Azure credentials
  AZURE_TENANT_ID: "your-tenant-id-from-step-2"
  AZURE_CLIENT_ID: "your-client-id-from-step-2"
  AZURE_CLIENT_SECRET: "your-client-secret-from-step-2"
```

Save and close the file. SOPS will automatically re-encrypt it.

### Step 5: Update CronJob Configuration

Edit the CronJob manifest:

```bash
vim cronjob.yaml
```

Update these values:

1. **Subscription ID** (line ~18):
   ```yaml
   - name: AZURE_SUBSCRIPTION_ID
     value: "YOUR_SUBSCRIPTION_ID"  # Replace with your subscription ID
   ```

2. **Slack Channel** (line ~38):
   ```yaml
   - name: SLACK_REPORT_CHANNEL
     value: "#billing"  # Change to your preferred channel
   ```

3. **Schedule** (optional, line ~10):
   ```yaml
   schedule: "0 9 * * 1"  # Every Monday at 9:00 AM UTC
   # Modify if you want a different schedule
   # Format: "minute hour day-of-month month day-of-week"
   # Examples:
   # "0 9 * * 1" = Every Monday at 9 AM
   # "0 9 1 * *" = First day of every month at 9 AM
   # "0 9 * * 5" = Every Friday at 9 AM
   ```

### Step 6: Commit and Deploy

```bash
# Stage your changes
git add secrets.yaml cronjob.yaml

# Commit
git commit -m "Configure Azure billing reports for Slack"

# Push to trigger ArgoCD sync
git push origin main
```

ArgoCD will automatically detect the changes and deploy them to your cluster.

### Step 7: Verify Deployment

Check that everything deployed correctly:

```bash
# Check if CronJob was created
kubectl get cronjobs -n jshipster

# Expected output:
# NAME                   SCHEDULE     SUSPEND   ACTIVE   LAST SCHEDULE   AGE
# azure-billing-report   0 9 * * 1    False     0        <none>          1m

# Check service account
kubectl get serviceaccount -n jshipster azure-billing-reporter

# Check secrets are mounted
kubectl get secret -n jshipster slack-notifications-secrets
```

### Step 8: Test the Report (Optional)

Manually trigger a billing report to test:

```bash
# Create a test job from the CronJob
kubectl create job -n jshipster test-billing-report \
  --from=cronjob/azure-billing-report

# Watch the job
kubectl get jobs -n jshipster -w

# Check logs
kubectl logs -n jshipster -l job-name=test-billing-report

# Clean up test job
kubectl delete job -n jshipster test-billing-report
```

You should receive a billing report in your Slack channel within a few seconds.

## What the Report Includes

Your weekly billing report will show:

```
📊 Azure Weekly Billing Report
Saturday, November 29, 2025

💰 Current Spend: $134.11 / $150 (89.4%)
📅 Period: Nov 22 - Nov 29, 2025

🔝 Top Resources by Cost:
1. Virtual Machines Dv3/DSv3 Series - D2 v3/D2s v3 - US East - $45.23
2. Azure Database for PostgreSQL Flexible Server - $12.34
3. Premium SSD Managed Disks - P10 LRS - US East - $8.45
4. Load Balancer - Standard Data Processed - $5.67
5. Standard IPv4 Static Public IP - $3.21

⚠️ Alert: You've exceeded 90% of your monthly budget!
```

The report will also include color-coded attachments:
- 🟢 Green: < 75% of budget
- 🟡 Yellow: 75-90% of budget  
- 🔴 Red: > 90% of budget

## Troubleshooting

### Report Not Sent

1. **Check CronJob schedule**:
   ```bash
   kubectl describe cronjob -n jshipster azure-billing-report
   ```

2. **Check recent jobs**:
   ```bash
   kubectl get jobs -n jshipster
   ```

3. **Check job logs**:
   ```bash
   # Get the most recent job
   JOB_NAME=$(kubectl get jobs -n jshipster -l app=azure-billing-report --sort-by=.status.startTime -o jsonpath='{.items[-1].metadata.name}')
   
   # View logs
   kubectl logs -n jshipster job/$JOB_NAME
   ```

### Authentication Errors

If you see "Failed to create Azure credential" errors:

1. Verify secrets are set correctly:
   ```bash
   kubectl get secret -n jshipster slack-notifications-secrets -o yaml
   ```

2. Check Service Principal permissions:
   ```bash
   az role assignment list --assignee <AZURE_CLIENT_ID> --subscription <SUBSCRIPTION_ID>
   ```

3. Test authentication manually:
   ```bash
   kubectl exec -n jshipster deployment/slack-notifications -- sh -c '
     echo "Testing Azure authentication..."
     env | grep AZURE
   '
   ```

### Slack Not Receiving Messages

1. **Check webhook URL** is correct in secrets
2. **Test webhook manually**:
   ```bash
   curl -X POST -H 'Content-type: application/json' \
     --data '{"text":"Test message from Azure billing"}' \
     YOUR_WEBHOOK_URL
   ```

3. **Verify channel exists** and bot has permission to post

### No Budget Data

If the report shows $0 budget:

1. **Create a budget** in Azure Portal:
   - Go to Cost Management + Billing
   - Select your subscription
   - Navigate to "Budgets"
   - Create a new budget (e.g., $150/month)

2. **Wait a few minutes** for Azure to propagate the budget

3. **Re-run the report**

## Customization

### Change Report Frequency

Edit the schedule in `cronjob.yaml`:

```yaml
spec:
  # Weekly on Mondays at 9 AM (default)
  schedule: "0 9 * * 1"
  
  # Daily at 9 AM
  schedule: "0 9 * * *"
  
  # First day of month at 9 AM
  schedule: "0 9 1 * *"
  
  # Every Friday at 5 PM
  schedule: "0 17 * * 5"
```

### Change Report Channel

Edit the environment variable in `cronjob.yaml`:

```yaml
- name: SLACK_REPORT_CHANNEL
  value: "#finance"  # or "#alerts" or "#devops"
```

### Adjust Resource Requests

If the job is using too much or too little resources:

```yaml
resources:
  requests:
    memory: "32Mi"   # Increase if job OOMs
    cpu: "10m"       # Increase if job is slow
  limits:
    memory: "128Mi"
    cpu: "100m"
```

## Security Notes

1. **Secrets are encrypted** with SOPS using Age encryption
2. **Service Principal** has read-only access to billing data
3. **No billing data is stored** - reports are generated on-demand
4. **Credentials are injected** at runtime via Kubernetes secrets
5. **Job runs with minimal permissions** via ServiceAccount

## Cost Impact

The billing report job itself has minimal cost impact:
- Runs for ~5-10 seconds per execution
- Uses ~50MB memory
- Negligible CPU usage (~10m cores)
- No data storage costs

Expected monthly cost: **< $0.01**

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review logs: `kubectl logs -n jshipster <pod-name>`
3. Check ArgoCD sync status in the UI
4. Review Azure Service Principal permissions

## Next Steps

- Set up additional budget alerts in Azure Portal
- Configure cost allocation tags on resources
- Review and optimize top spending resources
- Consider setting up Azure Cost Management alerts
- Document your cost optimization strategies

---

**Last Updated**: November 29, 2025
