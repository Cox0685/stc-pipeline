import os
import sys
import pandas as pd
from dateutil.parser import parse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_shared"))
import azure_io

# Data lake folder to process in-place (was a local OneDrive path)
TARGET_DIR = "SLV"

_adls = azure_io.get_client()

# Prefix / Suffix patterns to exclude from transformation
EXCLUDE_PATTERNS = ('detail_', 'result_', '_ingested', 'question_')

def should_exclude_col(col_name):
    """
    Check if a column starts or ends with any of the excluded patterns.
    """
    col_str = str(col_name).strip().lower()
    for pattern in EXCLUDE_PATTERNS:
        p = pattern.lower()
        if col_str.startswith(p) or col_str.endswith(p):
            return True
    return False

def parse_datetime_value(val):
    """
    Attempts to parse a single string/value into (date_str, time_str).
    Returns (None, None) if parsing fails or input is null.
    """
    if pd.isna(val) or isinstance(val, (int, float)):
        return None, None
        
    val_str = str(val).strip()
    if not val_str:
        return None, None

    try:
        dt = parse(val_str, fuzzy=False)
        return dt.strftime('%Y-%m-%d'), dt.strftime('%H:%M:%S')
    except (ValueError, TypeError, OverflowError):
        return None, None

def is_datetime_column(series):
    """
    Evaluates whether a column contains date/time string data based on a sample.
    """
    if pd.api.types.is_datetime64_any_dtype(series):
        return True

    sample = series.dropna().head(50)
    if sample.empty:
        return False

    parsed_count = 0
    for item in sample:
        d, t = parse_datetime_value(item)
        if d is not None:
            parsed_count += 1

    return (parsed_count / len(sample)) >= 0.6

def process_file(file_path):
    print(f"\n==========================================")
    print(f"  ENGAGING: {file_path}")
    print(f"==========================================")
    
    # Only CSV is handled - the local version also supported .xlsx/.parquet,
    # but this pipeline only ever produces CSVs, and azure_io doesn't (yet)
    # support the other formats. list_files() in main() already only looks
    # for .csv, so this branch is just a safety net.
    if not file_path.endswith('.csv'):
        return
    
    try:
        df = _adls.read_csv(file_path, low_memory=False)
    except Exception as e:
        print(f"  [!] Failed to read file: {e}")
        return

    modified = False

    # Iterate over a copy of columns list to safely manipulate the DataFrame structure
    for col in list(df.columns):
        if should_exclude_col(col):
            print(f"   --> Skipping excluded column: {col}")
            continue

        if is_datetime_column(df[col]):
            print(f"   --> Splitting Datetime Column: {col}")
            
            # Convert series values to parsed datetimes safely
            parsed_series = df[col].apply(lambda x: parse_datetime_value(x) if pd.notna(x) else (None, None))
            
            dates = [p[0] for p in parsed_series]
            times = [p[1] for p in parsed_series]

            # Replace original column content with Date
            df[col] = dates

            # Insert <col>_time column directly next to the original column
            time_col_name = f"{col}_time"
            col_idx = df.columns.get_loc(col)
            
            # Drop existing <col>_time if it already exists to avoid duplication
            if time_col_name in df.columns:
                df.drop(columns=[time_col_name], inplace=True)

            df.insert(col_idx + 1, time_col_name, times)
            modified = True

    if modified:
        try:
            _adls.write_csv(df, file_path, index=False)
            print(f"  [✓] Successfully transformed and saved: {file_path}")
        except Exception as e:
            print(f"  [!] Failed to save modified file: {e}")
    else:
        print("  No columns required splitting in this table.")

def main():
    files = _adls.list_files(TARGET_DIR, suffix=".csv")

    if not files:
        print("No table files (.csv) found in the SLV folder.")
        return

    print(f"Found {len(files)} table(s) to process...")
    for f in files:
        process_file(f)

if __name__ == "__main__":
    main()