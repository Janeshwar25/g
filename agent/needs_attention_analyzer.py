"""
Needs Attention Analyzer - Generates project-specific alerts for the dashboard

This module analyzes active project plans and identifies issues requiring attention,
specifically focusing on Optics task tracking and application team progress alignment.
"""

import sys
import os
import json
import re
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.mongodb_helper import MongoDBHelper
from langchain_core.messages import HumanMessage, SystemMessage

from agent.alert_constants import (
    UNDER_OVER_BURN_GAP_PCT,
    FEATURE_DUE_WINDOW_DAYS,
    FEATURE_MIN_COMPLETE_PCT,
    EXECUTION_WITHOUT_OPTICS_MIN_PCT,
    ARCHS_PLANNING_TESTING,
)
from agent.enterprise_llm import EnterpriseLLMClient
from agent.prompts import get_burn_analysis_system_prompt, PROJECT_OPTICS_SYSTEM_PROMPT
from config import Config

from engine.mapping import get_task_mapping
from upload.update_smartsheet import smartsheet_to_pandas


def _enterprise_llm_response(messages: List[Any], context: str) -> str:
    """Send analyzer prompts through the enterprise gateway."""
    client = EnterpriseLLMClient(Config())
    return client.generate_response(messages=messages, context=context)


def _extract_json_object(text: str) -> Dict[str, Any]:
    cleaned = text.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```", 1)[1].split("```", 1)[0].strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(cleaned[start:end + 1])
        raise


def extract_application_progress(df: pd.DataFrame) -> Dict[str, float]:
    """
    Extract application team progress from the Application View section.
    
    Args:
        df: DataFrame of the project plan
        
    Returns:
        dict: {application_name: percent_complete}
    """
    app_progress = {}
    
    if df is None or df.empty:
        return app_progress
    
    try:
        # Find rows where Section column contains "Application View"
        app_view_mask = df['Work Breakdown'].fillna('').str.contains('Application View', case=False, na=False)
        app_df = df[app_view_mask].copy()
        
        if app_df.empty:
            return app_progress
        
        # Extract application names and % Complete
        for _, row in app_df.iterrows():
            work_breakdown = str(row.get('Work Breakdown', ''))
            percent_complete = row.get('% Complete', 0)
            
            # Skip header rows and empty entries
            if work_breakdown and work_breakdown not in ['Work Breakdown', 'Application', '']:
                try:
                    # Convert percentage to float (handle both 0.5 and 50 formats)
                    if pd.notna(percent_complete):
                        pct = float(percent_complete)
                        # If it's between 0 and 1, convert to percentage
                        if 0 <= pct <= 1:
                            pct = pct * 100
                        app_progress[work_breakdown] = pct
                except (ValueError, TypeError):
                    continue
    except Exception as e:
        print(f"      ⚠️  Error extracting application progress: {e}")
    
    return app_progress


