#!/usr/bin/env python
# coding: utf-8

"""
Filter, Stack and Pivot Incidents - Robust Production Version
Reads gld_issues_answers.csv, filters, stacks, maps to aliases, pivots to columns
Combines separate _at and _at_time fields into complete datetime columns.
"""

import os
import sys
import pandas as pd
import re
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
# CONFIGURATION TOGGLES
# ============================================================================

# Test run: True = process only 10 rows, False = process all rows
TEST_RUN = False

# Filter substring for category_key
CATEGORY_KEY_FILTER = "005 INCIDENT REPORT"

print("=" * 80)
print("⚔️  FILTER, STACK AND PIVOT INCIDENTS (ROBUST)")
print("=" * 80)
print(f"📁 Input (GLD): ADLS/{GLD_PREFIX}")
print(f"📁 Output (REP): ADLS/{REP_PREFIX}")
print(f"🧪 Test Run: {'ON' if TEST_RUN else 'OFF'}")
print(f"🔍 Filter: category_key contains '{CATEGORY_KEY_FILTER}'")
print("=" * 80)

# ============================================================================
# QUESTION ID TO TEXT MAPPING
# ============================================================================

question_mapping = {
    # --- NEW TEMPLATE UUIDS (with & without hyphens) ---
    "ca62246582204512bb9133ace25a0b8c": "Name of Person Reporting the Incident",
    "ca622465-8220-4512-bb91-33ace25a0b8c": "Name of Person Reporting the Incident",

    "ef96f3c018834076bddcabc4672e2461": "Name of Site Client:",
    "ef96f3c0-1883-4076-bddc-abc4672e2461": "Name of Site Client:",

    "d079233a394a407a9f21da397a7333dd": "Incident Category",
    "d079233a-394a-407a-9f21-da397a7333dd": "Incident Category",

    "e6967249de404c809085bb051c824c64": "In the event of an accident, which of the following applies:",
    "e6967249-de40-4c80-9085-bb051c824c64": "In the event of an accident, which of the following applies:",

    "1466ab8ec34f4e64b49bc8616167a8be": "Incident Details",
    "1466ab8e-c34f-4e64-b49b-c8616167a8be": "Incident Details",

    "283a3c0df4dc43e296bbbb7495d6c9f0": "What immediate action has been taken to prevent any reoccurrence?",
    "283a3c0d-f4dc-43e2-96bb-bb7495d6c9f0": "What immediate action has been taken to prevent any reoccurrence?",

    "d3d24363ac1d4834897bf02e69abceda": "Please add any other information of note?",
    "d3d24363-ac1d-4834-897b-f02e69abceda": "Please add any other information of note?",

    "b32022ecb0a34948aba78d7b23978589": "Do not answer this question - SAFETY DEPARTMENT USE ONLY:",
    "b32022ec-b0a3-4948-aba7-8d7b23978589": "Do not answer this question - SAFETY DEPARTMENT USE ONLY:",

    # --- EXISTING TEMPLATE UUIDS ---
    "bad747f6153b4c588a8d9cf4ce9720c0": "Description",
    "acb7fdb80f154ae8be4b495300ecf0b4": "Do not answer this question - SAFETY DEPARTMENT USE ONLY:",
    "8e5dd421089d4ecc8a8f3f135cd1ba70": "Do not answer this question - SAFETY DEPARTMENT USE ONLY:",
    "a183345c08394376b4c0394157da03a3": "Do not answer this question - SAFETY DEPARTMENT USE ONLY:",
    "d42634e9803f4c3f860d99d7e85642b2": "Do not answer this question - SAFETY DEPARTMENT USE ONLY:",
    "92c5084191cf44dda92374b10a88be79": "Do not answer this question - SAFETY DEPARTMENT USE ONLY:",
    "8988a5d06924422d80b3bf710671b5c4": "In the event of a Near Miss / Unplanned Event, could this incident have resulted in very serious harm to persons, property or the environment",
    "432cf48ec3c24793ae6ab4d15ce87bec": "In the event of a Near Miss / Unplanned Event, could this incident have resulted in very serious harm to persons, property or the environment?",
    "8a1a97550d0944b190cb281795de9f00": "In the event of a Near Miss / Unplanned Event, could this incident have resulted in very serious harm to persons, property or the environment?",
    "cf1871701c2e404db63a04ec58792ab0": "In the event of a Near Miss / Unplanned Event, could this incident have resulted in very serious harm to persons, property or the environment?",
    "6aaa4f6946df472e917036eb6bd700ca": "In the event of a Near Miss / Unplanned Event, could this incident have resulted in very serious harm to persons, property or the environment?",
    "d739281965744cd08e6701f4b22bce7c": "In the event of a Near Miss / Unplanned Event, could this incident have resulted in very serious harm to persons, property or the environment?",
    "0b44e6180bf54d5db9caf34bc8adbb35": "In the event of an accident, which of the following applies:",
    "afa27d87a1c048b3b92e9e7625b0649d": "In the event of an accident, which of the following applies:",
    "070e35278f624939a5ef4f8687639b28": "In the event of an accident, which of the following applies:",
    "5daee59cbd124ea2b832e540248a0407": "In the event of an accident, which of the following applies:",
    "de065500bff44c8f9b25b2503c71bebb": "In the event of an accident, which of the following applies:",
    "33f6a3e6a6764b7c952756b5bc00096c": "In the event of an accident, which of the following applies:",
    "9b18a7019ada4edeb095442bc0df0225": "In the event of an accident, which of the following applies:",
    "ce923c780d224b2ca9b151eb1cffb4c3": "Incident Category",
    "abc7727a36da485580a48f9cdadfa865": "Incident Category",
    "36257e303a924e86b598ed2dbadd925d": "Incident Category",
    "4f4741caee954bfeaa7da467b6716e7d": "Incident Category",
    "8fbba53894f44e93860774f029ab7d51": "Incident Category",
    "5155f320120c438d8863a0ab3ffdef99": "Incident Category",
    "680a72131d32441f9cc90883c000db94": "Incident Details",
    "546ddc4aa5384ea18f9843fa96a2a529": "Incident Details",
    "6bb7da0539a9456ab04f86a430b4d1e7": "Incident Details",
    "700a625648b24035accd35d8505ea028": "Incident Details",
    "87edccf01c794d03a24288533b6cd189": "Incident Details",
    "1e03bec49ee54d7b808e2eed644e54f4": "Location",
    "aaa93e63194840a6b2b33a2c11de5de3": "Media",
    "c572f8e0fefd405abdcae47e7349336f": "Name of Person Reporting Incident",
    "0d7e8dc161e94d93a68d9c6975a5c63f": "Name of Person Reporting the Incident",
    "17af4d6c656e417898eafeb22b49f1cb": "Name of Person Reporting the Incident",
    "5de8f7ba022f4ed699301434b32251d7": "Name of Person Reporting the Incident",
    "b6194c8be3674eed9d337adf8f7add2e": "Name of Person Reporting the Incident",
    "502310a4bd5f45e38cb215b187726a7d": "Name of Person Reporting the Incident",
    "6159a8be6b0b45c58684e8ad31e07666": "Name of Site Client:",
    "a7ec40761727453ca7bb45f4d246c8ce": "Name of Site Client:",
    "eb1264442db34d8b985d3a95bc0cb926": "Name of Site Client:",
    "5736410a9d3f4b10a1e7e09424867051": "Name of Site Client:",
    "a5c1bd548c7c4a558512d5dc80b6c9cb": "Occurred At",
    "38b6a3a346104e6787f88e33949324fd": "Other Information of Note?",
    "31ccb64de6504f2699578821a15ced74": "Please add any other information of note?",
    "7fab14d065e44b71adcdf1b2101017e4": "Please add any other Information of Note?",
    "33af63ea30ba4cad87f5e00b8ca0c988": "Please add any other information of note?",
    "7fd4cc8650094929bfbfdbf445c44b61": "Please add any other information of note?",
    "98aa4df092fe45828ed68efd3af324c9": "Please add any other information of note?",
    "c16ae47b41a54a91a49616b62da09e59": "Please add any other information of note?",
    "ce0b60c3b6de42f8b096215653efab5b": "SAFETY DEPARTMENT USE ONLY:",
    "d896885309694e399bf5e93d48047b24": "Site",
    "cc3ef51f8dd64b89a1896ef081a2da79": "Title",
    "8147c57dfe4b4c85999ffeaa828f3483": "What immediate action has been taken to prevent any reoccurrence?",
    "0ef042b2bffe4e5f8340462e6144e774": "What immediate action has been taken to prevent any reoccurrence?",
    "db733b460f4741ea9fe49f83c70aac40": "What immediate action has been taken to prevent any reoccurrence?",
    "fbaf5a09436e422b811948d2d342af23": "What immediate action has been taken to prevent any reoccurrence?",
    "fbc08d61f1f541f199a07d10fa9e2326": "What immediate action has been taken to prevent any reoccurrence?",
    "1b4192e8737b4755ab55bcd990022ad1": "What immediate action has been taken to prevent reoccurrence?"
}

