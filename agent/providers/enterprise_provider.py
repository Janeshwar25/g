"""
agent.providers.enterprise_provider

Enterprise LLM Gateway provider for production use.

This is the only production inference provider. It calls the company's
LLM gateway using OAuth2 authentication.

Environment variables:
- LLM_GATEWAY_CLIENT_ID
- LLM_GATEWAY_CLIENT_SECRET
- LLM_GATEWAY_PROJECT_ID
- LLM_GATEWAY_TOKEN_URL
- LLM_GATEWAY_SCOPE
- LLM_GATEWAY_BASE_URL
"""

import logging
from typing import Any, List

from langchain_core.messages import BaseMessage

logger = logging.getLogger(__name__)


def is_configured(config: Any) -> bool:
    """
    Check if enterprise LLM gateway is properly configured.

    Returns:
        True if all required settings are present, False otherwise
    """
    required = [
        getattr(config, "LLM_GATEWAY_CLIENT_ID", ""),
        getattr(config, "LLM_GATEWAY_CLIENT_SECRET", ""),
        getattr(config, "LLM_GATEWAY_PROJECT_ID", ""),
        getattr(config, "LLM_GATEWAY_TOKEN_URL", ""),
        getattr(config, "LLM_GATEWAY_BASE_URL", ""),
    ]
    return all(str(v).strip() for v in required)


def generate_rag_response(
    messages: List[BaseMessage],
    config: Any,
    temperature: float = 0.1,
    is_reasoning: bool = False,
) -> str:
    """
    Generate response using enterprise LLM gateway with RAG context.

    Args:
        messages: List of LangChain message objects (system, history, user query)
        config: Configuration object with enterprise gateway settings
        temperature: Model temperature (0.1 for factual, ~0.7 for creative)

    Returns:
        Generated response string

    Raises:
        RuntimeError: If gateway request fails
    """
    from agent.enterprise_llm import EnterpriseLLMClient

    logger.debug("[Enterprise] Generating RAG response")

    try:
        client = EnterpriseLLMClient(config)
        response = client.generate_response(
            messages=messages,
            context="rag_pipeline",
            is_reasoning=is_reasoning,
        )
        logger.info("[Enterprise] RAG response generated (%d chars)", len(response))
        return response

    except ValueError as e:
        logger.error("[Enterprise] Configuration error: %s", e)
        raise RuntimeError(f"Enterprise LLM configuration error: {str(e)}")

    except RuntimeError as e:
        logger.error("[Enterprise] Gateway error: %s", e)
        raise

    except Exception as e:
        logger.exception("[Enterprise] Unexpected error in enterprise provider")
        raise RuntimeError(f"Enterprise LLM unexpected error: {str(e)}")
