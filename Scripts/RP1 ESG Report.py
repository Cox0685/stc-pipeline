#!/usr/bin/env python
# coding: utf-8

import os
import sys
import re
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_shared"))
import azure_io

# ============================================================================
# CONFIGURATION
# ============================================================================
SLV_PREFIX = "SLV"
REP_PREFIX = "REP"

client = azure_io.get_client()

TARGET_TEMPLATE = "iA5 Weekly ESG Report"

# ============================================================================
# CIPHER DICTIONARY (EXACT UUID TO QUESTION MAPPING)
# ============================================================================
raw_question_cipher = {
    # Title Page Section
    "d1cdea00-135d-4c89-ac41-77697c1cd7f9": "Site",
    "50694cc8-85dd-4090-b0e3-a42613925dea": "Date",
    "f3245d43-ea77-11e1-aff1-0800200c9a66": "Person Completing",
    # Site Hours Section
    "ae909b3c-74d6-442d-be68-03a8c993bfd6": "Total Weekly Hours for all RJM employees (Staff, Operatives and Plant Operators)",
    "af668731-f36e-494d-b621-b6c37f38267e": "Total Weekly Hours for all Labour Only Sub Contractors & Agency staff (Inc. Cleaners)",
    "01b53098-5d5c-4328-a0ce-bec904f1edb4": "Total Weekly Hours for all External Plant Hire (operators)",
    "69991fec-a4a7-41b2-83bf-90f55ae70eea": "Total Weekly Hours for all Sub Contractors Personnel",
    "0b74faad-aede-4479-ac30-a39e144b7f6e": "Total Weekly Hours for all Client Representatives, & appointed Contractors Personnel",
    "01bb2832-6a98-47b2-b9ec-7fb6a2552d9d": "Total Weekly Hours for all Delivery Drivers",
    "01f0f844-687d-4f4e-a4f8-e6979e297495": "Total Weekly Hours for all Site Visitors",
    "53903bd9-880e-4edc-8029-d79e5332c4ce": "Total Weekly Hours for others that have not been accounted for in the above submissions",
    # HSE Statistics Section
    "ad5ca287-4960-47dc-b801-4a964d0dd839": "Number of Site Inductions Completed",
    "93db6372-2e0c-43d7-bfb7-2124f83bb080": "Number of Weekly Safety Meetings Held",
    "02faf190-6bf9-46d1-9691-eef638dbabac": "Number of Yellow Cards Issued",
    "ac19b01f-b8ab-4688-8f59-68a4dfc7daf6": "Number of Red Cards Issued",
    "bbb5ec9c-9828-430b-aa5e-c98428f414de": "Has Drug and Alcohol testing being carried out this week?",
    "f060e469-676d-412c-93da-765f5c33fdbd": "Drug Testing Logic",
    "ded16edc-95c8-4050-b142-193de4f4743d": "How many tests were carried out?",
    "4b0ffb57-b505-4e80-adf3-cb519c659cfd": "Tests Count Logic",
    "b4e5c8a1-3d10-4370-b177-e26ac6fca98c": "Insert number of non-negative results (insert 0 if all persons passed)",
    # Planet Section
    "518d5577-ec5d-4e6c-9a42-dcf35a6ba02b": "Is the site using battery or solar power generation, or value engineering, that reduces plant fuel consumption?",
    "d8f17548-f3ee-4b55-a555-8820bbcb587e": "Battery/Solar Logic",
    "87e631a9-e2b8-4e18-858f-d6385f515ccf": "Approximately how many litres of fuel were saved this week?",
    # Work (Employment & Training) Section
    "fd56623e-ac4d-484f-99b2-db5c17c768a0": "How many job opportunities were advertised this week?",
    "9e5ac622-6e83-432d-ae43-efeb8d506f0c": "Jobs Advertised Logic",
    "6c52be4a-57a1-4578-87e2-3b5b19859381": "Were any high priority groups targeted? e.g. long term unemployed, job seekers, straight from education, no/low skills",
    "055a03c1-e4cf-4dd5-a865-e5d1820c60f0": "Priority Groups Logic",
    "49ed4473-8be9-450b-9669-c76dd8065408": "Which groups were targeted?",
    "d708c5fc-c9ec-4ea0-8131-50d89437f0c1": "Were any job opportunities filled this week?",
    "58bb521d-ebe0-4425-992c-ac9ade91db73": "Jobs Filled Logic",
    "604a5a7a-45ce-4b45-9561-eb3c6edf48b9": "How many?",
    "3912fff9-16e2-4b75-a565-b133866f9459": "Were any new employees provided with training this week?",
    "b28c264c-5077-4d03-9d49-c48ff15ccf88": "Training Logic",
    "2adb5208-2e32-4daa-b544-d5f25de76404": "Total hours training provided:",
    "154554b3-4f19-480e-9a7d-6cf145815718": "Were there any apprentices working on the project this week?",
    "efc02a77-b51b-403a-abc5-d5f2f4b800cb": "Apprentices Logic",
    "d822d9a0-02f1-482b-a72d-5cfa5048c698": "Total number of days:",
    # Work (Educational Support) Section
    "52d5194b-e512-4c9c-b193-47a84556e05a": "Educational Support Instruction",
    "c4bd50f8-5369-4bac-80ad-8eb69e19c9f2": "The number of events",
    "78f5165d-db82-415c-b8df-e9880cfc5af1": "Staff hours, including preparation and travel time",
    "0ca23a46-c4e7-4c2a-9da2-1a960052f426": "The cost of labour, plant, materials or cash donation",
    "a7c89bca-1c02-49cc-aefa-a0ceb36814e7": "Describe the support that was provided? e.g. school visit, site visit, CSCS Card at School or other",
    "f0f403b9-6090-47a5-9fa1-0ea2f5b683ab": "Did the site provide a work experience placement this week?",
    "7ea02851-0cf6-405a-8630-023f3d7aa00c": "Work Experience Logic",
    "ac16d22a-5450-4c4b-9eaf-398e75ea32ad": "How many days?",
    # Economy / Supply Chain Section
    "60ede7c2-16b3-4da7-b236-6eaa8d1b7f88": "Did the site conduct any supply chain development? e.g. PCS, Meet the Buyer, Subcontractor mentoring, etc.",
    "55479538-e4e9-4da4-91de-207423d6da4d": "Supply Chain Logic",
    "9bcabd19-241a-487a-8498-64b7a16f8162": "Total number of staff hours, including travel",
    "a6ce28bb-b13b-4e47-83b9-69f2fd5839fe": "Supply Chain Instruction",
    "093c0def-910a-49dd-bd82-2c990d332bde": "SME (Between 10 and 250 employees)",
    "d8475e6f-8786-405d-9c64-924240e17649": "SME Logic",
    "4e51efbc-7a69-4a2f-8367-4777e6204b37": 'How many were local (check definition of "local" in the contract):',
    "92240c4f-9226-4d76-aa26-1b05ca3a1be7": "Micro Business (Less than 10 employees)",
    "ecd29573-e4c3-4ea5-89c2-f8cf6dba71e7": "Micro Business Logic",
    "7dd4ca5e-6d59-4a0b-a189-54b0956e2f5a": 'Micro Business Local Count (check definition of "local")',
    "6769276c-0038-4151-913e-4d135d7967ba": "Social Enterprise, Supported Business, Voluntary Organisation, Third Sector/Community Group",
    "56efe4dc-fd5e-45eb-86d9-c504ca1d47c4": "Social Enterprise Logic",
    "5e6f6663-4f62-4e4b-ae6f-99e54912fab0": 'Social Enterprise Local Count (check definition of "local")',
    # Community Section
    "83c623b3-cf0b-4160-a683-954c5174a8a5": "Did the site make any financial or non-financial donations this week, including volunteering or other Social Benefit?",
    "b962ebe2-3b6c-4f9d-a815-d312bc21ff5c": "Donations Logic",
    "f0b3cb3d-425d-4842-9ea8-e475ead2f2f0": "Cash donation",
    "ed0e8293-a3bd-4c89-8667-6b5d1bfffe72": "Cash Donation Logic",
    "6dd4a7d6-20e1-4e2d-a3aa-d26318fbf34d": "What was the value?",
    "2e762c73-6123-4c6a-b6f9-cce909963af1": "Volunteering",
    "a9a6751a-a882-4344-8705-42fe910c9270": "Volunteering Logic",
    "a73cb31d-6284-411a-adf3-80831255edf3": "How many hours?",
    "fe1da1f7-b720-4c5d-b221-49181c8d818b": "Social Benefit (EG Materials Donation, Labour, Plant)",
    "d9fe45ac-9e28-4ed0-b667-eb10ed736ce0": "Social Benefit Logic",
    "077621b9-36a0-4c81-af2a-c6449d41ddf8": "Type?",
    "dd1dc9fc-afd1-4bb9-bb2e-fbdc8570d5b6": "What was the value of this?",
}