def extract_optics_tasks(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Extract Optics task information from the plan DataFrame.
    
    Args:
        df: DataFrame of the project plan
        
    Returns:
        dict: {
            'has_optics_tasks': bool,
            'optics_tasks': [
                {
                    'task_name': str,
                    'percent_complete': float,
                    'actuals': float,
                    'eac': float,
                    'app_tag': str
                }
            ],
            'execution_percent': float or None
        }
    """
    optics_info = {
        'has_optics_tasks': False,
        'optics_tasks': [],
        'execution_percent': None
    }
    
    if df is None or df.empty:
        return optics_info
    
    try:
        # Find Execution row
        execution_mask = df['Work Breakdown'].fillna('').str.contains('Execution', case=False, na=False)
        execution_rows = df[execution_mask]
        if not execution_rows.empty:
            exec_pct = execution_rows.iloc[0].get('% Complete', 0)
            if pd.notna(exec_pct):
                optics_info['execution_percent'] = float(exec_pct) * 100 if exec_pct <= 1 else float(exec_pct)
        
        # Find Optics tasks: STxxxxx_ pattern
        optics_mask = df['Work Breakdown'].fillna('').str.match(r'^ST\d+_', case=False, na=False)
        optics_df = df[optics_mask].copy()
        
        if not optics_df.empty:
            optics_info['has_optics_tasks'] = True
            
            for _, row in optics_df.iterrows():
                task_name = str(row.get('Work Breakdown', ''))
                
                # Extract tag from task name (e.g., [BAS])
                app_tag = ''
                tag_match = re.search(r'\[([A-Z0-9]+)\]', task_name)
                if tag_match:
                    app_tag = tag_match.group(1)
                
                # Extract percent complete
                percent_complete = row.get('% Complete', 0)
                try:
                    if pd.notna(percent_complete) and percent_complete != '':
                        pct = float(percent_complete)
                        if pct <= 1:
                            pct = pct * 100
                    else:
                        pct = 0
                except (ValueError, TypeError):
                    pct = 0
                
                # Extract actuals and EAC
                try:
                    actuals_val = row.get('Actuals', 0)
                    actuals = float(actuals_val) if pd.notna(actuals_val) and actuals_val != '' else 0
                except (ValueError, TypeError):
                    actuals = 0
                
                try:
                    eac_val = row.get('EAC', 0)
                    eac = float(eac_val) if pd.notna(eac_val) and eac_val != '' else 0
                except (ValueError, TypeError):
                    eac = 0
                
                optics_info['optics_tasks'].append({
                    'task_name': task_name,
                    'percent_complete': pct,
                    'actuals': actuals,
                    'eac': eac,
                    'app_tag': app_tag
                })
    except Exception as e:
        print(f"      ⚠️  Error extracting optics tasks: {e}")
    
    return optics_info


def match_optics_to_application(optics_task_name: str, app_tag: str, application_name: str) -> bool:
    """
    Determine if an Optics task maps to a specific application.
    
    Args:
        optics_task_name: Full name of the Optics task
        app_tag: Tag extracted from Optics task (e.g., "BAS" from "[BAS]")
        application_name: Name from Application View
        
    Returns:
        bool: True if they match
    """
    # Get known mappings from mapping.py
    try:
        task_mapping = get_task_mapping()
        
        # Check if app_tag maps to application_name
        if app_tag and app_tag in task_mapping:
            mapped_app = task_mapping[app_tag]
            if mapped_app.lower() in application_name.lower() or application_name.lower() in mapped_app.lower():
                return True
    except:
        pass
    
    # Fallback: intelligent matching based on name similarity
    app_lower = application_name.lower()
    task_lower = optics_task_name.lower()
    
    # Direct substring match
    if app_lower in task_lower or task_lower in app_lower:
        return True
    
    # Check for common abbreviations or patterns
    # e.g., "BASICS" matches "BAS", "Rally" matches "RAL"
    app_words = re.findall(r'\b[A-Za-z]{3,}\b', application_name)
    for word in app_words:
        if word.lower() in task_lower:
            return True
    
    # Check tag against application name
    if app_tag and app_tag.lower() in app_lower:
        return True
    
    return False


def analyze_burn_with_llm(df: pd.DataFrame) -> Dict[str, List[str]]:
    """
    Use LLM to analyze application-level under/over burn by comparing Application View with Optics tasks.
    
    Args:
        df: DataFrame of the project plan
        
    Returns:
        dict: {'underburn': [app1, app2, ...], 'overburn': [app3, app4, ...], 'missing_optics': [app5, app6, ...]}
    """
    result = {'underburn': [], 'overburn': [], 'missing_optics': []}
    
    if df is None or df.empty:
        return result
    
    try:
        # Extract Application View section (from "Application View" to "Financials", Level 2 or 3)
        app_view_start = df[df['Work Breakdown'] == 'Application View'].index
        financials_start = df[df['Work Breakdown'] == 'Financials'].index
        
        if len(app_view_start) == 0 or len(financials_start) == 0:
            return result
        
        app_view_section = df.loc[app_view_start[0]:financials_start[0]-1].copy()
        app_view_section = app_view_section[app_view_section['Level'].isin([2, 3])]
        
        if app_view_section.empty:
            return result
        
        # Extract Optics section (from "Task Name" to "Optics Total")
        task_name_start = df[df['Work Breakdown'] == 'Task Name'].index
        optics_total_start = df[df['Work Breakdown'].fillna('').str.contains('Optics Total', case=False, na=False)].index
        
        if len(task_name_start) == 0 or len(optics_total_start) == 0:
            return result
        
        optics_section = df.loc[task_name_start[0]:optics_total_start[0]].copy()
        
        if optics_section.empty:
            return result
        
        # Convert sections to markdown
        app_view_markdown = app_view_section.to_markdown(index=False)
        optics_markdown = optics_section.to_markdown(index=False)
        
        # Get task mapping as dictionary
        task_mapping_dict = get_task_mapping()
        
        # Convert to DataFrame for markdown display
        if task_mapping_dict and len(task_mapping_dict) > 0:
            # Remove nan keys and create DataFrame
            clean_mapping = {k: v for k, v in task_mapping_dict.items() if pd.notna(k)}
            mapping_df = pd.DataFrame(list(clean_mapping.items()), columns=['Optics Tag', 'Application Name'])
            mapping_markdown = mapping_df.to_markdown(index=False)
        else:
            mapping_markdown = "No predefined mappings available."

        system_prompt = get_burn_analysis_system_prompt()

        user_prompt = f"""Analyze burn rates between these sections:

**APPLICATION VIEW (Level 2 & 3 rows):**
{app_view_markdown}

**OPTICS TASKS:**
{optics_markdown}

**TASK MAPPING TABLE:**
{mapping_markdown}

Identify all under burn, over burn, and missing optics situations.
REMEMBER: Only flag under/over burn if gap is ≥{UNDER_OVER_BURN_GAP_PCT} percentage points. Be strict about this threshold.
Return JSON with underburn, overburn, and missing_optics arrays."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        response_content = _enterprise_llm_response(messages, context="needs_attention_burn")
        try:
            result = _extract_json_object(response_content)
        except Exception:
            retry_messages = messages + [
                HumanMessage(
                    content='Return only valid JSON matching exactly: {"underburn": [], "overburn": [], "missing_optics": []}. No markdown and no extra text.'
                )
            ]
            retry_response = _enterprise_llm_response(retry_messages, context="needs_attention_burn_retry")
            result = _extract_json_object(retry_response)

        if not isinstance(result, dict):
            result = {'underburn': [], 'overburn': [], 'missing_optics': []}

        result.setdefault('underburn', [])
        result.setdefault('overburn', [])
        result.setdefault('missing_optics', [])
        
    except Exception as e:
        print(f"      ⚠️  Error in LLM burn analysis: {e}")
    
    return result


def analyze_project_with_llm(project_theme: str, project_data: Dict) -> List[str]:
    """
    Use LLM to analyze project plan for Optics-related issues.
    
    Args:
        project_theme: Strategic theme ID
        project_data: Project data from MongoDB
        
    Returns:
        list: List of specific attention items (1-2 bullet points)
    """
    sheet_markdown = project_data.get('sheet_markdown', '')
    if not sheet_markdown:
        return []
    
    system_prompt = PROJECT_OPTICS_SYSTEM_PROMPT

    user_prompt = f"""Analyze this project plan for Optics issues:

{sheet_markdown}

Provide 1-2 specific attention items or "OK" if no issues."""

    try:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        result = _enterprise_llm_response(messages, context="needs_attention_project").strip()
        
        # Parse response
        if result.upper() == "OK":
            return []
        
        # Split by bullet points or newlines
        lines = [line.strip() for line in result.split('\n') if line.strip()]
        attention_items = []
        
        for line in lines:
            # Remove bullet points and clean up
            clean_line = line.lstrip('•-*').strip()
            if clean_line and clean_line.upper() != "OK":
                attention_items.append(clean_line)
        
        # Limit to 2 items
        return attention_items[:2]
        
    except Exception as e:
        print(f"      ❌ LLM analysis error: {e}")
        return []


def check_rule_based_alerts(project_theme: str, df: pd.DataFrame) -> List[str]:
    """
    Check for rule-based alerts using DataFrame analysis.
    
    Args:
        project_theme: Strategic theme ID
        df: DataFrame of the project plan
        
    Returns:
        list: List of alert messages
    """
    alerts = []
    
    if df is None or df.empty:
        return alerts
    
    current_year = datetime.now().year
    
    try:
        # Alert 1: Current year project with prior year features (2025.)
        if str(current_year) in project_theme:
            # Find features (rows starting with F1, F2, or F3)
            feature_mask = df['Work Breakdown'].fillna('').str.match(r'^F[123]\d*', na=False)
            features_df = df[feature_mask].copy()
            
            # Check for 2025. in Release column (exact pattern)
            if 'Release' in features_df.columns:
                prior_year_mask = features_df['Release'].fillna('').astype(str).str.startswith('2025.', na=False)
                prior_year_features = features_df[prior_year_mask]['Work Breakdown'].tolist()
                
                if prior_year_features:
                    feature_ids = [f.split()[0] for f in prior_year_features[:3]]  # Get just the ID part
                    more = '...' if len(prior_year_features) > 3 else ''
                    alerts.append(f"{current_year} project contains {len(prior_year_features)} features with 2025 release dates ({', '.join(feature_ids)}{more})")
        
        # Alert 2: Features with Actual End Date within configured window and below completion threshold
        if 'Actual End Date' in df.columns and '% Complete' in df.columns:
            # Filter for features (F1, F2, or F3)
            feature_mask = df['Work Breakdown'].fillna('').str.match(r'^F[123]\d*', na=False)
            features_df = df[feature_mask].copy()
            
            if not features_df.empty:
                today = datetime.now()
                due_window_end = today + timedelta(days=FEATURE_DUE_WINDOW_DAYS)
                
                # Convert Actual End Date to datetime
                features_df['Actual End Date'] = pd.to_datetime(features_df['Actual End Date'], errors='coerce')
                
                # Filter: Actual End Date within next configured window
                date_mask = (features_df['Actual End Date'].notna()) & \
                           (features_df['Actual End Date'] >= today) & \
                           (features_df['Actual End Date'] <= due_window_end)
                upcoming_features = features_df[date_mask].copy()
                
                if not upcoming_features.empty:
                    # Convert % Complete to float (handle 0-1 and 0-100 formats)
                    upcoming_features['pct_float'] = upcoming_features['% Complete'].apply(
                        lambda x: float(x) * 100 if pd.notna(x) and float(x) <= 1 else float(x) if pd.notna(x) else 0
                    )
                    
                    incomplete_mask = upcoming_features['pct_float'] < FEATURE_MIN_COMPLETE_PCT
                    incomplete_features = upcoming_features[incomplete_mask]
                    
                    if not incomplete_features.empty:
                        # Calculate days until end for each
                        incomplete_features['days_until'] = (incomplete_features['Actual End Date'] - today).dt.days
                        
                        feature_list = []
                        for _, row in incomplete_features.head(2).iterrows():
                            feature_id = str(row['Work Breakdown']).split()[0]
                            feature_list.append({
                                'id': feature_id,
                                'percent': row['pct_float'],
                                'days': int(row['days_until'])
                            })
                        
                        feature_summary = ', '.join([f"{f['id']} ({f['percent']:.0f}%, {f['days']} days)" for f in feature_list])
                        alerts.append(
                            f"{len(incomplete_features)} feature(s) ending within {FEATURE_DUE_WINDOW_DAYS} days are <{FEATURE_MIN_COMPLETE_PCT}% complete: {feature_summary}"
                        )
        
        # Alert 3: Planning row at 0% complete
        planning_mask = df['Work Breakdown'].fillna('').str.contains('Planning', case=False, na=False)
        planning_rows = df[planning_mask]
        if not planning_rows.empty:
            planning_pct = planning_rows.iloc[0].get('% Complete', None)
            if pd.notna(planning_pct):
                pct = float(planning_pct) * 100 if planning_pct <= 1 else float(planning_pct)
                if pct == 0:
                    alerts.append("Planning row is 0% complete")
        
        # Alert 4: EAC vs OS Approved > or < 10% (Tech only)
        # Find Optics Total and Aha Total in Financials section
        # financials_mask = df['Work Breakdown'].fillna('').str.contains('Financials', case=False, na=False)
        # financials_df = df[financials_mask]
        
        # optics_total_eac = 0 
        # aha_total = 0
        
        # if not financials_df.empty:
        #     optics_total_mask = financials_df['Work Breakdown'].fillna('').str.contains('Optics Total', case=False, na=False)
        #     optics_total_rows = financials_df[optics_total_mask]
        #     if not optics_total_rows.empty and 'EAC' in optics_total_rows.columns:
        #         eac_val = optics_total_rows.iloc[0].get('EAC', 0)
        #         if pd.notna(eac_val):
        #             optics_total_eac = float(eac_val)
            
        #     aha_total_mask = financials_df['Work Breakdown'].fillna('').str.contains('Aha Total', case=False, na=False)
        #     aha_total_rows = financials_df[aha_total_mask]
        #     if not aha_total_rows.empty:
        #         # Aha Total might be in a column like "Aha OS Approved Amount" or similar
        #         for col in aha_total_rows.columns:
        #             if 'aha' in col.lower() or 'approved' in col.lower():
        #                 aha_val = aha_total_rows.iloc[0].get(col, 0)
        #                 if pd.notna(aha_val) and aha_val > 0:
        #                     aha_total = float(aha_val)
        #                     break
        
        # if optics_total_eac > 0 and aha_total > 0:
        #     variance_pct = abs((optics_total_eac - aha_total) / aha_total) * 100
        #     if variance_pct >= 10:
        #         direction = "over" if optics_total_eac > aha_total else "under"
        #         alerts.append(f"Tech EAC (${int(optics_total_eac):,}) is {variance_pct:.1f}% {direction} OS Approved (${int(aha_total):,})")
        
        # Alert 5: No Optics tasks exist at all
        optics_info = extract_optics_tasks(df)
        
        if not optics_info['has_optics_tasks']:
            # Check if Execution is above threshold despite no Optics tasks
            execution_percent = optics_info.get('execution_percent')
            if execution_percent and execution_percent > EXECUTION_WITHOUT_OPTICS_MIN_PCT:
                alerts.append(f"Execution is {execution_percent:.1f}% but there are no Optics tasks")
            else:
                alerts.append("No Optics tasks configured")
        else:
            # Alert 6: Optics tasks exist but no actuals AND Execution >10%
            # COMMENTED OUT - Need to refine logic
            # execution_percent = optics_info['execution_percent']
            
            # if execution_percent and execution_percent > 10:
            #     # Find the Optics Total row
            #     optics_total_mask = df['Work Breakdown'].fillna('').str.contains('Optics Total', case=False, na=False)
            #     optics_total_rows = df[optics_total_mask]
            #     
            #     has_actuals = False
            #     if not optics_total_rows.empty:
            #         optics_total_row = optics_total_rows.iloc[0]
            #         
            #         # Check multiple possible actuals columns
            #         possible_actuals_columns = ['Actuals', 'Actual Cost', 'Actual Hours', 'Actuals Total', 'Actual']
            #         
            #         for col in possible_actuals_columns:
            #             if col in optics_total_row.index:
            #                 try:
            #                     val = optics_total_row[col]
            #                     if pd.notna(val) and val != '':
            #                         val_float = float(val)
            #                         if val_float > 0:
            #                             has_actuals = True
            #                             break
            #                 except (ValueError, TypeError):
            #                     continue
            #         
            #         # If no specific column found, check any column with 'actual' in the name
            #         if not has_actuals:
            #             for col in optics_total_row.index:
            #                 if 'actual' in str(col).lower():
            #                     try:
            #                         val = optics_total_row[col]
            #                         if pd.notna(val) and val != '':
            #                             val_float = float(val)
            #                             if val_float > 0:
            #                                 has_actuals = True
            #                                 break
            #                     except (ValueError, TypeError):
            #                         continue
            #     
            #     if not has_actuals:
            #         alerts.append(f"Execution is {execution_percent:.1f}% complete but no Optics actuals recorded")
            pass
            
            # Alert 7 & 8: Application-level under/over burn analysis (LLM-based)
            burn_analysis = analyze_burn_with_llm(df)
            
            # Filter out 0% apps and Archs/Planning/Testing from all categories
            # Also filter out items with <15% gap
            def extract_percentages(item_str):
                """Extract App and Optics percentages from alert string"""
                import re
                # Match patterns like "App: 50%, Optics: 30%" or "App: 50.5%, Optics: 30.2%"
                app_match = re.search(r'App:\s*([\d.]+)%', item_str)
                optics_match = re.search(r'Optics:\s*([\d.]+)%', item_str)
                if app_match and optics_match:
                    return float(app_match.group(1)), float(optics_match.group(1))
                return None, None
            
            if burn_analysis.get('missing_optics'):
                # Remove entries with 0% or 0.0% and Archs/Planning/Testing
                filtered_missing = [
                    item for item in burn_analysis['missing_optics']
                    if 'App: 0%' not in item and 'App: 0.0%' not in item and ARCHS_PLANNING_TESTING not in item
                ]
                burn_analysis['missing_optics'] = filtered_missing
            
            if burn_analysis.get('underburn'):
                # Filter out 0%, Archs/Planning/Testing, AND items with gap <15%
                filtered_underburn = []
                for item in burn_analysis['underburn']:
                    if 'App: 0%' in item or 'App: 0.0%' in item or ARCHS_PLANNING_TESTING in item:
                        continue
                    app_pct, optics_pct = extract_percentages(item)
                    if app_pct is not None and optics_pct is not None:
                        gap = app_pct - optics_pct
                        if gap >= UNDER_OVER_BURN_GAP_PCT:
                            filtered_underburn.append(item)
                burn_analysis['underburn'] = filtered_underburn
            
            if burn_analysis.get('overburn'):
                # Filter out 0%, Archs/Planning/Testing, AND items with gap <15%
                filtered_overburn = []
                for item in burn_analysis['overburn']:
                    if 'App: 0%' in item or 'App: 0.0%' in item or ARCHS_PLANNING_TESTING in item:
                        continue
                    app_pct, optics_pct = extract_percentages(item)
                    if app_pct is not None and optics_pct is not None:
                        gap = optics_pct - app_pct
                        if gap >= UNDER_OVER_BURN_GAP_PCT:
                            filtered_overburn.append(item)
                burn_analysis['overburn'] = filtered_overburn
            
            # Generate missing optics task alert
            if burn_analysis.get('missing_optics'):
                missing_list = burn_analysis['missing_optics']
                app_summary = ', '.join(missing_list)
                alerts.append(f"Applications with progress but no matching Optics task: {app_summary}")
            
            # Generate under burn alert
            if burn_analysis.get('underburn'):
                underburn_list = burn_analysis['underburn']
                app_summary = ', '.join(underburn_list)
                alerts.append(f"Under Burn: {app_summary}")
            
            # Generate over burn alert
            if burn_analysis.get('overburn'):
                overburn_list = burn_analysis['overburn']
                app_summary = ', '.join(overburn_list)
                alerts.append(f"Over Burn: {app_summary}")
    
    except Exception as e:
        print(f"      ⚠️  Error in rule-based alerts: {e}")
    
    return alerts


def analyze_project_optics_alignment(project_theme: str, df: pd.DataFrame) -> Dict[str, Any]:
    """
    Analyze a single project for all alert scenarios using DataFrame.
    
    Args:
        project_theme: Strategic theme ID
        df: DataFrame of the project plan from Smartsheet
        
    Returns:
        dict: {
            'status': {
                'planning_percent': float,
                'execution_percent': float
            },
            'alerts': [alert1, alert2, ...]
        }
    """
    # Extract status information
    status = {
        'planning_percent': None,
        'execution_percent': None
    }
    
    try:
        # Get Planning % Complete
        planning_mask = df['Work Breakdown'].fillna('').str.contains('Planning', case=False, na=False)
        planning_rows = df[planning_mask]
        if not planning_rows.empty:
            planning_pct = planning_rows.iloc[0].get('% Complete', None)
            if pd.notna(planning_pct):
                try:
                    pct = float(planning_pct)
                    status['planning_percent'] = pct * 100 if pct <= 1 else pct
                except (ValueError, TypeError):
                    pass
        
        # Get Execution % Complete
        execution_mask = df['Work Breakdown'].fillna('').str.contains('Execution', case=False, na=False)
        execution_rows = df[execution_mask]
        if not execution_rows.empty:
            exec_pct = execution_rows.iloc[0].get('% Complete', None)
            if pd.notna(exec_pct):
                try:
                    pct = float(exec_pct)
                    status['execution_percent'] = pct * 100 if pct <= 1 else pct
                except (ValueError, TypeError):
                    pass
    except Exception as e:
        print(f"      ⚠️  Error extracting status: {e}")
    
    # Get rule-based alerts from DataFrame analysis
    alerts = check_rule_based_alerts(project_theme, df)
    
    return {
        'status': status,
        'alerts': alerts
    }


def generate_needs_attention_for_all_projects() -> Dict[str, List[str]]:
    """
    Generate needs attention alerts for all active projects by fetching fresh DataFrames from Smartsheet.
    
    Returns:
        dict: {project_theme: [attention_item1, attention_item2]}
    """
    mongo_helper = MongoDBHelper()
    all_plans = mongo_helper.get_all_plans()
    
    if not all_plans:
        print("❌ No plans found in MongoDB")
        return {}
    
    print(f"📊 Total plans in MongoDB: {len(all_plans)}")
    
    # Filter for active projects
    active_plans = {
        theme: data for theme, data in all_plans.items() 
        if data.get('active', False)
    }
    
    print(f"✅ Active projects: {len(active_plans)}")
    
    if not active_plans:
        print("❌ No active projects found. Make sure projects have 'active': True in MongoDB")
        return {}
    
    needs_attention = {}
    
    for project_theme, project_data in active_plans.items():
        print(f"\n🔍 Analyzing {project_theme}...")
        
        # Get sheet_id from metadata
        sheet_id = project_data.get('sheet id')
        if not sheet_id:
            print(f"   ⚠️  No sheet_id found in metadata - skipping")
            continue
        
        # Fetch fresh DataFrame from Smartsheet
        print(f"   📥 Fetching fresh data from Smartsheet (ID: {sheet_id})...")
        try:
            df = smartsheet_to_pandas(sheet_id)
            
            if df is None or df.empty:
                print(f"   ⚠️  Failed to fetch DataFrame or sheet is empty - skipping")
                continue
            
            print(f"   ✓ Loaded {len(df)} rows from Smartsheet")
        except Exception as e:
            print(f"   ❌ Error fetching from Smartsheet: {e}")
            continue
        
        # Analyze using DataFrame
        analysis_result = analyze_project_optics_alignment(project_theme, df)
        
        status = analysis_result['status']
        attention_items = analysis_result['alerts']
        
        # Display status
        planning = status.get('planning_percent')
        execution = status.get('execution_percent')
        print(f"   📊 Status: Planning={planning}%, Execution={execution}%")
        
        if attention_items:
            print(f"   ✅ Found {len(attention_items)} attention items:")
            for item in attention_items:
                print(f"      • {item}")
            needs_attention[project_theme] = {
                'status': status,
                'alerts': attention_items
            }
        else:
            print(f"   ✓ No issues found")
            needs_attention[project_theme] = {
                'status': status,
                'alerts': []
            }
    
    return needs_attention


def save_needs_attention_to_mongodb(needs_attention: Dict[str, Dict[str, Any]]) -> bool:
    """
    Save needs attention alerts to MongoDB for dashboard display.
    
    Args:
        needs_attention: Dict of {project_theme: {'status': {...}, 'alerts': [...]}}
        
    Returns:
        bool: Success status
    """
    try:
        mongo_helper = MongoDBHelper()
        db = mongo_helper.db
        alerts_collection = db['needs_attention']
        
        # Clear existing alerts
        alerts_collection.delete_many({})
        
        # Insert new alerts
        for project_theme, data in needs_attention.items():
            alert_doc = {
                'project_theme': project_theme,
                'status': data.get('status', {}),
                'needs_attention': data.get('alerts', []),
                'generated_at': datetime.now().isoformat(),
                'resolved': False
            }
            alerts_collection.insert_one(alert_doc)
        
        print(f"✅ Saved {len(needs_attention)} project alerts to MongoDB")
        return True
    
    except Exception as e:
        print(f"❌ Error saving to MongoDB: {e}")
        return False


if __name__ == "__main__":
    print("Analyzing projects for 'Needs Attention' alerts...")
    print("=" * 80)
    
    # Generate alerts
    needs_attention = generate_needs_attention_for_all_projects()
    
    print(f"\nFound {len(needs_attention)} projects with attention items:\n")
    
    # Display results
    for project_theme, items in needs_attention.items():
        print(f"📋 {project_theme}")
        for item in items:
            print(f"   {item}")
        print()
    
    # Save to MongoDB
    if needs_attention:
        save_option = input("\nSave these alerts to MongoDB? (y/n): ").strip().lower()
        if save_option == 'y':
            save_needs_attention_to_mongodb(needs_attention)
    else:
        print("No attention items found - all projects look good!")
