#!/usr/bin/env python
# coding: utf-8

"""
Stack Issues Answers - Local Version (WITH OPTION TO SKIP STACKING)
Reads issues_answers.csv from SLV, optionally stacks answer sets, joins with issues_details, outputs to GLD
"""

import os
import pandas as pd
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

# ============================================================================
# CONFIGURATION
# ============================================================================

SLV_INPUT_PATH = r"C:\Users\Thomas.Cox\OneDrive - OCU Group\Desktop\00_AST_SystemsIntegration\00_AST_DataUploads\01_STC Safety Culture\Data\SLV"
GLD_OUTPUT_PATH = r"C:\Users\Thomas.Cox\OneDrive - OCU Group\Desktop\00_AST_SystemsIntegration\00_AST_DataUploads\01_STC Safety Culture\Data\GLD"

# Create output folder if it doesn't exist
os.makedirs(GLD_OUTPUT_PATH, exist_ok=True)

# ============================================================================
# CONFIGURATION TOGGLES
# ============================================================================

# Test run: True = process only 10 rows per table, False = process all rows
TEST_RUN = False

# If True, skip the answer stacking (keep original rows, coalesce answers across sets)
# If False, perform full stacking (one row per answer set)
SKIP_STACKING = False  # <-- SET TO True FOR TESTING

# If True, keep rows for empty answer sets (with empty values). If False, skip them.
KEEP_EMPTY_ANSWER_SETS = True

# If True, after stacking, keep only the most recent answer per (_ParentID, question_id)
# based on 'answered_at' (or answer_set_number as fallback).
KEEP_ONLY_NEWEST_ANSWER = True

print("=" * 80)
print("⚔️  STACK ISSUES ANSWERS - LOCAL VERSION")
print("=" * 80)
print(f"📁 Input (SLV): {SLV_INPUT_PATH}")
print(f"📁 Output (GLD): {GLD_OUTPUT_PATH}")
print(f"🧪 Test Run: {'ON' if TEST_RUN else 'OFF'}")
print(f"⏭️  Skip Stacking: {'ON' if SKIP_STACKING else 'OFF'}")
if not SKIP_STACKING:
    print(f"📦 Keep Empty Answer Sets: {'ON' if KEEP_EMPTY_ANSWER_SETS else 'OFF'}")
    print(f"🔄 Keep Only Newest Answer: {'ON' if KEEP_ONLY_NEWEST_ANSWER else 'OFF'}")
print("=" * 80)

# ============================================================================
# MAIN PROCESSING
# ============================================================================

