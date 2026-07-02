import os
import certifi
import pandas as pd
# from smartsheet.models import Row, Cell
from engine.mapping import get_aha_data, get_lead_team_mapping, get_optics_financials, get_rally_data_hcp
import math
import json
from collections import defaultdict
import requests
from config import Config
from engine.mongodb_helper import MongoDBHelper

# Load configuration
config = Config()

TOKEN = config.SMARTSHEET_API_KEY
SMARTSHEET_HEADERS = config.get_smartsheet_headers()
BASE_URL = config.SMARTSHEET_BASE_URL

# --------------------------------- RETRIEVING SMARTSHEET AS DF ----------------------------------

def smartsheet_to_pandas(id):
    '''
    Returning the smartsheet as a dataframe using the sheet id saved in the plan metadata json.
    '''
    # starting the smartsheet connection
    sheet_response = requests.get(
        f"{BASE_URL}/sheets/{id}",
        headers=SMARTSHEET_HEADERS,
        verify=False
    )

    sheet = sheet_response.json()
    
    # getting the column names
    columns = [col['title'] for col in sheet.get('columns', [])]

    # saving each row of data from the smartsheet and pushing it to a dataframe
    data = []
    for row in sheet.get('rows', []):
        row_data = []
        for cell in row.get('cells', []):
            row_data.append(cell.get('value', ''))
        while len(row_data) < len(columns):
            row_data.append('')
        data.append(row_data)

    df = pd.DataFrame(data, columns=columns)
    return df

# --------------------------------- RALLY DATA CLEANING HELPER FUNCTIONS ----------------------------------

def valid_value(val):
    '''
    Checking to see if a value exists.
    '''
    if pd.isna(val) or (isinstance(val, float) and math.isnan(val)):
        return ''
    if isinstance(val, pd.Timestamp):
        return val.strftime('%Y-%m-%d')
    return str(val).strip()

def format_smartsheet_value(col_name, value):
    if col_name == 'Rally Point Estimate':
        try:
            return float(value)
        except (ValueError, TypeError):
            return ''
    elif col_name == '% Complete':
        try:
            if isinstance(value, str) and value.endswith('%'):
                return float(value.rstrip('%')) / 100
            return float(value)
        except (ValueError, TypeError):
            return ''
    elif col_name == 'Level':
        try:
            return int(value)
        except (ValueError, TypeError):
            return ''  
    elif col_name == 'Rally Cost Estimate':
        try:
            return float(value)
        except (ValueError, TypeError):
            return ''
    elif col_name == 'Actuals Est (Hours x Rate)':
        try:
            return float(value)
        except (ValueError, TypeError):
            return ''
    elif col_name == 'ETCs':
        try:
            return float(value)
        except (ValueError, TypeError):
            return ''
    elif col_name == 'EACs':    
        try:
            return float(value)
        except (ValueError, TypeError):
            return ''
    return value

def rows_to_cells(row, mapping, parent_level):
    '''
    Turning the dataframe rows into cells which can be sent to smartsheet via its API.
    '''
    cells = []

    # function to create a smartsheet Cell
    def make_cell(col_name, value):
        # Skip columns that don't exist in the mapping
        if col_name not in mapping:
            return None
        return {
            'columnId': mapping[col_name],
            'value': format_smartsheet_value(col_name, value)
        }
    
    # adding the appropriate Cells to a list
    cells.append(make_cell('Work Breakdown', f"{valid_value(row['ID'])} - {valid_value(row.get('Name'))}"))
    cells.append(make_cell('Task ID', row['ID']))
    cells.append(make_cell('Level', parent_level + 1))
    cells.append(make_cell('Rally Lead Team', valid_value(row.get('Rally Lead Team', ''))))
    cells.append(make_cell('Assigned To', valid_value(row.get('Owner', ''))))
    cells.append(make_cell('Release', valid_value(row.get('Release', ''))))
    # Try both column names for end date (old sheets use 'Actual End Date', new sheets use 'Planned End Date (Rally)')
    cells.append(make_cell('Actual End Date', valid_value(row.get('Planned End Date', ''))))
    cells.append(make_cell('Planned End Date (Rally)', valid_value(row.get('Planned End Date', ''))))
    cells.append(make_cell('Status', valid_value(row.get('State', ''))))
    cells.append(make_cell('% Complete', valid_value(row.get('% Done By Story Plan Estimate', '0%'))))
    cells.append(make_cell('Rally Point Estimate', valid_value(row.get('Preliminary Estimate Value', ''))))
    cells.append(make_cell('Planned End Date', valid_value('2026-01-01')))
    cells.append(make_cell('Rally Cost Estimate', valid_value(row.get('Rally Cost Estimate', ''))))

    # Filter out None values (columns that don't exist)
    return [cell for cell in cells if cell is not None]

# --------------------------------- ENSURE REQUIRED COLUMNS EXIST ----------------------------------

def ensure_columns_exist(id):
    '''
    Checks if 'Start Date' and 'Notes' columns exist in the sheet.
    If they don't exist, adds them at specific positions.
    - 'Notes' is added to the right of '% Complete'
    - 'Start Date' is added to the left of 'Planned End Date (Rally)'
    '''
    # Get the sheet
    sheet_response = requests.get(
        f"{BASE_URL}/sheets/{id}",
        headers=SMARTSHEET_HEADERS,
        verify=False
    )
    sheet = sheet_response.json()
    
    # Get existing columns with their indices
    columns_list = sheet.get('columns', [])
    existing_columns = {col['title']: {'col': col, 'index': idx} for idx, col in enumerate(columns_list)}
    
    columns_to_add = []
    
    # Check for Notes column (should be to the right of '% Complete')
    if 'Notes' not in existing_columns:
        print("'Notes' column not found - will add it to the right of '% Complete'")
        if '% Complete' in existing_columns:
            # Add after % Complete (index + 1)
            notes_index = existing_columns['% Complete']['index'] + 1
        else:
            # If % Complete doesn't exist, add at the end
            notes_index = len(columns_list)
        
        columns_to_add.append({
            'title': 'Notes',
            'type': 'TEXT_NUMBER',
            'index': notes_index
        })
    
    # Check for Start Date column (should be to the left of 'Planned End Date (Rally)' OR 'Actual End Date')
    if 'Start Date' not in existing_columns:
        if 'Planned End Date (Rally)' in existing_columns:
            # Add before Planned End Date (Rally) - at the same index (pushes it to the right)
            start_date_index = existing_columns['Planned End Date (Rally)']['index']
            print("'Start Date' column not found - will add it to the left of 'Planned End Date (Rally)'")
        elif 'Actual End Date' in existing_columns:
            # If Planned End Date (Rally) doesn't exist, try Actual End Date
            start_date_index = existing_columns['Actual End Date']['index']
            print("'Start Date' column not found - will add it to the left of 'Actual End Date'")
        else:
            # If neither exists, add at the end
            start_date_index = len(columns_list)
            print("'Start Date' column not found - will add it at the end")
        
        columns_to_add.append({
            'title': 'Start Date',
            'type': 'DATE',
            'index': start_date_index
        })
    
    # Add the columns if needed (add in reverse order to maintain correct positions)
    if columns_to_add:
        # Sort by index in descending order to add from right to left
        columns_to_add.sort(key=lambda x: x['index'], reverse=True)
        
        for col in columns_to_add:
            payload = [{
                'title': col['title'],
                'type': col['type'],
                'index': col['index']
            }]
            
            res = requests.post(
                f"{BASE_URL}/sheets/{id}/columns",
                headers=SMARTSHEET_HEADERS,
                json=payload,
                verify=False
            )
            
            if res.status_code == 200:
                print(f"✓ Successfully added '{col['title']}' column at index {col['index']}")
            else:
                print(f"✗ Failed to add '{col['title']}' column: {res.status_code} - {res.text}")
        
        return True  # Columns were added
    else:
        print("✓ 'Start Date' and 'Notes' columns already exist")
        return False  # No columns added

# --------------------------------- AHA UPDATE FUNCTION ----------------------------------

