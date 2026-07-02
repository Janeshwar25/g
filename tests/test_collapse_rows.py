"""
Test script to test collapsing rows in Smartsheet
Usage: python test_collapse_rows.py <sheet_id>
"""

import sys
import requests
from config import Config

# Load configuration
config = Config()
BASE_URL = config.SMARTSHEET_BASE_URL
SMARTSHEET_HEADERS = config.get_smartsheet_headers()

def test_collapse_rows(sheet_id):
    """Test collapsing rows with Work Breakdown starting with C1, C2, or Task Name/Impacted Applications"""
    
    print("=" * 80)
    print("Testing Row Collapse Functionality")
    print("=" * 80)
    print(f"Sheet ID: {sheet_id}")
    print("=" * 80)
    
    # Fetch the sheet
    print("\nFetching sheet data...")
    sheet_response = requests.get(
        f"{BASE_URL}/sheets/{sheet_id}",
        headers=SMARTSHEET_HEADERS,
        verify=False
    )
    
    sheet = sheet_response.json()
    
    if 'errorCode' in sheet:
        print(f"ERROR: Failed to fetch sheet: {sheet.get('message')}")
        return
    
    sheet_rows = sheet.get('rows', [])
    sheet_columns = sheet['columns']
    
    # Find Work Breakdown column ID
    work_breakdown_col_id = None
    for col in sheet_columns:
        if col['title'] == 'Work Breakdown':
            work_breakdown_col_id = col['id']
            break
    
    if not work_breakdown_col_id:
        print("ERROR: Could not find 'Work Breakdown' column")
        return
    
    print(f"Work Breakdown column ID: {work_breakdown_col_id}")
    
    # Find rows to collapse
    print("\nSearching for rows to collapse...")
    rows_to_collapse = []
    
    for row in sheet_rows:
        work_breakdown_val = next((cell.get('value') for cell in row.get('cells', []) if cell.get('columnId') == work_breakdown_col_id), None)
        
        if work_breakdown_val:
            wb = str(work_breakdown_val).strip()
            
            # Check if Work Breakdown starts with C1, C2, or is Task Name/Impacted Applications
            if wb.startswith('C1') or wb.startswith('C2') or wb in ['Task Name', 'Impacted Applications']:
                current_expanded = row.get('expanded', True)
                print(f"  Found: '{wb}' (Row ID: {row['id']}, Currently expanded: {current_expanded})")
                rows_to_collapse.append({
                    'id': row['id'],
                    'expanded': False  # False means collapsed
                })
    
    print(f"\n" + "=" * 80)
    print(f"Found {len(rows_to_collapse)} rows to collapse")
    print("=" * 80)
    
    if not rows_to_collapse:
        print("No rows found to collapse")
        return
    
    # Show what we're about to send
    print(f"\nPayload to send (first 3 rows):")
    for i, row_data in enumerate(rows_to_collapse[:3]):
        print(f"  {i+1}. Row ID: {row_data['id']}, expanded: {row_data['expanded']}")
    
    if len(rows_to_collapse) > 3:
        print(f"  ... and {len(rows_to_collapse) - 3} more rows")
    
    # Ask for confirmation
    response = input(f"\nProceed to collapse {len(rows_to_collapse)} rows? (y/n): ")
    if response.lower() != 'y':
        print("Cancelled")
        return
    
    # Send collapse request
    print(f"\nSending collapse request...")
    collapse_payload = rows_to_collapse
    
    res = requests.put(
        f"{BASE_URL}/sheets/{sheet_id}/rows",
        headers=SMARTSHEET_HEADERS,
        json=collapse_payload,
        verify=False
    )
    
    print(f"\nResponse Status: {res.status_code}")
    
    if res.status_code == 200:
        result = res.json()
        print(f"✓ SUCCESS - Collapsed {len(rows_to_collapse)} rows")
        print(f"\nResponse preview:")
        print(f"  Result count: {len(result.get('result', []))}")
        if 'result' in result and len(result['result']) > 0:
            print(f"  First result: {result['result'][0]}")
    else:
        print(f"✗ FAILED - Error response:")
        print(res.text)
    
    # Verify by fetching sheet again
    print(f"\n" + "=" * 80)
    print("Verifying collapse state...")
    print("=" * 80)
    
    verify_response = requests.get(
        f"{BASE_URL}/sheets/{sheet_id}",
        headers=SMARTSHEET_HEADERS,
        verify=False
    )
    
    verify_sheet = verify_response.json()
    verify_rows = verify_sheet.get('rows', [])
    
    collapsed_count = 0
    for row in verify_rows:
        if row.get('expanded', True) == False:  # expanded=False means collapsed
            work_breakdown_val = next((cell.get('value') for cell in row.get('cells', []) if cell.get('columnId') == work_breakdown_col_id), None)
            if work_breakdown_val:
                wb = str(work_breakdown_val).strip()
                if wb.startswith('C1') or wb.startswith('C2') or wb in ['Task Name', 'Impacted Applications']:
                    collapsed_count += 1
                    print(f"  ✓ '{wb}' is collapsed (expanded=False)")
    
    print(f"\nTotal collapsed rows verified: {collapsed_count} / {len(rows_to_collapse)}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_collapse_rows.py <sheet_id>")
        print("\nExample: python test_collapse_rows.py 1234567890")
        print("\nOr enter value manually:")
        sheet_id = input("Enter Sheet ID: ").strip()
    else:
        sheet_id = sys.argv[1]
    
    if sheet_id:
        test_collapse_rows(sheet_id)
    else:
        print("ERROR: sheet_id is required")
