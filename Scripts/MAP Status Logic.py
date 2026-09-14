#!/usr/bin/env python
# coding: utf-8

"""
Add Reporting Status to GLD Tables and RP2 Reports
Reads GLD tables and RP2 reports, adds Reporting_Status column based on table-specific rules
"""

import os
import pandas as pd
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================

GLD_INPUT_PATH = r"C:\Users\Thomas.Cox\OneDrive - OCU Group\Desktop\00_AST_SystemsIntegration\00_AST_DataUploads\01_STC Safety Culture\Data\GLD"
REP_INPUT_PATH = r"C:\Users\Thomas.Cox\OneDrive - OCU Group\Desktop\00_AST_SystemsIntegration\00_AST_DataUploads\01_STC Safety Culture\Data\REP"
GLD_OUTPUT_PATH = r"C:\Users\Thomas.Cox\OneDrive - OCU Group\Desktop\00_AST_SystemsIntegration\00_AST_DataUploads\01_STC Safety Culture\Data\GLD"
REP_OUTPUT_PATH = r"C:\Users\Thomas.Cox\OneDrive - OCU Group\Desktop\00_AST_SystemsIntegration\00_AST_DataUploads\01_STC Safety Culture\Data\REP"

# Create output folders if they don't exist
os.makedirs(GLD_OUTPUT_PATH, exist_ok=True)
os.makedirs(REP_OUTPUT_PATH, exist_ok=True)

# ============================================================================
# CONFIGURATION TOGGLES
# ============================================================================

# Test run: True = process only 10 rows, False = process all rows
TEST_RUN = False

print("=" * 80)
print("⚔️  ADD REPORTING STATUS - LOCAL VERSION")
print("=" * 80)
print(f"📁 GLD Input: {GLD_INPUT_PATH}")
print(f"📁 REP Input: {REP_INPUT_PATH}")
print(f"📁 GLD Output: {GLD_OUTPUT_PATH}")
print(f"📁 REP Output: {REP_OUTPUT_PATH}")
print(f"🧪 Test Run: {'ON' if TEST_RUN else 'OFF'}")
print("=" * 80)

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_action_status(row):
    """
    Determine Reporting_Status for Actions.
    
    Rules:
    - If task_status_label == "To Do" AND task_due_at is in the past: "Overdue"
    - If task_status_label == "To Do" AND task_due_at is in the future or null: "Open"
    - If task_status_label in ["Auditor Accepted", "Cannot be done", "Assignee Closed"]: "Resolved"
    - Otherwise: task_status_label (as-is)
    """
    status_label = row.get('task_status_label', '')
    due_at = row.get('task_due_at', '')
    
    # Check for resolved statuses
    if status_label in ["Auditor Accepted", "Cannot be done", "Assignee Closed"]:
        return "Resolved"
    
    # Check for To Do status
    if status_label == "To Do":
        # Check if due date is in the past
        if pd.notna(due_at) and due_at:
            try:
                due_date = pd.to_datetime(due_at)
                current_date = pd.Timestamp.now()
                if due_date < current_date:
                    return "Overdue"
                else:
                    return "Open"
            except:
                return "Open"
        else:
            return "Open"
    
    # Default: return the original status label
    return status_label if status_label else "Unknown"


def get_inspection_status(row):
    """
    Determine Reporting_Status for Inspections and Reports.
    
    Rules:
    - If date_completed has a value: "Complete"
    - Otherwise: "In Progress"
    """
    date_completed = row.get('date_completed', '')
    
    if pd.notna(date_completed) and date_completed:
        return "Complete"
    else:
        return "In Progress"


def get_investigation_status(row):
    """
    Determine Reporting_Status for Investigations.
    
    Rules:
    - Copy the value from status_title
    """
    return row.get('status_title', 'Unknown')


def get_status_from_id(status_id):
    """
    Helper function to get status from an ID, handling both with and without hyphens.
    """
    # Handle None, NaN, or empty values
    if pd.isna(status_id) or not status_id:
        return "Unknown"
    
    # Convert to string to handle floats/ints
    status_id_str = str(status_id)
    
    # Remove hyphens to standardize
    clean_id = status_id_str.replace('-', '')
    
    if clean_id == "547ed6465e344732bb54a199d304368a":
        return "Open"
    elif clean_id == "450484b156cd47849b49a3cf97d0c0ad":
        return "Resolved"
    else:
        return "Unknown"


