import pandas as pd
from engine.mapping import build_plan

# Test parameters for a plan with financials
plan_params = {
    "plan idea": "PSTRATEGIC-I-838",
    "project type": "Care Cash",
    "idea name": "Care Cash Migration to Solutran",
    "BDL": "Test BDL",
    "RDL": "Test RDL"
}

print("Building plan with financial data...")
final_plan = build_plan(plan_params)

print("\n" + "="*80)
print("FINAL PLAN STRUCTURE:")
print("="*80)
print(f"Total rows: {len(final_plan)}")
print(f"\nColumns: {list(final_plan.columns)}")

print("\n" + "="*80)
print("LAST 15 ROWS (should include Financials section):")
print("="*80)
print(final_plan.tail(15).to_string())

print("\n" + "="*80)
print("FINANCIALS SECTION ONLY:")
print("="*80)
# Find rows with Level 3 or 4 after "Financials" Level 2
financials_mask = final_plan['Work Breakdown'] == 'Financials'
if financials_mask.any():
    financials_idx = final_plan[financials_mask].index[0]
    print(final_plan.iloc[financials_idx:].to_string())
else:
    print("Financials section not found")

print("\n" + "="*80)
print("LEVEL DISTRIBUTION:")
print("="*80)
print(final_plan['Level'].value_counts().sort_index())
