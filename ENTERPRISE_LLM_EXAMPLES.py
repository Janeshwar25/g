"""
ENTERPRISE LLM GATEWAY - USAGE EXAMPLES

Demonstrates how to use the Enterprise LLM client in various scenarios.
"""

import logging
from typing import Optional

# Configure logging to see detailed information
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# ========================================================================
# EXAMPLE 1: Basic initialization and availability check
# ========================================================================

def example_1_initialization():
    """Check if Enterprise LLM Gateway is properly configured."""
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Initialization and Configuration Check")
    print("=" * 70)

    from config import Config
    from agent.enterprise_llm import EnterpriseLLMClient

    try:
        config = Config()
        client = EnterpriseLLMClient(config)
        print("✓ Client initialized successfully")

        # Check if gateway is reachable
        if client.is_available():
            print("✓ Enterprise LLM Gateway is available")
        else:
            print("✗ Enterprise LLM Gateway is not reachable")
            print("  Check network connectivity and credentials")

    except ValueError as e:
        print(f"✗ Configuration error: {e}")
        print("  Update credentials.env with LLM_GATEWAY_* variables")
    except Exception as e:
        print(f"✗ Initialization failed: {e}")


# ========================================================================
# EXAMPLE 2: Simple prompt without RAG context
# ========================================================================

def example_2_simple_prompt():
    """Send a simple prompt directly to the gateway."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Simple Prompt (No RAG)")
    print("=" * 70)

    from config import Config
    from agent.enterprise_llm import EnterpriseLLMClient

    config = Config()
    client = EnterpriseLLMClient(config)

    prompt = "What is the purpose of a project plan?"

    try:
        response = client.generate_response(prompt=prompt)
        print(f"\nPrompt:\n  {prompt}")
        print(f"\nResponse:\n  {response}")
    except RuntimeError as e:
        print(f"✗ Error: {e}")


# ========================================================================
# EXAMPLE 3: Prompt with RAG context
# ========================================================================

def example_3_rag_context():
    """Send a prompt with RAG-retrieved context."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Prompt with RAG Context")
    print("=" * 70)

    from config import Config
    from agent.enterprise_llm import EnterpriseLLMClient

    config = Config()
    client = EnterpriseLLMClient(config)

    # Simulate RAG context
    rag_context = """
# Project Status Document

## Current Projects
1. **Project Alpha**: In planning phase, 40% complete
2. **Project Beta**: In execution phase, 65% complete
3. **Project Gamma**: Testing phase, 80% complete

## Recent Updates
- Project Alpha: Requirements finalized
- Project Beta: Core development completed
- Project Gamma: UAT in progress
"""

    prompt = f"""Based on this context:

{rag_context}

Question: What is the status of Project Beta?"""

    try:
        response = client.generate_response(prompt=prompt)
        print(f"\nContext:\n{rag_context}")
        print(f"\nQuestion: What is the status of Project Beta?")
        print(f"\nResponse:\n  {response}")
    except RuntimeError as e:
        print(f"✗ Error: {e}")


# ========================================================================
# EXAMPLE 4: Using LangChain message objects
# ========================================================================