def update_from_aha(st):
    '''
    Pulling the new Aha impacts and updating the dataframe appropriately. (stil need to add in 
    functionality to push this to smartsheet.)
    The 'st' parameter can be either a strategic theme OR an AHA idea.
    '''
    # OLD: opening the plan metadata file (active)
    # with open('documents/plan_metadata.json', 'r') as file:
    #     data = json.load(file)

    # # getting the sheet id
    # id = data[st]['sheet id']
    # aha = data[st]['idea']
    
    # NEW: Get metadata from MongoDB - search by theme or idea
    mongo_helper = MongoDBHelper()
    data, actual_key = mongo_helper.get_plan_metadata_by_key(st)
    mongo_helper.close()
    
    if not data:
        raise ValueError(f"No plan found with strategic theme or idea: {st}")
    
    id = data['sheet id']
    aha = data['idea']

    sheet_response = requests.get(
        f"{BASE_URL}/sheets/{id}",
        headers=SMARTSHEET_HEADERS,
        verify=False
    )

    sheet = sheet_response.json()

    # getting the smartsheet as a df
    smartsheet_df = smartsheet_to_pandas(id)

    # getting the aha data - fetch all return values to update metadata if needed (SINGLE API CALL)
    aha_df, os_approved, theme, tag, prj, go_live = get_aha_data(aha)

    aha_df = aha_df[['Impacts Delivery team', 'Impact Cost']].rename(columns={'Impacts Delivery team': 'Impacted Applications', 'Impact Cost': 'Aha OS Approved Amount'})
    
    # Update metadata in MongoDB if any values have changed
    metadata_updates = {}
    
    if theme != data.get('rally_theme', 'none'):
        metadata_updates['rally_theme'] = theme
        print(f"Updating theme in metadata: {data.get('rally_theme', 'none')} -> {theme}")
    
    if tag and tag != data.get('tag', ''):
        metadata_updates['tag'] = tag
        print(f"Updating tag in metadata: {data.get('tag', '')} -> {tag}")
    
    if prj and prj != data.get('prj', ''):
        metadata_updates['prj'] = prj
        print(f"Updating prj in metadata: {data.get('prj', '')} -> {prj}")
    
    if os_approved and float(os_approved) != float(data.get('os_approved', 0)):
        metadata_updates['os_approved'] = float(os_approved)
        print(f"Updating os_approved in metadata: {data.get('os_approved', 0)} -> {os_approved}")
    
    if go_live and go_live != data.get('go_live', ''):
        metadata_updates['go_live'] = go_live
        print(f"Updating go_live in metadata: {data.get('go_live', '')} -> {go_live}")
    
    # Apply all metadata updates at once if there are any changes
    if metadata_updates:
        mongo_helper = MongoDBHelper()
        mongo_helper.update_plan_metadata(actual_key, metadata_updates)
        mongo_helper.close()
        print(f"Updated {len(metadata_updates)} metadata field(s) in MongoDB")

    # Prepare Aha data - rename columns for clarity
    aha_df = aha_df.rename(columns={
        'Impacts Delivery team': 'Impacted Applications',
        'Impact Cost': 'Aha OS Approved Amount'
    })

    # Convert Aha OS Approved Amount to numeric
    aha_df['Aha OS Approved Amount'] = pd.to_numeric(
        aha_df['Aha OS Approved Amount'].astype(str).str.replace('$', '').str.replace(',', '').str.strip(), 
        errors='coerce'
    )
    
    print(f"\n[DEBUG] ==== AHA DATA ====")
    print(f"Aha DataFrame:\n{aha_df[['Impacted Applications', 'Aha OS Approved Amount']]}")
    print(f"Total Aha impacts: {len(aha_df)}")

    # Add row IDs to smartsheet dataframe
    row_id = []
    for row in sheet['rows']:
        row_id.append(row['id'])
    smartsheet_df['row_id'] = row_id

    # Find the column where the 'Impacted Applications' header row contains 'Aha OS Approved Amt'
    # This identifies which column has the Aha amounts (not looking at actual column name)
    aha_amount_col_name = None
    aha_column_id = None
    
    # Look for the row where Work Breakdown is 'Impacted Applications' (this is the header row)
    impacted_apps_rows = smartsheet_df[smartsheet_df['Work Breakdown'] == 'Impacted Applications']
    
    print(f"\n[DEBUG] ==== FINDING AHA COLUMN ====")
    print(f"Found {len(impacted_apps_rows)} 'Impacted Applications' header rows")
    
    if not impacted_apps_rows.empty:
        # Check each column in this header row to find which one contains 'Aha OS Approved Amt'
        header_row = impacted_apps_rows.iloc[0]
        print(f"[DEBUG] Checking header row columns for 'Aha OS Approved Amt'...")
        
        for col_idx, col_name in enumerate(smartsheet_df.columns):
            if col_name not in ['Work Breakdown', 'row_id']:
                col_value = str(header_row[col_name]).strip()
                if col_value == 'Aha OS Approved Amount':
                    # Now find the actual Smartsheet column ID and type
                    actual_col_idx = list(smartsheet_df.columns).index(col_name)
                    column_info = sheet['columns'][actual_col_idx]
                    column_type = column_info.get('type', 'UNKNOWN')
                    
                    # Check if this column type can accept numeric data
                    numeric_compatible_types = ['TEXT_NUMBER', 'CURRENCY', 'PERCENT', 'NUMBER']
                    if column_type not in numeric_compatible_types:
                        print(f"WARNING: Column '{col_name}' (type: {column_type}) for 'Aha OS Approved Amount' cannot accept numeric data!")
                        print(f"Skipping this column. Need to find or create proper numeric column.")
                        continue
                    
                    aha_amount_col_name = col_name
                    aha_column_id = column_info['id']
                    print(f"Found 'Aha OS Approved Amt' at column position {actual_col_idx} (column name: {col_name}, type: {column_type})")
                    print(f"Column ID: {aha_column_id}")
                    break
    
    if not aha_amount_col_name or not aha_column_id:
        print("ERROR: Could not find column with 'Aha OS Approved Amt' in the Impacted Applications header row")
        print(f"[DEBUG] Header row values: {impacted_apps_rows.iloc[0].to_dict() if not impacted_apps_rows.empty else 'No header row found'}")
        return

    print(f"\n[DEBUG] ==== MATCHING ROWS ====")
    print(f"Looking for matches between Aha and Smartsheet...")
    
    # First, identify existing impacts in the "Impacted Applications" section (Financials section only)
    # Important: Only look AFTER "Financials" row to avoid matching impacts from other sections
    past_financials = False
    found_impacted_apps = False
    existing_impacts_in_section = set()
    financials_section_indices = []  # Track row indices in Financials section
    
    for idx, row in smartsheet_df.iterrows():
        wb = str(row.get('Work Breakdown', '')).strip()
        
        # First, we need to pass the Financials section
        if wb == 'Financials':
            past_financials = True
            continue
        
        # Only start looking for Impacted Applications AFTER Financials
        if not past_financials:
            continue
            
        if wb == 'Impacted Applications':
            found_impacted_apps = True
            continue
        elif wb == 'Aha Total':
            break
        elif found_impacted_apps and wb:
            existing_impacts_in_section.add(wb)
            financials_section_indices.append(idx)  # Track this row's index
    
    print(f"Found {len(existing_impacts_in_section)} existing impacts in Impacted Applications section")
    print(f"Financials section row indices: {financials_section_indices}")
    
    rows_to_update = []
    new_impacts = []  # Track new impacted applications not in Smartsheet

    # Iterate through each Aha impacted application
    for _, aha_row in aha_df.iterrows():
        impacted_app = aha_row['Impacted Applications']
        aha_amount = aha_row['Aha OS Approved Amount']
        
        # Check if this impact exists in the Impacted Applications section
        if impacted_app not in existing_impacts_in_section:
            print(f"No match found for: '{impacted_app}' - will add as new row")
            new_impacts.append(aha_row)
            continue
        
        # Find matching rows in Smartsheet - ONLY in Financials section
        # Match on Work Breakdown column AND ensure it's in the financials_section_indices
        matching_rows = smartsheet_df[
            (smartsheet_df['Work Breakdown'] == impacted_app) &
            (smartsheet_df.index.isin(financials_section_indices))
        ]
        
        for idx, ss_row in matching_rows.iterrows():
            status_value = smartsheet_df.loc[idx, 'Status'] if 'Status' in smartsheet_df.columns else ''
            
            # Only update if Status is empty/null
            if pd.notna(status_value) and str(status_value).strip() != '':
                print(f"Skipping '{impacted_app}' - Status not empty: '{status_value}'")
                continue
            
            # Get the current value from Smartsheet using indexed access
            current_value_raw = smartsheet_df.loc[idx, aha_amount_col_name]
            current_value = pd.to_numeric(
                str(current_value_raw).replace('$', '').replace(',', '').strip() if pd.notna(current_value_raw) else '', 
                errors='coerce'
            )
            
            # Round both values for comparison
            aha_amount_rounded = round(aha_amount) if pd.notna(aha_amount) else None
            current_value_rounded = round(current_value) if pd.notna(current_value) else None
            
            # Check if values are different
            if aha_amount_rounded is not None and (current_value_rounded is None or aha_amount_rounded != current_value_rounded):
                print(f"UPDATE: '{impacted_app}' - ${current_value_rounded} -> ${aha_amount_rounded}")
                rows_to_update.append({
                    'id': int(smartsheet_df.loc[idx, 'row_id']),
                    'cells': [{
                        'columnId': aha_column_id,
                        'value': int(aha_amount_rounded),  # Send as whole number
                        'format': ',,,,,,,,,,,,,1,2'  # Number format with 0 decimal places
                    }]
                })
            else:
                print(f"No change: '{impacted_app}' - already ${current_value_rounded}")
        
    # Update the "Aha Total" row if it exists in the smartsheet
    print(f"\n[DEBUG] ==== AHA TOTAL ROW ====")
    aha_total_rows = smartsheet_df[smartsheet_df['Work Breakdown'] == 'Aha Total']
    
    if not aha_total_rows.empty:
        # Calculate the new total from aha_df
        new_aha_total = aha_df['Aha OS Approved Amount'].sum(skipna=True)
        
        # Get the old total from smartsheet
        aha_total_row = aha_total_rows.iloc[0]
        old_aha_total_raw = aha_total_row[aha_amount_col_name]
        old_aha_total = pd.to_numeric(
            str(old_aha_total_raw).replace('$', '').replace(',', '').strip() if pd.notna(old_aha_total_raw) else '', 
            errors='coerce'
        )
        
        # Round both values to nearest whole number for comparison
        new_aha_total_rounded = round(new_aha_total) if pd.notna(new_aha_total) else None
        old_aha_total_rounded = round(old_aha_total) if pd.notna(old_aha_total) else None
        
        # Update if rounded values are different
        if new_aha_total_rounded is not None and (old_aha_total_rounded is None or new_aha_total_rounded != old_aha_total_rounded):
            print(f"UPDATE: Aha Total - ${old_aha_total_rounded} -> ${new_aha_total_rounded}")
            rows_to_update.append({
                'id': int(aha_total_row['row_id']),
                'cells': [{
                    'columnId': aha_column_id,
                    'value': int(new_aha_total_rounded),  # Send as whole number
                    'format': ',,,,,,,,,,,,,1,2'  # Number format with 0 decimal places
                }]
            })
        else:
            print(f"No change: Aha Total already ${old_aha_total_rounded}")
    
    # Add new impacted applications that don't exist in Smartsheet
    print(f"\n[DEBUG] ==== ADDING NEW AHA IMPACTS ====")
    if new_impacts:
        print(f"Found {len(new_impacts)} new impacted applications to add")
        
        # Find the 'Impacted Applications' header row to get its row_id
        impacted_apps_header_rows = smartsheet_df[smartsheet_df['Work Breakdown'] == 'Impacted Applications']
        
        if not impacted_apps_header_rows.empty:
            # Get the Impacted Applications header row ID to use as parent
            impacted_apps_row_id = int(impacted_apps_header_rows.iloc[0]['row_id'])
            
            for new_impact in new_impacts:
                impacted_app = new_impact['Impacted Applications']
                aha_amount = new_impact['Aha OS Approved Amount']
                aha_amount_rounded = round(aha_amount) if pd.notna(aha_amount) else 0
                
                # Create cells for the new row
                new_row_cells = [
                    {
                        'columnId': sheet['columns'][0]['id'],  # Work Breakdown column
                        'value': impacted_app
                    },
                    {
                        'columnId': aha_column_id,
                        'value': int(aha_amount_rounded),
                        'format': ',,,,,,,,,,,,,1,2'  # Number format with 0 decimal places
                    }
                ]
                
                # Find Level column ID
                level_col_id = None
                for col in sheet['columns']:
                    if col['title'] == 'Level':
                        level_col_id = col['id']
                        break
                
                if level_col_id:
                    new_row_cells.append({
                        'columnId': level_col_id,
                        'value': 4  # New impacted apps should be Level 4
                    })
                
                # Add the new row as a child of Impacted Applications row
                print(f"Adding new impacted application: '{impacted_app}' with Aha OS Approved Amount=${int(aha_amount_rounded)}")
                
                new_row_payload = {
                    'parentId': impacted_apps_row_id,  # Add as child of Impacted Applications row
                    'toBottom': True,  # Add to bottom of parent's children
                    'cells': new_row_cells,
                    'format': ',,,,,,,,,5'  # Light yellow background
                }
                
                # POST new row to Smartsheet
                res = requests.post(
                    f"{BASE_URL}/sheets/{id}/rows",
                    headers=SMARTSHEET_HEADERS,
                    json=[new_row_payload],
                    verify=False
                )
                
                if res.status_code == 200:
                    print(f"✓ Successfully added new impacted application: '{impacted_app}'")
                else:
                    print(f"✗ Failed to add new impacted application '{impacted_app}': {res.status_code} - {res.text}")
        else:
            print("Warning: 'Impacted Applications' header row not found, cannot add new impacts")
    else:
        print("No new impacted applications to add - all Aha impacts already exist in Smartsheet")
    
    # Send updates to Smartsheet
    print(f"\n[DEBUG] ==== SENDING UPDATES ====")
    if rows_to_update:
        print(f"Sending {len(rows_to_update)} row updates to Smartsheet...")
        payload = rows_to_update
        res = requests.put(
            f"{BASE_URL}/sheets/{id}/rows",
            headers=SMARTSHEET_HEADERS,
            json=payload,
            verify=False
        )
        print(f"Smartsheet API response: {res.status_code}")
        if res.status_code == 200:
            print("✓ Updates successful!")
        else:
            print(f"✗ Update failed: {res.text}")
    else:
        print("No rows need updating - all values match or have non-empty Status") 

