#!/usr/bin/env python
# coding: utf-8

"""
Generate Formatted RP4_WeeklyIncidentReport from rp2_incidents.csv
Reads rp2_incidents.csv, calculates metrics, sorts newest first,
and outputs a styled Excel workbook named RP4_WeeklyIncidentReport.xlsx with:
- Sheet name: RP4_WeeklyIncidentReport
- Standard black border around all elements (headers & data cells)
- 1 shade off-black headers (#1A1A1A) with white text
- 90° rotated headers for specified columns, centered headers for all
- Left-justified & vertically centered Incident Details / Actions
- Precise custom hex color scheme for Incident Classification & Hipo Status
- Auto row-height with padding
"""

import os
import math
import pandas as pd
from datetime import datetime

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ============================================================================
# CONFIGURATION & PATHS
# ============================================================================

REP_PATH = r"C:\Users\Thomas.Cox\OneDrive - OCU Group\Desktop\00_AST_SystemsIntegration\00_AST_DataUploads\01_STC Safety Culture\Data\REP"

INPUT_CSV = os.path.join(REP_PATH, "rp2_incidents.csv")
REPORT_NAME = "RP4_WeeklyIncidentReport"
OUTPUT_XLSX = os.path.join(REP_PATH, f"{REPORT_NAME}.xlsx")

# Standardise classifications
CATEGORY_VALUE_MAPPING = {
    "Near Miss / Unplanned Event": "Near Miss",
    "Environmental Incident": "Environmental",
    "Accident (Personal Injury)": "Accident",
    "Security Incident": "Security",
    "Service Strike": "Services",
    "Service": "Services",
    "Accident": "Accident",
    "Near Miss": "Near Miss",
    "Property": "Property Damage",
    "Property Damage": "Property Damage"
}

# ============================================================================
# COLOR & FORMATTING RULES
# ============================================================================

# Fill & Font styling rules for Incident Classification
CLASSIFICATION_STYLES = {
    "Accident": {
        "fill": PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid"),
        "font": Font(name="Calibri", size=9, bold=True, color="FFFFFF")
    },
    "Near Miss": {
        "fill": PatternFill(start_color="FFCC00", end_color="FFCC00", fill_type="solid"),
        "font": Font(name="Calibri", size=9, bold=True, color="000000")
    },
    "Services": {
        "fill": PatternFill(start_color="0066FF", end_color="0066FF", fill_type="solid"),
        "font": Font(name="Calibri", size=9, bold=True, color="FFFFFF")
    },
    "Environmental": {
        "fill": PatternFill(start_color="33CCFF", end_color="33CCFF", fill_type="solid"),
        "font": Font(name="Calibri", size=9, bold=True, color="000000")
    },
    "Security": {
        "fill": PatternFill(start_color="FF66FF", end_color="FF66FF", fill_type="solid"),
        "font": Font(name="Calibri", size=9, bold=True, color="000000")
    },
    "Property Damage": {
        "fill": PatternFill(start_color="9933FF", end_color="9933FF", fill_type="solid"),
        "font": Font(name="Calibri", size=9, bold=True, color="FFFFFF")
    }
}

# Fill & Font styling rules for HIPO Status
HIPO_STYLES = {
    "Yes": {
        "fill": PatternFill(start_color="FF0000", end_color="FF0000", fill_type="solid"),
        "font": Font(name="Calibri", size=9, bold=True, color="FFFFFF")
    },
    "No": {
        "fill": PatternFill(start_color="00B050", end_color="00B050", fill_type="solid"),
        "font": Font(name="Calibri", size=9, bold=True, color="FFFFFF")
    }
}

# ============================================================================
# EXCEL FORMATTING FUNCTION
# ============================================================================

