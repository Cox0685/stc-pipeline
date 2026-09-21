#!/usr/bin/env python
# coding: utf-8

"""
STC Data Clean - Azure Version
Reads from the BNZ tier in ADLS, cleans/standardizes data, writes to the SLV tier.
"""

import os
import sys
import json
import pandas as pd
import re
import warnings
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_shared"))
import azure_io

# Suppress pandas DtypeWarnings
warnings.filterwarnings('ignore', category=pd.errors.DtypeWarning)

# ============================================================================
# CONFIGURATION
# ============================================================================

BNZ_PREFIX = "BNZ"
SLV_PREFIX = "SLV"

client = azure_io.get_client()

# ============================================================================
# CONFIGURATION TOGGLES
# ============================================================================

# Test run: True = process only 10 rows per table, False = process all rows
TEST_RUN = False

# ============================================================================
# TABLES TO PROCESS (LV1 -> LV2 mapping)
# ============================================================================

# Table toggles: True = process this table, False = skip it
TABLE_TOGGLES = {
    "actions_feed": True,
    "actions_retrieve": True,
    "audits_details": True,
    "audits_search": True,
    "groups_list": True,
    "groups_users": True,
    "headsup_list": True,
    "headsup_users": True,
    "incidents_details": True,
    "incidents_feed": True,
    "inspections_answers": True,
    "inspections_answers_flattened": True,
    "issues_details": True,
    "issues_list": True,
    "issues_answers": True,
    "schedule_items": True,
    "site_members": True,
    "sites_list": True,
    "templates_feed": True,
    "templates_list": True,
    "user_groups": True,
    "users_feed": True
}

# Runtime override from STC Pipeline Runner.py (optional) - see the matching
# block in STC JSON Map and Clean.py for the full explanation. Falls back to
# TABLE_TOGGLES as written when run standalone.
_table_overrides_raw = os.environ.get("TABLE_ENABLED_OVERRIDES")
if _table_overrides_raw:
    try:
        _table_overrides = json.loads(_table_overrides_raw)
        _applied = 0
        _unmatched = []
        for _table_name, _enabled in _table_overrides.items():
            if _table_name in TABLE_TOGGLES:
                TABLE_TOGGLES[_table_name] = _enabled
                _applied += 1
            else:
                _unmatched.append(_table_name)
        print(f"🔧 Applied {_applied} table toggle override(s) from Pipeline Runner")
        if _unmatched:
            print(f"   ℹ️ {len(_unmatched)} override(s) had no matching key here (fine if this "
                  f"stage doesn't produce that table): {_unmatched}")
    except Exception as e:
        print(f"⚠️ Could not parse TABLE_ENABLED_OVERRIDES - ignoring, using TABLE_TOGGLES as written: {e}")

# Deduplication toggles: True = deduplicate this table, False = skip deduplication
DEDUPE_TOGGLES = {
    "actions_feed": True,
    "actions_retrieve": True,
    "audits_details": True,
    "audits_search": True,
    "groups_list": True,
    "groups_users": True,
    "headsup_list": True,
    "headsup_users": True,
    "incidents_details": True,
    "incidents_feed": True,
    "inspections_answers": True,
    "inspections_answers_flattened": True,
    "issues_details": True,
    "issues_list": True,
    "issues_answers": True,  # Deduplication disabled for issues_answers
    "schedule_items": True,
    "site_members": True,
    "sites_list": True,
    "templates_feed": True,
    "templates_list": True,
    "user_groups": True,
    "users_feed": True
}