# ============================================================================
# QUESTION TO ALIAS MAPPING
# ============================================================================

question_alias_mapping = {
    "Do not answer this question - SAFETY DEPARTMENT USE ONLY:": "Lost Time",
    "In the event of a Near Miss / Unplanned Event, could this incident have resulted in very serious harm to persons, property or the environment": "HIPO?",
    "In the event of a Near Miss / Unplanned Event, could this incident have resulted in very serious harm to persons, property or the environment?": "HIPO?",
    "In the event of an accident, which of the following applies:": "Treatment Required",
    "Incident Category": "Category",
    "Incident Details": "Details",
    "Incident Details ": "Details",
    "Name of Person Reporting Incident": "Reporter",
    "Name of Person Reporting the Incident": "Reporter",
    "Name of Site Client:": "Site Client",
    "Name of Site Client: ": "Site Client",
    "Other Information of Note?": "Further Information",
    "Please add any other information of note?": "Further Information",
    "Please add any other Information of Note?": "Further Information",
    "SAFETY DEPARTMENT USE ONLY:": "Lost Time",
    "What immediate action has been taken to prevent any reoccurrence?": "Immediate Actions",
    "What immediate action has been taken to prevent reoccurrence?": "Immediate Actions"
}

# ============================================================================
# INCIDENT CATEGORY VALUE MAPPING
# ============================================================================