def example_4_langchain_messages():
    """Use LangChain message objects (preferred for RAG integration)."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: LangChain Messages (RAG-Ready)")
    print("=" * 70)

    from config import Config
    from agent.enterprise_llm import EnterpriseLLMClient
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

    config = Config()
    client = EnterpriseLLMClient(config)

    # Build messages like in RAG pipeline
    messages = [
        SystemMessage(
            content="You are a helpful assistant that answers questions about projects. "
            "Rely only on the provided context."
        ),
        HumanMessage(
            content="Context: Project Alpha is a new initiative starting in Q3. "
            "Expected timeline: 6 months. Budget: $500K.\n\n"
            "Question: When does Project Alpha start?"
        ),
    ]

    try:
        response = client.generate_response(messages=messages)
        print(f"\nMessages:")
        for i, msg in enumerate(messages):
            print(f"  {i + 1}. {msg.__class__.__name__}: {str(msg.content)[:100]}...")
        print(f"\nResponse:\n  {response}")
    except RuntimeError as e:
        print(f"✗ Error: {e}")


# ========================================================================
# EXAMPLE 5: Multi-turn conversation (chat history)
# ========================================================================

def example_5_multi_turn():
    """Demonstrate multi-turn conversation handling."""
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Multi-Turn Conversation")
    print("=" * 70)

    from config import Config
    from agent.enterprise_llm import EnterpriseLLMClient
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

    config = Config()
    client = EnterpriseLLMClient(config)

    # Conversation history
    messages = [
        SystemMessage(
            content="You are a project management assistant. "
            "Answer questions based on provided context."
        ),
        # Previous turn
        HumanMessage(content="What projects are in progress?"),
        AIMessage(
            content="Based on the context, Project Beta and Project Gamma are in progress."
        ),
        # Current turn
        HumanMessage(content="How much longer for Project Beta?"),
    ]

    context = "Project Beta is 65% complete with 2 months remaining."

    try:
        response = client.generate_response(
            messages=messages,
            context="project_status",
        )
        print(f"\nConversation history (4 messages)")
        print(f"Current question: How much longer for Project Beta?")
        print(f"Context: {context}")
        print(f"\nResponse:\n  {response}")
    except RuntimeError as e:
        print(f"✗ Error: {e}")


# ========================================================================
# EXAMPLE 6: Integration with RAG pipeline (HelpChatbot)
# ========================================================================

def example_6_rag_integration():
    """Shows how Enterprise LLM integrates with the full RAG pipeline."""
    print("\n" + "=" * 70)
    print("EXAMPLE 6: RAG Pipeline Integration (HelpChatbot)")
    print("=" * 70)

    from config import Config
    from agent.chatbot import HelpChatbot

    config = Config()

    # This is what Streamlit and FastAPI do automatically
    # The HelpChatbot handles:
    # 1. RAG retrieval
    # 2. Context building
    # 3. Message construction
    # 4. Provider selection (Enterprise first)
    # 5. Response generation

    bot = HelpChatbot(config)

    query = "Who is the project owner?"

    try:
        result = bot.answer(query)
        print(f"\nQuery: {query}")
        print(f"\nResponse:\n  {result['response']}")
        print(f"\nSources: {', '.join(result['sources_used'])}")
        print(f"Mode: {result['mode']}")
    except Exception as e:
        print(f"✗ Error: {e}")


# ========================================================================
# EXAMPLE 7: Token management and caching
# ========================================================================

def example_7_token_caching():
    """Demonstrates token caching and automatic refresh."""
    print("\n" + "=" * 70)
    print("EXAMPLE 7: Token Management and Caching")
    print("=" * 70)

    from config import Config
    from agent.enterprise_llm import EnterpriseLLMClient
    import time

    config = Config()
    client = EnterpriseLLMClient(config)

    print("Token lifecycle:")
    print("1. First request → Generate new token")
    print("2. Subsequent requests → Reuse cached token")
    print("3. Token near expiry → Auto-refresh before use")

    try:
        # First call - generates token
        print("\n  Attempt 1 (generates token)...")
        response1 = client.generate_response(prompt="Hello")
        print("  ✓ Token generated and cached")

        # Second call - uses cached token
        print("  Attempt 2 (uses cached token)...")
        response2 = client.generate_response(prompt="Hello again")
        print("  ✓ Used cached token")

        # Inspect cache
        cached_token = client._token_cache.get()
        if cached_token:
            print(f"  ✓ Token in cache: {cached_token[:20]}...{cached_token[-10:]}")
        else:
            print("  ✗ No token in cache")

    except RuntimeError as e:
        print(f"✗ Error: {e}")


# ========================================================================
# EXAMPLE 8: Error handling and recovery
# ========================================================================

def example_8_error_handling():
    """Demonstrates error handling and recovery."""
    print("\n" + "=" * 70)
    print("EXAMPLE 8: Error Handling")
    print("=" * 70)

    from config import Config
    from agent.enterprise_llm import EnterpriseLLMClient

    print("Errors handled by EnterpriseLLMClient:")
    print("  • Configuration errors (missing env vars)")
    print("  • Network timeouts (auto-retry with backoff)")
    print("  • Authentication failures (clear error message)")
    print("  • Rate limiting (retry with Retry-After header)")
    print("  • Server errors (retry with exponential backoff)")

    config = Config()

    # Example 1: Missing configuration
    print("\n1. Configuration Error:")
    try:
        # Simulate missing config by creating with empty client ID
        class BadConfig:
            LLM_GATEWAY_CLIENT_ID = ""
            REQUEST_TIMEOUT = 180
            VERIFY_SSL = True

        client = EnterpriseLLMClient(BadConfig())
    except ValueError as e:
        print(f"   ✓ Caught: {e}")

    # Example 2: Invalid prompt
    print("\n2. Empty Prompt Error:")
    try:
        config = Config()
        if config.LLM_GATEWAY_CLIENT_ID:  # Only if configured
            client = EnterpriseLLMClient(config)
            client.generate_response(prompt="")
    except ValueError as e:
        print(f"   ✓ Caught: {e}")

    # Example 3: Network error (would retry automatically)
    print("\n3. Network Errors (auto-retry):")
    print("   • Timeout: Retries with exponential backoff")
    print("   • Connection refused: Retries with exponential backoff")
    print("   • DNS failure: Retries with exponential backoff")


# ========================================================================
# EXAMPLE 9: Comparing providers
# ========================================================================

def example_9_provider_comparison():
    """Shows how Enterprise LLM fits into the provider chain."""
    print("\n" + "=" * 70)
    print("EXAMPLE 9: Provider Selection and Fallback")
    print("=" * 70)

    from config import Config
    from agent.llm_manager import LLMManager

    config = Config()
    manager = LLMManager(config)

    print("LLMManager tries providers in this order:")
    providers = manager._provider_order()
    for i, provider in enumerate(providers, 1):
        status = "✓ Configured" if provider in ["enterprise", "azure", "fallback"] else "  "
        print(f"  {i}. {provider:15} {status}")

    print("\nFallback behavior:")
    print("  • If Enterprise fails → tries Azure")
    print("  • If Azure fails → tries OpenAI (testing)")
    print("  • If OpenAI fails → tries Groq (testing)")
    print("  • If Groq fails → tries Gemini (testing)")
    print("  • If all fail → LocalFallback (always available)")


# ========================================================================
# EXAMPLE 10: Production deployment checklist
# ========================================================================

def example_10_deployment_checklist():
    """Checklist for deploying Enterprise LLM in production."""
    print("\n" + "=" * 70)
    print("EXAMPLE 10: Production Deployment Checklist")
    print("=" * 70)

    checklist = [
        ("credentials.env configured", "LLM_GATEWAY_* vars set"),
        ("Client credentials valid", "Test token generation"),
        ("Network connectivity", "Can reach token and API endpoints"),
        ("SSL/TLS validation", "Set VERIFY_SSL=true for prod"),
        ("Logging configured", "Monitor [Enterprise LLM] logs"),
        ("Request timeout", "Set appropriate REQUEST_TIMEOUT"),
        ("Rate limiting awareness", "Know your quota"),
        ("Fallback tested", "Verify fallback works if gateway down"),
        ("Secrets management", "credentials.env excluded from git"),
        ("Monitoring alerts", "Alert on provider failures"),
    ]

    print("\nBefore deploying to production:")
    for i, (item, details) in enumerate(checklist, 1):
        print(f"  ☐ {item:30} ({details})")


# ========================================================================
# MAIN
# ========================================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("ENTERPRISE LLM GATEWAY - USAGE EXAMPLES")
    print("=" * 70)
    print("\nThese examples demonstrate various use cases for the Enterprise LLM Client.")
    print("Uncomment examples to run them.\n")

    # Run all examples (comment out to skip)
    example_1_initialization()
    # example_2_simple_prompt()
    # example_3_rag_context()
    # example_4_langchain_messages()
    # example_5_multi_turn()
    # example_6_rag_integration()
    # example_7_token_caching()
    example_8_error_handling()
    example_9_provider_comparison()
    example_10_deployment_checklist()

    print("\n" + "=" * 70)
    print("For more information, see: ENTERPRISE_LLM_INTEGRATION.md")
    print("=" * 70 + "\n")
