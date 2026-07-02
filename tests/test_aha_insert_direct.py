"""
Test script for adding new Aha impacts directly using sheet ID
Usage: python test_aha_insert_direct.py <sheet_id>
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

def test_aha_insert_direct(sheet_id, aha_idea):
    """Test adding new Aha impacts using direct sheet ID"""
    
    print("=" * 80)
    print("Testing New Aha Impact Insertion (Direct Sheet ID)")
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
    
    # Add row IDs
    row_id = []
    for row in sheet['rows']:
        row_id.append(row['id'])
    smartsheet_df['row_id'] = row_id
    
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
    
    print(f"\nAha impacts from API:")
    print(aha_df[['Impacted Applications', 'Aha OS Approved Amount']])
    
    # Show existing impacts in Smartsheet
    print(f"\n" + "=" * 80)
    print("Existing impacts in Smartsheet:")
    print("=" * 80)
    
    # Find all rows that appear to be under Impacted Applications section
    # Important: Only look AFTER "Financials" row, then between "Impacted Applications" and "Aha Total"
    past_financials = False
    start_printing = False
    existing_impacts_list = []
    
    for idx, row in smartsheet_df.iterrows():
        wb = str(row.get('Work Breakdown', '')).strip()
        
        # First, we need to pass the Financials section
        if wb == 'Financials':
            past_financials = True
            print(f"DEBUG: Passed 'Financials' at row {idx}")
            continue
        
        # Only start looking for Impacted Applications AFTER Financials
        if not past_financials:
            continue
            
        if wb == 'Impacted Applications':
            start_printing = True
            print(f"DEBUG: Found 'Impacted Applications' at row {idx}")
            continue
        elif wb == 'Aha Total':
            print(f"DEBUG: Stopping at 'Aha Total' at row {idx}")
            break
        elif start_printing and wb:
            print(f"DEBUG: Found impact at row {idx}: '{wb}'")
            existing_impacts_list.append(wb)
    
    print(f"\n" + "=" * 80)
    if existing_impacts_list:
        print(f"Found {len(existing_impacts_list)} existing impacts:")
        for i, impact in enumerate(existing_impacts_list):
            print(f"  {i}: {impact}")
    else:
        print("No existing impacts found in Smartsheet")
    print("=" * 80)
    
    # Find the Aha column
    impacted_apps_rows = smartsheet_df[smartsheet_df['Work Breakdown'] == 'Impacted Applications']
    
    if impacted_apps_rows.empty:
        print("\nERROR: 'Impacted Applications' header row not found")
        return
    
    aha_column_id = None
    header_row = impacted_apps_rows.iloc[0]
    
    for col_idx, col_name in enumerate(smartsheet_df.columns):
        if col_name not in ['Work Breakdown', 'row_id']:
            col_value = str(header_row[col_name]).strip()
            if col_value == 'Aha OS Approved Amount':
                actual_col_idx = list(smartsheet_df.columns).index(col_name)
                column_info = sheet['columns'][actual_col_idx]
                aha_column_id = column_info['id']
                print(f"\nFound Aha column: {col_name} (ID: {aha_column_id})")
                break
    
    if not aha_column_id:
        print("\nERROR: Could not find Aha OS Approved Amount column")
        return
    
    # Find new impacts - compare against existing_impacts_list from the section above
    print(f"\n" + "=" * 80)
    print("Comparing Aha impacts with Smartsheet impacts:")
    print("=" * 80)
    
    existing_impacts_set = set(existing_impacts_list)
    new_impacts = []
    
    for _, aha_row in aha_df.iterrows():
        impacted_app = aha_row['Impacted Applications']
        if impacted_app in existing_impacts_set:
            print(f"  ✓ '{impacted_app}' - EXISTS in Smartsheet")
        else:
            print(f"  ✗ '{impacted_app}' - NEW (not in Smartsheet)")
            new_impacts.append(aha_row)
    
    print(f"\nFound {len(new_impacts)} new impacts to add")
    
    if not new_impacts:
        print("\nNo new impacts to add - all exist in Smartsheet")
        print("\nAdding a test impact for demonstration...")
        
        # Add a test impact
        test_impact = pd.Series({
            'Impacted Applications': 'TEST - New Impact Application',
            'Aha OS Approved Amount': 50000
        })
        new_impacts.append(test_impact)
    
    # Get parent row ID
    impacted_apps_row_id = int(impacted_apps_rows.iloc[0]['row_id'])
    print(f"\nParent row ID for 'Impacted Applications': {impacted_apps_row_id}")
    
    # Add new impacts
    for new_impact in new_impacts:
        impacted_app = new_impact['Impacted Applications']
        aha_amount = new_impact['Aha OS Approved Amount']
        aha_amount_rounded = round(aha_amount) if pd.notna(aha_amount) else 0
        
        # Create cells
        new_row_cells = [
            {
                'columnId': sheet['columns'][0]['id'],  # Work Breakdown
                'value': impacted_app
            },
            {
                'columnId': aha_column_id,
                'value': int(aha_amount_rounded),
                'format': ',,,,,,,,,,,,,1,2'  # Currency format with commas
            }
        ]
        
        # Find Level column
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
        
        print(f"\n" + "=" * 80)
        print(f"Adding new impact: '{impacted_app}' with amount=${int(aha_amount_rounded):,}")
        print("=" * 80)
        
        new_row_payload = {
            'parentId': impacted_apps_row_id,
            'toBottom': True,
            'cells': new_row_cells,
            'format': ',,,,,,,,,5'  # Light yellow background
        }
        
        print(f"\nPayload:")
        print(f"  parentId: {impacted_apps_row_id}")
        print(f"  toBottom: True")
        print(f"  cells: {len(new_row_cells)} cells")
        print(f"    - Work Breakdown: '{impacted_app}'")
        print(f"    - Aha Amount: ${int(aha_amount_rounded):,}")
        print(f"    - Level: 4")
        print(f"  format: ',,,,,,,,,5' (light yellow)")
        
        # POST to Smartsheet
        print("\nSending POST request to Smartsheet...")
        res = requests.post(
            f"{BASE_URL}/sheets/{sheet_id}/rows",
            headers=SMARTSHEET_HEADERS,
            json=[new_row_payload],
            verify=False
        )
        
        print(f"\nResponse Status: {res.status_code}")
        
        if res.status_code == 200:
            response_data = res.json()
            print(f"✓ SUCCESS - New impact added!")
            print(f"\nResponse data:")
            if 'result' in response_data:
                for result in response_data['result']:
                    print(f"  Row ID: {result.get('id')}")
                    print(f"  Row Number: {result.get('rowNumber')}")
                    print(f"  Parent ID: {result.get('parentId')}")
        else:
            print(f"✗ FAILED - Error response:")
            print(res.text)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python test_aha_insert_direct.py <sheet_id> <aha_idea>")
        print("\nExample: python test_aha_insert_direct.py 1234567890 IDEA-123")
        print("\nOr enter values manually:")
        sheet_id = input("Enter Sheet ID: ").strip()
        aha_idea = input("Enter AHA Idea (e.g., IDEA-123): ").strip()
    else:
        sheet_id = sys.argv[1]
        aha_idea = sys.argv[2]
    
    if sheet_id and aha_idea:
        test_aha_insert_direct(sheet_id, aha_idea)
    else:
        print("ERROR: Both sheet_id and aha_idea are required")
