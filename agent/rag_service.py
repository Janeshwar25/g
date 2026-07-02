"""
Modular retrieval layer for the AI Help Bot (Phase 1).

Phase 1 sources:
  - Built-in system / workflow documentation
  - Optional ARCHITECTURE_OVERVIEW.txt
  - FAQ knowledge
  - MongoDB project metadata summary
  - Targeted project metadata when identifiers appear in the query

Future extension points (stubs):
  - Vector database similarity search
  - Full Smartsheet markdown chunks
  - LangGraph tool outputs
"""

import logging
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

from config import Config

logger = logging.getLogger(__name__)

# Core application workflows (stable; avoids depending on external doc file)
SYSTEM_WORKFLOW_DOC = """
# Forge Project Plan Generation — How the application works

## UI tabs
- **Build Plan**: User enters Aha Idea, project type, idea name (max 40 chars), BDL, RDL. System fetches Aha data, saves metadata to MongoDB, calls FastAPI POST /chat to build a plan DataFrame, uploads to Smartsheet, stores sheet id in MongoDB.
- **Update Plan**: User enters strategic theme or Aha idea and selects sources (Aha, Optics, Rally fields). FastAPI POST /chat with "Update Request" runs upload.update_smartsheet.update() to refresh Smartsheet cells from Aha, Rally (via Icarus), and PPM Optics.
- **Test Plan**: Generates filtered PET test scripts from Excel templates (no external plan APIs).
- **AI Help Bot**: Answers questions about the system and portfolio metadata via POST /llm.

## Architecture (summary)
- **Streamlit** (app/app.py) on port 8080 — user interface.
- **FastAPI** (app/routes.py) on port 8000 — /chat, /financials, /llm.
- **engine/mapping.py** — build_plan(), Aha and Rally/Icarus integration, Excel templates.
- **upload/** — Smartsheet create (smartsheet_export) and update (update_smartsheet).
- **MongoDB** — plan_metadata collection: idea, name, tag, prj, sheet id, bdl, rdl, active, optional sheet_markdown for AI sync.
- **External APIs**: Aha, Icarus (Rally + Optics data), Smartsheet.

## Build plan requirements
- Valid Aha idea with a strategic theme (ST number) linked in Aha.
- Template: documents/GNP_Template_v4.xlsx.
- Plans land in Growth, New Product Smartsheet workspace folders by initiative area (tag).

## Update behavior
- Only the most recently created plan for a theme/idea is typically updated (per FAQ).
- Manual rows/columns are not overwritten except where update logic maps known fields.
- **Work Breakdown** column must stay in place when reordering columns.
- Rally/Optics data may lag ~1 day (third-party refresh).

## Configuration
- credentials.env (from env.template): API keys, MongoDB, and enterprise gateway credentials.
- config.py centralizes settings.
"""

FAQ_KNOWLEDGE = """
# Frequently Asked Questions (application)

- **Who creates the plan?** BDL and RDL should collaborate; only one build per idea — the most recent plan receives updates.
- **Where is my plan?** Growth, New Product Smartsheet workspace, folder by initiative area.
- **PMAT dashboard**: Can be created during Aha Approved Planning if Aha impacts exist; better after strategic theme exists.
- **Multiple plans**: Only the most recent is updated; delete older copies or they will not auto-update.
- **Capabilities / features mapping**: Based on Rally "Project" field into Application View; unmapped → "Other".
- **Optics tasks missing**: Aha must have correct Optics PRJ populated.
- **Rally/Optics not updating**: Third-party data refreshes roughly daily.
- **Drag/drop capabilities**: Only needed on initial build; later updates stay in place.
- **Custom rows/columns**: Updates are cell-level; manual rows/columns are not wiped.
- **Column reorder**: Allowed except **Work Breakdown** must remain in place.
"""


@dataclass
class RAGContext:
    """Structured retrieval result; serialized into the LLM prompt."""

    sections: List[str] = field(default_factory=list)
    sources_used: List[str] = field(default_factory=list)

    def to_prompt_text(self, max_chars: int) -> str:
        combined = "\n\n".join(self.sections).strip()
        if len(combined) <= max_chars:
            return combined
        return combined[: max_chars - 80] + "\n\n...[context truncated for token limits]..."


