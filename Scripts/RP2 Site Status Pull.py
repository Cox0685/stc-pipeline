#!/usr/bin/env python
# coding: utf-8

"""
RP2 Site Status Report
Creates a unique site report from gld_actions.csv with one row per site
Then updates gld_sites.csv with Site Area information
"""

import os
import sys
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_shared"))
import azure_io

# ============================================================================
# CONFIGURATION
# ============================================================================

GLD_PREFIX = "GLD"
REP_PREFIX = "REP"

client = azure_io.get_client()

# ============================================================================
# MAIN PROCESSING
# ============================================================================

def main():
    print("=" * 80)
    print("⚔️  RP2 SITE STATUS REPORT")
    print("=" * 80)
    print(f"📁 Input: ADLS/{GLD_PREFIX}")
    print(f"📁 Output: ADLS/{REP_PREFIX}")
    print("=" * 80)
    
    input_file = f"{GLD_PREFIX}/gld_actions.csv"
    
    if not client.exists(input_file):
        print(f"❌ Input file not found: {input_file}")
        return
    
    print(f"\n📂 Reading: {input_file}")
    
    try:
        # Read the CSV
        df = client.read_csv(input_file, dtype=str, low_memory=False)
        print(f"   ✅ Loaded {len(df):,} rows")
        
        # Check required columns
        required_cols = ['task_site_area', 'task_site_id', 'task_site_name']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            print(f"   ❌ Missing columns: {missing_cols}")
            print(f"   📋 Available columns: {list(df.columns)}")
            return
        
        # ====================================================================
        # STEP 1: Clean site names
        # ====================================================================
        
        def clean_site_name(name):
            """Clean site name by removing everything after the first '/'"""
            if pd.isna(name):
                return None
            name_str = str(name).strip()
            if '/' in name_str:
                return name_str.split('/')[0].strip()
            return name_str
        
        # Create cleaned site name
        df['Site Name Cleaned'] = df['task_site_name'].apply(clean_site_name)
        
        # ====================================================================
        # STEP 2: Get one row per site
        # ====================================================================
        
        # Option 1: Use task_site_id as the unique identifier
        df_unique = df.drop_duplicates(subset=['task_site_id'], keep='first').copy()
        print(f"\n   🎯 Found {len(df_unique):,} unique sites (by task_site_id)")
        
        # Option 2: If task_site_id is blank, use cleaned site name
        # Check how many have blank site_id
        blank_id_count = df_unique['task_site_id'].isna().sum()
        if blank_id_count > 0:
            print(f"   ⚠️ {blank_id_count} rows have blank task_site_id - using Site Name Cleaned instead")
            
            # For rows with blank task_site_id, use cleaned site name as identifier
            df_without_id = df[df['task_site_id'].isna() | (df['task_site_id'] == '')].copy()
            df_without_id = df_without_id.drop_duplicates(subset=['Site Name Cleaned'], keep='first')
            
            # For rows with task_site_id, keep those
            df_with_id = df[df['task_site_id'].notna() & (df['task_site_id'] != '')].copy()
            df_with_id = df_with_id.drop_duplicates(subset=['task_site_id'], keep='first')
            
            # Combine
            df_unique = pd.concat([df_with_id, df_without_id], ignore_index=True)
            print(f"   ✅ Combined: {len(df_unique):,} unique sites")
        
        # ====================================================================
        # STEP 3: Select columns for output
        # ====================================================================
        
        # Select the columns we want
        output_cols = ['task_site_area', 'task_site_id', 'task_site_name', 'Site Name Cleaned']
        existing_cols = [col for col in output_cols if col in df_unique.columns]
        
        df_output = df_unique[existing_cols].copy()
        
        # Rename columns for clarity
        df_output = df_output.rename(columns={
            'task_site_area': 'Site Area',
            'task_site_id': 'Site ID',
            'task_site_name': 'Site Name (Original)',
            'Site Name Cleaned': 'Site Name (Cleaned)'
        })
        
        # Sort by Site Name (Cleaned)
        df_output = df_output.sort_values('Site Name (Cleaned)')
        
        # ====================================================================
        # STEP 4: Save to REP folder
        # ====================================================================
        
        output_file = f"{REP_PREFIX}/rp2_site_status.csv"
        client.write_csv(df_output, output_file, index=False, encoding='utf-8')
        
        print(f"\n✅ Saved to: {output_file}")
        print(f"   📊 {len(df_output):,} rows, {len(df_output.columns)} columns")
        
        # ====================================================================
        # STEP 5: Show summary
        # ====================================================================
        
        print("\n📊 Site Status Summary:")
        print(f"   Total unique sites: {len(df_output):,}")
        
        # Show site area breakdown
        if 'Site Area' in df_output.columns:
            print(f"\n   Site Area breakdown:")
            area_counts = df_output['Site Area'].value_counts()
            for area, count in area_counts.head(10).items():
                print(f"      {area}: {count} sites")
        
        # Show sample
        print("\n📋 Sample data (first 10 rows):")
        print(df_output.head(10).to_string(index=False))
        
        # ====================================================================
        # STEP 6: Update gld_sites.csv with Site Area
        # ====================================================================
        
        update_sites_file(df_output)
        
        print("\n" + "=" * 80)
        print("🏁 COMPLETE")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