clean_question_cipher = {
    k.replace("-", "").strip().lower(): v
    for k, v in raw_question_cipher.items()
}


# ============================================================================
# HELPER: DATE PARSER (OUTPUTS DD/MM/YYYY)
# ============================================================================
def parse_date_robust(val):
    if pd.isna(val):
        return None
    val_str = str(val).strip()
    if not val_str or val_str.lower() == "nan":
        return None

    val_str = val_str.replace(".", "/")
    date_part = val_str.split(" ")[0].split("T")[0]

    try:
        dt = pd.to_datetime(date_part, dayfirst=False, errors="coerce")
        if pd.notna(dt):
            return dt.strftime("%d/%m/%Y")
    except Exception:
        pass

    dt = pd.to_datetime(val_str, dayfirst=False, errors="coerce")
    if pd.notna(dt):
        return dt.strftime("%d/%m/%Y")
    return None


# ============================================================================
# STAGE 1: LOAD & PARSE AUDITS
# ============================================================================
print("⚔️ [STAGE 1] Loading and cleaning audits...", flush=True)

audits_search_path = f"{SLV_PREFIX}/audits_search.csv"
df_audits = client.read_csv(audits_search_path, dtype=str, low_memory=False)

df_audits["id"] = (
    df_audits["id"].str.replace("-", "", regex=False).str.strip().str.lower()
)
df_audits_filtered = df_audits[
    df_audits["template_name"] == TARGET_TEMPLATE
].copy()