# --------------------------------- RALLY UPDATE FUNCTIONS ----------------------------------

def pull_in_capabilities_execution(id, rally_df):
    '''
    Simply adds any new capabilities sequentially under "Functional Capabilities" parent.
    '''
    # Ensure required columns exist before any updates
    print("\n[COLUMN CHECK] Ensuring 'Start Date' and 'Notes' columns exist...")
    ensure_columns_exist(id)
    
    # starting the smartsheet connection
    sheet_response = requests.get(
        f"{BASE_URL}/sheets/{id}",
        headers=SMARTSHEET_HEADERS,
        verify=False
    )

    sheet = sheet_response.json()

    # getting the smartsheet as a df
    smartsheet_df = smartsheet_to_pandas(id)

    # getting the smartsheet column names and reference IDs
    col_map = {col['title']: col['id'] for col in sheet.get('columns', [])}

    # FIX: Normalize any 'Functional Capabilities' variations to the standard name
    rows_to_fix = []
    for row in sheet['rows']:
        work_breakdown = None
        row_id = row['id']
        
        for cell in row.get('cells', []):
            if cell['columnId'] == col_map['Work Breakdown']:
                work_breakdown = str(cell.get('value', '')).strip() if cell.get('value', '') else ''
                break
        
        # If Work Breakdown contains 'Functional Capabilities' but is not exactly the correct name, fix it
        if work_breakdown and 'Functional Capabilities' in work_breakdown and work_breakdown != 'Functional Capabilities (do not delete)':
            print(f"Fixing row: '{work_breakdown}' -> 'Functional Capabilities (do not delete)'")
            rows_to_fix.append({
                'id': row_id,
                'cells': [{
                    'columnId': col_map['Work Breakdown'],
                    'value': 'Functional Capabilities (do not delete)'
                }]
            })
    
    # Apply fixes if needed
    if rows_to_fix:
        fix_res = requests.put(
            f"{BASE_URL}/sheets/{id}/rows",
            headers=SMARTSHEET_HEADERS,
            json=rows_to_fix,
            verify=False
        )
        if fix_res.status_code == 200:
            print(f"✓ Fixed {len(rows_to_fix)} 'Functional Capabilities' row(s)")
            
            # Re-fetch the sheet to get updated values
            sheet_response = requests.get(
                f"{BASE_URL}/sheets/{id}",
                headers=SMARTSHEET_HEADERS,
                verify=False
            )
            sheet = sheet_response.json()
            print("✓ Re-fetched sheet with updated row names")
        else:
            print(f"✗ Failed to fix 'Functional Capabilities' rows: {fix_res.status_code}")

    pcid = next(col['id'] for col in sheet.get('columns', []) if col['title'] == '% Complete')
    rpid = next(col['id'] for col in sheet.get('columns', []) if col['title'] == 'Rally Point Estimate')
    rcid = next(col['id'] for col in sheet.get('columns', []) if col['title'] == 'Rally Cost Estimate')
    rltid = next(col['id'] for col in sheet.get('columns', []) if col['title'] == 'Rally Lead Team')

    # Track existing capabilities in Execution section only (before Application View)
    existing_capability_ids = set()
    application_view_reached = False
    
    for _, row in smartsheet_df.iterrows():
        work_breakdown = str(row.get('Work Breakdown', '')).strip()
        if work_breakdown == 'Application View':
            application_view_reached = True
            break
        
        task_id = str(row.get('Task ID', '')).strip()
        if task_id and task_id.startswith('C'):
            existing_capability_ids.add(task_id)

    # Find "Functional Capbilities" parent row
    case_install_ready_parent = None
    
    for row in sheet['rows']:
        work_breakdown = None
        row_id = row['id']
        row_level = None

        for cell in row.get('cells', []):
            if cell['columnId'] == col_map['Work Breakdown']:
                work_breakdown = str(cell.get('value', '')).strip() if cell.get('value', '') else ''
            if cell['columnId'] == col_map['Level']:
                row_level = int(cell.get('value', 1)) if cell.get('value', '') is not None else 1

        if work_breakdown == 'Functional Capabilities (do not delete)':
            case_install_ready_parent = {'row_id': row_id, 'level': row_level}
            break
    
    if not case_install_ready_parent:
        print("Warning: 'Functional Capabilities (do not delete)' parent not found in sheet. Skipping execution capabilities.")
        return

    # changing the Rally df data types
    rally_df['ID'] = rally_df['ID'].astype(str).str.strip()
    rally_df['Rally Lead Team'] = rally_df['Rally Lead Team'].astype(str).str.strip()
    rally_df['Preliminary Estimate Value'] = pd.to_numeric(
        rally_df['Preliminary Estimate Value'], errors='coerce'
    ).astype('Int64')

    # subsetting the Rally df to be rows that are capabilities
    rally_capabilities = rally_df[rally_df['ID'].str.startswith('C', na=False)]
    
    rows_to_add = []

    # Add each new capability under Functional Capabilities
    for _, cap_row in rally_capabilities.iterrows():
        cap_id = cap_row['ID']

        # Skip if capability already exists in Execution section
        if cap_id in existing_capability_ids:
            continue

        parent_id = case_install_ready_parent['row_id']
        parent_level = case_install_ready_parent['level']

        # creating a new smartsheet row object
        new_row = {
            'parentId': parent_id,
            'format': ',,1,,,,,,,13',
            'cells': []
        }

        # calling the rows to cells function to create a new smartsheet cell in the proper format
        rtc = rows_to_cells(cap_row, col_map, parent_level)

        for i in rtc:
            # Exclude % Complete, Rally Point Estimate, and Rally Cost Estimate columns (will use formulas)
            if i['columnId'] in [pcid, rpid, rcid]:
                continue
            # Set Rally Lead Team to empty string for capabilities in execution section
            if i['columnId'] == rltid:
                i['value'] = ''
            new_row['cells'].append(i)

        new_row['cells'].extend([
            {
                'columnId': pcid,
                'formula': '=IF(COUNT(CHILDREN()) > 0, AVG(CHILDREN()), 0)'
            },
            {
                'columnId': rpid,
                'formula': '=IF(COUNT(CHILDREN()) > 0, SUM(CHILDREN()), 0)'
            },
            {
                'columnId': rcid,
                'formula': '=IF(COUNT(CHILDREN()) > 0, SUM(CHILDREN()), 0)'
            }
        ])
        rows_to_add.append(new_row)

    for i in rows_to_add:
        payload = [i]
        res = requests.post(
            f"{BASE_URL}/sheets/{id}/rows",
            headers=SMARTSHEET_HEADERS,
            json=payload,
            verify=False
        )

