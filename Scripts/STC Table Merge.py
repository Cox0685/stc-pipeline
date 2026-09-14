#!/usr/bin/env python
# coding: utf-8

"""
STC Table Merge - Local Version (Keep DROP_TABLE, but NO column drops on kept tables)
Reads from SLV folder, transforms/merges data, outputs to GLD folder
"""

import os
import pandas as pd
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

# ============================================================================
# CONFIGURATION
# ============================================================================

# Input folder (where SLV CSVs are)
SLV_INPUT_PATH = r"C:\Users\Thomas.Cox\OneDrive - OCU Group\Desktop\00_AST_SystemsIntegration\00_AST_DataUploads\01_STC Safety Culture\Data\SLV"

# Output folder (where GLD transformed data goes)
GLD_OUTPUT_PATH = r"C:\Users\Thomas.Cox\OneDrive - OCU Group\Desktop\00_AST_SystemsIntegration\00_AST_DataUploads\01_STC Safety Culture\Data\GLD"

# Create output folder if it doesn't exist
os.makedirs(GLD_OUTPUT_PATH, exist_ok=True)

# ============================================================================
# CONFIGURATION TOGGLES
# ============================================================================

# Test run: True = process only 10 rows per table, False = process all rows
TEST_RUN = False

# ============================================================================
# TABLE TOGGLES - True = process this table, False = skip it
# ============================================================================

TABLE_TOGGLES = {
    "actions_feed": True,
    "actions_retrieve": True,
    "audits_details": True,
    "audits_search": True,
    "groups_list": True,
    "groups_users": True,
    "incidents_details": True,
    "incidents_feed": True,
    "inspections_answers": True,
    "inspections_answers_flattened": True,
    "issues_details": True,
    "issues_list": True,
    "issues_question_answers": True,
    "schedule_items": True,
    "site_members": True,
    "sites_list": True,
    "templates_feed": True,
    "templates_list": True,
    "user_groups": True,
    "users_feed": True
}

# ============================================================================
# TRANSFORMATION CONFIGURATION
# ============================================================================

# DROP_TABLE = Table is NOT copied to GLD (dropped)
# KEEP_AND_TRANSFORM = Table IS copied to GLD (all columns preserved, joins applied)

lv3_transformation_config = {
    "actions_feed": {
        "status": "DROP_TABLE",  # Dropped - not needed
        "reason": "All columns marked for drop.",
        "joins": []
    },
    "actions_retrieve": {
        "status": "KEEP_AND_TRANSFORM",
        "target_table": "gld_actions",
        "joins": [
            {
                "target_column": "template_name",
                "join_table": "templates_list",
                "left_key": "task_template_id",
                "right_key": "id",
                "return_column": "name"
            }
        ]
    },
    "audits_details": {
        "status": "DROP_TABLE",  # Dropped - not needed
        "reason": "All columns marked for drop.",
        "joins": []
    },
    "audits_search": {
        "status": "KEEP_AND_TRANSFORM",
        "target_table": "gld_inspections",
        "joins": [
            {
                "target_column": "site_name",
                "join_table": "sites_list",
                "left_key": "site_id",
                "right_key": "site_uuid",
                "return_column": "name"
            }
        ]
    },
    "groups_list": {
        "status": "DROP_TABLE",  # Dropped - used only as lookup
        "reason": "Lookup source for groups_users.",
        "joins": []
    },
    "groups_users": {
        "status": "KEEP_AND_TRANSFORM",
        "target_table": "gld_groups",
        "joins": [
            {
                "target_column": "GroupName",
                "join_table": "groups_list",
                "left_key": "_ParentID",
                "right_key": "id",
                "return_column": "name"
            }
        ]
    },
    "incidents_details": {
        "status": "DROP_TABLE",  # Dropped - not needed
        "reason": "All columns marked for drop.",
        "joins": []
    },
    "incidents_feed": {
        "status": "KEEP_AND_TRANSFORM",
        "target_table": "gld_investigations",
        "joins": []
    },
    "inspections_answers": {
        "status": "KEEP_AND_TRANSFORM",
        "target_table": "gld_inspections_answers",
        "joins": []
    },
    "inspections_answers_flattened": {
        "status": "KEEP_AND_TRANSFORM",
        "target_table": "gld_inspections_answers_flattened",
        "joins": []
    },
    "issues_details": {
        "status": "DROP_TABLE",  # Dropped - not needed
        "reason": "All columns marked for drop.",
        "joins": []
    },
    "issues_list": {
        "status": "KEEP_AND_TRANSFORM",
        "target_table": "gld_issues",
        "joins": []
    },
    "issues_answers": {
        "status": "KEEP_AND_TRANSFORM",
        "target_table": "gld_issues_answers",
        "joins": [
            {
                "target_column": "location_geo_position_latitude",
                "join_table": "issues_list",
                "left_key": "task_unique_id",
                "right_key": "task_unique_id",
                "return_column": "location_geo_position_latitude"
            },
            {
                "target_column": "location_geo_position_longitude",
                "join_table": "issues_list",
                "left_key": "task_unique_id",
                "right_key": "task_unique_id",
                "return_column": "location_geo_position_longitude"
            }
        ]
    },
    "schedule_items": {
        "status": "DROP_TABLE",  # Dropped - not needed
        "reason": "All columns marked for drop.",
        "joins": []
    },
    "site_members": {
        "status": "KEEP_AND_TRANSFORM",
        "target_table": "gld_site_members",
        "joins": []
    },
    "sites_list": {
        "status": "KEEP_AND_TRANSFORM",
        "target_table": "gld_sites",
        "joins": []
    },
    "templates_feed": {
        "status": "DROP_TABLE",  # Dropped - not needed
        "reason": "All columns marked for drop.",
        "joins": []
    },
    "templates_list": {
        "status": "KEEP_AND_TRANSFORM",
        "target_table": "gld_templates",
        "joins": []
    },
    "user_groups": {
        "status": "DROP_TABLE",  # Dropped - not needed
        "reason": "All columns marked for drop.",
        "joins": []
    },
    "users_feed": {
        "status": "KEEP_AND_TRANSFORM",
        "target_table": "gld_users",
        "joins": []
    }
}

