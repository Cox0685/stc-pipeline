#!/usr/bin/env python
# coding: utf-8

"""
RP2 Metric Pivot Generator
Reads rp2_metric_list.csv, applies date filters, creates pivot table by site
Adds ESG data from rp1_esg_cards_hours_pivoted.csv
Creates Excel with three tabs: 'Metric_Pivot', 'Site_Totals', and 'ESG_Details'

Matching Strategy:
1. Full site name matching (with data cleaning)
2. Prefix fallback (with safeguards to prevent duplicates)

FIXED (v2) — brought in line with the RP3 fix:
- Replaced the single pd.to_datetime(errors='coerce') call (no explicit format,
  no dayfirst) with the same robust multi-format parser used in the RP3 script.
  The old call let pandas guess the format per-row, which is exactly the kind
  of silent misparse that caused the RP3 mismatch (65 vs 74) — pandas can flip
  between DD/MM and MM/DD depending on the row, and never tells you it did.
- Every row's parse method is tracked in 'Date_Parse_Method'.
- Weekly H&S Inspection rows excluded/included by the date filter are dumped
  to CSV for inspection, same as the RP3 fix.
- ESG date filtering (created_at / date_completed) now uses the same robust
  parser instead of a second unguarded pd.to_datetime(errors='coerce') call.
- End-of-range comparison now includes the full end day (23:59:59) instead of
  midnight, as a safety net.
"""

import os
import pandas as pd
import re
from datetime import datetime, timedelta

# ============================================================================
# CONFIGURATION
# ============================================================================

REP_OUTPUT_PATH = r"C:\Users\Thomas.Cox\OneDrive - OCU Group\Desktop\00_AST_SystemsIntegration\00_AST_DataUploads\01_STC Safety Culture\Data\REP"

os.makedirs(REP_OUTPUT_PATH, exist_ok=True)

# ============================================================================
# DATE FILTER
# ============================================================================

DATE_FILTER_START = "2026-08-01"
DATE_FILTER_END = "2026-08-31"

FILTER_START_DATE = datetime.strptime(DATE_FILTER_START, "%Y-%m-%d")
# Include the full end day, not just midnight, as a safety net.
FILTER_END_DATE = datetime.strptime(DATE_FILTER_END, "%Y-%m-%d") + timedelta(hours=23, minutes=59, seconds=59)

# ============================================================================
# METRICS EXCLUDED FROM DATE FILTERING (ALL TIME)
# ============================================================================

EXCLUDED_FROM_DATE_FILTER = [
    "Overdue Safety",
    "Overdue Environmental",
    "Overdue Quality",
]

# ============================================================================
# FINAL METRICS (columns to display)
# ============================================================================

FINAL_METRICS = [
    "SubCon Audits",
    "Weekly HS Inspection",
    "Work Area Inspections",
    "Overdue Quality Action",
    "Site Setup Audit",
    "Overdue Environmental Action",
    "Overdue Safety Action",
    "Env SOR Neg",
    "Env SOR Pos",
    "Safety SOR Neg",
    "Safety SOR Pos",
    "SOR Frequency Rate",
    "Open SORS",
    "Resolved SORS",
    "Accidents",
    "Environmental Incidents",
    "Near Misses",
    "Property Damage",
    "Security Breaches",
    "Service Strikes",
    "Contracts Managers Audits",
    "Senior Leadership Visits",
    "QSET Environmental",
    "QSET HS Inspection",
    "QSET Quality Inspections",
]

# ============================================================================
# METRIC MAPPING
# ============================================================================