def apply_excel_formatting(file_path):
    wb = openpyxl.load_workbook(file_path)
    ws = wb[REPORT_NAME] if REPORT_NAME in wb.sheetnames else wb.active

    # Column specifications: (width, data_horizontal_align, is_header_rotated_90)
    col_specs = {
        "Week Number":                (5,  "center", True),
        "Created At":                 (15, "center", True),
        "Unique Id":                  (10, "center", True),
        "Incident Classification":    (15, "center", True),
        "Hipo Status":                (10, "center", True),
        "Status":                     (10, "center", True),
        "Age Of Incident (Days)":     (10, "center", True),
        "Days Since Modified":        (10, "center", True),
        "Time To Report (hrs)":       (10, "center", True),
        "Client":                     (30, "center", True),
        "Sitename":                   (30, "center", False),
        "Incident Details":           (65, "left",   False),
        "Incident Immediate Actions": (65, "left",   False)
    }

    # Header fonts and fills
    header_font = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1A1A1A", end_color="1A1A1A", fill_type="solid")
    regular_font = Font(name="Calibri", size=9)

    # Standard Black Border around all elements
    black_edge = Side(style='thin', color='000000')
    black_border = Border(
        left=black_edge,
        right=black_edge,
        top=black_edge,
        bottom=black_edge
    )

    # 1. Header row formatting
    ws.row_dimensions[1].height = 105
    col_name_to_idx = {}

    for col_idx in range(1, ws.max_column + 1):
        cell = ws.cell(row=1, column=col_idx)
        header_title = str(cell.value).strip() if cell.value is not None else ""
        col_name_to_idx[header_title] = col_idx

        width, _, is_rotated = col_specs.get(header_title, (15, "center", False))
        ws.column_dimensions[get_column_letter(col_idx)].width = width

        cell.font = header_font
        cell.fill = header_fill
        cell.border = black_border  # Standard black border on header
        cell.alignment = Alignment(
            horizontal="center",
            vertical="center",
            textRotation=90 if is_rotated else 0,
            wrap_text=True
        )

    # Track column indexes for styling
    details_col_idx = col_name_to_idx.get("Incident Details")
    actions_col_idx = col_name_to_idx.get("Incident Immediate Actions")
    class_col_idx = col_name_to_idx.get("Incident Classification")
    hipo_col_idx = col_name_to_idx.get("Hipo Status")

    # 2. Data rows formatting & dynamic height calculation
    for row_idx in range(2, ws.max_row + 1):
        max_line_count = 1

        for col_idx in range(1, ws.max_column + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            header_title = ws.cell(row=1, column=col_idx).value or ""
            _, data_align, _ = col_specs.get(header_title, (15, "center", False))

            cell.font = regular_font
            cell.border = black_border  # Standard black border on data cells

            # Vertically centred for all cells; left-justified for details/actions, center for rest
            cell.alignment = Alignment(
                horizontal=data_align,
                vertical="center",
                wrap_text=True
            )

            # Apply Incident Classification colors
            if col_idx == class_col_idx and cell.value:
                val_clean = str(cell.value).strip()
                if val_clean in CLASSIFICATION_STYLES:
                    cell.fill = CLASSIFICATION_STYLES[val_clean]["fill"]
                    cell.font = CLASSIFICATION_STYLES[val_clean]["font"]

            # Apply Hipo Status colors
            if col_idx == hipo_col_idx and cell.value:
                val_clean = str(cell.value).strip()
                if val_clean in HIPO_STYLES:
                    cell.fill = HIPO_STYLES[val_clean]["fill"]
                    cell.font = HIPO_STYLES[val_clean]["font"]

            # Calculate wrapped lines for long text columns
            if col_idx in (details_col_idx, actions_col_idx) and cell.value:
                raw_text = str(cell.value)
                line_count = 0
                for paragraph in raw_text.splitlines():
                    # Width 65 is roughly ~58 chars per line wrapped
                    line_count += max(1, math.ceil(len(paragraph) / 58))
                max_line_count = max(max_line_count, line_count)

        # 14pt per line + 10pt padding, minimum height of 22pt
        ws.row_dimensions[row_idx].height = max(22, (max_line_count * 14) + 10)

    ws.freeze_panes = "A2"
    wb.save(file_path)

# ============================================================================
# MAIN SCRIPT
# ============================================================================

def main():
    if not os.path.exists(INPUT_CSV):
        print(f"❌ Input file not found: {INPUT_CSV}")
        return

    print(f"📂 Loading: {os.path.basename(INPUT_CSV)}...")
    df = pd.read_csv(INPUT_CSV, dtype=str, keep_default_na=False, low_memory=False)
    print(f"   ✅ Loaded {len(df):,} rows")

    def get_first_valid(df_in, col_names):
        for col in col_names:
            if col in df_in.columns:
                return df_in[col]
        return pd.Series('', index=df_in.index)

    print("\n⚙️ Calculating metrics and sorting by Created At (newest first)...")

    # Date parsing (dayfirst=True handles UK format like '27/07/2026 08:33')
    occurred_series = get_first_valid(df, ['task_occurred_at', 'Occurred At'])
    created_series = get_first_valid(df, ['task_created_at', 'Created At'])
    modified_series = get_first_valid(df, ['task_modified_at', 'Modified At'])

    occurred_dt = pd.to_datetime(occurred_series, dayfirst=True, errors='coerce')
    created_dt = pd.to_datetime(created_series, dayfirst=True, errors='coerce')
    modified_dt = pd.to_datetime(modified_series, dayfirst=True, errors='coerce')
    now = datetime.now()

    # 1. Week Number (from task_occurred_at)
    week_number = occurred_dt.apply(lambda dt: str(dt.isocalendar().week) if pd.notna(dt) else '')

    # 2. Created At (formatted as DD/MM/YYYY HH:MM)
    created_at_fmt = occurred_dt.apply(lambda dt: dt.strftime('%d/%m/%Y %H:%M') if pd.notna(dt) else '')

    # 3. Unique Id
    unique_id = get_first_valid(df, ['task_unique_id', 'Unique Id']).fillna('')

    # 4. Incident Classification
    raw_cat = get_first_valid(df, ['Category', 'Incident Classification', 'category_key']).fillna('')
    incident_classification = raw_cat.apply(
        lambda x: CATEGORY_VALUE_MAPPING.get(str(x).strip(), str(x).strip())
    )

    # 5. Hipo Status (Yes / No, default No)
    hipo_raw = get_first_valid(df, ['HIPO?', 'Hipo Status', 'hipo']).fillna('')
    hipo_status = hipo_raw.apply(
        lambda x: "Yes" if str(x).strip().upper() in ["YES", "Y", "TRUE", "1"] else "No"
    )

    # 6. Status
    status = get_first_valid(df, ['Reporting_Status', 'reporting_status', 'task_status_id', 'Status']).fillna('')

    # 7. Age Of Incident (Days)
    age_days = occurred_dt.apply(
        lambda dt: str(max(0, (now - dt).days)) if pd.notna(dt) else ''
    )

    # 8. Days Since Modified
    days_since_modified = modified_dt.apply(
        lambda dt: str(max(0, (now - dt).days)) if pd.notna(dt) else ''
    )

    # 9. Time To Report (hrs)
    def calc_time_to_report(occ, crt):
        if pd.notna(occ) and pd.notna(crt):
            diff_hrs = (crt - occ).total_seconds() / 3600.0
            return f"{diff_hrs:.1f}"
        return ''

    time_to_report = [calc_time_to_report(o, c) for o, c in zip(occurred_dt, created_dt)]

    # 10. Client
    client = get_first_valid(df, ['Site Client', 'Client', 'Name of Site Client:']).fillna('')

    # 11. Sitename
    sitename = get_first_valid(df, ['task_site_name', 'Sitename', 'Site']).fillna('')

    # 12. Incident Details
    details = get_first_valid(df, ['Details', 'Incident Details']).fillna('')

    # 13. Incident Immediate Actions
    immediate_actions = get_first_valid(df, ['Immediate Actions', 'Incident Immediate Actions']).fillna('')

    # Assemble DataFrame
    output_df = pd.DataFrame({
        "_sort_dt": occurred_dt,
        "Week Number": week_number,
        "Created At": created_at_fmt,
        "Unique Id": unique_id,
        "Incident Classification": incident_classification,
        "Hipo Status": hipo_status,
        "Status": status,
        "Age Of Incident (Days)": age_days,
        "Days Since Modified": days_since_modified,
        "Time To Report (hrs)": time_to_report,
        "Client": client,
        "Sitename": sitename,
        "Incident Details": details,
        "Incident Immediate Actions": immediate_actions
    })

    # Sort by Created At newest first
    output_df = output_df.sort_values(by="_sort_dt", ascending=False).drop(columns=["_sort_dt"]).reset_index(drop=True)

    # Save to Excel with sheet name RP4_WeeklyIncidentReport
    print(f"💾 Saving Excel workbook to: {OUTPUT_XLSX}")
    with pd.ExcelWriter(OUTPUT_XLSX, engine='openpyxl') as writer:
        output_df.to_excel(writer, sheet_name=REPORT_NAME, index=False)

    # Apply all visual styles, black borders, and formatting
    print("🎨 Applying black borders, custom colors, and padding...")
    apply_excel_formatting(OUTPUT_XLSX)

    print("\n✅ Successfully generated:")
    print(f"   📊 Report File: {OUTPUT_XLSX}")
    print(f"   📑 Sheet Name:  {REPORT_NAME}")
    print(f"   🆔 Total Rows:  {len(output_df):,}")

if __name__ == "__main__":
    main()