"""
Test script to verify the fix for Rally Point Estimate error when no Rally data exists.
Run this locally to test the changes.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from engine.mapping import build_plan, get_aha_data
import pandas as pd

def test_empty_rally():
    """Test building a plan when there's no valid Rally strategic theme."""
    
    print("\n" + "="*80)
    print("Testing: Build plan with AHA idea that has NO Rally strategic theme")
    print("="*80 + "\n")
    
    # Test parameters - use an actual AHA idea from your system
    # You may need to change this to a real idea that has no strategic theme
    plan_params = {
        "plan idea": "PSTRATEGIC-I-1967",  # Change this to your test idea
        "project type": "General",
        "idea name": "Test Plan - No Rally Data",
        "BDL": "Test BDL",
        "RDL": "Test RDL"
    }
    
    try:
        print("📋 Building plan with parameters:")
        for key, value in plan_params.items():
            print(f"   {key}: {value}")
        print()
        
        # First test get_aha_data directly to see all the values
        print("="*80)
        print("STEP 1: Testing get_aha_data() function directly")
        print("="*80)
        idea = plan_params["plan idea"]
        
        aha_data, os_approved, theme, tag, prj, go_live = get_aha_data(idea)
        
        print(f"\n📊 AHA Data Results:")
        print(f"   ✓ Strategic Theme: '{theme}'")
        print(f"   ✓ Initiative/Tag: '{tag}'")
        print(f"   ✓ Project ID: '{prj}'")
        print(f"   ✓ OS Approved Amount: {os_approved}")
        print(f"   ✓ Go Live Date: {go_live}")
        print(f"   ✓ AHA DataFrame Shape: {aha_data.shape}")
        
        if not aha_data.empty:
            print(f"\n   AHA DataFrame Columns: {list(aha_data.columns)}")
            print(f"\n   AHA DataFrame Content:")
            print(aha_data.to_string(index=False))
        else:
            print(f"\n   ⚠️  AHA DataFrame is empty")
        
        print("\n" + "="*80)
        print("STEP 2: Testing build_plan() function")
        print("="*80 + "\n")
        
        # Call build_plan
        result = build_plan(plan_params)
        
        # Check if we got a valid DataFrame
        if not isinstance(result, pd.DataFrame):
            print("❌ ERROR: Result is not a DataFrame")
            return False
        
        if result.empty:
            print("❌ ERROR: Result DataFrame is empty")
            return False
        
        # Check for Rally Point Estimate column
        if 'Rally Point Estimate' not in result.columns:
            print("❌ ERROR: 'Rally Point Estimate' column is missing!")
            print(f"   Available columns: {list(result.columns)}")
            return False
        
        # Check for other Rally columns
        rally_columns = ['Rally Point Estimate', 'Rally Cost Estimate', 'Rally Lead Team']
        missing_columns = [col for col in rally_columns if col not in result.columns]
        
        if missing_columns:
            print(f"❌ ERROR: Missing Rally columns: {missing_columns}")
            return False
        
        print("✅ SUCCESS: Plan built successfully!")
        print(f"\n📊 Result Summary:")
        print(f"   Rows: {len(result)}")
        print(f"   Columns: {list(result.columns)}")
        print(f"\n   Rally Column Values:")
        print(f"   - Rally Point Estimate: {result['Rally Point Estimate'].notna().sum()} non-null values")
        print(f"   - Rally Cost Estimate: {result['Rally Cost Estimate'].notna().sum()} non-null values")
        print(f"   - Rally Lead Team: {result['Rally Lead Team'].notna().sum()} non-null values")
        
        print(f"\n   First 5 rows of key columns:")
        print(result[['Work Breakdown', 'Task ID', 'Rally Point Estimate', 'Rally Cost Estimate']].head())
        
        return True
        
    except KeyError as e:
        print(f"❌ KeyError: {e}")
        print(f"   This is the error we're trying to fix!")
        import traceback
        traceback.print_exc()
        return False
    
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "🔧 Rally Point Estimate Fix - Local Test" + "\n")
    
    success = test_empty_rally()
    
    print("\n" + "="*80)
    if success:
        print("✅ TEST PASSED: All checks completed successfully!")
    else:
        print("❌ TEST FAILED: Please review the errors above")
    print("="*80 + "\n")
    
    sys.exit(0 if success else 1)
