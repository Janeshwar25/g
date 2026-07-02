"""
MIGRATION GUIDE: Groq → Enterprise LLM Gateway

Step-by-step instructions for migrating from Groq API to Enterprise LLM Gateway.
"""

========================================================================
QUICK START (5 minutes)
========================================================================

1. Get Enterprise Gateway Credentials
   ├─ Request from your IT team:
   │  - Client ID
   │  - Client Secret
   │  - Project ID
   │  - Token URL
   │  - API Base URL
   │  - Scope (usually "api")
   └─ Store securely in a separate file

2. Update credentials.env
   ├─ Open credentials.env
   ├─ Add these lines:
   │  LLM_GATEWAY_CLIENT_ID=<your_client_id>
   │  LLM_GATEWAY_CLIENT_SECRET=<your_client_secret>
   │  LLM_GATEWAY_PROJECT_ID=<your_project_id>
   │  LLM_GATEWAY_TOKEN_URL=<your_token_url>
   │  LLM_GATEWAY_SCOPE=api
   │  LLM_GATEWAY_BASE_URL=<your_api_base_url>
   │  LLM_GATEWAY_MODEL_NAME=enterprise-llm
   └─ Keep REQUEST_TIMEOUT=180 and VERIFY_SSL settings

3. Test the Integration
   ├─ Run: python ENTERPRISE_LLM_EXAMPLES.py
   ├─ Check output for: "✓ Enterprise LLM Gateway is available"
   └─ If successful, skip to "Configuration Complete"

4. Configuration Complete
   ├─ Groq will be bypassed automatically
   ├─ Enterprise LLM is now your primary provider
   └─ Groq can be removed when stable

========================================================================
DETAILED MIGRATION STEPS
========================================================================

PHASE 1: PREPARATION (Before Changes)
──────────────────────────────────────

Step 1.1: Create backup
  $ cp credentials.env credentials.env.backup
  $ cp config.py config.py.backup
  $ cp agent/llm_manager.py agent/llm_manager.py.backup

Step 1.2: Request enterprise gateway credentials
  Email IT with:
  - Project name: Forge AI Help Bot
  - Required scopes: api, read, write (or minimal needed)
  - Callback URL: N/A (server-to-server, not web OAuth)
  - Keep credentials in secure location (not in email)

Step 1.3: Gather information
  Obtain from IT/DevOps:
  ✓ OAuth2 Token Endpoint URL
  ✓ LLM API Base URL
  ✓ Client ID
  ✓ Client Secret
  ✓ Project ID
  ✓ API Scope name
  ✓ Any network/firewall requirements


PHASE 2: CODE INTEGRATION (New Files Already Added)
───────────────────────────────────────────────────

These files are already created:
  ✓ agent/enterprise_llm.py      (OAuth2 client + token caching)
  ✓ agent/providers/enterprise_provider.py (Provider wrapper)
  ✓ config.py (updated)          (Enterprise config vars)
  ✓ env.template (updated)       (Enterprise env example)
  ✓ agent/llm_manager.py (updated) (Enterprise provider chain)

No code changes needed - just configuration!


PHASE 3: CONFIGURATION (Your Action Required)
──────────────────────────────────────────────

Step 3.1: Update credentials.env
  
  Before:
    GROQ_API_KEY=gsk_xxxxxxxxxxxxx
    REQUEST_TIMEOUT=180
    VERIFY_SSL=false

  After:
    # Keep existing configs
    GROQ_API_KEY=gsk_xxxxxxxxxxxxx  (optional, keep as fallback)
    REQUEST_TIMEOUT=180
    VERIFY_SSL=false  (true if in production)
    
    # Add new configs
    LLM_GATEWAY_CLIENT_ID=your_client_id
    LLM_GATEWAY_CLIENT_SECRET=your_client_secret
    LLM_GATEWAY_PROJECT_ID=your_project_id
    LLM_GATEWAY_TOKEN_URL=https://your-oauth-provider.com/oauth2/token
    LLM_GATEWAY_SCOPE=api
    LLM_GATEWAY_BASE_URL=https://your-llm-gateway.com/api
    LLM_GATEWAY_MODEL_NAME=enterprise-llm

Step 3.2: Verify configuration
  $ python -c "from config import Config; c = Config(); print('✓ Loaded' if c.LLM_GATEWAY_CLIENT_ID else '✗ Missing')"

Step 3.3: Test provider selection
  $ python ENTERPRISE_LLM_EXAMPLES.py
  
  Expected output:
    EXAMPLE 1: Initialization and Configuration Check
    ✓ Client initialized successfully
    ✓ Enterprise LLM Gateway is available


PHASE 4: TESTING (Validation)
─────────────────────────────

Step 4.1: Unit test
  $ python -c "
from config import Config
from agent.enterprise_llm import EnterpriseLLMClient
client = EnterpriseLLMClient(Config())
print('✓ Client created')
print('✓ Available' if client.is_available() else '✗ Not available')
  "