print("=" * 80)
print("⚔️  STC TABLE MERGE - LOCAL VERSION")
print("=" * 80)
print(f"📁 Input (SLV): {SLV_INPUT_PATH}")
print(f"📁 Output (GLD): {GLD_OUTPUT_PATH}")
print(f"🧪 Test Run: {'ON' if TEST_RUN else 'OFF'}")
if TEST_RUN:
    print(f"   📊 Test Limit: 10 rows per table")
print("=" * 80)

# Show which tables are enabled/disabled
print("\n📋 TABLE STATUS:")
enabled_count = 0
disabled_count = 0
for table_name, enabled in TABLE_TOGGLES.items():
    status = "✅ ENABLED" if enabled else "❌ DISABLED"
    if enabled:
        enabled_count += 1
    else:
        disabled_count += 1
    print(f"   {status} - {table_name}")
print(f"\n   📊 {enabled_count} tables enabled, {disabled_count} tables disabled")
print("=" * 80)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def write_large_dataframe(df: pd.DataFrame, output_file: str, chunk_size: int = 1000):
    """
    Write a large DataFrame to CSV in chunks to avoid MemoryError.
    Preserves all columns exactly as they are.
    """
    total_rows = len(df)
    total_cols = len(df.columns)
    print(f"   💾 Writing {total_rows} rows with {total_cols} columns in chunks of {chunk_size}...")
    
    # Write header once
    header_written = False
    
    for i in range(0, total_rows, chunk_size):
        chunk = df.iloc[i:i+chunk_size]
        mode = 'a' if header_written else 'w'
        header = not header_written
        
        chunk.to_csv(
            output_file, 
            mode=mode, 
            header=header, 
            index=False, 
            encoding='utf-8'
        )
        header_written = True
        
        # Show progress periodically
        if (i + chunk_size) % 5000 == 0 or i == 0:
            written_so_far = min(i + chunk_size, total_rows)
            print(f"      📦 Written {written_so_far:,} / {total_rows:,} rows")
    
    print(f"   ✅ Complete: {total_rows:,} rows written to {output_file}")


def clean_inspection_name(name: str) -> str:
    """
    Clean the inspection name by extracting everything before the first '/'
    if it starts with a number.
    
    If it starts with a date pattern (DD/MM/YYYY), return empty string.
    
    Examples:
    "2314 Denny Eastern Access Road / 13 Nov 2023 / David Brown" -> "2314 Denny Eastern Access Road"
    "15/02/2024 Denny / 15/02/2024 / David" -> "" (excluded because it starts with date)
    "1234 Some Site / Some Date / Some Person" -> "1234 Some Site"
    "No Number Here" -> "No Number Here" (returns as-is)
    """
    if pd.isna(name):
        return name
    
    name_str = str(name).strip()
    if not name_str:
        return name_str
    
    # Check if it starts with a date pattern (DD/MM/YYYY or D/M/YYYY)
    date_pattern = r'^(\d{1,2}/\d{1,2}/\d{4})'
    if re.match(date_pattern, name_str):
        return ''  # Return empty string to exclude
    
    # Check if it starts with a number
    if re.match(r'^[0-9]', name_str):
        # Split on '/' and take the first part, then strip whitespace
        parts = name_str.split('/')
        if parts:
            return parts[0].strip()
    
    return name_str


