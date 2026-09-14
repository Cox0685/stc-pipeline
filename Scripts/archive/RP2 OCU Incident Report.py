#!/usr/bin/env python
# coding: utf-8

"""
OCU Incident Investigation Report - iAx Accident Investigation WiP
Exports ALL incidents under the template to Excel
Optimized for speed with 286k rows
"""

import os
import pandas as pd
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

SLV_INPUT_PATH = r"C:\Users\Thomas.Cox\OneDrive - OCU Group\Desktop\00_AST_SystemsIntegration\00_AST_DataUploads\01_STC Safety Culture\Data\SLV"
REP_OUTPUT_PATH = r"C:\Users\Thomas.Cox\OneDrive - OCU Group\Desktop\00_AST_SystemsIntegration\00_AST_DataUploads\01_STC Safety Culture\Data\REP"
os.makedirs(REP_OUTPUT_PATH, exist_ok=True)

TARGET_TEMPLATE_ID = "d291eef8e7584507b19c316536a6a36a"
TARGET_TEMPLATE_NAME = "iAx Accident Investigation WiP"

print("=" * 80)
print("🔍 OCU INCIDENT INVESTIGATION REPORT")
print("=" * 80)
print(f"📁 Input: {SLV_INPUT_PATH}")
print(f"📁 Output: {REP_OUTPUT_PATH}")
print(f"🎯 Template ID: {TARGET_TEMPLATE_ID}")
print(f"🎯 Template Name: {TARGET_TEMPLATE_NAME}")
print("=" * 80)

# ============================================================================
# COMPLETE QUESTION CIPHER - All IDs from the mapping
# ============================================================================

