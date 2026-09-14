#!/usr/bin/env python
# coding: utf-8

"""
Reporting Metric List Generator
Creates a simple list of Source Table, Reporting_Metric, and Date Column
NO FILTERING BY DATE - shows ALL records
Cross-references with rp2_site_status.csv to filter by Site Area

FIXED VERSION:
- "Site Setup Audit" added to rp2_site_reports metric filter list
- Metric filtering now matches values inside comma-separated
  Reporting_Metric cells (e.g. "Work Area Inspections, Site Setup Audit")
  instead of requiring an exact whole-cell match. Rows with multiple
  matching metrics are exploded into one row per matched metric so
  none are silently dropped.
- CHANGED: rp2_site_reports and rp2_QSET_reports now use 'conducted_on' 
  instead of 'created_at' or 'date_completed' for the Filter Date column
- FIXED: UK date format support (DD/MM/YYYY) with dayfirst=True
"""

import os
import pandas as pd
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

GLD_INPUT_PATH = r"C:\Users\Thomas.Cox\OneDrive - OCU Group\Desktop\00_AST_SystemsIntegration\00_AST_DataUploads\01_STC Safety Culture\Data\GLD"
REP_INPUT_PATH = r"C:\Users\Thomas.Cox\OneDrive - OCU Group\Desktop\00_AST_SystemsIntegration\00_AST_DataUploads\01_STC Safety Culture\Data\REP"
REP_OUTPUT_PATH = r"C:\Users\Thomas.Cox\OneDrive - OCU Group\Desktop\00_AST_SystemsIntegration\00_AST_DataUploads\01_STC Safety Culture\Data\REP"

# Create output folder if it doesn't exist
os.makedirs(REP_OUTPUT_PATH, exist_ok=True)

# ============================================================================
# VALID SITE AREAS (only include these)
# ============================================================================

VALID_SITE_AREAS = ["North", "South"]

# ============================================================================
# REPORTING METRIC FILTERS PER SOURCE
# ============================================================================

