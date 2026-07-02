"""
🔒 ENTERPRISE-ONLY AI HELP BOT 🔒

STRICT ENTERPRISE INFERENCE MODE

This chatbot provides enterprise-only AI assistance via the company's
LLM Gateway using OAuth2 authentication.

IMPORTANT:
  ✓ All inference MUST use Enterprise LLM Gateway
  ✓ No fallback providers
  ✓ No public LLMs
  ✓ No legacy integrations
  ✓ OAuth2 authentication required

The system will HARD FAIL if enterprise credentials are unavailable.

Architecture:
  User Query
    ↓
  RAGService (vector search + context retrieval)
    ↓
  HelpChatbot (prompt building)
    ↓
  LLMManager (ENTERPRISE-ONLY routing)
    ↓
  EnterpriseLLMClient (OAuth2 authentication)
    ↓
  Company LLM Gateway
    ↓
  Enterprise Approved Response
"""

import logging
import time
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage

from agent.llm_manager import LLMManager
from agent.bm25_retriever import BM25Retriever
from config import Config

logger = logging.getLogger(__name__)


class HelpChatbot:
    """
    🔒 Enterprise-Only AI Help Assistant
    
    Provides RAG-enhanced Q&A using ONLY the company's Enterprise LLM Gateway.
    
    Architecture:
      User Query
        ↓
      RAGService (vector search + context retrieval)
        ↓
      HelpChatbot (prompt building)
        ↓
      LLMManager (ENTERPRISE-ONLY routing)
        ↓
      EnterpriseLLMClient (OAuth2 authentication)
        ↓
      Company LLM Gateway
        ↓
      Enterprise Approved Response
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self.llm_manager = LLMManager(self.config)

    def answer(
        self,
        query: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        portfolio_filter: str = "all",
        session_id: str = None,
    ) -> Dict[str, Any]:
        """
        Generate a help-bot response via the LLM Manager.

        Returns:
            dict with keys: response, sources_used, mode 
        """
        query = (query or "").strip()
        if not query:
            raise ValueError("Query cannot be empty.")

        if self.config.RETRIEVER_TYPE == "bm25":
            retriever = BM25Retriever(self.config)
        else:
            raise NotImplementedError(f"Retriever type '{self.config.RETRIEVER_TYPE}' not currently supported.")
            
        full_context, sources_used = retriever.retrieve(query, session_id=session_id)

        # Build the exact prompt structure requested
        prompt = f"""You are the Forge AI Help Bot.

Answer ONLY using the knowledge provided below.

Never use outside knowledge.

If the answer is not available, explicitly say:
"I couldn't find that information in the available documents."

{full_context}

Question:
{query}"""

        messages = [HumanMessage(content=prompt)]
        
        num_chunks = full_context.count("--------------------") // 2
        
        logger.info("\n=== PRE-LLM DEBUG ===")
        logger.info("User question: %s", query)
        logger.info("Number of retrieved chunks: %d", num_chunks)
        logger.info("Prompt length: %d characters", len(prompt))
        logger.info("First 300 characters of prompt:\n%s...", prompt[:300])
        logger.info("=====================\n")

        logger.info(
            "Help bot requesting LLM Manager (portfolio=%s, sources=%s, context_chars=%d)",
            portfolio_filter,
            sources_used,
            len(full_context),
        )

        logger.info("\nLLM Started\n")
        start_time = time.time()
        
        result = self.llm_manager.answer_query(
             query=query,
             messages=messages,
             rag_context=full_context,
             sources_used=sources_used
        )
        
        end_time = time.time()
        latency = end_time - start_time
        logger.info("\nLLM Finished\n\nResponse Time:\n%.1f seconds", latency)
        
        if self.config.RETRIEVER_TYPE == "bm25":
            try:
                retriever.record_llm_latency(latency)
            except AttributeError:
                pass
        
        return result
