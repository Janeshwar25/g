"""
LangChain Agent for Project Plan Management

This agent can:
1. Answer questions about project data (using MongoDB + Smartsheet data)
2. Create user alerts to display on the dashboard
3. Generate email drafts based on templates

Uses LangGraph for agentic workflow with tool calling.
"""

import sys
import os
from typing import List, Dict, Any, Optional, TypedDict, Annotated
from datetime import datetime
import json
import re
from difflib import get_close_matches

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from agent.enterprise_llm import EnterpriseLLMClient
from agent.prompts import PROJECT_AGENT_SYSTEM_PROMPT
from config import Config

from agent.llm_context_builder import (
    get_all_active_projects_context, 
    get_project_context, 
    get_metadata_only_summary,
    search_projects_by_criteria,
    format_project_with_plan,
)

from engine.mongodb_helper import MongoDBHelper
from upload.update_smartsheet import smartsheet_to_pandas

_PROJECT_PORTFOLIO_FILTER = 'all'


def _normalize_portfolio_filter(portfolio_filter: str) -> str:
    value = str(portfolio_filter or 'all').strip().lower()
    aliases = {
        'all': 'all',
        'mmi': 'mmi',
        'growth_new_product': 'mmi',
        'growth, new product': 'mmi',
        'legacy': 'legacy',
    }
    return aliases.get(value, 'all')


def _record_matches_active_filter(project_data: Dict[str, Any]) -> bool:
    bc = str(project_data.get('bc', 'LEGACY') or 'LEGACY').upper()
    if _PROJECT_PORTFOLIO_FILTER == 'mmi':
        return bc == 'MMI'
    if _PROJECT_PORTFOLIO_FILTER == 'legacy':
        return bc != 'MMI'
    return True


def _normalize_identifier(value: str) -> str:
    return re.sub(r'[^A-Za-z0-9]', '', str(value or '').upper())


def _collect_identifier_values(doc: Dict[str, Any]) -> List[str]:
    values = []
    for field in ('_id', 'idea', 'strategic_theme_mmi'):
        val = doc.get(field)
        if val:
            values.append(str(val))
    return values


def _suggest_project_identifiers(project_key: str, max_suggestions: int = 3) -> List[str]:
    """Suggest close ST/Aha identifiers from Mongo records, honoring active portfolio filter."""
    mongo_helper = MongoDBHelper()
    collection = mongo_helper.collection

    candidates = []
    seen = set()
    for doc in collection.find({}, {'_id': 1, 'idea': 1, 'strategic_theme_mmi': 1, 'bc': 1}):
        if not _record_matches_active_filter(doc):
            continue
        for identifier in _collect_identifier_values(doc):
            normalized = _normalize_identifier(identifier)
            if normalized and normalized not in seen:
                seen.add(normalized)
                candidates.append(identifier)

    if not candidates:
        return []

    normalized_target = _normalize_identifier(project_key)
    normalized_map = {}
    for item in candidates:
        normalized_map.setdefault(_normalize_identifier(item), item)

    # Prefer prefix/same-family candidates first (e.g., ST2156x)
    prefix = normalized_target[:4] if len(normalized_target) >= 4 else normalized_target
    family = [v for k, v in normalized_map.items() if prefix and k.startswith(prefix)]

    close_norm = get_close_matches(normalized_target, list(normalized_map.keys()), n=max_suggestions, cutoff=0.7)
    close = [normalized_map[n] for n in close_norm]

    merged = []
    for item in family + close:
        if item not in merged:
            merged.append(item)
    return merged[:max_suggestions]


def _resolve_project_record(project_key: str) -> Optional[Dict[str, Any]]:
    """
    Resolve project metadata with MMI-aware preference when duplicate records share the same Aha idea.
    Honors the active portfolio filter.
    """
    mongo_helper = MongoDBHelper()
    collection = mongo_helper.collection

    # Exact key lookup first
    exact_doc = collection.find_one({"_id": project_key})

    # Exact lookup by idea and MMI strategic theme
    idea_doc = collection.find_one({"idea": project_key})
    st_doc = collection.find_one({"strategic_theme_mmi": project_key})

    # Gather candidates by idea as well (handles duplicate legacy/MMI docs)
    candidates = []
    if exact_doc:
        candidates.append(exact_doc)
    if idea_doc and not any(existing.get('_id') == idea_doc.get('_id') for existing in candidates):
        candidates.append(idea_doc)
    if st_doc and not any(existing.get('_id') == st_doc.get('_id') for existing in candidates):
        candidates.append(st_doc)

    idea_value = project_key
    if exact_doc and exact_doc.get('idea'):
        idea_value = exact_doc.get('idea')
    elif idea_doc and idea_doc.get('idea'):
        idea_value = idea_doc.get('idea')
    elif st_doc and st_doc.get('idea'):
        idea_value = st_doc.get('idea')

    for doc in collection.find({"idea": idea_value}):
        if not any(existing.get('_id') == doc.get('_id') for existing in candidates):
            candidates.append(doc)

    # Fuzzy fallback if still unresolved (ST/Aha typos)
    if not candidates:
        normalized_target = _normalize_identifier(project_key)
        for doc in collection.find({}, {'_id': 1, 'idea': 1, 'strategic_theme_mmi': 1, 'bc': 1}):
            if not _record_matches_active_filter(doc):
                continue
            identifiers = _collect_identifier_values(doc)
            if any(_normalize_identifier(identifier) == normalized_target for identifier in identifiers):
                candidates.append(doc)
                break

        if not candidates and normalized_target:
            # prefix-based fuzzy: ST21564 can resolve to ST21563 family if unique in filter scope
            family_matches = []
            prefix = normalized_target[:6] if len(normalized_target) >= 6 else normalized_target
            for doc in collection.find({}, {'_id': 1, 'idea': 1, 'strategic_theme_mmi': 1, 'bc': 1}):
                if not _record_matches_active_filter(doc):
                    continue
                identifiers = _collect_identifier_values(doc)
                if any(_normalize_identifier(identifier).startswith(prefix) for identifier in identifiers if prefix):
                    family_matches.append(doc)
            if len(family_matches) == 1:
                candidates.append(family_matches[0])

    if not candidates:
        return None

    # Respect active filter first
    filtered = [doc for doc in candidates if _record_matches_active_filter(doc)]
    candidates = filtered if filtered else candidates

    # Prefer exact key if it is MMI or if filter explicitly legacy
    if exact_doc and exact_doc in candidates:
        exact_bc = str(exact_doc.get('bc', 'LEGACY') or 'LEGACY').upper()
        if _PROJECT_PORTFOLIO_FILTER == 'legacy':
            return exact_doc
        if exact_bc == 'MMI':
            return exact_doc

    # Prefer MMI in ALL/MMI scopes when duplicates exist
    if _PROJECT_PORTFOLIO_FILTER in {'all', 'mmi'}:
        mmi_docs = [doc for doc in candidates if str(doc.get('bc', 'LEGACY') or 'LEGACY').upper() == 'MMI']
        if mmi_docs:
            # If input looks like an MMI idea key, prefer exact _id match among MMI docs
            if re.match(r'^USPPI', str(project_key), re.IGNORECASE):
                for doc in mmi_docs:
                    if str(doc.get('_id')) == str(project_key):
                        return doc
            return mmi_docs[0]

    # Fallback to exact doc if possible, otherwise first candidate
    if exact_doc and exact_doc in candidates:
        return exact_doc
    return candidates[0]


