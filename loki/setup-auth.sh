#!/bin/bash
# Setup script for Loki Basic Authentication

set -e

NAMESPACE="loki"
CONTEXT="jshipster"
SECRET_NAME="loki-auth"

echo "Setting up Loki Basic Authentication..."

# Check if htpasswd is available
if ! command -v htpasswd &> /dev/null; then
  echo "❌ htpasswd not found. Install it with:"
  echo "   macOS: brew install httpd"
  echo "   Ubuntu/Debian: sudo apt-get install apache2-utils"
  echo "   RHEL/CentOS: sudo yum install httpd-tools"
  exit 1
fi

# Prompt for username
read -p "Enter username for Loki access: " USERNAME

if [ -z "$USERNAME" ]; then
  echo "❌ Username cannot be empty"
  exit 1
fi

# Generate password
echo "Enter password for user '$USERNAME':"
htpasswd -c auth "$USERNAME"

if [ ! -f auth ]; then
  echo "❌ Failed to create auth file"
  exit 1
fi

# Create or update secret
echo "Creating Kubernetes secret..."
kubectl create secret generic "$SECRET_NAME" \
  --from-file=auth \
  -n "$NAMESPACE" \
  --context="$CONTEXT" \
  --dry-run=client -o yaml | kubectl apply -f -

# Clean up local auth file
rm -f auth

echo ""
echo "✅ Authentication secret created!"
echo ""
echo "Username: $USERNAME"
echo "Password: (the one you just entered)"
echo ""
echo "To access Loki:"
echo "  URL: https://logs.jshipster.io"
echo "  Username: $USERNAME"
echo ""
echo "To update credentials, run this script again."