question_cipher = {
    "d291eef8-e758-4507-b19c-316536a6a36a": "iAx Accident Investigation WiP",
    "f3245d39-ea77-11e1-aff1-0800200c9a66": "Title Page",
    "d1cdea00-135d-4c89-ac41-77697c1cd7f9": "Site",
    "f3245d42-ea77-11e1-aff1-0800200c9a66": "Date",
    "f3245d43-ea77-11e1-aff1-0800200c9a66": "Lead Investigator",
    "c2144f6e-f71a-4b18-8ffc-7f6e79eb7597": "Incident Type",
    "9962e2c3-717d-4b94-bb87-55482a6f6208": "",
    "98956813-0232-4cfb-bb22-c4b471b9afae": "Incident Classification",
    "3a983f29-5ee8-42cb-b2a9-149e305f4617": "",
    "75de490a-e6d4-4bc5-bf50-971172f96c22": "Date & Time of Incident",
    "1b8206c7-456a-4be5-b1bb-d7eb31f8c60c": "Date Investigation Commenced",
    "f3245d44-ea77-11e1-aff1-0800200c9a66": "Location",
    "d28bb11c-9488-4f7d-8580-c942dbb9648f": "Category 5 Issue Reference Number",
    "417be0c8-0568-4651-8bfb-69c8d3672895": "Technology",
    "b6d2420c-48f1-473d-aaae-2673ad76e912": "Examine equipment, plant, tools, materials, design, and engineering factors that contributed to the incident.",
    "0c0e579d-62a9-483e-a0ee-f4b0bcee9620": "Was any equipment, plant or machinery involved in the incident?",
    "76159833-7b7d-4b4d-9dcf-5ff42dc37923": "Identify the equipment / plant / machinery involved",
    "99492f6f-7420-445e-bd0e-2ed3d7733afb": "Was the equipment fit for purpose and correctly specified?",
    "f6fa67a1-ab72-473f-b1fe-d9155bcba5f3": "Was the equipment properly maintained and in good working order?",
    "ae8ef5b9-8cda-4718-bd36-a1697e8ccc48": "Describe any defects, failures or anomalies identified with the equipment",
    "345079b0-b42d-429d-a382-2eff2c412d01": "Were design or engineering deficiencies a contributing factor?",
    "d275d9c6-970f-4fa2-b945-373528c115d7": "Describe the design or engineering issues identified",
    "dbc8ce56-1438-41d7-8120-f5cfcc755ea6": "Were materials, substances or chemicals a contributing factor?",
    "7fddeda8-33d6-4d96-bceb-be9ea69f6f6d": "Describe the material / substance issues identified",
    "c06b6142-03f9-40b6-844a-040d81c2349d": "Technology causal factors summary",
    "c784bb73-57b3-4a8e-b55f-ea72fb1fdd3c": "Attach photographs of equipment / plant involved",
    "89977e13-b730-47e3-a46c-e2879bdf6dad": "Organisation",
    "ba4fab84-aea2-419c-85a2-efc1b3724669": "Examine management systems, organisational culture, resource allocation, supervision, and policy as contributing factors.",
    "77e0e8ac-2a28-4f44-b984-c8640ac850e0": "Were management systems or policies inadequate or absent?",
    "03a600f6-260a-4ec3-af94-26ff1eca51b5": "Describe the management system / policy gaps identified",
    "690c9313-762c-447b-8f55-18bf9e6e44ec": "Was supervision adequate at the time of the incident?",
    "b5211b52-2fa4-41f6-aaf2-44856cfdbd13": "Describe any supervision failures or gaps",
    "eb0cadac-36a9-44c9-a3da-f52c8cb156f9": "Were adequate resources (people, time, equipment) provided for the task?",
    "7a99050b-0ee4-4dd5-b0f5-0d47583f5d1c": "Describe resource deficiencies identified",
    "83cadd2e-072c-4ac1-b054-a18495e35289": "Did organisational culture, pressures or priorities contribute to the incident?",
    "31a4a4f7-717e-4be0-86b9-4217b9e95984": "Describe the cultural / pressure factors identified",
    "66be28ca-7830-4e07-bbfd-dafbbf1df05c": "Was communication within the organisation a contributing factor?",
    "0a0e364d-8fb9-459f-a88d-c3ef0e478559": "Describe the communication failures identified",
    "45a7c198-0602-46ed-b802-413fe02a9408": "Organisation causal factors summary",
    "cd743693-d8b0-4b53-b723-7d876ef37183": "Personnel",
    "d08d58e7-12b4-4bb0-b5a0-80268fa4ba96": "Examine human behaviour, competence, training, physical and mental condition, and individual decisions as contributing factors.",
    "fe9a8d76-a7b1-4988-813e-2c1830b4ecb2": "Was human error a contributing factor?",
    "b65b44ae-0b6b-46c6-964b-c902f219217e": "Describe the human error(s) identified",
    "79b790fe-32f3-45a7-80b1-dafda52114df": "Were the individuals involved adequately trained and competent for the task?",
    "992f4241-dc1c-47dc-aff4-a418a246c456": "Describe any training or competency gaps identified",
    "dc4fff6a-be85-428e-930f-7592c6664e2d": "Was fatigue, stress, or personal health a contributing factor?",
    "ef57a235-3727-43c0-9317-805cbc943c88": "Describe the fatigue / stress / health factors identified",
    "55e04d03-b0d3-442d-9b18-a478c3aedfd1": "Did the individual(s) deviate from the established procedure?",
    "1d5dfe0a-8780-4648-b6a9-3b5a5c15b19b": "Was the deviation intentional or unintentional?",
    "a3b66d08-1510-4e32-9e0c-cb1c8d9f5ed8": "Explain the deviation and the reason for it",
    "b7b79f5d-a357-4dad-a04d-d34591c2fa97": "Was appropriate Personal Protective Equipment (PPE) worn?",
    "e1c395ae-4f18-491c-9790-1aa6dc0af937": "Describe any PPE failures or non-compliance",
    "87a6d227-9b3a-471e-b6bd-4ae3bb3d22d1": "People causal factors summary",
    "8e78364c-a976-40a0-8049-7254f418956e": "Systemic",
    "8af0a018-e74d-4c09-ac7e-eac00519a923": "Examine safety management systems, permit to work, risk assessments, audit and inspection processes as contributing factors.",
    "de79683e-f0d1-4c7c-b2d4-d4f8f4953e3b": "Was a risk assessment in place for the task being carried out?",
    "3aecf268-f114-4ab0-b554-f2284d4fd75b": "Was the risk assessment suitable and sufficient?",
    "5e4581ff-e478-4399-97f9-44c9704631d5": "Describe any deficiencies in the risk assessment",
    "7217a0ff-c8ac-4bdf-8a3f-6cb03730c2c7": "Was a Permit to Work (PTW) or safe system of work in place?",
    "28223ac4-e3c7-450a-bdb6-ee871918ba8b": "Was the PTW / safe system of work correctly followed?",
    "47bf869f-da90-4aed-a074-9b337725306c": "Describe any PTW or safe system of work failures",
    "481a73ea-51c8-407c-b75d-4f9f364795c2": "Had previous audits or inspections identified relevant hazards or concerns?",
    "58a70a4f-2347-4195-8836-63aad4809823": "Describe previous audit or inspection findings that were relevant",
    "53a0d417-230f-4f5a-9913-68dbe68bb468": "Were emergency response procedures adequate and followed?",
    "aec11d42-16de-4a80-bda6-be51cba6679d": "Describe any emergency response system failures",
    "54c8eab8-d732-45ea-a947-34b7f644b7d8": "System causal factors summary",
    "8004b761-6cc5-48e0-b7ef-0f297786da36": "Environmental",
    "d4c1a10d-ed7d-48b3-aa87-eaca7f5dc0b0": "Examine physical workplace conditions, weather, housekeeping, lighting, noise, and other environmental factors as contributors to the incident.",
    "d32a0c8d-78cb-46de-9c7c-95b3a53ba57d": "Were weather or external environmental conditions a contributing factor?",
    "b7125c58-1e81-4c66-b014-5ea1431feadd": "Describe the weather / environmental conditions at the time",
    "e57b0d7e-38b6-4616-a919-76b1a9696c93": "Was the work area / workplace layout a contributing factor?",
    "b4fe0028-39a7-499b-8134-f9c2e5b7d6dd": "Describe any workplace layout or housekeeping issues identified",
    "b502e025-3f41-427c-af1c-214162f03dbb": "Was lighting a contributing factor?",
    "09285781-8cfb-466e-976d-52fbff77d649": "Was noise a contributing factor?",
    "bb62d47f-2eb8-42bf-8fb2-5c48828862d8": "Were temperature or atmospheric conditions a contributing factor?",
    "4757c367-0062-4ca5-bad5-50147a65bf87": "Describe temperature / atmospheric conditions",
    "0f3d1b49-836c-46e6-b239-6ecd370eae12": "Was congestion, restricted access or working at height a contributing factor?",
    "416abfcb-2fb8-44d6-bfd1-00b3b062924d": "Describe access / height / congestion factors identified",
    "e42ab586-db50-417b-99c1-0e36228be338": "Attach photographs of the environmental conditions at the scene",
    "fe7ff7b6-02c1-4305-ac4b-9b6e8e2b8cde": "Environment causal factors summary",
    "90316fca-ccde-4b90-966e-5e0b0f5088c5": "Timeline",
    "8a6b4199-eeb0-4f8b-b71e-9c89384527b3": "Construct a clear, chronological sequence of events leading up to, during, and immediately after the incident. Be factual and objective.",
    "b8be6190-89fd-4867-a8ee-dd8e2ade9b2d": "Timeline Start: When did normal operations begin?",
    "9998f93c-b96b-4a8d-8ac1-bcdd335be5d9": "Describe the sequence of events leading up to the incident",
    "2d6242d5-a026-4918-b30b-179a8ae934b9": "Exact date and time of the incident trigger event",
    "a3dc0c70-abac-4b60-adfa-51f95cea3763": "Describe the trigger event (what immediately caused the incident)",
    "0c845f66-2c80-48cd-bd46-7c849dbe78c3": "Describe what happened immediately after the incident",
    "4ce03ee5-3c4c-4a7c-b5bb-367c2e41ff09": "What emergency response / immediate actions were taken?",
    "a253f11e-1d9d-44ff-82f1-d0831c1c1339": "Date and time emergency response was initiated",
    "df5e68fd-15fd-405d-9755-b6b8384e3550": "Who was notified and when? (list individuals and times)",
    "76d34d33-5dc3-40ae-b9da-306786723b2e": "Attach timeline diagram, photographs or supporting evidence",
    "42a7f7da-a3e3-4d9e-b9a9-ab97599ebd7b": "Root Cause Analysis",
    "182bc69b-d756-4a9d-b050-f7107101e5ed": "Based on the TOPSET causal factor analysis and barrier analysis, identify the root causes of the incident. Root causes are the fundamental, underlying reasons — not just the immediate trigger.",
    "ddf96b34-e90c-460f-a80a-ad00c6fa3cb6": "Root Cause 1: Describe the first root cause identified",
    "1058dc58-5ae4-445d-9f5b-48bc789a5796": "Root Cause 1 TOPSET Category",
    "0138acae-1d0f-4ab7-bd4d-2d7091fa9573": "Root Cause 2: Describe the second root cause identified (if applicable)",
    "178e19e7-82e5-4eb4-a876-6ff62415065b": "Root Cause 2 TOPSET Category",
    "1ad865ad-b3f0-4edd-a052-e51ff2d16b60": "Root Cause 3: Describe the third root cause identified (if applicable)",
    "06c2e942-7e17-4dd9-b30c-55da55214113": "Root Cause 3 TOPSET Category",
    "1bf6c530-879d-49dc-a5e3-9ddabd6a27cc": "Contributing Causes: List any additional contributing causes",
    "5a54228a-e569-4fc3-98e0-3f4bb40bdfb5": "Overall root cause analysis narrative",
    "93f83333-4c04-41e0-befe-e77c68196c00": "Corrective Actions & Recommendations",
    "97ef8e05-a394-4083-99bc-ba02d47f066b": "For each root cause and contributing factor identified, define corrective actions to prevent recurrence. Each action should be SMART: Specific, Measurable, Achievable, Relevant, and Time-bound.",
    "f5f9dd0a-a742-469f-940b-28aa15fbd7e8": "Corrective Action 1: Describe the action required",
    "61fbeee9-01e5-444d-9032-2db0595bef67": "Action 1 Priority",
    "02ae07cb-5f8e-4b56-8c5a-6207d161ae46": "Action 1: Person responsible",
    "69e6dc61-ddbb-4c2a-ba58-032b5c28ba40": "Action 1: Target completion date",
    "23e62a08-e304-401e-8d3f-276267ce64c9": "Corrective Action 2: Describe the action required",
    "82704dee-7f07-4c50-89fb-3e06b560c0a8": "Action 2 Priority",
    "a55ded59-6e01-4310-9da1-c1679d1ee7e9": "Action 2: Person responsible",
    "e7e68d0e-8e95-47fe-b31f-0a1557e4f627": "Action 2: Target completion date",
    "ad229f30-633a-445d-bd85-1ac90588d484": "Corrective Action 3: Describe the action required",
    "372e2af4-1cfc-4f67-bee8-a1d7968c0052": "Action 3 Priority",
    "936bdb2a-ed6d-4ae3-88ca-22cb161d17f9": "Action 3: Person responsible",
    "ab3c3e89-e3f9-44c6-b08f-87016fd7f120": "Action 3: Target completion date",
    "c4320120-b43d-4c92-baaf-17216a447f6f": "Additional corrective actions or recommendations",
    "46f0f838-bcba-45af-8809-ad64f8e5b943": "Has a lessons learned communication been planned?",
    "e776e8b8-2fa6-4dee-a94f-d1108f64dbd9": "Describe the lessons learned communication plan and audience",
    "c7e2b1a8-1086-4ca7-9122-030a569371dd": "Target date for lessons learned communication",
    "eba7b234-9861-4397-b184-34e19a7d4b44": "Investigation sign-off: Investigator's summary statement",
    "085dc996-3162-49cc-8f60-77565f5525eb": "Lead Investigator Signature",
    "af1b4b52-9084-47e4-a613-e09d0a498074": "Date of Investigation Sign-off",
    "fbd0db3d-889f-4c0d-93c3-6173f4f445cb": "Approval",
    "a9eb9b25-51ea-42af-a4ef-2f0e42f81805": "Date and time of approval",
    "d9b6dd7a-d990-44b8-a148-39921d98458d": "Approval Justification",
    "0c8210a6-a80c-4a3d-bc43-290f3d5f5d1b": "Approver's signature"
}