def process_join(df: pd.DataFrame, join_spec: Dict, all_dfs: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Perform a left join on the DataFrame using the join specification.
    """
    target_col = join_spec.get("target_column")
    join_tbl = join_spec.get("join_table")
    left_key = join_spec.get("left_key")
    right_key = join_spec.get("right_key")
    return_col = join_spec.get("return_column")
    
    if join_tbl not in all_dfs:
        print(f"      ⚠️ Lookup table {join_tbl} missing! Skipped join for {target_col}.")
        return df
    
    lookup_df = all_dfs[join_tbl]
    
    # Check if keys exist
    if left_key not in df.columns:
        print(f"      ⚠️ Left key {left_key} not found in source table.")
        return df
    
    if right_key not in lookup_df.columns:
        print(f"      ⚠️ Right key {right_key} not found in lookup table.")
        return df
    
    if return_col not in lookup_df.columns:
        print(f"      ⚠️ Return column {return_col} not found in lookup table.")
        return df
    
    # Deduplicate lookup table on the join key
    lookup_df_deduped = lookup_df[[right_key, return_col]].drop_duplicates(subset=[right_key])
    
    # Rename columns for join
    lookup_df_renamed = lookup_df_deduped.rename(columns={
        right_key: '_lkp_join_key',
        return_col: target_col
    })
    
    # Perform left join
    result = df.merge(lookup_df_renamed, left_on=left_key, right_on='_lkp_join_key', how='left')
    result = result.drop('_lkp_join_key', axis=1)
    
    return result


def execute_transformations(config: Dict, toggles: Dict, test_run: bool = False) -> Dict[str, pd.DataFrame]:
    """
    Execute LV2 -> LV3 transformations based on the configuration dict.
    - DROP_TABLE: Table is skipped (not copied to GLD)
    - KEEP_AND_TRANSFORM: Table is copied with ALL columns preserved + joins applied
    - TABLE_TOGGLES: True = process, False = skip
    """
    # 1. Pre-load all tables
    all_dfs = {}
    print("\n📚 [MUSTERING RANKS] Reading SLV tables...")
    for table_name in config.keys():
        # Skip if table is disabled in toggles
        if not toggles.get(table_name, True):
            print(f"   ⏭️ Skipping {table_name} (disabled in TABLE_TOGGLES)")
            continue
            
        input_file = os.path.join(SLV_INPUT_PATH, f"{table_name}.csv")
        try:
            if os.path.exists(input_file):
                # Suppress mixed type warnings by reading all as string
                df = pd.read_csv(input_file, dtype=str, low_memory=False)
                if test_run and not df.empty:
                    df = df.head(10)
                all_dfs[table_name] = df
                print(f"   ✓ Staged {table_name} ({len(df)} rows, {len(df.columns)} columns)")
            else:
                print(f"   ⚠️ Table {table_name} not found in SLV folder.")
                all_dfs[table_name] = pd.DataFrame()
        except Exception as e:
            print(f"   ⚠️ Error reading {table_name}: {e}")
            all_dfs[table_name] = pd.DataFrame()
    
    # 2. Filter tables marked for transformation
    transform_targets = {tbl: cfg for tbl, cfg in config.items() 
                        if cfg.get("status") == "KEEP_AND_TRANSFORM" 
                        and toggles.get(tbl, True)}
    dropped_tables = [tbl for tbl, cfg in config.items() 
                     if cfg.get("status") == "DROP_TABLE"
                     and toggles.get(tbl, True)]
    
    print(f"\n🔥 [PURGING ORCS] Routing {len(dropped_tables)} tables to DROP_TABLE status...")
    for dt in dropped_tables:
        reason = config[dt].get('reason', 'No reason specified')
        print(f"   ❌ Dropped: {dt} ({reason})")
    
    print(f"\n🛡️ [ADVANCING SHIELD-WALL] Transforming {len(transform_targets)} Gold GLD target tables...")
    print("   📋 ALL columns preserved - NO column drops on kept tables")
    
    transformed_results = {}
    
    for table_name, table_cfg in transform_targets.items():
        if table_name not in all_dfs or all_dfs[table_name].empty:
            print(f"\n⚠️ Skipping {table_name}: No data available")
            continue
        
        target_table_name = table_cfg.get("target_table", f"gld_{table_name}")
        
        print(f"\n⚡ Processing: {table_name} ➔ {target_table_name}")
        df = all_dfs[table_name].copy()
        
        print(f"   -> Starting with {len(df.columns)} columns")
        
        # Step A: Apply Joins (NO column drops)
        joins = table_cfg.get("joins", [])
        for join_spec in joins:
            target_col = join_spec.get("target_column")
            join_tbl = join_spec.get("join_table")
            left_k = join_spec.get("left_key")
            
            print(f"   -> Executing Left Join with '{join_tbl}' on {left_k} -> Column: '{target_col}'")
            df = process_join(df, join_spec, all_dfs)
            print(f"   -> After join: {len(df.columns)} columns")
        
        # Step B: Apply fallback for inspections site_name
        if table_name == "audits_search" and target_table_name == "gld_inspections":
            print(f"   -> Applying fallback logic for site_name...")
            if 'site_name' in df.columns and 'name' in df.columns:
                # Create a cleaned name column from the name field
                df['_cleaned_name'] = df['name'].apply(clean_inspection_name)
                
                # Count how many were excluded (returned empty string)
                excluded_count = (df['_cleaned_name'] == '').sum()
                if excluded_count > 0:
                    print(f"      🚫 Excluded {excluded_count} rows that started with a date pattern")
                
                # If site_name is null or empty, use the cleaned name
                df['site_name'] = df['site_name'].fillna(df['_cleaned_name'])
                # If site_name is still empty, use the original name as last resort (but skip empty cleaned names)
                # Only fill with original name if cleaned_name was not empty
                mask = (df['site_name'].isna() | (df['site_name'] == '')) & (df['_cleaned_name'] != '')
                df.loc[mask, 'site_name'] = df.loc[mask, 'name']
                # If site_name is still empty, leave as blank
                # Drop the temporary column
                df = df.drop(columns=['_cleaned_name'])
                print(f"      ✅ Applied fallback: site_name populated from 'name' where missing")
            elif 'site_name' in df.columns and 'name' not in df.columns:
                print(f"      ⚠️ 'name' column not found, cannot apply fallback")
        
        print(f"   -> Final columns: {len(df.columns)} (ALL preserved)")
        
        # Step C: Save to GLD folder with chunked writing for large dataframes
        output_file = os.path.join(GLD_OUTPUT_PATH, f"{target_table_name}.csv")
        
        # Use chunked writing if dataframe has many columns or rows
        # This prevents MemoryError when saving large/wide dataframes
        if len(df.columns) > 500 or len(df) > 100000:
            write_large_dataframe(df, output_file, chunk_size=1000)
        else:
            df.to_csv(output_file, index=False, encoding='utf-8')
            print(f"   ✅ Saved {target_table_name} ({len(df)} rows, {len(df.columns)} columns)")
        
        transformed_results[target_table_name] = df
    
    print("\n🏰 [CAMPAIGN COMPLETE] All GLD tables deployed successfully.")
    return transformed_results


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    transformed_tables = execute_transformations(lv3_transformation_config, TABLE_TOGGLES, TEST_RUN)
    
    print("\n" + "=" * 80)
    print("🏁 TABLE MERGE COMPLETE")
    print("=" * 80)
    print(f"📊 Tables Transformed: {len(transformed_tables)}")
    print(f"📅 Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # Show summary of GLD folder
    print("\n📋 GLD Output Files:")
    print("-" * 70)
    
    for table_name in transformed_tables.keys():
        output_file = os.path.join(GLD_OUTPUT_PATH, f"{table_name}.csv")
        if os.path.exists(output_file):
            size = os.path.getsize(output_file)
            try:
                df = pd.read_csv(output_file)
                print(f"   {table_name:<35} | {len(df):>6} rows | {len(df.columns):>3} cols | {size:>10,} bytes")
            except:
                print(f"   {table_name:<35} | {size:>10,} bytes")
        else:
            print(f"   {table_name:<35} | NOT CREATED")
    
    print("\n📋 Table Status Summary:")
    print("-" * 70)
    for table_name, config in lv3_transformation_config.items():
        status = config.get("status", "UNKNOWN")
        enabled = TABLE_TOGGLES.get(table_name, True)
        if not enabled:
            print(f"   ⏭️ {table_name:<30} | DISABLED (skipped)")
        elif status == "DROP_TABLE":
            print(f"   ❌ {table_name:<30} | DROPPED")
        else:
            target = config.get("target_table", f"gld_{table_name}")
            output_file = os.path.join(GLD_OUTPUT_PATH, f"{target}.csv")
            if os.path.exists(output_file):
                try:
                    df = pd.read_csv(output_file)
                    print(f"   ✅ {table_name:<30} | KEPT -> {target} ({len(df.columns)} columns)")
                except:
                    print(f"   ✅ {table_name:<30} | KEPT -> {target}")
            else:
                print(f"   ⚠️ {table_name:<30} | KEPT but file not found")


if __name__ == "__main__":
    main()