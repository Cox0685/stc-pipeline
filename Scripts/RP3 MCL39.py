#!/usr/bin/env python
# coding: utf-8

"""
RP2 Metric Pivot Generator
Reads rp2_metric_list.csv, applies date filters, creates pivot table by site
Creates Excel with two tabs: 'Metric_Pivot' and 'Site_Totals'

FIXED (v2):
- Date parser now tries multiple known formats explicitly, instead of relying
  on a single strptime + a loose dayfirst=True fallback. The old fallback could
  silently mis-parse ambiguous strings (or parse ISO dates without you knowing
  it happened, other than a stray warning).
- Every row's parsing method is now tracked in a 'Date_Parse_Method' column,
  so you can see exactly how each date was interpreted.
- The script now DUMPS every 'Weekly H&S Inspection' row that gets excluded by
  the date filter to a CSV (weekly_hs_excluded_debug.csv) — raw value, parsed
  value, and parse method — so you can see precisely why any given row didn't
  make it into the July window instead of just trusting a total count.
- End-of-range comparison now includes the full end day (23:59:59) instead of
  midnight, as a safety net in case any Date_Parsed value ever carries a
  non-midnight time component.
"""

import os
import pandas as pd
from datetime import datetime, timedelta

# ============================================================================
# CONFIGURATION
# ============================================================================

REP_OUTPUT_PATH = r"C:\Users\Thomas.Cox\OneDrive - OCU Group\Desktop\00_AST_SystemsIntegration\00_AST_DataUploads\01_STC Safety Culture\Data\REP"

os.makedirs(REP_OUTPUT_PATH, exist_ok=True)

# ============================================================================
# DATE FILTER - UK FORMAT (DD/MM/YYYY)
# ============================================================================

DATE_FILTER_START = "01/08/2026"
DATE_FILTER_END = "31/08/2026"

FILTER_START_DATE = datetime.strptime(DATE_FILTER_START, "%d/%m/%Y")
# Push end date to the last moment of that day, so any date value that still
# carries a time component (shouldn't happen post-parsing, but just in case)
# doesn't get excluded for being "after midnight" on the last day.
FILTER_END_DATE = datetime.strptime(DATE_FILTER_END, "%d/%m/%Y") + timedelta(hours=23, minutes=59, seconds=59)

# ============================================================================
# METRICS EXCLUDED FROM DATE FILTERING (ALL TIME)
# ============================================================================

EXCLUDED_FROM_DATE_FILTER = [
    "Overdue Safety",
    "Overdue Environmental",
    "Overdue Quality",
]

# ============================================================================
# FINAL METRICS (columns to display) - WITHOUT "Count"
# ============================================================================

FINAL_METRICS = [
    # Site Reports
    "SubCon Audits",
    "Weekly HS Inspection",
    "Work Area Inspections",

    # Overdue
    "Overdue Quality Action",
    "Overdue Environmental Action",
    "Overdue Safety Action",

    # SORs
    "Env SOR Neg",
    "Env SOR Pos",
    "Safety SOR Neg",
    "Safety SOR Pos",
    "SOR Frequency Rate",

    # SOR Totals
    "Open SORS",
    "Resolved SORS",

    # Incident Types
    "Accidents",
    "Environmental Incidents",
    "Near Misses",
    "Property Damage",
    "Security Breaches",
    "Service Strikes",

    # Contracts Managers
    "Contracts Managers Audits",

    # Placeholder
    "Senior Leadership Visits",

    # QSET
    "QSET Environmental",
    "QSET HS Inspection",
    "QSET Quality Inspections",
]

# ============================================================================
# METRIC MAPPING - Maps original metrics to final column names
# ============================================================================

