# GCP Deployment Guide

## Overview
This guide provides step-by-step instructions for deploying the Forge Project Plan Generation application to Google Cloud Platform (GCP).

## Prerequisites

1. **GCP Account**: Access to a GCP project with Kubernetes Engine enabled
2. **kubectl**: Kubernetes command-line tool installed and configured
3. **Docker**: For building and pushing container images
4. **API Credentials**: Valid API keys for AHA, Icarus, Smartsheet, Rally, and AccelQ

## Deployment Steps

### 1. Prepare the Container Image

```bash
# Build the Docker image
docker build -t forge-projectplan-generation .

# Tag for GCP Container Registry (replace PROJECT_ID)
docker tag forge-projectplan-generation gcr.io/PROJECT_ID/forge-projectplan-generation:latest

# Push to GCP Container Registry
docker push gcr.io/PROJECT_ID/forge-projectplan-generation:latest
```

### 2. Configure API Credentials

Create Kubernetes secrets for your API credentials:

```bash
kubectl create secret generic prjplan-app-secrets \
  --from-literal=AHA_API_KEY="your_aha_api_key_here" \
  --from-literal=ICARUS_API_KEY="your_icarus_api_key_here" \
  --from-literal=SMARTSHEET_API_KEY="your_smartsheet_api_key_here" \
  --from-literal=RALLY_API_KEY="your_rally_api_key_here" \
  --from-literal=ACCELQ_API_KEY="your_accelq_api_key_here"
```

Create ConfigMap for non-sensitive configuration:

```bash
kubectl create configmap prjplan-app-config \
  --from-literal=STREAMLIT_HOST="0.0.0.0" \
  --from-literal=STREAMLIT_PORT="8080" \
  --from-literal=API_HOST="127.0.0.1" \
  --from-literal=API_PORT="8000" \
  --from-literal=VERIFY_SSL="false"
```

### 3. Update Deployment Configuration

Before deploying, update the `infrastructure/deployment.yml` file:

1. Replace the image name with your GCR path:
   ```yaml
   image: gcr.io/PROJECT_ID/forge-projectplan-generation:latest
   ```

2. Update the `SMARTSHEET_WORKSPACE_ID` value:
   ```yaml
   - name: SMARTSHEET_WORKSPACE_ID
     value: "your_actual_workspace_id"
   ```

### 4. Deploy to Kubernetes

```bash
# Apply the deployment
kubectl apply -f infrastructure/deployment.yml

# Apply the service
kubectl apply -f infrastructure/service.yml

# Check deployment status
kubectl get deployments
kubectl get pods
kubectl get services
```

### 5. Access the Application

If using a LoadBalancer service:
```bash
# Get the external IP
kubectl get service forge-projectplan-service
```

If using port forwarding for testing:
```bash
# Forward local port to the service
kubectl port-forward service/forge-projectplan-service 8080:8080
```

Then access the application at: `http://localhost:8080` (or external IP)

## Configuration Details

### Environment Variables
The application uses these key environment variables:

- `STREAMLIT_HOST`: Host for Streamlit frontend (0.0.0.0 for GCP)
- `STREAMLIT_PORT`: Port for Streamlit frontend (8080)
- `API_HOST`: Host for FastAPI backend (127.0.0.1)
- `API_PORT`: Port for FastAPI backend (8000)
- `VERIFY_SSL`: SSL verification (false for corporate environments)

### API Keys Required
- `AHA_API_KEY`: Bearer token for AHA API
- `ICARUS_API_KEY`: API key for Icarus Data Catalog
- `SMARTSHEET_API_KEY`: API key for Smartsheet integration
- `RALLY_API_KEY`: API key for Rally/Jira integration
- `ACCELQ_API_KEY`: API key for AccelQ testing platform

## Troubleshooting

### Common Issues

1. **Image Pull Errors**
   - Ensure the image is properly tagged and pushed to GCR
   - Check GCP IAM permissions for the service account

2. **API Authentication Failures**
   - Verify API keys are properly base64 encoded in secrets
   - Check that Bearer tokens don't have double "Bearer" prefixes

3. **SSL Certificate Issues**
   - Ensure `VERIFY_SSL=false` is set for corporate environments
   - Check network policies for external API access

4. **Port Configuration Issues**
   - Verify the service is exposing port 8080
   - Check that the container port matches the service target port

### Monitoring

```bash
# Check pod logs
kubectl logs -f deployment/forge-projectplan-deployment

# Check service endpoints
kubectl describe service forge-projectplan-service

# Check pod status
kubectl describe pod <pod-name>
```

## Security Considerations

1. **API Keys**: Store all API keys in Kubernetes secrets, never in code
2. **SSL**: Configure appropriate SSL settings for your environment
3. **Network Policies**: Implement appropriate network policies for API access
4. **Resource Limits**: Set appropriate CPU and memory limits in deployment.yml

## Performance Tuning

1. **Replicas**: Adjust replica count based on expected load
2. **Resources**: Tune CPU and memory requests/limits
3. **Timeouts**: Adjust `REQUEST_TIMEOUT` for your network conditions

## Maintenance

1. **Updates**: Update the image tag and redeploy
2. **Scaling**: Use `kubectl scale deployment` for horizontal scaling
3. **Monitoring**: Set up appropriate monitoring and alerting
4. **Backups**: Ensure proper backup procedures for generated project plans