METRIC_MAPPING = {
    "SubCon Audits": "SubCon Audits",
    "Weekly H&S Inspection": "Weekly HS Inspection",
    "Work Area Inspections": "Work Area Inspections",
    "Site Setup Audit": "Site Setup Audit",
    "Overdue Quality": "Overdue Quality Action",
    "Overdue Environmental": "Overdue Environmental Action",
    "Overdue Safety": "Overdue Safety Action",
    "Overdue Uncategorized": "DROP",
    "Open ENV -": "Env SOR Neg",
    "Resolved ENV -": "Env SOR Neg",
    "Open ENV +": "Env SOR Pos",
    "Resolved ENV +": "Env SOR Pos",
    "Open SOR -": "Safety SOR Neg",
    "Resolved SOR -": "Safety SOR Neg",
    "Open SOR +": "Safety SOR Pos",
    "Resolved SOR +": "Safety SOR Pos",
    "Open Accident (Personal Injury)": "Accidents",
    "Resolved Accident (Personal Injury)": "Accidents",
    "Open Environmental Incident": "Environmental Incidents",
    "Resolved Environmental Incident": "Environmental Incidents",
    "Open Near Miss / Unplanned Event": "Near Misses",
    "Resolved Near Miss / Unplanned Event": "Near Misses",
    "Property Damage": "Property Damage",
    "Security Breaches": "Security Breaches",
    "Service Strikes": "Service Strikes",
    "Contracts Managers Audits": "Contracts Managers Audits",
    "QSET Environmental": "QSET Environmental",
    "QSET H&S Inspection": "QSET HS Inspection",
    "QSET Quality Inspections": "QSET Quality Inspections",
    "Resolved Safety": "Resolved Safety",
    "Resolved Quality": "Resolved Quality",
    "Resolved Environmental": "Resolved Environmental",
    "Open Safety": "DROP",
    "Open Quality": "DROP",
    "Open nan": "DROP",
    "Open 005 INCIDENT REPORT": "DROP",
    "Open 007 QUALITY - WORK REMEDIATION": "DROP",
    "Open 999 - TEST * DO NOT USE *  INCIDENT REPORT": "DROP",
    "Overdue nan": "DROP",
    "Resolved Non QSET": "DROP",
    "Resolved Uncategorized": "DROP",
    "Resolved nan": "DROP",
    "Resolved 005 INCIDENT REPORT": "DROP",
    "Resolved 007 QUALITY - WORK REMEDIATION": "DROP",
}

# ============================================================================
# METRIC LISTS
# ============================================================================

OPEN_SOR_METRICS = ["Open SOR +", "Open SOR -", "Open ENV +", "Open ENV -"]
RESOLVED_SOR_METRICS = ["Resolved SOR +", "Resolved SOR -", "Resolved ENV +", "Resolved ENV -"]

PLACEHOLDER_METRICS = [
    "SOR Frequency Rate",
    "Senior Leadership Visits",
    "Property Damage",
    "Security Breaches",
    "Service Strikes",
]

# ============================================================================
# ESG COLUMNS
# ============================================================================

ESG_COLUMNS = [
    'Weekly ESG Reports DA Tests Conducted',
    'DA Test Failures',
    'Red Cards Issued',
    'Yellow Cards Issued',
    'Total Site Hours'
]

ESG_DETAILS_COLUMNS = [
    'client_site',
    'Agency/Subbie',
    'Client Reps',
    'Delivery Drivers',
    'Ext Plant',
    'Others',
    'Staff/Ops',
    'Sub Con Personnel',
    'Visitors',
    'Total Hours',
    'Yellow Cards Issued',
    'Red Cards Issued',
    'Cards Issued',
    'D&A Tests',
    'D&A Fails'
]

# ============================================================================
# ROBUST DATE PARSER - tries multiple explicit formats, tracks which one hit
# ============================================================================

# Add/remove formats here if you spot others in the debug CSV.
KNOWN_FORMATS = [
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y %H:%M",
    "%d-%m-%Y",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y",
]


def parse_date_robust(date_str):
    """
    Returns (parsed_timestamp_or_NaT, method_used_str).
    Tries each format in KNOWN_FORMATS in order. Falls back to pandas'
    general parser with dayfirst=True only as a last resort, and flags it
    clearly so you can spot rows that needed it.
    """
    if pd.isna(date_str):
        return pd.NaT, "NULL_INPUT"

    raw = str(date_str).strip()
    if raw == "" or raw.lower() == "nan":
        return pd.NaT, "EMPTY_INPUT"

    for fmt in KNOWN_FORMATS:
        try:
            return pd.to_datetime(raw, format=fmt), f"exact:{fmt}"
        except (ValueError, TypeError):
            continue

    # Excel serial date number (e.g. CSV exported a date as a raw number)
    try:
        serial = float(raw)
        parsed = pd.Timestamp("1899-12-30") + pd.to_timedelta(serial, unit="D")
        return parsed, "excel_serial"
    except (ValueError, TypeError):
        pass

    # Last-resort loose parse — flagged so you know it wasn't a clean match
    try:
        parsed = pd.to_datetime(raw, errors="coerce", dayfirst=True)
        if pd.notna(parsed):
            return parsed, "FALLBACK_dayfirst_loose"
    except Exception:
        pass

    return pd.NaT, "UNPARSEABLE"


