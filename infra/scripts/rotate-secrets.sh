#!/bin/bash
set -euo pipefail

echo "Rotating Kubernetes secrets for voiceai namespace..."

# Check if kustomize and kubectl exist
if ! command -v kubectl &> /dev/null; then
    echo "kubectl could not be found"
    exit 1
fi

# Example: generate new secret for JWT and apply
NEW_JWT=$(openssl rand -base64 32 | base64)

# Patch the secrets file or apply it directly
# For this script we will apply a patch to update the JWT_SECRET_KEY
kubectl patch secret voiceai-secrets -n voiceai -p="{\"data\":{\"JWT_SECRET_KEY\": \"$NEW_JWT\"}}"

echo "Secrets updated successfully."

# Restart deployments to pick up new secrets
echo "Restarting deployments..."

kubectl rollout restart deployment auth-service -n voiceai
kubectl rollout restart deployment ai-brain -n voiceai
kubectl rollout restart deployment ticket-service -n voiceai
kubectl rollout restart deployment analytics-service -n voiceai
kubectl rollout restart deployment notification-service -n voiceai
kubectl rollout restart deployment voice-agent -n voiceai
kubectl rollout restart deployment voice-agent-api -n voiceai
kubectl rollout restart deployment whatsapp-service -n voiceai
kubectl rollout restart deployment dashboard -n voiceai

# Check rollout status
kubectl rollout status deployment auth-service -n voiceai

echo "Secret rotation complete."
