#!/usr/bin/env python
# coding: utf-8

"""
Unified Safety Data Pipeline:
1. Reads gld_issues_answers.csv once.
2. Calculates Safety / Hazard Observations by year from SOR categories.
3. Filters for Incident Reports ('005 INCIDENT REPORT'), extracts questions, pivots, and saves rp2_annual incident data.csv.
4. Compiles the Master Annual Safety Performance Table (2022-2026) using placeholder hours and calculated metrics, saving to rp3_annual_safety_metrics_table.csv.
"""

import os
import pandas as pd
import numpy as np
import re
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

GLD_INPUT_PATH = r"C:\Users\Thomas.Cox\OneDrive - OCU Group\Desktop\00_AST_SystemsIntegration\00_AST_DataUploads\01_STC Safety Culture\Data\GLD"
REP_OUTPUT_PATH = r"C:\Users\Thomas.Cox\OneDrive - OCU Group\Desktop\00_AST_SystemsIntegration\00_AST_DataUploads\01_STC Safety Culture\Data\REP"

os.makedirs(REP_OUTPUT_PATH, exist_ok=True)

incident_output_file = os.path.join(REP_OUTPUT_PATH, "rp2_annual incident data.csv")
metrics_output_file = os.path.join(REP_OUTPUT_PATH, "rp3_annual_safety_metrics_table.csv")

TARGET_YEARS = [2022, 2023, 2024, 2025, 2026]

# Placeholder hours worked dictionary
hours_worked_dict = {
    2022: 928900,
    2023: 933059,
    2024: 0,
    2025: 1268532,
    2026: 1107375
}

print("=" * 80)
print("⚔️ UNIFIED SAFETY DATA PIPELINE: SOR COUNTS, INCIDENT PIVOT & ANNUAL METRICS")
print("=" * 80)

# ============================================================================
# QUESTION MAPPINGS
# ============================================================================