# Mapping of source tables (in BNZ) to target tables (in SLV)
TABLE_MAPPING = {
    "actions_feed": "actions_feed",
    "actions_retrieve": "actions_retrieve",
    "audits_details": "audits_details",
    "audits_search": "audits_search",
    "groups_list": "groups_list",
    "groups_users": "groups_users",
    "headsup_list": "headsup_list",
    "headsup_users": "headsup_users",
    "incidents_details": "incidents_details",
    "incidents_feed": "incidents_feed",
    "inspections_answers": "inspections_answers",
    "inspections_answers_flattened": "inspections_answers_flattened",
    "issues_details": "issues_details",
    "issues_list": "issues_list",
    "issues_answers": "issues_answers",
    "schedule_items": "schedule_items",
    "site_members": "site_members",
    "sites_list": "sites_list",
    "templates_feed": "templates_feed",
    "templates_list": "templates_list",
    "user_groups": "user_groups",
    "users_feed": "users_feed"
}

# ============================================================================
# DEDUPLICATION CONFIGURATION
# ============================================================================

# headsup_list / headsup_users column names confirmed directly (not guessed):
# headsup_list   -> sort by published_at, dedupe on id
# headsup_users  -> sort by _IngestedAt, dedupe on _ParentID + id
dedupe_config = {
    "actions_feed":             {"sort": "modified_at",      "dedupe": ["unique_id"]},
    "actions_retrieve":         {"sort": "task_modified_at", "dedupe": ["task_unique_id"]},
    "audits_details":           {"sort": "modified_at",      "dedupe": ["id"]},
    "audits_search":            {"sort": "date_modified",    "dedupe": ["id"]},
    "groups_list":              {"sort": "_IngestedAt",      "dedupe": ["id"]},
    "groups_users":             {"sort": "_IngestedAt",      "dedupe": ["_ParentID", "user_id"]},
    "headsup_list":              {"sort": "published_at",     "dedupe": ["id"]},
    "headsup_users":             {"sort": "_IngestedAt",      "dedupe": ["_ParentID", "id"]},
    "incidents_details":        {"sort": "modified_at",      "dedupe": ["investigation_id"]},
    "incidents_feed":           {"sort": "modified_at",      "dedupe": ["investigation_id"]},
    "inspections_answers":      {"sort": "_IngestedAt",      "dedupe": ["_ParentID", "result_question_id"]},
    "inspections_answers_flattened": {"sort": "_IngestedAt", "dedupe": ["_ParentID", "question_id"]},
    "issues_details":           {"sort": "task_modified_at", "dedupe": ["task_unique_id"]},
    "issues_list":              {"sort": "task_modified_at", "dedupe": ["task_unique_id"]},
    "issues_answers":           {"sort": "task_modified_at", "dedupe": ["task_unique_id"]},
    "schedule_items":           {"sort": "modified_at",      "dedupe": ["id"]},
    "site_members":             {"sort": "modified_at",      "dedupe": ["site_id", "member_id"]},
    "sites_list":               {"sort": "_IngestedAt",      "dedupe": ["site_uuid"]},
    "templates_feed":           {"sort": "modified_at",      "dedupe": ["id"]},
    "templates_list":           {"sort": "modified_at",      "dedupe": ["id"]},
    "user_groups":              {"sort": "_IngestedAt",      "dedupe": ["id"]},
    "users_feed":               {"sort": "_IngestedAt",      "dedupe": ["id"]}
}

print("=" * 80)
print("⚔️  STC DATA CLEAN - LOCAL VERSION")
print("=" * 80)
print(f"📁 Input (BNZ): ADLS/{BNZ_PREFIX}")
print(f"📁 Output (SLV): ADLS/{SLV_PREFIX}")
print(f"🧪 Test Run: {'ON' if TEST_RUN else 'OFF'}")
if TEST_RUN:
    print(f"   📊 Test Limit: 10 rows per table")
print("=" * 80)

# Show which tables are enabled/disabled
print("\n📋 TABLE STATUS:")
enabled_count = 0
disabled_count = 0
for table_name, enabled in TABLE_TOGGLES.items():
    if enabled:
        enabled_count += 1
        dedupe_status = "ON" if DEDUPE_TOGGLES.get(table_name, True) else "OFF"
        print(f"   ✅ ENABLED - {table_name} (Dedupe: {dedupe_status})")
    else:
        disabled_count += 1
        print(f"   ❌ DISABLED - {table_name}")
