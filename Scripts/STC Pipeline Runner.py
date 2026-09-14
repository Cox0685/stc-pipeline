#!/usr/bin/env python
# coding: utf-8

"""
STC Master Pipeline Runner
Orchestrates the complete SafetyCulture ETL pipeline in strategic order.
Halts immediately if any enabled stage fails.
"""

import os
import sys
import subprocess
import time
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_shared"))
import azure_io

# ============================================================================
# PRE-PULL ARCHIVE CONFIGURATION
# ============================================================================

RUN_PRE_PULL_ARCHIVE = True  # Snapshot existing CSVs before the pipeline runs

# These are ADLS Gen2 folder names inside the single data lake filesystem
# (ADLS_FILESYSTEM env var - see infra/main.bicep), not local Windows paths.
# TNS/SLV/GLD/REP together form the bronze->silver->gold->reporting layout;
# each script's own path constants determine the rest of the folder path
# under here.
DATA_FOLDERS_TO_ARCHIVE = ["TNS", "SLV", "GLD", "REP"]


def archive_stage_data() -> bool:
    """
    Copies every CSV currently sitting directly under each data-lake folder
    above into "<folder>/archive/<run timestamp>/" before the pipeline
    touches them.

    - Snapshot only: nothing is deleted or moved, originals are untouched.
    - Never reads back into the archive folder itself, so re-runs can't
      archive an archive (azure_io.archive_folder only lists top-level
      files, same guarantee as the old local os.listdir() version).
    - One timestamped subfolder per pipeline run, so today's runs don't
      overwrite yesterday's.
    - A stage with no CSVs yet is not treated as a failure (e.g. first-ever
      run) - it's logged and skipped.
    """
    run_stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    print("\n" + "=" * 80)
    print(f"🗄️  PRE-PULL ARCHIVE: snapshotting current CSVs (stamp: {run_stamp})")
    print("=" * 80)

    all_ok = True
    client = azure_io.get_client()

    for stage_name in DATA_FOLDERS_TO_ARCHIVE:
        try:
            archived_count = azure_io.archive_folder(client, stage_name, run_stamp=run_stamp)

            if archived_count == 0:
                print(f"   ℹ️ {stage_name}: no CSVs to archive")
                continue

            print(f"   ✅ {stage_name}: archived {archived_count} file(s) → {stage_name}/archive/{run_stamp}/")

        except Exception as e:
            all_ok = False
            print(f"   ❌ {stage_name}: archive failed - {e}")

    print("=" * 80)
    return all_ok


# ============================================================================
# PIPELINE TOGGLES (True = Run Stage, False = Skip Stage)
# ============================================================================

RUN_STC_API_IN            = True   # Stage 1: API Ingestion
RUN_STC_JSON_MAP          = True   # Stage 2: JSON Mapping & Flattening
RUN_STC_DATA_CLEAN        = True   # Stage 3: Standardization & ID Cleaning
RUN_STC_TABLE_MERGE       = True   # Stage 4: Final Table Merging
RUN_STC_DATE_SCRAPE       = True   # Stage 5: Date Scraping
RUN_RP1_ESG_REPORT        = True   # Stage 6: ESG Report Generation
RUN_RP1_ISSUES_ANS        = True   # Stage 7: Issues Answers Processing
RUN_MAP_STATUS_LOGIC      = True   # Stage 8: Status Logic Mapping
RUN_MAP_TEMP_LABELS       = True   # Stage 9: Template Label Mapping
RUN_MAP_QSET_LABELS       = True   # Stage 10: QSET Label Mapping
RUN_MAP_USER_GROUPS       = True   # Stage 11: User Group Mapping
RUN_RP2_SITE_STATUS_PULL  = True   # Stage 12: Site Status Pull
RUN_RP2_TEMP_LABEL        = True   # Stage 13: RP2 Template Labeling
RUN_RP2_USER_LABEL        = True   # Stage 14: RP2 User Labeling
RUN_RP2_CM_REPORTS        = True   # Stage 15: CM Reports Processing
RUN_RP2_INCIDENTS         = True   # Stage 16: RP2 Incidents Processing
RUN_RP2_QSET_REPORTS      = True   # Stage 17: RP2 QSET Reports Processing
RUN_RP2_SITE_REPORTS      = True   # Stage 18: RP2 Site Reports Processing
RUN_RP3_REPORTING_LOGIC   = True   # Stage 19: RP3 Reporting Logic
RUN_RP3_METRIC_LIST       = True   # Stage 20: RP3 Metric List Processing
RUN_RP3_MCL39             = True   # Stage 21: RP3 MCL39 Processing
RUN_RP3_ESG_TO_MC39       = True   # Stage 22: RP3 ESG to MC39 Processing
RUN_RP4_GLD_TO_TLB        = True   # Stage 23: Final Output Execution

