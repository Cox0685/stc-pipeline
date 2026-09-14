#!/usr/bin/env python
# coding: utf-8

"""
RP1 Inspection Answers - Local Version
Reads from SLV folder, joins with audits_search and sites_list, outputs ALL inspections
NO FILTERING - all inspections included
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
REP_OUTPUT_PATH = r"C:\Users\Thomas.Cox\OneDrive - OCU Group\Desktop\00_AST_SystemsIntegration\00_AST_DataUploads\01_STC Safety Culture\Data\REP"
os.makedirs(REP_OUTPUT_PATH, exist_ok=True)

TEST_RUN = False

# ============================================================================
# CIPHER DICTIONARIES
# ============================================================================

# Primary cipher with all known question IDs and their labels
raw_question_cipher = {
    # Title Page Section
    "f3245d39-ea77-11e1-aff1-0800200c9a66": "Title Page",
    "d1cdea00-135d-4c89-ac41-77697c1cd7f9": "Site",
    "50694cc8-85dd-4090-b0e3-a42613925dea": "Date",
    "f3245d43-ea77-11e1-aff1-0800200c9a66": "Person Completing",
    "88579881-f2c2-41b9-a0e7-7ae9a7e35479": "Site Weekly ESG Report",

    # Site Hours Section
    "fb8e43ef-bffd-4c8f-9ca4-be61670b096a": "Site Hours",
    "ae909b3c-74d6-442d-be68-03a8c993bfd6": "Total Weekly Hours - Staff/Ops",
    "af668731-f36e-494d-b621-b6c37f38267e": "Total Weekly Hours - Agency/Subbie",
    "01b53098-5d5c-4328-a0ce-bec904f1edb4": "Total Weekly Hours - Ext Plant",
    "69991fec-a4a7-41b2-83bf-90f55ae70eea": "Total Weekly Hours - Sub Con Personnel",
    "0b74faad-aede-4479-ac30-a39e144b7f6e": "Total Weekly Hours - Client Reps",
    "01bb2832-6a98-47b2-b9ec-7fb6a2552d9d": "Total Weekly Hours - Delivery Drivers",
    "01f0f844-687d-4f4e-a4f8-e6979e297495": "Total Weekly Hours - Visitors",
    "53903bd9-880e-4edc-8029-d79e5332c4ce": "Total Weekly Hours - Others",

    # HSE Statistics Section
    "d72a7431-1238-4fec-a759-0b9195341ca0": "HSE Statistics",
    "ad5ca287-4960-47dc-b801-4a964d0dd839": "Site Inductions Completed",
    "93db6372-2e0c-43d7-bfb7-2124f83bb080": "Safety Meetings Held",
    "02faf190-6bf9-46d1-9691-eef638dbabac": "Yellow Cards Issued",
    "ac19b01f-b8ab-4688-8f59-68a4dfc7daf6": "Red Cards Issued",
    "bbb5ec9c-9828-430b-aa5e-c98428f414de": "Drug & Alcohol Testing?",
    "f060e469-676d-412c-93da-765f5c33fdbd": "Drug Testing Logic",
    "ded16edc-95c8-4050-b142-193de4f4743d": "How many tests were carried out?",
    "4b0ffb57-b505-4e80-adf3-cb519c659cfd": "Tests Count Logic",
    "b4e5c8a1-3d10-4370-b177-e26ac6fca98c": "Insert number of non-negative results",

    # Carbon Savings / Planet Section
    "dadeb35c-cb12-4e27-9b9a-b86a193387ec": "Planet",
    "518d5577-ec5d-4e6c-9a42-dcf35a6ba02b": "Battery/Solar/Value Eng?",
    "d8f17548-f3ee-4b55-a555-8820bbcb587e": "Battery/Solar Logic",
    "87e631a9-e2b8-4e18-858f-d6385f515ccf": "Litres of fuel saved",

    # Work (Employment & Training) Section
    "ec7007ed-9aae-4225-947f-027354f7673a": "Work (Employment & Training)",
    "fd56623e-ac4d-484f-99b2-db5c17c768a0": "Jobs Advertised",
    "9e5ac622-6e83-432d-ae43-efeb8d506f0c": "Jobs Advertised Logic",
    "6c52be4a-57a1-4578-87e2-3b5b19859381": "High Priority Groups Targeted?",
    "055a03c1-e4cf-4dd5-a865-e5d1820c60f0": "Priority Groups Logic",
    "49ed4473-8be9-450b-9669-c76dd8065408": "Which groups were targeted?",
    "d708c5fc-c9ec-4ea0-8131-50d89437f0c1": "Jobs Filled",
    "58bb521d-ebe0-4425-992c-ac9ade91db73": "Jobs Filled Logic",
    "604a5a7a-45ce-4b45-9561-eb3c6edf48b9": "Jobs Filled Count",
    "3912fff9-16e2-4b75-a565-b133866f9459": "Employees Provided Training",
    "b28c264c-5077-4d03-9d49-c48ff15ccf88": "Training Logic",
    "2adb5208-2e32-4daa-b544-d5f25de76404": "Total hours training provided",
    "154554b3-4f19-480e-9a7d-6cf145815718": "Apprentices on Project",
    "efc02a77-b51b-403a-abc5-d5f2f4b800cb": "Apprentices Logic",
    "d822d9a0-02f1-482b-a72d-5cfa5048c698": "Apprentices Total Days",

    # Work (Educational Support) Section
    "d17e0b3a-e744-4297-b00e-f972ee6cbe92": "Work (Educational Support)",
    "52d5194b-e512-4c9c-b193-47a84556e05a": "Educational Support Instruction",
    "c4bd50f8-5369-4bac-80ad-8eb69e19c9f2": "Number of Events",
    "78f5165d-db82-415c-b8df-e9880cfc5af1": "Staff hours (Prep/Travel)",
    "0ca23a46-c4e7-4c2a-9da2-1a960052f426": "Cost of support/donation",
    "a7c89bca-1c02-49cc-aefa-a0ceb36814e7": "Support Description",
    "f0f403b9-6090-47a5-9fa1-0ea2f5b683ab": "Work Experience Placement?",
    "7ea02851-0cf6-405a-8630-023f3d7aa00c": "Work Experience Logic",
    "ac16d22a-5450-4c4b-9eaf-398e75ea32ad": "Work Experience Days",

    # Economy / Supply Chain Section
    "f3220f0e-e0fe-46ea-bddc-80f617b7b4e6": "Economy",
    "60ede7c2-16b3-4da7-b236-6eaa8d1b7f88": "Supply Chain Development?",
    "55479538-e4e9-4da4-91de-207423d6da4d": "Supply Chain Logic",
    "9bcabd19-241a-487a-8498-64b7a16f8162": "Supply Chain Staff Hours",
    "a6ce28bb-b13b-4e47-83b9-69f2fd5839fe": "Supply Chain Instruction",
    "093c0def-910a-49dd-bd82-2c990d332bde": "SME (10-250 employees)",
    "d8475e6f-8786-405d-9c64-924240e17649": "SME Logic",
    "4e51efbc-7a69-4a2f-8367-4777e6204b37": "SME Local Count",
    "92240c4f-9226-4d76-aa26-1b05ca3a1be7": "Micro Business (<10 employees)",
    "ecd29573-e4c3-4ea5-89c2-f8cf6dba71e7": "Micro Business Logic",
    "7dd4ca5e-6d59-4a0b-a189-54b0956e2f5a": "Micro Business Local Count",
    "6769276c-0038-4151-913e-4d135d7967ba": "Social Enterprise/Voluntary Org",
    "56efe4dc-fd5e-45eb-86d9-c504ca1d47c4": "Social Enterprise Logic",
    "5e6f6663-4f62-4e4b-ae6f-99e54912fab0": "Social Enterprise Local Count",

    # Community Section
    "26abda1f-aa64-4a67-8dc7-f2523ac253f0": "Community",
    "83c623b3-cf0b-4160-a683-954c5174a8a5": "Financial/Non-financial Donation?",
    "b962ebe2-3b6c-4f9d-a815-d312bc21ff5c": "Donations Logic",
    "f0b3cb3d-425d-4842-9ea8-e475ead2f2f0": "Cash Donation",
    "ed0e8293-a3bd-4c89-8667-6b5d1bfffe72": "Cash Donation Logic",
    "6dd4a7d6-20e1-4e2d-a3aa-d26318fbf34d": "Cash Donation Value",
    "2e762c73-6123-4c6a-b6f9-cce909963af1": "Volunteering",
    "a9a6751a-a882-4344-8705-42fe910c9270": "Volunteering Logic",
    "a73cb31d-6284-411a-adf3-80831255edf3": "Volunteering Hours",
    "fe1da1f7-b720-4c5d-b221-49181c8d818b": "Social Benefit",
    "d9fe45ac-9e28-4ed0-b667-eb10ed736ce0": "Social Benefit Logic",
    "077621b9-36a0-4c81-af2a-c6449d41ddf8": "Social Benefit Type",
    "dd1dc9fc-afd1-4bb9-bb2e-fbdc8570d5b6": "Social Benefit Value",
}

# Alternative labels for fallback lookups (for different template versions)
alternative_labels = {
    # These are alternative labels found in different template revisions
    "dadeb35c-cb12-4e27-9b9a-b86a193387ec": ["Planet", "Carbon savings"],
    "ec7007ed-9aae-4225-947f-027354f7673a": ["Work (Employment & Training)", "Employment and training"],
    "f3220f0e-e0fe-46ea-bddc-80f617b7b4e6": ["Economy", "Supply chain"],
    "d17e0b3a-e744-4297-b00e-f972ee6cbe92": ["Work (Educational Support)", "Educational support"],
    "26abda1f-aa64-4a67-8dc7-f2523ac253f0": ["Community", "Community & Charity Work"],
    "af668731-f36e-494d-b621-b6c37f38267e": ["Total Weekly Hours - Agency/Subbie", "Total Weekly Hours for all Labour Only Sub Contractors", "Total Weekly Hours for all Labour Only Sub Contractors & Agency staff (Inc. Cleaners)"],
    "0b74faad-aede-4479-ac30-a39e144b7f6e": ["Total Weekly Hours - Client Reps", "Total Weekly Hours for all Client Appointed Contractors Personnel", "Total Weekly Hours for all Client Representatives, & appointed Contractors Personnel"],
    "fb8e43ef-bffd-4c8f-9ca4-be61670b096a": ["Site Hours", "Site Hours - All site hours must be recorded"],
    "87e631a9-e2b8-4e18-858f-d6385f515ccf": ["Litres of fuel saved", "Approximately how many litres of fuel were saved this week?"],
}

# Build reverse lookup: map all alternative labels back to the primary key
# This allows fallback lookup if a question_id doesn't match the main cipher
reverse_cipher = {}
for key, primary_label in raw_question_cipher.items():
    # Add the primary label
    reverse_cipher[primary_label.lower()] = key
    # Add any alternative labels
    if key in alternative_labels:
        for alt_label in alternative_labels[key]:
            reverse_cipher[alt_label.lower()] = key

# Also create a label-to-label mapping for when we need to find the primary label
label_to_primary = {}
for key, primary_label in raw_question_cipher.items():
    label_to_primary[primary_label] = primary_label
    if key in alternative_labels:
        for alt_label in alternative_labels[key]:
            label_to_primary[alt_label] = primary_label

# Clean version without hyphens
clean_question_cipher = {k.replace("-", ""): v for k, v in raw_question_cipher.items()}

print("=" * 80)
print("⚔️  RP1 INSPECTION ANSWERS - LOCAL VERSION (NO FILTERING)")
print("=" * 80)
print(f"📁 Input (SLV): {SLV_INPUT_PATH}")
print(f"📁 Output (REP): {REP_OUTPUT_PATH}")
print(f"🧪 Test Run: {'ON' if TEST_RUN else 'OFF'}")
print("=" * 80)

# ============================================================================
# FUNCTIONS FOR FALLBACK LOOKUP
# ============================================================================

def get_question_label(question_id: str, question_text: Optional[str] = None) -> str:
    """
    Get the label for a question ID with fallback options.
    
    Strategy:
    1. Try direct lookup in raw_question_cipher
    2. Try direct lookup in clean_question_cipher (without hyphens)
    3. Try looking up by label in reverse_cipher (if question_text provided)
    4. Return "Logic/Unknown" if not found
    """
    if pd.isna(question_id):
        return "Logic/Unknown"
    
    # Normalize the ID
    norm_id = str(question_id).strip()
    
    # Try primary cipher first
    if norm_id in raw_question_cipher:
        return raw_question_cipher[norm_id]
    
    # Try clean cipher (without hyphens)
    clean_id = norm_id.replace("-", "")
    if clean_id in clean_question_cipher:
        return clean_question_cipher[clean_id]
    
    # If we have question text, try to find it in the reverse cipher
    if question_text and not pd.isna(question_text):
        text_lower = str(question_text).strip().lower()
        if text_lower in reverse_cipher:
            found_key = reverse_cipher[text_lower]
            return raw_question_cipher.get(found_key, "Logic/Unknown")
        
        # Try partial matching for question text
        for alt_text, key in reverse_cipher.items():
            if alt_text in text_lower or text_lower in alt_text:
                return raw_question_cipher.get(key, "Logic/Unknown")
    
    return "Logic/Unknown"

def get_primary_label(label: str) -> str:
    """
    Given any label variant, return the primary label from the cipher.
    """
    if pd.isna(label):
        return label
    
    label_str = str(label).strip()
    
    # Check if the label matches any primary or alternative label
    for primary, alts in alternative_labels.items():
        if label_str == raw_question_cipher.get(primary):
            return raw_question_cipher[primary]
        if label_str in alts:
            return raw_question_cipher[primary]
    
    # Check if it's a primary label directly
    if label_str in label_to_primary:
        return label_to_primary[label_str]
    
    return label_str

# ============================================================================
# PROCESS JOIN FUNCTION
# ============================================================================

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
    
    if left_key not in df.columns:
        print(f"      ⚠️ Left key {left_key} not found in source table.")
        return df
    
    if right_key not in lookup_df.columns:
        print(f"      ⚠️ Right key {right_key} not found in lookup table.")
        return df
    
    if return_col not in lookup_df.columns:
        print(f"      ⚠️ Return column {return_col} not found in lookup table.")
        return df
    
    lookup_df_deduped = lookup_df[[right_key, return_col]].drop_duplicates(subset=[right_key])
    
    lookup_df_renamed = lookup_df_deduped.rename(columns={
        right_key: '_lkp_join_key',
        return_col: target_col
    })
    
    result = df.merge(lookup_df_renamed, left_on=left_key, right_on='_lkp_join_key', how='left')
    result = result.drop('_lkp_join_key', axis=1)
    
    return result

# ============================================================================
# STEP 1: READ ALL NEEDED TABLES
# ============================================================================

print("\n⚔️ [MUSTERING RANKS] Reading tables...")

all_dfs = {}

inspections_answers_path = os.path.join(SLV_INPUT_PATH, "inspections_answers.csv")
NEEDED_COLUMNS = [
    '_ParentID',
    '_IngestedAt',
    'result_question_id',
    'result_checkbox_answer_answer',
    'result_datetime_answer_answer',
    'result_question_answer_note',
    'result_signature_answer_name',
    'result_signature_answer_signed_at',
    'result_site_answer_area',
    'result_site_answer_name',
    'result_text_answer_answer'
]

print(f"   📂 Reading: inspections_answers.csv")
df_esg = pd.read_csv(
    inspections_answers_path, 
    dtype=str, 
    low_memory=False,
    usecols=NEEDED_COLUMNS
)

rename_map = {
    '_ParentID': 'ParentID',
    '_IngestedAt': 'IngestedAt'
}
df_esg = df_esg.rename(columns=rename_map)

if TEST_RUN:
    df_esg = df_esg.head(10)

all_dfs['inspections_answers'] = df_esg
print(f"   ✓ Staged inspections_answers ({len(df_esg):,} rows, {len(df_esg.columns)} columns)")

audits_search_path = os.path.join(SLV_INPUT_PATH, "audits_search.csv")
if os.path.exists(audits_search_path):
    df_audits = pd.read_csv(audits_search_path, dtype=str, low_memory=False)
    all_dfs['audits_search'] = df_audits
    print(f"   ✓ Staged audits_search ({len(df_audits):,} rows, {len(df_audits.columns)} columns)")
else:
    print(f"   ⚠️ audits_search not found")

sites_list_path = os.path.join(SLV_INPUT_PATH, "sites_list.csv")
if os.path.exists(sites_list_path):
    df_sites = pd.read_csv(sites_list_path, dtype=str, low_memory=False)
    all_dfs['sites_list'] = df_sites
    print(f"   ✓ Staged sites_list ({len(df_sites):,} rows, {len(df_sites.columns)} columns)")
else:
    print(f"   ⚠️ sites_list not found")

# ============================================================================
# STEP 2: JOIN AND ENRICH - NO FILTERING (ALL INSPECTIONS)
# ============================================================================

print("\n⚔️ [JOINING] Adding client_site via audits_search -> sites_list...")

if 'audits_search' in all_dfs and 'sites_list' in all_dfs:
    df_audits = all_dfs['audits_search'].copy()
    
    join_spec = {
        "target_column": "client_site",
        "join_table": "sites_list",
        "left_key": "site_id",
        "right_key": "site_uuid",
        "return_column": "name"
    }
    
    df_audits_enriched = process_join(df_audits, join_spec, all_dfs)
    print(f"   ✅ audits_search enriched with client_site")
    
    print(f"   🔗 Joining ESG data with ALL inspections (NO FILTERING)...")
    
    if not df_audits_enriched.empty:
        def clean_name(name):
            if pd.isna(name):
                return None
            name_str = str(name)
            if name_str and re.match(r'^[0-9]', name_str):
                return name_str.split('/')[0].strip()
            return None
        
        df_audits_enriched['client_site'] = df_audits_enriched.apply(
            lambda row: row['client_site'] if pd.notna(row.get('client_site')) else clean_name(row.get('name')),
            axis=1
        )
        
        # Select columns from audits_search to bring in
        audit_columns = [
            'id', 
            'template_name', 
            'client_site',
            'author_id',
            'author_name',
            'conducted_on',
            'created_at',
            'date_completed',
            'date_modified',
            'date_started'
        ]
        
        # Only keep columns that exist
        existing_audit_cols = [col for col in audit_columns if col in df_audits_enriched.columns]
        lookup_join = df_audits_enriched[existing_audit_cols].drop_duplicates(subset=['id'])
        
        df_esg = all_dfs['inspections_answers'].copy()
        df_esg_renamed = df_esg.rename(columns={'ParentID': '_inspection_join_key'})
        df_enriched = df_esg_renamed.merge(
            lookup_join,
            left_on='_inspection_join_key',
            right_on='id',
            how='inner'
        ).drop(columns=['id', '_inspection_join_key'])
        
        print(f"   ✅ Joined: {len(df_enriched):,} rows with template_name, client_site, author, and dates")
        all_dfs['inspections_answers'] = df_enriched
        
        esg_report_path = os.path.join(REP_OUTPUT_PATH, "rp1_inspection_answers.csv")
        df_enriched.to_csv(esg_report_path, index=False, encoding='utf-8')
        print(f"   ✓ Saved rp1_inspection_answers.csv ({len(df_enriched):,} rows)")
    else:
        print(f"   ⚠️ No inspections found to join")
else:
    print(f"   ⚠️ Missing tables for join")

# ============================================================================
# STEP 3: MAP QUESTION IDs TO NAMES & MERGE ANSWER COLUMNS
# ============================================================================

print("\n⚔️ [MUSTERING CIPHER] Mapping question IDs...")

try:
    esg_report_path = os.path.join(REP_OUTPUT_PATH, "rp1_inspection_answers.csv")
    df_esg = pd.read_csv(esg_report_path, dtype=str, low_memory=False)
    
    if "Question" in df_esg.columns:
        df_esg = df_esg.drop(columns=["Question"])
    
    # Use the enhanced get_question_label function with fallback
    # We'll pass the raw question text if available to help with fallback
    df_esg['Question'] = df_esg.apply(
        lambda row: get_question_label(
            row.get('result_question_id'), 
            row.get('result_question_text')  # If this column exists
        ),
        axis=1
    )
    
    # If result_question_text doesn't exist, use the label from the cipher
    # or use the question_id itself as a fallback label
    if 'result_question_text' not in df_esg.columns:
        df_esg['Question'] = df_esg['result_question_id'].apply(
            lambda x: get_question_label(x)
        )
    
    print(f"   ✅ Mapped {len(df_esg):,} questions using cipher with fallback support")
    
    print("\n⚔️ [MERGING ANSWER COLUMNS] Combining all answer fields into 'Answer'...")
    
    answer_columns = [
        'result_checkbox_answer_answer',
        'result_datetime_answer_answer',
        'result_question_answer_note',
        'result_signature_answer_name',
        'result_signature_answer_signed_at',
        'result_site_answer_area',
        'result_site_answer_name',
        'result_text_answer_answer'
    ]
    
    existing_answer_cols = [col for col in answer_columns if col in df_esg.columns]
    
    df_esg['Answer'] = None
    for col in existing_answer_cols:
        df_esg['Answer'] = df_esg['Answer'].fillna(df_esg[col])
    
    df_esg = df_esg.drop(columns=existing_answer_cols)
    
    print(f"   ✅ Merged {len(existing_answer_cols)} answer columns into 'Answer'")
    
    ordered_columns = [
        "inspection_id", 
        "client_site", 
        "template_name", 
        "author_id",
        "author_name",
        "conducted_on",
        "created_at",
        "date_completed",
        "date_modified",
        "date_started",
        "Question",
        "question_id", 
        "Answer", 
        "IngestedAt"
    ]
    
    # Rename ParentID to inspection_id
    if "ParentID" in df_esg.columns and "inspection_id" not in df_esg.columns:
        df_esg = df_esg.rename(columns={"ParentID": "inspection_id"})
    
    if "result_question_id" in df_esg.columns and "question_id" not in df_esg.columns:
        df_esg = df_esg.rename(columns={"result_question_id": "question_id"})
    
    existing_cols = [col for col in ordered_columns if col in df_esg.columns]
    df_final = df_esg[existing_cols]
    
    df_final.to_csv(esg_report_path, index=False, encoding='utf-8')
    print(f"   ✅ Saved with merged 'Answer' column ({len(df_final):,} rows)")
    
except Exception as e:
    print(f"   ❌ Failed: {e}")
    import traceback
    traceback.print_exc()

# ============================================================================
# SUMMARY
# ============================================================================

print("\n" + "=" * 80)
print("🏁 RP1 INSPECTION ANSWERS COMPLETE")
print("=" * 80)

print("\n📋 REP Output Files:")
for f in os.listdir(REP_OUTPUT_PATH):
    if f.endswith('.csv') and f == 'rp1_inspection_answers.csv':
        p = os.path.join(REP_OUTPUT_PATH, f)
        s = os.path.getsize(p)
        try:
            df = pd.read_csv(p)
            print(f"   {f:<35} | {len(df):>6,} rows | {len(df.columns):>3} cols | {s:>10,} bytes")
        except:
            print(f"   {f:<35} | {s:>10,} bytes")