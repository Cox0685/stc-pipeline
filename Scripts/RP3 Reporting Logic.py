#!/usr/bin/env python
# coding: utf-8

"""
Reporting Metric Generator
Adds Reporting_Metric column to multiple CSV files based on rules
Returns ALL matching metrics, comma-separated, for every file - a single
row can legitimately match more than one rule at once (e.g. a
template_category listing "Site Shut Down Audit, Weekly H&S Inspection"
both apply to the same submission), and every match needs to survive, not
just the first one checked.

v2: Added "Site Shut Down Audit" as a new metric - Site Reports group,
requires Complete status, matches template_category containing
"Site Shut Down Audit". Separate metric from "Site Setup Audit" (which
stays exactly as it was, ANY status) - not a rename.

v3: get_reporting_metric_single() is retired. It returned on the FIRST
matching rule and stopped, silently discarding every other match on the
same row - confirmed happening for real with template_category values
like "Site Shut Down Audit, Weekly H&S Inspection, QSET H&S Inspection".
Every file now uses the same multi-match, comma-separated logic that
inspections always used. RP3 Metric List.py's comma-exploding logic
already treats every source uniformly, so nothing downstream needed to
change for this - it was already built to receive multi-value metrics
from any file, this was the only place still handing it single values.
"""

import os
import sys
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_shared"))
import azure_io

# ============================================================================
# CONFIGURATION
# ============================================================================

GLD_PREFIX = "GLD"
REP_PREFIX = "REP"

client = azure_io.get_client()

# ============================================================================
# ISSUE CATEGORY TRANSLATION MAP
# ============================================================================

ISSUE_CATEGORY_MAP = {
    "001 SOR - POSITIVE": "SOR +",
    "004 ENVIRONMENTAL SOR - NEGATIVE": "ENV -",
    "002 SOR - NEGATIVE": "SOR -",
    "003 ENVIRONMENTAL SOR - POSITIVE": "ENV +"
}

# ============================================================================
# METRIC FUNCTIONS
# ============================================================================

def get_reporting_metric(row):
    """
    Returns ALL matching metrics for a row, comma-separated. Used for
    every file - inspections, site reports, QSET, and CM audits alike.
    A single row can legitimately satisfy more than one rule at once
    (multiple categories in template_category, all matching the same
    Reporting_Group + Reporting_Status), and every match must survive.
    """
    group = str(row.get('Reporting_Group', '')).strip()
    template = str(row.get('template_category', '')).strip()
    status = str(row.get('Reporting_Status', '')).strip()
    
    # List to collect all matching metrics
    matching_metrics = []
    
    # ============================================================
    # STEP 1: Site Reports Metrics (require "Site Reports" in group)
    # ============================================================
    if "Site Reports" in group:
        # Work Area Inspections (ANY status)
        if "Work Area Inspections" in template:
            matching_metrics.append("Work Area Inspections")
        
        # Site Setup Audit (ANY status)
        if "Site Setup Audit" in template:
            matching_metrics.append("Site Setup Audit")
        
        # Site Reports metrics that require "Complete" status
        if status == "Complete":
            if "Weekly H&S Inspection" in template:
                matching_metrics.append("Weekly H&S Inspection")
            if "SubCon Audits" in template:
                matching_metrics.append("SubCon Audits")
            if "Weekly ESG Report" in template:
                matching_metrics.append("Weekly ESG Report")
            # Site Shut Down Audit - separate metric from Site Setup Audit
            # above, deliberately requires Complete status.
            if "Site Shut Down Audit" in template:
                matching_metrics.append("Site Shut Down Audit")
    
    # ============================================================
    # STEP 2: QSET Metrics (require "QSET" in group + "Complete")
    # ============================================================
    if status == "Complete" and "QSET" in group:
        if "QSET H&S Inspection" in template:
            matching_metrics.append("QSET H&S Inspection")
        if "QSET Environmental" in template:
            matching_metrics.append("QSET Environmental")
        if "QSET Quality Inspections" in template:
            matching_metrics.append("QSET Quality Inspections")
    
    # ============================================================
    # STEP 3: CM Audits Metrics (require "CM Audits" in group + "Complete")
    # ============================================================
    if status == "Complete" and "CM Audits" in group:
        if "Contracts Managers Audits" in template:
            matching_metrics.append("Contracts Managers Audits")
    
    # ============================================================
    # Return all matching metrics, comma-separated
    # ============================================================
    if matching_metrics:
        # Remove duplicates while preserving order
        seen = set()
        unique_metrics = []
        for metric in matching_metrics:
            if metric not in seen:
                seen.add(metric)
                unique_metrics.append(metric)
        return ", ".join(unique_metrics)
    else:
        return None

