#!/usr/bin/env python
# coding: utf-8

"""
STC JSON Map and Clean - Local Version
Reads CSVs from TNS folder, flattens JSON, outputs to BNZ folder
"""

import json
import os
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

# ============================================================================
# CONFIGURATION
# ============================================================================

# Input folder (where the 3-column CSVs are)
TNS_INPUT_PATH = r"C:\Users\Thomas.Cox\OneDrive - OCU Group\Desktop\00_AST_SystemsIntegration\00_AST_DataUploads\01_STC Safety Culture\Data\TNS"

# Output folder (where flattened CSVs go)
BNZ_OUTPUT_PATH = r"C:\Users\Thomas.Cox\OneDrive - OCU Group\Desktop\00_AST_SystemsIntegration\00_AST_DataUploads\01_STC Safety Culture\Data\BNZ"

# Create output folder if it doesn't exist
os.makedirs(BNZ_OUTPUT_PATH, exist_ok=True)

# ============================================================================
# CONFIGURATION TOGGLES
# ============================================================================

# Test run: True = process only 10 rows per table, False = process all rows
TEST_RUN = False

# Scorched Earth: True = overwrite existing BNZ files, False = append
WIPE_TABLE_DATA = True

# VIP containers that get counter suffixes for duplicate columns
COUNTER_CONTAINERS = ["question_answers", "items"]

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
    "issues_details": True,
    "issues_list": True,                 # Generate flattened issues_list.csv (needed for issues_answers)
    "issues_answers": True,              # Extracted from issues_list
    "schedule_items": True,
    "sites_list": True,
    "site_members": False,
    "templates_feed": True,
    "templates_list": True,
    "users_feed": True,
    "user_groups": True
}

# Special processing toggles
PROCESS_INSPECTIONS_ANSWERS_FLATTENED = True
PROCESS_ISSUES_ANSWERS = True

# ============================================================================
# TABLES TO PROCESS
# ============================================================================

tables = [
    "actions_feed",
    "actions_retrieve",
    "audits_details",
    "audits_search",
    "groups_list",
    "groups_users",
    "incidents_details",
    "incidents_feed",
    "inspections_answers",
    "issues_details",
    "issues_list",
    "issues_answers",
    "schedule_items",
    "sites_list",
    "site_members",
    "templates_feed",
    "templates_list",
    "users_feed",
    "user_groups"
]

print("=" * 80)
print("⚔️  STC JSON MAP AND CLEAN - LOCAL VERSION")
print("=" * 80)
print(f"📁 Input: {TNS_INPUT_PATH}")
print(f"📁 Output: {BNZ_OUTPUT_PATH}")
print(f"🧪 Test Run: {'ON' if TEST_RUN else 'OFF'}")
if TEST_RUN:
    print(f"   📊 Test Limit: 10 rows per table")
print("=" * 80)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def flatten_json_to_dict(obj: Any, prefix: str = '', 
                         counter_containers: List[str] = None,
                         parent_key: str = '') -> Dict[str, Any]:
    """
    Flatten a nested JSON structure into a flat dictionary.
    Handles duplicate column names with counters for VIP containers.
    """
    if counter_containers is None:
        counter_containers = []
    
    result = {}
    
    if isinstance(obj, dict):
        for key, value in obj.items():
            new_key = f"{prefix}_{key}" if prefix else key
            full_path = f"{parent_key}.{key}" if parent_key else key
            
            if isinstance(value, (dict, list)):
                # Check if this is a VIP container
                is_counter_container = any(container.lower() in full_path.lower() 
                                          for container in counter_containers)
                
                if is_counter_container and isinstance(value, list):
                    # For VIP containers, flatten each item with index
                    for idx, item in enumerate(value):
                        if isinstance(item, dict):
                            for sub_key, sub_value in item.items():
                                indexed_key = f"{new_key}_{idx}_{sub_key}"
                                if isinstance(sub_value, (dict, list)):
                                    nested = flatten_json_to_dict(
                                        sub_value, '', counter_containers, 
                                        f"{full_path}_{idx}.{sub_key}"
                                    )
                                    for k, v in nested.items():
                                        result[f"{indexed_key}_{k}"] = v
                                else:
                                    result[indexed_key] = sub_value
                        else:
                            result[f"{new_key}_{idx}"] = item
                else:
                    # Regular nested structure - recurse
                    nested = flatten_json_to_dict(
                        value, new_key, counter_containers, full_path
                    )
                    result.update(nested)
            else:
                # Simple value
                result[new_key] = value
    
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            if isinstance(item, dict):
                nested = flatten_json_to_dict(
                    item, f"{prefix}_{idx}" if prefix else str(idx),
                    counter_containers, f"{parent_key}.{idx}"
                )
                result.update(nested)
            else:
                result[f"{prefix}_{idx}" if prefix else str(idx)] = item
    
    else:
        # Scalar value
        result[prefix or 'value'] = obj
    
    return result