question_mapping = {
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

question_alias_mapping = {
    "Do not answer this question - SAFETY DEPARTMENT USE ONLY:": "Lost Time",
    "In the event of a Near Miss / Unplanned Event, could this incident have resulted in very serious harm to persons, property or the environment": "HIPO?",
    "In the event of a Near Miss / Unplanned Event, could this incident have resulted in very serious harm to persons, property or the environment?": "HIPO?",
    "In the event of an accident, which of the following applies:": "Treatment Required",
    "Incident Category": "Category",
    "Incident Details": "Details",
    "Name of Person Reporting Incident": "Reporter",
    "Name of Person Reporting the Incident": "Reporter",
    "Name of Site Client:": "Site Client",
    "Other Information of Note?": "Further Information",
    "Please add any other information of note?": "Further Information",
    "SAFETY DEPARTMENT USE ONLY:": "Lost Time",
    "What immediate action has been taken to prevent any reoccurrence?": "Immediate Actions",
    "What immediate action has been taken to prevent reoccurrence?": "Immediate Actions"
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    input_file = os.path.join(GLD_INPUT_PATH, "gld_issues_answers.csv")
    
    if not os.path.exists(input_file):
        print(f"❌ Input file not found: {input_file}")
        return
        
    print(f"\n📂 Reading master dataset: {os.path.basename(input_file)}")
    df = pd.read_csv(input_file, dtype=str, low_memory=False)
    print(f"   ✅ Loaded {len(df):,} rows, {len(df.columns)} columns")

    # Parse dates across dataset using dayfirst=True for UK date format (DD/MM/YYYY)
    if 'task_occurred_at' in df.columns:
        df['parsed_date'] = pd.to_datetime(df['task_occurred_at'], dayfirst=True, errors='coerce')
        df['Year'] = df['parsed_date'].dt.year.fillna(0).astype(int)
    else:
        print("❌ 'task_occurred_at' column missing!")
        return

    # ============================================================================
    # STEP 1: CALCULATE SAFETY / HAZARD OBSERVATIONS (SOR Categories)
    # ============================================================================
    print("\n⚔️ Step 1: Calculating Safety / Hazard Observations (SOR Counts)...")
    sor_categories = [
        "001 SOR - POSITIVE",
        "002 SOR - NEGATIVE",
        "003 ENVIRONMENTAL SOR - POSITIVE",
        "004 ENVIRONMENTAL SOR - NEGATIVE"
    ]

    sor_counts_dict = {year: 0 for year in TARGET_YEARS}
    if 'category_key' in df.columns:
        df_sor = df[df['category_key'].isin(sor_categories) & df['Year'].isin(TARGET_YEARS)]
        sor_counts = df_sor.groupby('Year').size().to_dict()
        for year in TARGET_YEARS:
            sor_counts_dict[year] = int(sor_counts.get(year, 0))
            print(f"   📊 Year {year} Safety / Hazard Observations: {sor_counts_dict[year]:,}")
    else:
        print("⚠️ 'category_key' column not found for SOR counting.")

    # ============================================================================
    # STEP 2: FILTER & PIVOT INCIDENT REPORTS (005 INCIDENT REPORT)
    # ============================================================================
    print("\n⚔️ Step 2: Extracting and pivoting Incident Reports ('005 INCIDENT REPORT')...")
    category_key_filter = "005 INCIDENT REPORT"
    df_filtered = df[df['category_key'] == category_key_filter].copy()
    print(f"   🎯 Found {len(df_filtered):,} incident rows matching filter")

    metadata_cols = [
        'task_site_name', 'task_status_id', 'task_site_area', 'task_unique_id',
        'task_created_at', 'task_modified_at', 'task_occurred_at',
        'task_creator_firstname', 'task_creator_lastname', 'task_creator_user_id',
        'category_key'
    ]
    existing_metadata = [col for col in metadata_cols if col in df_filtered.columns]
    question_id_cols = [col for col in df_filtered.columns if col.endswith('question_id') and 'question_data_id' not in col]

    extracted_data = []
    for idx, row in df_filtered.iterrows():
        metadata = {col: row.get(col, '') for col in existing_metadata}
        for q_col in question_id_cols:
            match = re.search(r'question_answers_(\d+)_question_id', q_col)
            if not match:
                continue
            q_idx = int(match.group(1))
            question_id = row.get(q_col, '')
            if pd.isna(question_id) or not str(question_id).strip():
                continue
            
            question_text = question_mapping.get(str(question_id).strip(), '')
            if not question_text:
                continue
            
            answer_value = ''
            text_col = f'question_answers_{q_idx}_answer_set_0_answer_text_text'
            if text_col in df_filtered.columns:
                val = row.get(text_col, '')
                if pd.notna(val) and str(val).strip():
                    answer_value = str(val).strip()
            
            if not answer_value:
                mc_col = f'question_answers_{q_idx}_answer_set_0_answer_multiple_choice_option_text'
                if mc_col in df_filtered.columns:
                    val = row.get(mc_col, '')
                    if pd.notna(val) and str(val).strip():
                        answer_value = str(val).strip()
            
            if not answer_value:
                for a_col in df_filtered.columns:
                    if f'question_answers_{q_idx}_answer_set_' in a_col and '_answer_text_text' in a_col:
                        val = row.get(a_col, '')
                        if pd.notna(val) and str(val).strip():
                            answer_value = str(val).strip()
                            break
            
            if not answer_value:
                for a_col in df_filtered.columns:
                    if f'question_answers_{q_idx}_answer_set_' in a_col and '_answer_multiple_choice_option_text' in a_col:
                        val = row.get(a_col, '')
                        if pd.notna(val) and str(val).strip():
                            answer_value = str(val).strip()
                            break
            
            if answer_value:
                new_row = metadata.copy()
                new_row['question_text'] = question_text
                new_row['answer'] = answer_value
                extracted_data.append(new_row)

    if extracted_data:
        df_extracted = pd.DataFrame(extracted_data)
        df_extracted['question_alias'] = df_extracted['question_text'].map(lambda x: question_alias_mapping.get(x, x))
        pivot_df = df_extracted.pivot_table(
            index=existing_metadata,
            columns='question_alias',
            values='answer',
            aggfunc='first'
        ).reset_index()
        pivot_df.columns.name = None
        
        expected_columns = [
            'Lost Time', 'HIPO?', 'Treatment Required', 'Immediate Actions',
            'Category', 'Details', 'Reporter', 'Site Client', 'Further Information'
        ]
        for col in expected_columns:
            if col not in pivot_df.columns:
                pivot_df[col] = ''
        
        pivot_df.to_csv(incident_output_file, index=False, encoding='utf-8')
        print(f"   ✅ Saved incident report dataset to: {incident_output_file} ({len(pivot_df):,} rows)")
    else:
        print("   ⚠️ No incident answers extracted.")
        pivot_df = pd.DataFrame()

    # ============================================================================
    # STEP 3: BUILD ANNUAL SAFETY PERFORMANCE TABLE (rp3)
    # ============================================================================
    print("\n⚔️ Step 3: Compiling Master Annual Safety Performance Matrix...")
    df_target_inc = df[df['category_key'] == category_key_filter].copy()
    
    metrics_data = {year: {} for year in TARGET_YEARS}

    for year in TARGET_YEARS:
        df_y = df_target_inc[df_target_inc['Year'] == year]
        hours = hours_worked_dict.get(year, 0)
        
        # 1. Hours Worked
        metrics_data[year]['Hours Worked'] = f"{hours:,}" if hours > 0 else "0"
        
        # 2. Fatalities
        metrics_data[year]['Fatalities'] = 0
        
        # Filter pivoted data for the current year
        df_y_pivot = pivot_df[pd.to_datetime(pivot_df['task_occurred_at'], dayfirst=True, errors='coerce').dt.year.fillna(0).astype(int) == year] if not pivot_df.empty else pd.DataFrame()
        
        # 3. Lost Time Incidents
        lti_count = 0
        if not df_y_pivot.empty and 'Lost Time' in df_y_pivot.columns:
            for val in df_y_pivot['Lost Time'].dropna():
                v_str = str(val).strip().lower()
                if v_str and v_str != 'no lost time' and v_str != 'nan':
                    lti_count += 1
        metrics_data[year]['Lost Time Incidents'] = lti_count
        
        # 4. Medical Treatment Incidents
        mti_count = 0
        mti_mapping = {
            "No Treatment or First  Aid was required": "No",
            "Taken to Hospital as a precaution": "Yes",
            "Taken to Hospital for Minor Treatment": "Yes",
            "No Treatment / First  Aid given": "Yes",
            "No Treatment or First  Aid required": "No",
            "Minor First Aid": "Yes",
            "Take to Hospital for Minor Treatment": "Yes"
        }
        if not df_y_pivot.empty and 'Treatment Required' in df_y_pivot.columns:
            for val in df_y_pivot['Treatment Required'].dropna():
                v_clean = str(val).strip()
                if mti_mapping.get(v_clean, "No") == "Yes":
                    mti_count += 1
        metrics_data[year]['Medical Treatment Incidents'] = mti_count
        
        # 5. Reportable Incidents
        metrics_data[year]['Reportable Incidents'] = len(df_y_pivot) if not df_y_pivot.empty else len(df_y)
        
        # 6. Near Misses
        near_miss_count = 0
        if not df_y_pivot.empty and 'Category' in df_y_pivot.columns:
            near_miss_count = df_y_pivot['Category'].str.contains("Near Miss", case=False, na=False).sum()
        metrics_data[year]['Near Misses'] = near_miss_count
        
        # 7. Reportable Dangerous Occurrence
        dang_occ_count = 0
        if not df_y_pivot.empty and 'Category' in df_y_pivot.columns:
            dang_occ_count = df_y_pivot['Category'].str.contains("Accident", case=False, na=False).sum()
        metrics_data[year]['Reportable Dangerous Occurrence'] = dang_occ_count
        
        # 8. Safety / Hazard Observations (Populated from SOR counts)
        sor_count = sor_counts_dict.get(year, 0)
        metrics_data[year]['Safety / Hazard Observations'] = f"{sor_count:,}" if sor_count > 0 else "0"
        
        # 9-10. Regulatory Placeholders
        metrics_data[year]['Prosecutions as a result of Health and Safety failings'] = "0"
        metrics_data[year]['Formal notices served by any regulatory body'] = "0"
        
        # 11. LTIFR: (Lost Time Incidents * 100,000) / Hours Worked
        if hours > 0:
            ltifr = (lti_count * 100000) / hours
            metrics_data[year]['Lost Time Incident Frequency rate (LTIFR)'] = round(ltifr, 2)
        else:
            metrics_data[year]['Lost Time Incident Frequency rate (LTIFR)'] = 0.0

    metric_names = [
        'Hours Worked',
        'Fatalities',
        'Lost Time Incidents',
        'Medical Treatment Incidents',
        'Reportable Incidents',
        'Near Misses',
        'Reportable Dangerous Occurrence',
        'Safety / Hazard Observations',
        'Prosecutions as a result of Health and Safety failings',
        'Formal notices served by any regulatory body',
        'Lost Time Incident Frequency rate (LTIFR)'
    ]

    table_rows = []
    for metric in metric_names:
        row = {'Metric': metric}
        for year in TARGET_YEARS:
            row[str(year)] = metrics_data[year].get(metric, '0')
        table_rows.append(row)

    result_table = pd.DataFrame(table_rows)

    print("\n" + "=" * 80)
    print("🛡️ MASTER SAFETY PERFORMANCE MATRIX (2022-2026)")
    print("=" * 80)
    print(result_table.to_string(index=False))

    result_table.to_csv(metrics_output_file, index=False, encoding='utf-8')
    print(f"\n✅ Master safety metrics table successfully forged and saved at: {metrics_output_file}")

if __name__ == "__main__":
    main()