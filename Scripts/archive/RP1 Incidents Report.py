#!/usr/bin/env python
# coding: utf-8

"""
RP1 Incidents Report - Local Version
Reads from TNS folder (ExactJSON, ParentID, IngestedAt), parses JSON, outputs to REP folder
"""

import os
import pandas as pd
import json
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

# ============================================================================
# CONFIGURATION
# ============================================================================

TNS_INPUT_PATH = r"C:\Users\Thomas.Cox\OneDrive - OCU Group\Desktop\00_AST_SystemsIntegration\00_AST_DataUploads\01_STC Safety Culture\Data\TNS"
REP_OUTPUT_PATH = r"C:\Users\Thomas.Cox\OneDrive - OCU Group\Desktop\00_AST_SystemsIntegration\00_AST_DataUploads\01_STC Safety Culture\Data\REP"
os.makedirs(REP_OUTPUT_PATH, exist_ok=True)

TEST_RUN = False

print("=" * 80)
print("⚔️  RP1 INCIDENTS REPORT - LOCAL VERSION (FROM TNS JSON)")
print("=" * 80)
print(f"📁 Input (TNS): {TNS_INPUT_PATH}")
print(f"📁 Output (REP): {REP_OUTPUT_PATH}")
print(f"🧪 Test Run: {'ON' if TEST_RUN else 'OFF'}")
print("=" * 80)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def safe_json_get(obj: Any, path: str, default: Any = None) -> Any:
    """Safely get a value from a nested JSON object using dot notation."""
    if obj is None:
        return default
    
    parts = path.split('.')
    current = obj
    
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
            if current is None:
                return default
        else:
            return default
    
    return current if current is not None else default


def extract_text_answer(answer_set: List[Dict]) -> str:
    """Extract answer text from an answer set, prioritizing non-empty values."""
    if not answer_set or not isinstance(answer_set, list):
        return None
    
    # Sort by answered_at (most recent first)
    sorted_answers = sorted(
        [a for a in answer_set if isinstance(a, dict)],
        key=lambda x: x.get('answered_at', ''),
        reverse=True
    )
    
    for ans in sorted_answers:
        # Check answer_text.text
        if 'answer_text' in ans and isinstance(ans['answer_text'], dict):
            text = ans['answer_text'].get('text', '')
            if text and str(text).strip():
                return str(text).strip()
        
        # Check answer_multiple_choice_option.text
        if 'answer_multiple_choice_option' in ans and isinstance(ans['answer_multiple_choice_option'], dict):
            text = ans['answer_multiple_choice_option'].get('text', '')
            if text and str(text).strip():
                return str(text).strip()
    
    return None


def coalesce_answers(qa_list: List[Dict], question_ids: List[str], fallback: Any = None) -> Any:
    """Find the first non-empty answer from a list of question IDs."""
    if not qa_list or not isinstance(qa_list, list):
        return fallback
    
    for qa in qa_list:
        if not isinstance(qa, dict):
            continue
        
        q_id = qa.get('question_id')
        if q_id in question_ids:
            answer_set = qa.get('answer_set', [])
            if answer_set:
                text = extract_text_answer(answer_set)
                if text:
                    return text
    
    return fallback


def classify_incident(category: str, details: str) -> str:
    """Classify incident based on category and details."""
    if pd.isna(category):
        category = ''
    if pd.isna(details):
        details = ''
    
    # Normalize: lowercase, remove spaces, hyphens, underscores
    cat_norm = re.sub(r'[\s\-_]', '', str(category).lower())
    det_norm = re.sub(r'[\s\-_]', '', str(details).lower())
    
    # Check Environmental
    if 'environmental' in cat_norm:
        return 'Environmental'
    
    # Check Service Strike
    if 'servicestrike' in cat_norm:
        return 'Service Strike'
    
    # Check Near Miss
    if 'nearmiss' in cat_norm or 'unplanned' in cat_norm:
        return 'Near Miss'
    
    # Check Property Damage
    if 'property' in cat_norm:
        return 'Property Damage'
    
    # Check Accident
    if 'accident' in cat_norm:
        return 'Accident'
    
    # Check Security
    if 'security' in cat_norm:
        return 'Security Breach'
    
    # Fallback to details
    if 'environmental' in det_norm:
        return 'Environmental'
    if 'servicestrike' in det_norm:
        return 'Service Strike'
    if 'nearmiss' in det_norm or 'unplanned' in det_norm:
        return 'Near Miss'
    if 'propertydamage' in det_norm:
        return 'Property Damage'
    if 'accident' in det_norm:
        return 'Accident'
    if 'security' in det_norm:
        return 'Security Breach'
    
    return 'Other'

