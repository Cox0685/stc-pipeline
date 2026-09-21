#!/usr/bin/env python
# coding: utf-8

"""
Add Reporting Group to GLD Groups
Reads gld_groups.csv, adds Reporting_Group column based on GroupName mapping
"""

import os
import sys
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_shared"))
import azure_io

# ============================================================================
# CONFIGURATION
# ============================================================================

GLD_PREFIX = "GLD"

client = azure_io.get_client()

# ============================================================================
# REPORTING GROUP MAPPING (GroupName -> Reporting Group)
# ============================================================================

reporting_group_mapping = {
    # Site Reports
    "agents": "Site Reports",
    "engineers": "Site Reports",
    "general foremen": "Site Reports",
    "sub agents": "Site Reports",
    "Site Reports": "Site Reports",
    
    # QSET
    "health & safety": "QSET",
    "environmental": "QSET",
    "quality": "QSET",
    "QSET": "QSET",
    
    # CM Audits
    "contracts managers": "CM Audits",
    "CM Audits": "CM Audits",
}

print("=" * 80)
print("⚔️  ADDING REPORTING GROUP TO GLD GROUPS")
print("=" * 80)
print(f"📁 Input: ADLS/{GLD_PREFIX}")
print(f"📁 Output: ADLS/{GLD_PREFIX}")
print("=" * 80)

# ============================================================================
# FUNCTION TO GET REPORTING GROUP
# ============================================================================

def get_reporting_group(group_name: str) -> str:
    """
    Get the Reporting Group based on GroupName.
    Returns the mapped value or "Non Reporter" if not found.
    """
    if pd.isna(group_name):
        return "Non Reporter"
    
    group_name = str(group_name).strip()
    
    # Try exact match
    if group_name in reporting_group_mapping:
        return reporting_group_mapping[group_name]
    
    # Try case-insensitive match
    group_lower = group_name.lower()
    for key, value in reporting_group_mapping.items():
        if key.lower() == group_lower:
            return value
    
    # If not found, return "Non Reporter"
    return "Non Reporter"

# ============================================================================
# MAIN PROCESSING
# ============================================================================

def main():
    input_file = f"{GLD_PREFIX}/gld_groups.csv"
    
    if not client.exists(input_file):
        print(f"❌ File not found: {input_file}")
        return
    
    print(f"\n📂 Reading: {input_file}")
    
    try:
        df = client.read_csv(input_file, dtype=str, low_memory=False)
        print(f"   ✅ Loaded {len(df):,} rows")
        print(f"   📋 Columns: {list(df.columns)}")
        
        # Check if GroupName column exists
        if 'GroupName' not in df.columns:
            print("   ❌ 'GroupName' column not found!")
            print(f"   📋 Available columns: {list(df.columns)}")
            return
        
        # Apply Reporting Group mapping
        print("\n⚔️ Applying Reporting Group mapping...")
        print("   📋 Unmapped groups will be marked as 'Non Reporter'")
        
        # Get reporting group for each row
        df['Reporting_Group'] = df['GroupName'].apply(get_reporting_group)
        
        # Show summary
        print("\n📊 Reporting Group Summary:")
        category_counts = df['Reporting_Group'].value_counts()
        for cat, count in category_counts.items():
            print(f"   {cat}: {count} groups")
        
        # Show the mapping that was applied
        print("\n📋 GroupName -> Reporting Group Mapping:")
        unique_groups = df[['GroupName', 'Reporting_Group']].drop_duplicates().sort_values('GroupName')
        for _, row in unique_groups.iterrows():
            print(f"   {row['GroupName']} -> {row['Reporting_Group']}")
        
        # Show Non Reporter groups (for awareness)
        non_reporter = df[df['Reporting_Group'] == 'Non Reporter']
        if not non_reporter.empty:
            print(f"\n⚠️ Non Reporter groups ({len(non_reporter)}):")
            for group in non_reporter['GroupName'].unique():
                print(f"   {group}")
        
        # Save back to GLD tier
        output_file = f"{GLD_PREFIX}/gld_groups.csv"
        client.write_csv(df, output_file, index=False, encoding='utf-8')
        print(f"\n✅ Saved to: {output_file}")
        print(f"   📊 {len(df):,} rows, {len(df.columns)} columns")
        print(f"   📋 New column: Reporting_Group")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()