# Join site list
sites_list_path = f"{SLV_PREFIX}/sites_list.csv"
if client.exists(sites_list_path):
    df_sites = client.read_csv(sites_list_path, dtype=str, low_memory=False)
    df_sites["site_uuid"] = df_sites["site_uuid"].str.strip()
    lookup_site = (
        df_sites[["site_uuid", "name"]]
        .drop_duplicates(subset=["site_uuid"])
        .rename(columns={"site_uuid": "_site_key", "name": "client_site"})
    )
    df_audits_filtered = df_audits_filtered.merge(
        lookup_site, left_on="site_id", right_on="_site_key", how="left"
    ).drop(columns=["_site_key"])


def clean_name(name):
    if pd.isna(name):
        return ""
    name_str = str(name).strip()
    if name_str and re.match(r"^[0-9]", name_str):
        return name_str.split("/")[0].strip()
    return name_str


if "client_site" not in df_audits_filtered.columns:
    df_audits_filtered["client_site"] = ""

df_audits_filtered["client_site"] = df_audits_filtered.apply(
    lambda row: (
        row["client_site"]
        if pd.notna(row.get("client_site"))
        and str(row.get("client_site")).strip() != ""
        else clean_name(row.get("name"))
    ),
    axis=1,
)

# Parse date columns
date_cols = [
    "conducted_on",
    "created_at",
    "date_completed",
    "date_modified",
    "date_started",
]
for dc in date_cols:
    if dc in df_audits_filtered.columns:
        df_audits_filtered[dc] = df_audits_filtered[dc].apply(parse_date_robust)

# Coalesce conducted_on if missing
df_audits_filtered["conducted_on"] = (
    df_audits_filtered["conducted_on"]
    .fillna(df_audits_filtered.get("date_started"))
    .fillna(df_audits_filtered.get("created_at"))
    .fillna(df_audits_filtered.get("date_completed"))
    .fillna("")
)

audit_columns = [
    "id",
    "client_site",
    "template_name",
    "author_id",
    "author_name",
] + date_cols
existing_audit_cols = [
    col for col in audit_columns if col in df_audits_filtered.columns
]
lookup_audits = (
    df_audits_filtered[existing_audit_cols]
    .drop_duplicates(subset=["id"])
    .rename(columns={"id": "inspection_id"})
)

if "author_id" in lookup_audits.columns:
    lookup_audits["author_id"] = (
        lookup_audits["author_id"]
        .str.replace("-", "", regex=False)
        .str.strip()
        .str.lower()
    )

target_inspection_ids = set(lookup_audits["inspection_id"])

# ============================================================================
# STAGE 2: LOAD ANSWERS & MERGE
# ============================================================================
print("⚔️ [STAGE 2] Loading answers and matching...", flush=True)

