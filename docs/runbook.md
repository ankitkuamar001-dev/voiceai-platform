# Runbook

This runbook contains operational procedures, alerts, scaling strategies, and troubleshooting steps for the VoiceAI Platform.

## 1. Operational Procedures

### 1.1 Restarting a Service
If a service is stuck or behaving unexpectedly, you can restart its pods:
```bash
kubectl rollout restart deployment/<service-name> -n voiceai
```

### 1.2 Accessing the Database
To connect to the primary PostgreSQL database for debugging:
```bash
kubectl port-forward svc/postgres 5432:5432 -n voiceai
# Then use your local psql client
psql -h localhost -U voiceai -d voiceai_db
```

### 1.3 Triggering a Manual Backup
Ensure logical backups are taken periodically. A quick manual backup:
```bash
pg_dump -h <db-host> -U <user> -d <db> -F c -f backup.dump
```

## 2. Alerts and Monitoring

We use Prometheus and Grafana for monitoring, and Alertmanager for notifications.

### High CPU/Memory Usage
- **Alert:** `HighCpuUsage` or `HighMemoryUsage`
- **Impact:** Service degradation or OOM kills.
- **Action:** 
  1. Check logs to see if a specific request is causing a spike.
  2. Scale the deployment horizontally (add more replicas).
  3. Profile the application for memory leaks.

### Elevated Error Rates (5xx)
- **Alert:** `High5xxErrorRate`
- **Impact:** Users are experiencing failed requests.
- **Action:**
  1. Check service logs for unhandled exceptions.
  2. Verify database and Redis connectivity.
  3. Ensure dependent services (like the LLM provider or Twilio/WhatsApp APIs) are not experiencing downtime.

### Database Connection Pool Exhaustion
- **Alert:** `DbConnectionPoolExhausted`
- **Impact:** Requests hang or fail with database timeout errors.
- **Action:**
  1. Check if long-running queries are blocking the pool.
  2. Consider increasing `pool_size` in the SQLAlchemy settings or deploying PgBouncer.

## 3. Scaling Strategies

### Horizontal Pod Autoscaling (HPA)
Most services should have HPA configured based on CPU and memory utilization.
- Example HPA for `voice-agent-api`:
  ```bash
  kubectl autoscale deployment voice-agent-api --cpu-percent=70 --min=2 --max=10 -n voiceai
  ```

### Vertical Scaling
If a service genuinely requires more memory per instance (e.g., loading large models or performing heavy audio processing), adjust the resource requests and limits in the deployment manifest.

### Database Scaling
- Scale read replicas for read-heavy workloads (analytics).
- Increase instance size for the primary write node.

## 4. Troubleshooting MinIO

If MinIO storage is inaccessible:
1. Verify the MinIO pods are running: `kubectl get pods -l app=minio`
2. Check PVC binding: `kubectl get pvc`
3. Ensure the access key and secret match the application secrets.