# ============================================================================
# MAIN PROCESSING
# ============================================================================

print("\n⚔️ [PROCESSING INCIDENTS] Reading issues_details from TNS...")

input_file = os.path.join(TNS_INPUT_PATH, "issues_details.csv")
output_file = os.path.join(REP_OUTPUT_PATH, "Rp1_incidents_report_dev.csv")

try:
    if not os.path.exists(input_file):
        print(f"   ❌ File not found: {input_file}")
        exit(1)
    
    print(f"   📂 Reading: {os.path.basename(input_file)} ({os.path.getsize(input_file):,} bytes)")
    
    # Read the 3-column CSV (ExactJSON, ParentID, IngestedAt)
    df = pd.read_csv(input_file, dtype=str, low_memory=False)
    
    if TEST_RUN:
        df = df.head(10)
    
    print(f"   📊 Loaded {len(df):,} rows")
    
    # ========================================================================
    # STEP 1: Filter to category containing '005 INCIDENT REPORT' from JSON
    # ========================================================================
    
    print("\n⚔️ [FILTERING] Filtering to category containing '005 INCIDENT REPORT'...")
    
    incident_rows = []
    
    for idx, row in df.iterrows():
        try:
            exact_json = row.get('ExactJSON', '{}')
            if pd.isna(exact_json):
                continue
            
            json_data = json.loads(exact_json) if isinstance(exact_json, str) else exact_json
            
            # Get category key from JSON
            incident = json_data.get('incident', {}) if isinstance(json_data, dict) else {}
            category = incident.get('category', {}) if isinstance(incident, dict) else {}
            category_key = str(category.get('key', '')).strip().upper() if isinstance(category, dict) else ''
            
            # CONTAINS filter (case-insensitive)
            if '005 INCIDENT REPORT' in category_key:
                incident_rows.append({
                    'row_idx': idx,
                    'json_data': json_data,
                    'ParentID': row.get('ParentID', ''),
                    'IngestedAt': row.get('IngestedAt', '')
                })
        except Exception as e:
            continue
    
    print(f"   🎯 Found {len(incident_rows)} incident reports")
    
    if not incident_rows:
        print("   ⚠️ No incident reports found containing category_key '005 INCIDENT REPORT'")
        exit(0)
    
    # ========================================================================
    # STEP 2: Extract fields from JSON
    # ========================================================================
    
    print("\n⚔️ [EXTRACTING] Extracting incident fields from JSON...")
    
    results = []
    
    for item in incident_rows:
        try:
            json_data = item['json_data']
            incident = json_data.get('incident', {})
            task = incident.get('task', {})
            
            # Extract task_unique_id
            task_unique_id = safe_json_get(task, 'unique_id')
            
            # Extract basic fields
            incident_title = safe_json_get(task, 'title')
            sitename = safe_json_get(task, 'site.name')
            description_fallback = safe_json_get(task, 'description')
            status_id = safe_json_get(task, 'status_id')
            
            # Reporter
            creator = safe_json_get(task, 'creator', {})
            reporter_first = safe_json_get(creator, 'firstname', '')
            reporter_last = safe_json_get(creator, 'lastname', '')
            reporter_fallback = f"{reporter_first} {reporter_last}".strip()
            
            # Timestamps
            occurred_at_raw = safe_json_get(task, 'occurred_at') or safe_json_get(incident, 'occurred_at')
            created_at_raw = safe_json_get(task, 'created_at') or safe_json_get(incident, 'created_at')
            modified_at_raw = safe_json_get(task, 'modified_at')
            
            # File count
            media = safe_json_get(incident, 'media', [])
            file_count = len(media) if isinstance(media, list) else 0
            
            # Question answers
            qa_list = safe_json_get(incident, 'question_answers', [])
            
            # Extract HIPO status
            hipo_status = 'No'
            if isinstance(qa_list, list):
                for qa in qa_list:
                    if not isinstance(qa, dict):
                        continue
                    answer_set = qa.get('answer_set', [])
                    for ans in answer_set:
                        if not isinstance(ans, dict):
                            continue
                        mco = ans.get('answer_multiple_choice_option', {})
                        if isinstance(mco, dict):
                            mco_id = mco.get('id', '')
                            if mco_id in ['8bf35df5-b051-48a1-9096-49e3fdf3c224', 'fbe4eba8-80be-4339-a441-e6f9e28f903f']:
                                hipo_status = 'Yes'
                                break
                    if hipo_status == 'Yes':
                        break
            
            # Coalesce fields from question answers
            incident_reporter = coalesce_answers(
                qa_list,
                ['b6194c8b-e367-4eed-9d33-7adf8f7add2e', 'c572f8e0-fefd-405a-bdca-e47e7349336f',
                 '5de8f7ba-022f-4ed6-9930-1434b32251d7', '0d7e8dc1-61e9-4d93-a68d-9c6975a5c63f',
                 '502310a4-bd5f-45e3-8cb2-15b187726a7d'],
                reporter_fallback
            )
            
            incident_client = coalesce_answers(
                qa_list,
                ['a7ec4076-1727-453c-a7bb-45f4d246c8ce', 'eb126444-2db3-4d8b-985d-3a95bc0cb926',
                 '6159a8be-6b0b-45c5-8684-e8ad31e07666', '5736410a-9d3f-4b10-a1e7-e09424867051'],
                None
            )
            
            incident_category = coalesce_answers(
                qa_list,
                ['36257e30-3a92-4e86-b598-ed2dbadd925d', 'abc7727a-36da-4855-80a4-8f9cdadfa865',
                 'ce923c78-0d22-4b2c-a9b1-51eb1cffb4c3', '4f4741ca-ee95-4bfe-aa7d-a467b6716e7d',
                 '8fbba538-94f4-4e93-8607-74f029ab7d51', '5155f320-120c-438d-8863-a0ab3ffdef99'],
                None
            )
            
            incident_details = coalesce_answers(
                qa_list,
                ['700a6256-48b2-4035-accd-35d8505ea028', '680a7213-1d32-441f-9cc9-0883c000db94',
                 '546ddc4a-a538-4ea1-8f98-43fa96a2a529', '6bb7da05-39a9-456a-b04f-86a430b4d1e7',
                 '87edccf0-1c79-4d03-a242-88533b6cd189'],
                description_fallback
            )
            
            incident_immediate_actions = coalesce_answers(
                qa_list,
                ['fbaf5a09-436e-422b-8119-48d2d342af23', '1b4192e8-737b-4755-ab55-bcd990022ad1',
                 'db733b46-0f47-41ea-9fe4-9f83c70aac40', '0ef042b2-bffe-4e5f-8340-462e6144e774',
                 'fbc08d61-f1f5-41f1-99a0-7d10fa9e2326'],
                None
            )
            
            incident_updates = coalesce_answers(
                qa_list,
                ['98aa4df0-92fe-4582-8ed6-8efd3af324c9', '31ccb64d-e650-4f26-9957-8821a15ced74',
                 '38b6a3a3-4610-4e67-87f8-8e33949324fd', '33af63ea-30ba-4cad-87f5-e00b8ca0c988',
                 '7fd4cc86-5009-4929-bfbf-dbf445c44b61', 'c16ae47b-41a5-4a91-a496-16b62da09e59'],
                None
            )
            
            # Status label
            if status_id == '547ed646-5e34-4732-bb54-a199d304368a':
                task_status_label = 'OPEN'
            elif status_id == '450484b1-56cd-4784-9b49-a3cf97d0c0ad':
                task_status_label = 'RESOLVED'
            else:
                task_status_label = status_id
            
            # Classification
            classification = classify_incident(incident_category, incident_details)
            
            # Build result row
            result = {
                'task_unique_id': task_unique_id,
                'Incident_Title': incident_title,
                'sitename': sitename,
                'Incident_Client': incident_client,
                'Incident_Reporter': incident_reporter,
                'Incident_Category': incident_category,
                'Incident_Details': incident_details,
                'Incident_Immediate_Actions': incident_immediate_actions,
                'Incident_Updates': incident_updates,
                'HIPO_Status': hipo_status,
                'Incident_Classification': classification,
                'File_Count': file_count,
                'Task_Status_Label': task_status_label,
                'occurred_at': occurred_at_raw,
                'created_at': created_at_raw,
                'modified_at': modified_at_raw,
                'IngestionTimestamp': item.get('IngestedAt', '')
            }
            
            results.append(result)
            
        except Exception as e:
            print(f"      ⚠️ Row failed: {e}")
            continue
    
    # ========================================================================
    # STEP 3: Create DataFrame and deduplicate
    # ========================================================================
    
    print("\n⚔️ [BUILDING DATAFRAME] Creating results...")
    
    df_results = pd.DataFrame(results)
    print(f"   📊 Total rows extracted: {len(df_results):,}")
    
    if 'task_unique_id' in df_results.columns:
        null_count = df_results['task_unique_id'].isna().sum()
        unique_count = df_results['task_unique_id'].nunique()
        print(f"   📋 Rows with null task_unique_id: {null_count}")
        print(f"   📋 Unique task_unique_ids: {unique_count}")
        
        if unique_count > 0:
            sample_ids = df_results['task_unique_id'].dropna().head(10).tolist()
            print(f"   📋 Sample task_unique_ids: {sample_ids}")
    
    # ========================================================================
    # STEP 4: Deduplicate by task_unique_id
    # ========================================================================
    
    print("\n⚔️ [DEDUPLICATING] Removing duplicates...")
    
    if not df_results.empty and 'task_unique_id' in df_results.columns:
        total_before = len(df_results)
        null_count = df_results['task_unique_id'].isna().sum()
        unique_count = df_results['task_unique_id'].nunique()
        
        print(f"   📊 Before deduplication:")
        print(f"      Total rows: {total_before}")
        print(f"      Rows with null task_unique_id: {null_count}")
        print(f"      Unique task_unique_ids: {unique_count}")
        
        # Convert timestamps
        df_results['modified_at'] = pd.to_datetime(df_results['modified_at'], errors='coerce')
        df_results['IngestionTimestamp'] = pd.to_datetime(df_results['IngestionTimestamp'], errors='coerce')
        
        # Sort by modified_at desc, then IngestionTimestamp desc
        df_results = df_results.sort_values(
            ['modified_at', 'IngestionTimestamp'],
            ascending=[False, False]
        )
        
        # Keep first occurrence of each task_unique_id (most recent)
        df_results = df_results.drop_duplicates(subset=['task_unique_id'], keep='first')
        
        # Sort by occurred_at desc
        df_results['occurred_at'] = pd.to_datetime(df_results['occurred_at'], errors='coerce')
        df_results = df_results.sort_values('occurred_at', ascending=False)
        
        total_after = len(df_results)
        purged = total_before - total_after
        
        print(f"   ✅ After deduplication:")
        print(f"      Total rows: {total_after}")
        print(f"      Purged duplicates: {purged}")
    
    # ========================================================================
    # STEP 5: Save to CSV
    # ========================================================================
    
    print(f"\n💾 Saving to: {output_file}")
    df_results.to_csv(output_file, index=False, encoding='utf-8')
    print(f"   ✅ Saved {len(df_results):,} rows")
    
except Exception as e:
    print(f"   ❌ Failed: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# ============================================================================
# SUMMARY
# ============================================================================

print("\n" + "=" * 80)
print("🏁 RP1 INCIDENTS REPORT COMPLETE")
print("=" * 80)

print("\n📋 REP Output Files:")
for f in os.listdir(REP_OUTPUT_PATH):
    if f.endswith('.csv'):
        p = os.path.join(REP_OUTPUT_PATH, f)
        s = os.path.getsize(p)
        try:
            df = pd.read_csv(p)
            print(f"   {f:<35} | {len(df):>6,} rows | {len(df.columns):>3} cols | {s:>10,} bytes")
        except:
            print(f"   {f:<35} | {s:>10,} bytes")