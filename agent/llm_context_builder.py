"""
LLM Context Builder - Formats MongoDB project data for LLM consumption.

This module retrieves project metadata and Smartsheet data from MongoDB
and formats it into LLM-friendly text for question answering.
"""

import sys
import os
import re
from typing import Dict, List, Optional
from engine.mongodb_helper import MongoDBHelper


def _project_bc(project_data: Dict) -> str:
    return str(project_data.get('bc', 'LEGACY') or 'LEGACY').upper()


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


def _matches_portfolio(project_data: Dict, portfolio_filter: str) -> bool:
    normalized = _normalize_portfolio_filter(portfolio_filter)
    if normalized == 'all':
        return True
    bc = _project_bc(project_data)
    if normalized == 'mmi':
        return bc == 'MMI'
    if normalized == 'legacy':
        return bc != 'MMI'
    return True


def _searchable_plan_content(project_data: Dict) -> str:
    """Return the best plan text for searching based on project format."""
    if _project_bc(project_data) == 'MMI':
        program_plan = project_data.get('program_plan_markdown', '')
        budget_plan = project_data.get('budget_markdown', '')
        combined = []
        if program_plan:
            combined.append(program_plan)
        if budget_plan:
            combined.append(budget_plan)
        if combined:
            return "\n\n".join(combined)
        return project_data.get('sheet_markdown', '')
    return project_data.get('sheet_markdown', '')


def _display_strategic_theme(rally_theme: str, project_data: Dict) -> str:
    """Strategic theme to show users (MMI should use extracted strategic_theme_mmi)."""
    if _project_bc(project_data) == 'MMI':
        return project_data.get('strategic_theme_mmi', 'N/A') or 'N/A'
    return rally_theme


def format_project_metadata(rally_theme: str, project_data: Dict) -> str:
    """
    Format project metadata into human-readable text.
    
    Args:
        rally_theme: Strategic theme ID
        project_data: Dictionary containing project metadata
        
    Returns:
        str: Formatted metadata text
    """
    bc = _project_bc(project_data)
    display_strategic_theme = _display_strategic_theme(rally_theme, project_data)
    metadata_text = f"""
## Project: {project_data.get('name', 'Unknown')}

**BC:** {bc}
**Strategic Theme:** {display_strategic_theme}
**Aha Idea:** {project_data.get('idea', 'N/A')}
**Optics PRJ:** {project_data.get('prj', 'N/A')}
**Go-Live:** {project_data.get('go live', 'N/A')}
**Status:** {project_data.get('status', 'N/A')}
**Business Delivery Lead (BDL):** {project_data.get('bdl', 'N/A')}
**Resource Delivery Lead (RDL):** {project_data.get('rdl', 'N/A')}
**Initiative Area:** {project_data.get('tag', 'N/A')}
**Active:** {project_data.get('active', False)}
**Last Synced:** {project_data.get('last_synced', 'Never')}
**Notes:** {project_data.get('notes', 'N/A')}
"""

    if bc == 'MMI':
        metadata_text += f"""
**Aha Idea Key:** {rally_theme}
**Program Plan Sheet ID:** {project_data.get('program_plan_sheet_id', 'N/A')}
**Budget Sheet ID:** {project_data.get('budget_sheet_id', 'N/A')}
**MMI Strategic Theme:** {project_data.get('strategic_theme_mmi', 'N/A')}
**MMI Project Number:** {project_data.get('project_number_mmi', project_data.get('prj', 'N/A'))}
**MMI Go Live Date:** {project_data.get('go_live_date_mmi', project_data.get('go live', 'N/A'))}
**MMI Overall Status:** {project_data.get('overall_status_mmi', project_data.get('status', 'N/A'))}
**MMI Executive Summary:** {project_data.get('executive_summary_mmi', 'N/A')}
"""

    return metadata_text