def pull_in_capabilities_application_view(id, rally_df, aha_teams=None):
    '''
    Pulling in new capabilities from Rally into the Application View section.
    Implements the complex grouping logic where:
    - Each capability can appear multiple times (once per unique feature lead team)
    - Each instance goes under the correct AHA delivery team (Level 3 parent)
    - Features are grouped under their corresponding capability instance based on lead team
    - Creates missing AHA delivery team parent rows if they don't exist
    
    Args:
        id: Smartsheet ID
        rally_df: Rally data DataFrame
        aha_teams: List of AHA delivery team names that should exist as Level 3 parents
    '''
    # starting the smartsheet connection
    sheet_response = requests.get(
        f"{BASE_URL}/sheets/{id}",
        headers=SMARTSHEET_HEADERS,
        verify=False
    )

    sheet = sheet_response.json()

    # getting the smartsheet as a df
    smartsheet_df = smartsheet_to_pandas(id)

    # getting the smartsheet column names and reference IDs
    col_map = {col['title']: col['id'] for col in sheet.get('columns', [])}

    pcid = next(col['id'] for col in sheet.get('columns', []) if col['title'] == '% Complete')
    rpid = next(col['id'] for col in sheet.get('columns', []) if col['title'] == 'Rally Point Estimate')
    rcid = next(col['id'] for col in sheet.get('columns', []) if col['title'] == 'Rally Cost Estimate')

    # Track existing capabilities in Application View section only (between Application View and Financials)
    existing_capability_keys = set()
    application_view_reached = False
    financials_reached = False
    
    for _, row in smartsheet_df.iterrows():
        work_breakdown = str(row.get('Work Breakdown', '')).strip()
        
        if work_breakdown == 'Application View':
            application_view_reached = True
            continue
        
        if work_breakdown == 'Financials':
            financials_reached = True
            break
        
        if application_view_reached and not financials_reached:
            task_id = str(row.get('Task ID', '')).strip()
            rally_lead_team = str(row.get('Rally Lead Team', '')).strip()
            if task_id and task_id.startswith('C'):
                existing_capability_keys.add((task_id, rally_lead_team))

    # Build map of Level 3 parent rows (delivery team names) in Application View
    delivery_team_parents = {}
    application_view_reached = False
    financials_reached = False
    application_view_row_id = None  # Track Application View row for adding new teams
    
    for row in sheet['rows']:
        work_breakdown = None
        row_id = row['id']
        row_level = None

        for cell in row.get('cells', []):
            if cell['columnId'] == col_map['Work Breakdown']:
                work_breakdown = str(cell.get('value', '')).strip() if cell.get('value', '') else ''
            if cell['columnId'] == col_map['Level']:
                row_level = int(cell.get('value', 1)) if cell.get('value', '') is not None else 1

        if work_breakdown == 'Application View':
            application_view_reached = True
            application_view_row_id = row_id  # Save this for adding new Level 3 rows
            continue
        
        if work_breakdown == 'Financials':
            financials_reached = True
            break
        
        # Capture Level 3 rows in Application View section (delivery team names)
        if application_view_reached and not financials_reached and row_level == 3:
            delivery_team_parents[work_breakdown] = {'row_id': row_id, 'level': row_level}

    # If aha_teams is provided, ensure all AHA teams have Level 3 parent rows
    missing_aha_teams = []
    if aha_teams and application_view_row_id:
        for team in aha_teams:
            if team not in delivery_team_parents and team != 'Other':  # 'Other' is special case
                missing_aha_teams.append(team)
        
        if missing_aha_teams:
            print(f"Creating missing AHA delivery team parent rows: {missing_aha_teams}")
            
            # Create Level 3 parent rows for missing AHA teams
            for team in missing_aha_teams:
                new_parent_row = {
                    'parentId': application_view_row_id,
                    'format': ',,1,,,,,,,13',
                    'cells': [
                        {
                            'columnId': col_map['Work Breakdown'],
                            'value': team
                        },
                        {
                            'columnId': col_map['Level'],
                            'value': 3
                        }
                    ]
                }
                
                # Add the row to Smartsheet
                res = requests.post(
                    f"{BASE_URL}/sheets/{id}/rows",
                    headers=SMARTSHEET_HEADERS,
                    json=[new_parent_row],
                    verify=False
                )
                
                if res.status_code == 200:
                    result = res.json()
                    if 'result' in result and result['result']:
                        new_row_id = result['result'][0]['id']
                        delivery_team_parents[team] = {'row_id': new_row_id, 'level': 3}
                        print(f"Created Level 3 parent row for '{team}' with ID {new_row_id}")
                    else:
                        print(f"Warning: Could not create parent row for '{team}' - no row ID in response")
                else:
                    print(f"Error creating parent row for '{team}': {res.status_code} - {res.text}")

    # changing the Rally df data types
    rally_df['ID'] = rally_df['ID'].astype(str).str.strip()
    rally_df['Lead Team'] = rally_df['Lead Team'].astype(str).str.strip()
    rally_df['Rally Lead Team'] = rally_df['Rally Lead Team'].astype(str).str.strip()
    rally_df['Solution Capability'] = rally_df['Solution Capability'].astype(str).str.strip() if 'Solution Capability' in rally_df.columns else ''
    rally_df['Preliminary Estimate Value'] = pd.to_numeric(
        rally_df['Preliminary Estimate Value'], errors='coerce'
    ).astype('Int64')

    # Get capabilities and features
    capabilities = rally_df[rally_df['ID'].str.startswith('C', na=False)]
    features = rally_df[rally_df['ID'].str.startswith('F', na=False)]
    
    rows_to_add = []
    unmatched_capabilities = []  # Track capabilities that don't match any AHA team

    # For each capability, find unique feature lead teams and create instances
    for _, cap in capabilities.iterrows():
        cap_id = cap['ID']
        
        # Get all features belonging to this capability
        cap_features = features[features['Solution Capability'] == cap_id]
        
        if cap_features.empty:
            # No features - add to unmatched capabilities for "Other" section
            unmatched_capabilities.append((cap, ''))
            continue
        
        # Get unique Rally Lead Teams from the features
        unique_rally_teams = cap_features['Rally Lead Team'].dropna().unique()
        
        if len(unique_rally_teams) == 0:
            # No valid rally teams - add to unmatched capabilities for "Other" section
            unmatched_capabilities.append((cap, ''))
            continue
        
        # Create one capability instance per unique rally lead team
        for rally_team in unique_rally_teams:
            # Get the mapped Lead Team for this rally team
            # Match the feature's Lead Team (already mapped in rally_df)
            matching_features = cap_features[cap_features['Rally Lead Team'] == rally_team]
            if matching_features.empty:
                continue
            
            # Get the mapped lead team from the first matching feature
            mapped_lead_team = matching_features.iloc[0]['Lead Team']
            
            # Check if this capability instance already exists
            composite_key = (cap_id, rally_team)
            if composite_key in existing_capability_keys:
                continue
            
            # Find the parent delivery team row
            parent_info = delivery_team_parents.get(mapped_lead_team)
            if not parent_info:
                # This capability doesn't match any AHA team - save for "Other" section
                unmatched_capabilities.append((cap, rally_team))
                continue
            
            parent_id = parent_info['row_id']
            parent_level = parent_info['level']

            # Create capability row with the rally_team
            cap_copy = cap.copy()
            cap_copy['Rally Lead Team'] = rally_team

            # creating a new smartsheet row object
            new_row = {
                'parentId': parent_id,
                'format': ',,1,,,,,,,13',
                'cells': []
            }

            # calling the rows to cells function to create a new smartsheet cell in the proper format
            rtc = rows_to_cells(cap_copy, col_map, parent_level)

            for i in rtc:
                if i['columnId'] in [pcid, rpid, rcid]:
                    continue
                new_row['cells'].append(i)

            new_row['cells'].extend([
                {
                    'columnId': pcid,
                    'formula': '=IF(COUNT(CHILDREN()) > 0, AVG(CHILDREN()), 0)'
                },
                {
                    'columnId': rpid,
                    'formula': '=IF(COUNT(CHILDREN()) > 0, SUM(CHILDREN()), 0)'
                },
                {
                    'columnId': rcid,
                    'formula': '=IF(COUNT(CHILDREN()) > 0, SUM(CHILDREN()), 0)'
                }
            ])
            rows_to_add.append(new_row)

    # Add unmatched capabilities to "Other" section
    if unmatched_capabilities:
        print(f"Adding {len(unmatched_capabilities)} unmatched capabilities to 'Other' section")
        
        # Find "Other" parent row
        other_parent = delivery_team_parents.get('Other')
        
        if other_parent:
            for cap, rally_team in unmatched_capabilities:
                cap_id = cap['ID']
                composite_key = (cap_id, rally_team)
                
                # Skip if already exists
                if composite_key in existing_capability_keys:
                    continue
                
                # Create capability row
                cap_copy = cap.copy()
                cap_copy['Rally Lead Team'] = rally_team
                
                new_row = {
                    'parentId': other_parent['row_id'],
                    'format': ',,1,,,,,,,13',
                    'cells': []
                }
                
                rtc = rows_to_cells(cap_copy, col_map, other_parent['level'])
                
                for i in rtc:
                    if i['columnId'] in [pcid, rpid, rcid]:
                        continue
                    new_row['cells'].append(i)
                
                new_row['cells'].extend([
                    {
                        'columnId': pcid,
                        'formula': '=IF(COUNT(CHILDREN()) > 0, AVG(CHILDREN()), 0)'
                    },
                    {
                        'columnId': rpid,
                        'formula': '=IF(COUNT(CHILDREN()) > 0, SUM(CHILDREN()), 0)'
                    },
                    {
                        'columnId': rcid,
                        'formula': '=IF(COUNT(CHILDREN()) > 0, SUM(CHILDREN()), 0)'
                    }
                ])
                rows_to_add.append(new_row)
        else:
            print("Warning: 'Other' section not found in Application View. Cannot add unmatched capabilities.")

    for i in rows_to_add:
        payload = [i]
        res = requests.post(
            f"{BASE_URL}/sheets/{id}/rows",
            headers=SMARTSHEET_HEADERS,
            json=payload,
            verify=False
        )

def pull_in_features_execution(id, rally_df):
    '''
    Pulling in new features from Rally into the Execution section.
    Matches features to capabilities based on Solution Capability only (ignores rally_lead_team).
    '''

    sheet_response = requests.get(
        f"{BASE_URL}/sheets/{id}",
        headers=SMARTSHEET_HEADERS,
        verify=False
    )

    sheet = sheet_response.json()

    # getting the smartsheet as a df
    smartsheet_df = smartsheet_to_pandas(id)
    
    # getting the smartsheet column names and reference IDs
    col_map = {col['title']: col['id'] for col in sheet.get('columns', [])}

    rows_to_add = []

    # Track existing features in Execution section only (before Application View)
    existing_feature_ids = set()
    application_view_reached = False
    
    for _, row in smartsheet_df.iterrows():
        work_breakdown = str(row.get('Work Breakdown', '')).strip()
        if work_breakdown == 'Application View':
            application_view_reached = True
            break
        
        task_id = str(row.get('Task ID', '')).strip()
        if task_id and task_id.startswith('F'):
            existing_feature_ids.add(task_id)

    # changing the Rally df data types
    rally_df['ID'] = rally_df['ID'].astype(str).str.strip()
    rally_df['Solution Capability'] = rally_df['Solution Capability'].astype(str).str.strip()
    rally_df['Rally Lead Team'] = rally_df['Rally Lead Team'].astype(str).str.strip()
    rally_df['Rally Lead Team'] = rally_df['Rally Lead Team'].replace('None', '')
    rally_df['Preliminary Estimate Value'] = pd.to_numeric(
        rally_df['Preliminary Estimate Value'], errors='coerce'
    ).astype('Int64')
    rally_df['Rally Cost Estimate'] = pd.to_numeric(
        rally_df['Rally Cost Estimate'], errors='coerce'
    ).astype('Int64')

    rally_features = rally_df[rally_df['ID'].str.startswith('F', na=False)]
    
    # Build map of capabilities in Execution section (before Application View)
    capability_to_row_map = {}
    application_view_reached = False
    
    # looping through each row in the sheet
    for row in sheet['rows']:
        task_id = None
        work_breakdown = None
        row_id = row['id']
        row_level = 1
        
        for cell in row.get('cells', []):
            # pulling the work breakdown to detect Application View section
            if cell['columnId'] == col_map['Work Breakdown']:
                work_breakdown = str(cell.get('value', None)).strip() if cell.get('value', None) else None
            # pulling the task id from the updated date
            elif cell['columnId'] == col_map['Task ID']:
                task_id = str(cell.get('value', None)).strip() if cell.get('value', None) else None
            # pulling level from the updated date
            elif cell['columnId'] == col_map['Level']:
                row_level = int(cell.get('value', None)) if cell.get('value', None) is not None else 1
        
        # Stop processing once we reach Application View section
        if work_breakdown == 'Application View':
            application_view_reached = True
            break
        
        # Store capability rows in Execution section (match by capability ID only, ignore rally_lead_team)
        if task_id and task_id.startswith('C') and not application_view_reached:
            if task_id not in capability_to_row_map:
                capability_to_row_map[task_id] = {'row_id': row_id, 'level': row_level}

    # Add features under their parent capabilities
    for _, feat_row in rally_features.iterrows():
        feat_id = feat_row['ID']
        
        # Skip if feature already exists in Execution section
        if feat_id in existing_feature_ids:
            continue

        solution_capability = feat_row['Solution Capability']

        # Find the parent capability (match by capability ID only)
        parent_info = capability_to_row_map.get(solution_capability)

        if not parent_info:
            continue
        
        parent_id = parent_info['row_id']
        parent_level = parent_info['level']

        # creating a new smartsheet row object
        new_row = {
            'parentId': parent_id,
            'format': ',,,,,,,,,13',
            'cells': []
        }

        # calling the rows to cells function to create a new smartsheet cell in the proper format
        new_row['cells'] = rows_to_cells(feat_row, col_map, parent_level)

        rows_to_add.append(new_row)
    
    for i in rows_to_add:
        payload = [i]
        res = requests.post(
            f"{BASE_URL}/sheets/{id}/rows",
            headers=SMARTSHEET_HEADERS,
            json=payload,
            verify=False
        )