class RAGService:
    """
    Phase 1 retrieval orchestrator.

    Swap or extend individual _retrieve_* methods for enterprise RAG later.
    """

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config()
        self._project_id_patterns = [
            re.compile(r"\bST\d+\b", re.IGNORECASE),
            re.compile(r"\bPSTRATEGIC-I-\d+\b", re.IGNORECASE),
            re.compile(r"\bUSPP[A-Z]+-I-\d+\b", re.IGNORECASE),
            re.compile(r"\bGNP-\d+\b", re.IGNORECASE),
        ]

    def retrieve(
        self,
        query: str,
        portfolio_filter: str = "all",
        include_project_details: bool = True,
    ) -> RAGContext:
        """
        Gather all context sections for the current user query.

        Args:
            query: User question.
            portfolio_filter: all | mmi | legacy (portfolio scoping for MongoDB).
            include_project_details: When True, fetch per-project context for detected IDs.

        Returns:
            RAGContext with sections and source labels.
        """
        ctx = RAGContext()
        ctx.sections.append(SYSTEM_WORKFLOW_DOC)
        ctx.sources_used.append("system_workflows")

        arch = self._retrieve_architecture_doc()
        if arch:
            ctx.sections.append(arch)
            ctx.sources_used.append("architecture_overview")

        ctx.sections.append(FAQ_KNOWLEDGE)
        ctx.sources_used.append("faq")

        meta = self._retrieve_mongodb_summary(portfolio_filter)
        if meta:
            ctx.sections.append(meta)
            ctx.sources_used.append("mongodb_portfolio_summary")

        if include_project_details:
            for section in self._retrieve_project_contexts(query, portfolio_filter):
                ctx.sections.append(section)
                ctx.sources_used.append("mongodb_project_detail")

        # Vector / smartsheet markdown / tool results
        vector_matches = self._retrieve_vector_matches(query)
        if vector_matches:
            ctx.sections.extend(vector_matches)
            ctx.sources_used.append("vector_store")
            
        # ctx.sections.extend(self._retrieve_smartsheet_markdown(query))

        return ctx

    def _retrieve_architecture_doc(self) -> Optional[str]:
        """Load ARCHITECTURE_OVERVIEW.txt when present (repo root or /app in Docker)."""
        candidates = [
            "ARCHITECTURE_OVERVIEW.txt",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "ARCHITECTURE_OVERVIEW.txt"),
            "/app/ARCHITECTURE_OVERVIEW.txt",
        ]
        max_chars = 12000
        for path in candidates:
            if os.path.isfile(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        text = f.read(max_chars + 1)
                    if len(text) > max_chars:
                        text = text[:max_chars] + "\n...[architecture doc truncated]..."
                    logger.info("RAG loaded architecture doc from %s", path)
                    return f"# Architecture reference\n\n{text}"
                except OSError as e:
                    logger.warning("Could not read architecture doc %s: %s", path, e)
        return None

    def _retrieve_mongodb_summary(self, portfolio_filter: str) -> Optional[str]:
        try:
            from agent.llm_context_builder import get_metadata_only_summary

            summary = get_metadata_only_summary(portfolio_filter=portfolio_filter)
            if summary and "No projects found" not in summary:
                return summary
        except Exception as e:
            logger.warning("MongoDB portfolio summary unavailable: %s", e)
            return (
                "# Project metadata\n\n"
                "*MongoDB portfolio summary could not be loaded. "
                "Answers will rely on system documentation only.*"
            )
        return None

    def _extract_project_identifiers(self, query: str) -> List[str]:
        found = []
        seen = set()
        for pattern in self._project_id_patterns:
            for match in pattern.findall(query):
                key = match.upper()
                if key not in seen:
                    seen.add(key)
                    found.append(match)
        return found[:3]

    def _retrieve_project_contexts(self, query: str, portfolio_filter: str) -> List[str]:
        identifiers = self._extract_project_identifiers(query)
        if not identifiers:
            return []

        sections = []
        mongo = None
        try:
            from agent.llm_context_builder import get_project_context
            from engine.mongodb_helper import MongoDBHelper

            mongo = MongoDBHelper()
            for ident in identifiers:
                data, key = mongo.get_plan_metadata_by_key(ident)
                if not data or not key:
                    sections.append(f"### Project lookup: {ident}\n\n*No metadata found for this identifier.*")
                    continue
                # Metadata only in Phase 1 to control token size; full sheet_markdown in Phase 2
                ctx = get_project_context(key, include_plan=False, portfolio_filter=portfolio_filter)
                if ctx:
                    sections.append(ctx)
                else:
                    sections.append(f"### Project lookup: {ident}\n\n*Project not available for current portfolio filter.*")
            return sections
        except Exception as e:
            logger.warning("Project context retrieval failed: %s", e)
            return []
        finally:
            if mongo:
                mongo.close()

    # --- Future RAG extension points ---

    def _retrieve_vector_matches(self, query: str) -> List[str]:
        """Search vector database with hybrid exact/semantic matching."""
        try:
            from agent.vector_store import get_vector_store
            store = get_vector_store(self.config)
            if not store:
                return []
                
            # 1. Fetch semantic matches
            semantic_results = store.similarity_search(query, k=15)
            
            # 2. Try to get all docs for exact matching
            all_docs = []
            try:
                if hasattr(store, "docstore") and hasattr(store.docstore, "_dict"):
                    all_docs = list(store.docstore._dict.values())
            except Exception:
                pass
                
            docs_to_score = all_docs if len(all_docs) > 0 else semantic_results
            
            query_lower = query.lower()
            
            # Clean common stop words to identify entity
            stop_pattern = re.compile(r'\b(provide|me|with|the|email|of|what|is|who|where|how|give|show|tell|for|my|find)\b', re.IGNORECASE)
            cleaned_query = stop_pattern.sub('', query_lower).strip()
            cleaned_query = re.sub(r'\s+', ' ', cleaned_query)
            
            scored_docs = []
            seen_content = set()
            
            for doc in docs_to_score:
                if doc.page_content in seen_content:
                    continue
                seen_content.add(doc.page_content)
                
                content_lower = doc.page_content.lower()
                exact_score = 0.0
                
                # Exact full phrase match gets massive boost
                if cleaned_query and len(cleaned_query) > 3:
                    if cleaned_query in content_lower:
                        exact_score += 15.0
                        
                # Split and search terms
                terms = cleaned_query.split()
                term_matches = 0
                for term in terms:
                    if len(term) > 2 and term in content_lower:
                        term_matches += 1
                        # Boost heavily if matched within Name, POC, Contact or Email fields
                        if re.search(rf"\b(name|poc|contact|email|id)\b.*?:.*?(?:{re.escape(term)})", content_lower):
                            exact_score += 5.0
                            
                if terms and term_matches > 0:
                    exact_score += (term_matches / len(terms)) * 5.0
                    
                # Base semantic score based on position in FAISS result (if present)
                semantic_score = 0.0
                if doc in semantic_results:
                    idx = semantic_results.index(doc)
                    semantic_score = (15 - idx) / 15.0  # 0.0 to 1.0 (Top result = 1.0)
                    
                # Hybrid Final Score combining exact match + semantics
                final_score = (0.7 * exact_score) + (0.3 * semantic_score * 10)
                
                if final_score > 0:
                    scored_docs.append((final_score, doc))
                    
            scored_docs.sort(key=lambda x: x[0], reverse=True)
            
            if scored_docs:
                return [doc.page_content for score, doc in scored_docs[:3]]
                
            return [doc.page_content for doc in semantic_results[:3]]

        except Exception as e:
            logger.warning("Vector search failed: %s", e)
        return []

    def _retrieve_smartsheet_markdown(self, query: str, portfolio_filter: str = "all") -> List[str]:
        """Placeholder for chunked Smartsheet markdown retrieval."""
        return []