Step 4.2: Integration test
  $ python -c "
from config import Config
from agent.chatbot import HelpChatbot
bot = HelpChatbot(Config())
result = bot.answer('test question')
print('Response:', result['response'][:100])
print('Mode:', result['mode'])
  "

Step 4.3: Full E2E test
  1. Start FastAPI: python app/routes.py
  2. Start Streamlit: streamlit run app/app.py
  3. Navigate to AI Help Bot tab
  4. Ask a question
  5. Verify response appears and "mode" in logs shows "enterprise"

Step 4.4: Check logs
  Watch for:
  ✓ [Enterprise LLM] Client initialized
  ✓ [Enterprise LLM] Generating new access token
  ✓ [Enterprise LLM] Response received
  ✓ [LLM] Provider selected: Enterprise LLM Gateway
  
  NOT seeing these = check credentials.env


PHASE 5: FALLBACK CONFIGURATION
───────────────────────────────

The system automatically falls back if Enterprise fails:

Provider Order (automatic):
  1. Enterprise LLM Gateway (NEW)
  2. Azure OpenAI (if configured)
  3. OpenAI (if configured, testing)
  4. Groq (if configured, testing)
  5. Gemini (if configured, testing)
  6. LocalFallback (always available)

To keep Groq as fallback:
  ✓ Keep GROQ_API_KEY in credentials.env
  ✓ System will use Enterprise, fall back to Groq if needed

To disable Groq fallback:
  ✓ Remove GROQ_API_KEY from credentials.env
  ✓ Groq won't be attempted
  ✓ Only Azure/Enterprise/LocalFallback available


PHASE 6: MONITORING (After Deployment)
──────────────────────────────────────

Enable detailed logging:
  import logging
  logging.basicConfig(level=logging.DEBUG)

Watch for errors:
  ✗ [Enterprise LLM] Configuration error → Check credentials.env
  ✗ [Enterprise LLM] Token request failed → Check client ID/secret
  ✗ [Enterprise LLM] Connection error → Check firewall/network
  ✗ [Enterprise LLM] Rate limited → Contact gateway admin

Metrics to monitor:
  • Token generation latency (should be <1s with cache)
  • Inference latency (depends on prompt size)
  • Success rate (track failures to fallback)
  • Rate limit hits (429 errors)


PHASE 7: OPTIMIZATION (Optional, After Stable)
──────────────────────────────────────────────

Once Enterprise LLM is stable and primary:

Option A: Keep Groq as fallback
  ✓ No action needed
  ✓ System handles automatically
  ✓ Removes single point of failure

Option B: Remove Groq (production-only)
  Step 1: Delete groq_provider.py
  Step 2: Remove Groq import from llm_manager.py
  Step 3: Remove Groq from _provider_order()
  Step 4: Remove "groq" case from answer_query()
  Step 5: Remove from requirements.txt (groq package)
  
  Does NOT require changing:
  ✗ chatbot.py
  ✗ rag_service.py
  ✗ prompt_builder.py
  ✗ Streamlit UI
  ✗ FastAPI routes


========================================================================
TROUBLESHOOTING
========================================================================

Problem: "Missing required Enterprise LLM config"
─────────────────────────────────────────────────
Cause: env vars not set
Fix:
  1. Check credentials.env exists
  2. Verify all LLM_GATEWAY_* vars are present
  3. Restart Python process to reload env
  4. Run: python -c "from config import Config; print(Config().LLM_GATEWAY_CLIENT_ID)"

Problem: "Token request failed: 401 - Unauthorized"
────────────────────────────────────────────────────
Cause: Wrong credentials
Fix:
  1. Double-check CLIENT_ID from IT
  2. Double-check CLIENT_SECRET from IT
  3. Verify token URL is correct
  4. Ensure client is activated in OAuth provider
  5. Check if credentials were rotated

Problem: "Token request timed out"
──────────────────────────────────
Cause: Network issue
Fix:
  1. Test connectivity: curl -v https://your-token-url
  2. Check firewall rules
  3. Check corporate proxy settings
  4. Increase REQUEST_TIMEOUT to 300
  5. Check if OAuth provider is down

Problem: "LLM request failed: 429 - Rate Limited"
──────────────────────────────────────────────────
Cause: Hit rate limit quota
Fix:
  1. Wait 60+ seconds (client retries automatically)
  2. Check rate limit quota with gateway admin
  3. Reduce concurrent requests if possible
  4. Request quota increase for peak hours

Problem: "LLM response missing 'response' field"
─────────────────────────────────────────────────
Cause: Response format changed
Fix:
  1. Check gateway API response format
  2. May be 'text' or 'output' instead of 'response'
  3. Edit agent/enterprise_llm.py _send_request() method
  4. Change: result = data.get("response") or data.get("text")