def main():
    # Input files
    issues_answers_file = os.path.join(SLV_INPUT_PATH, "issues_answers.csv")
    issues_details_file = os.path.join(SLV_INPUT_PATH, "issues_details.csv")
    output_file = os.path.join(GLD_OUTPUT_PATH, "gld_issues_answers.csv")
    
    if not os.path.exists(issues_answers_file):
        print(f"❌ issues_answers file not found: {issues_answers_file}")
        return
    
    if not os.path.exists(issues_details_file):
        print(f"❌ issues_details file not found: {issues_details_file}")
        return
    
    print(f"\n📂 Reading: {os.path.basename(issues_answers_file)}")
    
    try:
        # ====================================================================
        # STEP 1: Read issues_answers
        # ====================================================================
        df_answers = pd.read_csv(issues_answers_file, dtype=str, low_memory=False)
        print(f"   ✅ Loaded {len(df_answers):,} rows from issues_answers")
        print(f"   📋 Columns: {len(df_answers.columns)}")
        
        if TEST_RUN:
            df_answers = df_answers.head(10)
            print(f"   🧪 TEST MODE: Processing {len(df_answers)} rows")
        
        # ====================================================================
        # STEP 2: Read issues_details
        # ====================================================================
        print(f"\n📂 Reading: {os.path.basename(issues_details_file)}")
        df_details = pd.read_csv(issues_details_file, dtype=str, low_memory=False)
        print(f"   ✅ Loaded {len(df_details):,} rows from issues_details")
        
        # ====================================================================
        # STEP 3: Stack the answer sets (or skip)
        # ====================================================================
        
        if SKIP_STACKING:
            print("\n⏭️ Skipping answer stacking. Using original rows with coalesced answers.")
            
            # Identify all answer_set_*_answer_text_text and answer_multiple_choice_option_text columns
            answer_text_cols = [col for col in df_answers.columns if '_answer_text_text' in col]
            multi_choice_cols = [col for col in df_answers.columns if '_answer_multiple_choice_option_text' in col]
            
            # We'll create a single 'answer' column by coalescing across all answer sets
            # (first non-null value across sets, prioritizing multiple choice over text if same set?)
            # Simpler: combine all text answers and all multi-choice answers, then coalesce.
            # For testing, we'll just take the first non-null from any set.
            df_stacked = df_answers.copy()
            
            # Combine all answer_text columns into a single column
            if answer_text_cols:
                # Fill NaN with empty string to avoid issues
                df_stacked['_temp_text'] = df_stacked[answer_text_cols].fillna('').apply(
                    lambda row: '; '.join([val for val in row if val.strip()]), axis=1
                )
            else:
                df_stacked['_temp_text'] = ''
            
            if multi_choice_cols:
                df_stacked['_temp_multi'] = df_stacked[multi_choice_cols].fillna('').apply(
                    lambda row: '; '.join([val for val in row if val.strip()]), axis=1
                )
            else:
                df_stacked['_temp_multi'] = ''
            
            # Combine: use multi-choice if available, else text
            df_stacked['answer'] = df_stacked['_temp_multi'].fillna(df_stacked['_temp_text'])
            # If both empty, set empty string
            df_stacked['answer'] = df_stacked['answer'].fillna('')
            
            # Drop temporary columns
            df_stacked = df_stacked.drop(columns=['_temp_text', '_temp_multi'])
            
            # Add a placeholder for answer_set_number and answer_id (since we're not stacking)
            df_stacked['answer_set_number'] = 0  # or null
            # For answer_id, we could take the first non-null from any set, but we'll leave blank
            df_stacked['answer_id'] = ''
            # answered_at: take the first non-null from any set
            answered_cols = [col for col in df_answers.columns if '_answered_at' in col]
            if answered_cols:
                df_stacked['answered_at'] = df_stacked[answered_cols].bfill(axis=1).iloc[:, 0]
            else:
                df_stacked['answered_at'] = ''
            
            # Keep only needed columns (the ones we want in final output)
            # We'll keep all original columns plus the new ones, but we'll later select only desired ones.
            # Actually, we'll keep all and later select in final column order.
            
            print(f"   ✅ Created {len(df_stacked):,} rows (no stacking)")
            
        else:
            # ================================================================
            # Original stacking logic
            # ================================================================
            
            answer_set_pattern = r'^answer_set_(\d+)_'
            answer_set_numbers = set()
            
            for col in df_answers.columns:
                match = re.match(answer_set_pattern, col)
                if match:
                    answer_set_numbers.add(int(match.group(1)))
            
            answer_set_numbers = sorted(answer_set_numbers)
            print(f"\n   📋 Found {len(answer_set_numbers)} answer sets: {answer_set_numbers}")
            
            # Columns that should stay as-is (not stacked)
            fixed_columns = [
                '_IngestedAt',
                '_ParentID',
                'question_id',
                'question_text',
                'question_type',
                'question_is_mandatory'
            ]
            
            # Also include multiple choice option columns
            for col in df_answers.columns:
                if col.startswith('question_multiple_choice_options_options_'):
                    fixed_columns.append(col)
            
            # Remove duplicates
            fixed_columns = list(dict.fromkeys(fixed_columns))
            
            # Only keep columns that actually exist
            fixed_columns = [col for col in fixed_columns if col in df_answers.columns]
            
            print(f"   📋 Fixed columns ({len(fixed_columns)})")
            
            # ================================================================
            # STACKING LOOP
            # ================================================================
            
            print("\n⚔️ Stacking answer sets...")
            
            stacked_rows = []
            total_original_rows = len(df_answers)
            rows_with_no_data = 0
            
            for idx, row in df_answers.iterrows():
                row_has_any_answer = False
                for answer_num in answer_set_numbers:
                    # Check if this answer set has any data
                    prefix = f"answer_set_{answer_num}_"
                    
                    # Get all columns for this answer set
                    answer_cols = [col for col in df_answers.columns if col.startswith(prefix)]
                    
                    # Check if any of the answer columns have non-null values
                    has_data = False
                    for col in answer_cols:
                        val = row.get(col)
                        if pd.notna(val) and str(val).strip():
                            has_data = True
                            break
                    
                    if has_data:
                        row_has_any_answer = True
                        # Build the stacked row
                        new_row = {}
                        
                        # Add fixed columns
                        for col in fixed_columns:
                            new_row[col] = row.get(col, '')
                        
                        # Add answer_set_number (track which set it came from)
                        new_row['answer_set_number'] = answer_num
                        
                        # Add answer columns (remove the prefix)
                        for col in answer_cols:
                            new_col = col.replace(prefix, '')
                            new_row[new_col] = row.get(col, '')
                        
                        stacked_rows.append(new_row)
                    else:
                        # This answer set has no data
                        if KEEP_EMPTY_ANSWER_SETS:
                            # Still create a row with empty values
                            new_row = {}
                            for col in fixed_columns:
                                new_row[col] = row.get(col, '')
                            new_row['answer_set_number'] = answer_num
                            for col in answer_cols:
                                new_col = col.replace(prefix, '')
                                new_row[new_col] = ''
                            stacked_rows.append(new_row)
                
                if not row_has_any_answer and not KEEP_EMPTY_ANSWER_SETS:
                    rows_with_no_data += 1
            
            print(f"   ✅ Stacking complete.")
            print(f"   📊 Original rows: {total_original_rows:,}")
            print(f"   📊 Stacked rows: {len(stacked_rows):,}")
            if rows_with_no_data > 0:
                print(f"   ⚠️ Rows with no answer data (skipped): {rows_with_no_data:,}")
            
            if not stacked_rows:
                print("   ⚠️ No stacked rows created")
                return
            
            df_stacked = pd.DataFrame(stacked_rows)
            print(f"   ✅ Created {len(df_stacked):,} stacked rows")
            
            # ================================================================
            # DEDUPLICATE TO KEEP NEWEST ANSWER (if enabled)
            # ================================================================
            
            if KEEP_ONLY_NEWEST_ANSWER:
                print("\n🔄 Deduplicating to keep only the newest answer per incident/question...")
                
                # Ensure 'answered_at' exists; if not, use 'answer_set_number' as fallback
                if 'answered_at' in df_stacked.columns:
                    # Convert to datetime, but keep as string for sorting if conversion fails
                    df_stacked['_sort_date'] = pd.to_datetime(df_stacked['answered_at'], errors='coerce')
                    # If conversion fails, fallback to answer_set_number
                    df_stacked['_sort_date'] = df_stacked['_sort_date'].fillna(
                        df_stacked['answer_set_number'].astype(float)
                    )
                    sort_col = '_sort_date'
                else:
                    # Fallback to answer_set_number (higher number = newer)
                    df_stacked['_sort_date'] = df_stacked['answer_set_number'].astype(float)
                    sort_col = '_sort_date'
                    print(f"   ⚠️ 'answered_at' column not found, using 'answer_set_number' as sort key.")
                
                # Sort by _ParentID, question_id, and sort date descending (newest first)
                df_stacked_sorted = df_stacked.sort_values(
                    ['_ParentID', 'question_id', sort_col],
                    ascending=[True, True, False]
                )
                
                # Keep first occurrence per (_ParentID, question_id)
                before = len(df_stacked_sorted)
                df_stacked_deduped = df_stacked_sorted.drop_duplicates(
                    subset=['_ParentID', 'question_id'],
                    keep='first'
                )
                after = len(df_stacked_deduped)
                removed = before - after
                
                # Drop temporary sort column
                df_stacked_deduped = df_stacked_deduped.drop(columns=[sort_col])
                
                print(f"   ✅ Deduplication complete.")
                print(f"      Before: {before:,} rows")
                print(f"      After: {after:,} rows")
                print(f"      Removed: {removed:,} older answers")
                
                df_stacked = df_stacked_deduped
            
            # ================================================================
            # COMBINE ANSWER COLUMNS (multiple choice vs text)
            # ================================================================
            
            print("\n⚔️ Combining answer columns into 'answer'...")
            
            # Check if both columns exist
            has_multiple_choice = 'answer_multiple_choice_option_text' in df_stacked.columns
            has_text = 'answer_text_text' in df_stacked.columns
            
            if has_multiple_choice and has_text:
                # Combine: use multiple_choice_option_text if available, otherwise use answer_text_text
                df_stacked['answer'] = df_stacked['answer_multiple_choice_option_text'].fillna(df_stacked['answer_text_text'])
                print(f"   ✅ Combined 'answer_multiple_choice_option_text' and 'answer_text_text' into 'answer'")
            elif has_multiple_choice:
                df_stacked['answer'] = df_stacked['answer_multiple_choice_option_text']
                print(f"   ✅ Using 'answer_multiple_choice_option_text' as 'answer'")
            elif has_text:
                df_stacked['answer'] = df_stacked['answer_text_text']
                print(f"   ✅ Using 'answer_text_text' as 'answer'")
            else:
                df_stacked['answer'] = ''
                print(f"   ⚠️ No answer columns found, 'answer' set to empty string")
        
        # ====================================================================
        # STEP 6: Join with issues_details to get additional columns
        # ====================================================================
        
        print("\n⚔️ Joining with issues_details...")
        
        # Columns to bring from issues_details
        join_columns = [
            '_ParentID',  # For the join
            'task_unique_id',
            'task_site_name',
            'task_site_area',
            'category_key',
            'location_geo_position_latitude',
            'location_geo_position_longitude',
            'task_occurred_at',
            'task_completed_at',
            'task_created_at',
            'task_creator_firstname',
            'task_creator_lastname',
            'task_creator_user_id',
            'task_description',
            'task_status_id',
            'task_title'
        ]
        
        # Only keep columns that exist in issues_details
        existing_join_cols = [col for col in join_columns if col in df_details.columns]
        print(f"   📋 Joining with columns: {existing_join_cols}")
        
        # Create a copy of details with only needed columns
        df_details_join = df_details[existing_join_cols].copy()
        
        # Check _ParentID matching rate
        print(f"   🔍 Checking _ParentID matching rate...")
        stacked_parents = set(df_stacked['_ParentID'].dropna().unique())
        details_parents = set(df_details_join['_ParentID'].dropna().unique())
        matching_parents = stacked_parents.intersection(details_parents)
        print(f"      Stacked unique _ParentIDs: {len(stacked_parents):,}")
        print(f"      Details unique _ParentIDs: {len(details_parents):,}")
        print(f"      Matching _ParentIDs: {len(matching_parents):,} ({len(matching_parents)/len(stacked_parents)*100:.1f}% of stacked)")
        
        # Join on _ParentID
        df_joined = df_stacked.merge(
            df_details_join,
            on='_ParentID',
            how='left',
            suffixes=('', '_details')
        )
        
        print(f"   ✅ Joined: {len(df_joined):,} rows")
        
        # Count how many got a match (non-null task_unique_id)
        matched_count = df_joined['task_unique_id'].notna().sum()
        print(f"      Rows with matching details: {matched_count:,} ({matched_count/len(df_joined)*100:.1f}%)")
        
        # ====================================================================
        # STEP 7: Define final column order and save
        # ====================================================================
        
        # Define column order with 'answer' replacing the individual columns
        column_order = [
            '_ParentID',
            '_IngestedAt',
            'task_unique_id',
            'task_title',
            'task_site_name',
            'task_site_area',
            'category_key',
            'location_geo_position_latitude',
            'location_geo_position_longitude',
            'task_occurred_at',
            'task_completed_at',
            'task_created_at',
            'task_creator_firstname',
            'task_creator_lastname',
            'task_creator_user_id',
            'task_description',
            'task_status_id',
            'question_id',
            'question_text',
            'question_type',
            'question_is_mandatory',
            'answer_set_number',  # Which answer set it came from (0, 1, 2, etc.)
            'answer_id',          # The actual answer_id UUID
            'answer',             # Combined answer text
            'answered_at'
        ]
        
        # Add multiple choice option columns if they exist
        option_cols = [col for col in df_joined.columns if col.startswith('question_multiple_choice_options_options_')]
        column_order.extend(option_cols)
        
        # Only keep columns that exist
        existing_cols = [col for col in column_order if col in df_joined.columns]
        df_final = df_joined[existing_cols]
        
        # Sort by ParentID and question_id
        df_final = df_final.sort_values(['_ParentID', 'question_id', 'answer_set_number'])
        
        # ====================================================================
        # STEP 8: Save to CSV
        # ====================================================================
        
        df_final.to_csv(output_file, index=False, encoding='utf-8')
        print(f"\n✅ Saved to: {output_file}")
        print(f"   📊 {len(df_final):,} rows, {len(df_final.columns)} columns")
        
        # ====================================================================
        # STEP 9: Show summary
        # ====================================================================
        
        print("\n📊 Stacked Data Summary:")
        print(f"   Total stacked rows: {len(df_final):,}")
        print(f"   Unique questions: {df_final['question_id'].nunique()}")
        print(f"   Unique ParentIDs: {df_final['_ParentID'].nunique()}")
        
        # Show join success rate
        joined_count = df_final['task_unique_id'].notna().sum()
        print(f"   Rows with task_unique_id: {joined_count:,} ({joined_count/len(df_final)*100:.1f}%)")
        
        # Show sample of the combined answer column
        print("\n📋 Sample of combined 'answer' column:")
        sample_df = df_final[['_ParentID', 'question_id', 'answer_set_number', 'answer_id', 'answer']].head(5)
        for _, row in sample_df.iterrows():
            answer_preview = row['answer'][:50] if row['answer'] else '(empty)'
            print(f"   {row['_ParentID']} | Q{row['question_id']} | Set {row['answer_set_number']} | ID {row['answer_id'][:20] if row['answer_id'] else 'None'} | {answer_preview}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()