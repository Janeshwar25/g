import sys
import pandas as pd
from upload.update_smartsheet import update_ppmo

# Test script for testing new task insertion under Task Name parent
# Usage: python test_new_task_insert.py <sheet_id>

def test_new_task_insert():
    if len(sys.argv) >= 2:
        sheet_id = sys.argv[1]
    else:
        print("Usage: python test_new_task_insert.py <sheet_id>")
        print("\nOr enter value manually:")
        sheet_id = input("Enter Smartsheet Sheet ID: ").strip()
    
    print(f"\n{'='*80}")
    print(f"Testing New Task Insertion")
    print(f"{'='*80}")
    print(f"Sheet ID: {sheet_id}")
    print(f"{'='*80}\n")
    
    # Create a fake optics dataframe with a new task that doesn't exist in Smartsheet
    optics_data = {
        'Task Name': [
            'ST15926_2025 Test New Task_Test-App'  # This task should not exist
        ],
        'Actuals': [12345.0],
        'ETCs': [54321.0],
        'EACs': [66666.0],
        '% Burn': [18.0]
    }
    
    optics_df = pd.DataFrame(optics_data)
    
    print("Test Optics Data (with new task):")
    print(optics_df.to_string())
    print()
    
    try:
        print(f"\n{'='*80}")
        print("Running update_ppmo function...")
        print(f"{'='*80}\n")
        
        update_ppmo(sheet_id, optics_df)
        
        print(f"\n{'='*80}")
        print("Update completed!")
        print(f"Check Smartsheet to verify the new task was added under 'Task Name' parent")
        print(f"{'='*80}")
        
    except Exception as e:
        print(f"\n{'='*80}")
        print(f"ERROR: {type(e).__name__}")
        print(f"{'='*80}")
        print(f"{str(e)}")
        import traceback
        print(f"\nFull traceback:")
        traceback.print_exc()

if __name__ == "__main__":
    test_new_task_insert()
