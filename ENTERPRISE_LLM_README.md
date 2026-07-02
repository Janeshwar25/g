# Enterprise LLM Gateway Integration

**Status**: Production-Ready | **Version**: 1.0

## Overview

The Forge AI project has been upgraded from Groq API to the company's **Enterprise LLM Gateway** using OAuth2 Client Credentials authentication.

### What Changed
- ✅ **Inference Provider**: Groq → Enterprise LLM Gateway
- ✅ **Authentication**: API key → OAuth2 Client Credentials
- ✅ **Architecture**: Fully modular, no changes to RAG pipeline or UI
- ✅ **Fallback**: Groq/Azure/OpenAI available as fallbacks

### What Stayed the Same
- ✅ Streamlit UI (unchanged)
- ✅ FastAPI routes (unchanged)
- ✅ RAG pipeline (unchanged)
- ✅ Vector database (unchanged)
- ✅ Chunking/retrieval (unchanged)
- ✅ Prompt building (unchanged)

## Quick Start

### 1. Get Credentials
Contact your IT team for Enterprise Gateway credentials:
```
- LLM_GATEWAY_CLIENT_ID
- LLM_GATEWAY_CLIENT_SECRET  
- LLM_GATEWAY_PROJECT_ID
- LLM_GATEWAY_TOKEN_URL
- LLM_GATEWAY_BASE_URL
```

### 2. Update credentials.env
```bash
# Add these lines to credentials.env
LLM_GATEWAY_CLIENT_ID=your_client_id
LLM_GATEWAY_CLIENT_SECRET=your_client_secret
LLM_GATEWAY_PROJECT_ID=your_project_id
LLM_GATEWAY_TOKEN_URL=https://your-oauth-provider.com/oauth2/token
LLM_GATEWAY_SCOPE=api
LLM_GATEWAY_BASE_URL=https://your-llm-gateway.com/api
LLM_GATEWAY_MODEL_NAME=enterprise-llm
```

### 3. Test Configuration
```bash
python ENTERPRISE_LLM_EXAMPLES.py
```

Expected output:
```
✓ Client initialized successfully
✓ Enterprise LLM Gateway is available
```

## Architecture

```
User Query
    ↓
Streamlit UI (no changes)
    ↓
FastAPI POST /llm (no changes)
    ↓
HelpChatbot.answer() (no changes)
    ↓
RAGService.retrieve() (no changes)
    ↓
Vector Search + Context Building (no changes)
    ↓
LLMManager._provider_order() (UPDATED - Enterprise first)
    ↓
EnterpriseLLMClient (NEW - OAuth2 + token caching)
    ↓
Enterprise LLM Gateway (OAuth2 flow)
    ↓
Response back to user
```

## Provider Selection Order

When a query arrives, LLMManager tries providers in this order:

1. **Enterprise LLM Gateway** (production) ← NEW
2. **Azure OpenAI** (legacy if configured)
3. **OpenAI** (temporary testing)
4. **Groq** (temporary testing)
5. **Gemini** (temporary testing)
6. **LocalFallback** (always available)

Only configured providers are attempted. If Enterprise is configured, it's tried first.

## Core Components

### 1. `agent/enterprise_llm.py`
Main client for enterprise LLM gateway.

**Key Classes:**
- `TokenCache`: Manages OAuth2 tokens with auto-refresh
- `EnterpriseLLMClient`: OAuth2 client + inference wrapper

**Features:**
- OAuth2 client credentials authentication
- Automatic token generation and caching
- Retry logic with exponential backoff
- Request/response logging
- Configurable timeouts and models

**Usage:**
```python
from config import Config
from agent.enterprise_llm import EnterpriseLLMClient

client = EnterpriseLLMClient(Config())
response = client.generate_response(prompt="Your question")
```

### 2. `agent/providers/enterprise_provider.py`
Provider wrapper that integrates with LLMManager.

**Functions:**
- `is_configured(config)`: Check if gateway is properly configured
- `generate_rag_response(messages, config, temperature)`: Generate RAG response

**Usage:**
Automatically used by LLMManager when enterprise config is present.

### 3. `config.py` (updated)
Added enterprise gateway configuration:
```python
LLM_GATEWAY_CLIENT_ID      # OAuth2 client ID
LLM_GATEWAY_CLIENT_SECRET  # OAuth2 client secret
LLM_GATEWAY_PROJECT_ID     # Project ID
LLM_GATEWAY_TOKEN_URL      # OAuth2 token endpoint
LLM_GATEWAY_SCOPE          # OAuth2 scope
LLM_GATEWAY_BASE_URL       # LLM API base URL
LLM_GATEWAY_MODEL_NAME     # Model name
```

### 4. `agent/llm_manager.py` (updated)
Updated provider selection logic:
- Imports enterprise_provider
- Sets enterprise as first priority
- Maintains backward compatibility with testing providers

