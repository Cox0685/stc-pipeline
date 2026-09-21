#!/usr/bin/env python
# coding: utf-8

"""
RP2 Contracts Managers Audits Report
Filters gld_inspections.csv by template_category = 'Contracts Managers Audits', outputs to REP folder
"""

import os
import sys
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_shared"))
from report_utils import load_site_lookup, get_site_name, clean_site_name_from_string
import azure_io

# ============================================================================
# CONFIGURATION
# ============================================================================

GLD_PREFIX = "GLD"
REP_PREFIX = "REP"

client = azure_io.get_client()

# ============================================================================
# CONFIGURATION TOGGLES
# ============================================================================

# Test run: True = process only 10 rows, False = process all rows
TEST_RUN = False

# Filter criteria
TEMPLATE_CATEGORY_FILTER = "Contracts Managers Audits"

print("=" * 80)
print("⚔️  RP2 CONTRACTS MANAGERS AUDITS REPORT")
print("=" * 80)
print(f"📁 Input (GLD): ADLS/{GLD_PREFIX}")
print(f"📁 Output (REP): ADLS/{REP_PREFIX}")
print(f"🧪 Test Run: {'ON' if TEST_RUN else 'OFF'}")
print(f"🔍 Template Category: '{TEMPLATE_CATEGORY_FILTER}'")
print("=" * 80)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def contains_template_category(value):
    """
    Check if the template_category column contains 'Contracts Managers Audits'.
    Handles comma-separated values.
    """
    if pd.isna(value):
        return False
    
    value_str = str(value)
    return TEMPLATE_CATEGORY_FILTER in value_str


# load_site_lookup, get_site_name, and clean_site_name_from_string now live in
# _shared/report_utils.py - they were identical copies in this file and in
# RP2 QSET Reports.py / RP2 Site Reports.py.

# ============================================================================
# MAIN PROCESSING
# ============================================================================

def main():
    input_file = f"{GLD_PREFIX}/gld_inspections.csv"
    output_file = f"{REP_PREFIX}/rp2_contracts_managers_audits.csv"
    
    if not client.exists(input_file):
        print(f"❌ Input file not found: {input_file}")
        return
    
    print(f"\n📂 Reading: {input_file}")
    
    try:
        # Read the CSV
        df = client.read_csv(input_file, dtype=str, low_memory=False)
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
        
        # ====================================================================
        # STEP 2: Load site lookup
        # ====================================================================
        
        print(f"\n⚔️ Loading site lookup from gld_sites.csv...")
        site_lookup = load_site_lookup(GLD_PREFIX)
        
        # ====================================================================
        # STEP 3: Filter by template_category = Contracts Managers Audits
        # ====================================================================
        
        print(f"\n⚔️ Filtering by template_category (must contain: '{TEMPLATE_CATEGORY_FILTER}')...")
        
        # Show current distribution
        print(f"\n   📋 Current template_category distribution:")
        cat_counts = df['template_category'].value_counts().head(10)
        for cat, count in cat_counts.items():
            print(f"      '{cat}': {count} rows")
        
        # Apply filter
        df_final = df[df['template_category'].apply(contains_template_category)].copy()
        print(f"\n   🎯 Found {len(df_final):,} rows matching template_category filter")
        
        if df_final.empty:
            print(f"   ⚠️ No rows found matching template_category criteria")
            return
        
        # ====================================================================
        # STEP 4: Apply site name patch
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
        # STEP 5: Sort and save
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
        client.write_csv(df_final, output_file, index=False, encoding='utf-8')
        print(f"\n✅ Saved to: {output_file}")
        print(f"   📊 {len(df_final):,} rows, {len(df_final.columns)} columns")
        
        # ====================================================================
        # STEP 6: Show summary
        # ====================================================================
        
        print("\n📊 RP2 Contracts Managers Audits Summary:")
        print(f"   Total rows: {len(df_final):,}")
        
        # Show template_category breakdown
        if 'template_category' in df_final.columns:
            print(f"\n   Template Category breakdown:")
            for cat, count in df_final['template_category'].value_counts().items():
                print(f"      {cat}: {count} rows")
        
        # Show sample of the data
        print("\n📋 Sample data (first 5 rows):")
        sample_cols = ['inspection_id', 'template_name', 'template_category', 'Site_Name_Cleaned', 'conducted_on']
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