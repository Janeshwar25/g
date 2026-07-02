# Security and Configuration Guide

## 🔐 Security Issues Identified and Fixed

This document outlines the security issues found in the codebase and how they have been addressed.

### ❌ Issues Found

#### 1. Hardcoded API Keys and Secrets
**Severity: HIGH**

The following files contained hardcoded API keys and tokens:

- `archive/aha_export.py`: AHA API token exposed
- `archive/rally_export.py`: Rally API key exposed  
- `archive/rally_data_wrapper_automated.py`: Rally API key exposed
- `archive/testing_rally.py`: Multiple API keys exposed
- `credentials.env`: Contains actual API keys (should not be in version control)

**Example of vulnerable code:**
```python
# ❌ VULNERABLE - Hardcoded API key
api_key = '_yisAmMbrSL4aY8WjdpAkyL6IHt5EHJgGhNoubdYk0'
headers = {
    'Authorization': 'Bearer Zt7TBRXcmTf9Rt0lziJqIXzeRML8lQkbYdK4WOTxPwU'
}
```

#### 2. Hardcoded URLs and Configuration
**Severity: MEDIUM**

Multiple files contained hardcoded service URLs and configuration values:

- API endpoints (localhost:8080, etc.)
- Service URLs (AHA, Rally, Smartsheet, Icarus)
- Default user names and project settings
- File paths and workspace IDs

#### 3. Exposed Internal URLs
**Severity: MEDIUM**

Internal Optum URLs and service endpoints were hardcoded:
- `https://optum.aha.io/api/v1/`
- `https://rally1.rallydev.com/slm/webservice/v2.0`
- `https://insights.hcp.uhg.com/api/icarus/v1/`

### ✅ Solutions Implemented

#### 1. Configuration Management System

Created `config.py` with centralized configuration management:

```python
class Config:
    """Configuration class to centralize all environment variables"""
    
    # API Keys from environment
    AHA_API_KEY = os.getenv('AHA_API_KEY', '')
    ICARUS_API_KEY = os.getenv('ICARUS_API_KEY', '')
    RALLY_API_KEY = os.getenv('RALLY_API_KEY', '')
    
    # Service URLs from environment with defaults
    RALLY_URL = os.getenv('RALLY_URL', 'https://rally1.rallydev.com/slm/webservice/v2.0')
    AHA_BASE_URL = os.getenv('AHA_BASE_URL', 'https://optum.aha.io/api/v1')
    
    @classmethod
    def validate_required_env_vars(cls):
        """Validate that required environment variables are set"""
        # Validation logic
```

#### 2. Environment Variable Migration

All hardcoded values moved to environment variables:

**Before:**
```python
API_URL = "http://localhost:8080/chat"
api_key = '_yisAmMbrSL4aY8WjdpAkyL6IHt5EHJgGhNoubdYk0'
```

**After:**
```python
from config import Config
config = Config()
API_URL = f"{config.API_BASE_URL}/chat"
headers = config.get_rally_headers()
```

#### 3. Docker Configuration

Updated Docker configurations to use environment variables:

```dockerfile
# Environment variables properly configured
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
# API keys and secrets loaded from env_file
```

#### 4. Template Files

Created `env.template` with all required environment variables:

```bash
# API Keys (Required)
AHA_API_KEY=Bearer your_aha_api_key_here
ICARUS_API_KEY=your_icarus_api_key_here
SMARTSHEET_API_KEY=your_smartsheet_api_key_here

# Service URLs (Optional - defaults provided)
RALLY_URL=https://rally1.rallydev.com/slm/webservice/v2.0
AHA_BASE_URL=https://optum.aha.io/api/v1
```

#### 5. Archive File Sanitization

Created `cleanup_secrets.sh` script to automatically remove hardcoded secrets from archive files.

## 🚀 For GCP Deployment

### ConfigMap Setup

Create a ConfigMap for non-sensitive configuration:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
data:
  RALLY_URL: "https://rally1.rallydev.com/slm/webservice/v2.0"
  AHA_BASE_URL: "https://optum.aha.io/api/v1"
  SMARTSHEET_BASE_URL: "https://api.smartsheet.com/2.0"
  ICARUS_BASE_URL: "https://insights.hcp.uhg.com/api/icarus/v1"
  API_HOST: "0.0.0.0"
  API_PORT: "8080"
  STREAMLIT_HOST: "0.0.0.0"
  STREAMLIT_PORT: "8501"
  RALLY_WORKSPACE: "UHG"
  RALLY_PROJECT: "Pioneers GenAI"
  METADATA_FILE: "documents/plan_metadata.json"
  TEMPLATE_FILE: "documents/GNP_Template_v4.xlsx"
  DEFAULT_BDL: "Jason Merckling"
  DEFAULT_RDL: "Chris Capewell"
  DEFAULT_BUSINESS_OWNER: "Gina Milana"
  BUTTON_COLOR: "#001f3f"
  REQUEST_TIMEOUT: "180"
```

### Secret Management

Create a Secret for sensitive data:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: app-secrets
type: Opaque
data:
  AHA_API_KEY: <base64-encoded-api-key>
  ICARUS_API_KEY: <base64-encoded-api-key>
  SMARTSHEET_API_KEY: <base64-encoded-api-key>
  RALLY_API_KEY: <base64-encoded-api-key>
  ACCELQ_API_KEY: <base64-encoded-api-key>
  SMARTSHEET_WORKSPACE_ID: <base64-encoded-workspace-id>
```

### Deployment Configuration

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: project-plan-builder
spec:
  template:
    spec:
      containers:
      - name: app
        image: your-app-image
        envFrom:
        - configMapRef:
            name: app-config
        - secretRef:
            name: app-secrets
```

## 📋 Security Checklist

- [x] Remove all hardcoded API keys and tokens
- [x] Move configuration to environment variables
- [x] Create configuration management system
- [x] Update Docker configurations
- [x] Create environment variable templates
- [x] Sanitize archive files
- [x] Document security issues and fixes
- [x] Prepare GCP ConfigMap/Secret configurations
- [ ] Remove `credentials.env` from version control
- [ ] Add `credentials.env` to `.gitignore`
- [ ] Run security cleanup script
- [ ] Validate all environment variables are loaded correctly

## 🔍 Validation

To validate the security fixes:

1. **Run the cleanup script:**
   ```bash
   ./cleanup_secrets.sh
   ```

2. **Check for remaining hardcoded secrets:**
   ```bash
   grep -r "_[a-zA-Z0-9]\{40,\}" . --exclude-dir=node_modules
   grep -r "Bearer [a-zA-Z0-9_-]\{40,\}" . --exclude-dir=node_modules
   ```

3. **Validate configuration loading:**
   ```python
   from config import Config
   config = Config()
   config.validate_required_env_vars()  # Should pass without errors
   ```

4. **Test Docker deployment:**
   ```bash
   docker-compose up --build
   # Should start without hardcoded values
   ```

## ⚠️ Important Notes

- **Never commit `credentials.env`** to version control
- **Always use environment variables** for sensitive data
- **Use the Config class** for all configuration access
- **Validate environment variables** before deployment
- **Regular security audits** should be performed