def get_question_label(question_id):
    """Get the question label from the cipher"""
    if pd.isna(question_id):
        return None
    
    question_id = str(question_id).strip()
    
    # Try exact match first
    if question_id in question_cipher:
        label = question_cipher[question_id]
        # Skip empty labels
        if label == "":
            return None
        return label
    
    # Try without hyphens
    clean_id = question_id.replace("-", "")
    for key, label in question_cipher.items():
        if key.replace("-", "") == clean_id:
            if label == "":
                return None
            return label
    
    return None  # Skip unknown questions

# ============================================================================
# STEP 1: READ AUDITS_SEARCH ONLY (SMALL FILE)
# ============================================================================

print("\n📂 Reading audits_search...")
audits_path = os.path.join(SLV_INPUT_PATH, "audits_search.csv")
df_audits = pd.read_csv(audits_path, dtype=str, low_memory=False)
print(f"   ✓ Loaded {len(df_audits):,} rows")

# ============================================================================
# STEP 2: FILTER TO TARGET TEMPLATE
# ============================================================================

print(f"\n🔍 Filtering to template: {TARGET_TEMPLATE_NAME}...")

# Filter by template_id and template_name
df_incidents = df_audits[
    (df_audits['template_id'] == TARGET_TEMPLATE_ID) & 
    (df_audits['template_name'] == TARGET_TEMPLATE_NAME)
].copy()

