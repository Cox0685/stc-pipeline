#!/usr/bin/env python
# coding: utf-8

"""
RP2 Site Reports - Local Version
Filters gld_inspections.csv by template_category and Reporting_Group, outputs to REP folder
"""

import os
import sys
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_shared"))
from report_utils import load_site_lookup, get_site_name, clean_site_name_from_string
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

GLD_INPUT_PATH = r"C:\Users\Thomas.Cox\OneDrive - OCU Group\Desktop\00_AST_SystemsIntegration\00_AST_DataUploads\01_STC Safety Culture\Data\GLD"
REP_OUTPUT_PATH = r"C:\Users\Thomas.Cox\OneDrive - OCU Group\Desktop\00_AST_SystemsIntegration\00_AST_DataUploads\01_STC Safety Culture\Data\REP"

# Create output folder if it doesn't exist
os.makedirs(REP_OUTPUT_PATH, exist_ok=True)

# ============================================================================
# CONFIGURATION TOGGLES
# ============================================================================

# Test run: True = process only 10 rows, False = process all rows
TEST_RUN = False

# Filter criteria
TEMPLATE_CATEGORIES = [
    "Weekly H&S Inspection",
    "SubCon Audits",
    "Weekly ESG Report",
    "Work Area Inspections",
    "Site Setup Audit"
]

REPORTING_GROUP_FILTER = "Site Reports"

print("=" * 80)
print("⚔️  RP2 SITE REPORTS - LOCAL VERSION")
print("=" * 80)
print(f"📁 Input (GLD): {GLD_INPUT_PATH}")
print(f"📁 Output (REP): {REP_OUTPUT_PATH}")
print(f"🧪 Test Run: {'ON' if TEST_RUN else 'OFF'}")
print(f"🔍 Template Categories: {TEMPLATE_CATEGORIES}")
print(f"🔍 Reporting Group: '{REPORTING_GROUP_FILTER}'")
print("=" * 80)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def contains_template_category(value):
    """
    Check if the template_category column contains any of the target categories.
    Handles comma-separated values.
    """
    if pd.isna(value):
        return False
    
    value_str = str(value)
    for category in TEMPLATE_CATEGORIES:
        if category in value_str:
            return True
    return False


def contains_reporting_group(value):
    """
    Check if the Reporting_Group column contains 'Site Reports'.
    Handles comma-separated values.
    """
    if pd.isna(value):
        return False
    
    value_str = str(value)
    return REPORTING_GROUP_FILTER in value_str


# ============================================================================
# MAIN PROCESSING
# ============================================================================

