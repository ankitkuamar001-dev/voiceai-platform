# Deployment Guide

This document outlines the step-by-step process for deploying the VoiceAI Platform to a Kubernetes cluster using Kustomize.

## Prerequisites

- Kubernetes cluster (v1.28+ recommended)
- `kubectl` configured with cluster access
- Kustomize (v5.0.0+)
- Helm (for some infrastructure dependencies like MinIO or Redis, if not using managed services)
- Access to the GitHub Container Registry (`ghcr.io`) for pulling images

## Infrastructure Setup

1. **Database:** Ensure your PostgreSQL instance is running and accessible from the cluster.
2. **Redis:** Ensure Redis is running for caching and background tasks.
3. **MinIO:** Ensure MinIO is running and accessible for object storage.

## Kustomize Structure

Our Kubernetes deployment manifests are structured using Kustomize overlays:

```
infra/k8s/
├── base/
│   ├── kustomization.yaml
│   ├── deployment.yaml
│   ├── service.yaml
│   └── configmap.yaml
└── overlays/
    ├── staging/
    │   ├── kustomization.yaml
    │   └── patch.yaml
    └── production/
        ├── kustomization.yaml
        └── patch.yaml
```

*(Note: Ensure you have populated the overlays before deploying).*

## Deploying to Staging

Staging deployments happen automatically on push to the `main` branch via GitHub Actions. To deploy manually:

1. Target the staging cluster:
   ```bash
   export KUBECONFIG=~/.kube/staging-config
   ```

2. Set your environment variables and secrets:
   ```bash
   kubectl create secret generic voiceai-secrets \
     --from-literal=DATABASE_URL="postgresql+asyncpg://..." \
     --from-literal=REDIS_URL="..." \
     --from-literal=MINIO_ACCESS_KEY="..." \
     --from-literal=MINIO_SECRET_KEY="..." \
     --dry-run=client -o yaml | kubectl apply -f -
   ```

3. Deploy using Kustomize:
   ```bash
   kustomize build infra/k8s/overlays/staging | kubectl apply -f -
   ```

## Deploying to Production

Production deployments happen automatically when a GitHub Release is published. To deploy manually:

1. Target the production cluster:
   ```bash
   export KUBECONFIG=~/.kube/prod-config
   ```

2. Set your environment variables and secrets (similar to Staging).

3. Deploy using Kustomize:
   ```bash
   kustomize build infra/k8s/overlays/production | kubectl apply -f -
   ```

## Verifying Deployment

1. Check the status of pods:
   ```bash
   kubectl get pods -n voiceai
   ```

2. Check logs for a specific service (e.g., voice-agent-api):
   ```bash
   kubectl logs -f deployment/voice-agent-api -n voiceai
   ```

## Rollbacks

If a deployment fails or exhibits issues, you can roll back to the previous revision:

```bash
kubectl rollout undo deployment/<service-name> -n voiceai
```