def format_project_with_plan(rally_theme: str, project_data: Dict, include_plan: bool = True) -> str:
    """
    Format complete project information including metadata and Smartsheet plan.
    
    Args:
        rally_theme: Strategic theme ID
        project_data: Dictionary containing project metadata
        include_plan: Whether to include the full Smartsheet markdown
        
    Returns:
        str: Complete formatted project information
    """
    # Start with metadata
    output = "=" * 80 + "\n"
    output += format_project_metadata(rally_theme, project_data)
    bc = _project_bc(project_data)
    
    # Add Smartsheet plan if available and requested
    if include_plan and bc == 'MMI':
        program_plan_markdown = project_data.get('program_plan_markdown')
        budget_markdown = project_data.get('budget_markdown')

        if program_plan_markdown:
            output += "\n### Program Plan (MMI)\n\n"
            output += program_plan_markdown
        else:
            output += "\n### Program Plan (MMI)\n\n"
            output += "*No MMI Program Plan markdown available. Run sync_smartsheet_markdown.py to populate.*\n"

        if budget_markdown:
            output += "\n\n### Budget-PPMO Export (MMI)\n\n"
            output += budget_markdown
        else:
            output += "\n\n### Budget-PPMO Export (MMI)\n\n"
            output += "*No MMI Budget-PPMO Export markdown available. Run sync_smartsheet_markdown.py to populate.*\n"
    elif include_plan and 'sheet_markdown' in project_data:
        output += "\n### Project Plan (Smartsheet Data)\n\n"
        output += project_data['sheet_markdown']
    elif include_plan:
        output += "\n### Project Plan\n\n"
        output += "*No Smartsheet data available. Run sync_smartsheet_markdown.py to populate.*\n"
    
    output += "\n" + "=" * 80 + "\n"
    
    return output


def get_all_active_projects_context(include_plans: bool = True, portfolio_filter: str = 'all') -> str:
    """
    Retrieve all active projects and format for LLM context.
    
    Args:
        include_plans: Whether to include full Smartsheet markdown for each project
        
    Returns:
        str: Formatted context containing all active project data
    """
    mongo_helper = MongoDBHelper()
    all_plans = mongo_helper.get_all_plans()
    
    if not all_plans:
        return "No projects found in database."
    
    # Filter for active projects
    active_plans = {
        theme: data for theme, data in all_plans.items() 
        if data.get('active', False) and _matches_portfolio(data, portfolio_filter)
    }
    
    if not active_plans:
        return "No active projects found in database."
    
    # Build context
    context = f"""# Project Portfolio Context

Total Active Projects: {len(active_plans)}
Last Updated: {max([p.get('last_synced', '1970-01-01') for p in active_plans.values()], default='Unknown')}

---

"""
    
    # Add each project
    for rally_theme, project_data in active_plans.items():
        context += format_project_with_plan(rally_theme, project_data, include_plans)
        context += "\n\n"
    
    return context


def get_project_context(rally_theme: str, include_plan: bool = True, portfolio_filter: str = 'all') -> Optional[str]:
    """
    Get context for a specific project by strategic theme.
    
    Args:
        rally_theme: Strategic theme ID
        include_plan: Whether to include Smartsheet markdown
        
    Returns:
        str: Formatted project context or None if not found
    """
    mongo_helper = MongoDBHelper()
    project_data = mongo_helper.get_plan_metadata(rally_theme)
    
    if not project_data:
        return None

    if not _matches_portfolio(project_data, portfolio_filter):
        return None
    
    return format_project_with_plan(rally_theme, project_data, include_plan)


def get_projects_by_name(search_term: str, include_plans: bool = True, portfolio_filter: str = 'all') -> str:
    """
    Search for projects by name and return formatted context.
    
    Args:
        search_term: Term to search for in project names (case-insensitive)
        include_plans: Whether to include Smartsheet markdown
        
    Returns:
        str: Formatted context for matching projects
    """
    mongo_helper = MongoDBHelper()
    all_plans = mongo_helper.get_all_plans()
    
    if not all_plans:
        return "No projects found in database."
    
    # Search for matching projects
    search_lower = search_term.lower()
    matching_plans = {
        theme: data for theme, data in all_plans.items()
        if search_lower in data.get('name', '').lower() and _matches_portfolio(data, portfolio_filter)
    }
    
    if not matching_plans:
        return f"No projects found matching '{search_term}'."
    
    # Build context
    context = f"# Projects Matching '{search_term}'\n\n"
    context += f"Found {len(matching_plans)} matching project(s)\n\n---\n\n"
    
    for rally_theme, project_data in matching_plans.items():
        context += format_project_with_plan(rally_theme, project_data, include_plans)
        context += "\n\n"
    
    return context