def pull_in_features_application_view(id, rally_df):
    '''
    Pulling in new features from Rally into the Application View section.
    Matches features to capabilities based on BOTH Solution Capability AND rally_lead_team.
    '''

    sheet_response = requests.get(
        f"{BASE_URL}/sheets/{id}",
        headers=SMARTSHEET_HEADERS,
        verify=False
    )

    sheet = sheet_response.json()

    # getting the smartsheet as a df
    smartsheet_df = smartsheet_to_pandas(id)
    
    # getting the smartsheet column names and reference IDs
    col_map = {col['title']: col['id'] for col in sheet.get('columns', [])}

    rows_to_add = []

    # Track existing features in Application View section only (between Application View and Financials)
    existing_feature_keys = set()
    application_view_reached = False
    financials_reached = False
    
    for _, row in smartsheet_df.iterrows():
        work_breakdown = str(row.get('Work Breakdown', '')).strip()
        
        if work_breakdown == 'Application View':
            application_view_reached = True
            continue
        
        if work_breakdown == 'Financials':
            financials_reached = True
            break
        
        if application_view_reached and not financials_reached:
            task_id = str(row.get('Task ID', '')).strip()
            rally_lead_team = str(row.get('Rally Lead Team', '')).strip()
            if task_id and task_id.startswith('F'):
                existing_feature_keys.add((task_id, rally_lead_team))

    # changing the Rally df data types
    rally_df['ID'] = rally_df['ID'].astype(str).str.strip()
    rally_df['Solution Capability'] = rally_df['Solution Capability'].astype(str).str.strip()
    rally_df['Rally Lead Team'] = rally_df['Rally Lead Team'].astype(str).str.strip()
    rally_df['Rally Lead Team'] = rally_df['Rally Lead Team'].replace('None', '')
    rally_df['Preliminary Estimate Value'] = pd.to_numeric(
        rally_df['Preliminary Estimate Value'], errors='coerce'
    ).astype('Int64')
    rally_df['Rally Cost Estimate'] = pd.to_numeric(
        rally_df['Rally Cost Estimate'], errors='coerce'
    ).astype('Int64')

    rally_features = rally_df[rally_df['ID'].str.startswith('F', na=False)]
    
    # Build map of capabilities in Application View section (between Application View and Financials)
    capability_to_row_map = {}
    application_view_reached = False
    financials_reached = False
    
    # looping through each row in the sheet
    for row in sheet['rows']:
        task_id = None
        rally_lead_team = None
        work_breakdown = None
        row_id = row['id']
        row_level = 1
        
        for cell in row.get('cells', []):
            # pulling the work breakdown to detect sections
            if cell['columnId'] == col_map['Work Breakdown']:
                work_breakdown = str(cell.get('value', None)).strip() if cell.get('value', None) else None
            # pulling the task id from the updated date
            elif cell['columnId'] == col_map['Task ID']:
                task_id = str(cell.get('value', None)).strip() if cell.get('value', None) else None
            elif cell['columnId'] == col_map['Rally Lead Team']:
                rally_lead_team = str(cell.get('value', None)).strip() if cell.get('value', None) else None
            # pulling level from the updated date
            elif cell['columnId'] == col_map['Level']:
                row_level = int(cell.get('value', None)) if cell.get('value', None) is not None else 1
        
        if work_breakdown == 'Application View':
            application_view_reached = True
            continue
        
        if work_breakdown == 'Financials':
            financials_reached = True
            break
        
        # Store capability rows in Application View section (match by capability ID AND rally_lead_team)
        if task_id and task_id.startswith('C') and application_view_reached and not financials_reached:
            key = (task_id, rally_lead_team if rally_lead_team else '')
            capability_to_row_map[key] = {'row_id': row_id, 'level': row_level}

    # Add features under their parent capabilities
    for _, feat_row in rally_features.iterrows():
        feat_id = feat_row['ID']
        rally_lead_team = feat_row['Rally Lead Team']
        solution_capability = feat_row['Solution Capability']

        composite_key = (feat_id, rally_lead_team if rally_lead_team else '')

        # Skip if feature already exists in Application View section
        if composite_key in existing_feature_keys:
            continue

        # Find the parent capability (match by capability ID AND rally_lead_team)
        parent_info = capability_to_row_map.get((solution_capability, rally_lead_team))

        if not parent_info:
            continue
        
        parent_id = parent_info['row_id']
        parent_level = parent_info['level']

        # creating a new smartsheet row object
        new_row = {
            'parentId': parent_id,
            'format': ',,,,,,,,,13',
            'cells': []
        }

        # calling the rows to cells function to create a new smartsheet cell in the proper format
        new_row['cells'] = rows_to_cells(feat_row, col_map, parent_level)

        rows_to_add.append(new_row)
    
    for i in rows_to_add:
        payload = [i]
        res = requests.post(
            f"{BASE_URL}/sheets/{id}/rows",
            headers=SMARTSHEET_HEADERS,
            json=payload,
            verify=False
        )

def update_existing_tasks(id, rally_df, rally_fields=None, aha_teams=None):
    '''
    Udpating existing capabilities and features in Rally at a cell by cell level.
    '''
     # Default to all fields if none specified
    if rally_fields is None:
        rally_fields = {
            'release': True,
            'end_date': True,
            'status': True,
            'complete': True,
            'point': True,
            'cost': True
        }
    
    # Build fields_to_check based on selected rally_fields
    fields_to_check = []
    if rally_fields.get('release', False):
        fields_to_check.append(('Release', 'Release'))
    if rally_fields.get('end_date', False):
        # Will be dynamically adjusted based on which column exists in the sheet
        fields_to_check.append(('Planned End Date', 'END_DATE_COLUMN'))
    if rally_fields.get('status', False):
        fields_to_check.append(('State', 'Status'))
    if rally_fields.get('complete', False):
        fields_to_check.append(('% Done By Story Plan Estimate', '% Complete'))
    if rally_fields.get('point', False):
        fields_to_check.append(('Preliminary Estimate Value', 'Rally Point Estimate'))
    if rally_fields.get('cost', False):
        fields_to_check.append(('Rally Cost Estimate', 'Rally Cost Estimate'))
    
    # If no fields selected, return early
    if not fields_to_check:
        return
    
    # starting the smartsheet connection
    sheet_response = requests.get(
        f"{BASE_URL}/sheets/{id}",
        headers=SMARTSHEET_HEADERS,
        verify=False
    )

    sheet = sheet_response.json()

    # getting the smartsheet as a df
    smartsheet_df = smartsheet_to_pandas(id)
    
    # Determine which end date column exists in this sheet
    if 'Planned End Date (Rally)' in smartsheet_df.columns:
        end_date_col = 'Planned End Date (Rally)'
    elif 'Actual End Date' in smartsheet_df.columns:
        end_date_col = 'Actual End Date'
    else:
        end_date_col = None
    
    # Replace placeholder with actual column name
    fields_to_check = [
        (rally_field, end_date_col if smartsheet_col == 'END_DATE_COLUMN' and end_date_col else smartsheet_col)
        for rally_field, smartsheet_col in fields_to_check
        if smartsheet_col != 'END_DATE_COLUMN' or end_date_col is not None
    ]

    # getting the smartsheet column names and reference IDs
    col_map = {col['title']: col['id'] for col in sheet.get('columns', [])}

    # converting the task id and id columns to strings and removing nulls
    smartsheet_df['Task ID'] = smartsheet_df['Task ID'].fillna('').astype(str).str.strip()
    rally_df['ID'] = rally_df['ID'].fillna('').astype(str).str.strip()
    rally_df['Planned End Date'] = pd.to_datetime(rally_df['Planned End Date'], errors='coerce').dt.strftime('%Y-%m-%d')

    # Include both Capabilities (C*) and Features (F*) for updates
    rally_updates = {
        str(row['ID']).strip(): row
        for _, row in rally_df.iterrows()
        if str(row['ID']).strip().startswith(('C', 'F'))}

    task_to_row_id = defaultdict(list)
    row_id_to_index = {}  # Map row_id to DataFrame index

    for idx, row in enumerate(sheet['rows']):
        task_id = None
        for cell in row['cells']:
            if cell['columnId'] == col_map['Task ID'] and cell.get('value', None):
                task_id = str(cell.get('value', None)).strip()
        if task_id and (task_id.startswith('C') or task_id.startswith('F')):
            task_to_row_id[task_id].append(row['id'])
            row_id_to_index[row['id']] = idx  # Store the mapping
    
    # fields_to_check = [
    #     ('Release', 'Release'),
    #     ('Planned End Date', 'Actual End Date'),
    #     ('State', 'Status'),
    #     ('% Done By Story Plan Estimate', '% Complete'),
    #     ('Preliminary Estimate Value', 'Rally Point Estimate'),
    #     ('Rally Cost Estimate', 'Rally Cost Estimate')
    # ]

    rows_to_update = []

    # Detect task IDs that exist in Smartsheet but are missing from the Rally pull
    # and mark them as 'Deleted' (highlight the whole row). Do not delete rows.
    missing_task_updates = []
    status_col_id = col_map.get('Status')
    # Cell-level format string to highlight only the Status cell
    status_cell_highlight_format = ',,,,,,,,,19'

    if status_col_id:
        for task_id, row_ids in task_to_row_id.items():
            # If this task id is not present in rally_updates, mark it
            if task_id not in rally_updates:
                for row_id in row_ids:
                    df_idx = row_id_to_index.get(row_id)
                    # Safeguard: ensure we can read the current Status value
                    if df_idx is None or df_idx >= len(smartsheet_df):
                        continue
                    current_status = ''
                    if 'Status' in smartsheet_df.columns:
                        current_status = valid_value(smartsheet_df.iloc[df_idx]['Status'])

                    # Only update if it's not already marked
                    if str(current_status).strip() != 'Deleted':
                        missing_task_updates.append({
                            'id': row_id,
                            'cells': [{
                                'columnId': status_col_id,
                                'value': 'Deleted',
                                'format': status_cell_highlight_format
                            }]
                        })

        if missing_task_updates:
            print(f"Marking {len(missing_task_updates)} Smartsheet row(s) as 'Deleted' (missing in Rally)")
            # Merge these into rows_to_update so they're sent in the same API call
            rows_to_update.extend(missing_task_updates)
    else:
        print("Status column not found in sheet - cannot mark missing Rally items")

    for task_id, row_ids in task_to_row_id.items():
        rally_row = rally_updates.get(task_id, None)
        if rally_row is None or rally_row.empty:
            continue

        for row_id in row_ids:
            updated_cells = []
            
            # Get the DataFrame row index for this specific row_id
            df_idx = row_id_to_index.get(row_id)
            if df_idx is None or df_idx >= len(smartsheet_df):
                continue

            # Check if Work Breakdown name needs updating
            if 'Work Breakdown' in smartsheet_df.columns and 'Name' in rally_row:
                current_work_breakdown = str(smartsheet_df.iloc[df_idx]['Work Breakdown']).strip()
                rally_name = str(rally_row.get('Name', '')).strip()
                expected_work_breakdown = f"{task_id} - {rally_name}"
                
                # If the names differ, update Work Breakdown
                if current_work_breakdown != expected_work_breakdown and rally_name:
                    updated_cells.append({
                        'columnId': col_map['Work Breakdown'],
                        'value': expected_work_breakdown,
                        'format': ',,,,,,,0,,,,'  # No highlighting for name updates
                    })

            # For capabilities (C*), ONLY update Work Breakdown name and add rollup formula for end date
            if task_id.startswith('C'):
                # Check if end date column needs a rollup formula
                if end_date_col and end_date_col in col_map:
                    # Check if this cell already has a formula by looking at the sheet data
                    sheet_row = next((r for r in sheet['rows'] if r['id'] == row_id), None)
                    if sheet_row:
                        end_date_cell = next((c for c in sheet_row.get('cells', []) if c.get('columnId') == col_map[end_date_col]), None)
                        # If the cell doesn't have a formula, add one
                        if end_date_cell and not end_date_cell.get('formula'):
                            updated_cells.append({
                                'columnId': col_map[end_date_col],
                                'formula': '=MAX(CHILDREN())'
                            })
                
                if updated_cells:
                    rows_to_update.append({
                        'id': row_id,
                        'cells': updated_cells
                    })
                continue  # Skip the fields_to_check loop for capabilities

            # For features (F*), continue with normal field updates
            for rally_field, smartsheet_col in fields_to_check:
                # Skip if the column doesn't exist in the smartsheet
                if smartsheet_col not in smartsheet_df.columns:
                    continue
                    
                rally_value = rally_row.get(rally_field, '')

                # Get the value for THIS specific row, not just the first match
                smartsheet_value = valid_value(smartsheet_df.iloc[df_idx][smartsheet_col])
                
                if pd.isna(rally_value) or str(rally_value).strip() == '':
                    if str(smartsheet_value).strip() == '':
                        cell_format = ',,,,,,,0,,,,'
                elif type(rally_value) in (float, int):
                    try:
                        smartsheet_value = float(smartsheet_value)
                        if smartsheet_value == float(rally_value):
                            cell_format = ',,,,,,,0,,,,'
                        else:
                            cell_format = ',,,,,,,,,13'
                    except (ValueError, TypeError):
                        if str(smartsheet_value).strip() == '':
                            cell_format = ',,,,,,,,,13'
                        else:
                            cell_format = ',,,,,,,,,13'
                elif str(rally_value).strip() == str(smartsheet_value).strip():
                        cell_format = ',,,,,,,0,,,,'
                else:
                    cell_format = ',,,,,,,,,13'


                if (
                    (pd.isna(rally_value) and not pd.isna(smartsheet_value)) or
                    (not pd.isna(rally_value) and pd.isna(smartsheet_value)) or
                    (not pd.isna(rally_value) and rally_value != smartsheet_value)
                ):
                    updated_cells.append({
                        'columnId' : col_map[smartsheet_col],
                        'value' : format_smartsheet_value(smartsheet_col, valid_value(rally_value)),
                        'format' : cell_format
                    })
            
            if updated_cells:
                updated_row = {
                    'id': row_id,
                    'cells': []
                }
                for cell in updated_cells:
                    updated_row['cells'].append({
                        'columnId': cell['columnId'],
                        'value': cell.get('value', None),
                        'format': cell['format']
                    })
                rows_to_update.append(updated_row)

    if rows_to_update:
        payload = rows_to_update
        res = requests.put(
            f"{BASE_URL}/sheets/{id}/rows",
            headers=SMARTSHEET_HEADERS,
            json=payload,
            verify=False
        )
    
    # Add date rollup formulas to milestone rows if they don't already exist
    milestone_rows = ['Quote Ready', 'Billing Ready', 'Consumer Services / Portal Ready', 'Reporting Ready', 'Development', 'Case Install Ready', 'Functional Capabilities (do not delete)', 'Planning', 'Claims Ready', 'Finance Ready', 'Renewal Ready', 'GNG Checkpoint', 'GNG Final Go Live', 'PET Testing', 'Operations Ready', 'Enrollment Ready', 'Go To Production Plan', 'Other', 'Core team assigned - RDL, BDL', 'Renewals Impacts confirmed', 'PRJs set up (Tech & Business)', 'Solution Completed', 'Execution']
    
    # Add AHA delivery team app names from Application View to milestone_rows
    if aha_teams:
        milestone_rows.extend(aha_teams)
        print(f"Including {len(aha_teams)} app rows for date rollup formulas: {aha_teams}")
    
    milestone_updates = []
    
    if end_date_col and end_date_col in col_map:
        for row in sheet['rows']:
            work_breakdown = None
            row_id = row['id']
            
            # Get Work Breakdown value
            for cell in row.get('cells', []):
                if cell['columnId'] == col_map['Work Breakdown']:
                    work_breakdown = str(cell.get('value', '')).strip() if cell.get('value', '') else ''
                    break
            
            # Check if this is a milestone row
            if work_breakdown in milestone_rows:
                # Check if end date cell already has a formula
                end_date_cell = next((c for c in row.get('cells', []) if c.get('columnId') == col_map[end_date_col]), None)
                
                # If the cell doesn't have a formula, add one
                if end_date_cell and not end_date_cell.get('formula'):
                    milestone_updates.append({
                        'id': row_id,
                        'cells': [{
                            'columnId': col_map[end_date_col],
                            'formula': '=MAX(CHILDREN())'
                        }]
                    })
    
    if milestone_updates:
        print(f"Adding date rollup formulas to {len(milestone_updates)} milestone rows...")
        res = requests.put(
            f"{BASE_URL}/sheets/{id}/rows",
            headers=SMARTSHEET_HEADERS,
            json=milestone_updates,
            verify=False
        )
        if res.status_code == 200:
            print(f"✓ Successfully added date rollup formulas to milestone rows")
        else:
            print(f"✗ Failed to add date rollup formulas: {res.status_code}")

