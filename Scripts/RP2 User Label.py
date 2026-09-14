#!/usr/bin/env python
# coding: utf-8

"""
Map User Groups to Actions, Inspections, Investigations, and Issues
Reads gld_groups.csv and maps GroupName and Reporting_Group to:
- gld_actions.csv (via task_creator_user_id, fallback to task_creator_firstname + task_creator_lastname)
- gld_inspections.csv (via author_id, fallback to owner_name)
- gld_investigations.csv (via creator_id)
- gld_issues.csv (via task_creator_user_id, fallback to task_creator_firstname + task_creator_lastname)
"""

import os
import pandas as pd
import re
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

GLD_INPUT_PATH = r"C:\Users\Thomas.Cox\OneDrive - OCU Group\Desktop\00_AST_SystemsIntegration\00_AST_DataUploads\01_STC Safety Culture\Data\GLD"
GLD_OUTPUT_PATH = r"C:\Users\Thomas.Cox\OneDrive - OCU Group\Desktop\00_AST_SystemsIntegration\00_AST_DataUploads\01_STC Safety Culture\Data\GLD"

# Create output folder if it doesn't exist
os.makedirs(GLD_OUTPUT_PATH, exist_ok=True)

# ============================================================================
# CONFIGURATION TOGGLES
# ============================================================================

# Test run: True = process only 10 rows, False = process all rows
TEST_RUN = False

# Values to exclude from results
EXCLUDED_VALUES = ["Non Reporter"]

print("=" * 80)
print("⚔️  MAP USER GROUPS - LOCAL VERSION")
print("=" * 80)
print(f"📁 Input (GLD): {GLD_INPUT_PATH}")
print(f"📁 Output (GLD): {GLD_OUTPUT_PATH}")
print(f"🧪 Test Run: {'ON' if TEST_RUN else 'OFF'}")
print(f"🚫 Excluded Values: {EXCLUDED_VALUES}")
print("=" * 80)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def is_invalid_id(value):
    """Check if the ID is invalid (all 1s, null, or empty)"""
    if pd.isna(value):
        return True
    val_str = str(value).strip()
    if not val_str:
        return True
    # Check if it's all 1s (with optional decimal point or E notation)
    cleaned = val_str.replace('.', '').replace('E+31', '').replace('E', '').replace('-', '')
    if cleaned and all(c == '1' for c in cleaned):
        return True
    return False


def normalize_name(name):
    """Normalize a name string for comparison (lowercase, remove extra spaces)"""
    if pd.isna(name):
        return ''
    return ' '.join(str(name).strip().split()).lower()


def is_excluded(value):
    """Check if a value should be excluded"""
    if pd.isna(value):
        return False
    val_str = str(value).strip()
    for excluded in EXCLUDED_VALUES:
        if val_str.lower() == excluded.lower():
            return True
    return False


def create_group_lookup(df_groups):
    """
    Create a lookup dictionary for groups.
    Uses EXACT name matching only - no partial or first/last alone matches.
    """
    lookup_by_id = {}
    lookup_by_name = {}
    
    for _, row in df_groups.iterrows():
        user_id = row.get('user_id', '')
        firstname = normalize_name(row.get('firstname', ''))
        lastname = normalize_name(row.get('lastname', ''))
        
        # Build full name variations (exact matches only)
        full_name_parts = []
        if firstname:
            full_name_parts.append(firstname)
        if lastname:
            full_name_parts.append(lastname)
        full_name = ' '.join(full_name_parts) if full_name_parts else ''
        
        group_name = row.get('GroupName', '')
        reporting_group = row.get('Reporting_Group', '')
        
        # Skip if either value is excluded
        if is_excluded(group_name) or is_excluded(reporting_group):
            continue
        
        group_info = {
            'GroupName': group_name,
            'Reporting_Group': reporting_group,
            'firstname': firstname,
            'lastname': lastname
        }
        
        # Lookup by user_id (if valid) - store as list for multiple matches
        if user_id and not is_invalid_id(user_id):
            id_key = str(user_id)
            if id_key not in lookup_by_id:
                lookup_by_id[id_key] = []
            lookup_by_id[id_key].append(group_info)
        
        # Lookup by exact full name only
        if full_name:
            if full_name not in lookup_by_name:
                lookup_by_name[full_name] = []
            lookup_by_name[full_name].append(group_info)
        
        # Also store as "last, first" format for exact matching
        if firstname and lastname:
            last_first = f"{lastname}, {firstname}"
            if last_first not in lookup_by_name:
                lookup_by_name[last_first] = []
            lookup_by_name[last_first].append(group_info)
    
    return lookup_by_id, lookup_by_name


