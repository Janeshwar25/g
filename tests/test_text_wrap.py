"""
Test script to check if text wrap is enabled for Work Breakdown column
Usage: python test_text_wrap.py <sheet_id>
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from config import Config

# Load configuration
config = Config()
BASE_URL = config.SMARTSHEET_BASE_URL
SMARTSHEET_HEADERS = config.get_smartsheet_headers()

def test_text_wrap(sheet_id):
    """Test if text wrapping is enabled for Work Breakdown column"""
    
    print("=" * 80)
    print("Testing Text Wrap Functionality")
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
    
    sheet_columns = sheet['columns']
    
    # Find Work Breakdown column
    work_breakdown_col = None
    for col in sheet_columns:
        if col['title'] == 'Work Breakdown':
            work_breakdown_col = col
            break
    
    if not work_breakdown_col:
        print("ERROR: Could not find 'Work Breakdown' column")
        return
    
    print(f"Work Breakdown column ID: {work_breakdown_col['id']}")
    
    # Check if format is present
    if 'format' in work_breakdown_col:
        print(f"\n✓ Format is set: {work_breakdown_col['format']}")
        
        # Text wrap format code is at position 15 (1-indexed), value 1 = on
        # Format string: ',,,,,,,,,,,,,,,1,'
        format_str = work_breakdown_col['format']
        format_parts = format_str.split(',')
        
        # Position 15 should have value '1' for text wrap
        if len(format_parts) > 15 and format_parts[15] == '1':
            print("✓ Text wrap is ENABLED (position 15 = 1)")
        else:
            print(f"✗ Text wrap is NOT enabled (format: {format_str})")
            print(f"  Format parts: {format_parts}")
            print(f"  Position 15 value: {format_parts[15] if len(format_parts) > 15 else 'N/A'}")
    else:
        print("\n✗ No format found on Work Breakdown column")
        print("  Text wrap is NOT enabled")
    
    print("\n" + "=" * 80)
    print("Full column details:")
    print("=" * 80)
    import pprint
    pprint.pprint(work_breakdown_col)
    
    # Ask user if they want to enable text wrap
    print("\n" + "=" * 80)
    response = input("\nDo you want to enable text wrap for this column? (y/n): ")
    
    if response.lower() == 'y':
        print("\nEnabling text wrap...")
        wrap_payload = {
            'format': ',,,,,,,,,,,,,,,1,'
        }
        
        res = requests.put(
            f"{BASE_URL}/sheets/{sheet_id}/columns/{work_breakdown_col['id']}",
            headers=SMARTSHEET_HEADERS,
            json=wrap_payload,
            verify=False
        )
        
        print(f"\nResponse Status: {res.status_code}")
        
        if res.status_code == 200:
            print("✓ Successfully enabled text wrapping")
            
            # Verify by fetching again
            print("\nVerifying text wrap was applied...")
            verify_response = requests.get(
                f"{BASE_URL}/sheets/{sheet_id}",
                headers=SMARTSHEET_HEADERS,
                verify=False
            )
            
            verify_sheet = verify_response.json()
            verify_col = None
            for col in verify_sheet['columns']:
                if col['title'] == 'Work Breakdown':
                    verify_col = col
                    break
            
            if verify_col and 'format' in verify_col:
                print(f"✓ Verified - Format is now: {verify_col['format']}")
            else:
                print("✗ Verification failed - no format found")
        else:
            print(f"✗ Failed to enable text wrap: {res.text}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_text_wrap.py <sheet_id>")
        sys.exit(1)
    
    sheet_id = sys.argv[1]
    test_text_wrap(sheet_id)