incident_ids = df_incidents['id'].tolist()
print(f"   ✅ Found {len(incident_ids)} incidents")

if len(incident_ids) == 0:
    print("   ❌ No incidents found!")
    exit(1)

# Show the incidents found
print("\n   📋 Incidents found:")
for idx, row in df_incidents.iterrows():
    site = row.get('name', row.get('site_name', row.get('site', 'Unknown')))
    print(f"      - ID: {row.get('id', 'Unknown')} | Site: {site}")

# ============================================================================
# STEP 3: READ ONLY NEEDED COLUMNS FROM INSPECTIONS_ANSWERS
# ============================================================================

print(f"\n📂 Reading inspections_answers (optimized)...")

# Only read these columns to save memory and time
needed_cols = [
    '_ParentID',
    'result_question_id',
    'result_text_answer_answer',
    'result_question_answer_note',
    'result_datetime_answer_answer',
    'result_checkbox_answer_answer',
    'result_signature_answer_name',
    'result_site_answer_name'
]

inspections_path = os.path.join(SLV_INPUT_PATH, "inspections_answers.csv")

# Read in chunks to process large file efficiently
chunk_size = 50000
df_answers_list = []

print(f"   Reading in chunks of {chunk_size:,} rows...")

chunk_count = 0
for chunk in pd.read_csv(inspections_path, 
                         dtype=str, 
                         low_memory=False,
                         usecols=needed_cols,
                         chunksize=chunk_size):
    
    chunk_count += 1
    # Only keep rows that match our incident IDs
    chunk_filtered = chunk[chunk['_ParentID'].isin(incident_ids)]
    
    if len(chunk_filtered) > 0:
        df_answers_list.append(chunk_filtered)
        print(f"   Chunk {chunk_count}: Found {len(chunk_filtered):,} matching rows")
    
    # Free memory
    del chunk

