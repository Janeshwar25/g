"""
Sync Smartsheet data to MongoDB as markdown for LLM access.

This script:
1. Retrieves all active plans from MongoDB
2. Fetches each Smartsheet using the sheet ID
3. Converts the dataframe to markdown format
4. Updates the MongoDB document with the markdown and sync timestamp
"""

import sys
import os
from datetime import datetime
import logging
import requests
import re

# Add parent directory to path so we can import engine and upload modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.mongodb_helper import MongoDBHelper
from upload.update_smartsheet import smartsheet_to_pandas
from config import Config

config = Config()
SMARTSHEET_HEADERS = config.get_smartsheet_headers()
BASE_URL = config.SMARTSHEET_BASE_URL
MMI_WORKSPACE_ID = os.getenv('MMI_WORKSPACE_ID', '2348159855814532')
MMI_FOLDER_PREFIXES = ('USPPIMMI', 'USPPIGNP', 'PSTRATEGIC')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def dataframe_to_markdown(df):
    """
    Convert a pandas DataFrame to markdown table format.
    
    Args:
        df: pandas DataFrame
        
    Returns:
        str: Markdown formatted table
    """
    if df is None or df.empty:
        return "No data available"
    
    # Convert DataFrame to markdown using pandas built-in method
    markdown = df.to_markdown(index=False)
    return markdown


def _parse_mmi_folder_name(folder_name):
    """
    Parse folder name in format: "Aha Idea - Project Name - MMI Blueprint"

    Returns:
        tuple[str, str]: (aha_idea, project_name)
    """
    if not folder_name:
        return "", ""

    parts = [part.strip() for part in str(folder_name).split(' - ') if part.strip()]

    if len(parts) >= 2:
        return parts[0], parts[1]

    # Fallback for folders that don't have spaces around '-'
    fallback_parts = [part.strip() for part in str(folder_name).split('-') if part.strip()]
    if len(fallback_parts) >= 2:
        return fallback_parts[0], fallback_parts[1]

    # Last fallback: first token as key, whole name as project
    first_token = str(folder_name).strip().split()[0] if str(folder_name).strip() else ""
    return first_token, str(folder_name).strip()


def _select_sheet_by_suffix(sheets, suffix):
    """Return first sheet whose name ends with suffix (case-insensitive)."""
    suffix_lower = suffix.lower()
    for sheet in sheets:
        sheet_name = str(sheet.get('name', '')).strip().lower()
        if sheet_name.endswith(suffix_lower):
            return sheet
    return None