def get_issue_status(row):
    """
    Determine Reporting_Status for Issues (gld_issues).
    
    Rules:
    - 547ed6465e344732bb54a199d304368a = Open
    - 450484b156cd47849b49a3cf97d0c0ad = Resolved
    - Otherwise: "Unknown"
    """
    status_id = row.get('task_status_id', '')
    return get_status_from_id(status_id)


def get_incident_status(row):
    """
    Determine Reporting_Status for Incidents (rp2_incidents).
    
    Rules:
    - 547ed6465e344732bb54a199d304368a = Open
    - 450484b156cd47849b49a3cf97d0c0ad = Resolved
    - Otherwise: "Unknown"
    """
    status_id = row.get('task_status_id', '')
    return get_status_from_id(status_id)


# ============================================================================
# MAIN PROCESSING
# ============================================================================

def main():
    total_processed = 0
    tables_processed = 0
    
    # ========================================================================
    # PROCESS: gld_actions.csv
    # ========================================================================
    
    actions_file = os.path.join(GLD_INPUT_PATH, "gld_actions.csv")
    if os.path.exists(actions_file):
        print(f"\n📂 Processing: {os.path.basename(actions_file)}")
        
        try:
            df = pd.read_csv(actions_file, dtype=str, low_memory=False)
            print(f"   ✅ Loaded {len(df):,} rows")
            
            if TEST_RUN:
                df = df.head(10)
                print(f"   🧪 TEST MODE: Processing {len(df)} rows")
            
            # Check required columns
            if 'task_status_label' not in df.columns:
                print(f"   ⚠️ 'task_status_label' column not found, skipping...")
            else:
                # Apply status logic
                df['Reporting_Status'] = df.apply(get_action_status, axis=1)
                
                # Show status distribution
                print(f"\n   📊 Reporting_Status distribution:")
                status_counts = df['Reporting_Status'].value_counts()
                for status, count in status_counts.items():
                    print(f"      {status}: {count} rows")
                
                # Save back
                df.to_csv(actions_file, index=False, encoding='utf-8')
                print(f"   ✅ Saved to: {actions_file}")
                total_processed += len(df)
                tables_processed += 1
                
        except Exception as e:
            print(f"   ❌ Error processing actions: {e}")
    else:
        print(f"\n⚠️ gld_actions.csv not found, skipping...")
    
    # ========================================================================
    # PROCESS: gld_inspections.csv
    # ========================================================================
    
    inspections_file = os.path.join(GLD_INPUT_PATH, "gld_inspections.csv")
    if os.path.exists(inspections_file):
        print(f"\n📂 Processing: {os.path.basename(inspections_file)}")
        
        try:
            df = pd.read_csv(inspections_file, dtype=str, low_memory=False)
            print(f"   ✅ Loaded {len(df):,} rows")
            
            if TEST_RUN:
                df = df.head(10)
                print(f"   🧪 TEST MODE: Processing {len(df)} rows")
            
            # Check required columns
            if 'date_completed' not in df.columns:
                print(f"   ⚠️ 'date_completed' column not found, skipping...")
            else:
                # Apply status logic
                df['Reporting_Status'] = df.apply(get_inspection_status, axis=1)
                
                # Show status distribution
                print(f"\n   📊 Reporting_Status distribution:")
                status_counts = df['Reporting_Status'].value_counts()
                for status, count in status_counts.items():
                    print(f"      {status}: {count} rows")
                
                # Save back
                df.to_csv(inspections_file, index=False, encoding='utf-8')
                print(f"   ✅ Saved to: {inspections_file}")
                total_processed += len(df)
                tables_processed += 1
                
        except Exception as e:
            print(f"   ❌ Error processing inspections: {e}")
    else:
        print(f"\n⚠️ gld_inspections.csv not found, skipping...")
    
    # ========================================================================
    # PROCESS: gld_investigations.csv
    # ========================================================================
    
    investigations_file = os.path.join(GLD_INPUT_PATH, "gld_investigations.csv")
    if os.path.exists(investigations_file):
        print(f"\n📂 Processing: {os.path.basename(investigations_file)}")
        
        try:
            df = pd.read_csv(investigations_file, dtype=str, low_memory=False)
            print(f"   ✅ Loaded {len(df):,} rows")
            
            if TEST_RUN:
                df = df.head(10)
                print(f"   🧪 TEST MODE: Processing {len(df)} rows")
            
            # Check required columns
            if 'status_title' not in df.columns:
                print(f"   ⚠️ 'status_title' column not found, skipping...")
            else:
                # Apply status logic
                df['Reporting_Status'] = df.apply(get_investigation_status, axis=1)
                
                # Show status distribution
                print(f"\n   📊 Reporting_Status distribution:")
                status_counts = df['Reporting_Status'].value_counts()
                for status, count in status_counts.items():
                    print(f"      {status}: {count} rows")
                
                # Save back
                df.to_csv(investigations_file, index=False, encoding='utf-8')
                print(f"   ✅ Saved to: {investigations_file}")
                total_processed += len(df)
                tables_processed += 1
                
        except Exception as e:
            print(f"   ❌ Error processing investigations: {e}")
    else:
        print(f"\n⚠️ gld_investigations.csv not found, skipping...")
    
    # ========================================================================
    # PROCESS: gld_issues.csv
    # ========================================================================
    
    issues_file = os.path.join(GLD_INPUT_PATH, "gld_issues.csv")
    if os.path.exists(issues_file):
        print(f"\n📂 Processing: {os.path.basename(issues_file)}")
        
        try:
            df = pd.read_csv(issues_file, dtype=str, low_memory=False)
            print(f"   ✅ Loaded {len(df):,} rows")
            
            if TEST_RUN:
                df = df.head(10)
                print(f"   🧪 TEST MODE: Processing {len(df)} rows")
            
            # Check required columns
            if 'task_status_id' not in df.columns:
                print(f"   ⚠️ 'task_status_id' column not found, skipping...")
            else:
                # Apply status logic
                df['Reporting_Status'] = df.apply(get_issue_status, axis=1)
                
                # Show status distribution
                print(f"\n   📊 Reporting_Status distribution:")
                status_counts = df['Reporting_Status'].value_counts()
                for status, count in status_counts.items():
                    print(f"      {status}: {count} rows")
                
                # Save back
                df.to_csv(issues_file, index=False, encoding='utf-8')
                print(f"   ✅ Saved to: {issues_file}")
                total_processed += len(df)
                tables_processed += 1
                
        except Exception as e:
            print(f"   ❌ Error processing issues: {e}")
    else:
        print(f"\n⚠️ gld_issues.csv not found, skipping...")
    
    # ========================================================================
    # PROCESS: gld_issues_answers.csv
    # ========================================================================
    
    issues_answers_file = os.path.join(GLD_INPUT_PATH, "gld_issues_answers.csv")
    if os.path.exists(issues_answers_file):
        print(f"\n📂 Processing: {os.path.basename(issues_answers_file)}")
        
        try:
            df = pd.read_csv(issues_answers_file, dtype=str, low_memory=False)
            print(f"   ✅ Loaded {len(df):,} rows")
            
            if TEST_RUN:
                df = df.head(10)
                print(f"   🧪 TEST MODE: Processing {len(df)} rows")
            
            # Check if task_status_id exists
            if 'task_status_id' in df.columns:
                print(f"   ✅ 'task_status_id' column found, applying status mapping...")
                df['Reporting_Status'] = df.apply(get_issue_status, axis=1)
                
                # Show status distribution
                print(f"\n   📊 Reporting_Status distribution:")
                status_counts = df['Reporting_Status'].value_counts()
                for status, count in status_counts.items():
                    print(f"      {status}: {count} rows")
                
                # Save back
                df.to_csv(issues_answers_file, index=False, encoding='utf-8')
                print(f"   ✅ Saved to: {issues_answers_file}")
                total_processed += len(df)
                tables_processed += 1
            else:
                print(f"   ⚠️ 'task_status_id' column not found. Attempting to join with gld_issues.csv...")
                
                # Try to join with gld_issues.csv on a common key
                issues_file_join = os.path.join(GLD_INPUT_PATH, "gld_issues.csv")
                if os.path.exists(issues_file_join):
                    df_issues = pd.read_csv(issues_file_join, dtype=str, low_memory=False)
                    
                    # Find a common key: try 'task_unique_id' or '_ParentID'
                    join_key = None
                    if 'task_unique_id' in df.columns and 'task_unique_id' in df_issues.columns:
                        join_key = 'task_unique_id'
                    elif '_ParentID' in df.columns and '_ParentID' in df_issues.columns:
                        join_key = '_ParentID'
                    
                    if join_key:
                        print(f"   🔗 Joining on '{join_key}'...")
                        # Keep only needed columns from issues
                        df_issues_subset = df_issues[['task_status_id', join_key]].drop_duplicates(subset=[join_key])
                        df_merged = df.merge(df_issues_subset, on=join_key, how='left')
                        
                        if 'task_status_id_y' in df_merged.columns:
                            # Use the joined status_id
                            df_merged['task_status_id'] = df_merged['task_status_id_y']
                            df_merged.drop(columns=['task_status_id_y'], inplace=True)
                        
                        # Now apply status mapping
                        if 'task_status_id' in df_merged.columns:
                            df_merged['Reporting_Status'] = df_merged.apply(get_issue_status, axis=1)
                            print(f"\n   📊 Reporting_Status distribution after join:")
                            status_counts = df_merged['Reporting_Status'].value_counts()
                            for status, count in status_counts.items():
                                print(f"      {status}: {count} rows")
                            
                            # Save back
                            df_merged.to_csv(issues_answers_file, index=False, encoding='utf-8')
                            print(f"   ✅ Saved to: {issues_answers_file}")
                            total_processed += len(df_merged)
                            tables_processed += 1
                        else:
                            print(f"   ❌ Failed to get task_status_id after join.")
                    else:
                        print(f"   ❌ No common key found to join with gld_issues.csv")
                else:
                    print(f"   ❌ gld_issues.csv not found, cannot join.")
                
        except Exception as e:
            print(f"   ❌ Error processing issues_answers: {e}")
    else:
        print(f"\n⚠️ gld_issues_answers.csv not found, skipping...")
    
    # ========================================================================
    # PROCESS: rp2_incidents.csv (in REP folder)
    # ========================================================================
    
    incidents_file = os.path.join(REP_INPUT_PATH, "rp2_incidents.csv")
    if os.path.exists(incidents_file):
        print(f"\n📂 Processing: {os.path.basename(incidents_file)}")
        
        try:
            df = pd.read_csv(incidents_file, dtype=str, low_memory=False)
            print(f"   ✅ Loaded {len(df):,} rows")
            
            if TEST_RUN:
                df = df.head(10)
                print(f"   🧪 TEST MODE: Processing {len(df)} rows")
            
            # Check required columns
            if 'task_status_id' not in df.columns:
                print(f"   ⚠️ 'task_status_id' column not found, skipping...")
            else:
                # Apply status logic for incidents (same as issues)
                df['Reporting_Status'] = df.apply(get_incident_status, axis=1)
                
                # Show status distribution
                print(f"\n   📊 Reporting_Status distribution:")
                status_counts = df['Reporting_Status'].value_counts()
                for status, count in status_counts.items():
                    print(f"      {status}: {count} rows")
                
                # Save back
                df.to_csv(incidents_file, index=False, encoding='utf-8')
                print(f"   ✅ Saved to: {incidents_file}")
                total_processed += len(df)
                tables_processed += 1
                
        except Exception as e:
            print(f"   ❌ Error processing incidents: {e}")
    else:
        print(f"\n⚠️ rp2_incidents.csv not found, skipping...")
    
    # ========================================================================
    # PROCESS: rp2_site_reports.csv (in REP folder) - uses inspection logic
    # ========================================================================
    
    site_reports_file = os.path.join(REP_INPUT_PATH, "rp2_site_reports.csv")
    if os.path.exists(site_reports_file):
        print(f"\n📂 Processing: {os.path.basename(site_reports_file)}")
        
        try:
            df = pd.read_csv(site_reports_file, dtype=str, low_memory=False)
            print(f"   ✅ Loaded {len(df):,} rows")
            
            if TEST_RUN:
                df = df.head(10)
                print(f"   🧪 TEST MODE: Processing {len(df)} rows")
            
            # Check required columns
            if 'date_completed' not in df.columns:
                print(f"   ⚠️ 'date_completed' column not found, skipping...")
            else:
                # Apply same logic as inspections
                df['Reporting_Status'] = df.apply(get_inspection_status, axis=1)
                
                # Show status distribution
                print(f"\n   📊 Reporting_Status distribution:")
                status_counts = df['Reporting_Status'].value_counts()
                for status, count in status_counts.items():
                    print(f"      {status}: {count} rows")
                
                # Save back
                df.to_csv(site_reports_file, index=False, encoding='utf-8')
                print(f"   ✅ Saved to: {site_reports_file}")
                total_processed += len(df)
                tables_processed += 1
                
        except Exception as e:
            print(f"   ❌ Error processing site_reports: {e}")
    else:
        print(f"\n⚠️ rp2_site_reports.csv not found, skipping...")
    
    # ========================================================================
    # PROCESS: rp2_QSET_reports.csv (in REP folder) - uses inspection logic
    # ========================================================================
    
    qset_reports_file = os.path.join(REP_INPUT_PATH, "rp2_QSET_reports.csv")
    if os.path.exists(qset_reports_file):
        print(f"\n📂 Processing: {os.path.basename(qset_reports_file)}")
        
        try:
            df = pd.read_csv(qset_reports_file, dtype=str, low_memory=False)
            print(f"   ✅ Loaded {len(df):,} rows")
            
            if TEST_RUN:
                df = df.head(10)
                print(f"   🧪 TEST MODE: Processing {len(df)} rows")
            
            # Check required columns
            if 'date_completed' not in df.columns:
                print(f"   ⚠️ 'date_completed' column not found, skipping...")
            else:
                # Apply same logic as inspections
                df['Reporting_Status'] = df.apply(get_inspection_status, axis=1)
                
                # Show status distribution
                print(f"\n   📊 Reporting_Status distribution:")
                status_counts = df['Reporting_Status'].value_counts()
                for status, count in status_counts.items():
                    print(f"      {status}: {count} rows")
                
                # Save back
                df.to_csv(qset_reports_file, index=False, encoding='utf-8')
                print(f"   ✅ Saved to: {qset_reports_file}")
                total_processed += len(df)
                tables_processed += 1
                
        except Exception as e:
            print(f"   ❌ Error processing qset_reports: {e}")
    else:
        print(f"\n⚠️ rp2_QSET_reports.csv not found, skipping...")
    
    # ========================================================================
    # PROCESS: rp2_contracts_managers_audits.csv (in REP folder) - uses inspection logic
    # ========================================================================
    
    contracts_file = os.path.join(REP_INPUT_PATH, "rp2_contracts_managers_audits.csv")
    if os.path.exists(contracts_file):
        print(f"\n📂 Processing: {os.path.basename(contracts_file)}")
        
        try:
            df = pd.read_csv(contracts_file, dtype=str, low_memory=False)
            print(f"   ✅ Loaded {len(df):,} rows")
            
            if TEST_RUN:
                df = df.head(10)
                print(f"   🧪 TEST MODE: Processing {len(df)} rows")
            
            # Check required columns
            if 'date_completed' not in df.columns:
                print(f"   ⚠️ 'date_completed' column not found, skipping...")
            else:
                # Apply same logic as inspections
                df['Reporting_Status'] = df.apply(get_inspection_status, axis=1)
                
                # Show status distribution
                print(f"\n   📊 Reporting_Status distribution:")
                status_counts = df['Reporting_Status'].value_counts()
                for status, count in status_counts.items():
                    print(f"      {status}: {count} rows")
                
                # Save back
                df.to_csv(contracts_file, index=False, encoding='utf-8')
                print(f"   ✅ Saved to: {contracts_file}")
                total_processed += len(df)
                tables_processed += 1
                
        except Exception as e:
            print(f"   ❌ Error processing contracts_managers_audits: {e}")
    else:
        print(f"\n⚠️ rp2_contracts_managers_audits.csv not found, skipping...")
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    
    print("\n" + "=" * 80)
    print("🏁 ADD REPORTING STATUS COMPLETE")
    print("=" * 80)
    print(f"📊 Tables Processed: {tables_processed}")
    print(f"📊 Total Rows Processed: {total_processed:,}")
    print(f"📅 Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

if __name__ == "__main__":
    main()