# ============================================================================
# PROCESS FUNCTIONS
# ============================================================================

def process_file(filename, folder_path, metric_func):
    """Generic function to process a file with the specified metric logic"""
    print("\n" + "=" * 80)
    print(f"📋 PROCESSING: {filename}")
    print("=" * 80)
    
    input_file = f"{folder_path}/{filename}"
    
    if not client.exists(input_file):
        print(f"❌ File not found: {input_file}")
        return
    
    try:
        df = client.read_csv(input_file, dtype=str, low_memory=False)
        print(f"   ✅ Loaded {len(df):,} rows")
        
        # Check required columns
        if 'Reporting_Group' not in df.columns:
            print(f"   ❌ 'Reporting_Group' column not found!")
            return
        
        if 'template_category' not in df.columns:
            print(f"   ❌ 'template_category' column not found!")
            return
        
        if 'Reporting_Status' not in df.columns:
            print(f"   ❌ 'Reporting_Status' column not found!")
            return
        
        # Apply the metric logic using the provided function
        df['Reporting_Metric'] = df.apply(metric_func, axis=1)
        
        # Save back
        client.write_csv(df, input_file, index=False, encoding='utf-8')
        print(f"   ✅ Saved to: {input_file}")
        print(f"   📊 {len(df):,} rows, Reporting_Metric added")
        
        # Show summary
        metric_counts = df['Reporting_Metric'].value_counts()
        print(f"\n   📊 Reporting_Metric distribution:")
        for metric, count in metric_counts.items():
            print(f"      {metric}: {count} rows")
        
        # Show blank rows for debugging
        blank_rows = df[df['Reporting_Metric'].isna() | (df['Reporting_Metric'] == '')]
        if len(blank_rows) > 0:
            print(f"\n   ⚠️ {len(blank_rows):,} rows have blank Reporting_Metric")
            print(f"   📌 Sample of blank rows (first 3):")
            for idx, row in blank_rows.head(3).iterrows():
                print(f"      Reporting_Group: '{row.get('Reporting_Group', '')}'")
                print(f"      template_category: '{row.get('template_category', '')}'")
                print(f"      Reporting_Status: '{row.get('Reporting_Status', '')}'")
                print()
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()


def process_actions():
    """Process gld_actions.csv - combine Reporting_Status and QSET_category"""
    print("\n" + "=" * 80)
    print("📋 PROCESSING: gld_actions.csv")
    print("=" * 80)
    
    input_file = f"{GLD_PREFIX}/gld_actions.csv"
    
    if not client.exists(input_file):
        print(f"❌ File not found: {input_file}")
        return
    
    try:
        df = client.read_csv(input_file, dtype=str, low_memory=False)
        print(f"   ✅ Loaded {len(df):,} rows")
        
        # Check required columns
        if 'Reporting_Status' not in df.columns:
            print(f"   ❌ 'Reporting_Status' column not found!")
            return
        
        if 'QSET_category' not in df.columns:
            print(f"   ❌ 'QSET_category' column not found!")
            return
        
        def get_metric(row):
            status = str(row.get('Reporting_Status', ''))
            category = str(row.get('QSET_category', ''))
            
            # Combine with space in between
            if status and category:
                return f"{status} {category}"
            elif status:
                return status
            elif category:
                return category
            else:
                return None
        
        df['Reporting_Metric'] = df.apply(get_metric, axis=1)
        
        # Save back
        client.write_csv(df, input_file, index=False, encoding='utf-8')
        print(f"   ✅ Saved to: {input_file}")
        print(f"   📊 {len(df):,} rows, Reporting_Metric added")
        
        # Show summary
        metric_counts = df['Reporting_Metric'].value_counts().head(10)
        print(f"\n   📊 Reporting_Metric distribution (top 10):")
        for metric, count in metric_counts.items():
            print(f"      {metric}: {count} rows")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()