def process_table(table_name: str, test_run: bool = False, 
                  wipe_data: bool = True) -> Tuple[int, int]:
    """
    Process a single table: read CSV, flatten JSON, save to BNZ.
    Returns: (rows_processed, rows_failed)
    """
    input_file = os.path.join(TNS_INPUT_PATH, f"{table_name}.csv")
    output_file = os.path.join(BNZ_OUTPUT_PATH, f"{table_name}.csv")
    
    # Check if input file exists
    if not os.path.exists(input_file):
        return 0, 0
    
    try:
        # Read the CSV
        df = pd.read_csv(input_file)
        
        if df.empty:
            return 0, 0
        
        # Apply test limit
        if test_run:
            df = df.head(10)
        
        # Process each row
        rows_processed = 0
        rows_failed = 0
        all_rows = []
        
        for idx, row in df.iterrows():
            try:
                # Parse the ExactJSON
                exact_json_str = row['ExactJSON']
                
                if isinstance(exact_json_str, str):
                    try:
                        json_data = json.loads(exact_json_str)
                    except json.JSONDecodeError:
                        try:
                            cleaned = exact_json_str.strip('"')
                            json_data = json.loads(cleaned)
                        except:
                            json_data = {}
                else:
                    json_data = {}
                
                # Flatten the JSON
                flattened = flatten_json_to_dict(
                    json_data, 
                    counter_containers=COUNTER_CONTAINERS
                )
                
                # Add metadata columns
                flattened['_ParentID'] = row.get('ParentID', '')
                flattened['_IngestedAt'] = row.get('IngestedAt', '')
                
                all_rows.append(flattened)
                rows_processed += 1
                
            except Exception as e:
                rows_failed += 1
                continue
        
        if not all_rows:
            return rows_processed, rows_failed
        
        # Convert to DataFrame
        df_result = pd.DataFrame(all_rows)
        
        # Sort columns alphabetically for consistency
        df_result = df_result.reindex(sorted(df_result.columns), axis=1)
        
        # Move metadata columns to the front
        cols = df_result.columns.tolist()
        for meta_col in ['_ParentID', '_IngestedAt']:
            if meta_col in cols:
                cols.remove(meta_col)
                cols.insert(0, meta_col)
        df_result = df_result[cols]
        
        # Save to CSV
        if wipe_data or not os.path.exists(output_file):
            df_result.to_csv(output_file, index=False, encoding='utf-8')
        else:
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                df_existing = pd.read_csv(output_file)
                df_combined = pd.concat([df_existing, df_result], ignore_index=True)
                df_combined.to_csv(output_file, index=False, encoding='utf-8')
            else:
                df_result.to_csv(output_file, index=False, encoding='utf-8')
        
        return rows_processed, rows_failed
        
    except Exception as e:
        return 0, 0


# ============================================================================
# SPECIAL PROCESSING: Inspections Answers (Question/Answer extraction)
# ============================================================================