# ============================================================================
# DIRECTORY & SCRIPT PATH CONFIGURATION
# ============================================================================

# Self-locating: this always resolves to whatever folder STC Pipeline Runner.py
# itself is sitting in, so it survives being extracted/moved/renamed (e.g.
# Windows appending "(2)", "(3)" etc. to a re-extracted zip's folder name).
# The 23 stage scripts all live alongside this file, so this one line replaces
# a hardcoded path that broke every time the folder location changed.
SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

PIPELINE_STAGES = [
    {
        "name": "Stage 1: STC API Ingestion",
        "script": "STC API IN.py",
        "enabled": RUN_STC_API_IN
    },
    {
        "name": "Stage 2: STC JSON Map & Clean",
        "script": "STC JSON Map and Clean.py",
        "enabled": RUN_STC_JSON_MAP
    },
    {
        "name": "Stage 3: STC Data Clean",
        "script": "STC Data Clean.py",
        "enabled": RUN_STC_DATA_CLEAN
    },
    {
        "name": "Stage 4: STC Table Merge",
        "script": "STC Table Merge.py",
        "enabled": RUN_STC_TABLE_MERGE
    },
    {
        "name": "Stage 5: STC Date Scrape",
        "script": "STC Date Scrape.py",
        "enabled": RUN_STC_DATE_SCRAPE
    },
    {
        "name": "Stage 6: RP1 ESG Report",
        "script": "RP1 ESG Report.py",
        "enabled": RUN_RP1_ESG_REPORT
    },
    {
        "name": "Stage 7: RP1 Issues Answers",
        "script": "RP1 Issues Answers.py",
        "enabled": RUN_RP1_ISSUES_ANS
    },
    {
        "name": "Stage 8: MAP Status Logic",
        "script": "MAP Status Logic.py",
        "enabled": RUN_MAP_STATUS_LOGIC
    },
    {
        "name": "Stage 9: MAP Template Labels",
        "script": "MAP Template Labels.py",
        "enabled": RUN_MAP_TEMP_LABELS
    },
    {
        "name": "Stage 10: MAP Template QSET Labels",
        "script": "MAP Template QSET Labels.py",
        "enabled": RUN_MAP_QSET_LABELS
    },
    {
        "name": "Stage 11: MAP User Groups",
        "script": "MAP User Groups.py",
        "enabled": RUN_MAP_USER_GROUPS
    },
    {
        "name": "Stage 12: RP2 Site Status Pull",
        "script": "RP2 Site Status Pull.py",
        "enabled": RUN_RP2_SITE_STATUS_PULL
    },
    {
        "name": "Stage 13: RP2 Template Label",
        "script": "RP2 Template Label.py",
        "enabled": RUN_RP2_TEMP_LABEL
    },
    {
        "name": "Stage 14: RP2 User Label",
        "script": "RP2 User Label.py",
        "enabled": RUN_RP2_USER_LABEL
    },
    {
        "name": "Stage 15: RP2 CM Reports",
        "script": "RP2 CM Reports.py",
        "enabled": RUN_RP2_CM_REPORTS
    },
    {
        "name": "Stage 16: RP2 Incidents",
        "script": "RP2 Incidents.py",
        "enabled": RUN_RP2_INCIDENTS
    },
    {
        "name": "Stage 17: RP2 QSET Reports",
        "script": "RP2 QSET Reports.py",
        "enabled": RUN_RP2_QSET_REPORTS
    },
    {
        "name": "Stage 18: RP2 Site Reports",
        "script": "RP2 Site Reports.py",
        "enabled": RUN_RP2_SITE_REPORTS
    },
    {
        "name": "Stage 19: RP3 Reporting Logic",
        "script": "RP3 Reporting Logic.py",
        "enabled": RUN_RP3_REPORTING_LOGIC
    },
    {
        "name": "Stage 20: RP3 Metric List",
        "script": "RP3 Metric List.py",
        "enabled": RUN_RP3_METRIC_LIST
    },
    {
        "name": "Stage 21: RP3 MCL39",
        "script": "RP3 MCL39.py",
        "enabled": RUN_RP3_MCL39
    },
    {
        "name": "Stage 22: RP3 ESG to MC39",
        "script": "RP3 ESG to MC39.py",
        "enabled": RUN_RP3_ESG_TO_MC39
    },
    {
        "name": "Stage 23: Final Output Execution",
        "script": "RP4 GLD to TLB.py",
        "enabled": RUN_RP4_GLD_TO_TLB
    }
]

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def run_script(script_name: str, stage_name: str) -> bool:
    """
    Executes a target Python script and streams output in real time.
    Returns True on success (exit code 0), False otherwise.
    """
    script_path = os.path.join(SCRIPTS_DIR, script_name)

    if not os.path.exists(script_path):
        print(f"\n❌ ERROR: Script not found: {script_path}")
        return False

    print("\n" + "=" * 80)
    print(f"🚀 EXECUTING: {stage_name}")
    print(f"📄 File: {script_name}")
    print("=" * 80 + "\n")

    start_time = time.time()

    process = subprocess.Popen(
        [sys.executable, script_path],
        cwd=SCRIPTS_DIR,
        text=True
    )

    return_code = process.wait()
    elapsed = round(time.time() - start_time, 2)

    if return_code == 0:
        print(f"\n✅ SUCCESS: {stage_name} completed in {elapsed}s")
        return True
    else:
        print(f"\n💥 FAILURE: {stage_name} failed with Exit Code {return_code} after {elapsed}s")
        return False

# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================

def main():
    print("=" * 80)
    print("⚔️  STC MASTER PIPELINE RUNNER (FULL CAMPAIGN)")
    print("=" * 80)
    print(f"📂 Execution Directory: {SCRIPTS_DIR}")
    print("📋 Active Configuration:")
    for stage in PIPELINE_STAGES:
        status = "ENABLED " if stage["enabled"] else "DISABLED"
        print(f"   [{status}] {stage['name']} -> {stage['script']}")
    print("=" * 80)

    total_start = time.time()

    if RUN_PRE_PULL_ARCHIVE:
        archive_ok = archive_stage_data()
        if not archive_ok:
            print("\n" + "🛑" * 40)
            print("CRITICAL PIPELINE HALT: pre-pull archive failed for at least one stage.")
            print("Refusing to pull fresh data over CSVs that couldn't be snapshotted.")
            print("🛑" * 40)
            sys.exit(1)
    else:
        print("\n⏭️  SKIPPING: Pre-pull archive (disabled in configuration)")

    for stage in PIPELINE_STAGES:
        if not stage["enabled"]:
            print(f"\n⏭️  SKIPPING: {stage['name']} (Disabled in configuration)")
            continue

        success = run_script(stage["script"], stage["name"])

        if not success:
            print("\n" + "🛑" * 40)
            print(f"CRITICAL PIPELINE HALT: {stage['name']} encountered an error.")
            print("Subsequent stages aborted to safeguard data integrity.")
            print("🛑" * 40)
            sys.exit(1)

    total_elapsed = round(time.time() - total_start, 2)

    print("\n" + "=" * 80)
    print("🏁 ALL ENABLED PIPELINE STAGES COMPLETED SUCCESSFULLY")
    print(f"⏱️  Total Duration: {total_elapsed}s")
    print(f"📅 Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

if __name__ == "__main__":
    main()