METRIC_FILTERS = {
    "rp2_site_reports": [
        "Weekly H&S Inspection",
        "SubCon Audits",
        "Weekly ESG Report",
        "Work Area Inspections",
        "Site Setup Audit"          # <-- ADDED
    ],
    "rp2_QSET_reports": [
        "QSET H&S Inspection",
        "QSET Environmental",
        "QSET Quality Inspections"
    ],
    "rp2_contracts_managers_audits": [
        "Contracts Managers Audits"
    ]
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def clean_site_name(name):
    """Clean site name by removing everything after the first '/'"""
    if pd.isna(name):
        return None
    name_str = str(name).strip()
    if '/' in name_str:
        return name_str.split('/')[0].strip()
    return name_str


def get_site_column(df):
    """Find the site name column in a DataFrame"""
    for col in ['task_site_name', 'site_name', 'Site', 'client_site', 'inspection_name']:
        if col in df.columns:
            return col
    return None


def get_id_column(df):
    """Find the ID column in a DataFrame"""
    # For REP files (site_reports, QSET, contracts_managers)
    if 'id' in df.columns:
        return 'id'
    # For GLD files (actions, issues)
    if 'task_unique_id' in df.columns:
        return 'task_unique_id'
    # For incidents
    if 'task_unique_id' in df.columns:
        return 'task_unique_id'
    return None


def extract_site_from_name(name):
    """
    Fallback: some sources (e.g. Contracts Managers Audits) embed the site
    in the 'name' field, like:
        '2399 Redheughs Village Earthworks / 17 Jul 2026 / Stuart Robertson'
    We take the first '/'-separated segment, but only if it doesn't look
    like a date (e.g. Site Reports' name field is '27 Jul 2026 / Gavin Macfarlane',
    which has no site in it at all).
    """
    if pd.isna(name):
        return None

    first_part = str(name).split('/')[0].strip()
    if not first_part:
        return None

    # crude check: if the first segment parses as a date, it's not a site name
    try:
        pd.to_datetime(first_part, dayfirst=True)
        return None
    except Exception:
        return first_part


def parse_date_robust(date_str):
    """
    Parse dates with multiple format support - PRIORITIZES UK FORMAT (DD/MM/YYYY)
    
    Handles:
    - 31/07/2026 14:16:03 (UK format with time)
    - 31/07/2026 14:16 (UK format with time, no seconds)
    - 31/07/2026 (UK format date only)
    - 2026-07-31 14:16:03 (ISO format)
    - 2026-07-31 (ISO format date only)
    - 07/31/2026 (US format - handled as fallback)
    """
    if pd.isna(date_str):
        return None

    date_str = str(date_str).strip()
    
    # Try UK formats FIRST (DD/MM/YYYY)
    uk_formats = [
        '%d/%m/%Y  %H:%M:%S',   # 31/07/2026  14:16:03 (TWO spaces)
        '%d/%m/%Y %H:%M:%S',    # 31/07/2026 14:16:03 (ONE space)
        '%d/%m/%Y  %H:%M',      # 31/07/2026  14:16 (TWO spaces, no seconds)
        '%d/%m/%Y %H:%M',       # 31/07/2026 14:16 (ONE space, no seconds)
        '%d/%m/%Y',             # 31/07/2026
        '%d-%m-%Y %H:%M:%S',    # 31-07-2026 14:16:03
        '%d-%m-%Y',             # 31-07-2026
        '%d.%m.%Y %H:%M:%S',    # 31.07.2026 14:16:03
        '%d.%m.%Y',             # 31.07.2026
    ]
    
    for fmt in uk_formats:
        try:
            return pd.to_datetime(date_str, format=fmt)
        except:
            continue
    
    # Try ISO formats (YYYY-MM-DD)
    iso_formats = [
        '%Y-%m-%d %H:%M:%S',    # 2026-07-31 14:16:03
        '%Y-%m-%d',             # 2026-07-31
        '%Y-%m-%d %H:%M',       # 2026-07-31 14:16
    ]
    
    for fmt in iso_formats:
        try:
            return pd.to_datetime(date_str, format=fmt)
        except:
            continue
    
    # Try US formats LAST (MM/DD/YYYY) - these are ambiguous and should be avoided
    us_formats = [
        '%m/%d/%Y %H:%M:%S',    # 07/31/2026 14:16:03
        '%m/%d/%Y',             # 07/31/2026
        '%m-%d-%Y %H:%M:%S',    # 07-31-2026 14:16:03
        '%m-%d-%Y',             # 07-31-2026
    ]
    
    for fmt in us_formats:
        try:
            return pd.to_datetime(date_str, format=fmt)
        except:
            continue
    
    # Ultimate fallback: use pandas with dayfirst=True for UK format
    try:
        return pd.to_datetime(date_str, errors='coerce', dayfirst=True)
    except:
        return None


def load_site_status_lookup():
    """
    Load rp2_site_status.csv and create lookup dictionaries for Site Area.
    Returns dictionaries mapping site name (cleaned and original) to Site Area.
    """
    site_status_file = os.path.join(REP_OUTPUT_PATH, "rp2_site_status.csv")

    if not os.path.exists(site_status_file):
        print(f"   ⚠️ rp2_site_status.csv not found at: {site_status_file}")
        print(f"   ⚠️ Please run RP2 site status report first.")
        return {}, {}

    try:
        df_sites = pd.read_csv(site_status_file, dtype=str, low_memory=False)
        print(f"   ✅ Loaded rp2_site_status.csv ({len(df_sites):,} rows)")

        # Create lookup dictionaries
        site_area_lookup_cleaned = {}  # Site Name (Cleaned) -> Site Area
        site_area_lookup_original = {}  # Site Name (Original) -> Site Area

        for _, row in df_sites.iterrows():
            site_area = str(row.get('Site Area', '')).strip() if pd.notna(row.get('Site Area')) else ''

            # Cleaned site name
            cleaned_name = str(row.get('Site Name (Cleaned)', '')).strip() if pd.notna(row.get('Site Name (Cleaned)')) else ''
            if cleaned_name and site_area:
                site_area_lookup_cleaned[cleaned_name] = site_area

            # Original site name
            original_name = str(row.get('Site Name (Original)', '')).strip() if pd.notna(row.get('Site Name (Original)')) else ''
            if original_name and site_area:
                site_area_lookup_original[original_name] = site_area

        print(f"   ✅ Created site area lookup with {len(site_area_lookup_cleaned):,} cleaned names and {len(site_area_lookup_original):,} original names")
        return site_area_lookup_cleaned, site_area_lookup_original

    except Exception as e:
        print(f"   ❌ Error loading rp2_site_status.csv: {e}")
        return {}, {}


def get_site_area(site_name, lookup_cleaned, lookup_original):
    """
    Get Site Area for a given site name.
    First tries cleaned name lookup, then original name lookup.
    Returns None if not found.
    """
    if pd.isna(site_name):
        return None

    site_name_str = str(site_name).strip()

    # Try cleaned name lookup first
    if site_name_str in lookup_cleaned:
        return lookup_cleaned[site_name_str]

    # Try original name lookup
    if site_name_str in lookup_original:
        return lookup_original[site_name_str]

    return None


# ============================================================================
# MAIN PROCESSING
# ============================================================================

def main():
    print("=" * 80)
    print("⚔️  REPORTING METRIC LIST GENERATOR")
    print("=" * 80)
    print("📋 NO DATE FILTERING - Showing ALL records")
    print(f"🔍 Site Area Filter: Only include '{VALID_SITE_AREAS}'")
    print("📅 CHANGED: rp2_site_reports and rp2_QSET_reports use 'conducted_on'")
    print("🇬🇧 UK Date Format: DD/MM/YYYY (dayfirst=True)")
    print("=" * 80)

    # ========================================================================
    # STEP 1: Load site status lookup
    # ========================================================================

    print("\n⚔️ Loading site status lookup...")
    site_area_lookup_cleaned, site_area_lookup_original = load_site_status_lookup()

    if not site_area_lookup_cleaned and not site_area_lookup_original:
        print("   ⚠️ No site lookup data available - will not filter by Site Area")

    all_records = []

    # ========================================================================
    # File configurations:
    # (file_path, source_name, metric_filters, date_column_for_filtering, 
    #  created_date_col, completed_date_col, id_col)
    # 
    # CHANGED: rp2_site_reports and rp2_QSET_reports now use 'conducted_on' 
    # instead of 'created_at' or 'date_completed' for the Filter Date column
    # ========================================================================

    file_configs = [
        # Site Reports - NOW using conducted_on for filtering
        (os.path.join(REP_INPUT_PATH, "rp2_site_reports.csv"), "rp2_site_reports", 
         METRIC_FILTERS["rp2_site_reports"], "conducted_on", "created_at", "date_completed", "id"),
        
        # QSET Reports - NOW using conducted_on for filtering
        (os.path.join(REP_INPUT_PATH, "rp2_QSET_reports.csv"), "rp2_QSET_reports", 
         METRIC_FILTERS["rp2_QSET_reports"], "conducted_on", "created_at", "date_completed", "id"),
        
        # Contracts Managers - STILL using date_completed
        (os.path.join(REP_INPUT_PATH, "rp2_contracts_managers_audits.csv"), "rp2_contracts_managers_audits", 
         METRIC_FILTERS["rp2_contracts_managers_audits"], "date_completed", "created_at", "date_completed", "id"),

        # Other files - use task_created_at for filtering
        (os.path.join(REP_INPUT_PATH, "rp2_incidents.csv"), "rp2_incidents", 
         None, "task_created_at", "task_created_at", None, "task_unique_id"),

        # GLD files - id column is 'task_unique_id'
        (os.path.join(GLD_INPUT_PATH, "gld_actions.csv"), "gld_actions", 
         None, "task_created_at", "task_created_at", None, "task_unique_id"),
        (os.path.join(GLD_INPUT_PATH, "gld_issues.csv"), "gld_issues", 
         None, "task_created_at", "task_created_at", None, "task_unique_id"),
    ]

    for file_path, source_name, metric_filters, filter_date_col, created_col, completed_col, id_col in file_configs:
        process_file(
            file_path=file_path,
            source_name=source_name,
            metric_filters=metric_filters,
            filter_date_column=filter_date_col,
            created_date_column=created_col,
            completed_date_column=completed_col,
            id_column=id_col,
            all_records=all_records,
            site_area_lookup_cleaned=site_area_lookup_cleaned,
            site_area_lookup_original=site_area_lookup_original
        )

    # ========================================================================
    # CREATE FINAL DATAFRAME
    # ========================================================================

    if not all_records:
        print("\n⚠️ No records found!")
        return

    df_all = pd.DataFrame(all_records)
    print(f"\n✅ Total records collected: {len(df_all):,}")

    # Show Site Area breakdown before filtering
    if 'Site Area' in df_all.columns:
        print(f"\n   📋 Site Area breakdown (before filtering):")
        area_counts = df_all['Site Area'].value_counts()
        for area, count in area_counts.items():
            print(f"      {area}: {count} rows")

    # Filter by Site Area
    if 'Site Area' in df_all.columns:
        df_all = df_all[df_all['Site Area'].isin(VALID_SITE_AREAS)].copy()
        print(f"\n   🎯 After filtering to '{VALID_SITE_AREAS}': {len(df_all):,} rows")

    # Remove rows with empty Site Name or Reporting_Metric
    before_drop = len(df_all)
    missing_mask = df_all['Site Name'].isna() | df_all['Reporting_Metric'].isna()
    if missing_mask.any():
        print(f"\n⚠️ Dropping {missing_mask.sum():,} rows with no Site Name / Reporting_Metric, by source:")
        print(df_all[missing_mask].groupby('Source').size().to_string())

    df_all = df_all.dropna(subset=['Site Name', 'Reporting_Metric'])
    print(f"\n   After removing nulls: {len(df_all):,} records (removed {before_drop - len(df_all):,})")

    # ========================================================================
    # SAVE OUTPUT
    # ========================================================================

    output_file = os.path.join(REP_OUTPUT_PATH, "rp2_metric_list.csv")
    df_all.to_csv(output_file, index=False, encoding='utf-8')

    print(f"\n✅ Saved to: {output_file}")
    print(f"   📊 {len(df_all):,} rows, {len(df_all.columns)} columns")

    # ========================================================================
    # SHOW SUMMARY
    # ========================================================================

    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)

    # Show by source
    print(f"\n📋 Records by Source:")
    for source in sorted(df_all['Source'].unique()):
        count = len(df_all[df_all['Source'] == source])
        print(f"      {source}: {count:,} records")

    # Show Site Area breakdown
    if 'Site Area' in df_all.columns:
        print(f"\n📋 Site Area breakdown (final):")
        area_counts = df_all['Site Area'].value_counts()
        for area, count in area_counts.items():
            print(f"      {area}: {count} rows")

    # Show unique metrics
    print(f"\n📋 Unique Reporting_Metric values:")
    unique_metrics = sorted(df_all['Reporting_Metric'].unique())
    for metric in unique_metrics:
        count = len(df_all[df_all['Reporting_Metric'] == metric])
        print(f"      {metric}: {count:,} records")

    # Show date range for Created At
    if 'Created At' in df_all.columns:
        df_all['Created At'] = pd.to_datetime(df_all['Created At'], errors='coerce', dayfirst=True)
        print(f"\n📋 Created At Date Range:")
        print(f"      Min: {df_all['Created At'].min()}")
        print(f"      Max: {df_all['Created At'].max()}")

    # Show date range for Completed At
    if 'Completed At' in df_all.columns:
        df_all['Completed At'] = pd.to_datetime(df_all['Completed At'], errors='coerce', dayfirst=True)
        print(f"\n📋 Completed At Date Range:")
        print(f"      Min: {df_all['Completed At'].min()}")
        print(f"      Max: {df_all['Completed At'].max()}")

    # Show date range for Filter Date
    if 'Filter Date' in df_all.columns:
        df_all['Filter Date'] = pd.to_datetime(df_all['Filter Date'], errors='coerce', dayfirst=True)
        print(f"\n📋 Filter Date Date Range:")
        print(f"      Min: {df_all['Filter Date'].min()}")
        print(f"      Max: {df_all['Filter Date'].max()}")

    # Show sample
    print("\n📋 Sample data (first 10 rows):")
    print(df_all.head(10).to_string(index=False))

    print("\n" + "=" * 80)
    print("🏁 COMPLETE")
    print("=" * 80)

    return df_all


