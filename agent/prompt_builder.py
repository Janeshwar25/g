"""
Prompt construction for the Phase 1 AI Help Bot.

Keeps system instructions and message assembly separate from retrieval and inference
so prompts can evolve without touching RAG or API routes.
"""

from typing import Any, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

HELP_BOT_SYSTEM_PROMPT = """You are an Enterprise AI Help Bot and Document Analyst.

You assist users by generating clear, professional, and concise answers using ONLY the context provided below. 

Guidelines:
- Rely strictly on retrieved sections (documents, spreadsheets, vector matches, workflow knowledge).
- Prioritize exact entity matches over general fuzzy descriptions.
- Format responses cleanly. Do not emit large dumps of raw metadata.
- When retrieving data from uploaded files (like Excel), provide a brief summary rather than just repeating isolated row structures.
- Include explicit and clean markdown URL links if you output emails or web addresses (e.g. `[user@domain.com](mailto:user@domain.com)`).
- When appropriate, append a concise citation pointing back to the Source File, Sheet, or System context at the bottom of your answer.
- If the context does not contain enough information, state this directly. Do not invent answers or hallucinate data.
- Avoid printing "row strings" iteratively. If several contacts exist, wrap them in clean sentence structures.

When listing steps, use numbered or bullet lists.
"""


def build_help_bot_messages(
    user_query: str,
    rag_context: str,
    chat_history: Optional[List[Dict[str, str]]] = None,
    max_history_messages: int = 10,
) -> List[Any]:
    """
    Assemble LangChain messages for a single help-bot turn.

    Args:
        user_query: Current user question.
        rag_context: Retrieved context string from RAGService.
        chat_history: Prior turns [{"role": "user"|"assistant", "content": "..."}].
        max_history_messages: Cap on prior turns included for continuity.

    Returns:
        List of LangChain message objects for invoke().
    """
    context_block = rag_context.strip() if rag_context else "*No additional context retrieved.*"
    system_content = (
        f"{HELP_BOT_SYSTEM_PROMPT}\n\n"
        f"---\n## Retrieved context\n\n{context_block}\n---"
    )

    messages: List[Any] = [SystemMessage(content=system_content)]

    if chat_history:
        trimmed = chat_history[-max_history_messages:]
        for msg in trimmed:
            role = (msg.get("role") or "").lower()
            content = (msg.get("content") or "").strip()
            if not content or content == "Thinking...":
                continue
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content=user_query.strip()))
    return messages