# ============================================================================
# UPDATE SITES FILE FUNCTION
# ============================================================================

def update_sites_file(df_site_status):
    """
    Update gld_sites.csv with Site Area information from the site status report
    Matches by Site ID (task_site_id) with the 'id' column in gld_sites.csv
    """
    print("\n" + "=" * 80)
    print("📋 UPDATING GLD_SITES.CSV WITH SITE AREA")
    print("=" * 80)
    
    sites_file = f"{GLD_PREFIX}/gld_sites.csv"
    
    if not client.exists(sites_file):
        print(f"❌ Sites file not found: {sites_file}")
        return
    
    try:
        # Read the sites CSV
        df_sites = client.read_csv(sites_file, dtype=str, low_memory=False)
        print(f"   ✅ Loaded {len(df_sites):,} rows from gld_sites.csv")
        print(f"   📋 Columns in gld_sites.csv: {list(df_sites.columns)}")
        
        # Check if 'id' column exists
        if 'id' not in df_sites.columns:
            print(f"   ❌ 'id' column not found in gld_sites.csv")
            print(f"   📋 Available columns: {list(df_sites.columns)}")
            return
        
        # Check if 'Site Area' column exists, if not create it
        if 'Site Area' not in df_sites.columns:
            df_sites['Site Area'] = None
            print(f"   ➕ Added 'Site Area' column to gld_sites.csv")
        
        # Create a mapping of Site ID to Site Area from the status report
        # Only use rows where Site ID is not blank
        df_status_clean = df_site_status[df_site_status['Site ID'].notna() & 
                                         (df_site_status['Site ID'] != '')].copy()
        
        if len(df_status_clean) == 0:
            print(f"   ⚠️ No valid Site IDs found in status report to map")
            return
        
        # Create lookup dictionary
        site_area_lookup = dict(zip(df_status_clean['Site ID'], df_status_clean['Site Area']))
        print(f"   📊 Created lookup with {len(site_area_lookup):,} site mappings")
        
        # Update the Site Area column in df_sites
        updated_count = 0
        matched_count = 0
        
        for idx, row in df_sites.iterrows():
            site_id = str(row.get('id', '')).strip()
            if site_id and site_id in site_area_lookup:
                matched_count += 1
                # Only update if the site area is not already set or is blank
                current_area = str(row.get('Site Area', '')).strip()
                if pd.isna(current_area) or current_area == '' or current_area == 'nan':
                    df_sites.at[idx, 'Site Area'] = site_area_lookup[site_id]
                    updated_count += 1
        
        print(f"   🔗 Found {matched_count:,} matching sites")
        print(f"   ✅ Updated 'Site Area' for {updated_count:,} sites")
        
        # Save the updated sites file
        client.write_csv(df_sites, sites_file, index=False, encoding='utf-8')
        print(f"   ✅ Saved updated gld_sites.csv")
        
        # Show summary of Site Area distribution in sites file
        area_counts = df_sites['Site Area'].value_counts()
        if len(area_counts) > 0:
            print(f"\n   📊 Site Area distribution in updated sites file:")
            for area, count in area_counts.head(10).items():
                if pd.notna(area) and area != '' and area != 'nan':
                    print(f"      {area}: {count} sites")
        else:
            print(f"\n   ⚠️ No Site Area values were updated in gld_sites.csv")
        
        # Show sample of updated rows
        updated_rows = df_sites[df_sites['Site Area'].notna() & 
                               (df_sites['Site Area'] != '') & 
                               (df_sites['Site Area'] != 'nan')].head(5)
        if len(updated_rows) > 0:
            print(f"\n   📋 Sample of updated sites (first 5):")
            for idx, row in updated_rows.iterrows():
                print(f"      ID: {row.get('id', 'N/A')}, Name: {row.get('name', 'N/A')}, Area: {row.get('Site Area', 'N/A')}")
        else:
            print(f"\n   ⚠️ No sites were updated - check if Site Area values exist in the status report")
            print(f"   📋 Sample of site status data (first 5 rows):")
            print(df_site_status[['Site ID', 'Site Area']].head(5).to_string(index=False))
        
    except Exception as e:
        print(f"   ❌ Error updating sites file: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()