if df_answers_list:
    df_answers = pd.concat(df_answers_list, ignore_index=True)
    print(f"   ✅ Loaded {len(df_answers):,} matching answers")
else:
    print("   ❌ No answers found for these incidents!")
    exit(1)

# ============================================================================
# STEP 4: MAP QUESTIONS AND CREATE PIVOTED REPORT
# ============================================================================

print(f"\n🔑 Mapping questions and creating pivoted report...")

# Map question IDs to labels
df_answers['Question'] = df_answers['result_question_id'].apply(get_question_label)

# Remove rows with unknown or empty questions
df_answers = df_answers[df_answers['Question'].notna()].copy()

# Combine answer columns into single Answer column
answer_cols = ['result_text_answer_answer', 'result_question_answer_note', 
               'result_datetime_answer_answer', 'result_checkbox_answer_answer',
               'result_signature_answer_name', 'result_site_answer_name']

df_answers['Answer'] = None
for col in answer_cols:
    if col in df_answers.columns:
        df_answers['Answer'] = df_answers['Answer'].fillna(df_answers[col])

# Keep only needed columns
df_answers = df_answers[['_ParentID', 'Question', 'Answer']]

# Pivot - each question becomes a column
print(f"\n📊 Pivoting data...")

pivot_df = df_answers.pivot_table(
    index='_ParentID',
    columns='Question',
    values='Answer',
    aggfunc='first'
).reset_index()

