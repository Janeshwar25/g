import sys
import pandas as pd
from upload.update_smartsheet import update_ppmo
from engine.mapping import get_optics_financials

# Test script for debugging optics updates
# Usage: python test_optics_update.py <sheet_id> <prj_id> <strategic_theme>

def test_optics_update():
    # Get parameters from command line or use defaults
    if len(sys.argv) >= 4:
        sheet_id = sys.argv[1]
        prj = sys.argv[2]
        st = sys.argv[3]
    else:
        print("Usage: python test_optics_update.py <sheet_id> <prj_id> <strategic_theme>")
        print("\nExample: python test_optics_update.py 1234567890 PRJ12345 ST19894")
        print("\nOr enter values manually:")
        sheet_id = input("Enter Smartsheet Sheet ID: ").strip()
        prj = input("Enter Project ID (from Optics): ").strip()
        st = input("Enter Strategic Theme (e.g., ST19894): ").strip()
    
    print(f"\n{'='*80}")
    print(f"Testing Optics Update")
    print(f"{'='*80}")
    print(f"Sheet ID: {sheet_id}")
    print(f"Project ID: {prj}")
    print(f"Strategic Theme: {st}")
    print(f"{'='*80}\n")
    
    try:
        # Fetch optics data
        print("Fetching Optics financial data...")
        optics_df = get_optics_financials(prj, st)
        
        if optics_df is None or optics_df.empty:
            print("ERROR: No Optics data returned. Check if the project ID and strategic theme are correct.")
            return
        
        print(f"\n✓ Successfully fetched {len(optics_df)} Optics records")
        print(f"\nOptics Data Preview:")
        print(optics_df.to_string())
        
        # Run the update
        print(f"\n{'='*80}")
        print("Running update_ppmo function...")
        print(f"{'='*80}\n")
        
        update_ppmo(sheet_id, optics_df)
        
        print(f"\n{'='*80}")
        print("Update completed!")
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
    test_optics_update()