def update_ppmo(id, optics_df):
    debug_logs = []  # Collect all debug output
    
    def log(msg):
        """Helper to both print and collect logs"""
        print(msg)
        debug_logs.append(msg)
    
    sheet_response = requests.get(
        f"{BASE_URL}/sheets/{id}",
        headers=SMARTSHEET_HEADERS,
        verify=False
    )

    sheet = sheet_response.json()
    
    # Check if the API call was successful
    if 'errorCode' in sheet:
        error_msg = f"Smartsheet API Error: {sheet.get('errorCode')} - {sheet.get('message', 'Unknown error')}"
        log(error_msg)
        raise ValueError(error_msg)
    
    if 'rows' not in sheet:
        log(f"ERROR: Smartsheet response missing 'rows' key")
        log(f"Response status: {sheet_response.status_code}")
        log(f"Response keys: {list(sheet.keys())}")
        log(f"Full response preview: {str(sheet)[:500]}")
        raise KeyError("Smartsheet response does not contain 'rows' - check API permissions and sheet ID")

    # getting the smartsheet as a df
    smartsheet_df = smartsheet_to_pandas(id)

    row_id = []
    for row in sheet['rows']:
        row_id.append(row['id'])

    smartsheet_df['row_id'] = row_id

    # Rename task_name_mapped to Work Breakdown for matching
    optics_df['Work Breakdown'] = optics_df['Task Name']

    log(f"\n[DEBUG PPMO] ==== OPTICS DATA ====")
    log(f"Optics dataframe:\n{optics_df[['Work Breakdown', 'Actuals', 'ETCs', 'EACs', '% Burn']].to_string()}")

    # Find the columns where the 'Task Name' header row contains 'Actuals', 'ETCs', 'EACs', '% Burn'
    # This identifies which columns have the optics financial data (not looking at actual column names)
    ppmo_columns = {}  # Will store {field_name: (column_name, column_id)} mapping
    
    # Look for the row where Work Breakdown is 'Task Name' (this is the header row)
    task_name_header_rows = smartsheet_df[smartsheet_df['Work Breakdown'] == 'Task Name']
    
    log(f"\n[DEBUG PPMO] ==== FINDING OPTICS COLUMNS ====")
    log(f"Found {len(task_name_header_rows)} 'Task Name' header rows")
    
    # Debug: Print all column information
    log(f"\n[DEBUG PPMO] Sheet columns:")
    for idx, col in enumerate(sheet['columns']):
        log(f"  Column {idx}: title='{col.get('title')}', id={col.get('id')}, type={col.get('type')}, primary={col.get('primary', False)}")
    
    # Check if 'Task Name' header row doesn't exist - need to create the optics section
    if task_name_header_rows.empty:
        print("'Task Name' header row not found - checking if Financials section exists...")
        financials_rows = smartsheet_df[smartsheet_df['Work Breakdown'] == 'Financials']
        
        if not financials_rows.empty:
            print("Found 'Financials' row - will create 'Task Name' header with optics columns")
            
            # Find the Work Breakdown column ID and other column IDs we need
            work_breakdown_col_id = sheet['columns'][0]['id']
            level_col_id = None
            
            # Find available columns to use for Actuals, ETCs, EACs, % Burn
            # We'll use the first 4 available columns after Work Breakdown
            available_columns = []
            for col in sheet['columns'][1:]:  # Skip Work Breakdown column
                if col['title'] not in ['Work Breakdown', 'Level']:
                    available_columns.append(col)
                if col['title'] == 'Level':
                    level_col_id = col['id']
            
            if len(available_columns) >= 4:
                # Create the 'Task Name' header row
                task_name_row_cells = [
                    {'columnId': work_breakdown_col_id, 'value': 'Task Name'},
                    {'columnId': available_columns[0]['id'], 'value': 'Actuals'},
                    {'columnId': available_columns[1]['id'], 'value': 'ETCs'},
                    {'columnId': available_columns[2]['id'], 'value': 'EACs'},
                    {'columnId': available_columns[3]['id'], 'value': '% Burn'}
                ]
                
                if level_col_id:
                    task_name_row_cells.append({'columnId': level_col_id, 'value': 3})
                
                # Add the header row to Smartsheet
                print("Creating 'Task Name' header row...")
                res = requests.post(
                    f"{BASE_URL}/sheets/{id}/rows",
                    headers=SMARTSHEET_HEADERS,
                    json=[{'toBottom': True, 'cells': task_name_row_cells}],
                    verify=False
                )
                
                if res.status_code == 200:
                    print("✓ Successfully created 'Task Name' header row")
                    
                    # Now set up ppmo_columns mapping for the newly created structure
                    ppmo_columns = {
                        'Actuals': {'column_name': available_columns[0]['title'], 'column_id': available_columns[0]['id']},
                        'ETCs': {'column_name': available_columns[1]['title'], 'column_id': available_columns[1]['id']},
                        'EACs': {'column_name': available_columns[2]['title'], 'column_id': available_columns[2]['id']},
                        '% Burn': {'column_name': available_columns[3]['title'], 'column_id': available_columns[3]['id']}
                    }
                    print(f"Set up ppmo_columns: {list(ppmo_columns.keys())}")
                else:
                    print(f"✗ Failed to create 'Task Name' header row: {res.status_code} - {res.text}")
                    return
            else:
                print(f"ERROR: Not enough columns available to create optics section (need 4, found {len(available_columns)})")
                return
        else:
            print("ERROR: Neither 'Task Name' nor 'Financials' row found - cannot determine where to add optics data")
            return
    else:
        # Task Name header exists - find the columns as before
        header_row = task_name_header_rows.iloc[0]
        log(f"\n[DEBUG PPMO] Task Name header row contents:")
        for col_name in smartsheet_df.columns:
            if col_name not in ['row_id']:
                log(f"  Column '{col_name}': value='{header_row[col_name]}'")
        
        log(f"\n[DEBUG PPMO] Checking header row columns for 'Actuals', 'ETCs', 'EACs', '% Burn'...")
        
        # Map the expected values to their column names and IDs
        # IMPORTANT: We need to verify the columns can actually accept numeric data
        for col_idx, col_name in enumerate(smartsheet_df.columns):
            if col_name not in ['Work Breakdown', 'row_id']:
                col_value = str(header_row[col_name]).strip()
                if col_value in ['Actuals', 'ETCs', 'EACs', '% Burn']:
                    # Get the actual Smartsheet column ID and type
                    actual_col_idx = list(smartsheet_df.columns).index(col_name)
                    column_info = sheet['columns'][actual_col_idx]
                    column_id = column_info['id']
                    column_type = column_info.get('type', 'UNKNOWN')
                    
                    # Check if this column type can accept numeric data
                    numeric_compatible_types = ['TEXT_NUMBER', 'CURRENCY', 'PERCENT', 'NUMBER']
                    if column_type not in numeric_compatible_types:
                        log(f"WARNING: Column '{col_name}' (type: {column_type}) for '{col_value}' cannot accept numeric data!")
                        log(f"  Skipping this mapping. Need to find or create proper numeric columns.")
                        continue
                    
                    ppmo_columns[col_value] = {
                        'column_name': col_name,
                        'column_id': column_id
                    }
                    log(f"Found '{col_value}' at position {actual_col_idx} (column name: {col_name}, ID: {column_id}, type: {column_type})")
    
        if len(ppmo_columns) < 4:
            log(f"ERROR: Could not find all 4 required numeric columns. Only found: {list(ppmo_columns.keys())}")
            log(f"The 'Task Name' header row is using columns with incompatible types (CONTACT_LIST, PICKLIST, etc.)")
            log(f"Solution: Need to create dedicated TEXT_NUMBER columns for Optics financial data or reassign labels to existing numeric columns.")
            return
    
        if not ppmo_columns:
            log("ERROR: Could not find PPMO columns with 'Actuals', 'ETCs', 'EACs', '% Burn' in Task Name header row")
            log(f"Header row values: {task_name_header_rows.iloc[0].to_dict() if not task_name_header_rows.empty else 'No header row found'}")
            return
    
    log(f"\nFound {len(ppmo_columns)} valid PPMO columns: {list(ppmo_columns.keys())}")

    log(f"\n[DEBUG PPMO] ==== MATCHING ROWS ====")
    log(f"Looking for matches between Optics and Smartsheet...")
    log(f"Optics tasks: {optics_df['Work Breakdown'].tolist()}")
    log(f"ppmo_columns mapping: {ppmo_columns}")
    
    rows_to_update = []

    # Iterate through each optics task
    for _, optics_row in optics_df.iterrows():
        task_name = optics_row['Work Breakdown']
        
        # Find matching rows in Smartsheet by Work Breakdown
        matching_rows = smartsheet_df[smartsheet_df['Work Breakdown'] == task_name]
        
        if matching_rows.empty:
            print(f"No match found for: '{task_name}'")
            continue
        
        print(f"\nProcessing task: '{task_name}'")
            
        for idx, ss_row in matching_rows.iterrows():
            changed_cells = []

            # Update Actuals, ETCs, EACs
            for field in ['Actuals', 'ETCs', 'EACs']:
                if field not in ppmo_columns:
                    print(f"  {field} not in ppmo_columns, skipping")
                    continue
                    
                col_name = ppmo_columns[field]['column_name']
                col_id = ppmo_columns[field]['column_id']
                
                # Get new value from optics
                new_value = optics_row[field]
                
                # Get old value from smartsheet - use the actual smartsheet_df with index
                old_value_raw = smartsheet_df.loc[idx, col_name]
                
                print(f"  {field}: col_name='{col_name}', new={new_value}, old_raw={old_value_raw}")
                
                # Convert both to numeric for comparison
                new_value_numeric = pd.to_numeric(
                    str(new_value).replace('$', '').replace(',', '').strip() if pd.notna(new_value) else '',
                    errors='coerce'
                )
                old_value_numeric = pd.to_numeric(
                    str(old_value_raw).replace('$', '').replace(',', '').strip() if pd.notna(old_value_raw) else '',
                    errors='coerce'
                )
                
                # Round both values to nearest whole number for comparison
                new_value_rounded = round(new_value_numeric) if pd.notna(new_value_numeric) else None
                old_value_rounded = round(old_value_numeric) if pd.notna(old_value_numeric) else None
                
                print(f"  {field}: new_rounded={new_value_rounded}, old_rounded={old_value_rounded}")
                
                # Only update if rounded values are different
                if new_value_rounded is not None and (old_value_rounded is None or new_value_rounded != old_value_rounded):
                    print(f"  ✓ UPDATE: '{task_name}' {field} - ${old_value_rounded:,} -> ${new_value_rounded:,}")
                    changed_cells.append({
                        'columnId': col_id,
                        'value': int(new_value_rounded),  # Send as integer value
                        'format': ',,,,,,,,,,,,,1,2'
                    })
                else:
                    print(f"  No change for {field}")
            
            # Update % Burn
            if '% Burn' in ppmo_columns:
                col_name = ppmo_columns['% Burn']['column_name']
                col_id = ppmo_columns['% Burn']['column_id']
                
                # Get new value from optics (comes as whole number like 96 for 96%)
                new_burn = optics_row['% Burn']
                
                # Get old value from smartsheet (stored as decimal like 0.96 for 96%)
                old_burn_raw = smartsheet_df.loc[idx, col_name]
                
                print(f"  % Burn: col_name='{col_name}', new={new_burn}, old_raw={old_burn_raw}")
                
                # Convert new value to numeric (it's already a whole number like 96)
                new_burn_numeric = pd.to_numeric(new_burn, errors='coerce')
                
                # Convert old value: if it's a decimal (0.96), multiply by 100 to get percentage
                old_burn_numeric = pd.to_numeric(old_burn_raw, errors='coerce')
                if pd.notna(old_burn_numeric):
                    # If the value is between 0 and 1, it's stored as decimal - convert to percentage
                    if 0 <= old_burn_numeric <= 1:
                        old_burn_numeric = old_burn_numeric * 100
                
                # Round both values to nearest whole number for comparison
                new_burn_rounded = round(new_burn_numeric) if pd.notna(new_burn_numeric) else None
                old_burn_rounded = round(old_burn_numeric) if pd.notna(old_burn_numeric) else None
                
                print(f"  % Burn: new_rounded={new_burn_rounded}, old_rounded={old_burn_rounded}")
                
                # Only update if rounded values are different
                if new_burn_rounded is not None and (old_burn_rounded is None or new_burn_rounded != old_burn_rounded):
                    print(f"  ✓ UPDATE: '{task_name}' % Burn - {old_burn_rounded}% -> {new_burn_rounded}%")
                    # Convert to decimal for Smartsheet (e.g., 96 -> 0.96)
                    changed_cells.append({
                        'columnId': col_id,
                        'value': float(new_burn_rounded) / 100,
                        'format': ',,,,,,,,,,,,,,3'  # Percentage format with 0 decimal places
                    })
                else:
                    print(f"  No change for % Burn")
        
            if changed_cells:
                print(f"  Adding {len(changed_cells)} cell(s) to update for row_id={ss_row['row_id']}")
                rows_to_update.append({
                    'id': int(ss_row['row_id']),
                    'cells': changed_cells
                })
            else:
                print(f"  No changes needed for this row")
    
    # Add new tasks that don't exist in Smartsheet
    print(f"\n[DEBUG PPMO] ==== ADDING NEW TASKS ====")
    existing_tasks = set(smartsheet_df['Work Breakdown'].dropna().unique())
    new_tasks = optics_df[~optics_df['Work Breakdown'].isin(existing_tasks)]
    new_tasks_were_added = False
    
    if not new_tasks.empty:
        print(f"Found {len(new_tasks)} new tasks to add")
        
        # Find the 'Task Name' header row to get its row_id (we'll insert as siblings after it)
        task_name_header_rows = smartsheet_df[smartsheet_df['Work Breakdown'] == 'Task Name']
        
        if not task_name_header_rows.empty:
            # Get the Task Name header row ID to use as parent
            task_name_row_id = int(task_name_header_rows.iloc[0]['row_id'])
            
            # We need to insert new rows as children of the Task Name section
            # New rows should be at Level 4
            for _, new_task_row in new_tasks.iterrows():
                task_name = new_task_row['Work Breakdown']
                actuals = new_task_row['Actuals']
                etcs = new_task_row['ETCs']
                eacs = new_task_row['EACs']
                burn = new_task_row['% Burn']
                
                # Create cells for the new row
                new_row_cells = [
                    {
                        'columnId': sheet['columns'][0]['id'],  # Work Breakdown column
                        'value': task_name
                    },
                    {
                        'columnId': ppmo_columns['Actuals']['column_id'],
                        'value': int(round(actuals)) if pd.notna(actuals) else 0,
                        'format': ',,,,,,,,,,,,,1,2'
                    },
                    {
                        'columnId': ppmo_columns['ETCs']['column_id'],
                        'value': int(round(etcs)) if pd.notna(etcs) else 0,
                        'format': ',,,,,,,,,,,,,1,2'
                    },
                    {
                        'columnId': ppmo_columns['EACs']['column_id'],
                        'value': int(round(eacs)) if pd.notna(eacs) else 0,
                        'format': ',,,,,,,,,,,,,1,2'
                    },
                    {
                        'columnId': ppmo_columns['% Burn']['column_id'],
                        'value': float(round(burn)) / 100 if pd.notna(burn) else 0,
                        'format': ',,,,,,,,,,,,,,3'  # Percentage format with 0 decimal places
                    }
                ]
                
                # Find Level column ID
                level_col_id = None
                for col in sheet['columns']:
                    if col['title'] == 'Level':
                        level_col_id = col['id']
                        break
                
                if level_col_id:
                    new_row_cells.append({
                        'columnId': level_col_id,
                        'value': 4  # New tasks should be Level 4
                    })
                
                # Add the new row as a child of Task Name row
                print(f"Adding new task: '{task_name}' with Actuals=${int(round(actuals)):,}, ETCs=${int(round(etcs)):,}, EACs=${int(round(eacs)):,}, Burn={int(round(burn))}%")
                
                new_row_payload = {
                    'parentId': task_name_row_id,  # Add as child of Task Name row
                    'toBottom': True,  # Add to bottom of parent's children
                    'cells': new_row_cells,
                    'format': ',,,,,,,,,5'  # Light yellow background
                }
                
                # POST new row to Smartsheet
                res = requests.post(
                    f"{BASE_URL}/sheets/{id}/rows",
                    headers=SMARTSHEET_HEADERS,
                    json=[new_row_payload],
                    verify=False
                )
                
                if res.status_code == 200:
                    print(f"✓ Successfully added new task: '{task_name}'")
                    new_tasks_were_added = True
                else:
                    print(f"✗ Failed to add new task '{task_name}': {res.status_code} - {res.text}")
        else:
            print("Warning: 'Task Name' header row not found, cannot add new tasks")
    else:
        print("No new tasks to add - all Optics tasks already exist in Smartsheet")
    
    # Update the "Optics Total" row if it exists
    print(f"\n[DEBUG PPMO] ==== OPTICS TOTAL ROW ====")
    optics_total_rows = smartsheet_df[smartsheet_df['Work Breakdown'] == 'Optics Total']
    
    if not optics_total_rows.empty:
        # Calculate totals from optics_df
        total_actuals = optics_df['Actuals'].sum(skipna=True)
        total_etcs = optics_df['ETCs'].sum(skipna=True)
        total_eacs = optics_df['EACs'].sum(skipna=True)
        total_burn = (total_actuals / total_eacs * 100) if total_eacs != 0 else 0
        
        optics_total_row = optics_total_rows.iloc[0]
        
        # Round totals for comparison
        new_actuals_rounded = round(total_actuals) if pd.notna(total_actuals) else None
        new_etcs_rounded = round(total_etcs) if pd.notna(total_etcs) else None
        new_eacs_rounded = round(total_eacs) if pd.notna(total_eacs) else None
        new_burn_rounded = round(total_burn) if pd.notna(total_burn) else None
        
        # Get old values from smartsheet
        old_actuals_raw = optics_total_row[ppmo_columns['Actuals']['column_name']] if 'Actuals' in ppmo_columns else None
        old_etcs_raw = optics_total_row[ppmo_columns['ETCs']['column_name']] if 'ETCs' in ppmo_columns else None
        old_eacs_raw = optics_total_row[ppmo_columns['EACs']['column_name']] if 'EACs' in ppmo_columns else None
        old_burn_raw = optics_total_row[ppmo_columns['% Burn']['column_name']] if '% Burn' in ppmo_columns else None
        
        # Convert old values to numeric
        old_actuals = pd.to_numeric(str(old_actuals_raw).replace('$', '').replace(',', '').strip() if pd.notna(old_actuals_raw) else '', errors='coerce')
        old_etcs = pd.to_numeric(str(old_etcs_raw).replace('$', '').replace(',', '').strip() if pd.notna(old_etcs_raw) else '', errors='coerce')
        old_eacs = pd.to_numeric(str(old_eacs_raw).replace('$', '').replace(',', '').strip() if pd.notna(old_eacs_raw) else '', errors='coerce')
        old_burn = pd.to_numeric(old_burn_raw, errors='coerce')
        
        # Convert burn from decimal to percentage if needed
        if pd.notna(old_burn) and 0 <= old_burn <= 1:
            old_burn = old_burn * 100
        
        # Round old values
        old_actuals_rounded = round(old_actuals) if pd.notna(old_actuals) else None
        old_etcs_rounded = round(old_etcs) if pd.notna(old_etcs) else None
        old_eacs_rounded = round(old_eacs) if pd.notna(old_eacs) else None
        old_burn_rounded = round(old_burn) if pd.notna(old_burn) else None
        
        # Check if any value has changed
        needs_update = (
            (new_actuals_rounded != old_actuals_rounded) or
            (new_etcs_rounded != old_etcs_rounded) or
            (new_eacs_rounded != old_eacs_rounded) or
            (new_burn_rounded != old_burn_rounded)
        )
        
        if needs_update:
            old_actuals_str = f"${old_actuals_rounded:,}" if old_actuals_rounded is not None else "None"
            new_actuals_str = f"${new_actuals_rounded:,}" if new_actuals_rounded is not None else "None"
            old_etcs_str = f"${old_etcs_rounded:,}" if old_etcs_rounded is not None else "None"
            new_etcs_str = f"${new_etcs_rounded:,}" if new_etcs_rounded is not None else "None"
            old_eacs_str = f"${old_eacs_rounded:,}" if old_eacs_rounded is not None else "None"
            new_eacs_str = f"${new_eacs_rounded:,}" if new_eacs_rounded is not None else "None"
            old_burn_str = f"{old_burn_rounded}%" if old_burn_rounded is not None else "None"
            new_burn_str = f"{new_burn_rounded}%" if new_burn_rounded is not None else "None"
            
            print(f"UPDATE: Optics Total - Actuals: {old_actuals_str} -> {new_actuals_str}")
            print(f"UPDATE: Optics Total - ETCs: {old_etcs_str} -> {new_etcs_str}")
            print(f"UPDATE: Optics Total - EACs: {old_eacs_str} -> {new_eacs_str}")
            print(f"UPDATE: Optics Total - % Burn: {old_burn_str} -> {new_burn_str}")
            
            total_changed_cells = [
                {
                    'columnId': ppmo_columns['Actuals']['column_id'],
                    'value': int(new_actuals_rounded),
                    'format': ',,,,,,,,,,,,,1,2'
                },
                {
                    'columnId': ppmo_columns['ETCs']['column_id'],
                    'value': int(new_etcs_rounded),
                    'format': ',,,,,,,,,,,,,1,2'
                },
                {
                    'columnId': ppmo_columns['EACs']['column_id'],
                    'value': int(new_eacs_rounded),
                    'format': ',,,,,,,,,,,,,1,2'
                },
                {
                    'columnId': ppmo_columns['% Burn']['column_id'],
                    'value': float(new_burn_rounded) / 100,
                    'format': ',,,,,,,,,,,,,,3'
                }
            ]
            
            rows_to_update.append({
                'id': int(optics_total_row['row_id']),
                'cells': total_changed_cells
            })
        else:
            actuals_str = f"${old_actuals_rounded:,}" if old_actuals_rounded is not None else "None"
            etcs_str = f"${old_etcs_rounded:,}" if old_etcs_rounded is not None else "None"
            eacs_str = f"${old_eacs_rounded:,}" if old_eacs_rounded is not None else "None"
            burn_str = f"{old_burn_rounded}%" if old_burn_rounded is not None else "None"
            print(f"No change: Optics Total - Actuals: {actuals_str}, ETCs: {etcs_str}, EACs: {eacs_str}, Burn: {burn_str}")

    # Send updates to Smartsheet
    print(f"\n[DEBUG PPMO] ==== SENDING UPDATES ====")
    if rows_to_update:
        print(f"Sending {len(rows_to_update)} row updates to Smartsheet...")
        payload = rows_to_update
        res = requests.put(
            f"{BASE_URL}/sheets/{id}/rows",
            headers=SMARTSHEET_HEADERS,
            json=payload,
            verify=False
        )
        print(f"[DEBUG PPMO] Smartsheet API response: {res.status_code}")
        if res.status_code != 200:
            print(f"[DEBUG PPMO] Response body: {res.text}")
    else:
        print("[DEBUG PPMO] No rows to update for Optics data")   