category_value_mapping = {
    "Near Miss / Unplanned Event": "Near Miss",
    "Environmental Incident": "Environmental",
    "Accident (Personal Injury)": "Accident",
    "Security Incident": "Security",
    "Service Strike": "Service",
    "Accident": "Accident",
    "Near Miss": "Near Miss",
    "Property Damage": "Property"
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def lookup_question_text(q_id_raw):
    """
    Looks up question text using raw ID, stripped ID, or normalized ID without hyphens.
    """
    clean_id = str(q_id_raw).strip()
    if clean_id in question_mapping:
        return question_mapping[clean_id]
    
    no_hyphens = clean_id.replace("-", "").lower()
    if no_hyphens in question_mapping:
        return question_mapping[no_hyphens]
        
    return None

def get_answer_for_question(row, q_idx, all_columns):
    """
    Search across multiple answer column types and answer sets for a given question index.
    """
    prefix = f'question_answers_{q_idx}_'
    relevant_cols = [c for c in all_columns if c.startswith(prefix)]
    
    # Priority 1: Answer set 0 (most recent / primary answer)
    preferred_suffixes = [
        '_answer_text_text',
        '_answer_multiple_choice_option_text',
        '_answer_date_date',
        '_answer_datetime_datetime',
        '_answer_user_name',
        '_answer_value'
    ]
    
    for suffix in preferred_suffixes:
        col = f'question_answers_{q_idx}_answer_set_0{suffix}'
        if col in relevant_cols:
            val = row.get(col, '')
            if pd.notna(val) and str(val).strip():
                return str(val).strip()

    # Priority 2: Fallback across any answer set in descending order
    for col in relevant_cols:
        if 'question_id' in col or 'question_data_id' in col:
            continue
        val = row.get(col, '')
        if pd.notna(val) and str(val).strip():
            return str(val).strip()
            
    return ''

def combine_date_and_time_series(df, date_col, time_col):
    """
    Combines date_col and time_col into date_col in-place, keeping the column name as is.
    Extracts true date even if date_col contains 00:00:00 or T00:00:00.
    """
    if date_col not in df.columns or time_col not in df.columns:
        return

    def _combine(d, t):
        d_str = str(d).strip() if pd.notna(d) else ''
        t_str = str(t).strip() if pd.notna(t) else ''

        if d_str.lower() in ['nan', 'none', 'null', 'nat', '']:
            return ''
        if t_str.lower() in ['nan', 'none', 'null', 'nat', '']:
            return d_str

        # Isolate the pure date component
        date_part = d_str.split('T')[0].split(' ')[0].strip()
        if not date_part:
            return d_str

        return f"{date_part} {t_str}"

    df[date_col] = [_combine(d, t) for d, t in zip(df[date_col], df[time_col])]

# ============================================================================
# MAIN PROCESSING
# ============================================================================

def main():
    input_file = f"{GLD_PREFIX}/gld_issues_answers.csv"
    output_file = f"{REP_PREFIX}/rp2_incidents.csv"
    
    if not client.exists(input_file):
        print(f"❌ Input file not found: {input_file}")
        return
    
    print(f"\n📂 Reading: {input_file}")
    
    try:
        # Load raw CSV with keep_default_na=False to avoid unwanted NaN values
        df = client.read_csv(input_file, dtype=str, keep_default_na=False, low_memory=False)
        df.columns = df.columns.str.strip()
        print(f"   ✅ Loaded {len(df):,} rows | Total columns: {len(df.columns)}")

        # Combine date and time columns into date column
        print("🕒 Merging separate date & time columns (task_created_at, task_modified_at, task_occurred_at)...")
        combine_date_and_time_series(df, 'task_created_at', 'task_created_at_time')
        combine_date_and_time_series(df, 'task_modified_at', 'task_modified_at_time')
        combine_date_and_time_series(df, 'task_occurred_at', 'task_occurred_at_time')

        # ====================================================================
        # RAW DATA DATE SUMMARY
        # ====================================================================
        print("\n📅 Raw Data Summary:")
        if 'task_occurred_at' in df.columns:
            parsed_dates = pd.to_datetime(df['task_occurred_at'], dayfirst=True, errors='coerce').dropna()
            if not parsed_dates.empty:
                print(f"   📅 Date range in file: {parsed_dates.min()} to {parsed_dates.max()}")
                most_recent_idx = parsed_dates.idxmax()
                most_recent_task = df.loc[most_recent_idx, 'task_unique_id'] if 'task_unique_id' in df.columns else 'N/A'
                print(f"   🆔 Most recent raw task_unique_id: {most_recent_task} ({df.loc[most_recent_idx, 'task_occurred_at']})")
        
        if TEST_RUN:
            df = df.head(10).copy()
            print(f"   🧪 TEST MODE: Limiting to {len(df)} rows")

        # ====================================================================
        # STEP 1: CATEGORY FILTERING (CONTAINS) & NOT-FOUND REPORTING
        # ====================================================================
        print(f"\n⚔️ Filtering by category_key contains '{CATEGORY_KEY_FILTER}'...")
        
        if 'category_key' not in df.columns:
            print("   ❌ 'category_key' column not found in input CSV!")
            return

        # Strip whitespace for robust comparison
        df['category_key_clean'] = df['category_key'].fillna('').astype(str).str.strip()
        target_filter = CATEGORY_KEY_FILTER.strip()

        # Perform CONTAINS filter (case-insensitive)
        df_filtered = df[df['category_key_clean'].str.upper().str.contains(target_filter.upper(), na=False, regex=False)].copy()

        if df_filtered.empty:
            print(f"\n⚠️ NOT FOUND: Zero records found containing category '{CATEGORY_KEY_FILTER}'.")
            print("📋 Top available categories in dataset:")
            category_counts = df['category_key'].value_counts(dropna=False).head(15)
            for cat, count in category_counts.items():
                print(f"   - '{cat}': {count:,} rows")
            
            print("\n📋 Recent task_unique_ids present in the file:")
            id_col = 'task_unique_id' if 'task_unique_id' in df.columns else df.columns[0]
            date_col = 'task_occurred_at' if 'task_occurred_at' in df.columns else 'task_created_at'
            cols_to_show = [c for c in [id_col, 'category_key', date_col] if c in df.columns]
            print(df[cols_to_show].head(10).to_string(index=False))
            return

        print(f"   🎯 Found {len(df_filtered):,} rows matching filter")
        
        # Track initial list of unique tasks
        if 'task_unique_id' in df_filtered.columns:
            all_filtered_task_ids = set(df_filtered['task_unique_id'].dropna().unique())
            print(f"   📊 Unique task_unique_ids matched: {len(all_filtered_task_ids):,}")
        else:
            all_filtered_task_ids = set()

        # ====================================================================
        # STEP 2: METADATA EXTRACTION & BASE TABLE
        # ====================================================================
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
            'category_key',
            'location_geo_position_latitude',
            'location_geo_position_longitude'
        ]
        
        existing_metadata = [col for col in metadata_cols if col in df_filtered.columns]
        
        # Clean metadata (prevent NaN values from dropping rows during pivot)
        df_filtered[existing_metadata] = df_filtered[existing_metadata].fillna('').astype(str)
        
        # Preserve 100% of task unique IDs in the base DataFrame
        if 'task_unique_id' in existing_metadata:
            base_task_df = df_filtered[existing_metadata].drop_duplicates(subset=['task_unique_id']).copy()
        else:
            base_task_df = df_filtered[existing_metadata].drop_duplicates().copy()

        # ====================================================================
        # STEP 3: EXTRACT QUESTIONS & ANSWERS
        # ====================================================================
        print("\n⚔️ Extracting questions and answers...")
        
        question_id_cols = [
            col for col in df_filtered.columns 
            if col.endswith('question_id') and 'question_data_id' not in col
        ]
        
        extracted_data = []
        unknown_questions_map = {}
        tasks_with_answers = set()
        all_cols_list = df_filtered.columns.tolist()

        for _, row in df_filtered.iterrows():
            row_task_id = row.get('task_unique_id', 'UNKNOWN_TASK')
            metadata = {col: row.get(col, '') for col in existing_metadata}
            
            for q_col in question_id_cols:
                match = re.search(r'question_answers_(\d+)_question_id', q_col)
                if not match:
                    continue
                
                q_idx = int(match.group(1))
                q_id_val = str(row.get(q_col, '')).strip()
                
                if not q_id_val:
                    continue
                
                # Check mapped question
                question_text = lookup_question_text(q_id_val)
                
                if not question_text:
                    if q_id_val not in unknown_questions_map:
                        unknown_questions_map[q_id_val] = set()
                    unknown_questions_map[q_id_val].add(row_task_id)
                    continue
                
                # Get the answer
                ans = get_answer_for_question(row, q_idx, all_cols_list)
                
                if ans:
                    new_entry = metadata.copy()
                    new_entry['question_text'] = question_text
                    new_entry['answer'] = ans
                    extracted_data.append(new_entry)
                    tasks_with_answers.add(row_task_id)

        # Report Unknown Questions (New UUIDs)
        if unknown_questions_map:
            print(f"\n⚠️ Found {len(unknown_questions_map)} unmapped question_id UUID(s) in filtered records:")
            for q_id, task_list in list(unknown_questions_map.items())[:10]:
                sample_tasks = list(task_list)[:3]
                print(f"   - Question ID '{q_id}' (seen on task_ids: {sample_tasks})")
            print("   👉 Add these to 'question_mapping' if they contain incident data.")

        # Report Tasks matching filter but missing answers
        missing_answer_tasks = all_filtered_task_ids - tasks_with_answers
        if missing_answer_tasks:
            print(f"\n⚠️ {len(missing_answer_tasks)} task_unique_id(s) matched category filter but had NO valid answers extracted:")
            print(f"   IDs: {list(missing_answer_tasks)[:10]}")

        # ====================================================================
        # STEP 4: PIVOT & MERGE BACK TO BASE TASKS
        # ====================================================================
        expected_columns = [
            'Lost Time', 'HIPO?', 'Treatment Required', 'Immediate Actions',
            'Category', 'Details', 'Reporter', 'Site Client', 'Further Information'
        ]

        if extracted_data:
            df_extracted = pd.DataFrame(extracted_data)
            
            # Map aliases with stripped fallback
            df_extracted['question_alias'] = df_extracted['question_text'].map(
                lambda x: question_alias_mapping.get(x, question_alias_mapping.get(x.strip(), x.strip()))
            )
            
            # Pivot answers
            pivoted = df_extracted.pivot_table(
                index='task_unique_id',
                columns='question_alias',
                values='answer',
                aggfunc='first',
                dropna=False
            ).reset_index()
            pivoted.columns.name = None
            
            # Left join back to base tasks so no task_unique_id is dropped
            final_df = base_task_df.merge(pivoted, on='task_unique_id', how='left')
        else:
            print("⚠️ No answers could be mapped! Producing metadata skeleton table.")
            final_df = base_task_df.copy()

        # Ensure all expected columns exist
        for col in expected_columns:
            if col not in final_df.columns:
                final_df[col] = ''
            else:
                final_df[col] = final_df[col].fillna('')

        # Apply Category value mapping
        if 'Category' in final_df.columns:
            final_df['Category'] = final_df['Category'].apply(
                lambda x: category_value_mapping.get(str(x).strip(), str(x).strip()) if pd.notna(x) else ''
            )

        # Fill any remaining NaNs
        final_df = final_df.fillna('')

        # ====================================================================
        # STEP 5: SAVE & REPORT SUMMARY
        # ====================================================================
        client.write_csv(final_df, output_file, index=False, encoding='utf-8')
        print(f"\n✅ Output successfully saved: {output_file}")
        print(f"   📊 Total Rows: {len(final_df):,} | Total Columns: {len(final_df.columns)}")
        
        if 'task_unique_id' in final_df.columns:
            print(f"   🆔 Unique incidents in output: {final_df['task_unique_id'].nunique():,}")

        print("\n📋 Sample of Output (First 5 rows):")
        display_cols = [
            c for c in ['task_unique_id', 'task_occurred_at', 'task_created_at', 'Category', 'Details', 'Reporter', 'Lost Time'] 
            if c in final_df.columns
        ]
        print(final_df[display_cols].head(5).to_string(index=False))

    except Exception as e:
        print(f"❌ Execution Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()