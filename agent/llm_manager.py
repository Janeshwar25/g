"""
🔒 ENTERPRISE-ONLY LLM MANAGER 🔒

STRICT ENTERPRISE INFERENCE MODE

This manager enforces enterprise-only LLM inference via OAuth2 authentication.
No fallback providers. No legacy integrations. No public LLMs.

ONLY the company's Enterprise LLM Gateway is used.

All requests MUST authenticate with:
  - LLM_GATEWAY_CLIENT_ID
  - LLM_GATEWAY_CLIENT_SECRET
  - LLM_GATEWAY_TOKEN_URL
  - LLM_GATEWAY_BASE_URL

CRITICAL REQUIREMENTS:
  ✓ OAuth2 authentication mandatory
  ✓ Hard failure if credentials missing
  ✓ No provider fallback logic
  ✓ No automatic switching
  ✓ No legacy provider support
  ✓ Enterprise gateway ONLY

Only the enterprise gateway provider is available in this runtime.
"""

import logging
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage

from config import Config
from agent.providers import enterprise_provider

logger = logging.getLogger(__name__)

class LLMManager:
    """
    🔒 Enterprise-Only LLM Manager
    
    Enforces strict enterprise-only inference via OAuth2 Client Credentials.
    No fallback. No alternatives. Enterprise gateway only.
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        
        # 🔒 CRITICAL: Validate enterprise credentials on startup
        self._validate_enterprise_credentials()
        
        logger.info("🔒 ENTERPRISE-ONLY MODE ACTIVE")
        logger.info("✅ Enterprise LLM Gateway is REQUIRED and CONFIGURED")

    def _validate_enterprise_credentials(self) -> None:
        """
        🔒 Validate that enterprise credentials are present.
        
        HARD FAIL if any required credential is missing.
        No fallback. No alternatives. Must have enterprise authentication.
        
        Raises:
            ValueError: If any required enterprise credential is missing
        """
        required_fields = {
            "CLIENT_ID": self.config.LLM_GATEWAY_CLIENT_ID,
            "CLIENT_SECRET": self.config.LLM_GATEWAY_CLIENT_SECRET,
            "PROJECT_ID": self.config.LLM_GATEWAY_PROJECT_ID,
            "TOKEN_URL": self.config.LLM_GATEWAY_TOKEN_URL,
            "BASE_URL": self.config.LLM_GATEWAY_BASE_URL,
            "REASONING_BASE_URL": getattr(self.config, "LLM_GATEWAY_REASONING_BASE_URL", ""),
            "API_VERSION": getattr(self.config, "LLM_GATEWAY_API_VERSION", ""),
        }
        
        missing = [k for k, v in required_fields.items() if not v or not str(v).strip()]
        
        if missing:
            error_msg = (
                f"🔴 ENTERPRISE AUTHENTICATION FAILED 🔴\n"
                f"Missing required LLM_GATEWAY_* credentials:\n"
                f"  {', '.join(missing)}\n"
                f"\nSTRICT ENTERPRISE-ONLY MODE REQUIRES:\n"
                f"  ✓ LLM_GATEWAY_CLIENT_ID\n"
                f"  ✓ LLM_GATEWAY_CLIENT_SECRET\n"
                f"  ✓ LLM_GATEWAY_PROJECT_ID\n"
                f"  ✓ LLM_GATEWAY_TOKEN_URL\n"
                f"  ✓ LLM_GATEWAY_BASE_URL\n"
                f"  ✓ LLM_GATEWAY_REASONING_BASE_URL\n"
                f"  ✓ LLM_GATEWAY_API_VERSION\n"
                f"\nNo fallback providers available.\n"
                f"No public LLMs allowed.\n"
                f"Enterprise gateway authentication is MANDATORY.\n"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

    def answer_query(
        self,
        query: str,
        messages: List[BaseMessage],
        rag_context: str,
        sources_used: List[str],
        is_reasoning: bool = False,
    ) -> Dict[str, Any]:
        """
        🔒 ENTERPRISE-ONLY INFERENCE
        
        Routes query to company's Enterprise LLM Gateway ONLY.
        No fallback. No alternatives. OAuth2 authentication required.
        
        HARD FAILS if:
          - Credentials missing
          - Token generation fails
          - Gateway unreachable
          - Authentication rejected
        
        Args:
            query: Original user query
            messages: LangChain message objects (system + context + query)
            rag_context: Retrieved context from vector DB
            sources_used: List of source documents
        
        Returns:
            Dictionary with:
              - response: Generated text from enterprise gateway
              - sources_used: List of sources
              - mode: "enterprise" (always)
        
        Raises:
            RuntimeError: If enterprise gateway fails (no fallback)
            ValueError: If credentials missing (detected in __init__)
        """
        
        logger.info("🚀 ENTERPRISE LLM GATEWAY REQUEST")
        logger.info(f"   Query length: {len(query)} chars")
        logger.info(f"   RAG context: {len(rag_context)} chars")
        logger.info(f"   Sources: {sources_used}")
        
        try:
            # 🔒 ENTERPRISE GATEWAY ONLY
            logger.info("🔐 Authenticating with Enterprise LLM Gateway...")
            
            content = enterprise_provider.generate_rag_response(
                messages,
                config=self.config,
                temperature=0.1,
                is_reasoning=is_reasoning
            )
            
            logger.info("✅ Enterprise LLM Gateway response received")
            logger.info(f"   Response length: {len(content)} chars")
            logger.info("🔒 ENTERPRISE INFERENCE COMPLETE")
            
            return {
                "response": content,
                "sources_used": sources_used,
                "mode": "enterprise"
            }
        
        except Exception as e:
            # 🔴 HARD FAIL - No fallback
            error_msg = (
                f"🔴 ENTERPRISE LLM GATEWAY FAILED 🔴\n"
                f"Error: {str(e)}\n"
                f"\nSTRICT ENTERPRISE-ONLY MODE:\n"
                f"  ✗ No fallback providers available\n"
                f"  ✗ No public LLMs allowed\n"
                f"  ✗ No automatic switching\n"
                f"\nACTION REQUIRED:\n"
                f"  1. Check enterprise gateway connectivity\n"
                f"  2. Verify OAuth2 credentials\n"
                f"  3. Review gateway logs\n"
                f"  4. Contact IT/DevOps\n"
            )
            logger.error(error_msg)
            logger.exception("Enterprise LLM Gateway exception:")
            
            # 🔴 HARD FAIL - Raise exception instead of fallback
            raise RuntimeError(
                f"Enterprise LLM Gateway failed. No fallback available. {str(e)}"
            )