def main():
    input_file = os.path.join(GLD_INPUT_PATH, "gld_inspections.csv")
    output_file = os.path.join(REP_OUTPUT_PATH, "rp2_site_reports.csv")
    
    if not os.path.exists(input_file):
        print(f"❌ Input file not found: {input_file}")
        return
    
    print(f"\n📂 Reading: {os.path.basename(input_file)}")
    
    try:
        # Read the CSV
        df = pd.read_csv(input_file, dtype=str, low_memory=False)
        print(f"   ✅ Loaded {len(df):,} rows")
        print(f"   📋 Columns: {len(df.columns)}")
        
        if TEST_RUN:
            df = df.head(10)
            print(f"   🧪 TEST MODE: Processing {len(df)} rows")
        
        # ====================================================================
        # STEP 1: Check for required columns
        # ====================================================================
        
        if 'template_category' not in df.columns:
            print(f"   ❌ 'template_category' column not found!")
            print(f"   📋 Available columns: {list(df.columns)}")
            return
        
        if 'Reporting_Group' not in df.columns:
            print(f"   ❌ 'Reporting_Group' column not found!")
            print(f"   📋 Available columns: {list(df.columns)}")
            return
        
        # ====================================================================
        # STEP 2: Load site lookup
        # ====================================================================
        
        print(f"\n⚔️ Loading site lookup from gld_sites.csv...")
        site_lookup = load_site_lookup(GLD_INPUT_PATH)
        
        # ====================================================================
        # STEP 3: Filter by template_category
        # ====================================================================
        
        print(f"\n⚔️ Filtering by template_category (must contain: {TEMPLATE_CATEGORIES})...")
        
        # Show current distribution
        print(f"\n   📋 Current template_category distribution:")
        cat_counts = df['template_category'].value_counts().head(10)
        for cat, count in cat_counts.items():
            print(f"      '{cat}': {count} rows")
        
        # Apply filter
        df_filtered = df[df['template_category'].apply(contains_template_category)].copy()
        print(f"\n   🎯 Found {len(df_filtered):,} rows matching template_category filter")
        
        if df_filtered.empty:
            print(f"   ⚠️ No rows found matching template_category criteria")
            return
        
        # ====================================================================
        # STEP 4: Filter by Reporting_Group
        # ====================================================================
        
        print(f"\n⚔️ Filtering by Reporting_Group (must contain: '{REPORTING_GROUP_FILTER}')...")
        
        # Show current distribution
        print(f"\n   📋 Current Reporting_Group distribution:")
        rg_counts = df_filtered['Reporting_Group'].value_counts().head(10)
        for rg, count in rg_counts.items():
            print(f"      '{rg}': {count} rows")
        
        # Apply filter
        df_final = df_filtered[df_filtered['Reporting_Group'].apply(contains_reporting_group)].copy()
        print(f"\n   🎯 Found {len(df_final):,} rows matching both filters")
        
        if df_final.empty:
            print(f"   ⚠️ No rows found matching Reporting_Group criteria")
            return
        
        # ====================================================================
        # STEP 5: Apply site name patch
        # ====================================================================
        
        print(f"\n⚔️ Applying site name patch...")
        
        # Apply the site name function to each row
        df_final['Site_Name_Cleaned'] = df_final.apply(
            lambda row: get_site_name(row, site_lookup), 
            axis=1
        )
        
        # Show how many got cleaned
        cleaned_count = df_final['Site_Name_Cleaned'].notna().sum()
        print(f"   ✅ Cleaned site names for {cleaned_count:,} rows")
        
        # Show sample of before/after
        print(f"\n   📋 Sample of site name cleaning:")
        sample_cols = ['site_id', 'site_name', 'name', 'Site_Name_Cleaned']
        existing_sample = [col for col in sample_cols if col in df_final.columns]
        if existing_sample:
            print(df_final[existing_sample].head(5).to_string(index=False))
        
        # ====================================================================
        # STEP 6: Sort and save
        # ====================================================================
        
        # Sort by conducted_on or date if available
        if 'conducted_on' in df_final.columns:
            df_final['conducted_on'] = pd.to_datetime(df_final['conducted_on'], errors='coerce')
            df_final = df_final.sort_values('conducted_on', ascending=False)
            print(f"\n   ✅ Sorted by conducted_on (newest first)")
        elif 'created_at' in df_final.columns:
            df_final['created_at'] = pd.to_datetime(df_final['created_at'], errors='coerce')
            df_final = df_final.sort_values('created_at', ascending=False)
            print(f"\n   ✅ Sorted by created_at (newest first)")
        
        # Save to REP folder
        df_final.to_csv(output_file, index=False, encoding='utf-8')
        print(f"\n✅ Saved to: {output_file}")
        print(f"   📊 {len(df_final):,} rows, {len(df_final.columns)} columns")
        
        # ====================================================================
        # STEP 7: Show summary
        # ====================================================================
        
        print("\n📊 RP2 Site Reports Summary:")
        print(f"   Total rows: {len(df_final):,}")
        
        # Show template_category breakdown
        if 'template_category' in df_final.columns:
            print(f"\n   Template Category breakdown:")
            for cat, count in df_final['template_category'].value_counts().items():
                print(f"      {cat}: {count} rows")
        
        # Show Reporting_Group breakdown
        if 'Reporting_Group' in df_final.columns:
            print(f"\n   Reporting Group breakdown:")
            for rg, count in df_final['Reporting_Group'].value_counts().items():
                print(f"      {rg}: {count} rows")
        
        # Show sample of the data
        print("\n📋 Sample data (first 5 rows):")
        sample_cols = ['inspection_id', 'template_name', 'template_category', 'Reporting_Group', 'Site_Name_Cleaned', 'conducted_on']
        existing_sample = [col for col in sample_cols if col in df_final.columns]
        if existing_sample:
            print(df_final[existing_sample].head(5).to_string(index=False))
        else:
            print(df_final.head(5).to_string(index=False))
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()