METRIC_MAPPING = {
    # Site Reports
    "SubCon Audits": "SubCon Audits",
    "Weekly H&S Inspection": "Weekly HS Inspection",
    "Work Area Inspections": "Work Area Inspections",
    "Site Setup Audit": "DROP",

    # Overdue
    "Overdue Quality": "Overdue Quality Action",
    "Overdue Environmental": "Overdue Environmental Action",
    "Overdue Safety": "Overdue Safety Action",
    "Overdue Uncategorized": "DROP",

    # SORs - Negative/Positive by type (Open + Resolved combined)
    "Open ENV -": "Env SOR Neg",
    "Resolved ENV -": "Env SOR Neg",
    "Open ENV +": "Env SOR Pos",
    "Resolved ENV +": "Env SOR Pos",
    "Open SOR -": "Safety SOR Neg",
    "Resolved SOR -": "Safety SOR Neg",
    "Open SOR +": "Safety SOR Pos",
    "Resolved SOR +": "Safety SOR Pos",

    # Incident Types
    "Open Accident (Personal Injury)": "Accidents",
    "Resolved Accident (Personal Injury)": "Accidents",
    "Open Environmental Incident": "Environmental Incidents",
    "Resolved Environmental Incident": "Environmental Incidents",
    "Open Near Miss / Unplanned Event": "Near Misses",
    "Resolved Near Miss / Unplanned Event": "Near Misses",
    "Property Damage": "Property Damage",
    "Security Breaches": "Security Breaches",
    "Service Strikes": "Service Strikes",

    # Contracts Managers
    "Contracts Managers Audits": "Contracts Managers Audits",

    # QSET
    "QSET Environmental": "QSET Environmental",
    "QSET H&S Inspection": "QSET HS Inspection",
    "QSET Quality Inspections": "QSET Quality Inspections",

    # Resolved Actions - KEEP AS SEPARATE METRICS FOR SITE TOTALS
    "Resolved Safety": "Resolved Safety",
    "Resolved Quality": "Resolved Quality",
    "Resolved Environmental": "Resolved Environmental",

    # DROP these
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
# METRIC LISTS FOR CALCULATIONS
# ============================================================================

OPEN_SOR_METRICS = ["Open SOR +", "Open SOR -", "Open ENV +", "Open ENV -"]
RESOLVED_SOR_METRICS = ["Resolved SOR +", "Resolved SOR -", "Resolved ENV +", "Resolved ENV -"]

# Resolved Actions source metrics (for Site Totals)
RESOLVED_ACTIONS_METRICS = ["Resolved Safety", "Resolved Quality", "Resolved Environmental"]

# Metrics that should ALWAYS be 0 (placeholders)
PLACEHOLDER_METRICS = [
    "SOR Frequency Rate",
    "Senior Leadership Visits",
    "Property Damage",
    "Security Breaches",
    "Service Strikes",
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
    Tries each format in KNOWN_FORMATS in order (DD/MM/YYYY variants first,
    since that's the expected UK format). Falls back to pandas' general
    parser with dayfirst=True only as a last resort, and flags it clearly
    so you can spot rows that needed it.
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
        # Excel's epoch (1899-12-30) — handles the classic 1900 leap-year bug
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


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 80)
    print("⚔️  RP2 METRIC PIVOT GENERATOR - ROBUST DATE PARSING (v2)")
    print("=" * 80)
    print(f"📅 Date Filter: {DATE_FILTER_START} to {DATE_FILTER_END} (inclusive, full end day)")
    print(f"   Excluded from date filter: {EXCLUDED_FROM_DATE_FILTER}")
    print("=" * 80)

    input_file = os.path.join(REP_OUTPUT_PATH, "rp2_metric_list.csv")

    if not os.path.exists(input_file):
        print(f"❌ Input file not found: {input_file}")
        return

    df = pd.read_csv(input_file, dtype=str, low_memory=False)
    print(f"\n📂 Loaded {len(df):,} rows from rp2_metric_list.csv")

    if 'Filter Date' not in df.columns:
        print(f"\n   ❌ 'Filter Date' column not found!")
        print(f"   📋 Available columns: {list(df.columns)}")
        return

    print(f"\n   ✅ Using 'Filter Date' column for date filtering")

    # ------------------------------------------------------------------
    # Parse dates with the robust parser, tracking method per row
    # ------------------------------------------------------------------
    parsed_results = df['Filter Date'].apply(parse_date_robust)
    df['Date_Parsed'] = parsed_results.apply(lambda x: x[0])
    df['Date_Parse_Method'] = parsed_results.apply(lambda x: x[1])

    valid_dates = df['Date_Parsed'].notna().sum()
    invalid_dates = df['Date_Parsed'].isna().sum()

    print(f"\n   📊 Date parsing results:")
    print(f"      Valid dates: {valid_dates:,}")
    print(f"      Invalid dates: {invalid_dates:,}")

    print(f"\n   📊 Parse method breakdown (all rows):")
    print(df['Date_Parse_Method'].value_counts().to_string())

    if invalid_dates > 0:
        print(f"\n   ⚠️ Sample invalid dates:")
        invalid_samples = df[df['Date_Parsed'].isna()]['Filter Date'].head(10).tolist()
        for sample in invalid_samples:
            print(f"      {sample!r}")

    # ------------------------------------------------------------------
    # Check Weekly H&S Inspection specifically
    # ------------------------------------------------------------------
    weekly_mask_all = df['Reporting_Metric'] == 'Weekly H&S Inspection'
    weekly_total = weekly_mask_all.sum()
    weekly_valid = (weekly_mask_all & df['Date_Parsed'].notna()).sum()
    weekly_invalid = weekly_total - weekly_valid

    print(f"\n   📊 Weekly H&S Inspection:")
    print(f"      Total records: {weekly_total}")
    print(f"      Valid dates: {weekly_valid}")
    print(f"      Invalid dates: {weekly_invalid}")
    print(f"\n   📊 Weekly H&S Inspection parse method breakdown:")
    print(df.loc[weekly_mask_all, 'Date_Parse_Method'].value_counts().to_string())

    # ------------------------------------------------------------------
    # Apply date filter (with exceptions) + DEBUG DUMP for Weekly H&S
    # ------------------------------------------------------------------
    print(f"\n⚔️ Applying date filter...")

    is_overdue = df['Reporting_Metric'].isin(EXCLUDED_FROM_DATE_FILTER)
    date_mask = (df['Date_Parsed'] >= FILTER_START_DATE) & (df['Date_Parsed'] <= FILTER_END_DATE)

    weekly_before_filter = weekly_total
    weekly_in_range = (weekly_mask_all & date_mask).sum()
    weekly_outside = weekly_before_filter - weekly_in_range

    print(f"\n   📊 Weekly H&S Inspection date filter:")
    print(f"      Total: {weekly_before_filter}")
    print(f"      In date range: {weekly_in_range}")
    print(f"      Outside date range: {weekly_outside}")

    # --- DEBUG EXPORT: every Weekly H&S row that got excluded, with the
    #     exact raw string, parsed value, and parse method used. This is
    #     the file to open to see WHY any specific row didn't make it in. ---
    debug_cols = [c for c in ['Site Name', 'Reporting_Metric', 'ID', 'Created At',
                               'Completed At', 'Filter Date', 'Date_Parsed',
                               'Date_Parse_Method'] if c in df.columns]
    weekly_excluded = df.loc[weekly_mask_all & ~date_mask, debug_cols].copy()
    weekly_excluded = weekly_excluded.sort_values('Date_Parsed', na_position='first')

    debug_file = os.path.join(REP_OUTPUT_PATH, "weekly_hs_excluded_debug.csv")
    weekly_excluded.to_csv(debug_file, index=False, encoding='utf-8')
    print(f"\n   🔍 Wrote {len(weekly_excluded):,} excluded Weekly H&S rows to:")
    print(f"      {debug_file}")

    # Also dump the INCLUDED rows so you can cross-check the count of 65 vs
    # your own manual list of 74 directly, row by row.
    weekly_included = df.loc[weekly_mask_all & date_mask, debug_cols].copy()
    weekly_included = weekly_included.sort_values('Date_Parsed')
    included_file = os.path.join(REP_OUTPUT_PATH, "weekly_hs_included_debug.csv")
    weekly_included.to_csv(included_file, index=False, encoding='utf-8')
    print(f"   🔍 Wrote {len(weekly_included):,} included Weekly H&S rows to:")
    print(f"      {included_file}")

    # Apply filter
    df_filtered = df[is_overdue | date_mask].copy()

    print(f"\n   📊 After filtering: {len(df_filtered):,} rows")

    overdue_count = df_filtered[df_filtered['Reporting_Metric'].isin(EXCLUDED_FROM_DATE_FILTER)].shape[0]
    non_overdue_count = df_filtered[~df_filtered['Reporting_Metric'].isin(EXCLUDED_FROM_DATE_FILTER)].shape[0]
    print(f"      - Overdue metrics (all time): {overdue_count:,} rows")
    print(f"      - Non-overdue metrics (date range): {non_overdue_count:,} rows")

    if df_filtered.empty:
        print("\n⚠️ No records after filtering!")
        return

    # ------------------------------------------------------------------
    # Apply metric mapping
    # ------------------------------------------------------------------
    print(f"\n⚔️ Applying metric mapping...")

    dropped_count = 0
    mapped_count = 0

    def map_metric(metric):
        nonlocal dropped_count, mapped_count
        if metric in METRIC_MAPPING:
            new_metric = METRIC_MAPPING[metric]
            if new_metric == "DROP":
                dropped_count += 1
                return None
            if new_metric != metric:
                mapped_count += 1
            return new_metric
        return metric

    df_filtered['Mapped_Metric'] = df_filtered['Reporting_Metric'].apply(map_metric)
    df_filtered = df_filtered[df_filtered['Mapped_Metric'].notna()].copy()

    print(f"\n   📊 After mapping:")
    print(f"      - Dropped rows: {dropped_count:,}")
    print(f"      - Mapped rows: {mapped_count:,}")
    print(f"      - Remaining rows: {len(df_filtered):,}")

    if df_filtered.empty:
        print("\n⚠️ No records after mapping!")
        return

    df_filtered = df_filtered.dropna(subset=['Site Name', 'Mapped_Metric'])
    print(f"\n   After removing nulls: {len(df_filtered):,} rows")

    if df_filtered.empty:
        print("\n⚠️ No records after removing nulls!")
        return

    # ------------------------------------------------------------------
    # Create pivot table
    # ------------------------------------------------------------------
    print(f"\n⚔️ Creating pivot table...")

    pivot_df = df_filtered.groupby(['Site Name', 'Mapped_Metric']).size().reset_index(name='Count')
    pivot_table = pivot_df.pivot(index='Site Name', columns='Mapped_Metric', values='Count').fillna(0).astype(int)

    weekly_in_pivot = pivot_table['Weekly HS Inspection'].sum() if 'Weekly HS Inspection' in pivot_table.columns else 0
    print(f"\n   📊 Weekly HS Inspection in pivot: {weekly_in_pivot}")

    # ------------------------------------------------------------------
    # Calculate Open SORS and Resolved SORS
    # ------------------------------------------------------------------
    print(f"\n⚔️ Calculating Open SORS and Resolved SORS...")

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

    # ------------------------------------------------------------------
    # Build final pivot with correct column order
    # ------------------------------------------------------------------
    print(f"\n⚔️ Building final pivot with correct column order...")

    final_pivot = pd.DataFrame(index=pivot_table.index)

    for metric in FINAL_METRICS:
        if metric in ["Open SORS", "Resolved SORS"]:
            if metric in pivot_totals_table.columns:
                final_pivot[metric] = pivot_totals_table[metric]
            else:
                final_pivot[metric] = 0
        elif metric in PLACEHOLDER_METRICS:
            final_pivot[metric] = 0
        else:
            if metric in pivot_table.columns:
                final_pivot[metric] = pivot_table[metric]
            else:
                final_pivot[metric] = 0

    # ------------------------------------------------------------------
    # Calculate Resolved Actions from source metrics for Site Totals
    # ------------------------------------------------------------------
    print(f"\n⚔️ Calculating Resolved Actions from source metrics...")

    resolved_safety = pivot_table['Resolved Safety'] if 'Resolved Safety' in pivot_table.columns else pd.Series(0, index=pivot_table.index)
    resolved_quality = pivot_table['Resolved Quality'] if 'Resolved Quality' in pivot_table.columns else pd.Series(0, index=pivot_table.index)
    resolved_environmental = pivot_table['Resolved Environmental'] if 'Resolved Environmental' in pivot_table.columns else pd.Series(0, index=pivot_table.index)

    total_resolved_actions = resolved_safety + resolved_quality + resolved_environmental
    final_pivot['Total Resolved Actions'] = total_resolved_actions

    # ------------------------------------------------------------------
    # Sort by index (Site Name)
    # ------------------------------------------------------------------
    final_pivot = final_pivot.sort_index()

    # ------------------------------------------------------------------
    # Create Site Totals tab
    # ------------------------------------------------------------------
    print(f"\n⚔️ Creating Site Totals...")

    site_totals = final_pivot.copy()

    site_totals['Total Overdue Actions'] = (
        site_totals['Overdue Quality Action'] +
        site_totals['Overdue Environmental Action'] +
        site_totals['Overdue Safety Action']
    )

    site_totals['Total Incidents'] = (
        site_totals['Accidents'] +
        site_totals['Environmental Incidents'] +
        site_totals['Near Misses'] +
        site_totals['Property Damage'] +
        site_totals['Security Breaches'] +
        site_totals['Service Strikes']
    )

    site_totals['Total Leadership'] = (
        site_totals['Contracts Managers Audits'] +
        site_totals['Senior Leadership Visits']
    )

    site_totals['Total QSET'] = (
        site_totals['QSET Environmental'] +
        site_totals['QSET HS Inspection'] +
        site_totals['QSET Quality Inspections']
    )

    site_totals['Total Open SORs'] = site_totals['Open SORS']
    site_totals['Total Resolved SORs'] = site_totals['Resolved SORS']

    site_totals_columns = [
        'Site Name',
        'Total Overdue Actions',
        'Total Resolved Actions',
        'Total Incidents',
        'Total Leadership',
        'Total QSET',
        'Total Open SORs',
        'Total Resolved SORs'
    ]

    existing_site_totals_cols = [col for col in site_totals_columns if col in site_totals.columns]
    df_site_totals = site_totals[existing_site_totals_cols].copy()
    df_site_totals = df_site_totals.reset_index()

    print(f"   ✅ Created Site Totals with {len(df_site_totals)} sites, {len(df_site_totals.columns)} columns")

    # ------------------------------------------------------------------
    # Save to Excel
    # ------------------------------------------------------------------
    output_file = os.path.join(REP_OUTPUT_PATH, "rp2_metric_pivot_by_site.xlsx")

    try:
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            final_pivot.to_excel(writer, sheet_name='Metric_Pivot', index=True)
            print(f"\n✅ Saved 'Metric_Pivot' sheet to: {output_file}")
            print(f"   📊 {len(final_pivot):,} sites, {len(final_pivot.columns)} columns")

            df_site_totals.to_excel(writer, sheet_name='Site_Totals', index=False)
            print(f"✅ Saved 'Site_Totals' sheet")
            print(f"   📊 {len(df_site_totals):,} sites, {len(df_site_totals.columns)} columns")

    except ModuleNotFoundError:
        print(f"\n⚠️ openpyxl not found. Please install: pip install openpyxl")
        print(f"   Saving as CSV instead...")

        csv_file = os.path.join(REP_OUTPUT_PATH, "rp2_metric_pivot_by_site.csv")
        final_pivot.to_csv(csv_file, index=True, encoding='utf-8')
        print(f"✅ Saved pivot to CSV: {csv_file}")

        csv_totals_file = os.path.join(REP_OUTPUT_PATH, "rp2_site_totals.csv")
        df_site_totals.to_csv(csv_totals_file, index=False, encoding='utf-8')
        print(f"✅ Saved Site Totals to CSV: {csv_totals_file}")

    # ------------------------------------------------------------------
    # Show summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("📊 PIVOT TABLE SUMMARY")
    print("=" * 80)

    print(f"\n📋 Total Sites: {len(final_pivot):,}")
    print(f"📋 Total Metrics: {len(final_pivot.columns)}")

    print(f"\n📋 Weekly H&S Inspection count breakdown:")
    print(f"   Original in file: {weekly_total}")
    print(f"   Valid dates: {weekly_valid}")
    print(f"   In date range: {weekly_in_range}")
    print(f"   In final pivot: {weekly_in_pivot}")
    print(f"   >>> See weekly_hs_excluded_debug.csv for the {weekly_outside} excluded rows")
    print(f"   >>> See weekly_hs_included_debug.csv for the {weekly_in_range} included rows")

    print(f"\n📋 Site Totals Summary:")
    for col in df_site_totals.columns:
        if col != 'Site Name':
            total = df_site_totals[col].sum()
            print(f"      {col:<25} total: {total:>8,}")

    print("\n📋 Sample Site Totals (first 10 rows):")
    print(df_site_totals.head(10).to_string())

    print("\n" + "=" * 80)
    print("🏁 PIVOT GENERATOR COMPLETE")
    print("=" * 80)

    return final_pivot


if __name__ == "__main__":
    main()