pivot_df = pivot_df.rename(columns={'_ParentID': 'incident_id'})

# ============================================================================
# STEP 5: ADD INCIDENT METADATA
# ============================================================================

print(f"\n📊 Adding incident metadata...")

# Get available columns in df_incidents
available_cols = df_incidents.columns.tolist()

# Find the right column names for metadata
meta_cols = ['id']
name_col = None

# Find the column that contains site/name info
for col in ['name', 'site_name', 'site', 'client_site']:
    if col in available_cols:
        name_col = col
        break

# Find author column
author_col = None
for col in ['author_name', 'author', 'created_by']:
    if col in available_cols:
        author_col = col
        break

# Add columns we found
if name_col:
    meta_cols.append(name_col)
if author_col:
    meta_cols.append(author_col)

# Add other common columns
for col in ['conducted_on', 'created_at', 'date_completed', 'template_name']:
    if col in available_cols:
        meta_cols.append(col)

print(f"   Using metadata columns: {meta_cols}")

df_incidents_meta = df_incidents[meta_cols].copy()
df_incidents_meta = df_incidents_meta.rename(columns={'id': 'incident_id'})

# Rename name column to site_name if it exists
if name_col and name_col != 'site_name':
    df_incidents_meta = df_incidents_meta.rename(columns={name_col: 'site_name'})

# Merge with pivoted data
final_df = df_incidents_meta.merge(pivot_df, on='incident_id', how='left')

# Reorder columns - put metadata first
meta_cols_renamed = ['incident_id', 'site_name']
if author_col:
    meta_cols_renamed.append(author_col if author_col != 'author_name' else 'author_name')
meta_cols_renamed.extend(['conducted_on', 'created_at', 'date_completed', 'template_name'])

# Only include columns that exist
existing_meta = [col for col in meta_cols_renamed if col in final_df.columns]
other_cols = [col for col in final_df.columns if col not in existing_meta]
final_df = final_df[existing_meta + other_cols]

# ============================================================================
# STEP 6: SAVE TO EXCEL
# ============================================================================

print(f"\n💾 Saving to Excel...")

excel_path = os.path.join(REP_OUTPUT_PATH, "ocu_incident_report.xlsx")

# Convert all columns to string for Excel to avoid type issues
for col in final_df.columns:
    final_df[col] = final_df[col].fillna('').astype(str)

# Use openpyxl engine
with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
    final_df.to_excel(writer, sheet_name='Incident Report', index=False)
    
    # Auto-adjust column widths
    workbook = writer.book
    worksheet = writer.sheets['Incident Report']
    
    for column in worksheet.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        worksheet.column_dimensions[column_letter].width = adjusted_width

print(f"   ✅ Saved: {excel_path}")
print(f"   📊 {len(final_df)} rows, {len(final_df.columns)} columns")

# ============================================================================
# SUMMARY
# ============================================================================

print("\n" + "=" * 80)
print("🏁 OCU INCIDENT INVESTIGATION REPORT COMPLETE")
print("=" * 80)

print(f"\n📋 Summary:")
print(f"   Template: {TARGET_TEMPLATE_NAME}")
print(f"   Incidents found: {len(incident_ids)}")
print(f"   Questions mapped: {len(final_df.columns) - len(existing_meta)}")
print(f"   Output file: {excel_path}")

print("\n✅ Report generation completed successfully!")
print("=" * 80)