def process_file(file_path, source_name, metric_filters, filter_date_column, created_date_column, completed_date_column, id_column, all_records, site_area_lookup_cleaned, site_area_lookup_original):
    """Process a single file and collect records with Site Name, Reporting_Metric, Dates, and ID"""

    if not os.path.exists(file_path):
        print(f"⚠️ File not found: {file_path}")
        return

    try:
        df = pd.read_csv(file_path, dtype=str, low_memory=False)
        print(f"\n📋 Processing: {source_name}")
        print(f"   Loaded {len(df):,} rows")

        if 'Reporting_Metric' not in df.columns:
            print(f"   ⚠️ 'Reporting_Metric' column not found!")
            print(f"   📋 Available columns: {list(df.columns)[:10]}...")
            return

        # ================================================================
        # APPLY METRIC FILTERS (if any)
        # FIXED: matches values even when Reporting_Metric is a
        # comma-separated block, e.g. "Work Area Inspections, Site Setup Audit"
        # Rows with multiple matches are exploded into one row per metric.
        # ================================================================
        if metric_filters:
            # Split each row's Reporting_Metric on comma, strip whitespace
            df['_metric_list'] = df['Reporting_Metric'].fillna('').apply(
                lambda x: [m.strip() for m in x.split(',') if m.strip()]
            )
            # Keep only the values that are in our allowed filter list
            df['_matched_metrics'] = df['_metric_list'].apply(
                lambda lst: [m for m in lst if m in metric_filters]
            )
            # Keep rows that matched at least one allowed metric
            df_filtered = df[df['_matched_metrics'].apply(len) > 0].copy()

            # Explode: one row per matched metric, so a row with two
            # matches produces two output rows instead of being dropped
            # or left merged as an unmatched combined string
            df_filtered = df_filtered.explode('_matched_metrics')
            df_filtered['Reporting_Metric'] = df_filtered['_matched_metrics']
            df_filtered = df_filtered.drop(columns=['_metric_list', '_matched_metrics'])

            print(f"   📊 Filtered to {len(df_filtered):,} rows with allowed metrics:")
            for metric in metric_filters:
                count = len(df_filtered[df_filtered['Reporting_Metric'] == metric])
                print(f"      {metric}: {count} rows")
        else:
            # No metric filter - keep all rows with non-empty Reporting_Metric
            df_filtered = df[df['Reporting_Metric'].notna() & (df['Reporting_Metric'] != '')].copy()
            print(f"   📊 Found {len(df_filtered):,} rows with Reporting_Metric")

        if df_filtered.empty:
            print(f"   ⚠️ No records after filtering")
            return

        # Find site column
        site_col = get_site_column(df_filtered)
        if not site_col:
            print(f"   ⚠️ No site column found!")
            return
        print(f"   🏷️  Using site column: '{site_col}'")

        # Check if ID column exists
        if id_column and id_column not in df_filtered.columns:
            print(f"   ⚠️ ID column '{id_column}' not found!")
            id_column = None
        if id_column:
            print(f"   🆔 Using ID column: '{id_column}'")

        # Check filter date column exists
        if filter_date_column not in df_filtered.columns:
            print(f"   ⚠️ Filter date column '{filter_date_column}' not found!")
            filter_date_column = None
        else:
            print(f"   🗓️  Filter date column: '{filter_date_column}'")

        # Check created date column exists
        if created_date_column not in df_filtered.columns:
            print(f"   ⚠️ Created date column '{created_date_column}' not found!")
            created_date_column = None
        else:
            print(f"   📅 Created date column: '{created_date_column}'")

        # Check completed date column exists
        if completed_date_column and completed_date_column not in df_filtered.columns:
            print(f"   ⚠️ Completed date column '{completed_date_column}' not found!")
            completed_date_column = None
        elif completed_date_column:
            print(f"   📅 Completed date column: '{completed_date_column}'")

        # Clean site names
        df_filtered['Site Name'] = df_filtered[site_col].apply(clean_site_name)

        # ------------------------------------------------------------------
        # FALLBACK: if the site column was blank, try to pull the site out
        # of the 'name' field instead
        # ------------------------------------------------------------------
        missing_before = df_filtered['Site Name'].isna().sum()
        if missing_before > 0 and 'name' in df_filtered.columns:
            fallback = df_filtered['name'].apply(extract_site_from_name)
            recovered = (df_filtered['Site Name'].isna() & fallback.notna()).sum()
            df_filtered['Site Name'] = df_filtered['Site Name'].fillna(fallback)
            if recovered > 0:
                print(f"   🔄 Recovered {recovered:,} Site Names from 'name' field fallback")

        missing_after = df_filtered['Site Name'].isna().sum()
        if missing_after > 0:
            print(f"   ⚠️ {missing_after:,} rows still have no Site Name")

        # ------------------------------------------------------------------
        # GET SITE AREA from lookup
        # ------------------------------------------------------------------
        df_filtered['Site Area'] = df_filtered['Site Name'].apply(
            lambda x: get_site_area(x, site_area_lookup_cleaned, site_area_lookup_original)
        )

        # Show how many got matched
        matched_count = df_filtered['Site Area'].notna().sum()
        print(f"   🏷️  Matched {matched_count:,} rows to a Site Area")

        # Show unmatched sites
        unmatched = df_filtered[df_filtered['Site Area'].isna()]['Site Name'].unique()
        if len(unmatched) > 0:
            print(f"   ⚠️ {len(unmatched)} unique sites could not be matched:")
            for site in unmatched[:5]:
                print(f"      - {site}")
            if len(unmatched) > 5:
                print(f"      ... and {len(unmatched) - 5} more")

        # ================================================================
        # ID: Get the ID column
        # ================================================================
        if id_column:
            df_filtered['ID'] = df_filtered[id_column]
            print(f"   🆔 Extracted IDs from '{id_column}'")
        else:
            df_filtered['ID'] = None

        # ================================================================
        # DATES: Store both Created At and Completed At
        # ================================================================

        # Get Created date using robust parser (UK format first)
        if created_date_column:
            df_filtered['Created At'] = df_filtered[created_date_column].apply(parse_date_robust)
            print(f"   📅 Created date column '{created_date_column}' - sample values:")
            sample_dates = df_filtered[created_date_column].head(3).tolist()
            for d in sample_dates:
                print(f"      {d}")
        else:
            df_filtered['Created At'] = None

        # Get Completed date using robust parser (UK format first)
        if completed_date_column:
            df_filtered['Completed At'] = df_filtered[completed_date_column].apply(parse_date_robust)
            print(f"   📅 Completed date column '{completed_date_column}' - sample values:")
            sample_dates = df_filtered[completed_date_column].head(3).tolist()
            for d in sample_dates:
                print(f"      {d}")
        else:
            df_filtered['Completed At'] = None

        # ================================================================
        # FILTER DATE: This is the column used for date filtering later
        # ================================================================
        if filter_date_column:
            df_filtered['Filter Date'] = df_filtered[filter_date_column].apply(parse_date_robust)
            print(f"   🗓️  Filter date column '{filter_date_column}' - sample values:")
            sample_dates = df_filtered[filter_date_column].head(3).tolist()
            for d in sample_dates:
                print(f"      {d}")
        else:
            df_filtered['Filter Date'] = None

        # Select columns
        df_result = df_filtered[['Site Name', 'Reporting_Metric', 'ID', 'Created At', 'Completed At', 'Filter Date', 'Site Area']].copy()
        df_result['Source'] = source_name

        # Add to all records
        all_records.extend(df_result.to_dict('records'))
        print(f"   ✅ Added {len(df_result):,} records")

    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()