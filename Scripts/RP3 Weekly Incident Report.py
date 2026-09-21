#!/usr/bin/env python
# coding: utf-8

"""
Generate Formatted rp3_weekly_incident_report from rp2_incidents.csv
Reads rp2_incidents.csv, calculates metrics, sorts newest first,
and outputs a styled Excel workbook named rp3_weekly_incident_report.xlsx with:
- Sheet name: rp3_weekly_incident_report
- Standard black border around all elements (headers & data cells)
- 1 shade off-black headers (#1A1A1A) with white text
- 90° rotated headers for specified columns, centered headers for all
- Left-justified & vertically centered Incident Details / Actions
- Precise custom hex color scheme for Incident Classification & Hipo Status
- Auto row-height with padding
"""

import os
import sys
import io
import math
import pandas as pd
from datetime import datetime

import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_shared"))
import azure_io

# ============================================================================
# CONFIGURATION & PATHS
# ============================================================================

REP_PREFIX = "REP"

INPUT_CSV = f"{REP_PREFIX}/rp2_incidents.csv"
REPORT_NAME = "rp3_weekly_incident_report"
OUTPUT_XLSX = f"{REP_PREFIX}/{REPORT_NAME}.xlsx"

adls_client = azure_io.get_client()

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

# Incident Status ID Mapping
INCIDENT_STATUS_MAP = {
    "547ed6465e344732bb54a199d304368a": "Open",
    "450484b156cd47849b49a3cf97d0c0ad": "Resolved"
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
        cell.border = black_border
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
            cell.border = black_border

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
    out_buf = io.BytesIO()
    wb.save(out_buf)
    return out_buf.getvalue()

# ============================================================================
# MAIN SCRIPT
# ============================================================================

def main():
    if not adls_client.exists(INPUT_CSV):
        print(f"❌ Input file not found: {INPUT_CSV}")
        return

    print(f"📂 Loading: {os.path.basename(INPUT_CSV)}...")
    df = adls_client.read_csv(INPUT_CSV, dtype=str, keep_default_na=False, low_memory=False)
    # Strip any whitespace from CSV column names
    df.columns = df.columns.str.strip()
    print(f"   ✅ Loaded {len(df):,} rows")

    # Flexible column lookup (case-insensitive & picks column with non-blank data)
    def get_first_valid(df_in, col_names):
        col_lookup = {str(c).strip().lower(): c for c in df_in.columns}
        for col in col_names:
            c_clean = str(col).strip().lower()
            if c_clean in col_lookup:
                series = df_in[col_lookup[c_clean]]
                if series.astype(str).str.strip().replace({'nan': '', 'None': '', 'null': '', 'N/A': '', 'n/a': ''}).ne('').any():
                    return series
        # Fallback to first existing matching column
        for col in col_names:
            c_clean = str(col).strip().lower()
            if c_clean in col_lookup:
                return df_in[col_lookup[c_clean]]
        return pd.Series('', index=df_in.index)

    def parse_dt_safe(series):
        clean = (
            series.astype(str)
            .str.strip()
            .replace({'': None, 'nan': None, 'None': None, 'null': None, 'NaT': None, 'N/A': None, 'n/a': None})
        )
        # Parse UTC/ISO timestamps and standard UK dates, converting to naive UTC
        parsed = pd.to_datetime(clean, dayfirst=True, errors='coerce', utc=True)
        return parsed.dt.tz_localize(None)

    print("\n⚙️ Calculating metrics and sorting by Created At (newest first)...")

    # Date parsing
    occurred_series = get_first_valid(df, ['task_occurred_at', 'Occurred At', 'occurred_at'])
    created_series = get_first_valid(df, ['task_created_at', 'Created At', 'created_at'])
    modified_series = get_first_valid(df, ['task_modified_at', 'task_modified', 'modified_at', 'Modified At', 'Modified', 'task_updated_at', 'updated_at'])

    occurred_dt = parse_dt_safe(occurred_series)
    created_dt = parse_dt_safe(created_series)
    modified_dt = parse_dt_safe(modified_series)
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

    # 6. Status (Mapped using INCIDENT_STATUS_MAP)
    raw_status = get_first_valid(df, ['task_status_id', 'Reporting_Status', 'reporting_status', 'Status', 'task_status']).fillna('')
    status = raw_status.apply(
        lambda x: INCIDENT_STATUS_MAP.get(str(x).strip(), str(x).strip())
    )

    # 7. Age Of Incident (Days)
    age_days = occurred_dt.apply(
        lambda dt: str(max(0, (now - dt).days)) if pd.notna(dt) else ''
    )

    # 8. Days Since Modified:
    # If task_modified_at is blank (incident was never modified), fallback to task_created_at, then occurred_dt
    effective_modified_dt = modified_dt.fillna(created_dt).fillna(occurred_dt)
    days_since_modified = effective_modified_dt.apply(
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

    # Save to Excel with sheet name rp3_weekly_incident_report
    print(f"💾 Saving Excel workbook to: {OUTPUT_XLSX}")
    excel_buf = io.BytesIO()
    with pd.ExcelWriter(excel_buf, engine='openpyxl') as writer:
        output_df.to_excel(writer, sheet_name=REPORT_NAME, index=False)

    # Apply all visual styles, black borders, and formatting - second pass,
    # reopening the just-written workbook from the in-memory buffer rather
    # than a real file path (apply_excel_formatting already returns the
    # reformatted bytes rather than saving to a path, see above).
    print("🎨 Applying black borders, custom colors, and padding...")
    excel_buf.seek(0)
    formatted_bytes = apply_excel_formatting(excel_buf)
    adls_client.write_bytes(formatted_bytes, OUTPUT_XLSX)

    print("\n✅ Successfully generated:")
    print(f"   📊 Report File: {OUTPUT_XLSX}")
    print(f"   📑 Sheet Name:  {REPORT_NAME}")
    print(f"   🆔 Total Rows:  {len(output_df):,}")

if __name__ == "__main__":
    main()