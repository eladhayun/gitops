.PHONY: argocd-install argocd-access argocd-password argocd-uninstall argocd-repo-add get-argo-cd-token

CONTEXT := jshipster
NAMESPACE := argocd

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