def process_issues():
    """Process gld_issues.csv - translate category_key and combine with Reporting_Status"""
    print("\n" + "=" * 80)
    print("📋 PROCESSING: gld_issues.csv")
    print("=" * 80)
    
    input_file = f"{GLD_PREFIX}/gld_issues.csv"
    
    if not client.exists(input_file):
        print(f"❌ File not found: {input_file}")
        return
    
    try:
        df = client.read_csv(input_file, dtype=str, low_memory=False)
        print(f"   ✅ Loaded {len(df):,} rows")
        
        # Check required columns
        if 'Reporting_Status' not in df.columns:
            print(f"   ❌ 'Reporting_Status' column not found!")
            return
        
        if 'category_key' not in df.columns:
            print(f"   ❌ 'category_key' column not found!")
            return
        
        def get_metric(row):
            status = str(row.get('Reporting_Status', ''))
            category_key = str(row.get('category_key', ''))
            
            # Translate category_key
            translated = ISSUE_CATEGORY_MAP.get(category_key, category_key)
            
            # Combine: Reporting_Status + translated category
            if status and translated:
                return f"{status} {translated}"
            elif status:
                return status
            elif translated:
                return translated
            else:
                return None
        
        df['Reporting_Metric'] = df.apply(get_metric, axis=1)
        
        # Save back
        client.write_csv(df, input_file, index=False, encoding='utf-8')
        print(f"   ✅ Saved to: {input_file}")
        print(f"   📊 {len(df):,} rows, Reporting_Metric added")
        
        # Show summary
        metric_counts = df['Reporting_Metric'].value_counts().head(10)
        print(f"\n   📊 Reporting_Metric distribution (top 10):")
        for metric, count in metric_counts.items():
            print(f"      {metric}: {count} rows")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()


def process_incidents():
    """Process rp2_incidents.csv - combine Reporting_Status and Category"""
    print("\n" + "=" * 80)
    print("📋 PROCESSING: rp2_incidents.csv")
    print("=" * 80)
    
    input_file = f"{REP_PREFIX}/rp2_incidents.csv"
    
    if not client.exists(input_file):
        print(f"❌ File not found: {input_file}")
        return
    
    try:
        df = client.read_csv(input_file, dtype=str, low_memory=False)
        print(f"   ✅ Loaded {len(df):,} rows")
        
        # Check required columns
        if 'Reporting_Status' not in df.columns:
            print(f"   ❌ 'Reporting_Status' column not found!")
            return
        
        if 'Category' not in df.columns:
            print(f"   ❌ 'Category' column not found!")
            return
        
        def get_metric(row):
            status = str(row.get('Reporting_Status', ''))
            category = str(row.get('Category', ''))
            
            # Combine with space in between: "Status Category"
            if status and category:
                return f"{status} {category}"
            elif status:
                return status
            elif category:
                return category
            else:
                return None
        
        df['Reporting_Metric'] = df.apply(get_metric, axis=1)
        
        # Save back
        client.write_csv(df, input_file, index=False, encoding='utf-8')
        print(f"   ✅ Saved to: {input_file}")
        print(f"   📊 {len(df):,} rows, Reporting_Metric added")
        
        # Show summary
        metric_counts = df['Reporting_Metric'].value_counts().head(10)
        print(f"\n   📊 Reporting_Metric distribution (top 10):")
        for metric, count in metric_counts.items():
            print(f"      {metric}: {count} rows")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()


# ============================================================================
# MAIN
# ============================================================================

def main():
    print("=" * 80)
    print("⚔️  REPORTING METRIC GENERATOR")
    print("=" * 80)
    print(f"📁 GLD Input: ADLS/{GLD_PREFIX}")
    print(f"📁 REP Input/Output: ADLS/{REP_PREFIX}")
    print("=" * 80)
    
    # All four now use the same multi-match, comma-separated rule engine -
    # no more single-value/multi-value split, that split was the bug.
    process_file("gld_inspections.csv", GLD_PREFIX, get_reporting_metric)
    process_file("rp2_site_reports.csv", REP_PREFIX, get_reporting_metric)
    process_file("rp2_QSET_reports.csv", REP_PREFIX, get_reporting_metric)
    process_file("rp2_contracts_managers_audits.csv", REP_PREFIX, get_reporting_metric)
    
    # Process files with different logic
    process_actions()
    process_issues()
    process_incidents()
    
    print("\n" + "=" * 80)
    print("🏁 REPORTING METRIC GENERATOR COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()