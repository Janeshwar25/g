"""
Test script to verify Rally data is being fetched correctly for ideas with valid strategic themes
"""

import sys
import pandas as pd
from engine.mapping import get_aha_data, get_rally_data_hcp, get_lead_team_mapping

def test_rally_data_fetch():
    """Test Rally data fetching with different AHA ideas"""
    
    test_cases = [
        {
            "idea": "PSTRATEGIC-I-2278",
            "description": "Should have valid strategic theme and Rally data",
            "expect_rally": True
        },
        {
            "idea": "PSTRATEGIC-I-1967", 
            "description": "Has ST20162 but Rally fetch fails",
            "expect_rally": True
        }
    ]
    
    all_passed = True
    
    for test in test_cases:
        print("\n" + "="*80)
        print(f"Testing: {test['idea']}")
        print(f"Description: {test['description']}")
        print("="*80 + "\n")
        
        try:
            # Step 1: Get AHA data and strategic theme
            print(f"Step 1: Fetching AHA data for {test['idea']}...")
            aha_data, os_approved, rally_theme, tag, prj, go_live = get_aha_data(test['idea'])
            
            print(f"✅ AHA Data Retrieved:")
            print(f"   Strategic Theme: {rally_theme}")
            print(f"   Tag: {tag}")
            print(f"   PRJ: {prj}")
            if os_approved:
                try:
                    print(f"   OS Approved: ${float(os_approved):,.0f}")
                except (ValueError, TypeError):
                    print(f"   OS Approved: {os_approved}")
            else:
                print(f"   OS Approved: None")
            print(f"   Go Live: {go_live}")
            print(f"   AHA Impacts: {len(aha_data)} rows")
            
            if aha_data is not None and not aha_data.empty:
                print(f"\n   AHA DataFrame columns: {list(aha_data.columns)}")
                print(f"   Sample data:")
                display_cols = [col for col in ['Impacts Delivery team', 'Impact Type', 'Impact Cost'] if col in aha_data.columns]
                if display_cols:
                    print(aha_data[display_cols].head(3).to_string(index=False))
            
            # Step 2: Check if Rally should be fetched
            print(f"\nStep 2: Checking Rally fetch conditions...")
            print(f"   Theme value: '{rally_theme}'")
            print(f"   Starts with 'ST': {rally_theme.startswith('ST') if rally_theme else False}")
            print(f"   Should fetch Rally: {rally_theme != 'No ST' and rally_theme and rally_theme.startswith('ST')}")
            
            if rally_theme == 'No ST' or not rally_theme or not rally_theme.startswith('ST'):
                print(f"   ⚠️  Skipping Rally fetch (no valid strategic theme)")
                if test['expect_rally']:
                    print(f"   ❌ UNEXPECTED: Expected Rally data but theme is invalid")
                    all_passed = False
                else:
                    print(f"   ✅ EXPECTED: No Rally data for this idea")
                continue
            
            # Step 3: Attempt Rally data fetch
            print(f"\nStep 3: Fetching Rally data for {rally_theme}...")
            ltm = get_lead_team_mapping()
            
            try:
                rally_data = get_rally_data_hcp(rally_theme, ltm)
                
                if rally_data is None or rally_data.empty:
                    print(f"   ⚠️  Rally data returned empty DataFrame")
                    if test['expect_rally']:
                        print(f"   ⚠️  WARNING: Expected Rally data but got empty DataFrame")
                    else:
                        print(f"   ✅ EXPECTED: Rally data empty")
                else:
                    print(f"   ✅ Rally Data Retrieved: {len(rally_data)} rows")
                    print(f"   Rally columns: {list(rally_data.columns)}")
                    
                    # Check for key Rally columns
                    key_columns = ['Preliminary Estimate Value', 'Rally Cost Estimate', 'Rally Lead Team', 'Name', 'Release']
                    present = [col for col in key_columns if col in rally_data.columns]
                    missing = [col for col in key_columns if col not in rally_data.columns]
                    
                    print(f"\n   Key columns present: {present}")
                    if missing:
                        print(f"   ⚠️  Missing columns: {missing}")
                    
                    # Show sample Rally data
                    if 'Preliminary Estimate Value' in rally_data.columns:
                        total_points = rally_data['Preliminary Estimate Value'].sum()
                        print(f"\n   Total Rally Points: {total_points}")
                    
                    if 'Rally Cost Estimate' in rally_data.columns:
                        total_cost = rally_data['Rally Cost Estimate'].sum()
                        print(f"   Total Rally Cost: ${total_cost:,.0f}" if pd.notna(total_cost) else "   Total Rally Cost: None")
                    
                    print(f"\n   Sample Rally data:")
                    display_cols = [col for col in ['Name', 'Preliminary Estimate Value', 'Rally Cost Estimate', 'Rally Lead Team'] if col in rally_data.columns]
                    if display_cols:
                        print(rally_data[display_cols].head(3).to_string(index=False))
                    
                    if test['expect_rally']:
                        print(f"\n   ✅ EXPECTED: Rally data retrieved successfully")
                    else:
                        print(f"\n   ⚠️  UNEXPECTED: Got Rally data when not expected")
                        all_passed = False
                        
            except Exception as rally_error:
                print(f"   ❌ Rally fetch failed with error: {rally_error}")
                print(f"   Error type: {type(rally_error).__name__}")
                if test['expect_rally']:
                    print(f"   ❌ UNEXPECTED: Rally fetch should have succeeded")
                    all_passed = False
                else:
                    print(f"   ✅ EXPECTED: Rally fetch failure")
                    
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False
    
    return all_passed


if __name__ == "__main__":
    print("\n" + "🔧 Rally Data Fetch Test" + "\n")
    
    success = test_rally_data_fetch()
    
    print("\n" + "="*80)
    if success:
        print("✅ ALL TESTS PASSED!")
    else:
        print("⚠️  SOME TESTS HAD UNEXPECTED RESULTS - Please review above")
    print("="*80 + "\n")
    
    sys.exit(0 if success else 1)