## Authentication Flow

```
┌─────────────────────────────────────────────────────┐
│ EnterpriseLLMClient Initialization                  │
├─────────────────────────────────────────────────────┤
│ 1. Load env vars (CLIENT_ID, SECRET, TOKEN_URL)    │
│ 2. Validate configuration                          │
│ 3. Initialize TokenCache                           │
└────────────────────┬────────────────────────────────┘
                     │
                     ↓
         ┌───────────────────────┐
         │ First Request Arrives │
         └───────────┬───────────┘
                     │
                     ↓
    ┌────────────────────────────────┐
    │ Generate OAuth2 Access Token   │
    ├────────────────────────────────┤
    │ POST /oauth2/token             │
    │ grant_type=client_credentials  │
    │ client_id=...                  │
    │ client_secret=...              │
    │ scope=api                      │
    └─────────────┬──────────────────┘
                  │
                  ↓
     ┌────────────────────────────┐
     │ Cache Token               │
     │ (expires in 3600 seconds) │
     │ (refresh 5 min early)     │
     └────────────┬───────────────┘
                  │
                  ↓
     ┌────────────────────────────┐
     │ Send Inference Request     │
     ├────────────────────────────┤
     │ POST /inference            │
     │ Authorization: Bearer ...  │
     │ body: prompt, model, ...   │
     └────────────┬───────────────┘
                  │
                  ↓
    ┌─────────────────────────┐
    │ Receive Response        │
    └────────────┬────────────┘
                 │
                 ↓
    ┌─────────────────────────────────────┐
    │ Return Response to Application      │
    └─────────────────────────────────────┘
```

## Error Handling

The client handles common failure scenarios:

| Error | Behavior | Recovery |
|-------|----------|----------|
| Missing config | ValueError | Check credentials.env |
| Invalid credentials | RuntimeError | Verify with IT |
| Token timeout | Retry (1, 2, 4 sec) | Automatic |
| Rate limited (429) | Retry with Retry-After | Automatic |
| Server error (5xx) | Retry with backoff | Automatic |
| Client error (4xx) | RuntimeError | Check request format |
| Network error | Retry with backoff | Automatic |

All errors are logged with `[Enterprise LLM]` prefix for debugging.

## Logging

Enable debug logging to see detailed information:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Key Log Messages:**

| Log Message | Meaning |
|------------|---------|
| `[Enterprise LLM] Client initialized` | Client created successfully |
| `[Enterprise LLM] Generating new access token` | Requesting OAuth2 token |
| `[Enterprise LLM] Token cached` | Token stored for reuse |
| `[Enterprise LLM] Using cached access token` | Reused existing token |
| `[Enterprise LLM] Inference request` | Sending prompt to gateway |
| `[Enterprise LLM] Response received` | Got response from gateway |
| `[LLM] Provider selected: Enterprise LLM Gateway` | LLMManager chose this provider |
| `[Enterprise LLM] Failed after 3 retries` | Giving up, trying next provider |

## Performance

### Token Caching
- **First request**: ~500ms (includes token generation)
- **Subsequent requests**: ~5-10ms per request (cached token)
- **Token lifespan**: Typically 3600 seconds (1 hour)
- **Cache refresh**: 5 minutes before expiry

### Inference
- **Prompt submission**: ~100-200ms
- **Generation**: Depends on gateway (typically 1-10 seconds)
- **Total latency**: Usually 1-15 seconds

### Retry Logic
- **Max retries**: 3 by default
- **Backoff strategy**: Exponential (1s, 2s, 4s)
- **Timeout**: 180 seconds (configurable)

## Configuration Examples

### Development
```bash
REQUEST_TIMEOUT=180
VERIFY_SSL=false  # Corporate proxy
LLM_GATEWAY_CLIENT_ID=dev_client_id
LLM_GATEWAY_CLIENT_SECRET=dev_secret
```

### Production
```bash
REQUEST_TIMEOUT=180
VERIFY_SSL=true   # Verify SSL certificates
LLM_GATEWAY_CLIENT_ID=prod_client_id
LLM_GATEWAY_CLIENT_SECRET=prod_secret
```

### With Groq Fallback
```bash
# Enterprise (primary)
LLM_GATEWAY_CLIENT_ID=...
LLM_GATEWAY_CLIENT_SECRET=...

# Groq (fallback)
GROQ_API_KEY=gsk_...

# System tries Enterprise first, falls back to Groq if needed
```

## Testing

### Unit Tests
```python
from config import Config
from agent.enterprise_llm import EnterpriseLLMClient

client = EnterpriseLLMClient(Config())
assert client.is_available()
```

### Integration Tests
```python
from agent.chatbot import HelpChatbot

bot = HelpChatbot()
result = bot.answer("test question")
assert result['mode'] == 'enterprise'
```