def _summarize_text(text: str, max_sentences: int = 3, max_chars: int = 500) -> str:
    """Create a concise deterministic summary from long free-text content."""
    raw = str(text or '').strip()
    if not raw:
        return "Not available"

    # Normalize whitespace and markdown bullets/emojis for concise display
    cleaned = re.sub(r'\s+', ' ', raw.replace('✅', '').replace('⚠️', '').replace('➡️', '')).strip()

    # Prefer sentence-based summarization
    parts = re.split(r'(?<=[.!?])\s+', cleaned)
    selected = []
    for part in parts:
        chunk = part.strip(' -•')
        if not chunk:
            continue
        selected.append(chunk)
        if len(selected) >= max_sentences:
            break

    if not selected:
        summary = cleaned[:max_chars].strip()
        return summary + ('...' if len(cleaned) > max_chars else '')

    summary = ' '.join(selected)
    if len(summary) > max_chars:
        summary = summary[:max_chars].rsplit(' ', 1)[0].strip() + '...'
    return summary


def _normalize_percent(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {'nan', 'none'}:
        return None
    try:
        pct = float(text.replace('%', ''))
    except ValueError:
        return None
    if pct <= 1:
        pct *= 100
    return pct


def _format_date_mmddyy(value: Any) -> str:
    text = str(value).strip() if value is not None else ''
    if not text or text.lower() in {'nan', 'none'}:
        return "N/A"

    # Common datetime/date formats seen from Smartsheet extracts
    formats = [
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d',
        '%m/%d/%Y',
        '%m/%d/%y',
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(text, fmt)
            return dt.strftime('%m/%d/%y')
        except ValueError:
            continue

    # Fallback: keep original if unparsable
    return text


def _parse_date(value: Any) -> Optional[datetime]:
    text = str(value).strip() if value is not None else ''
    if not text or text.lower() in {'nan', 'none'}:
        return None

    formats = [
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d',
        '%m/%d/%Y',
        '%m/%d/%y',
    ]

    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    return None


def _status_is_complete(value: Any) -> bool:
    text = str(value or '').strip().lower()
    if not text:
        return False
    complete_terms = [
        'complete',
        'completed',
        'done',
        'closed',
        'cancelled',
        'canceled',
    ]
    return any(term in text for term in complete_terms)


def _find_column_name(columns: List[str], desired_pairs: List[List[str]]) -> Optional[str]:
    normalized = [(col, re.sub(r'\s+', ' ', str(col).strip().lower())) for col in columns]
    for col, lowered in normalized:
        for pair in desired_pairs:
            if all(token in lowered for token in pair):
                return col
    return None


def _find_task_name_columns(columns: List[str]) -> List[str]:
    """Return Task Name candidate columns with exact 'Task Name' first."""
    normalized = [(col, re.sub(r'\s+', ' ', str(col).strip().lower())) for col in columns]
    exact = [col for col, lowered in normalized if lowered == 'task name']
    partial = [col for col, lowered in normalized if ('task' in lowered and 'name' in lowered and lowered != 'task name')]
    return exact + partial


def _find_task_description_columns(columns: List[str]) -> List[str]:
    """Return Task Description candidate columns with exact name first."""
    normalized = [(col, re.sub(r'\s+', ' ', str(col).strip().lower())) for col in columns]
    exact = [col for col, lowered in normalized if lowered == 'task description']
    partial = [col for col, lowered in normalized if ('task' in lowered and 'description' in lowered and lowered != 'task description')]
    return exact + partial


# ================================================================================================
# AGENT STATE
# ================================================================================================

class AgentState(TypedDict):
    """State that gets passed through the agent graph"""
    messages: Annotated[List, add_messages]


# ================================================================================================
# TOOL DEFINITIONS
# ================================================================================================

@tool
def get_project_list() -> str:
    """
    Get a lightweight summary of all projects (metadata only, no detailed plans).
    
    Use this tool FIRST when answering questions to:
    - See what projects exist
    - Get high-level info (status, dates, BDL, RDL, etc.)
    - Identify which specific projects to query in detail
    
    This tool is fast and uses minimal tokens. After reviewing this data,
    use get_project_details() for specific projects that need detailed analysis.
    
    Returns:
        str: Formatted summary table of all projects
    """
    context = get_metadata_only_summary(portfolio_filter=_PROJECT_PORTFOLIO_FILTER)
    return f"""Here is the project portfolio summary:

{context}

If you need detailed plan data for specific projects, use get_project_details() next.
"""


@tool
def get_project_details(project_theme: str) -> str:
    """
    Get detailed project plan data for a SPECIFIC project by its strategic theme ID.
    
    This includes:
    - Full metadata
    - Complete Smartsheet plan (Markdown tables)
    - Work breakdown structure with tasks, dates, estimates
    - Financials section
    - Application view with progress by team
    - Impacted applications (Aha impacts)
    
    Use this tool AFTER get_project_list() to drill into specific projects.
    
    Args:
        project_theme: The strategic theme ID (e.g., "GNP-1234", "PD-5678")
        
    Returns:
        str: Complete project data including detailed plan
    """
    context = get_project_context(project_theme, include_plan=True, portfolio_filter=_PROJECT_PORTFOLIO_FILTER)

    if not context:
        resolved = _resolve_project_record(project_theme)
        if not resolved:
            return f"Project '{project_theme}' not found. Use get_project_list() to see available projects."
        resolved_key = str(resolved.get('_id', project_theme))
        context = format_project_with_plan(resolved_key, resolved, include_plan=True)
    
    return f"""Here is the detailed data for project {project_theme}:

{context}
"""


@tool
def get_project_summary(project_theme: str) -> str:
    """
    Get metadata-only summary for a specific project (no full plan markdown).

    Use this FIRST for direct project questions (status, owner, high-level overview)
    to avoid loading full plan tables unnecessarily.

    Args:
        project_theme: The strategic theme ID (or key) of the project

    Returns:
        str: Lightweight metadata summary
    """
    context = get_project_context(project_theme, include_plan=False, portfolio_filter=_PROJECT_PORTFOLIO_FILTER)

    if not context:
        resolved = _resolve_project_record(project_theme)
        if not resolved:
            return f"Project '{project_theme}' not found. Use search_projects() to find the correct project key first."
        resolved_key = str(resolved.get('_id', project_theme))
        context = format_project_with_plan(resolved_key, resolved, include_plan=False)

    return f"""Here is the project summary for {project_theme}:

{context}
"""


@tool
def get_project_high_level_update(project_theme: str) -> str:
    """
    Get a deterministic high-level update for a project from metadata only.

    For MMI projects, this prioritizes:
    - overall_status_mmi
    - executive_summary_mmi

    Use this tool for questions like:
    - "What's the executive summary for this project?"
    - "What's the latest on <project>?"
    - "Give me a status update"
    - "How is this project progressing?"
    """
    project_data = _resolve_project_record(project_theme)

    if not project_data:
        suggestions = _suggest_project_identifiers(project_theme)
        if suggestions:
            suggestion_lines = "\n".join([f"- {item}" for item in suggestions])
            return (
                f"Project '{project_theme}' not found.\n\n"
                f"Did you mean:\n{suggestion_lines}\n\n"
                f"Tip: You can ask using either Aha ID (e.g., USPP...) or Strategic Theme (e.g., ST...)."
            )
        return (
            f"Project '{project_theme}' not found. "
            f"Use search_projects() to find the correct project key first."
        )

    bc = str(project_data.get('bc', 'LEGACY') or 'LEGACY').upper()
    project_name = project_data.get('name', 'Unknown')
    idea = project_data.get('idea', 'N/A')

    # MMI-first fields
    if bc == 'MMI':
        strategic_theme = project_data.get('strategic_theme_mmi', 'N/A')
        prj_number = project_data.get('prj') or project_data.get('project_number_mmi')
        overall_status = project_data.get('overall_status_mmi')
        executive_summary = project_data.get('executive_summary_mmi')
        go_live = project_data.get('go_live_date_mmi')

        prj_number = prj_number if prj_number else "Not available in MMI summary metadata"
        overall_status = overall_status if overall_status else "Not available in MMI summary metadata"
        executive_summary = executive_summary if executive_summary else "Not available in MMI summary metadata"
        go_live = go_live if go_live else "Not available in MMI summary metadata"
        executive_summary_brief = _summarize_text(executive_summary)

        return (
            f"High-level update for {project_name} ({project_theme}):\n\n"
            f"Overall Status: {overall_status}\n\n"
            f"Executive Summary (concise): {executive_summary_brief}\n\n"
            f"Strategic Theme: {strategic_theme} | PRJ Number: {prj_number} | Go-Live: {go_live}"
        )

    # Legacy fallback
    strategic_theme = project_theme
    prj_number = project_data.get('prj', 'N/A')
    overall_status = project_data.get('status', 'N/A')
    executive_summary = project_data.get('notes', 'N/A')
    go_live = project_data.get('go live', 'N/A')
    executive_summary_brief = _summarize_text(executive_summary)

    return (
        f"High-level update for {project_name} ({project_theme}):\n\n"
        f"Overall Status: {overall_status}\n\n"
        f"Executive Summary (concise): {executive_summary_brief}\n\n"
        f"Strategic Theme: {strategic_theme} | PRJ Number: {prj_number} | Aha Idea: {idea} | Go-Live: {go_live}"
    )


@tool
def get_mmi_task_progress(project_theme: str, task_identifier: str) -> str:
    """
    Get deterministic task-level progress for an MMI feature/capability/milestone from Program Plan.

    For MMI projects, task IDs such as Fxxxxx/Cxxxxx are stored in the Task Name column.
    This tool reads the Program Plan and returns % Complete for the matching Task Name row.
    """
    project_data = _resolve_project_record(project_theme)

    if not project_data:
        return f"Project '{project_theme}' not found."

    bc = str(project_data.get('bc', 'LEGACY') or 'LEGACY').upper()
    if bc != 'MMI':
        return (
            f"Project '{project_theme}' is not an MMI project (BC={bc}). "
            f"Use standard project detail queries for legacy formats."
        )

    sheet_id = project_data.get('program_plan_sheet_id')
    if not sheet_id:
        return f"No Program Plan sheet ID found for project '{project_theme}'."

    try:
        df = smartsheet_to_pandas(sheet_id)
    except Exception as e:
        return f"Unable to load Program Plan for '{project_theme}': {e}"

    if df is None or df.empty:
        return f"Program Plan is empty for project '{project_theme}'."

    task_name_cols = _find_task_name_columns(list(df.columns))
    percent_col = _find_column_name(list(df.columns), [['%', 'complete'], ['percent', 'complete']])
    status_col = _find_column_name(list(df.columns), [['status']])

    if not task_name_cols or not percent_col:
        return (
            f"Required columns were not found in Program Plan for '{project_theme}'. "
            f"Expected Task Name and % Complete columns."
        )

    identifier = str(task_identifier).strip()
    if not identifier:
        return "task_identifier is required (for example F1757625)."

    pattern = re.compile(rf'\b{re.escape(identifier)}\b', re.IGNORECASE)

    matches = None
    matched_task_col = None
    for task_col in task_name_cols:
        candidate = df[df[task_col].fillna('').astype(str).str.contains(pattern, na=False)]
        if not candidate.empty:
            matches = candidate
            matched_task_col = task_col
            break

    if matches is None or matches.empty:
        return f"Task '{identifier}' was not found in Task Name for project '{project_theme}'."

    row = matches.iloc[0]
    task_name = str(row.get(matched_task_col, '')).strip()
    pct_value = _normalize_percent(row.get(percent_col))
    pct_text = f"{pct_value:.1f}%" if pct_value is not None else "N/A"

    status_text = "N/A"
    if status_col:
        status_text = str(row.get(status_col, '')).strip() or "N/A"

    return (
        f"Task progress for {identifier} in {project_theme}:\n\n"
        f"- Task Name: {task_name}\n"
        f"- % Complete: {pct_text}\n"
        f"- Status: {status_text}"
    )


@tool
def get_project_milestone_timeline(project_theme: str, milestone_name: str) -> str:
    """
    Get timeline for a milestone/task by name from project plan data.

    Matching strategy:
    - Search milestone text in Task Name first
    - Then Task Description
    - Return Start and Finish dates (and status if available)
    """
    project_data = _resolve_project_record(project_theme)
    if not project_data:
        return f"Project '{project_theme}' not found."

    # MMI uses program_plan_sheet_id, legacy uses sheet id
    sheet_id = project_data.get('program_plan_sheet_id') or project_data.get('sheet id')
    if not sheet_id:
        return f"No project plan sheet ID found for project '{project_theme}'."

    try:
        df = smartsheet_to_pandas(sheet_id)
    except Exception as e:
        return f"Unable to load project plan for '{project_theme}': {e}"

    if df is None or df.empty:
        return f"Project plan is empty for project '{project_theme}'."

    milestone = str(milestone_name or '').strip()
    if not milestone:
        return "milestone_name is required (for example 'PCAT Testing Ready')."

    task_name_cols = _find_task_name_columns(list(df.columns))
    task_desc_cols = _find_task_description_columns(list(df.columns))
    start_col = _find_column_name(list(df.columns), [['start']])
    finish_col = _find_column_name(list(df.columns), [['finish']])
    status_col = _find_column_name(list(df.columns), [['status']])

    if not task_name_cols and not task_desc_cols:
        return f"Could not find Task Name/Task Description columns for project '{project_theme}'."

    pattern = re.compile(re.escape(milestone), re.IGNORECASE)

    def _find_matches(col_list: List[str]):
        for col in col_list:
            candidate = df[df[col].fillna('').astype(str).str.contains(pattern, na=False)]
            if not candidate.empty:
                return candidate, col
        return None, None

    matches, matched_col = _find_matches(task_name_cols)
    if matches is None:
        matches, matched_col = _find_matches(task_desc_cols)

    if matches is None or matches.empty:
        return (
            f"Milestone '{milestone}' was not found in Task Name/Task Description for project '{project_theme}'."
        )

    row = matches.iloc[0]
    task_name_display = ""
    if task_name_cols:
        task_name_display = str(row.get(task_name_cols[0], '')).strip()
    task_desc_display = ""
    if task_desc_cols:
        task_desc_display = str(row.get(task_desc_cols[0], '')).strip()

    start_val = row.get(start_col, '') if start_col else ''
    finish_val = row.get(finish_col, '') if finish_col else ''
    status_val = str(row.get(status_col, '')).strip() if status_col else ''

    start_text = _format_date_mmddyy(start_val)
    finish_text = _format_date_mmddyy(finish_val)
    status_text = status_val if status_val else "N/A"

    return (
        f"Timeline for '{milestone}' in {project_theme}:\n\n"
        f"- Matched Column: {matched_col}\n"
        f"- Task Name: {task_name_display or 'N/A'}\n"
        f"- Task Description: {task_desc_display or 'N/A'}\n"
        f"- Start: {start_text}\n"
        f"- Finish: {finish_text}\n"
        f"- Status: {status_text}"
    )


@tool
def get_overdue_capabilities_features(project_theme: str) -> str:
    """
    Deterministically list overdue capabilities/features for MMI and legacy projects.

    Criteria:
    - Task identifier must be capability/feature ID (Cxxxxx/Fxxxxx)
    - Completion date is in the past (using Finish/End/Due/Completion columns)
    - Item is not complete/done/closed/cancelled
    """
    project_data = _resolve_project_record(project_theme)
    if not project_data:
        return f"Project '{project_theme}' not found."

    bc = str(project_data.get('bc', 'LEGACY') or 'LEGACY').upper()

    sheet_id = project_data.get('program_plan_sheet_id') or project_data.get('sheet id')
    if not sheet_id:
        return f"No project plan sheet ID found for project '{project_theme}'."

    try:
        df = smartsheet_to_pandas(sheet_id)
    except Exception as e:
        return f"Unable to load project plan for '{project_theme}': {e}"

    if df is None or df.empty:
        return f"Project plan is empty for project '{project_theme}'."

    columns = list(df.columns)
    task_name_cols = _find_task_name_columns(columns)
    task_desc_cols = _find_task_description_columns(columns)
    status_col = _find_column_name(columns, [['status']])
    percent_col = _find_column_name(columns, [['%', 'complete'], ['percent', 'complete']])
    if bc == 'MMI':
        id_candidates = [
            ['capability', 'id'],
            ['feature', 'id'],
            ['task', 'id'],
        ]
        date_candidates = [
            [['finish']],
            [['planned', 'finish']],
            [['target', 'finish']],
            [['end']],
            [['due']],
            [['completion', 'date']],
            [['complete', 'date']],
        ]
    else:
        id_candidates = [
            ['task', 'id'],
            ['work', 'breakdown'],
            ['wbs'],
            ['capability', 'id'],
            ['feature', 'id'],
        ]
        date_candidates = [
            [['finish']],
            [['target', 'finish']],
            [['planned', 'finish']],
            [['end', 'date']],
            [['due', 'date']],
            [['completion', 'date']],
            [['complete', 'date']],
        ]

    capability_id_col = _find_column_name(columns, id_candidates)

    completion_date_cols: List[str] = []
    for candidate in date_candidates:
        col = _find_column_name(columns, candidate)
        if col and col not in completion_date_cols:
            completion_date_cols.append(col)

    if not task_name_cols and not task_desc_cols and not capability_id_col:
        return (
            f"Could not find task text or capability/feature ID columns for project '{project_theme}'."
        )

    if not completion_date_cols:
        return (
            f"Could not find completion date columns (Finish/End/Due) for project '{project_theme}'."
        )

    today = datetime.now().date()
    cf_pattern = re.compile(r'\b([CF]\d{5,})\b', re.IGNORECASE)
    overdue_items: List[Dict[str, Any]] = []

    for _, row in df.iterrows():
        identifier = None

        if capability_id_col:
            cap_value = str(row.get(capability_id_col, '')).strip()
            cap_match = re.search(r'^([CF]\d{5,})$', cap_value, flags=re.IGNORECASE)
            if cap_match:
                identifier = cap_match.group(1).upper()

        matched_task_name = ''
        if not identifier:
            for task_col in task_name_cols:
                task_text = str(row.get(task_col, '')).strip()
                if not task_text:
                    continue
                match = cf_pattern.search(task_text)
                if match:
                    identifier = match.group(1).upper()
                    matched_task_name = task_text
                    break

        if not identifier:
            for task_desc_col in task_desc_cols:
                desc_text = str(row.get(task_desc_col, '')).strip()
                if not desc_text:
                    continue
                match = cf_pattern.search(desc_text)
                if match:
                    identifier = match.group(1).upper()
                    break

        if not identifier:
            continue

        raw_status = row.get(status_col, '') if status_col else ''
        if _status_is_complete(raw_status):
            continue

        pct = _normalize_percent(row.get(percent_col)) if percent_col else None
        if pct is not None and pct >= 100:
            continue

        completion_dt = None
        completion_source = None
        completion_raw = ''
        for date_col in completion_date_cols:
            raw_value = row.get(date_col, '')
            parsed = _parse_date(raw_value)
            if parsed is not None:
                completion_dt = parsed
                completion_source = date_col
                completion_raw = raw_value
                break

        if completion_dt is None:
            continue

        if completion_dt.date() < today:
            task_name_value = matched_task_name
            if not task_name_value and task_name_cols:
                task_name_value = str(row.get(task_name_cols[0], '')).strip()

            task_desc_value = ''
            if task_desc_cols:
                task_desc_value = str(row.get(task_desc_cols[0], '')).strip()

            overdue_items.append({
                'id': identifier,
                'task_name': task_name_value,
                'task_description': task_desc_value,
                'status': str(raw_status).strip() or 'N/A',
                'completion_date': _format_date_mmddyy(completion_raw),
                'completion_col': completion_source,
                'sort_date': completion_dt,
            })

    overdue_items.sort(key=lambda item: item['sort_date'])

    if not overdue_items:
        return (
            f"No overdue capabilities/features (C*/F*) were found for '{project_theme}'. "
            f"Criteria: past completion date and not marked complete."
        )

    lines = [
        f"Overdue capabilities/features for {project_theme} (BC={bc}):",
        "",
        f"Count: {len(overdue_items)}",
        "",
    ]

    for item in overdue_items:
        lines.append(
            f"- {item['id']} | Finish: {item['completion_date']} | Status: {item['status']} | Task Name: {item['task_name'] or 'N/A'}"
        )

    return "\n".join(lines)


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {'nan', 'none'}:
        return None
    text = text.replace('$', '').replace(',', '').replace('%', '').strip()
    try:
        return float(text)
    except ValueError:
        return None


def _find_first_column(columns: List[str], candidates: List[List[str]]) -> Optional[str]:
    normalized = [(col, re.sub(r'\s+', ' ', str(col).strip().lower())) for col in columns]
    for tokens in candidates:
        for col, lowered in normalized:
            if all(token in lowered for token in tokens):
                return col
    return None


@tool
def get_mmi_financial_overview(project_theme: str) -> str:
    """
    Deterministic financial overview for MMI projects using Budget-PPMO Export.

    Returns aggregate Actuals, ETC, EAC, Aha Budget, Burn %, and Variance based on budget sheet data.
    """
    project_data = _resolve_project_record(project_theme)
    if not project_data:
        return f"Project '{project_theme}' not found."

    bc = str(project_data.get('bc', 'LEGACY') or 'LEGACY').upper()
    if bc != 'MMI':
        return (
            f"Project '{project_theme}' is not an MMI project (BC={bc}). "
            f"Use standard project detail queries for legacy financials."
        )

    budget_sheet_id = project_data.get('budget_sheet_id')
    if not budget_sheet_id:
        return f"No Budget-PPMO Export sheet ID found for project '{project_theme}'."

    try:
        df = smartsheet_to_pandas(budget_sheet_id)
    except Exception as e:
        return f"Unable to load Budget-PPMO Export for '{project_theme}': {e}"

    if df is None or df.empty:
        return f"Budget-PPMO Export is empty for project '{project_theme}'."

    # Normalize column keys by removing non-alphanumeric characters so
    # variants like "Actuals($)" or "Actuals from PPMO($)" match "actuals"
    normalized_columns = {}
    for col in list(df.columns):
        key = re.sub(r'[^a-z0-9]', '', str(col).strip().lower())
        normalized_columns[key] = col

    # Canonical MMI financial source columns only (do not use PPMO-derived alternatives)
    actuals_col = normalized_columns.get('actuals')
    etc_col = normalized_columns.get('etc')
    eac_col = normalized_columns.get('eac')
    budget_col = _find_first_column(list(df.columns), [['budget from aha'], ['approved budget']])
    burn_col = _find_first_column(list(df.columns), [['percentage burned']])
    variance_col = _find_first_column(list(df.columns), [['variance', 'budget', 'eac']])

    missing_core = [
        name for col, name in [
            (actuals_col, 'Actuals'),
            (etc_col, 'ETC'),
            (eac_col, 'EAC'),
        ] if not col
    ]

    if missing_core:
        return (
            f"Could not find required canonical financial columns in Budget-PPMO Export for '{project_theme}': "
            f"{', '.join(missing_core)}. "
            f"Expected exact columns: Actuals, ETC, EAC."
        )

    def col_sum(col_name: Optional[str]) -> float:
        if not col_name:
            return 0.0
        return float(sum(v for v in (_to_float(x) for x in df[col_name].tolist()) if v is not None))

    def first_row_or_sum(col_name: Optional[str]) -> float:
        """Use the first row value as a roll-up if present, otherwise fall back to summing the column."""
        if not col_name or df is None or df.empty:
            return 0.0
        try:
            first_val = _to_float(df[col_name].iloc[0])
        except Exception:
            first_val = None
        if first_val is not None:
            return float(first_val)
        return col_sum(col_name)

    # Prefer budget column detected by normalized name if available
    if not budget_col:
        budget_col = normalized_columns.get('budget') or normalized_columns.get('budgetfromaha')

    total_actuals = first_row_or_sum(actuals_col)
    total_etc = first_row_or_sum(etc_col)
    total_eac = first_row_or_sum(eac_col)
    total_budget = first_row_or_sum(budget_col)

    # Variance per request: Budget total - EACs total
    total_variance = (total_budget - total_eac) if (total_budget is not None and total_eac is not None) else 0.0

    if burn_col:
        burns = [_to_float(x) for x in df[burn_col].tolist()]
        burns = [b for b in burns if b is not None]
        burn_pct = (sum(burns) / len(burns) * 100) if burns and max(burns) <= 1 else (sum(burns) / len(burns) if burns else 0.0)
    else:
        burn_pct = (total_actuals / total_eac * 100) if total_eac else 0.0

    project_name = project_data.get('name', 'Unknown')
    strategic_theme = project_data.get('strategic_theme_mmi', 'N/A')

    return (
        f"MMI financial overview for {project_name} ({project_theme}):\n\n"
        f"- Strategic Theme: {strategic_theme}\n"
        f"- Total Actuals: ${total_actuals:,.2f}\n"
        f"- Total ETC: ${total_etc:,.2f}\n"
        f"- Total EAC: ${total_eac:,.2f}\n"
        f"- Total Budget (Aha): ${total_budget:,.2f}\n"
        f"- Total Variance (Budget-EAC): ${total_variance:,.2f}\n"
        f"- Percentage Burned: {burn_pct:.1f}%"
    )


@tool
def search_projects(search_term: str, search_in_detailed_plans: bool = False) -> str:
    """
    Search across all projects for specific criteria (teams, applications, people, keywords).
    
    Use this tool when you need to:
    - Find which projects a specific team/application is impacted in
    - Locate projects by person (BDL, RDL, or team member)
    - Search for specific keywords across projects
    - Get a summary of projects matching certain criteria
    
    This is MUCH more efficient than loading all project details!
    
    Args:
        search_term: What to search for (e.g., "BASICS", "John Smith", "Cloud Migration")
        search_in_detailed_plans: Set to True to search within full Smartsheet plans (slower but thorough).
                                  Set to False to search only metadata (faster, good for BDL/RDL/status).
                                  
    Returns:
        str: List of matching projects with relevant context
        
    Examples:
        - search_projects("BASICS", True) → finds all projects where BASICS team is mentioned
        - search_projects("Sarah Johnson", False) → finds projects with Sarah as BDL/RDL
        - search_projects("API Integration", True) → finds projects mentioning API work
    """
    results = search_projects_by_criteria(
        search_term,
        search_in_plans=search_in_detailed_plans,
        portfolio_filter=_PROJECT_PORTFOLIO_FILTER,
    )
    return results


# @tool
# def create_user_alert(
#     user_name: str,
#     message: str,
#     st: Optional[str] = None,
#     next_steps: Optional[str] = None
# ) -> Dict[str, Any]:
#     """
#     Create an alert for a specific user when they need to take action on a project.
    
#     IMPORTANT - Generate recommended next steps based on the alert type:
    
#     INSTRUCTIONS FOR NEXT STEPS:
#     - Financial updates: Depending on the context, suggest actions like "update PPM Optics", "get allocations"
#     - Timeline delays: Depending on the context, suggest actions like "update the Smartsheet plan", "adjust dates", "notify correct people"
#     - Data quality: Depending on the context, suggestion actions like "validate data", "update records with correct information", "align data with Rally, Aha, or Optics" (if the work is related to a feature or capability, Rally should be mentioned, if work is related to an impact, Aha should be mentioned, if work is related to financials, Optics should be mentioned)
#     - Dependency issues: Depending on the context, suggest actions like "Contact certain impacted application teams", "confirm or gather delivery dates", "update project plan accordingly"
#     - General updates: "Review project details in system, make necessary updates, confirm changes with team"
    
#     These are purely examples - the exact verbiage should be tailored to the specific alert context.
#     Customize the next steps to be specific and actionable based on the alert context.
    
#     Args:
#         user_name: The full name of the user to alert (e.g., 'Kathy Smith', 'Chris Capewell')
#         message: The alert message describing what needs to be done
#         st: The strategic theme ID if applicable (e.g., 'ST15926')
#         next_steps: AI-generated recommended next steps - be specific and actionable. Include 2-3 concrete actions the user should take.
        
#     Returns:
#         dict: Created alert data
#     """
#     mongo_helper = MongoDBHelper()
    
#     # Create alert document
#     alert = {
#         "user_name": user_name,
#         "message": message,
#         "st": st,
#         "next_steps": next_steps,
#         "created_at": datetime.now().isoformat(),
#         "resolved": False
#     }
    
#     # Store in MongoDB alerts collection
#     db = mongo_helper.db
#     alerts_collection = db['user_alerts']
#     result = alerts_collection.insert_one(alert)
    
#     return {
#         "success": True,
#         "alert_id": str(result.inserted_id),
#         "user_name": user_name,
#         "message": f"Alert created for {user_name}"
#     }


@tool
def draft_email(
    recipient_name: str,
    subject: str,
    body: str,
    cc: Optional[str] = None
) -> Dict[str, Any]:
    """
    Open Outlook (or default email client) with a pre-filled draft email ready to send.
    Use this when the user wants to email someone about a project.
    The recipient name will be used directly and Outlook will resolve it from the corporate directory.
    
    FOR INFORMATION REQUESTS (allocations, Optics data, financial info, etc.), USE THIS TEMPLATE:
    
    Subject: Request for [Impacted Application Team Name] Optics Allocations - [Project/Theme]
    Body: Hi,
    
    I hope you are doing well. I am reaching out for Optics resource / hour allocations for [project/theme name].
    
    Please provide me the following information for each resource:
    - Resource ID
    - Resource Name
    - Number of Hours
    
    Please let me know if you have any questions.
    
    Thank You,
    **Your Name**
    
    Args:
        recipient_name: The full name of the recipient as it appears in Outlook (e.g., 'Chris Capewell', 'Rahil Sharma'). Email address is NOT needed.
        subject: The email subject line - follow the template format for requests
        body: The email body content
        cc: Optional CC recipient names (comma-separated)
        
    Returns:
        dict: Email draft data with mailto URL
    """
    import urllib.parse
    
    # Convert "First Last" to "Last First" format for Outlook directory search
    name_parts = recipient_name.strip().split()
    if len(name_parts) >= 2:
        first_name = ' '.join(name_parts[:-1])
        last_name = name_parts[-1]
        formatted_name = f"{last_name} {first_name}"
    else:
        formatted_name = recipient_name
    
    # URL encode all fields
    encoded_recipient = urllib.parse.quote(formatted_name)
    encoded_subject = urllib.parse.quote(subject)
    encoded_body = urllib.parse.quote(body)
    
    # Build mailto URL
    mailto_url = f"mailto:{encoded_recipient}?subject={encoded_subject}&body={encoded_body}"
    
    if cc:
        cc_names = [name.strip() for name in cc.split(',')]
        formatted_cc_names = []
        for cc_name in cc_names:
            cc_parts = cc_name.split()
            if len(cc_parts) >= 2:
                cc_formatted = f"{cc_parts[-1]} {' '.join(cc_parts[:-1])}"
                formatted_cc_names.append(cc_formatted)
            else:
                formatted_cc_names.append(cc_name)
        encoded_cc = urllib.parse.quote(','.join(formatted_cc_names))
        mailto_url += f"&cc={encoded_cc}"
    
    # Save the email draft info
    email_file = 'documents/email_draft.json'
    email_data = {
        "recipient_name": formatted_name,
        "subject": subject,
        "body": body,
        "cc": cc,
        "mailto_url": mailto_url,
        "timestamp": datetime.now().isoformat()
    }
    
    with open(email_file, 'w') as f:
        json.dump(email_data, f, indent=4)
    
    return {
        "success": True,
        "email_draft": email_data,
        "message": f"Email draft has been created and is ready to send.\n\n**Recipient:** {formatted_name}\n**Subject:** {subject}\n**Body:**\n{body}\n\n[OPEN_OUTLOOK:{mailto_url}]"
    }


@tool
def generate_report(
    report_title: str,
    table_data_json: str,
    format: str = "csv"
) -> Dict[str, Any]:
    """
    Generate a downloadable report (CSV or Excel) from structured table data.
    Use this when the user wants to export, download, or generate a report of project data.
    
    IMPORTANT: You must first query the data and structure it, then pass it to this tool as JSON.
    
    Example workflow:
    1. User asks for a table of data
    2. You query the data and display it
    3. User asks to export/download
    4. You call this tool with the table data in JSON format
    
    Args:
        report_title: Title/name for the report file (e.g., "At_Risk_Projects", "Budget_Analysis")
        table_data_json: JSON string containing the table data. Format: '[{"col1": "val1", "col2": "val2"}, ...]'
        format: File format - "csv" or "excel" (default: "csv")
        
    Returns:
        dict: Report generation status with download information
    """
    import pandas as pd
    from datetime import datetime
    import os
    
    # Create reports directory if it doesn't exist
    reports_dir = 'documents/reports'
    os.makedirs(reports_dir, exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    safe_title = report_title.replace(' ', '_').replace('/', '_')
    
    if format.lower() == "excel":
        filename = f"{safe_title}_{timestamp}.xlsx"
    else:
        filename = f"{safe_title}_{timestamp}.csv"
    
    filepath = os.path.join(reports_dir, filename)
    
    try:
        # Parse JSON data
        import json
        data = json.loads(table_data_json)
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        # Save to file
        if format.lower() == "excel":
            df.to_excel(filepath, index=False, engine='openpyxl')
        else:
            df.to_csv(filepath, index=False)
        
        # Return success with download info
        return {
            "success": True,
            "filename": filename,
            "filepath": filepath,
            "row_count": len(df),
            "message": f"Report generated successfully: **{filename}**\n\nRows: {len(df)} | Columns: {len(df.columns)} | Format: {format.upper()}\n\n[DOWNLOAD_REPORT:{filepath}]"
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to generate report: {str(e)}"
        }


# ================================================================================================
# AGENT SETUP
# ================================================================================================

def create_project_agent(model_name: str = "enterprise-llm", temperature: float = 0.1):
    """
    Create the project management agent with tools.
    
    Args:
        model_name: LLM model to use (default gpt-4)
        temperature: Temperature for LLM responses (default 0.1 for consistency)
        
    Returns:
        Compiled LangGraph agent
    """
    tools = [
        get_project_list,
        get_project_summary,
        get_project_high_level_update,
        get_mmi_task_progress,
        get_project_milestone_timeline,
        get_overdue_capabilities_features,
        get_mmi_financial_overview,
        get_project_details,
        search_projects,
        draft_email,
        generate_report,
    ]

    # Create tool node
    tool_node = ToolNode(tools)
    client = EnterpriseLLMClient(Config())
    
    # Define agent node
    def agent_node(state: AgentState):
        """Agent reasoning node"""
        messages = state["messages"]
        content = client.generate_response(messages=messages, context="project_agent")
        return {"messages": [AIMessage(content=content)]}
    
    # Define conditional edge logic
    def should_continue(state: AgentState):
        """Decide whether to continue or end"""
        messages = state["messages"]
        last_message = messages[-1]
        
        # If there are no tool calls, we're done
        if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
            return "end"
        return "continue"
    
    # Build graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    
    # Set entry point
    workflow.set_entry_point("agent")
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "continue": "tools",
            "end": END
        }
    )
    
    # Add edge from tools back to agent
    workflow.add_edge("tools", "agent")
    
    # Compile
    app = workflow.compile()
    
    return app


# ================================================================================================
# AGENT INTERFACE
# ================================================================================================

class ProjectAgent:
    """High-level interface for the project management agent"""
    
    def __init__(self, model_name: str = "gpt-4", temperature: float = 0.1):
        self.model_name = model_name
        self.temperature = temperature
        self.system_prompt = PROJECT_AGENT_SYSTEM_PROMPT
        self.max_history_messages = 12
        self.max_graph_recursion = 14

    def _extract_project_identifier(self, user_input: str) -> Optional[str]:
        """Extract likely project identifier from user input for fallback handling."""
        patterns = [
            r'\bUSPP[A-Z]+-I-\d+\b',
            r'\bPSTRATEGIC-I-\d+\b',
            r'\bST\d+\b',
            r'\bGNP-\d+\b',
            r'\bPD-\d+\b',
        ]
        for pattern in patterns:
            match = re.search(pattern, user_input, flags=re.IGNORECASE)
            if match:
                return match.group(0)
        return None

    def _is_high_level_update_intent(self, user_input: str) -> bool:
        text = str(user_input or '').lower()
        intent_terms = [
            'status', 'overall status', 'executive summary', 'summary',
            'latest', 'latest on', 'update', 'status update', 'progress',
            'prj', 'prj number', 'project number'
        ]
        intent_phrases = [
            'tell me about',
            'about this project',
            'project overview',
            'high level',
            'how is this project',
            'how is the project',
        ]
        return any(term in text for term in intent_terms) or any(phrase in text for phrase in intent_phrases)

    def _extract_task_identifier(self, user_input: str) -> Optional[str]:
        text = str(user_input or '')
        match = re.search(r'\b([FC]\d{5,})\b', text, flags=re.IGNORECASE)
        if match:
            return match.group(1).upper()
        return None

    def _extract_milestone_name(self, user_input: str, project_identifier: Optional[str]) -> Optional[str]:
        text = str(user_input or '').strip()
        if not text or not project_identifier:
            return None

        patterns = [
            rf'timeline\s+of\s+(.+?)\s+for\s+{re.escape(project_identifier)}',
            rf'dates?\s+for\s+(.+?)\s+for\s+{re.escape(project_identifier)}',
            rf'when\s+is\s+(.+?)\s+for\s+{re.escape(project_identifier)}',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                milestone = match.group(1).strip(' ?"\'')
                if milestone:
                    return milestone
        return None

    def _is_financial_intent(self, user_input: str) -> bool:
        text = str(user_input or '').lower()
        terms = [
            'financial', 'actuals', 'etc', 'eac', 'budget', 'burn',
            'variance', 'cost', 'spend', 'funding'
        ]
        return any(term in text for term in terms)

    def _is_overdue_cf_intent(self, user_input: str) -> bool:
        text = str(user_input or '').lower()
        has_item_scope = any(term in text for term in [
            'capability', 'capabilities', 'feature', 'features', 'c/', 'f/',
        ]) or bool(re.search(r'\b[cf]\d{5,}\b', text, flags=re.IGNORECASE))

        has_overdue_signal = any(term in text for term in [
            'overdue',
            'past due',
            'completion date in the past',
            'finish date in the past',
            'date in the past',
            'late',
        ])

        has_incomplete_signal = any(term in text for term in [
            'not complete',
            'not completed',
            'not marked complete',
            'incomplete',
        ])

        return has_item_scope and (has_overdue_signal or has_incomplete_signal)
    
    def run(
        self,
        user_input: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        portfolio_filter: str = 'all'
    ) -> Dict[str, Any]:
        """
        Run the agent with user input and optional chat history.
        
        Args:
            user_input: User's question or request
            chat_history: Optional list of previous messages [{"role": "user"|"assistant", "content": "..."}]
            
        Returns:
            dict: Agent response with results
        """
        global _PROJECT_PORTFOLIO_FILTER
        normalized_filter = _normalize_portfolio_filter(portfolio_filter)
        _PROJECT_PORTFOLIO_FILTER = normalized_filter

        # Create agent with fresh token on each run
        agent = create_project_agent(self.model_name, self.temperature)
        
        # Build message list starting with system prompt
        filter_instruction = (
            "Active project scope filter: ALL projects."
            if normalized_filter == 'all'
            else (
                "Active project scope filter: MMI / Growth, New Product only. Do not use non-MMI projects."
                if normalized_filter == 'mmi'
                else "Active project scope filter: Legacy projects only. Do not use MMI projects."
            )
        )
        messages = [SystemMessage(content=self.system_prompt), SystemMessage(content=filter_instruction)]
        
        # Add chat history if provided
        if chat_history:
            trimmed_history = chat_history[-self.max_history_messages:]
            for msg in trimmed_history:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    messages.append(AIMessage(content=msg["content"]))
        
        # Add current user input
        messages.append(HumanMessage(content=user_input))

        # Deterministic fast path for explicit project high-level questions
        identifier = self._extract_project_identifier(user_input)
        task_identifier = self._extract_task_identifier(user_input)
        milestone_name = self._extract_milestone_name(user_input, identifier)

        if not identifier and chat_history:
            for msg in reversed(chat_history):
                if msg.get("role") == "user":
                    identifier = self._extract_project_identifier(msg.get("content", ""))
                    if identifier:
                        break

        if identifier and milestone_name:
            timeline_response = get_project_milestone_timeline.invoke(
                {
                    "project_theme": identifier,
                    "milestone_name": milestone_name,
                }
            )
            return {
                "response": timeline_response,
                "tool_calls": [],
                "full_conversation": messages,
            }

        if identifier and task_identifier:
            task_response = get_mmi_task_progress.invoke(
                {
                    "project_theme": identifier,
                    "task_identifier": task_identifier,
                }
            )
            return {
                "response": task_response,
                "tool_calls": [],
                "full_conversation": messages,
            }

        if identifier and self._is_financial_intent(user_input):
            financial_response = get_mmi_financial_overview.invoke({"project_theme": identifier})
            return {
                "response": financial_response,
                "tool_calls": [],
                "full_conversation": messages,
            }

        if identifier and self._is_overdue_cf_intent(user_input):
            overdue_response = get_overdue_capabilities_features.invoke({"project_theme": identifier})
            return {
                "response": overdue_response,
                "tool_calls": [],
                "full_conversation": messages,
            }

        if identifier and self._is_high_level_update_intent(user_input):
            fast_response = get_project_high_level_update.invoke({"project_theme": identifier})
            return {
                "response": fast_response,
                "tool_calls": [],
                "full_conversation": messages,
            }
        
        # Create initial state
        initial_state = {"messages": messages}
        
        # Run agent
        try:
            result = agent.invoke(initial_state, config={"recursion_limit": self.max_graph_recursion})
        except Exception as e:
            error_text = str(e)
            if "Recursion limit" in error_text or "GRAPH_RECURSION_LIMIT" in error_text:
                # Deterministic fallback for common project-specific summary/status questions
                identifier = self._extract_project_identifier(user_input)
                if identifier:
                    fallback_response = get_project_high_level_update.invoke({"project_theme": identifier})
                    return {
                        "response": f"{fallback_response}\n\n(Note: Used deterministic fallback due to tool-loop limit.)",
                        "tool_calls": [],
                        "full_conversation": messages,
                    }

                raise RuntimeError(
                    "The AI took too many tool steps for this query. "
                    "Please try a more specific project question (for example including the project key)."
                )
            raise
        
        # Extract final response
        messages = result["messages"]
        final_message = messages[-1]
        
        return {
            "response": final_message.content if hasattr(final_message, "content") else str(final_message),
            "tool_calls": [msg for msg in messages if hasattr(msg, "tool_calls") and msg.tool_calls],
            "full_conversation": messages
        }


# ================================================================================================
# CLI INTERFACE FOR TESTING
# ================================================================================================

if __name__ == "__main__":
    print("Project Management Agent")
    print("=" * 80)
    print("\nCapabilities:")
    print("1. Answer questions about projects")
    print("2. Create user alerts")
    print("3. Generate email drafts")
    print("\nType 'exit' to quit\n")
    
    agent = ProjectAgent()
    
    while True:
        user_input = input("\n👤 You: ").strip()
        
        if user_input.lower() in ['exit', 'quit', 'q']:
            print("Goodbye!")
            break
        
        if not user_input:
            continue
        
        print("\nAgent: ", end="", flush=True)
        
        try:
            result = agent.run(user_input)
            print(result["response"])
            
            # Show tool calls if any
            if result["tool_calls"]:
                print("\nTools used:")
                for msg in result["tool_calls"]:
                    if hasattr(msg, "tool_calls"):
                        for tool_call in msg.tool_calls:
                            print(f"  - {tool_call['name']}")
        
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