def process_inspections_answers(test_run: bool = False, wipe_data: bool = True) -> Tuple[int, int]:
    """
    Special processing for inspections_answers - extracts question/answer pairs.
    """
    table_name = "inspections_answers"
    input_file = os.path.join(TNS_INPUT_PATH, f"{table_name}.csv")
    output_file = os.path.join(BNZ_OUTPUT_PATH, "inspections_answers_flattened.csv")
    
    if not os.path.exists(input_file):
        return 0, 0
    
    try:
        df = pd.read_csv(input_file)
        
        if df.empty:
            return 0, 0
        
        if test_run:
            df = df.head(10)
        
        all_rows = []
        rows_processed = 0
        
        for idx, row in df.iterrows():
            try:
                exact_json_str = row['ExactJSON']
                
                if isinstance(exact_json_str, str):
                    try:
                        json_data = json.loads(exact_json_str)
                    except:
                        json_data = {}
                else:
                    json_data = {}
                
                parent_id = row.get('ParentID', '')
                ingested_at = row.get('IngestedAt', '')
                
                if isinstance(json_data, list):
                    for item_idx, item in enumerate(json_data):
                        if isinstance(item, dict) and 'question_answers' in item:
                            flattened = flatten_json_to_dict(
                                item,
                                counter_containers=COUNTER_CONTAINERS
                            )
                            flattened['_ParentID'] = parent_id
                            flattened['_IngestedAt'] = ingested_at
                            flattened['_RowIndex'] = idx
                            flattened['_ItemIndex'] = item_idx
                            all_rows.append(flattened)
                        else:
                            flattened = flatten_json_to_dict(
                                item,
                                counter_containers=COUNTER_CONTAINERS
                            )
                            flattened['_ParentID'] = parent_id
                            flattened['_IngestedAt'] = ingested_at
                            flattened['_RowIndex'] = idx
                            flattened['_ItemIndex'] = item_idx
                            all_rows.append(flattened)
                elif isinstance(json_data, dict):
                    if 'question_answers' in json_data:
                        flattened = flatten_json_to_dict(
                            json_data,
                            counter_containers=COUNTER_CONTAINERS
                        )
                        flattened['_ParentID'] = parent_id
                        flattened['_IngestedAt'] = ingested_at
                        all_rows.append(flattened)
                    else:
                        flattened = flatten_json_to_dict(
                            json_data,
                            counter_containers=COUNTER_CONTAINERS
                        )
                        flattened['_ParentID'] = parent_id
                        flattened['_IngestedAt'] = ingested_at
                        all_rows.append(flattened)
                
                rows_processed += 1
                
            except Exception as e:
                continue
        
        if not all_rows:
            return rows_processed, 0
        
        df_result = pd.DataFrame(all_rows)
        
        # Sort columns
        df_result = df_result.reindex(sorted(df_result.columns), axis=1)
        
        # Move metadata columns to front
        cols = df_result.columns.tolist()
        for meta_col in ['_ParentID', '_IngestedAt', '_RowIndex', '_ItemIndex']:
            if meta_col in cols:
                cols.remove(meta_col)
                cols.insert(0, meta_col)
        df_result = df_result[cols]
        
        # Save
        if wipe_data or not os.path.exists(output_file):
            df_result.to_csv(output_file, index=False, encoding='utf-8')
        else:
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                df_existing = pd.read_csv(output_file)
                df_combined = pd.concat([df_existing, df_result], ignore_index=True)
                df_combined.to_csv(output_file, index=False, encoding='utf-8')
            else:
                df_result.to_csv(output_file, index=False, encoding='utf-8')
        
        return rows_processed, 0
        
    except Exception as e:
        return 0, 0


# ============================================================================
# SPECIAL PROCESSING: Issues Answers (Using legacy extraction from issues_list)
# ============================================================================