def find_exact_name_matches(search_name, lookup_by_name):
    """
    Find exact name matches from the lookup.
    Returns a list of all exact matches found.
    """
    if not search_name:
        return []
    
    search_name = normalize_name(search_name)
    matches = []
    
    # 1. Exact match
    if search_name in lookup_by_name:
        matches.extend(lookup_by_name[search_name])
    
    # 2. Try "Last, First" format
    parts = search_name.split()
    if len(parts) >= 2:
        last_first = f"{parts[-1]}, {' '.join(parts[:-1])}"
        if last_first in lookup_by_name:
            matches.extend(lookup_by_name[last_first])
    
    return matches


def get_group_info(row, lookup_by_id, lookup_by_name, id_col, name_col1=None, name_col2=None):
    """
    Get group info from lookup, trying ID first then name fallback.
    Returns comma-separated strings for GroupName and Reporting_Group.
    Excludes any values that are in EXCLUDED_VALUES.
    """
    matches = []
    
    # Try by ID first
    id_val = row.get(id_col, '')
    if not is_invalid_id(id_val):
        id_key = str(id_val)
        if id_key in lookup_by_id:
            matches.extend(lookup_by_id[id_key])
    
    # Try by name (single column or combined) - EXACT MATCH ONLY
    if name_col1 and name_col2:
        name1 = str(row.get(name_col1, '')).strip()
        name2 = str(row.get(name_col2, '')).strip()
        if name1 or name2:
            # Build full name
            full_name = ' '.join([name1, name2]).strip() if name1 and name2 else name1 or name2
            if full_name:
                matches.extend(find_exact_name_matches(full_name, lookup_by_name))
    elif name_col1 and not name_col2:
        name = str(row.get(name_col1, '')).strip()
        if name:
            matches.extend(find_exact_name_matches(name, lookup_by_name))
    
    # Remove duplicates and filter out excluded values
    unique_matches = []
    seen = set()
    for match in matches:
        key = f"{match['GroupName']}|{match['Reporting_Group']}"
        if key not in seen:
            # Skip if either value is excluded
            if is_excluded(match['GroupName']) or is_excluded(match['Reporting_Group']):
                continue
            seen.add(key)
            unique_matches.append(match)
    
    if unique_matches:
        # Extract all GroupNames and Reporting_Groups as comma-separated strings
        group_names = [m['GroupName'] for m in unique_matches if m['GroupName'] and not is_excluded(m['GroupName'])]
        reporting_groups = [m['Reporting_Group'] for m in unique_matches if m['Reporting_Group'] and not is_excluded(m['Reporting_Group'])]
        
        return {
            'GroupName': ', '.join(sorted(set(group_names))) if group_names else '',
            'Reporting_Group': ', '.join(sorted(set(reporting_groups))) if reporting_groups else ''
        }
    
    # Return empty values
    return {'GroupName': '', 'Reporting_Group': ''}


# ============================================================================
# MAIN PROCESSING
# ============================================================================