needed_cols = [
    "_ParentID",
    "_IngestedAt",
    "result_question_id",
    "result_question_answer_responses_0",
    "result_list_answer_responses_0",
    "result_slider_answer_answer",
    "result_checkbox_answer_answer",
    "result_datetime_answer_answer",
    "result_question_answer_note",
    "result_signature_answer_name",
    "result_signature_answer_signed_at",
    "result_site_answer_area",
    "result_site_answer_name",
    "result_text_answer_answer",
]

sample = client.read_csv(
    f"{SLV_PREFIX}/inspections_answers.csv", nrows=1
)
available_cols = [c for c in needed_cols if c in sample.columns]

df_answers = client.read_csv(
    f"{SLV_PREFIX}/inspections_answers.csv",
    usecols=available_cols,
    dtype=str,
    low_memory=False,
)

df_answers["inspection_id"] = (
    df_answers["_ParentID"]
    .str.replace("-", "", regex=False)
    .str.strip()
    .str.lower()
)
df_answers = df_answers[
    df_answers["inspection_id"].isin(target_inspection_ids)
].copy()

# Format IngestedAt
if "_IngestedAt" in df_answers.columns:
    df_answers["IngestedAt"] = (
        pd.to_datetime(df_answers["_IngestedAt"], errors="coerce")
        .dt.strftime("%d/%m/%Y %H:%M")
        .fillna("")
    )
else:
    df_answers["IngestedAt"] = ""

df_answers["question_id"] = (
    df_answers["result_question_id"]
    .str.replace("-", "", regex=False)
    .str.strip()
    .str.lower()
)
df_answers["Question"] = df_answers["question_id"].map(clean_question_cipher)
df_answers = df_answers[df_answers["Question"].notna()].copy()

answer_priority_cols = [
    "result_question_answer_responses_0",
    "result_list_answer_responses_0",
    "result_slider_answer_answer",
    "result_text_answer_answer",
    "result_checkbox_answer_answer",
    "result_datetime_answer_answer",
    "result_question_answer_note",
    "result_signature_answer_name",
    "result_signature_answer_signed_at",
    "result_site_answer_area",
    "result_site_answer_name",
]
existing_answer_cols = [
    col for col in answer_priority_cols if col in df_answers.columns
]

df_answers["Answer"] = ""
for col in existing_answer_cols:
    df_answers["Answer"] = df_answers["Answer"].where(
        df_answers["Answer"] != "", df_answers[col].fillna("")
    )


def clean_answer_value(val):
    if pd.isna(val):
        return ""
    val_str = str(val).replace("\r\n", " ").replace("\n", " ").strip()
    if val_str.lower() == "nan":
        return ""
    if re.match(r"^\d{4}-\d{2}-\d{2}T", val_str):
        try:
            return pd.to_datetime(val_str).strftime("%d/%m/%Y %H:%M")
        except Exception:
            return val_str
    if re.match(r"^[a-fA-F0-9-]{32,36}$", val_str):
        return val_str.replace("-", "").lower()
    return val_str


df_answers["Answer"] = df_answers["Answer"].apply(clean_answer_value)

# ============================================================================
# STAGE 3: JOIN & EXPORT
# ============================================================================
print("⚔️ [STAGE 3] Joining and producing final report...", flush=True)

df_final = df_answers.merge(lookup_audits, on="inspection_id", how="right")

output_cols = [
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
    "IngestedAt",
]

for col in output_cols:
    if col not in df_final.columns:
        df_final[col] = ""

df_report = df_final[output_cols].fillna("")

out_path_csv = f"{REP_PREFIX}/rp1_esg_report.csv"
client.write_csv(df_report, out_path_csv, index=False, encoding="utf-8-sig")

# ============================================================================
# DIAGNOSTIC VERIFICATION
# ============================================================================
print("\n" + "=" * 60)
print("📅 AUDIT COUNT BY MONTH (conducted_on)")
print("=" * 60)

df_unique_audits = df_report[["inspection_id", "conducted_on"]].drop_duplicates()
dt_series = pd.to_datetime(
    df_unique_audits["conducted_on"], format="%d/%m/%Y", errors="coerce"
)

month_counts = dt_series.dt.month_name().value_counts()
months_order = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]

for m in months_order:
    cnt = month_counts.get(m, 0)
    print(f"  {m:<12} : {cnt:>4} audits")

print("=" * 60)
print(f"✅ Clean report ready at: {out_path_csv}")