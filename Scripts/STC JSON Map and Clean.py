#!/usr/bin/env python
# coding: utf-8

"""
STC JSON Map and Clean - Local Version (Optimized)
Reads CSVs from TNS folder, flattens JSON, outputs to BNZ folder
"""

import json
import os
import sys
import gc
import time
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_shared"))
import azure_io

# Increase recursion limit for deeply nested JSON
sys.setrecursionlimit(10000)

# ============================================================================
# CONFIGURATION
# ============================================================================

# Data lake folder names (was a local OneDrive path) - both live inside the
# same ADLS Gen2 filesystem, ADLS_FILESYSTEM env var
TNS_INPUT_PATH = "TNS"
BNZ_OUTPUT_PATH = "BNZ"

_adls = azure_io.get_client()

# ============================================================================
# CONFIGURATION TOGGLES
# ============================================================================

# Test run: True = process only X rows per table, False = process all rows
TEST_RUN = False
TEST_LIMIT = 100

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
    "issues_list": True,
    "issues_answers": True,
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
print("⚔️  STC JSON MAP AND CLEAN - LOCAL VERSION (OPTIMIZED)")
print("=" * 80)
print(f"📁 Input: {TNS_INPUT_PATH}")
print(f"📁 Output: {BNZ_OUTPUT_PATH}")
print(f"🧪 Test Run: {'ON' if TEST_RUN else 'OFF'}")
if TEST_RUN:
    print(f"   📊 Test Limit: {TEST_LIMIT} rows per table")
print("=" * 80)

# ============================================================================
# OPTIMIZED FLATTEN FUNCTION
# ============================================================================