def _normalize_search_term(text: str) -> str:
    """
    Normalize text for fuzzy matching by removing common separators and whitespace.
    
    Args:
        text: Text to normalize
        
    Returns:
        str: Normalized text (lowercase, no spaces/hyphens/underscores)
    """
    if not text:
        return ""
    # Remove spaces, hyphens, underscores, and lowercase
    return re.sub(r'[\s\-_]', '', text.lower())


def _fuzzy_match(search_term: str, value: str, threshold: float = 0.8) -> bool:
    """
    Check if search_term fuzzy matches value.
    Uses normalized comparison and substring matching.
    
    Args:
        search_term: What to search for
        value: Value to search in
        threshold: Match threshold (not currently used, for future enhancement)
        
    Returns:
        bool: True if match found
    """
    if not search_term or not value:
        return False
    
    # Exact substring match (case-insensitive)
    if search_term.lower() in value.lower():
        return True
    
    # Normalized fuzzy match (removes spaces, hyphens, etc.)
    normalized_search = _normalize_search_term(search_term)
    normalized_value = _normalize_search_term(value)
    
    # Check if normalized search term is in normalized value
    if normalized_search in normalized_value:
        return True
    
    # Check if normalized value is in normalized search (handles partial matches)
    if len(normalized_search) > 5 and normalized_value in normalized_search:
        return True
    
    # Additional check: if search is at least 80% of the value (handles minor typos)
    if len(normalized_search) >= 5 and len(normalized_value) >= 5:
        # Check if most of search term is in value
        min_len = min(len(normalized_search), len(normalized_value))
        if min_len >= 5:
            # Check for substantial overlap
            for i in range(len(normalized_search) - 4):
                substr = normalized_search[i:i+5]
                if substr in normalized_value:
                    return True
    
    return False