def _fetch_workspace_folders(workspace_id):
    """Fetch folders from a Smartsheet workspace."""
    response = requests.get(
        f"{BASE_URL}/workspaces/{workspace_id}",
        headers=SMARTSHEET_HEADERS,
        verify=False,
        timeout=60
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get('folders', [])


def _fetch_folder_sheets(folder_id):
    """Fetch full folder details and return sheet list."""
    response = requests.get(
        f"{BASE_URL}/folders/{folder_id}",
        headers=SMARTSHEET_HEADERS,
        verify=False,
        timeout=60
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get('sheets', [])


def _clean_cell_value(value):
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"", "nan", "none"}:
        return ""
    return text


def _extract_field_from_labels(df, scan_cols, label_patterns, blocked_terms=None, lookahead=8):
    """
    Find a value for a labeled field (e.g., "Overall Status", "Project Number")
    by scanning candidate columns and nearby cells.
    """
    blocked_terms = blocked_terms or []

    for col in scan_cols:
        series = df[col].fillna("").astype(str)
        for idx, value in series.items():
            text = _clean_cell_value(value)
            if not text:
                continue

            matched_pattern = None
            for pattern in label_patterns:
                if re.search(pattern, text, flags=re.IGNORECASE):
                    matched_pattern = pattern
                    break

            if not matched_pattern:
                continue

            # 1) Inline pattern: "Label: value"
            inline_match = re.search(r'[:\-]\s*(.+)$', text)
            if inline_match:
                candidate = _clean_cell_value(inline_match.group(1))
                if candidate and not any(term in candidate.lower() for term in blocked_terms):
                    return candidate

            # 2) Same row, other columns
            row = df.loc[idx]
            for other_col in df.columns:
                if other_col == col:
                    continue
                candidate = _clean_cell_value(row.get(other_col, ""))
                if candidate and not any(term in candidate.lower() for term in blocked_terms):
                    return candidate

            # 3) Next non-empty lines in same column
            for next_idx in range(idx + 1, min(idx + lookahead + 1, len(df))):
                candidate = _clean_cell_value(series.iloc[next_idx])
                if candidate and not any(term in candidate.lower() for term in blocked_terms):
                    return candidate

    return ""


def _extract_mmi_summary_fields(df):
    """
    Extract key executive summary fields from MMI Program Plan.

    Targets:
    - initiative_name_mmi
    - strategic_theme_mmi
    - project_number_mmi
    - go_live_date_mmi
    - overall_status_mmi
    - executive_summary_mmi
    """
    result = {
        "initiative_name_mmi": "",
        "strategic_theme_mmi": "",
        "project_number_mmi": "",
        "go_live_date_mmi": "",
        "overall_status_mmi": "",
        "executive_summary_mmi": "",
    }

    if df is None or df.empty:
        return result

    # Deterministic mapping for MMI summary rows:
    # Task Name == label, Task Description == value (first occurrence wins)
    task_name_col = None
    task_desc_col = None

    normalized_columns = []
    for col in df.columns:
        col_lower = re.sub(r'\s+', ' ', str(col).strip().lower())
        normalized_columns.append((col, col_lower))

    # First pass: exact canonical names
    for col, col_lower in normalized_columns:
        if task_name_col is None and col_lower == 'task name':
            task_name_col = col
        if task_desc_col is None and col_lower == 'task description':
            task_desc_col = col

    # Second pass: tolerant contains matching (handles variants/newlines)
    if task_name_col is None:
        for col, col_lower in normalized_columns:
            if 'task' in col_lower and 'name' in col_lower:
                task_name_col = col
                break

    if task_desc_col is None:
        for col, col_lower in normalized_columns:
            if 'task' in col_lower and 'description' in col_lower:
                task_desc_col = col
                break

    if task_name_col is None or task_desc_col is None:
        # Fallback to previous heuristic only if required columns are missing
        desc_cols = [col for col in df.columns if 'task description' in str(col).lower()]
        scan_cols = desc_cols if desc_cols else list(df.columns)
        result['strategic_theme_mmi'] = _extract_field_from_labels(
            df,
            scan_cols,
            label_patterns=[r'\bstrategic\s*theme\b'],
            blocked_terms=['strategic theme'],
            lookahead=8
        )
        result['initiative_name_mmi'] = _extract_field_from_labels(
            df,
            scan_cols,
            label_patterns=[r'\binitiative\s*name\b'],
            blocked_terms=['initiative name'],
            lookahead=8
        )
        result['project_number_mmi'] = _extract_field_from_labels(
            df,
            scan_cols,
            label_patterns=[r'\bproject\s*number\b', r'\bproject\s*#\b', r'\bproject\s*no\b'],
            blocked_terms=['project number', 'project #', 'project no'],
            lookahead=8
        )
        result['go_live_date_mmi'] = _extract_field_from_labels(
            df,
            scan_cols,
            label_patterns=[r'\bgo\s*live\s*date\b', r'\bgo\s*live\b', r'\bgo-?live\b'],
            blocked_terms=['go live'],
            lookahead=8
        )
        result['overall_status_mmi'] = _extract_field_from_labels(
            df,
            scan_cols,
            label_patterns=[r'\boverall\s*status\b'],
            blocked_terms=['overall status'],
            lookahead=4
        )
        result['executive_summary_mmi'] = _extract_field_from_labels(
            df,
            scan_cols,
            label_patterns=[r'\bexecutive\s*summary\b'],
            blocked_terms=['executive summary', 'overall status'],
            lookahead=12
        )
        return result

    label_to_field = {
        'initiative name': 'initiative_name_mmi',
        'strategic theme': 'strategic_theme_mmi',
        'project number': 'project_number_mmi',
        'go-live date': 'go_live_date_mmi',
        'go live date': 'go_live_date_mmi',
        'executive summary': 'executive_summary_mmi',
        'overall status': 'overall_status_mmi',
    }

    # First occurrence of each label wins
    seen_fields = set()
    for _, row in df.iterrows():
        label_raw = _clean_cell_value(row.get(task_name_col, ""))
        if not label_raw:
            continue

        label_norm = re.sub(r'\s+', ' ', label_raw.strip().lower())
        label_norm = label_norm.replace('–', '-').replace('—', '-')
        if label_norm in label_to_field:
            field_name = label_to_field[label_norm]
            if field_name in seen_fields:
                continue

            value = _clean_cell_value(row.get(task_desc_col, ""))
            if value:
                result[field_name] = value
                seen_fields.add(field_name)

        # Stop early when all fields are found
        if len(seen_fields) == 6:
            break

    return result


def sync_mmi_workspace_to_markdown():
    """
    Sync MMI workspace sheets to MongoDB using Aha Idea as key.

    Folder selection:
    - Only folders whose names start with USPPIMMI, USPPIGNP, or PSTRATEGIC

    Sheet selection within each folder:
    - Sheet ending with "Program Plan"
    - Sheet ending with "Budget-PPMO Export"

    MongoDB schema (upsert by _id = Aha Idea):
    - idea (Aha Idea)
    - name (Project Name)
    - program_plan_sheet_id
    - budget_sheet_id
    - program_plan_markdown
    - budget_markdown
    - active=True
    - bc='MMI'
    """
    logger.info(f"Starting MMI Smartsheet sync for workspace: {MMI_WORKSPACE_ID}")

    results = {
        "folders_scanned": 0,
        "folders_matched": 0,
        "upserted": 0,
        "failed": 0,
        "skipped": 0,
    }

    mongo_helper = MongoDBHelper()

    try:
        folders = _fetch_workspace_folders(MMI_WORKSPACE_ID)
        results["folders_scanned"] = len(folders)

        if not folders:
            logger.warning("No folders found in MMI workspace")
            return results

        for folder in folders:
            folder_name = str(folder.get('name', '')).strip()
            folder_id = folder.get('id')

            if not folder_id:
                results["skipped"] += 1
                continue

            if not folder_name.startswith(MMI_FOLDER_PREFIXES):
                results["skipped"] += 1
                continue

            results["folders_matched"] += 1
            logger.info(f"Processing MMI folder: {folder_name} (ID: {folder_id})")

            aha_idea, project_name = _parse_mmi_folder_name(folder_name)
            if not aha_idea:
                logger.warning(f"Could not derive Aha Idea from folder name: {folder_name}")
                results["failed"] += 1
                continue

            try:
                sheets = _fetch_folder_sheets(folder_id)
                program_plan_sheet = _select_sheet_by_suffix(sheets, 'Program Plan')
                budget_sheet = _select_sheet_by_suffix(sheets, 'Budget-PPMO Export')

                if not program_plan_sheet and not budget_sheet:
                    logger.warning(f"No Program Plan/Budget-PPMO Export sheets found in folder: {folder_name}")
                    results["skipped"] += 1
                    continue

                program_plan_sheet_id = program_plan_sheet.get('id') if program_plan_sheet else None
                budget_sheet_id = budget_sheet.get('id') if budget_sheet else None

                program_plan_markdown = ""
                budget_markdown = ""
                summary_fields = {
                    "initiative_name_mmi": "",
                    "strategic_theme_mmi": "",
                    "project_number_mmi": "",
                    "go_live_date_mmi": "",
                    "overall_status_mmi": "",
                    "executive_summary_mmi": "",
                }

                if program_plan_sheet_id:
                    plan_df = smartsheet_to_pandas(program_plan_sheet_id)
                    if plan_df is not None and not plan_df.empty:
                        summary_fields = _extract_mmi_summary_fields(plan_df)
                        program_plan_markdown = dataframe_to_markdown(plan_df)

                if budget_sheet_id:
                    budget_df = smartsheet_to_pandas(budget_sheet_id)
                    if budget_df is not None and not budget_df.empty:
                        budget_markdown = dataframe_to_markdown(budget_df)

                # Keep compatibility with existing LLM readers by providing a combined markdown field
                combined_markdown_parts = []
                if program_plan_markdown:
                    combined_markdown_parts.append(f"### Program Plan\n\n{program_plan_markdown}")
                if budget_markdown:
                    combined_markdown_parts.append(f"### Budget-PPMO Export\n\n{budget_markdown}")
                combined_sheet_markdown = "\n\n".join(combined_markdown_parts)

                resolved_project_name = summary_fields.get("initiative_name_mmi") or project_name

                metadata = {
                    "idea": aha_idea,
                    "name": resolved_project_name,
                    "program_plan_sheet_id": program_plan_sheet_id,
                    "budget_sheet_id": budget_sheet_id,
                    "program_plan_markdown": program_plan_markdown,
                    "budget_markdown": budget_markdown,
                    "sheet_markdown": combined_sheet_markdown,
                    "active": True,
                    "bc": "MMI",
                    "last_synced": datetime.now().isoformat(),
                }

                if summary_fields.get("initiative_name_mmi"):
                    metadata["initiative_name_mmi"] = summary_fields["initiative_name_mmi"]

                if summary_fields.get("overall_status_mmi"):
                    metadata["overall_status_mmi"] = summary_fields["overall_status_mmi"]
                    # Keep existing status-based queries efficient
                    metadata["status"] = summary_fields["overall_status_mmi"]

                if summary_fields.get("executive_summary_mmi"):
                    metadata["executive_summary_mmi"] = summary_fields["executive_summary_mmi"]

                if summary_fields.get("strategic_theme_mmi"):
                    metadata["strategic_theme_mmi"] = summary_fields["strategic_theme_mmi"]

                if summary_fields.get("project_number_mmi"):
                    metadata["project_number_mmi"] = summary_fields["project_number_mmi"]
                    # Keep existing project-number/PPMO searches efficient
                    metadata["prj"] = summary_fields["project_number_mmi"]

                if summary_fields.get("go_live_date_mmi"):
                    metadata["go_live_date_mmi"] = summary_fields["go_live_date_mmi"]
                    # Keep existing go-live queries efficient
                    metadata["go live"] = summary_fields["go_live_date_mmi"]

                saved = mongo_helper.save_plan_metadata(aha_idea, metadata)
                if saved:
                    results["upserted"] += 1
                    logger.info(f"Upserted MMI project for Aha Idea: {aha_idea}")
                else:
                    results["failed"] += 1

            except Exception as folder_error:
                logger.error(f"Error processing folder '{folder_name}': {folder_error}")
                results["failed"] += 1

        logger.info("=" * 60)
        logger.info("MMI Sync Summary:")
        logger.info(f"  Workspace folders scanned: {results['folders_scanned']}")
        logger.info(f"  Folders matched by prefix: {results['folders_matched']}")
        logger.info(f"  Mongo upserts: {results['upserted']}")
        logger.info(f"  Failed: {results['failed']}")
        logger.info(f"  Skipped: {results['skipped']}")
        logger.info("=" * 60)

        return results

    finally:
        mongo_helper.close()


def sync_plan_to_markdown(mongo_helper, rally_theme, sheet_id):
    """
    Fetch a Smartsheet and update MongoDB with markdown version.
    
    Args:
        mongo_helper: MongoDBHelper instance
        rally_theme: Strategic theme ID (MongoDB document key)
        sheet_id: Smartsheet ID to fetch
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"Syncing plan {rally_theme} (sheet ID: {sheet_id})")
        
        # Fetch Smartsheet as DataFrame
        df = smartsheet_to_pandas(sheet_id)
        
        if df is None or df.empty:
            logger.warning(f"No data retrieved for sheet {sheet_id}")
            return False
        
        logger.info(f"Retrieved {len(df)} rows from Smartsheet")
        
        # Convert to markdown
        markdown = dataframe_to_markdown(df)
        
        # Update MongoDB with markdown and timestamp
        update_data = {
            "sheet_markdown": markdown,
            "last_synced": datetime.now().isoformat()
        }
        
        success = mongo_helper.update_plan_metadata(rally_theme, update_data)
        
        if success:
            logger.info(f"Successfully synced plan {rally_theme}")
        else:
            logger.error(f"Failed to update MongoDB for plan {rally_theme}")
            
        return success
        
    except Exception as e:
        logger.error(f"Error syncing plan {rally_theme}: {e}")
        return False


def sync_all_active_plans():
    """
    Sync all active plans from Smartsheet to MongoDB as markdown.
    
    Returns:
        dict: Summary of sync results
    """
    logger.info("Starting Smartsheet to Markdown sync for active plans")
    
    try:
        # Connect to MongoDB
        mongo_helper = MongoDBHelper()
        
        # Get all plans
        all_plans = mongo_helper.get_all_plans()
        
        if not all_plans:
            logger.warning("No plans found in MongoDB")
            return {"total": 0, "success": 0, "failed": 0, "skipped": 0}
        
        logger.info(f"Found {len(all_plans)} total plans in MongoDB")
        
        # Filter for active plans with sheet IDs
        results = {
            "total": len(all_plans),
            "success": 0,
            "failed": 0,
            "skipped": 0
        }
        
        for rally_theme, plan_data in all_plans.items():
            # Check if plan is active
            is_active = plan_data.get('active', False)
            if not is_active:
                logger.info(f"Skipping inactive plan: {rally_theme}")
                results["skipped"] += 1
                continue
            
            # Check if sheet ID exists
            sheet_id = plan_data.get('sheet id')
            if not sheet_id:
                logger.warning(f"No sheet ID found for plan: {rally_theme}")
                results["skipped"] += 1
                continue
            
            # Sync the plan
            if sync_plan_to_markdown(mongo_helper, rally_theme, sheet_id):
                results["success"] += 1
            else:
                results["failed"] += 1
        
        # Log summary
        logger.info("=" * 60)
        logger.info("Sync Summary:")
        logger.info(f"  Total plans: {results['total']}")
        logger.info(f"  Successfully synced: {results['success']}")
        logger.info(f"  Failed: {results['failed']}")
        logger.info(f"  Skipped (inactive or no sheet ID): {results['skipped']}")
        logger.info("=" * 60)
        
        return results
        
    except Exception as e:
        logger.error(f"Error during sync: {e}")
        raise


def sync_all_sources():
    """Run both legacy active-plan sync and MMI workspace sync."""
    legacy_results = sync_all_active_plans()
    mmi_results = sync_mmi_workspace_to_markdown()
    return {
        "legacy": legacy_results,
        "mmi": mmi_results,
    }


if __name__ == "__main__":
    try:
        results = sync_all_sources()
        
        legacy_failed = results.get("legacy", {}).get("failed", 0)
        mmi_failed = results.get("mmi", {}).get("failed", 0)

        # Exit with error code if there were failures
        if legacy_failed > 0 or mmi_failed > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
