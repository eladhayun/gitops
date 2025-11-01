.PHONY: argocd-install argocd-access argocd-password argocd-uninstall argocd-repo-add get-argo-cd-token tunnel-setup tunnel-credentials tunnel-status postgres-setup postgres-password

CONTEXT := jshipster
NAMESPACE := argocd
POSTGRES_NAMESPACE := johnson

# Add ArgoCD Helm repository
argocd-repo-add:
	@echo "Adding ArgoCD Helm repository..."
	helm repo add argo https://argoproj.github.io/argo-helm
	helm repo update

# Install ArgoCD using Helm
argocd-install: argocd-repo-add
	@echo "Installing ArgoCD on cluster with context: $(CONTEXT)..."
	helm install argocd argo/argo-cd \
		--namespace $(NAMESPACE) \
		--create-namespace \
		--kube-context $(CONTEXT)
	@echo ""
	@echo "✅ ArgoCD installation completed!"
	@echo ""
	@echo "Waiting for pods to be ready..."
	kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=argocd-server \
		-n $(NAMESPACE) \
		--context $(CONTEXT) \
		--timeout=300s
	@echo ""
	@$(MAKE) argocd-password

# Get ArgoCD admin password
argocd-password:
	@echo "=========================================="
	@echo "ArgoCD Login Credentials"
	@echo "=========================================="
	@echo "Username: admin"
	@printf "Password: "
	@kubectl -n $(NAMESPACE) get secret argocd-initial-admin-secret \
		-o jsonpath="{.data.password}" \
		--context $(CONTEXT) | base64 -d
	@echo ""
	@echo "=========================================="
	@echo ""

# Port forward to ArgoCD server and display credentials
argocd-access: argocd-password
	@echo "Starting port forward to ArgoCD server..."
	@echo "Access ArgoCD UI at: http://localhost:8080"
	@echo ""
	kubectl port-forward service/argocd-server \
		-n $(NAMESPACE) \
		8080:443 \
		--context $(CONTEXT)

# Uninstall ArgoCD
argocd-uninstall:
	@echo "Uninstalling ArgoCD..."
	helm uninstall argocd \
		--namespace $(NAMESPACE) \
		--kube-context $(CONTEXT)
	@echo "Deleting namespace..."
	kubectl delete namespace $(NAMESPACE) \
		--context $(CONTEXT)
	@echo "✅ ArgoCD uninstalled successfully!"

get-argo-cd-token:
	@echo "Getting ArgoCD token..."
	@echo "Starting temporary port forward..."
	@kubectl port-forward service/argocd-server \
		-n $(NAMESPACE) \
		8080:443 \
		--context $(CONTEXT) > /dev/null 2>&1 & \
	PF_PID=$$!; \
	sleep 2; \
	PASSWORD=$$(kubectl -n $(NAMESPACE) get secret argocd-initial-admin-secret \
		-o jsonpath="{.data.password}" \
		--context $(CONTEXT) | base64 -d); \
	TOKEN=$$(curl -s https://localhost:8080/api/v1/session \
		-d '{"username":"admin","password":"'"$$PASSWORD"'"}' \
		-H "Content-Type: application/json" \
		-k | jq -r '.token'); \
	kill $$PF_PID 2>/dev/null || true; \
	echo "ArgoCD token: $$TOKEN"

# Cloudflare Tunnel Setup Commands

# Setup Cloudflare Tunnel for ArgoCD
tunnel-setup:
	@echo "=========================================="
	@echo "Cloudflare Tunnel Setup for ArgoCD"
	@echo "=========================================="
	@echo ""
	@echo "Prerequisites:"
	@echo "  1. Cloudflare account with a domain"
	@echo "  2. cloudflared CLI installed (brew install cloudflare/cloudflare/cloudflared)"
	@echo ""
	@echo "Run these commands:"
	@echo ""
	@echo "  # 1. Authenticate with Cloudflare"
	@echo "  cloudflared tunnel login"
	@echo ""
	@echo "  # 2. Create a tunnel"
	@echo "  cloudflared tunnel create argocd-tunnel"
	@echo ""
	@echo "  # 3. Create Kubernetes secret with credentials"
	@echo "  kubectl create secret generic tunnel-credentials \\"
	@echo "    --from-file=credentials.json=~/.cloudflared/<TUNNEL_ID>.json \\"
	@echo "    -n $(NAMESPACE) \\"
	@echo "    --context $(CONTEXT)"
	@echo ""
	@echo "  # 4. Update argocd-tunnel/configmap.yaml with your tunnel ID and domain"
	@echo ""
	@echo "  # 5. Configure DNS"
	@echo "  cloudflared tunnel route dns argocd-tunnel argocd.yourdomain.com"
	@echo ""
	@echo "  # 6. Apply the tunnel (after updating configmap)"
	@echo "  make tunnel-deploy"
	@echo ""
	@echo "For detailed instructions, see: docs/argocd-cloudflare-tunnel.md"
	@echo ""

