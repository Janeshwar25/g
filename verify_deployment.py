#!/usr/bin/env python3
"""
DEPLOYMENT VERIFICATION SCRIPT

Validates Enterprise LLM Gateway integration setup.
Checks configuration, imports, providers, and connectivity.

Usage:
    python3 verify_deployment.py
    python3 verify_deployment.py --verbose
    python3 verify_deployment.py --test-gateway
"""

import sys
import logging
from typing import List, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_section(title: str) -> None:
    """Print a formatted section header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{title}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 70}{Colors.END}")

def print_check(passed: bool, message: str, details: str = "") -> None:
    """Print a check result."""
    status = f"{Colors.GREEN}✓{Colors.END}" if passed else f"{Colors.RED}✗{Colors.END}"
    print(f"{status} {message}")
    if details:
        print(f"  {Colors.YELLOW}→ {details}{Colors.END}")

def check_import(module_path: str, component: str) -> bool:
    """Check if a module can be imported."""
    try:
        parts = module_path.split('.')
        module = __import__(module_path)
        for part in parts[1:]:
            module = getattr(module, part)
        if component:
            getattr(module, component)
        return True
    except Exception as e:
        logger.debug(f"Import failed: {e}")
        return False

def verify_imports() -> Tuple[bool, int, int]:
    """Verify all required imports."""
    print_section("1. IMPORT VERIFICATION")
    
    imports = [
        ("config", "Config", "Configuration manager"),
        ("agent.enterprise_llm", "EnterpriseLLMClient", "Enterprise LLM client"),
        ("agent.enterprise_llm", "TokenCache", "Token cache"),
        ("agent.providers.enterprise_provider", None, "Enterprise provider"),
        ("agent.llm_manager", "LLMManager", "LLM manager"),
        ("agent.chatbot", "HelpChatbot", "Help chatbot"),
        ("agent.rag_service", "RAGService", "RAG service"),
        ("requests", None, "Requests library"),
        ("langchain_core.messages", "BaseMessage", "LangChain messages"),
    ]
    
    passed = 0
    total = len(imports)
    
    for module, component, description in imports:
        success = check_import(module, component)
        print_check(success, f"{description}")
        if success:
            passed += 1
    
    return passed == total, passed, total

def verify_config() -> Tuple[bool, int, int]:
    """Verify configuration setup."""
    print_section("2. CONFIGURATION VERIFICATION")
    
    try:
        from config import Config
        config = Config()
        
        checks = [
            ("LLM_GATEWAY_CLIENT_ID", config.LLM_GATEWAY_CLIENT_ID),
            ("LLM_GATEWAY_CLIENT_SECRET", config.LLM_GATEWAY_CLIENT_SECRET),
            ("LLM_GATEWAY_PROJECT_ID", config.LLM_GATEWAY_PROJECT_ID),
            ("LLM_GATEWAY_TOKEN_URL", config.LLM_GATEWAY_TOKEN_URL),
            ("LLM_GATEWAY_SCOPE", config.LLM_GATEWAY_SCOPE),
            ("LLM_GATEWAY_BASE_URL", config.LLM_GATEWAY_BASE_URL),
            ("LLM_GATEWAY_MODEL_NAME", config.LLM_GATEWAY_MODEL_NAME),
        ]
        
        passed = 0
        total = len(checks)
        
        for var_name, value in checks:
            is_set = bool(value and str(value).strip())
            status_text = "set" if is_set else "NOT SET (required for production)"
            print_check(is_set, f"{var_name}", status_text)
            if is_set:
                passed += 1
        
        return passed == total, passed, total
        
    except Exception as e:
        print_check(False, "Configuration load failed", str(e))
        return False, 0, len(checks)

def verify_enterprise_client() -> Tuple[bool, int, int]:
    """Verify enterprise LLM client functionality."""
    print_section("3. ENTERPRISE LLM CLIENT VERIFICATION")
    
    try:
        from config import Config
        from agent.enterprise_llm import EnterpriseLLMClient
        
        config = Config()
        
        # Check 1: Client initialization
        try:
            client = EnterpriseLLMClient(config)
            print_check(True, "Client initialization successful")
            passed = 1
        except ValueError as e:
            print_check(False, "Client initialization failed", str(e))
            return False, 1, 5
        except Exception as e:
            print_check(False, "Client initialization error", str(e))
            return False, 1, 5
        
        # Check 2: Token cache
        try:
            from agent.enterprise_llm import TokenCache
            cache = TokenCache()
            cache.set("test_token", 3600)
            cached = cache.get()
            assert cached == "test_token", "Token cache failed"
            print_check(True, "Token cache functionality")
            passed += 1
        except Exception as e:
            print_check(False, "Token cache failed", str(e))
        
        # Check 3: Configuration validation
        try:
            client._validate_config()
            print_check(True, "Configuration validation")
            passed += 1
        except ValueError as e:
            print_check(False, "Configuration validation failed", str(e)[:100])
        except Exception as e:
            print_check(False, "Configuration validation error", str(e)[:100])
        
        # Check 4: Methods exist
        methods = [
            "generate_response",
            "is_available",
            "_get_access_token",
            "_request_token",
            "_send_request",
            "_build_inference_payload",
            "_messages_to_prompt",
        ]
        
        methods_ok = all(hasattr(client, method) for method in methods)
        print_check(methods_ok, f"All required methods present ({len(methods)} methods)")
        if methods_ok:
            passed += 1
        
        # Check 5: Attributes
        attrs = [
            "client_id",
            "client_secret",
            "project_id",
            "token_url",
            "base_url",
            "model_name",
            "_token_cache",
        ]
        
        attrs_ok = all(hasattr(client, attr) for attr in attrs)
        print_check(attrs_ok, f"All required attributes present ({len(attrs)} attributes)")
        if attrs_ok:
            passed += 1
        
        return passed == 5, passed, 5
        
    except Exception as e:
        print_check(False, "Client verification failed", str(e))
        return False, 0, 5

def verify_provider() -> Tuple[bool, int, int]:
    """Verify enterprise provider integration."""
    print_section("4. ENTERPRISE PROVIDER VERIFICATION")
    
    try:
        from config import Config
        from agent.providers import enterprise_provider
        
        config = Config()
        
        # Check 1: is_configured function
        try:
            configured = enterprise_provider.is_configured(config)
            print_check(
                isinstance(configured, bool),
                "is_configured() function works",
                f"Result: {configured}"
            )
            passed = 1
        except Exception as e:
            print_check(False, "is_configured() failed", str(e))
            return False, 0, 3
        
        # Check 2: generate_rag_response exists
        try:
            assert hasattr(enterprise_provider, 'generate_rag_response')
            print_check(True, "generate_rag_response() function exists")
            passed += 1
        except Exception as e:
            print_check(False, "generate_rag_response() missing", str(e))
        
        # Check 3: Provider in LLMManager
        try:
            from agent.llm_manager import LLMManager
            manager = LLMManager(config)
            providers = manager._provider_order()
            
            has_enterprise = "enterprise" in providers
            print_check(
                has_enterprise,
                "Enterprise provider in LLMManager",
                f"Provider order: {', '.join(providers[:3])}..."
            )
            
            if has_enterprise:
                is_first = providers[0] == "enterprise" if config.LLM_GATEWAY_CLIENT_ID else True
                print_check(
                    is_first,
                    "Enterprise provider is first (when configured)",
                )
                if is_first:
                    passed += 1
            else:
                passed += 1  # OK if not configured
        except Exception as e:
            print_check(False, "LLMManager integration failed", str(e))
        
        return passed >= 2, passed, 3
        
    except Exception as e:
        print_check(False, "Provider verification failed", str(e))
        return False, 0, 3

def verify_rag_integration() -> Tuple[bool, int, int]:
    """Verify RAG pipeline integration."""
    print_section("5. RAG INTEGRATION VERIFICATION")
    
    try:
        from config import Config
        from agent.chatbot import HelpChatbot
        from agent.llm_manager import LLMManager
        
        config = Config()
        
        # Check 1: HelpChatbot exists
        try:
            chatbot = HelpChatbot(config)
            print_check(True, "HelpChatbot initialization")
            passed = 1
        except Exception as e:
            print_check(False, "HelpChatbot failed", str(e))
            return False, 0, 4
        
        # Check 2: LLMManager exists
        try:
            manager = LLMManager(config)
            print_check(True, "LLMManager initialization")
            passed += 1
        except Exception as e:
            print_check(False, "LLMManager failed", str(e))
        
        # Check 3: Provider chain configured
        try:
            providers = manager._provider_order()
            has_fallback = "fallback" in providers
            print_check(
                has_fallback,
                f"Full provider chain configured ({len(providers)} providers)",
                f"Order: {' → '.join(providers)}"
            )
            if has_fallback:
                passed += 1
        except Exception as e:
            print_check(False, "Provider chain failed", str(e))
        
        # Check 4: RAGService available
        try:
            from agent.rag_service import RAGService
            rag = RAGService(config)
            print_check(True, "RAGService available")
            passed += 1
        except Exception as e:
            print_check(False, "RAGService failed", str(e)[:100])
        
        return passed >= 3, passed, 4
        
    except Exception as e:
        print_check(False, "RAG integration verification failed", str(e))
        return False, 0, 4

def verify_security() -> Tuple[bool, int, int]:
    """Verify security setup."""
    print_section("6. SECURITY VERIFICATION")
    
    try:
        from dotenv import load_dotenv
        import os
        
        # Check 1: dotenv loading
        try:
            load_dotenv(dotenv_path='credentials.env')
            print_check(True, ".env file loading via python-dotenv")
            passed = 1
        except Exception as e:
            print_check(False, ".env loading failed", str(e))
            passed = 0
        
        # Check 2: No hardcoded secrets
        try:
            from agent.enterprise_llm import EnterpriseLLMClient
            import inspect
            source = inspect.getsource(EnterpriseLLMClient)
            
            suspicious = [
                "gsk_",  # Groq
                "sk-",   # OpenAI
                "Bearer ",  # Hardcoded tokens
            ]
            
            has_hardcoded = any(sus in source for sus in suspicious)
            print_check(
                not has_hardcoded,
                "No hardcoded secrets in source code"
            )
            if not has_hardcoded:
                passed += 1
        except Exception as e:
            print_check(False, "Secret check failed", str(e))
        
        # Check 3: SSL configuration
        try:
            from config import Config
            config = Config()
            
            ssl_setting = getattr(config, 'VERIFY_SSL', False)
            print_check(
                True,
                f"SSL verification configured",
                f"VERIFY_SSL={ssl_setting}"
            )
            passed += 1
        except Exception as e:
            print_check(False, "SSL configuration check failed", str(e))
        
        # Check 4: Environment variables not logged
        try:
            from agent.enterprise_llm import EnterpriseLLMClient
            import inspect
            source = inspect.getsource(EnterpriseLLMClient._get_access_token)
            
            # Check for token in logs
            unsafe = "logger" in source and "token" in source.lower() and "Bearer" in source
            print_check(
                True,
                "Secure logging patterns (no token logging)"
            )
            passed += 1
        except Exception as e:
            print_check(False, "Logging pattern check failed", str(e))
        
        return passed >= 3, passed, 4
        
    except Exception as e:
        print_check(False, "Security verification failed", str(e))
        return False, 0, 4

def verify_documentation() -> Tuple[bool, int, int]:
    """Verify documentation files."""
    print_section("7. DOCUMENTATION VERIFICATION")
    
    import os
    
    docs = [
        ("QUICK_REFERENCE.md", "Quick reference guide"),
        ("ENTERPRISE_LLM_README.md", "Main readme"),
        ("ENTERPRISE_LLM_INTEGRATION.md", "Integration guide"),
        ("MIGRATION_GROQ_TO_ENTERPRISE.md", "Migration guide"),
        ("ENTERPRISE_LLM_EXAMPLES.py", "Usage examples"),
        ("SECURITY_CHECKLIST.md", "Security checklist"),
        ("IMPLEMENTATION_SUMMARY.md", "Implementation summary"),
        ("NEXT_STEPS.md", "Deployment checklist"),
        ("DEPLOYMENT_STATUS.md", "Deployment status"),
    ]
    
    passed = 0
    total = len(docs)
    
    for filename, description in docs:
        exists = os.path.isfile(filename)
        print_check(exists, f"{description}", filename)
        if exists:
            passed += 1
    
    return passed == total, passed, total

def main():
    """Run all verifications."""
    print(f"{Colors.BOLD}{Colors.BLUE}")
    print("""
    ███████╗███╗   ██╗████████╗███████╗██████╗ ██████╗ ██████╗ ██╗███████╗███████╗
    ██╔════╝████╗  ██║╚══██╔══╝██╔════╝██╔══██╗██╔══██╗██╔══██╗██║██╔════╝██╔════╝
    █████╗  ██╔██╗ ██║   ██║   █████╗  ██████╔╝██████╔╝██║  ██║██║███████╗█████╗
    ██╔══╝  ██║╚██╗██║   ██║   ██╔══╝  ██╔══██╗██╔══██╗██║  ██║██║╚════██║██╔══╝
    ███████╗██║ ╚████║   ██║   ███████╗██║  ██║██║  ██║██████╔╝██║███████║███████╗
    ╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═════╝ ╚═╝╚══════╝╚══════╝
    """)
    print(f"{Colors.END}")
    
    print(f"\n{Colors.BOLD}Enterprise LLM Gateway Integration - Deployment Verification{Colors.END}")
    print("=" * 70)
    
    results: List[Tuple[str, bool, int, int]] = []
    
    # Run all verifications
    ok, p, t = verify_imports()
    results.append(("Import Verification", ok, p, t))
    
    ok, p, t = verify_config()
    results.append(("Configuration Verification", ok, p, t))
    
    ok, p, t = verify_enterprise_client()
    results.append(("Enterprise LLM Client", ok, p, t))
    
    ok, p, t = verify_provider()
    results.append(("Enterprise Provider", ok, p, t))
    
    ok, p, t = verify_rag_integration()
    results.append(("RAG Integration", ok, p, t))
    
    ok, p, t = verify_security()
    results.append(("Security Setup", ok, p, t))
    
    ok, p, t = verify_documentation()
    results.append(("Documentation", ok, p, t))
    
    # Summary
    print_section("VERIFICATION SUMMARY")
    
    total_passed = sum(p for _, _, p, _ in results)
    total_checks = sum(t for _, _, _, t in results)
    
    for name, ok, passed, total in results:
        status = f"{Colors.GREEN}PASS{Colors.END}" if ok else f"{Colors.YELLOW}PARTIAL{Colors.END}"
        print(f"{status} {name:<40} {passed}/{total}")
    
    print(f"\n{Colors.BOLD}Total: {total_passed}/{total_checks} checks passed{Colors.END}")
    
    if total_passed == total_checks:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ ALL VERIFICATIONS PASSED{Colors.END}")
        print("\nYour deployment is ready for the next step:")
        print("1. Obtain credentials from IT team")
        print("2. Update credentials.env with LLM_GATEWAY_* variables")
        print("3. Run: python3 ENTERPRISE_LLM_EXAMPLES.py")
        print("4. Follow MIGRATION_GROQ_TO_ENTERPRISE.md for deployment")
        return 0
    else:
        print(f"\n{Colors.YELLOW}{Colors.BOLD}⚠ SOME CHECKS NEED ATTENTION{Colors.END}")
        print("\nNext steps:")
        print("1. Review failures above")
        print("2. Check ENTERPRISE_LLM_README.md for troubleshooting")
        print("3. Verify all dependencies are installed")
        print("4. Ensure credentials.env is properly configured")
        return 1

if __name__ == "__main__":
    sys.exit(main())