def parse_date_series(series):
    """Vectorized-ish wrapper: returns (parsed_series, method_series)."""
    results = series.apply(parse_date_robust)
    parsed = results.apply(lambda x: x[0])
    method = results.apply(lambda x: x[1])
    return parsed, method


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def extract_prefix(name):
    """Extract the numeric prefix from a site name (e.g., '2349 HVDC...' -> '2349')"""
    if pd.isna(name):
        return None
    match = re.match(r'^(\d+)', str(name).strip())
    return match.group(1) if match else None

def clean_site_name(name):
    """
    Clean site name for matching.
    - Standardizes apostrophes
    - Removes extra spaces
    - Removes special characters
    - Converts to lowercase
    """
    if pd.isna(name):
        return None
    name = str(name).strip()
    # Replace all apostrophe variations with a standard apostrophe
    name = name.replace('’', "'").replace('‘', "'").replace('"', "'")
    # Remove parentheses and their content (for more flexible matching)
    name = re.sub(r'\([^)]*\)', '', name).strip()
    # Remove special characters except apostrophes, hyphens, and spaces
    name = re.sub(r'[^a-zA-Z0-9\s\'\-]', '', name)
    # Remove extra spaces
    name = ' '.join(name.split())
    # Lowercase for case-insensitive matching
    name = name.lower()
    return name

def clean_site_name_strict(name):
    """
    Strict cleaning - removes everything except alphanumeric.
    Used for stricter matching.
    """
    if pd.isna(name):
        return None
    name = str(name).strip()
    # Remove all non-alphanumeric characters
    name = re.sub(r'[^a-zA-Z0-9]', '', name)
    # Lowercase
    name = name.lower()
    return name

# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 80)
    print("⚔️  RP2 METRIC PIVOT GENERATOR (with ESG) - ROBUST DATE PARSING (v2)")
    print("=" * 80)
    print(f"📅 Date Filter: {DATE_FILTER_START} to {DATE_FILTER_END} (inclusive, full end day)")
    print("=" * 80)

    # Read the metric list
    input_file = os.path.join(REP_OUTPUT_PATH, "rp2_metric_list.csv")
    if not os.path.exists(input_file):
        print(f"❌ Input file not found: {input_file}")
        return

    df = pd.read_csv(input_file, dtype=str, low_memory=False)
    print(f"\n📂 Loaded {len(df):,} rows from rp2_metric_list.csv")

    # ------------------------------------------------------------------
    # Parse date column with the robust parser (replaces the old
    # unguarded pd.to_datetime(errors='coerce') call)
    # ------------------------------------------------------------------
    date_column = 'Filter Date' if 'Filter Date' in df.columns else 'Date' if 'Date' in df.columns else None
    if not date_column:
        print(f"\n   ❌ No date column found!")
        return

    print(f"\n   ✅ Using '{date_column}' column for date filtering")

    df['Date_Parsed'], df['Date_Parse_Method'] = parse_date_series(df[date_column])

    valid_dates = df['Date_Parsed'].notna().sum()
    invalid_dates = df['Date_Parsed'].isna().sum()
    print(f"   ✅ {valid_dates:,} valid dates ({invalid_dates:,} invalid)")

    print(f"\n   📊 Parse method breakdown (all rows):")
    print(df['Date_Parse_Method'].value_counts().to_string())

    if invalid_dates > 0:
        print(f"\n   ⚠️ Sample invalid dates:")
        for sample in df.loc[df['Date_Parsed'].isna(), date_column].head(10):
            print(f"      {sample!r}")

    # ------------------------------------------------------------------
    # Weekly H&S Inspection diagnostics + debug export (same as RP3 fix)
    # ------------------------------------------------------------------
    weekly_mask_all = df['Reporting_Metric'] == 'Weekly H&S Inspection'
    weekly_total = weekly_mask_all.sum()

    is_overdue = df['Reporting_Metric'].isin(EXCLUDED_FROM_DATE_FILTER)
    date_mask = (df['Date_Parsed'] >= FILTER_START_DATE) & (df['Date_Parsed'] <= FILTER_END_DATE)

    weekly_in_range = (weekly_mask_all & date_mask).sum()
    weekly_outside = weekly_total - weekly_in_range

    print(f"\n   📊 Weekly H&S Inspection date filter:")
    print(f"      Total: {weekly_total}")
    print(f"      In date range: {weekly_in_range}")
    print(f"      Outside date range: {weekly_outside}")

    debug_cols = [c for c in ['Site Name', 'Reporting_Metric', 'ID', 'Created At',
                               'Completed At', date_column, 'Date_Parsed',
                               'Date_Parse_Method'] if c in df.columns]

    weekly_excluded = df.loc[weekly_mask_all & ~date_mask, debug_cols].copy().sort_values('Date_Parsed', na_position='first')
    debug_file = os.path.join(REP_OUTPUT_PATH, "weekly_hs_excluded_debug.csv")
    weekly_excluded.to_csv(debug_file, index=False, encoding='utf-8')
    print(f"\n   🔍 Wrote {len(weekly_excluded):,} excluded Weekly H&S rows to: {debug_file}")

    weekly_included = df.loc[weekly_mask_all & date_mask, debug_cols].copy().sort_values('Date_Parsed')
    included_file = os.path.join(REP_OUTPUT_PATH, "weekly_hs_included_debug.csv")
    weekly_included.to_csv(included_file, index=False, encoding='utf-8')
    print(f"   🔍 Wrote {len(weekly_included):,} included Weekly H&S rows to: {included_file}")

    # ------------------------------------------------------------------
    # Apply date filter
    # ------------------------------------------------------------------
    df_filtered = df[is_overdue | date_mask].copy()
    print(f"\n   📊 After filtering: {len(df_filtered):,} rows")

    if df_filtered.empty:
        print("\n⚠️ No records after filtering!")
        return

    # Apply metric mapping
    def map_metric(metric):
        if metric in METRIC_MAPPING:
            new_metric = METRIC_MAPPING[metric]
            return None if new_metric == "DROP" else new_metric
        return metric

    df_filtered['Mapped_Metric'] = df_filtered['Reporting_Metric'].apply(map_metric)
    df_filtered = df_filtered[df_filtered['Mapped_Metric'].notna()].copy()
    df_filtered = df_filtered.dropna(subset=['Site Name', 'Mapped_Metric'])
    print(f"   📊 After mapping: {len(df_filtered):,} rows")

    if df_filtered.empty:
        print("\n⚠️ No records after mapping!")
        return

    # Create pivot table
    pivot_df = df_filtered.groupby(['Site Name', 'Mapped_Metric']).size().reset_index(name='Count')
    pivot_table = pivot_df.pivot(index='Site Name', columns='Mapped_Metric', values='Count').fillna(0).astype(int)

    weekly_in_pivot = pivot_table['Weekly HS Inspection'].sum() if 'Weekly HS Inspection' in pivot_table.columns else 0
    print(f"\n   📊 Weekly HS Inspection in pivot: {weekly_in_pivot}")

    # Calculate Open SORS and Resolved SORS
    def map_for_totals(metric):
        if metric in METRIC_MAPPING:
            new_metric = METRIC_MAPPING[metric]
            if new_metric == "DROP":
                return None
            if metric in OPEN_SOR_METRICS:
                return "Open SORS"
            if metric in RESOLVED_SOR_METRICS:
                return "Resolved SORS"
            return new_metric
        return metric

    df_filtered['Total_Metric'] = df_filtered['Reporting_Metric'].apply(map_for_totals)
    df_totals = df_filtered[df_filtered['Total_Metric'].notna()].copy()
    pivot_totals = df_totals.groupby(['Site Name', 'Total_Metric']).size().reset_index(name='Count')
    pivot_totals_table = pivot_totals.pivot(index='Site Name', columns='Total_Metric', values='Count').fillna(0).astype(int)

    # Build final pivot
    final_pivot = pd.DataFrame(index=pivot_table.index)
    for metric in FINAL_METRICS:
        if metric in ["Open SORS", "Resolved SORS"]:
            final_pivot[metric] = pivot_totals_table[metric] if metric in pivot_totals_table.columns else 0
        elif metric in PLACEHOLDER_METRICS:
            final_pivot[metric] = 0
        else:
            final_pivot[metric] = pivot_table[metric] if metric in pivot_table.columns else 0

    # Calculate Total Resolved Actions
    resolved_safety = pivot_table['Resolved Safety'] if 'Resolved Safety' in pivot_table.columns else pd.Series(0, index=pivot_table.index)
    resolved_quality = pivot_table['Resolved Quality'] if 'Resolved Quality' in pivot_table.columns else pd.Series(0, index=pivot_table.index)
    resolved_environmental = pivot_table['Resolved Environmental'] if 'Resolved Environmental' in pivot_table.columns else pd.Series(0, index=pivot_table.index)
    final_pivot['Total Resolved Actions'] = resolved_safety + resolved_quality + resolved_environmental

    # ========================================================================
    # ADD ESG DATA WITH CLEAN MATCHING
    # ========================================================================

    print(f"\n⚔️ Adding ESG data with clean matching...")

    esg_data_by_site = {}
    esg_report_counts = {}
    esg_total_hours = {}
    df_esg_details = None

    esg_pivot_path = os.path.join(REP_OUTPUT_PATH, "rp1_esg_cards_hours_pivoted.csv")

    if os.path.exists(esg_pivot_path):
        df_esg = pd.read_csv(esg_pivot_path, dtype=str, low_memory=False)
        print(f"   ✅ Loaded ESG pivot: {len(df_esg):,} rows")

        # Filter by date — same robust parser, replacing the old
        # unguarded pd.to_datetime(errors='coerce') calls.
        df_esg['created_at'], df_esg['created_at_method'] = parse_date_series(df_esg['created_at'])
        df_esg['date_completed'], df_esg['date_completed_method'] = parse_date_series(df_esg['date_completed'])

        esg_invalid_created = df_esg['created_at'].isna().sum()
        esg_invalid_completed = df_esg['date_completed'].isna().sum()
        if esg_invalid_created or esg_invalid_completed:
            print(f"   ⚠️ ESG date parsing: {esg_invalid_created:,} invalid created_at, "
                  f"{esg_invalid_completed:,} invalid date_completed")

        date_mask_esg = (
            (df_esg['created_at'] >= FILTER_START_DATE) & (df_esg['created_at'] <= FILTER_END_DATE) |
            (df_esg['date_completed'] >= FILTER_START_DATE) & (df_esg['date_completed'] <= FILTER_END_DATE)
        )
        df_esg_filtered = df_esg[date_mask_esg].copy()
        print(f"   📊 After date filter: {len(df_esg_filtered):,} rows")

        # Build ESG data by client_site with cleaned keys
        esg_source_data = {}
        for _, row in df_esg_filtered.iterrows():
            site = row['client_site']
            clean_key = clean_site_name(site)
            if clean_key not in esg_source_data:
                esg_source_data[clean_key] = {
                    'rows': [],
                    'original_site': site,
                    'prefix': extract_prefix(site),
                    'inspection_ids': set(),
                    'total_hours': 0,
                    'd_a_tests': 0,
                    'd_a_fails': 0,
                    'red_cards': 0,
                    'yellow_cards': 0,
                    'agency': 0,
                    'client_reps': 0,
                    'delivery_drivers': 0,
                    'ext_plant': 0,
                    'others': 0,
                    'staff_ops': 0,
                    'sub_con': 0,
                    'visitors': 0
                }
            esg_source_data[clean_key]['rows'].append(row)

        # Process each ESG site to aggregate data
        for clean_key, data in esg_source_data.items():
            for row in data['rows']:
                inspection_id = row.get('inspection_id')
                if inspection_id and not pd.isna(inspection_id):
                    data['inspection_ids'].add(str(inspection_id))

                data['total_hours'] += pd.to_numeric(row.get('Total Hours', 0), errors='coerce') or 0
                data['d_a_tests'] += pd.to_numeric(row.get('D&A Tests', 0), errors='coerce') or 0
                data['d_a_fails'] += pd.to_numeric(row.get('D&A Fails', 0), errors='coerce') or 0
                data['red_cards'] += pd.to_numeric(row.get('Red Cards Issued', 0), errors='coerce') or 0
                data['yellow_cards'] += pd.to_numeric(row.get('Yellow Cards Issued', 0), errors='coerce') or 0
                data['agency'] += pd.to_numeric(row.get('Agency/Subbie', 0), errors='coerce') or 0
                data['client_reps'] += pd.to_numeric(row.get('Client Reps', 0), errors='coerce') or 0
                data['delivery_drivers'] += pd.to_numeric(row.get('Delivery Drivers', 0), errors='coerce') or 0
                data['ext_plant'] += pd.to_numeric(row.get('Ext Plant', 0), errors='coerce') or 0
                data['others'] += pd.to_numeric(row.get('Others', 0), errors='coerce') or 0
                data['staff_ops'] += pd.to_numeric(row.get('Staff/Ops', 0), errors='coerce') or 0
                data['sub_con'] += pd.to_numeric(row.get('Sub Con Personnel', 0), errors='coerce') or 0
                data['visitors'] += pd.to_numeric(row.get('Visitors', 0), errors='coerce') or 0

        print(f"   ✅ Built ESG data for {len(esg_source_data)} sites")

        # ================================================================
        # STEP 1: Full site name matching (with cleaning)
        # ================================================================

        dest_to_esg = {}
        used_esg_sites = set()

        print("\n   📋 Matching destination sites to ESG data:")
        print("   [STRATEGY 1: Full site name matching]")

        # Build destination site cleaned keys
        dest_sites_info = {}
        for dest_site in final_pivot.index:
            clean_key = clean_site_name(dest_site)
            prefix = extract_prefix(dest_site)
            dest_sites_info[dest_site] = {
                'clean_key': clean_key,
                'prefix': prefix
            }

        # Match by full site name (cleaned)
        for dest_site in final_pivot.index:
            clean_key = dest_sites_info[dest_site]['clean_key']

            if clean_key in esg_source_data:
                if clean_key not in used_esg_sites:
                    dest_to_esg[dest_site] = clean_key
                    used_esg_sites.add(clean_key)
                    print(f"      ✅ Full match: '{dest_site}' -> '{esg_source_data[clean_key]['original_site']}'")
                else:
                    print(f"      ⚠️ Already used: '{dest_site}' (key: {clean_key})")

        # ================================================================
        # STEP 2: Prefix fallback for unmatched sites
        # ================================================================

        print("\n   [STRATEGY 2: Prefix fallback]")

        prefix_to_esg = {}
        for clean_key, data in esg_source_data.items():
            prefix = data['prefix']
            if prefix:
                if prefix not in prefix_to_esg:
                    prefix_to_esg[prefix] = []
                prefix_to_esg[prefix].append(clean_key)

        for dest_site in final_pivot.index:
            if dest_site in dest_to_esg:
                continue  # Already matched

            dest_prefix = dest_sites_info[dest_site]['prefix']
            if dest_prefix and dest_prefix in prefix_to_esg:
                available = [k for k in prefix_to_esg[dest_prefix] if k not in used_esg_sites]
                if available:
                    esg_key = available[0]
                    dest_to_esg[dest_site] = esg_key
                    used_esg_sites.add(esg_key)
                    print(f"      🔄 Prefix fallback: '{dest_site}' -> '{esg_source_data[esg_key]['original_site']}' (prefix: {dest_prefix})")
                else:
                    print(f"      ❌ No available ESG sites with prefix: {dest_prefix}")
            else:
                print(f"      ❌ No match for '{dest_site}'")

        print(f"\n   ✅ Matched {len(dest_to_esg)} destination sites to ESG data")

        # ================================================================
        # Create ESG Details DataFrame
        # ================================================================

        df_esg_details_rows = []
        for clean_key, data in esg_source_data.items():
            if clean_key in dest_to_esg.values():
                df_esg_details_rows.append({
                    'client_site': data['original_site'],
                    'Agency/Subbie': data['agency'],
                    'Client Reps': data['client_reps'],
                    'Delivery Drivers': data['delivery_drivers'],
                    'Ext Plant': data['ext_plant'],
                    'Others': data['others'],
                    'Staff/Ops': data['staff_ops'],
                    'Sub Con Personnel': data['sub_con'],
                    'Visitors': data['visitors'],
                    'Total Hours': data['total_hours'],
                    'Yellow Cards Issued': data['yellow_cards'],
                    'Red Cards Issued': data['red_cards'],
                    'Cards Issued': data['red_cards'] + data['yellow_cards'],
                    'D&A Tests': data['d_a_tests'],
                    'D&A Fails': data['d_a_fails']
                })

        df_esg_details = pd.DataFrame(df_esg_details_rows)
        if not df_esg_details.empty:
            df_esg_details = df_esg_details[ESG_DETAILS_COLUMNS].copy().sort_values('client_site')
            print(f"   ✅ Created ESG Details: {len(df_esg_details):,} rows")
        else:
            df_esg_details = None
            print(f"   ⚠️ No ESG Details created")

        # ================================================================
        # Add ESG columns to Metric_Pivot
        # ================================================================

        for col in ESG_COLUMNS:
            final_pivot[col] = 0.0

        fill_count = 0
        for dest_site in final_pivot.index:
            if dest_site in dest_to_esg:
                esg_key = dest_to_esg[dest_site]
                if esg_key in esg_source_data:
                    data = esg_source_data[esg_key]
                    final_pivot.at[dest_site, 'Weekly ESG Reports DA Tests Conducted'] = float(data['d_a_tests'])
                    final_pivot.at[dest_site, 'DA Test Failures'] = float(data['d_a_fails'])
                    final_pivot.at[dest_site, 'Red Cards Issued'] = float(data['red_cards'])
                    final_pivot.at[dest_site, 'Yellow Cards Issued'] = float(data['yellow_cards'])
                    final_pivot.at[dest_site, 'Total Site Hours'] = float(data['total_hours'])
                    fill_count += 1

        print(f"   ✅ Filled ESG data for {fill_count} sites")

        # ================================================================
        # STORE ESG DATA FOR SITE_TOTALS
        # ================================================================

        esg_report_counts = {}
        esg_total_hours = {}
        for dest_site in final_pivot.index:
            if dest_site in dest_to_esg:
                esg_key = dest_to_esg[dest_site]
                if esg_key in esg_source_data:
                    data = esg_source_data[esg_key]
                    esg_report_counts[dest_site] = len(data['inspection_ids'])
                    esg_total_hours[dest_site] = data['total_hours']

        print(f"\n   📊 ESG Report Counts by Site:")
        for site, count in sorted(esg_report_counts.items()):
            print(f"      {site[:40]:<40} {count:>3} reports, {esg_total_hours.get(site, 0):>8.1f} hours")

    else:
        print(f"   ⚠️ ESG pivot file not found")
        for col in ESG_COLUMNS:
            final_pivot[col] = 0.0

    final_pivot = final_pivot.sort_index()

    # ========================================================================
    # CREATE SITE TOTALS
    # ========================================================================

    print(f"\n⚔️ Creating Site Totals...")

    site_totals = final_pivot.copy()
    site_totals['Total Overdue Actions'] = site_totals['Overdue Quality Action'] + site_totals['Overdue Environmental Action'] + site_totals['Overdue Safety Action']
    site_totals['Total Incidents'] = site_totals['Accidents'] + site_totals['Environmental Incidents'] + site_totals['Near Misses'] + site_totals['Property Damage'] + site_totals['Security Breaches'] + site_totals['Service Strikes']
    site_totals['Total Leadership'] = site_totals['Contracts Managers Audits'] + site_totals['Senior Leadership Visits']
    site_totals['Total QSET'] = site_totals['QSET Environmental'] + site_totals['QSET HS Inspection'] + site_totals['QSET Quality Inspections']
    site_totals['Total Open SORs'] = site_totals['Open SORS']
    site_totals['Total Resolved SORs'] = site_totals['Resolved SORS']

    # Add ESG Report Count and Total Hours to Site Totals
    site_totals['ESG Reports Completed'] = 0
    site_totals['ESG Total Hours'] = 0.0

    for site in site_totals.index:
        if site in esg_report_counts:
            site_totals.at[site, 'ESG Reports Completed'] = esg_report_counts[site]
        if site in esg_total_hours:
            site_totals.at[site, 'ESG Total Hours'] = esg_total_hours[site]

    # Define Site Totals columns in order
    site_totals_columns = [
        'Site Name',
        'Total Overdue Actions',
        'Total Resolved Actions',
        'Total Incidents',
        'Total Leadership',
        'Total QSET',
        'Total Open SORs',
        'Total Resolved SORs',
        'ESG Reports Completed',
        'ESG Total Hours'
    ]

    site_totals_columns = [col for col in site_totals_columns if col in site_totals.columns]
    df_site_totals = site_totals[site_totals_columns].copy().reset_index()
    print(f"   ✅ Created Site Totals: {len(df_site_totals)} sites, {len(df_site_totals.columns)} columns")

    # ========================================================================
    # SAVE TO EXCEL
    # ========================================================================

    output_file = os.path.join(REP_OUTPUT_PATH, "rp2_metric_pivot_by_site.xlsx")

    try:
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            final_pivot.to_excel(writer, sheet_name='Metric_Pivot', index=True)
            df_site_totals.to_excel(writer, sheet_name='Site_Totals', index=False)
            if df_esg_details is not None and not df_esg_details.empty:
                df_esg_details.to_excel(writer, sheet_name='ESG_Details', index=False)
                print(f"\n✅ Saved Excel with 3 tabs to: {output_file}")
            else:
                empty_esg = pd.DataFrame(columns=ESG_DETAILS_COLUMNS)
                empty_esg.to_excel(writer, sheet_name='ESG_Details', index=False)
                print(f"\n✅ Saved Excel with 3 tabs to: {output_file} (ESG_Details empty)")
            print(f"   📊 Metric_Pivot: {len(final_pivot)} sites, {len(final_pivot.columns)} columns")
            print(f"   📊 Site_Totals: {len(df_site_totals)} sites, {len(df_site_totals.columns)} columns")
    except ModuleNotFoundError:
        print(f"\n⚠️ openpyxl not found. Please install: pip install openpyxl")
        return

    # ========================================================================
    # SUMMARY
    # ========================================================================

    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    print(f"\n📋 Total Sites: {len(final_pivot):,}")

    print(f"\n📋 Weekly H&S Inspection count breakdown:")
    print(f"   Original in file: {weekly_total}")
    print(f"   In date range: {weekly_in_range}")
    print(f"   In final pivot: {weekly_in_pivot}")
    print(f"   >>> See weekly_hs_excluded_debug.csv for the {weekly_outside} excluded rows")
    print(f"   >>> See weekly_hs_included_debug.csv for the {weekly_in_range} included rows")

    print(f"\n📋 ESG Columns added to Metric_Pivot:")
    for col in ESG_COLUMNS:
        if col in final_pivot.columns:
            total = final_pivot[col].sum()
            non_zero = (final_pivot[col] > 0).sum()
            print(f"      {col:<40} total: {total:>10,.2f} | sites: {non_zero:>6,}")

    print(f"\n📋 Site Totals Summary:")
    for col in df_site_totals.columns:
        if col != 'Site Name':
            total = df_site_totals[col].sum()
            print(f"      {col:<25} total: {total:>8,}")

    print("\n" + "=" * 80)
    print("🏁 PIVOT GENERATOR COMPLETE")
    print("=" * 80)

    return final_pivot

if __name__ == "__main__":
    main()