# Create tunnel credentials secret
tunnel-credentials:
	@echo "Creating tunnel credentials secret..."
	@read -p "Enter path to credentials.json file: " CREDS_PATH; \
	kubectl create secret generic tunnel-credentials \
		--from-file=credentials.json=$$CREDS_PATH \
		-n $(NAMESPACE) \
		--context $(CONTEXT)
	@echo "✅ Tunnel credentials secret created!"

# Deploy the tunnel via ArgoCD
tunnel-deploy:
	@echo "Deploying Cloudflare Tunnel for ArgoCD..."
	kubectl apply -f apps/argocd-tunnel.yaml --context $(CONTEXT)
	@echo "✅ Tunnel application created in ArgoCD"
	@echo ""
	@echo "Check status with: make tunnel-status"

# Check tunnel status
tunnel-status:
	@echo "=========================================="
	@echo "Cloudflare Tunnel Status"
	@echo "=========================================="
	@echo ""
	@echo "ArgoCD Application:"
	@kubectl get application argocd-tunnel -n $(NAMESPACE) --context $(CONTEXT) || echo "Application not found"
	@echo ""
	@echo "Pods:"
	@kubectl get pods -n $(NAMESPACE) -l app=cloudflared --context $(CONTEXT) || echo "No pods found"
	@echo ""
	@echo "Recent logs:"
	@kubectl logs -n $(NAMESPACE) -l app=cloudflared --tail=20 --context $(CONTEXT) 2>/dev/null || echo "No logs available"

# PostgreSQL Setup Commands

# Generate a secure PostgreSQL password
postgres-password:
	@echo "Generating secure PostgreSQL password..."
	@openssl rand -base64 32
	@echo ""
	@echo "Copy this password and update:"
	@echo "  1. johnson-postgres/secrets.yaml (postgres-password field)"
	@echo "  2. johnson-backend-secrets secret in namespace $(POSTGRES_NAMESPACE) (JOHNSON_DATABASE_URL field)"

# Setup PostgreSQL secret with password and database URL
postgres-setup:
	@echo "=========================================="
	@echo "PostgreSQL Setup for Johnson Backend"
	@echo "=========================================="
	@echo ""
	@echo "Generating secure PostgreSQL password..."
	@POSTGRES_PASSWORD=$$(openssl rand -base64 32); \
	echo "Generated password: $$POSTGRES_PASSWORD"; \
	echo ""; \
	echo "Creating/updating PostgreSQL secret..."; \
	kubectl create secret generic johnson-postgres-secret \
		--from-literal=postgres-user=postgres \
		--from-literal=postgres-password="$$POSTGRES_PASSWORD" \
		-n $(POSTGRES_NAMESPACE) \
		--context $(CONTEXT) \
		--dry-run=client -o yaml | kubectl apply -f - --context $(CONTEXT); \
	echo ""; \
	echo "Creating/updating Johnson Backend secret with database URL..."; \
	POSTGRES_HOST=johnson-postgres.johnson.svc.cluster.local; \
	POSTGRES_PORT=5432; \
	POSTGRES_DB=johnson; \
	POSTGRES_USER=postgres; \
	DATABASE_URL="postgresql://$$POSTGRES_USER:$$POSTGRES_PASSWORD@$$POSTGRES_HOST:$$POSTGRES_PORT/$$POSTGRES_DB"; \
	if kubectl get secret johnson-backend-secrets -n $(POSTGRES_NAMESPACE) --context $(CONTEXT) &>/dev/null; then \
		echo "Secret exists - patching JOHNSON_DATABASE_URL field..."; \
		kubectl patch secret johnson-backend-secrets \
			-n $(POSTGRES_NAMESPACE) \
			--context $(CONTEXT) \
			--type='json' \
			-p='[{"op": "replace", "path": "/data/JOHNSON_DATABASE_URL", "value": "'$$(echo -n $$DATABASE_URL | base64)'"}]'; \
	else \
		echo "Secret does not exist - creating with database URL..."; \
		kubectl create secret generic johnson-backend-secrets \
			--from-literal=JOHNSON_DATABASE_URL="$$DATABASE_URL" \
			-n $(POSTGRES_NAMESPACE) \
			--context $(CONTEXT); \
		echo "⚠️  Note: You may need to add other required fields:"; \
		echo "   - JOHNSON_AUTH_SECRET"; \
		echo "   - JOHNSON_RESET_SECRET"; \
		echo "   - WHATSAPP_TWILIO_ACCOUNT_SID"; \
		echo "   - WHATSAPP_TWILIO_AUTH_TOKEN"; \
	fi; \
	echo ""; \
	echo "✅ PostgreSQL setup completed!"; \
	echo ""; \
	echo "IMPORTANT: Update johnson-postgres/secrets.yaml with the password:"; \
	echo "  postgres-password: \"$$POSTGRES_PASSWORD\""; \
	echo ""; \
	echo "Database URL format:"; \
	echo "  $$DATABASE_URL"
