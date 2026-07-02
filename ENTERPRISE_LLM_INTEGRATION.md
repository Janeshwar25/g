"""
ENTERPRISE LLM GATEWAY INTEGRATION GUIDE

This guide explains how the Forge AI project has been upgraded to use
the company's Enterprise LLM Gateway instead of Groq API.

========================================================================
ARCHITECTURE OVERVIEW
========================================================================

Before (Groq-only):
  Streamlit UI → FastAPI → RAG Pipeline → Groq API → Response

After (Enterprise Gateway):
  Streamlit UI → FastAPI → RAG Pipeline → Enterprise Gateway → Response

The integration maintains:
  ✓ Existing RAG pipeline unchanged
  ✓ Vector database unchanged
  ✓ Retrieval logic unchanged
  ✓ Prompt structure unchanged
  ✓ Only inference provider replaced

========================================================================
CONFIGURATION
========================================================================

1. Update your credentials.env file with Enterprise Gateway credentials:

    LLM_GATEWAY_CLIENT_ID=your_client_id
    LLM_GATEWAY_CLIENT_SECRET=your_client_secret
    LLM_GATEWAY_PROJECT_ID=your_project_id
    LLM_GATEWAY_TOKEN_URL=https://your-oauth-provider.com/oauth2/token
    LLM_GATEWAY_SCOPE=api
    LLM_GATEWAY_BASE_URL=https://your-llm-gateway.com/api
    LLM_GATEWAY_MODEL_NAME=enterprise-llm

2. Ensure REQUEST_TIMEOUT and VERIFY_SSL are set appropriately:

    REQUEST_TIMEOUT=180
    VERIFY_SSL=false (for corporate proxies)

========================================================================
MAIN COMPONENTS
========================================================================

1. agent/enterprise_llm.py
   - EnterpriseLLMClient: Main OAuth2 client for gateway communication
   - TokenCache: Automatic token caching with expiry handling
   - Features:
     * OAuth2 client credentials authentication
     * Automatic token refresh
     * Retry logic with exponential backoff
     * Request/response logging
     * Configurable timeouts

2. agent/providers/enterprise_provider.py
   - Production provider module that integrates with LLMManager
   - Wraps EnterpriseLLMClient for RAG use
   - Can be registered in llm_manager.py

3. config.py
   - LLM_GATEWAY_* settings loaded from environment
   - Validated by EnterpriseLLMClient initialization

========================================================================
HOW IT WORKS
========================================================================

Step 1: User asks a question in Streamlit
Step 2: FastAPI /llm endpoint receives query
Step 3: RAG pipeline retrieves relevant context
Step 4: LLMManager selects Enterprise provider (if configured)
Step 5: Enterprise provider creates EnterpriseLLMClient
Step 6: Client authenticates using OAuth2 client credentials
Step 7: Client sends prompt + context to gateway
Step 8: Gateway returns generated response
Step 9: Response is sent back to user

========================================================================
AUTHENTICATION FLOW
========================================================================

OAuth2 Client Credentials (RFC 6749):

1. Client sends:
   POST /oauth2/token HTTP/1.1
   Content-Type: application/x-www-form-urlencoded

   grant_type=client_credentials
   &client_id=YOUR_CLIENT_ID
   &client_secret=YOUR_CLIENT_SECRET
   &scope=api

2. Authorization server returns:
   {
     "access_token": "eyJhbGciOiJIUzI1NiIsInR...",
     "expires_in": 3600,
     "token_type": "Bearer"
   }

3. Client caches token and uses for subsequent requests:
   GET /inference HTTP/1.1
   Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR...

TokenCache automatically:
  - Caches tokens until 5 minutes before expiry
  - Refreshes when needed
  - Handles concurrent requests safely

========================================================================
INFERENCE REQUEST
========================================================================

The client sends structured requests:

POST /inference HTTP/1.1
Authorization: Bearer <token>
Content-Type: application/json

{
  "model": "enterprise-llm",
  "prompt": "SYSTEM: You are a helpful assistant...\n\nUSER: What is the project status?",
  "max_tokens": 2048,
  "temperature": 0.1,
  "top_p": 0.95,
  "project_id": "your_project_id"
}

Gateway returns:
{
  "response": "Based on the provided context...",
  "tokens_used": 523,
  "model": "enterprise-llm"
}

========================================================================
RETRY LOGIC
========================================================================

The client implements exponential backoff:

Attempt 1: Immediate
Attempt 2: Wait 1 second
Attempt 3: Wait 2 seconds
(max 3 attempts by default)

Retried on:
  - 429 (Rate Limited) - waits for Retry-After header
  - 5xx (Server errors)
  - Connection errors
  - Timeouts

Not retried:
  - 4xx errors (except 429)
  - Configuration errors
  - Authentication failures

========================================================================
ERROR HANDLING
========================================================================

Enterprise LLMClient handles:

1. Configuration Errors
   - Missing required env vars → raises ValueError
   - Invalid credentials → handled during auth attempt

2. Network Errors
   - Timeout → retry with exponential backoff
   - Connection error → retry with exponential backoff
   - DNS failure → retried up to max_retries

3. Authentication Errors
   - Invalid credentials → RuntimeError (no retry)
   - Token generation failure → RuntimeError (no retry)
   - 401 Unauthorized → RuntimeError (no retry)

4. Service Errors
   - 429 Rate limit → retry with Retry-After
   - 5xx Server error → retry with exponential backoff
   - 400 Bad request → RuntimeError (no retry)

All errors are logged with [Enterprise LLM] prefix for easy debugging.

========================================================================
PROVIDER PRIORITY
========================================================================

The LLMManager tries providers in this order:

1. Enterprise LLM Gateway (production)
2. Azure OpenAI (legacy)
3. OpenAI (temporary testing)
4. Groq (temporary testing)
5. Gemini (temporary testing)
6. Local Fallback (always available)

To use Enterprise:
  ✓ Configure all LLM_GATEWAY_* env vars

To skip and use Azure:
  - Don't set LLM_GATEWAY_CLIENT_ID (it will be empty)
  - Keep Azure config

To use testing providers:
  - Don't configure Enterprise or Azure
  - Configure testing provider (GROQ_API_KEY, OPENAI_API_KEY, etc)

========================================================================
REMOVING TEMPORARY PROVIDERS
========================================================================

Once Enterprise is stable, remove Groq/OpenAI/Gemini:

1. Delete files:
   - agent/providers/groq_provider.py
   - agent/providers/openai_provider.py
   - agent/providers/gemini_provider.py

2. Update agent/llm_manager.py:
   - Remove imports: groq_provider, openai_provider, gemini_provider
   - Remove from _provider_order() checks for groq, openai, gemini
   - Remove from answer_query() blocks for these providers

3. Update requirements.txt:
   - Remove: groq, google-generativeai, langchain-openai
   - Keep: requests, langchain, langchain-core

4. This does NOT require changing:
   - chatbot.py
   - rag_service.py
   - prompt_builder.py
   - retrieval pipeline
   - vector store
   - Streamlit UI
   - FastAPI routes

========================================================================
LOGGING AND DEBUGGING
========================================================================

Enable debug logging in your application:

import logging
logging.basicConfig(level=logging.DEBUG)

Watch for these logs:

[Enterprise LLM] Client initialized
[Enterprise LLM] Generating new access token
[Enterprise LLM] Token cached (expires in 3600 seconds)
[Enterprise LLM] Using cached access token
[Enterprise LLM] Inference request (attempt 1/3, prompt_len=5234)
[Enterprise LLM] Response received (1245 chars)
[LLM] Provider selected: Enterprise LLM Gateway
[LLM] RAG response generated (1245 chars)

For troubleshooting:

1. Check credentials.env is loaded:
   python -c "from config import Config; c = Config(); print(c.LLM_GATEWAY_CLIENT_ID)"

2. Test token generation directly:
   from agent.enterprise_llm import EnterpriseLLMClient
   client = EnterpriseLLMClient(Config())
   print(client.is_available())

3. Check network connectivity:
   curl -v https://your-oauth-provider.com/oauth2/token

========================================================================
EXAMPLE USAGE
========================================================================

# Direct usage
from config import Config
from agent.enterprise_llm import EnterpriseLLMClient

config = Config()
client = EnterpriseLLMClient(config)

# Single prompt
response = client.generate_response(
    prompt="What is the project status?"
)
print(response)

# With RAG context and messages
from langchain_core.messages import SystemMessage, HumanMessage

messages = [
    SystemMessage(content="You are a helpful assistant."),
    HumanMessage(content="Based on the context: ..., answer: what is the status?")
]
response = client.generate_response(messages=messages)
print(response)

# Via RAG pipeline (automatic)
from agent.chatbot import HelpChatbot

bot = HelpChatbot(config)
result = bot.answer("What is the project status?")
print(result["response"])

========================================================================
PERFORMANCE CONSIDERATIONS
========================================================================

Token Caching:
  - Reduces authentication overhead
  - Tokens cached for full validity period (minus 5-min buffer)
  - Concurrent requests reuse same token

Retry Logic:
  - Improves reliability for transient failures
  - Exponential backoff prevents overwhelming the service
  - Max 3 retries by default (configurable)

Request Timeouts:
  - Default 180 seconds (3 minutes)
  - Configurable via REQUEST_TIMEOUT env var
  - Prevents hanging on network issues

Prompt Size:
  - Monitor prompt_len in logs
  - Max tokens: 2048 (configurable in _build_inference_payload)
  - Larger prompts may incur higher latency

========================================================================
SECURITY BEST PRACTICES
========================================================================

1. Credentials Management
   ✓ Use credentials.env for sensitive values
   ✓ Never commit credentials.env to git
   ✓ Rotate client secrets regularly
   ✓ Use different secrets for dev/staging/prod

2. SSL/TLS
   ✓ Set VERIFY_SSL=true in production
   ✓ For corporate proxies: VERIFY_SSL=false (with caution)
   ✓ Ensure SSL certificates are valid

3. Logging
   ✓ Tokens are never logged (masked)
   ✓ Client secrets are never logged
   ✓ Error messages mask sensitive data
   ✓ Debug logs include [Enterprise LLM] prefix for filtering

4. Scope and Permissions
   ✓ Use minimal scope (e.g., 'api' not 'admin')
   ✓ Limit token lifetime (expires_in: 3600)
   ✓ Implement rate limiting awareness

========================================================================
TROUBLESHOOTING
========================================================================

Problem: "Missing required Enterprise LLM config"
Solution:
  - Check credentials.env has all LLM_GATEWAY_* vars
  - Ensure they are not empty strings
  - Verify env vars are loaded: python -c "from config import Config; ..."

Problem: "Token request failed: 401 - Unauthorized"
Solution:
  - Verify CLIENT_ID and CLIENT_SECRET are correct
  - Check token endpoint URL is correct
  - Ensure client has permission to request tokens

Problem: "Token request timed out"
Solution:
  - Increase REQUEST_TIMEOUT
  - Check network connectivity to token endpoint
  - Check firewall/proxy settings

Problem: "LLM request failed: 429 - Rate Limited"
Solution:
  - Client retries automatically
  - Reduce concurrent requests
  - Contact gateway administrator for rate limit increase

Problem: "Connection failed: ... Connection refused"
Solution:
  - Check LLM_GATEWAY_BASE_URL is correct
  - Verify service is running
  - Check network connectivity
  - Check firewall/proxy settings

Problem: "Response missing 'response' field"
Solution:
  - Check gateway API response format
  - May be 'text' or 'output' instead of 'response'
  - Update _send_request() response parsing if needed

========================================================================
SUPPORT AND FEEDBACK
========================================================================

For issues with:
- Enterprise Gateway: Contact your IT/DevOps team
- Integration: Check this guide and logs
- Bugs: File issues with [Enterprise LLM] logs included
- Feature requests: Submit to development team

========================================================================
"""