def search_projects_by_criteria(search_term: str, search_in_plans: bool = False, portfolio_filter: str = 'all') -> str:
    """
    Search for projects matching specific criteria.
    Can search in metadata or scan Smartsheet plans for specific text.
    
    Args:
        search_term: What to search for (team name, application, person, keyword, etc.)
        search_in_plans: If True, searches within Smartsheet markdown content (slower but thorough)
                        If False, searches only metadata (faster)
        
    Returns:
        str: Formatted list of matching projects with relevant excerpts
    """
    mongo_helper = MongoDBHelper()
    all_plans = mongo_helper.get_all_plans()
    
    if not all_plans:
        return "No projects found in database."
    
    search_lower = search_term.lower()
    matching_projects = []
    
    for rally_theme, data in all_plans.items():
        if not _matches_portfolio(data, portfolio_filter):
            continue

        match_found = False
        match_locations = []
        match_type = "exact"  # Track if it's exact or fuzzy match
        
        # Search in metadata with fuzzy matching
        metadata_fields = [
            'name', 'idea', 'prj', 'bdl', 'rdl', 'tag', 'status', 'notes', 'bc',
            'program_plan_sheet_id', 'budget_sheet_id', 'strategic_theme_mmi',
            'project_number_mmi', 'go_live_date_mmi', 'overall_status_mmi', 'executive_summary_mmi'
        ]
        for field in metadata_fields:
            value = str(data.get(field, ''))
            
            # Try fuzzy matching
            if _fuzzy_match(search_term, value):
                match_found = True
                # Indicate if it was a fuzzy match vs exact
                if search_lower not in value.lower():
                    match_type = "fuzzy"
                    match_locations.append(f"{field}: {data.get(field, 'N/A')} (fuzzy match)")
                else:
                    match_locations.append(f"{field}: {data.get(field, 'N/A')}")
        
        # Also check strategic theme itself with fuzzy matching
        if _fuzzy_match(search_term, rally_theme):
            match_found = True
            theme_label = "Aha Idea Key" if _project_bc(data) == 'MMI' else "Strategic Theme"
            if search_lower not in rally_theme.lower():
                match_type = "fuzzy"
                match_locations.append(f"{theme_label}: {rally_theme} (fuzzy match)")
            else:
                match_locations.append(f"{theme_label}: {rally_theme}")
        
        # Search in Smartsheet plan data if requested
        searchable_plan = _searchable_plan_content(data)
        if search_in_plans and searchable_plan:
            sheet_content = searchable_plan.lower()
            if search_lower in sheet_content:
                match_found = True
                
                # Extract context around the match (show a snippet)
                lines = searchable_plan.split('\n')
                matching_lines = [line for line in lines if search_lower in line.lower()]
                
                # Get first few matches as preview
                preview_lines = matching_lines[:5]
                if preview_lines:
                    match_locations.append(f"Found in plan data ({len(matching_lines)} occurrences):")
                    for line in preview_lines:
                        match_locations.append(f"  • {line.strip()[:100]}")
        
        if match_found:
            matching_projects.append({
                'theme': rally_theme,
                'name': data.get('name', 'Unknown'),
                'status': data.get('status', 'N/A'),
                'go_live': data.get('go live', 'N/A'),
                'bdl': data.get('bdl', 'N/A'),
                'rdl': data.get('rdl', 'N/A'),
                'active': data.get('active', False),
                'bc': _project_bc(data),
                'strategic_theme_display': _display_strategic_theme(rally_theme, data),
                'matches': match_locations,
                'match_type': match_type
            })
    
    if not matching_projects:
        # Get all project themes for suggestions
        all_themes = list(all_plans.keys())
        
        # Find close matches using edit distance / similarity
        suggestions = []
        search_normalized = _normalize_search_term(search_term)
        
        # If search looks like a strategic theme (starts with letters, has numbers)
        if re.match(r'^[A-Z]{2,}\s*\d+', search_term, re.IGNORECASE):
            # Extract prefix and numbers
            search_parts = re.match(r'^([A-Z]+)\s*(\d+)', search_term, re.IGNORECASE)
            if search_parts:
                search_prefix = search_parts.group(1).upper()
                search_number = search_parts.group(2)
                
                # Find themes with same prefix and similar numbers
                for theme in all_themes:
                    theme_parts = re.match(r'^([A-Z]+)(\d+)', theme)
                    if theme_parts:
                        theme_prefix = theme_parts.group(1)
                        theme_number = theme_parts.group(2)
                        
                        # Same prefix check
                        if theme_prefix == search_prefix:
                            # Check if numbers are close (substring match or small difference)
                            if search_number in theme_number or theme_number in search_number:
                                suggestions.append(theme)
                            elif abs(len(search_number) - len(theme_number)) <= 1:
                                # Similar length, check similarity
                                if theme_number.startswith(search_number) or search_number.startswith(theme_number):
                                    suggestions.append(theme)
        
        # Try matching on Aha Ideas and project names if no theme matches
        if not suggestions and len(search_normalized) >= 4:
            for theme, data in all_plans.items():
                # Check Aha Idea
                idea = str(data.get('idea', ''))
                if idea and _fuzzy_match(search_term, idea):
                    suggestions.append((theme, data.get('name', 'Unknown'), f"Aha Idea: {idea}"))
                    continue
                
                # Check project name
                name = str(data.get('name', ''))
                if name and _fuzzy_match(search_term, name):
                    suggestions.append((theme, name))
        
        # If still no suggestions, try normalized matching on all themes
        if not suggestions:
            for theme in all_themes:
                theme_normalized = _normalize_search_term(theme)
                # Check if normalized search is substantially in theme
                if len(search_normalized) >= 4 and search_normalized in theme_normalized:
                    suggestions.append(theme)
                elif len(theme_normalized) >= 4 and theme_normalized in search_normalized:
                    suggestions.append(theme)
        
        # Limit to top 5 suggestions
        suggestions = suggestions[:5]
        
        if suggestions:
            suggestion_text = "\n\n**Did you mean one of these?**\n"
            for item in suggestions:
                if isinstance(item, tuple) and len(item) == 3:
                    theme, name, extra = item
                    suggestion_text += f"- {theme}: {name} - {extra}\n"
                elif isinstance(item, tuple) and len(item) == 2:
                    theme, name = item
                    suggestion_text += f"- {theme}: {name}\n"
                else:
                    theme = item
                    name = all_plans.get(theme, {}).get('name', 'Unknown')
                    suggestion_text += f"- {theme}: {name}\n"
            suggestion_text += "\n**Tip:** Use get_project_details('THEME') to view a specific project"
            return f"No projects found matching '{search_term}'.{suggestion_text}"
        else:
            # Provide generic help
            suggestion = "\n\n💡 **Tip:** Try searching with:\n"
            suggestion += "- Strategic theme (e.g., ST21461, GNP-1234)\n"
            suggestion += "- Aha Idea ID (e.g., EI-12345)\n"
            suggestion += "- Project name or partial name\n"
            suggestion += "- Use get_project_list() to see all available projects"
            return f"No projects found matching '{search_term}'.{suggestion}"
    
    # Sort: exact matches first, then fuzzy matches
    matching_projects.sort(key=lambda x: (x['match_type'] != 'exact', x['name']))
    
    # Format results
    result = f"# Search Results for '{search_term}'\n\n"
    result += f"Found {len(matching_projects)} matching project(s)"
    
    # Indicate if fuzzy matches were used
    fuzzy_count = sum(1 for p in matching_projects if p['match_type'] == 'fuzzy')
    if fuzzy_count > 0:
        result += f" ({fuzzy_count} fuzzy match{'es' if fuzzy_count > 1 else ''})"
    result += "\n\n"
    result += "---\n\n"
    
    for proj in matching_projects:
        result += f"## {proj['name']} ({proj['theme']})\n\n"
        result += f"**BC:** {proj.get('bc', 'LEGACY')} | **Strategic Theme:** {proj.get('strategic_theme_display', 'N/A')} | **Status:** {proj['status']} | **Go-Live:** {proj['go_live']} | **Active:** {proj['active']}\n"
        result += f"**BDL:** {proj['bdl']} | **RDL:** {proj['rdl']}\n\n"
        
        if proj['matches']:
            result += "**Matches Found:**\n"
            for match in proj['matches']:
                result += f"- {match}\n"
        
        result += "\n---\n\n"
    
    result += f"\n💡 **Tip:** Use get_project_details(project_theme) to view full details for any project above.\n"
    
    return result