def main():
    # ========================================================================
    # STEP 1: Read gld_groups.csv (the mapping source)
    # ========================================================================
    
    groups_file = os.path.join(GLD_INPUT_PATH, "gld_groups.csv")
    
    if not os.path.exists(groups_file):
        print(f"❌ groups file not found: {groups_file}")
        return
    
    print(f"\n📂 Reading: {os.path.basename(groups_file)}")
    df_groups = pd.read_csv(groups_file, dtype=str, low_memory=False)
    print(f"   ✅ Loaded {len(df_groups):,} rows")
    
    # Check for required columns
    if 'user_id' not in df_groups.columns:
        print(f"   ❌ 'user_id' column not found in groups file!")
        return
    
    if 'GroupName' not in df_groups.columns:
        print(f"   ❌ 'GroupName' column not found in groups file!")
        return
    
    if 'Reporting_Group' not in df_groups.columns:
        print(f"   ❌ 'Reporting_Group' column not found in groups file!")
        return
    
    # Create lookup dictionaries (EXACT NAME MATCH ONLY)
    lookup_by_id, lookup_by_name = create_group_lookup(df_groups)
    print(f"   ✅ Created lookup: {len(lookup_by_id)} by ID, {len(lookup_by_name)} by name")
    print(f"   🚫 Excluded 'Non Reporter' values from lookup")
    print(f"   🎯 Using EXACT name matching only (no partial matches)")
    
    # ========================================================================
    # STEP 2: Map to gld_actions.csv (via task_creator_user_id, fallback to firstname+lastname)
    # ========================================================================
    
    actions_file = os.path.join(GLD_INPUT_PATH, "gld_actions.csv")
    
    if os.path.exists(actions_file):
        print(f"\n📂 Reading: {os.path.basename(actions_file)}")
        df_actions = pd.read_csv(actions_file, dtype=str, low_memory=False)
        print(f"   ✅ Loaded {len(df_actions):,} rows")
        
        if TEST_RUN:
            df_actions = df_actions.head(10)
            print(f"   🧪 TEST MODE: Processing {len(df_actions)} rows")
        
        # Check for required columns
        if 'task_creator_user_id' in df_actions.columns:
            # Add mapping function
            def get_action_group(row):
                return get_group_info(
                    row, lookup_by_id, lookup_by_name,
                    'task_creator_user_id',
                    'task_creator_firstname', 'task_creator_lastname'
                )
            
            # Apply mapping
            group_info = df_actions.apply(get_action_group, axis=1)
            df_actions['GroupName'] = group_info.apply(lambda x: x['GroupName'])
            df_actions['Reporting_Group'] = group_info.apply(lambda x: x['Reporting_Group'])
            
            # Count how many were mapped
            mapped_count = df_actions[df_actions['GroupName'] != ''].shape[0]
            print(f"   ✅ Mapped {mapped_count:,} rows with GroupName and Reporting_Group")
            
            # Show sample of multiple matches
            multi_matches = df_actions[df_actions['GroupName'].str.contains(',', na=False)]
            if not multi_matches.empty:
                print(f"   📋 Found {len(multi_matches)} rows with multiple GroupName matches")
            
            # Save back to GLD folder
            output_file = os.path.join(GLD_OUTPUT_PATH, "gld_actions.csv")
            df_actions.to_csv(output_file, index=False, encoding='utf-8')
            print(f"   ✅ Saved to: {output_file}")
        else:
            print(f"   ⚠️ 'task_creator_user_id' column not found in gld_actions.csv")
    else:
        print(f"\n⚠️ gld_actions.csv not found, skipping...")
    
    # ========================================================================
    # STEP 3: Map to gld_inspections.csv (via author_id, fallback to owner_name)
    # ========================================================================
    
    inspections_file = os.path.join(GLD_INPUT_PATH, "gld_inspections.csv")
    
    if os.path.exists(inspections_file):
        print(f"\n📂 Reading: {os.path.basename(inspections_file)}")
        df_inspections = pd.read_csv(inspections_file, dtype=str, low_memory=False)
        print(f"   ✅ Loaded {len(df_inspections):,} rows")
        
        if TEST_RUN:
            df_inspections = df_inspections.head(10)
            print(f"   🧪 TEST MODE: Processing {len(df_inspections)} rows")
        
        # Check for required columns
        if 'author_id' in df_inspections.columns:
            # Add mapping function
            def get_inspection_group(row):
                return get_group_info(
                    row, lookup_by_id, lookup_by_name,
                    'author_id',
                    'owner_name', None  # owner_name is already combined
                )
            
            # Apply mapping
            group_info = df_inspections.apply(get_inspection_group, axis=1)
            df_inspections['GroupName'] = group_info.apply(lambda x: x['GroupName'])
            df_inspections['Reporting_Group'] = group_info.apply(lambda x: x['Reporting_Group'])
            
            # Count how many were mapped
            mapped_count = df_inspections[df_inspections['GroupName'] != ''].shape[0]
            print(f"   ✅ Mapped {mapped_count:,} rows with GroupName and Reporting_Group")
            
            # Show sample of multiple matches
            multi_matches = df_inspections[df_inspections['GroupName'].str.contains(',', na=False)]
            if not multi_matches.empty:
                print(f"   📋 Found {len(multi_matches)} rows with multiple GroupName matches")
            
            # Save back to GLD folder
            output_file = os.path.join(GLD_OUTPUT_PATH, "gld_inspections.csv")
            df_inspections.to_csv(output_file, index=False, encoding='utf-8')
            print(f"   ✅ Saved to: {output_file}")
        else:
            print(f"   ⚠️ 'author_id' column not found in gld_inspections.csv")
    else:
        print(f"\n⚠️ gld_inspections.csv not found, skipping...")
    
    # ========================================================================
    # STEP 4: Map to gld_investigations.csv (via creator_id)
    # ========================================================================
    
    investigations_file = os.path.join(GLD_INPUT_PATH, "gld_investigations.csv")
    
    if os.path.exists(investigations_file):
        print(f"\n📂 Reading: {os.path.basename(investigations_file)}")
        df_investigations = pd.read_csv(investigations_file, dtype=str, low_memory=False)
        print(f"   ✅ Loaded {len(df_investigations):,} rows")
        
        if TEST_RUN:
            df_investigations = df_investigations.head(10)
            print(f"   🧪 TEST MODE: Processing {len(df_investigations)} rows")
        
        # Check for required columns
        if 'creator_id' in df_investigations.columns:
            # Add mapping function (no name fallback needed)
            def get_investigation_group(row):
                return get_group_info(
                    row, lookup_by_id, lookup_by_name,
                    'creator_id', None, None
                )
            
            # Apply mapping
            group_info = df_investigations.apply(get_investigation_group, axis=1)
            df_investigations['GroupName'] = group_info.apply(lambda x: x['GroupName'])
            df_investigations['Reporting_Group'] = group_info.apply(lambda x: x['Reporting_Group'])
            
            # Count how many were mapped
            mapped_count = df_investigations[df_investigations['GroupName'] != ''].shape[0]
            print(f"   ✅ Mapped {mapped_count:,} rows with GroupName and Reporting_Group")
            
            # Show sample of multiple matches
            multi_matches = df_investigations[df_investigations['GroupName'].str.contains(',', na=False)]
            if not multi_matches.empty:
                print(f"   📋 Found {len(multi_matches)} rows with multiple GroupName matches")
            
            # Save back to GLD folder
            output_file = os.path.join(GLD_OUTPUT_PATH, "gld_investigations.csv")
            df_investigations.to_csv(output_file, index=False, encoding='utf-8')
            print(f"   ✅ Saved to: {output_file}")
        else:
            print(f"   ⚠️ 'creator_id' column not found in gld_investigations.csv")
    else:
        print(f"\n⚠️ gld_investigations.csv not found, skipping...")
    
    # ========================================================================
    # STEP 5: Map to gld_issues.csv (via task_creator_user_id, fallback to firstname+lastname)
    # ========================================================================
    
    issues_file = os.path.join(GLD_INPUT_PATH, "gld_issues.csv")
    
    if os.path.exists(issues_file):
        print(f"\n📂 Reading: {os.path.basename(issues_file)}")
        df_issues = pd.read_csv(issues_file, dtype=str, low_memory=False)
        print(f"   ✅ Loaded {len(df_issues):,} rows")
        
        if TEST_RUN:
            df_issues = df_issues.head(10)
            print(f"   🧪 TEST MODE: Processing {len(df_issues)} rows")
        
        # Check for required columns
        if 'task_creator_user_id' in df_issues.columns:
            # Add mapping function
            def get_issue_group(row):
                return get_group_info(
                    row, lookup_by_id, lookup_by_name,
                    'task_creator_user_id',
                    'task_creator_firstname', 'task_creator_lastname'
                )
            
            # Apply mapping
            group_info = df_issues.apply(get_issue_group, axis=1)
            df_issues['GroupName'] = group_info.apply(lambda x: x['GroupName'])
            df_issues['Reporting_Group'] = group_info.apply(lambda x: x['Reporting_Group'])
            
            # Count how many were mapped
            mapped_count = df_issues[df_issues['GroupName'] != ''].shape[0]
            print(f"   ✅ Mapped {mapped_count:,} rows with GroupName and Reporting_Group")
            
            # Show sample of multiple matches
            multi_matches = df_issues[df_issues['GroupName'].str.contains(',', na=False)]
            if not multi_matches.empty:
                print(f"   📋 Found {len(multi_matches)} rows with multiple GroupName matches")
            
            # Save back to GLD folder
            output_file = os.path.join(GLD_OUTPUT_PATH, "gld_issues.csv")
            df_issues.to_csv(output_file, index=False, encoding='utf-8')
            print(f"   ✅ Saved to: {output_file}")
        else:
            print(f"   ⚠️ 'task_creator_user_id' column not found in gld_issues.csv")
    else:
        print(f"\n⚠️ gld_issues.csv not found, skipping...")
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    
    print("\n" + "=" * 80)
    print("🏁 MAP USER GROUPS COMPLETE")
    print("=" * 80)
    print(f"📅 Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🚫 Excluded 'Non Reporter' from results")
    print(f"🎯 Using EXACT name matching only (no partial matches)")
    print("=" * 80)
    
    print("\n📋 GLD Output Files Updated:")
    print("-" * 60)
    
    updated_files = ['gld_actions.csv', 'gld_inspections.csv', 'gld_investigations.csv', 'gld_issues.csv']
    for file in updated_files:
        file_path = os.path.join(GLD_OUTPUT_PATH, file)
        if os.path.exists(file_path):
            size = os.path.getsize(file_path)
            try:
                df = pd.read_csv(file_path)
                # Check if GroupName column exists
                if 'GroupName' in df.columns:
                    mapped = df[df['GroupName'] != ''].shape[0]
                    multi = df[df['GroupName'].str.contains(',', na=False)].shape[0]
                    print(f"   {file:<35} | {len(df):>6} rows | {mapped:>6} mapped | {multi:>6} multi | {size:>10,} bytes")
                else:
                    print(f"   {file:<35} | {len(df):>6} rows | {size:>10,} bytes")
            except:
                print(f"   {file:<35} | {size:>10,} bytes")
        else:
            print(f"   {file:<35} | NOT CREATED")

if __name__ == "__main__":
    main()