print(f"\n   📊 {enabled_count} tables enabled, {disabled_count} tables disabled")
print("=" * 80)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def sanitize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize ID columns:
    1. Removes any prefix ending with '_' (e.g., 'audit_', 'task_', 'user_').
    2. Strips all hyphens, braces, quotes, and whitespace/tabs.
    3. Converts to lowercase.
    4. Normalizes ISO dates.
    """
    if df.empty:
        return df

    ISO_DATE_REGEX = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}'

    def clean_cell(val):
        # Convert to string and strip whitespace/tabs
        if val is None or pd.isna(val):
            return val
            
        s = str(val).strip()
        if not s:
            return val

        # 1. Handle ISO Date normalization first
        if re.match(ISO_DATE_REGEX, s):
            try:
                dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                return s

        # 2. Lop off any prefix ending in '_' (e.g., audit_, task_, user_audit_)
        # Look for '_' and check if what follows looks like an ID
        if '_' in s:
            parts = s.split('_')
            # Take the last part after the last underscore
            candidate = parts[-1]
            # If the candidate looks like a UUID (32-36 chars with or without hyphens)
            cand_clean = candidate.replace('-', '').replace('{', '').replace('}', '')
            if len(cand_clean) == 32:
                s = candidate

        # 3. Strip hyphens, braces, double/single quotes, and lowercase
        clean_id = s.replace('-', '').replace('{', '').replace('}', '').replace('"', '').replace("'", '').strip().lower()

        # 4. If it cleans down to a standard 32-character ID, return the clean version
        if len(clean_id) == 32:
            return clean_id

        # Otherwise return trimmed original string
        return s

    # Forcefully apply to ALL non-numeric columns without checking dtype strictness
    for col in df.columns:
        df[col] = df[col].apply(clean_cell)

    return df

def deduplicate_table(df: pd.DataFrame, sort_col: str, dedupe_cols: List[str]) -> pd.DataFrame:
    """
    Deduplicate a DataFrame keeping the row with the latest sort_col value.
    """
    if df.empty:
        return df
    
    # Check if sort column exists
    if sort_col not in df.columns:
        # Try alternative sort columns
        alt_cols = ['_IngestedAt', 'answered_at_combined']
        for alt in alt_cols:
            if alt in df.columns:
                sort_col = alt
                break
        else:
            print(f"      ⚠️ Sort column not found, keeping all rows")
            return df
    
    # Check if dedupe columns exist
    valid_dedupe_cols = [col for col in dedupe_cols if col in df.columns]
    if not valid_dedupe_cols:
        print(f"      ⚠️ No valid dedupe columns found, keeping all rows")
        return df
    
    # Convert sort column to datetime for proper ordering
    try:
        df[sort_col] = pd.to_datetime(df[sort_col], errors='coerce')
    except:
        pass
    
    # Sort by the sort column descending and drop duplicates
    df_sorted = df.sort_values(sort_col, ascending=False)
    df_deduped = df_sorted.drop_duplicates(subset=valid_dedupe_cols, keep='first')
    
    # Sort back to original order
    df_deduped = df_deduped.sort_index()
    
    return df_deduped


def process_table(source_name: str, target_name: str, test_run: bool = False) -> Tuple[int, int]:
    """
    Process a single table: read from BNZ, clean, deduplicate, save to SLV.
    Returns: (rows_processed, rows_failed)
    """
    input_file = f"{BNZ_PREFIX}/{source_name}.csv"
    output_file = f"{SLV_PREFIX}/{target_name}.csv"
    
    print(f"\n📋 Processing: {source_name} -> {target_name}")
    
    # Check if input file exists
    if not client.exists(input_file):
        print(f"   ⚠️ Input file not found: {input_file}")
        return 0, 0
    
    try:
        # Read the CSV - read all as string to avoid DtypeWarnings
        df = client.read_csv(input_file, dtype=str, low_memory=False)
        
        if df.empty:
            print(f"   ⚠️ No data in {source_name}")
            return 0, 0
        
        initial_count = len(df)
        print(f"   📊 Initial rows: {initial_count}")
        
        # Apply test limit
        if test_run:
            df = df.head(10)
            print(f"   🧪 TEST MODE: Processing {len(df)} rows")
        
        # ============================================================
        # SPECIAL PRE-PROCESSING: issues_answers coalesce answered_at
        # ============================================================
        if source_name == "issues_answers":
            print(f"   🔄 Coalescing answered_at from answer_set_0 to answer_set_5...")
            
            # Find all answered_at columns
            answered_cols = []
            for i in range(6):
                col = f"answer_set_{i}_answered_at"
                if col in df.columns:
                    answered_cols.append(col)
            
            if answered_cols:
                # Create combined column with first non-null value
                df['answered_at_combined'] = df[answered_cols].bfill(axis=1).iloc[:, 0]
                print(f"      ✅ Created answered_at_combined from {len(answered_cols)} answer sets")
            else:
                print(f"      ⚠️ No answer_set_X_answered_at columns found")
        
        # Step 1: Sanitize/standardize columns
        print(f"   🔧 Standardizing columns...")
        df_cleaned = sanitize_columns(df)
        
        # Step 2: Deduplicate if enabled in DEDUPE_TOGGLES
        deduped_count = len(df_cleaned)
        if DEDUPE_TOGGLES.get(source_name, True):
            if source_name in dedupe_config:
                config = dedupe_config[source_name]
                sort_col = config["sort"]
                dedupe_cols = config["dedupe"]
                
                # For issues_answers, use the combined column if it exists
                if source_name == "issues_answers" and 'answered_at_combined' in df_cleaned.columns:
                    sort_col = 'answered_at_combined'
                    print(f"   🗑️ Using 'answered_at_combined' as sort column")
                
                print(f"   🗑️ Deduplicating by: {dedupe_cols} (sort: {sort_col})")
                df_deduped = deduplicate_table(df_cleaned, sort_col, dedupe_cols)
                deduped_count = len(df_deduped)
                purged = len(df_cleaned) - deduped_count
                if purged > 0:
                    print(f"   🗑️ Purged {purged} duplicate rows")
            else:
                df_deduped = df_cleaned
                print(f"   ℹ️ No dedupe config for {source_name}, keeping all rows")
        else:
            df_deduped = df_cleaned
            print(f"   ℹ️ Deduplication disabled for {source_name} (via DEDUPE_TOGGLES)")
        
        # Save to SLV
        client.write_csv(df_deduped, output_file, index=False, encoding='utf-8')
        print(f"   ✅ Saved {deduped_count} rows to SLV")
        
        return deduped_count, 0
        
    except Exception as e:
        print(f"   ❌ Failed to process {source_name}: {e}")
        import traceback
        traceback.print_exc()
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
    
    for source_name, target_name in TABLE_MAPPING.items():
        # Check if this table is enabled
        if not TABLE_TOGGLES.get(source_name, False):
            print(f"\n⏭️ Skipping: {source_name} (disabled in TABLE_TOGGLES)")
            tables_skipped += 1
            continue
        
        tables_processed += 1
        processed, failed = process_table(
            source_name, 
            target_name,
            test_run=TEST_RUN
        )
        total_processed += processed
        total_failed += failed
    
    print("\n" + "=" * 80)
    print("🏁 DATA CLEAN COMPLETE")
    print("=" * 80)
    print(f"📊 Tables Processed: {tables_processed}")
    print(f"⏭️ Tables Skipped: {tables_skipped}")
    print(f"📊 Total Rows Processed: {total_processed}")
    if total_failed > 0:
        print(f"   ❌ Failed: {total_failed}")
    print(f"📅 Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)


if __name__ == "__main__":
    main()