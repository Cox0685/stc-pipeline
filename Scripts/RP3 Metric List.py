#!/usr/bin/env python
# coding: utf-8

"""
Reporting Metric List Generator
Creates a simple list of Source Table, Reporting_Metric, and Date Column
NO FILTERING BY DATE - shows ALL records
Cross-references with rp2_site_status.csv to filter by Site Area

FIXED VERSION (v2 - date parser now matches RP3 MCL39.py's standard):
- "Site Setup Audit" added to rp2_site_reports metric filter list
- Metric filtering now matches values inside comma-separated
  Reporting_Metric cells (e.g. "Work Area Inspections, Site Setup Audit")
  instead of requiring an exact whole-cell match. Rows with multiple
  matching metrics are exploded into one row per matched metric so
  none are silently dropped.
- CHANGED: rp2_site_reports and rp2_QSET_reports now use 'conducted_on' 
  instead of 'created_at' or 'date_completed' for the Filter Date column
- FIXED: UK date format support (DD/MM/YYYY) with dayfirst=True
- v2: Replaced the old single-pass parse_date_robust() with the same
  explicit-multi-format parser used downstream in RP3 MCL39.py (tries a
  known list of formats first, Excel serial numbers second, a loose
  dayfirst=True parse only as a last resort). The old version could
  silently fail to parse a row with no visible trace of why - this one
  tracks which method actually matched for the 'Filter Date' column (the
  one that drives downstream date filtering in MCL39) in a new
  'Filter Date Method' column, and prints a breakdown per source so a bad
  parse is visible the moment this script runs, not several stages later.
- v2: Removed get_id_column() - it was fully defined but never actually
  called (id_column comes from the hardcoded file_configs tuples instead).
"""

import os
import sys
import pandas as pd
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
        "Site Setup Audit",         # <-- ADDED
        "Site Shut Down Audit"      # <-- ADDED (separate metric, requires Complete)
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


# ============================================================================
# ROBUST DATE PARSER (v2) - matches RP3 MCL39.py's standard
# ============================================================================
# Tries each explicit format in KNOWN_FORMATS first (UK DD/MM/YYYY variants
# ahead of anything ambiguous), then an Excel serial-date number, then a
# loose dayfirst=True parse as an absolute last resort. Returns
# (parsed_timestamp_or_NaT, method_used_str) so a silent misparse is always
# visible in the output, not just a blank cell with no explanation.

KNOWN_FORMATS = [
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y %H:%M",
    "%d-%m-%Y",
    "%d.%m.%Y %H:%M:%S",
    "%d.%m.%Y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%m/%d/%Y %H:%M:%S",
    "%m/%d/%Y %H:%M",
    "%m/%d/%Y",
]


