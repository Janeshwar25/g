"""
Test script for testing update_from_aha with direct sheet ID
This bypasses MongoDB and directly tests the Aha update logic
"""

import sys
import pandas as pd
import requests
from config import Config
from engine.mapping import get_aha_data

# Load configuration
config = Config()
BASE_URL = config.SMARTSHEET_BASE_URL
SMARTSHEET_HEADERS = config.get_smartsheet_headers()

def smartsheet_to_pandas(id):
    '''
    Returning the smartsheet as a dataframe using the sheet id.
    '''
    sheet_response = requests.get(
        f"{BASE_URL}/sheets/{id}",
        headers=SMARTSHEET_HEADERS,
        verify=False
    )
    sheet = sheet_response.json()
    
    # getting the column names
    columns = [col['title'] for col in sheet.get('columns', [])]

    # saving each row of data from the smartsheet
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

def update_from_aha_direct(sheet_id, aha_idea):
    """
    Test the update_from_aha logic with direct sheet ID
    This mimics the actual function but without MongoDB dependency
    """
    
    print("=" * 80)
    print("Testing update_from_aha with Direct Sheet ID")
    print("=" * 80)
    print(f"Sheet ID: {sheet_id}")
    print(f"AHA Idea: {aha_idea}")
    print("=" * 80)
    
    # Fetch the sheet
    sheet_response = requests.get(
        f"{BASE_URL}/sheets/{sheet_id}",
        headers=SMARTSHEET_HEADERS,
        verify=False
    )
    sheet = sheet_response.json()
    
    if 'errorCode' in sheet:
        print(f"ERROR: Failed to fetch sheet: {sheet.get('message')}")
        return
    
    # Get smartsheet as dataframe
    smartsheet_df = smartsheet_to_pandas(sheet_id)
    
    # Get Aha data
    print("\nFetching Aha data...")
    aha_df, os_approved, theme, tag, prj, go_live = get_aha_data(aha_idea)
    
    # Prepare Aha data
    aha_df = aha_df[['Impacts Delivery team', 'Impact Cost']].rename(columns={
        'Impacts Delivery team': 'Impacted Applications',
        'Impact Cost': 'Aha OS Approved Amount'
    })
    
    # Convert to numeric
    aha_df['Aha OS Approved Amount'] = pd.to_numeric(
        aha_df['Aha OS Approved Amount'].astype(str).str.replace('$', '').str.replace(',', '').str.strip(), 
        errors='coerce'
    )
    
    print(f"\n[DEBUG] ==== AHA DATA ====")
    print(f"Aha DataFrame:\n{aha_df[['Impacted Applications', 'Aha OS Approved Amount']]}")
    print(f"Total Aha impacts: {len(aha_df)}")
    
    # Add row IDs
    row_id = []
    for row in sheet['rows']:
        row_id.append(row['id'])
    smartsheet_df['row_id'] = row_id
    
    # Find the Aha column
    impacted_apps_rows = smartsheet_df[smartsheet_df['Work Breakdown'] == 'Impacted Applications']
    
    print(f"\n[DEBUG] ==== FINDING AHA COLUMN ====")
    print(f"Found {len(impacted_apps_rows)} 'Impacted Applications' header rows")
    
    if impacted_apps_rows.empty:
        print("ERROR: 'Impacted Applications' header row not found")
        return
    
    aha_column_id = None
    aha_amount_col_name = None
    header_row = impacted_apps_rows.iloc[0]
    
    for col_idx, col_name in enumerate(smartsheet_df.columns):
        if col_name not in ['Work Breakdown', 'row_id']:
            col_value = str(header_row[col_name]).strip()
            if col_value == 'Aha OS Approved Amount':
                actual_col_idx = list(smartsheet_df.columns).index(col_name)
                column_info = sheet['columns'][actual_col_idx]
                column_type = column_info.get('type', 'UNKNOWN')
                
                numeric_compatible_types = ['TEXT_NUMBER', 'CURRENCY', 'PERCENT', 'NUMBER']
                if column_type not in numeric_compatible_types:
                    print(f"WARNING: Column '{col_name}' (type: {column_type}) cannot accept numeric data!")
                    continue
                
                aha_amount_col_name = col_name
                aha_column_id = column_info['id']
                print(f"Found 'Aha OS Approved Amt' at column position {actual_col_idx} (column name: {col_name}, type: {column_type})")
                print(f"Column ID: {aha_column_id}")
                break
    
    if not aha_amount_col_name or not aha_column_id:
        print("ERROR: Could not find column with 'Aha OS Approved Amt'")
        return
    
    print(f"\n[DEBUG] ==== MATCHING ROWS ====")
    print(f"Looking for matches between Aha and Smartsheet...")
    
    # First, identify existing impacts in the "Impacted Applications" section
    # Important: Only look AFTER "Financials" row to avoid matching impacts from Development section
    past_financials = False
    found_impacted_apps = False
    existing_impacts_in_section = set()
    
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
    
    print(f"Found {len(existing_impacts_in_section)} existing impacts in Impacted Applications section:")
    for imp in sorted(existing_impacts_in_section):
        print(f"  - {imp}")
    
    rows_to_update = []
    new_impacts = []
    
    # Iterate through each Aha impacted application
    for _, aha_row in aha_df.iterrows():
        impacted_app = aha_row['Impacted Applications']
        aha_amount = aha_row['Aha OS Approved Amount']
        
        # Check if this impact exists in the Impacted Applications section
        if impacted_app not in existing_impacts_in_section:
            print(f"No match found for: '{impacted_app}' - will add as new row")
            new_impacts.append(aha_row)
            continue
        
        # Find matching rows in Smartsheet
        matching_rows = smartsheet_df[
            (smartsheet_df['Work Breakdown'] == impacted_app)
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
                        'value': int(aha_amount_rounded),
                        'format': ',,,,,,,,,,,,,1,2'
                    }]
                })
            else:
                print(f"No change: '{impacted_app}' - already ${current_value_rounded}")
    
    # Add new impacted applications
    print(f"\n[DEBUG] ==== ADDING NEW AHA IMPACTS ====")
    print(f"[DEBUG] new_impacts list has {len(new_impacts)} items")
    
    if new_impacts:
        print(f"Found {len(new_impacts)} new impacted applications to add")
        for i, imp in enumerate(new_impacts):
            print(f"  Impact {i}: {imp['Impacted Applications']}")
        
        # Get parent row ID
        impacted_apps_row_id = int(impacted_apps_rows.iloc[0]['row_id'])
        print(f"[DEBUG] Parent row ID for 'Impacted Applications': {impacted_apps_row_id}")
        
        for new_impact in new_impacts:
            impacted_app = new_impact['Impacted Applications']
            aha_amount = new_impact['Aha OS Approved Amount']
            aha_amount_rounded = round(aha_amount) if pd.notna(aha_amount) else 0
            
            # Create cells for the new row
            new_row_cells = [
                {
                    'columnId': sheet['columns'][0]['id'],
                    'value': impacted_app
                },
                {
                    'columnId': aha_column_id,
                    'value': int(aha_amount_rounded),
                    'format': ',,,,,,,,,,,,,1,2'
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
                    'value': 4
                })
            
            print(f"\nAdding new impacted application: '{impacted_app}' with Aha OS Approved Amount=${int(aha_amount_rounded):,}")
            print(f"[DEBUG] Full payload being sent:")
            
            new_row_payload = {
                'parentId': impacted_apps_row_id,
                'toBottom': True,
                'cells': new_row_cells,
                'format': ',,,,,,,,,5'
            }
            
            print(f"[DEBUG] {new_row_payload}")
            
            # POST new row to Smartsheet
            res = requests.post(
                f"{BASE_URL}/sheets/{sheet_id}/rows",
                headers=SMARTSHEET_HEADERS,
                json=[new_row_payload],
                verify=False
            )
            
            print(f"[DEBUG] Response status: {res.status_code}")
            if res.status_code == 200:
                print(f"✓ Successfully added new impacted application: '{impacted_app}'")
                print(f"[DEBUG] Response body: {res.json()}")
            else:
                print(f"✗ Failed to add new impacted application '{impacted_app}': {res.status_code} - {res.text}")
    else:
        print("No new impacted applications to add - all Aha impacts already exist in Smartsheet")
    
    # Send updates to Smartsheet
    print(f"\n[DEBUG] ==== SENDING UPDATES ====")
    if rows_to_update:
        print(f"Sending {len(rows_to_update)} row updates to Smartsheet...")
        payload = rows_to_update
        res = requests.put(
            f"{BASE_URL}/sheets/{sheet_id}/rows",
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

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python test_aha_update_direct.py <sheet_id> <aha_idea>")
        print("\nExample: python test_aha_update_direct.py 1234567890 IDEA-123")
        print("\nOr enter values manually:")
        sheet_id = input("Enter Sheet ID: ").strip()
        aha_idea = input("Enter AHA Idea (e.g., IDEA-123): ").strip()
    else:
        sheet_id = sys.argv[1]
        aha_idea = sys.argv[2]
    
    if sheet_id and aha_idea:
        update_from_aha_direct(sheet_id, aha_idea)
    else:
        print("ERROR: Both sheet_id and aha_idea are required")