def get_metadata_only_summary(portfolio_filter: str = 'all') -> str:
    """
    Get a lightweight summary of all projects (metadata only, no Smartsheet data).
    Useful for quick overview or when full plans aren't needed.
    
    Returns:
        str: Formatted summary of all projects
    """
    mongo_helper = MongoDBHelper()
    all_plans = mongo_helper.get_all_plans()
    
    if not all_plans:
        return "No projects found in database."
    
    context = "# Project Portfolio Summary (Metadata Only)\n\n"
    filtered_plans = {
        theme: data for theme, data in all_plans.items() if _matches_portfolio(data, portfolio_filter)
    }

    context += f"Total Projects: {len(filtered_plans)}\n\n"
    
    # Create a table-like summary
    context += "| Theme | BC | Name | PPMO ID | Initiative Area | Aha Idea | Status | Go Live | BDL | RDL | Active |\n"
    context += "|-------|----|------|---------|-----------------|----------|--------|---------|-----|-----|--------|\n"
    
    for rally_theme, data in filtered_plans.items():
        context += f"| {rally_theme} | {_project_bc(data)} | {data.get('name', 'Unknown')} | "
        context += f"{data.get('prj', 'N/A')} | {data.get('tag', 'N/A')} | "
        context += f"{data.get('idea', 'N/A')} | {data.get('status', 'N/A')} | "
        context += f"{data.get('go live', 'N/A')} | {data.get('bdl', 'N/A')} | "
        context += f"{data.get('rdl', 'N/A')} | {data.get('active', False)} |\n"
    
    return context


if __name__ == "__main__":
    # Test the context builder
    print("Testing LLM Context Builder...")
    print("\n" + "=" * 80)
    print("METADATA ONLY SUMMARY")
    print("=" * 80)
    print(get_metadata_only_summary())
    
    print("\n" + "=" * 80)
    print("FULL CONTEXT (First Project Only)")
    print("=" * 80)
    
    mongo_helper = MongoDBHelper()
    all_plans = mongo_helper.get_all_plans()
    if all_plans:
        first_theme = list(all_plans.keys())[0]
        print(get_project_context(first_theme, include_plan=True))