def flatten_json_to_dict(obj: Any, prefix: str = '', 
                         counter_containers: List[str] = None,
                         parent_key: str = '') -> Dict[str, Any]:
    """
    Optimized flatten function - faster recursion with less overhead.
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


# ============================================================================
# OPTIMIZED TABLE PROCESSING
# ============================================================================

def process_table(table_name: str, test_run: bool = False, 
                  wipe_data: bool = True) -> Tuple[int, int, float]:
    """
    Process a single table: read CSV, flatten JSON, save to BNZ.
    Returns: (rows_processed, rows_failed, time_taken)
    """
    start_time = time.time()
    
    input_file = f"{TNS_INPUT_PATH}/{table_name}.csv"
    output_file = f"{BNZ_OUTPUT_PATH}/{table_name}.csv"
    
    print(f"\n{'='*80}")
    print(f"📋 PROCESSING: {table_name}")
    print(f"{'='*80}")
    
    # Check if input file exists
    if not _adls.exists(input_file):
        print(f"   ⚠️ Input file not found: {input_file}")
        return 0, 0, 0
    
    try:
        # Read the CSV
        print(f"   📂 Reading CSV...")
        df = _adls.read_csv(input_file)
        total_rows = len(df)
        print(f"   ✅ Loaded {total_rows:,} rows")
        
        if df.empty:
            return 0, 0, 0
        
        # Apply test limit
        if test_run:
            df = df.head(TEST_LIMIT)
            print(f"   🧪 TEST MODE: Processing {len(df)} rows")
        
        # Process each row
        rows_processed = 0
        rows_failed = 0
        all_rows = []
        
        # Show progress every 10% or every 1000 rows
        progress_interval = max(1, len(df) // 10) if len(df) > 100 else 10
        if progress_interval > 1000:
            progress_interval = 1000
        
        print(f"   🔄 Processing {len(df):,} rows...")
        
        for idx, row in df.iterrows():
            # Progress indicator
            if idx % progress_interval == 0 and idx > 0:
                percent = (idx / len(df)) * 100
                print(f"      ⏳ Progress: {percent:.0f}% ({idx:,}/{len(df):,} rows)")
            
            try:
                # Parse the ExactJSON
                exact_json_str = row['ExactJSON']
                
                if isinstance(exact_json_str, str):
                    try:
                        json_data = json.loads(exact_json_str)
                    except json.JSONDecodeError:
                        # Try cleaning the string
                        try:
                            cleaned = exact_json_str.strip('"').replace('""', '"')
                            json_data = json.loads(cleaned)
                        except:
                            json_data = {}
                else:
                    json_data = {}
                
                # Flatten the JSON - use optimized function
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
                if rows_failed <= 5:  # Only show first 5 errors
                    print(f"      ⚠️ Error on row {idx}: {str(e)[:100]}")
                continue
        
        print(f"   📊 Processing complete: {rows_processed:,} rows, {rows_failed} failed")
        
        if not all_rows:
            print(f"   ⚠️ No rows successfully processed")
            return rows_processed, rows_failed, time.time() - start_time
        
        print(f"   🗂️ Building DataFrame ({len(all_rows):,} rows)...")
        df_result = pd.DataFrame(all_rows)
        
        # Clear memory
        all_rows = None
        gc.collect()
        
        # Sort columns alphabetically for consistency
        print(f"   🗂️ Sorting columns...")
        df_result = df_result.reindex(sorted(df_result.columns), axis=1)
        
        # Move metadata columns to the front
        cols = df_result.columns.tolist()
        for meta_col in ['_ParentID', '_IngestedAt']:
            if meta_col in cols:
                cols.remove(meta_col)
                cols.insert(0, meta_col)
        df_result = df_result[cols]
        
        print(f"   💾 Saving to CSV ({len(df_result.columns)} columns)...")
        if wipe_data or not _adls.exists(output_file):
            _adls.write_csv(df_result, output_file, index=False, encoding='utf-8')
        else:
            df_existing = _adls.read_csv(output_file)
            df_combined = pd.concat([df_existing, df_result], ignore_index=True)
            _adls.write_csv(df_combined, output_file, index=False, encoding='utf-8')
            df_existing = None
            df_combined = None
        
        # Clear memory
        df_result = None
        df = None
        gc.collect()
        
        elapsed = time.time() - start_time
        print(f"   ✅ Completed in {elapsed:.2f} seconds")
        print(f"   📊 Saved {rows_processed:,} rows to {output_file}")
        return rows_processed, rows_failed, elapsed
        
    except MemoryError:
        print(f"   ❌ MEMORY ERROR: {table_name} is too large to process at once")
        print(f"   💡 Try setting TEST_RUN=True or splitting the file")
        return 0, 0, time.time() - start_time
    except Exception as e:
        print(f"   ❌ Error processing {table_name}: {e}")
        import traceback
        traceback.print_exc()
        return 0, 0, time.time() - start_time


# ============================================================================
# SPECIAL PROCESSING: Inspections Answers (Question/Answer extraction)
# ============================================================================

def process_inspections_answers(test_run: bool = False, wipe_data: bool = True) -> Tuple[int, int, float]:
    """
    Special processing for inspections_answers - extracts question/answer pairs.
    """
    start_time = time.time()
    table_name = "inspections_answers"
    input_file = f"{TNS_INPUT_PATH}/{table_name}.csv"
    output_file = f"{BNZ_OUTPUT_PATH}/inspections_answers_flattened.csv"
    
    print(f"\n{'='*80}")
    print(f"📋 SPECIAL PROCESSING: {table_name} (Question/Answer extraction)")
    print(f"{'='*80}")
    
    if not _adls.exists(input_file):
        print(f"   ⚠️ Input file not found: {input_file}")
        return 0, 0, 0
    
    try:
        df = _adls.read_csv(input_file)
        total_rows = len(df)
        print(f"   ✅ Loaded {total_rows:,} rows")
        
        if df.empty:
            return 0, 0, 0
        
        if test_run:
            df = df.head(TEST_LIMIT)
            print(f"   🧪 TEST MODE: Processing {len(df)} rows")
        
        all_rows = []
        rows_processed = 0
        progress_interval = max(1, len(df) // 10) if len(df) > 100 else 10
        if progress_interval > 1000:
            progress_interval = 1000
        
        print(f"   🔄 Processing {len(df):,} rows...")
        
        for idx, row in df.iterrows():
            if idx % progress_interval == 0 and idx > 0:
                percent = (idx / len(df)) * 100
                print(f"      ⏳ Progress: {percent:.0f}% ({idx:,}/{len(df):,} rows)")
            
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
                        if isinstance(item, dict):
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
            print(f"   ⚠️ No rows successfully processed")
            return rows_processed, 0, time.time() - start_time
        
        print(f"   🗂️ Building DataFrame ({len(all_rows):,} rows)...")
        df_result = pd.DataFrame(all_rows)
        all_rows = None
        gc.collect()
        
        # Sort columns
        df_result = df_result.reindex(sorted(df_result.columns), axis=1)
        
        # Move metadata columns to front
        cols = df_result.columns.tolist()
        for meta_col in ['_ParentID', '_IngestedAt', '_RowIndex', '_ItemIndex']:
            if meta_col in cols:
                cols.remove(meta_col)
                cols.insert(0, meta_col)
        df_result = df_result[cols]
        
        print(f"   💾 Saving to CSV ({len(df_result.columns)} columns)...")
        if wipe_data or not _adls.exists(output_file):
            _adls.write_csv(df_result, output_file, index=False, encoding='utf-8')
        else:
            df_existing = _adls.read_csv(output_file)
            df_combined = pd.concat([df_existing, df_result], ignore_index=True)
            _adls.write_csv(df_combined, output_file, index=False, encoding='utf-8')
        
        df_result = None
        df = None
        gc.collect()
        
        elapsed = time.time() - start_time
        print(f"   ✅ Completed in {elapsed:.2f} seconds")
        print(f"   📊 Saved {rows_processed:,} rows to {output_file}")
        return rows_processed, 0, elapsed
        
    except MemoryError:
        print(f"   ❌ MEMORY ERROR: {table_name} is too large")
        return 0, 0, time.time() - start_time
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return 0, 0, time.time() - start_time


# ============================================================================
# SPECIAL PROCESSING: Issues Answers
# ============================================================================

def process_issues_answers(test_run: bool = False, wipe_data: bool = True) -> Tuple[int, int, float]:
    """
    Special processing for issues_answers - extracts items_ and question_answers_ columns
    from the flattened issues_list.csv.
    """
    start_time = time.time()
    table_name = "issues_list"
    input_file = f"{BNZ_OUTPUT_PATH}/{table_name}.csv"
    output_file = f"{BNZ_OUTPUT_PATH}/issues_answers.csv"
    
    print(f"\n{'='*80}")
    print(f"📋 SPECIAL PROCESSING: Issues Answers (from {table_name})")
    print(f"{'='*80}")
    
    if not _adls.exists(input_file):
        print(f"   ⚠️ Input file not found: {input_file}")
        return 0, 0, 0
    
    try:
        df = _adls.read_csv(input_file)
        total_rows = len(df)
        print(f"   ✅ Loaded {total_rows:,} rows")
        
        if df.empty:
            return 0, 0, 0
        
        if test_run:
            df = df.head(TEST_LIMIT)
            print(f"   🧪 TEST MODE: Processing {len(df)} rows")
        
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
            print(f"   ⚠️ No relevant columns found")
            return 0, 0, 0
        
        print(f"   📋 Found {len(item_cols)} item columns, {len(qa_cols)} question_answers columns")
        print(f"   📋 Found {len(existing_metadata)} metadata columns")
        
        # Select only those columns
        df_result = df[desired_cols].copy()
        
        print(f"   💾 Saving to CSV ({len(df_result.columns)} columns)...")
        if wipe_data or not _adls.exists(output_file):
            _adls.write_csv(df_result, output_file, index=False, encoding='utf-8')
        else:
            df_existing = _adls.read_csv(output_file)
            df_combined = pd.concat([df_existing, df_result], ignore_index=True)
            _adls.write_csv(df_combined, output_file, index=False, encoding='utf-8')
        
        elapsed = time.time() - start_time
        print(f"   ✅ Completed in {elapsed:.2f} seconds")
        print(f"   📊 Saved {len(df_result):,} rows to {output_file}")
        return len(df_result), 0, elapsed
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return 0, 0, time.time() - start_time


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    start_time = time.time()
    total_processed = 0
    total_failed = 0
    tables_processed = 0
    tables_skipped = 0
    total_time = 0
    
    print("\n⚔️ [STARTING PROCESSING]")
    print("=" * 80)
    
    # Process all tables (check toggles)
    for table in tables:
        if not TABLE_TOGGLES.get(table, False):
            tables_skipped += 1
            print(f"\n⏭️ SKIPPED: {table} (disabled)")
            continue
        
        tables_processed += 1
        processed, failed, elapsed = process_table(
            table, 
            test_run=TEST_RUN, 
            wipe_data=WIPE_TABLE_DATA
        )
        total_processed += processed
        total_failed += failed
        total_time += elapsed
        
        # Force garbage collection after each table
        gc.collect()
    
    # Special processing for inspections_answers
    if PROCESS_INSPECTIONS_ANSWERS_FLATTENED and TABLE_TOGGLES.get("inspections_answers", False):
        processed, failed, elapsed = process_inspections_answers(
            test_run=TEST_RUN,
            wipe_data=WIPE_TABLE_DATA
        )
        total_processed += processed
        total_failed += failed
        total_time += elapsed
        gc.collect()
    
    # Special processing for issues_answers
    if PROCESS_ISSUES_ANSWERS and TABLE_TOGGLES.get("issues_list", False):
        processed, failed, elapsed = process_issues_answers(
            test_run=TEST_RUN,
            wipe_data=WIPE_TABLE_DATA
        )
        total_processed += processed
        total_failed += failed
        total_time += elapsed
        gc.collect()
    
    print("\n" + "=" * 80)
    print("🏁 GRAND CAMPAIGN COMPLETE")
    print("=" * 80)
    print(f"📊 Tables Processed: {tables_processed}")
    print(f"⏭️ Tables Skipped: {tables_skipped}")
    print(f"📊 Total Rows Processed: {total_processed:,}")
    if total_failed > 0:
        print(f"   ❌ Failed: {total_failed:,}")
    print(f"⏱️ Total Time: {total_time:.2f} seconds")
    if total_time > 60:
        print(f"   ({total_time/60:.2f} minutes)")
    print(f"📅 Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)


if __name__ == "__main__":
    main()