def update(st, prj=None, update_options=None):
    '''
    Comprehensive update of Rally using the above functions.
    The 'st' parameter can be either a strategic theme OR an AHA idea.
    '''
    # Default to all updates if no options provided
    if update_options is None:
        update_options = {
            "aha": True,
            "optics": True,
            "rally_fields": {
                "release": True,
                "end_date": True,
                "status": True,
                "complete": True,
                "point": True,
                "cost": True
            }
        }
    # OLD: Read from JSON file (active)
    # with open('documents/plan_metadata.json', 'r') as file:
    #     data = json.load(file)
    
    # id = data[st]['sheet id']
    # prj = data[st]['prj']
    
    # NEW: Get metadata from MongoDB - search by theme or idea
    mongo_helper = MongoDBHelper()
    data, actual_key = mongo_helper.get_plan_metadata_by_key(st)
    
    if not data:
        mongo_helper.close()
        raise ValueError(f"No plan found with strategic theme or idea: {st}")
    
    id = data['sheet id']
    prj = data['prj']
    idea = data['idea']
    current_theme = data.get('rally_theme', 'No ST')
    
    # Fetch fresh AHA data once for metadata validation (SINGLE API CALL)
    print(f"Fetching latest AHA data for metadata validation...")
    aha_df, os_approved, new_theme, tag, new_prj, go_live = get_aha_data(idea)
    
    # Extract AHA delivery team names for Application View verification
    aha_teams = []
    if not aha_df.empty and 'Impacts Delivery team' in aha_df.columns:
        aha_teams = aha_df['Impacts Delivery team'].dropna().unique().tolist()
        print(f"AHA delivery teams found: {aha_teams}")
    
    metadata_updates = {}

    # Check if this plan was created without a theme (using idea as key)
    # and if a theme has now been discovered in AHA
    if current_theme == 'No ST' and actual_key == idea:
        print(f"Plan was created without theme. Checking if theme now exists in AHA...")
        
        if new_theme != 'No ST' and new_theme.startswith('ST'):
            print(f"Strategic theme discovered: {new_theme}. Migrating MongoDB key from {actual_key} to {new_theme}")
            # Migrate the MongoDB document from idea key to theme key
            mongo_helper.migrate_plan_key(actual_key, new_theme)
            actual_key = new_theme  # Update the key we're working with
            current_theme = new_theme
    elif new_theme != current_theme and new_theme != 'No ST':
        # Theme has changed in AHA
        metadata_updates['rally_theme'] = new_theme
        print(f"Theme updated in AHA: {current_theme} -> {new_theme}")
        current_theme = new_theme
    
    # Check for other missing or changed metadata
    if tag and tag != data.get('tag', ''):
        metadata_updates['tag'] = tag
        print(f"Updating tag: {data.get('tag', '')} -> {tag}")
    
    # Use new_prj from the single AHA call instead of making another call
    if new_prj and (new_prj != prj or prj == 'dne'):
        metadata_updates['prj'] = new_prj
        print(f"Updating prj: {prj} -> {new_prj}")
        prj = new_prj
    
    if os_approved and float(os_approved) != float(data.get('os_approved', 0)):
        metadata_updates['os_approved'] = float(os_approved)
        print(f"Updating os_approved: {data.get('os_approved', 0)} -> {os_approved}")
    
    if go_live and go_live != data.get('go_live', ''):
        metadata_updates['go_live'] = go_live
        print(f"Updating go_live: {data.get('go_live', '')} -> {go_live}")
    
    # Apply all metadata updates in a single MongoDB operation
    if metadata_updates:
        mongo_helper.update_plan_metadata(actual_key, metadata_updates)
        print(f"Updated {len(metadata_updates)} metadata field(s) in MongoDB")
    
    # Only fetch Rally data if we have a real strategic theme
    if current_theme != 'No ST' and current_theme.startswith('ST'):
        ltm = get_lead_team_mapping()
        rally_df = get_rally_data_hcp(current_theme, ltm)
        
        pull_in_capabilities_execution(id, rally_df)
        pull_in_capabilities_application_view(id, rally_df, aha_teams)  # Pass AHA teams
        pull_in_features_execution(id, rally_df)
        pull_in_features_application_view(id, rally_df)

        rally_fields = update_options.get("rally_fields", {})
        if any(rally_fields.values()):
            update_existing_tasks(id, rally_df, rally_fields, aha_teams)
    else:
        print(f"No strategic theme available (theme={current_theme}). Skipping Rally data updates.")
    
    mongo_helper.close() 

    if update_options.get("aha", True):
        update_from_aha(actual_key)  # Use actual_key instead of st

    if update_options.get("optics", True):
        try:
            # Only fetch optics data if we have a real strategic theme and valid PRJ format
            import re
            prj_valid = prj and re.match(r'^PRJ\d+$', prj.strip(), re.IGNORECASE)
            
            if current_theme != 'No ST' and current_theme.startswith('ST') and prj_valid:
                optics_df = get_optics_financials(prj, current_theme)
                update_ppmo(id, optics_df)
            else:
                if not prj_valid:
                    print(f"Skipping Optics data updates - Invalid or missing PRJ format (PRJ={prj})")
                else:
                    print(f"No strategic theme available. Skipping Optics data updates.")
        except Exception as e:
            print(f"Error updating PPMO data: {e}")