Problem: Using Groq instead of Enterprise
─────────────────────────────────────────
Cause: Enterprise config missing or Groq configured
Fix:
  1. Check logs show "Provider selected: Enterprise LLM Gateway"
  2. Verify LLM_GATEWAY_CLIENT_ID is set
  3. Remove GROQ_API_KEY temporarily to test
  4. Run: python -c "from agent.llm_manager import LLMManager; from config import Config; print(LLMManager(Config())._provider_order())"


========================================================================
ROLLBACK PROCEDURE (If Needed)
========================================================================

If Enterprise LLM has issues and you need to rollback to Groq:

Quick Rollback (5 minutes):
  1. Remove LLM_GATEWAY_* from credentials.env
  2. Ensure GROQ_API_KEY is still present
  3. Restart application
  4. Logs will show "Provider selected: Groq"

Full Rollback:
  $ cp config.py.backup config.py
  $ cp credentials.env.backup credentials.env
  $ cp agent/llm_manager.py.backup agent/llm_manager.py
  $ python app/routes.py  # Restart

Then contact support for Enterprise LLM issues.


========================================================================
ARCHITECTURE DIAGRAM: Migration Path
========================================================================

BEFORE (Groq):
┌─────────────┐
│ Streamlit   │
└──────┬──────┘
       │
┌──────▼──────────────────┐
│ FastAPI /llm endpoint    │
└──────┬───────────────────┘
       │
┌──────▼──────────────────┐
│ HelpChatbot (RAG)        │
└──────┬───────────────────┘
       │
┌──────▼──────────────────┐
│ LLMManager               │
└──────┬───────────────────┘
       │ selects
       │
    ┌──┴────────────────┬────────────┬────────────┐
    ▼                   ▼            ▼            ▼
  Groq ────────── [Fallback Chain]
                  OpenAI, Azure
                  LocalFallback


AFTER (Enterprise + Groq fallback):
┌─────────────┐
│ Streamlit   │
└──────┬──────┘
       │
┌──────▼──────────────────┐
│ FastAPI /llm endpoint    │
└──────┬───────────────────┘
       │
┌──────▼──────────────────┐
│ HelpChatbot (RAG)        │
└──────┬───────────────────┘
       │
┌──────▼──────────────────┐
│ LLMManager               │
└──────┬───────────────────┘
       │ selects (in order)
       │
    ┌──┴──────────────────┬───────────┬────────────┬────────────┐
    ▼                     ▼           ▼            ▼            ▼
Enterprise ────────── Azure ────── OpenAI ────── Groq ─── LocalFallback
(OAuth2)              (legacy)   (testing)   (testing)    (always)
(NEW)


========================================================================
TIMELINE AND MILESTONES
========================================================================

T+0 hours: Configuration Phase
├─ Get enterprise gateway credentials from IT
├─ Update credentials.env
└─ Run test: python ENTERPRISE_LLM_EXAMPLES.py

T+1 hour: Integration Testing
├─ Test with python -c "..." command
├─ Test with Streamlit UI
└─ Monitor logs for errors

T+4 hours: Fallback Testing
├─ Verify Groq still works as fallback
├─ Test failure scenarios
└─ Document any issues

T+1 day: Production Deployment
├─ Deploy to production environment
├─ Monitor [Enterprise LLM] logs
├─ Have rollback plan ready
└─ Notify team of change

T+7 days: Optimization
├─ Review logs for patterns
├─ Adjust timeout if needed
├─ Monitor rate limiting
└─ Consider removing Groq if stable

T+30 days: Production-Ready
├─ Groq can be removed if desired
├─ Enterprise LLM fully production
└─ Full team trained on new system


========================================================================
SUPPORT CONTACTS
========================================================================

For different issues, contact:

Enterprise LLM Gateway Issues:
  → IT/DevOps team or your LLM platform admin
  → Provide: error message, time, logs

Integration Issues:
  → Development team
  → Provide: credentials.env config (masked), logs with [Enterprise LLM]

Fallback/Groq Issues:
  → Development team (temporary, can be removed)

Network/Firewall Issues:
  → IT Security team
  → Your gateway URL and ports needed


========================================================================
SUCCESS CRITERIA
========================================================================

Migration is successful when:
  ✓ python ENTERPRISE_LLM_EXAMPLES.py shows "Available"
  ✓ Streamlit UI responds to questions
  ✓ Logs show "Provider selected: Enterprise LLM Gateway"
  ✓ Logs show "RAG response generated"
  ✓ No errors related to authentication
  ✓ Fallback providers work if Enterprise fails
  ✓ Performance is acceptable (latency <5s typical)

Migration is complete when:
  ✓ Groq fallback option removed (optional)
  ✓ All team trained on new system
  ✓ Monitoring/alerts configured
  ✓ Documentation updated
  ✓ Old Groq config removed from codebase


========================================================================
"""