def parse_date_robust(date_str):
    """
    Returns (parsed_timestamp_or_NaT, method_used_str).
    Tries each format in KNOWN_FORMATS in order (DD/MM/YYYY variants first,
    since that's the expected UK format). Falls back to an Excel serial
    date number, then pandas' general parser with dayfirst=True only as a
    last resort - flagged clearly so a fallback parse is never silent.
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

    # Excel serial date number (e.g. a CSV that carries a date as a raw number)
    try:
        serial = float(raw)
        parsed = pd.Timestamp("1899-12-30") + pd.to_timedelta(serial, unit="D")
        return parsed, "excel_serial"
    except (ValueError, TypeError):
        pass

    # Last-resort loose parse - flagged so you know it wasn't a clean match
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


def load_site_status_lookup():
    """
    Load rp2_site_status.csv and create lookup dictionaries for Site Area.
    Returns dictionaries mapping site name (cleaned and original) to Site Area.
    """
    site_status_file = f"{REP_PREFIX}/rp2_site_status.csv"

    if not client.exists(site_status_file):
        print(f"   ⚠️ rp2_site_status.csv not found at: {site_status_file}")
        print(f"   ⚠️ Please run RP2 site status report first.")
        return {}, {}

    try:
        df_sites = client.read_csv(site_status_file, dtype=str, low_memory=False)
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
    print("⚔️  REPORTING METRIC LIST GENERATOR (v2 - robust date parsing)")
    print("=" * 80)
    print("📋 NO DATE FILTERING - Showing ALL records")
    print(f"🔍 Site Area Filter: Only include '{VALID_SITE_AREAS}'")
    print("📅 rp2_site_reports and rp2_QSET_reports use 'conducted_on'")
    print("🇬🇧 UK Date Format: DD/MM/YYYY (explicit formats tried first)")
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
    # rp2_site_reports and rp2_QSET_reports use 'conducted_on' for the
    # Filter Date column.
    # ========================================================================

    file_configs = [
        # Site Reports - using conducted_on for filtering
        (f"{REP_PREFIX}/rp2_site_reports.csv", "rp2_site_reports", 
         METRIC_FILTERS["rp2_site_reports"], "conducted_on", "created_at", "date_completed", "id"),
        
        # QSET Reports - using conducted_on for filtering
        (f"{REP_PREFIX}/rp2_QSET_reports.csv", "rp2_QSET_reports", 
         METRIC_FILTERS["rp2_QSET_reports"], "conducted_on", "created_at", "date_completed", "id"),
        
        # Contracts Managers - still using date_completed
        (f"{REP_PREFIX}/rp2_contracts_managers_audits.csv", "rp2_contracts_managers_audits", 
         METRIC_FILTERS["rp2_contracts_managers_audits"], "date_completed", "created_at", "date_completed", "id"),

        # Other files - use task_created_at for filtering
        (f"{REP_PREFIX}/rp2_incidents.csv", "rp2_incidents", 
         None, "task_created_at", "task_created_at", None, "task_unique_id"),

        # GLD files - id column is 'task_unique_id'
        (f"{GLD_PREFIX}/gld_actions.csv", "gld_actions", 
         None, "task_created_at", "task_created_at", None, "task_unique_id"),
        (f"{GLD_PREFIX}/gld_issues.csv", "gld_issues", 
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
    # FILTER DATE PARSE METHOD BREAKDOWN - visibility into how many rows
    # needed a fallback parse (or failed entirely) before this feeds MCL39
    # ========================================================================
    if 'Filter Date Method' in df_all.columns:
        print(f"\n📋 'Filter Date' parse method breakdown (all sources combined):")
        print(df_all['Filter Date Method'].value_counts().to_string())

        fallback_or_bad = df_all['Filter Date Method'].isin(['FALLBACK_dayfirst_loose', 'UNPARSEABLE'])
        if fallback_or_bad.any():
            print(f"\n   ⚠️ {fallback_or_bad.sum():,} row(s) needed a loose fallback parse or "
                  f"failed to parse entirely - these are the ones most likely to be silently "
                  f"excluded (or wrongly included) by MCL39's date filter downstream.")
            print(df_all.loc[fallback_or_bad, ['Source', 'Site Name', 'Reporting_Metric', 'Filter Date Method']]
                  .head(10).to_string(index=False))

    # ========================================================================
    # SAVE OUTPUT
    # ========================================================================

    output_file = f"{REP_PREFIX}/rp2_metric_list.csv"
    client.write_csv(df_all, output_file, index=False, encoding='utf-8')

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
        created_dt = pd.to_datetime(df_all['Created At'], errors='coerce')
        print(f"\n📋 Created At Date Range:")
        print(f"      Min: {created_dt.min()}")
        print(f"      Max: {created_dt.max()}")

    # Show date range for Completed At
    if 'Completed At' in df_all.columns:
        completed_dt = pd.to_datetime(df_all['Completed At'], errors='coerce')
        print(f"\n📋 Completed At Date Range:")
        print(f"      Min: {completed_dt.min()}")
        print(f"      Max: {completed_dt.max()}")

    # Show date range for Filter Date
    if 'Filter Date' in df_all.columns:
        filter_dt = pd.to_datetime(df_all['Filter Date'], errors='coerce')
        print(f"\n📋 Filter Date Date Range:")
        print(f"      Min: {filter_dt.min()}")
        print(f"      Max: {filter_dt.max()}")

    # Show sample
    print("\n📋 Sample data (first 10 rows):")
    print(df_all.head(10).to_string(index=False))

    print("\n" + "=" * 80)
    print("🏁 COMPLETE")
    print("=" * 80)

    return df_all


def process_file(file_path, source_name, metric_filters, filter_date_column, created_date_column, completed_date_column, id_column, all_records, site_area_lookup_cleaned, site_area_lookup_original):
    """Process a single file and collect records with Site Name, Reporting_Metric, Dates, and ID"""

    if not client.exists(file_path):
        print(f"⚠️ File not found: {file_path}")
        return

    try:
        df = client.read_csv(file_path, dtype=str, low_memory=False)
        print(f"\n📋 Processing: {source_name}")
        print(f"   Loaded {len(df):,} rows")

        if 'Reporting_Metric' not in df.columns:
            print(f"   ⚠️ 'Reporting_Metric' column not found!")
            print(f"   📋 Available columns: {list(df.columns)[:10]}...")
            return

        # ================================================================
        # APPLY METRIC FILTERS (if any)
        # Matches values even when Reporting_Metric is a comma-separated
        # block, e.g. "Work Area Inspections, Site Setup Audit". Rows with
        # multiple matches are exploded into one row per metric.
        # ================================================================
        if metric_filters:
            df['_metric_list'] = df['Reporting_Metric'].fillna('').apply(
                lambda x: [m.strip() for m in x.split(',') if m.strip()]
            )
            df['_matched_metrics'] = df['_metric_list'].apply(
                lambda lst: [m for m in lst if m in metric_filters]
            )
            df_filtered = df[df['_matched_metrics'].apply(len) > 0].copy()

            df_filtered = df_filtered.explode('_matched_metrics')
            df_filtered['Reporting_Metric'] = df_filtered['_matched_metrics']
            df_filtered = df_filtered.drop(columns=['_metric_list', '_matched_metrics'])

            print(f"   📊 Filtered to {len(df_filtered):,} rows with allowed metrics:")
            for metric in metric_filters:
                count = len(df_filtered[df_filtered['Reporting_Metric'] == metric])
                print(f"      {metric}: {count} rows")
        else:
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
        # DATES: Store Created At, Completed At, and Filter Date - all
        # using the same v2 robust parser. Filter Date also gets its parse
        # method tracked, since that's the one column MCL39 actually
        # filters on downstream.
        # ================================================================

        if created_date_column:
            df_filtered['Created At'], _ = parse_date_series(df_filtered[created_date_column])
            print(f"   📅 Created date column '{created_date_column}' - sample values:")
            for d in df_filtered[created_date_column].head(3).tolist():
                print(f"      {d}")
        else:
            df_filtered['Created At'] = None

        if completed_date_column:
            df_filtered['Completed At'], _ = parse_date_series(df_filtered[completed_date_column])
            print(f"   📅 Completed date column '{completed_date_column}' - sample values:")
            for d in df_filtered[completed_date_column].head(3).tolist():
                print(f"      {d}")
        else:
            df_filtered['Completed At'] = None

        if filter_date_column:
            df_filtered['Filter Date'], df_filtered['Filter Date Method'] = parse_date_series(df_filtered[filter_date_column])
            print(f"   🗓️  Filter date column '{filter_date_column}' - sample values:")
            for d in df_filtered[filter_date_column].head(3).tolist():
                print(f"      {d}")
            method_counts = df_filtered['Filter Date Method'].value_counts()
            non_exact = method_counts[~method_counts.index.str.startswith('exact:')] if not method_counts.empty else method_counts
            if not non_exact.empty and non_exact.sum() > 0:
                print(f"   ⚠️  Non-exact parse methods used: {non_exact.to_dict()}")
        else:
            df_filtered['Filter Date'] = None
            df_filtered['Filter Date Method'] = None

        # Select columns
        df_result = df_filtered[['Site Name', 'Reporting_Metric', 'ID', 'Created At', 'Completed At',
                                  'Filter Date', 'Filter Date Method', 'Site Area']].copy()
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