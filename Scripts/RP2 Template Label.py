#!/usr/bin/env python
# coding: utf-8

"""
Map Template Categories to Actions and Inspections
Reads gld_templates.csv and maps template_category and QSET_category to:
- gld_actions.csv (via task_template_id)
- gld_inspections.csv (via template_id)
"""

import os
import sys
import io
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_shared"))
import azure_io

# ============================================================================
# CONFIGURATION
# ============================================================================

GLD_PREFIX = "GLD"

client = azure_io.get_client()

# ============================================================================
# CONFIGURATION TOGGLES
# ============================================================================

# Test run: True = process only 10 rows, False = process all rows
TEST_RUN = False

print("=" * 80)
print("⚔️  MAP TEMPLATE CATEGORIES - LOCAL VERSION")
print("=" * 80)
print(f"📁 Input (GLD): ADLS/{GLD_PREFIX}")
print(f"📁 Output (GLD): ADLS/{GLD_PREFIX}")
print(f"🧪 Test Run: {'ON' if TEST_RUN else 'OFF'}")
print("=" * 80)

# ============================================================================
# MAIN PROCESSING
# ============================================================================

def main():
    # ========================================================================
    # STEP 1: Read gld_templates.csv (the mapping source)
    # ========================================================================
    
    templates_file = f"{GLD_PREFIX}/gld_templates.csv"
    
    if not client.exists(templates_file):
        print(f"❌ templates file not found: {templates_file}")
        return
    
    print(f"\n📂 Reading: {templates_file}")
    df_templates = client.read_csv(templates_file, dtype=str, low_memory=False)
    print(f"   ✅ Loaded {len(df_templates):,} rows")
    
    # Check for required columns
    if 'id' not in df_templates.columns:
        print(f"   ❌ 'id' column not found in templates file!")
        return
    
    if 'template_category' not in df_templates.columns:
        print(f"   ❌ 'template_category' column not found in templates file!")
        return
    
    if 'QSET_category' not in df_templates.columns:
        print(f"   ❌ 'QSET_category' column not found in templates file!")
        return
    
    # Create lookup dictionary: template_id -> (template_category, QSET_category)
    template_lookup = {}
    for _, row in df_templates.iterrows():
        template_id = row.get('id', '')
        if template_id:
            template_lookup[template_id] = {
                'template_category': row.get('template_category', ''),
                'QSET_category': row.get('QSET_category', '')
            }
    
    print(f"   ✅ Created lookup for {len(template_lookup):,} templates")
    
    # ========================================================================
    # STEP 2: Map to gld_actions.csv (via task_template_id)
    # ========================================================================
    
    actions_file = f"{GLD_PREFIX}/gld_actions.csv"
    
    if client.exists(actions_file):
        print(f"\n📂 Reading: {actions_file}")
        df_actions = client.read_csv(actions_file, dtype=str, low_memory=False)
        print(f"   ✅ Loaded {len(df_actions):,} rows")
        
        if TEST_RUN:
            df_actions = df_actions.head(10)
            print(f"   🧪 TEST MODE: Processing {len(df_actions)} rows")
        
        # Check for task_template_id column
        if 'task_template_id' in df_actions.columns:
            # Add the new columns
            df_actions['template_category'] = df_actions['task_template_id'].map(
                lambda x: template_lookup.get(x, {}).get('template_category', '') if pd.notna(x) else ''
            )
            df_actions['QSET_category'] = df_actions['task_template_id'].map(
                lambda x: template_lookup.get(x, {}).get('QSET_category', '') if pd.notna(x) else ''
            )
            
            # Count how many were mapped
            mapped_count = df_actions['template_category'].notna().sum()
            print(f"   ✅ Mapped {mapped_count:,} rows with template_category and QSET_category")
            
            # Save back to GLD folder
            output_file = f"{GLD_PREFIX}/gld_actions.csv"
            client.write_csv(df_actions, output_file, index=False, encoding='utf-8')
            print(f"   ✅ Saved to: {output_file}")
        else:
            print(f"   ⚠️ 'task_template_id' column not found in gld_actions.csv")
    else:
        print(f"\n⚠️ gld_actions.csv not found, skipping...")
    
    # ========================================================================
    # STEP 3: Map to gld_inspections.csv (via template_id)
    # ========================================================================
    
    inspections_file = f"{GLD_PREFIX}/gld_inspections.csv"
    
    if client.exists(inspections_file):
        print(f"\n📂 Reading: {inspections_file}")
        df_inspections = client.read_csv(inspections_file, dtype=str, low_memory=False)
        print(f"   ✅ Loaded {len(df_inspections):,} rows")
        
        if TEST_RUN:
            df_inspections = df_inspections.head(10)
            print(f"   🧪 TEST MODE: Processing {len(df_inspections)} rows")
        
        # Check for template_id column
        if 'template_id' in df_inspections.columns:
            # Add the new columns
            df_inspections['template_category'] = df_inspections['template_id'].map(
                lambda x: template_lookup.get(x, {}).get('template_category', '') if pd.notna(x) else ''
            )
            df_inspections['QSET_category'] = df_inspections['template_id'].map(
                lambda x: template_lookup.get(x, {}).get('QSET_category', '') if pd.notna(x) else ''
            )
            
            # Count how many were mapped
            mapped_count = df_inspections['template_category'].notna().sum()
            print(f"   ✅ Mapped {mapped_count:,} rows with template_category and QSET_category")
            
            # Save back to GLD folder
            output_file = f"{GLD_PREFIX}/gld_inspections.csv"
            client.write_csv(df_inspections, output_file, index=False, encoding='utf-8')
            print(f"   ✅ Saved to: {output_file}")
        else:
            print(f"   ⚠️ 'template_id' column not found in gld_inspections.csv")
    else:
        print(f"\n⚠️ gld_inspections.csv not found, skipping...")
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    
    print("\n" + "=" * 80)
    print("🏁 MAP TEMPLATE CATEGORIES COMPLETE")
    print("=" * 80)
    print(f"📅 Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # Show summary of GLD folder
    print("\n📋 GLD Output Files:")
    print("-" * 60)
    
    for file in ['gld_actions.csv', 'gld_inspections.csv']:
        file_path = f"{GLD_PREFIX}/{file}"
        if client.exists(file_path):
            try:
                raw = client.read_bytes(file_path)
                df = pd.read_csv(io.BytesIO(raw))
                print(f"   {file:<35} | {len(df):>6} rows | {len(df.columns):>3} cols | {len(raw):>10,} bytes")
            except Exception:
                print(f"   {file:<35} | (could not read for summary)")
        else:
            print(f"   {file:<35} | NOT CREATED")

if __name__ == "__main__":
    main()