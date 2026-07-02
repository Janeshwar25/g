import sys
import pandas as pd
from upload.update_smartsheet import update_from_aha

# Test script for testing new Aha impacted application insertion
# Usage: python test_new_aha_insert.py <strategic_theme>

def test_new_aha_insert():
    if len(sys.argv) >= 2:
        st = sys.argv[1]
    else:
        print("Usage: python test_new_aha_insert.py <strategic_theme>")
        print("\nExample: python test_new_aha_insert.py ST19894")
        print("\nOr enter value manually:")
        st = input("Enter Strategic Theme (e.g., ST19894): ").strip()
    
    print(f"\n{'='*80}")
    print(f"Testing New Aha Impact Insertion")
    print(f"{'='*80}")
    print(f"Strategic Theme: {st}")
    print(f"{'='*80}\n")
    
    # Create a fake aha dataframe with a new impacted application that doesn't exist
    aha_data = {
        'Impacted Applications': [
            'Test New Impact Application'  # This should not exist in Smartsheet
        ],
        'Aha OS Approved Amount': [99999.0]
    }
    
    aha_df = pd.DataFrame(aha_data)
    
    print("Test Aha Data (with new impacted application):")
    print(aha_df.to_string())
    print()
    
    try:
        print(f"\n{'='*80}")
        print("Running update_from_aha function...")
        print(f"{'='*80}\n")
        
        update_from_aha(st)
        
        print(f"\n{'='*80}")
        print("Update completed!")
        print(f"Check Smartsheet to verify the new impacted application was added under 'Impacted Applications' parent")
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
    test_new_aha_insert()