### Manual Tests
```bash
# Run examples
python ENTERPRISE_LLM_EXAMPLES.py

# Test with Streamlit
streamlit run app/app.py
# Navigate to AI Help Bot tab, ask a question

# Check logs for:
# [Enterprise LLM] Response received
# [LLM] Provider selected: Enterprise LLM Gateway
```

## Future: Removing Temporary Providers

Once Enterprise is stable, you can remove testing providers:

### Files to Delete
```bash
rm agent/providers/groq_provider.py
rm agent/providers/openai_provider.py  
rm agent/providers/gemini_provider.py
```

### Code Changes
Edit `agent/llm_manager.py`:
- Remove imports: `groq_provider`, `openai_provider`, `gemini_provider`
- Remove from `_provider_order()`: groq, openai, gemini checks
- Remove from `answer_query()`: groq, openai, gemini cases

### Requirements Changes
Remove from `requirements.txt`:
```
-groq
-google-generativeai
-langchain-openai  # (only if not used elsewhere)
```

### What Doesn't Change
✅ RAG pipeline
✅ Prompt building
✅ Vector store
✅ Streamlit UI
✅ FastAPI routes
✅ Chatbot logic

## Troubleshooting

### "Missing required Enterprise LLM config"
**Cause**: Environment variables not set
**Fix**:
```bash
# Check credentials.env
grep "LLM_GATEWAY_" credentials.env

# Verify all 5 variables are present
# Restart Python process
```

### "Token request failed: 401"
**Cause**: Invalid credentials
**Fix**:
1. Verify CLIENT_ID from IT
2. Verify CLIENT_SECRET from IT  
3. Ensure client is enabled
4. Check token URL is correct

### "Connection failed"
**Cause**: Network unreachable
**Fix**:
```bash
# Test connectivity
curl -v https://your-oauth-provider.com/oauth2/token

# Check firewall rules
# Check corporate proxy settings
```

### Using Groq instead of Enterprise
**Cause**: Enterprise config not set
**Fix**:
```bash
# Verify in credentials.env
echo "CLIENT_ID: ${LLM_GATEWAY_CLIENT_ID}"
echo "Is set: $([ -z "$LLM_GATEWAY_CLIENT_ID" ] && echo 'NO' || echo 'YES')"

# Check logs
# Should show: [LLM] Provider selected: Enterprise LLM Gateway
```

## Security

### Secrets Management
- ✅ Never hardcode credentials
- ✅ Use credentials.env (excluded from git)
- ✅ Use environment variables for secrets
- ✅ Mask tokens in logs
- ✅ Validate SSL in production

### Rate Limiting
- ✅ Built-in retry logic respects Retry-After
- ✅ Exponential backoff prevents overwhelming service
- ✅ Token caching reduces auth overhead
- ✅ Configurable timeout prevents hanging

### Credentials Rotation
When rotating credentials:
1. Get new credentials from IT
2. Update `credentials.env`
3. Restart application
4. Monitor logs for token errors
5. Old credentials expire automatically

## Documentation

- **`ENTERPRISE_LLM_INTEGRATION.md`**: Comprehensive guide
- **`MIGRATION_GROQ_TO_ENTERPRISE.md`**: Step-by-step migration
- **`ENTERPRISE_LLM_EXAMPLES.py`**: 10 usage examples
- **This file**: Overview and quick reference

## Support

For issues:
- **Enterprise Gateway**: Contact IT/DevOps
- **Integration**: See ENTERPRISE_LLM_INTEGRATION.md
- **Migration**: See MIGRATION_GROQ_TO_ENTERPRISE.md
- **Bugs**: Check logs for `[Enterprise LLM]` prefix

## Files Modified/Created

| File | Status | Changes |
|------|--------|---------|
| `agent/enterprise_llm.py` | Created | Main OAuth2 client |
| `agent/providers/enterprise_provider.py` | Created | Provider wrapper |
| `config.py` | Updated | Added LLM_GATEWAY_* vars |
| `env.template` | Updated | Added enterprise section |
| `agent/llm_manager.py` | Updated | Enterprise provider first |
| `ENTERPRISE_LLM_INTEGRATION.md` | Created | Full guide |
| `MIGRATION_GROQ_TO_ENTERPRISE.md` | Created | Migration guide |
| `ENTERPRISE_LLM_EXAMPLES.py` | Created | Usage examples |
| `requirements.txt` | Updated | Added note about requests |

## Version History

- **v1.0** (2026-06-06): Initial production release
  - OAuth2 client credentials auth
  - Token caching with auto-refresh
  - Retry logic with exponential backoff
  - Full integration with RAG pipeline
  - Backward compatible with testing providers

---

**Status**: ✅ Production-Ready | **Last Updated**: 2026-06-06 | **Maintained By**: Development Team