def process_issues_answers(test_run: bool = False, wipe_data: bool = True) -> Tuple[int, int]:
    """
    Special processing for issues_answers - extracts items_ and question_answers_ columns
    along with task metadata, from the flattened issues_list.csv.
    Saves as issues_answers.csv.
    """
    table_name = "issues_list"
    input_file = os.path.join(BNZ_OUTPUT_PATH, f"{table_name}.csv")
    output_file = os.path.join(BNZ_OUTPUT_PATH, "issues_answers.csv")
    
    if not os.path.exists(input_file):
        return 0, 0
    
    try:
        df = pd.read_csv(input_file)
        
        if df.empty:
            return 0, 0
        
        if test_run:
            df = df.head(10)
        
        # Columns to keep: all items_*, question_answers_*, plus metadata
        metadata_cols = [
            'task_site_name',
            'task_status_id',
            'task_site_area',
            'task_unique_id',
            'task_created_at',
            'task_modified_at',
            'task_occurred_at',
            'task_creator_firstname',
            'task_creator_lastname',
            'task_creator_user_id',
            'category_key'
        ]
        
        # Find all columns starting with 'items_' or 'question_answers_'
        item_cols = [col for col in df.columns if col.startswith('items_')]
        qa_cols = [col for col in df.columns if col.startswith('question_answers_')]
        
        # Also include the metadata columns (only those that exist)
        existing_metadata = [col for col in metadata_cols if col in df.columns]
        
        # Combine all desired columns
        desired_cols = item_cols + qa_cols + existing_metadata
        
        if not desired_cols:
            return 0, 0
        
        # Select only those columns
        df_result = df[desired_cols].copy()
        
        # Save
        if wipe_data or not os.path.exists(output_file):
            df_result.to_csv(output_file, index=False, encoding='utf-8')
        else:
            if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                df_existing = pd.read_csv(output_file)
                df_combined = pd.concat([df_existing, df_result], ignore_index=True)
                df_combined.to_csv(output_file, index=False, encoding='utf-8')
            else:
                df_result.to_csv(output_file, index=False, encoding='utf-8')
        
        return len(df_result), 0
        
    except Exception as e:
        return 0, 0


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    total_processed = 0
    total_failed = 0
    tables_processed = 0
    tables_skipped = 0
    
    print("\n⚔️ [STARTING PROCESSING]")
    print("=" * 80)
    
    # Process all tables (check toggles)
    for table in tables:
        if not TABLE_TOGGLES.get(table, False):
            tables_skipped += 1
            continue
        
        tables_processed += 1
        processed, failed = process_table(
            table, 
            test_run=TEST_RUN, 
            wipe_data=WIPE_TABLE_DATA
        )
        total_processed += processed
        total_failed += failed
    
    # Special processing for inspections_answers
    if PROCESS_INSPECTIONS_ANSWERS_FLATTENED and TABLE_TOGGLES.get("inspections_answers", False):
        processed, failed = process_inspections_answers(
            test_run=TEST_RUN,
            wipe_data=WIPE_TABLE_DATA
        )
        total_processed += processed
        total_failed += failed
    
    # Special processing for issues_answers (using legacy extraction from issues_list)
    if PROCESS_ISSUES_ANSWERS and TABLE_TOGGLES.get("issues_list", False):
        processed, failed = process_issues_answers(
            test_run=TEST_RUN,
            wipe_data=WIPE_TABLE_DATA
        )
        total_processed += processed
        total_failed += failed
    
    print("\n" + "=" * 80)
    print("🏁 GRAND CAMPAIGN COMPLETE")
    print("=" * 80)
    print(f"📊 Tables Processed: {tables_processed}")
    print(f"⏭️ Tables Skipped: {tables_skipped}")
    print(f"📊 Total Rows Processed: {total_processed:,}")
    if total_failed > 0:
        print(f"   ❌ Failed: {total_failed:,}")
    print(f"📅 Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)


if __name__ == "__main__":
    main()