#!/usr/bin/env python
# coding: utf-8

"""
rp2 HeadsUp Report - Local Version
Reads from GLD folder (gld_headsup.csv, gld_headsup_users.csv), builds a
two-sheet Excel workbook, outputs to REP folder.

Sheet 1 "HeadsUp Summary": one row per HeadsUp, engagement stats.
Sheet 2 "User Totals": one row per user, aggregated across every HeadsUp
                        they appear in, with unique-HeadsUp count enriched
                        via a join back to Sheet 1's titles (_ParentID -> id,
                        same join pattern already used elsewhere in this
                        pipeline, e.g. groups_users -> groups_list).
"""

import re
import os
import sys
import io
import pandas as pd
import numpy as np
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_shared"))
import azure_io

# ============================================================================
# CONFIGURATION
# ============================================================================

GLD_PREFIX = "GLD"
REP_PREFIX = "REP"

client = azure_io.get_client()

OUTPUT_FILE = f"{REP_PREFIX}/rp2_heads_up.xlsx"

print("=" * 80)
print("⚔️  rp2 HEADSUP REPORT - LOCAL VERSION")
print("=" * 80)
print(f"📁 Input (GLD): ADLS/{GLD_PREFIX}")
print(f"📁 Output (REP): ADLS/{REP_PREFIX}")
print("=" * 80)


# ============================================================================
# HELPERS
# ============================================================================

def to_bool(val) -> bool:
    """Robust True/False parsing - CSVs can carry this as a real bool, or as
    the strings 'True'/'False'/'TRUE'/'FALSE'/'1'/'0', depending on what
    wrote them. Treat anything unrecognised as False rather than crashing."""
    if isinstance(val, bool):
        return val
    if pd.isna(val):
        return False
    s = str(val).strip().lower()
    return s in ("true", "1", "yes")


def to_numeric(series: pd.Series) -> pd.Series:
    """Convert a column to numeric, treating anything unparseable as 0 -
    these are count columns (viewed_count etc.), a blank/bad value means
    zero engagement, not a crash."""
    return pd.to_numeric(series, errors="coerce").fillna(0)


def safe_percent(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """numerator/denominator * 100, rounded to 1dp. Where denominator is 0
    (nobody assigned yet), the result is 0 rather than a divide-by-zero
    error or an Excel #DIV/0!."""
    num = numerator.astype(float).to_numpy()
    den = denominator.astype(float).to_numpy()
    with np.errstate(divide="ignore", invalid="ignore"):
        pct = np.where(den == 0, 0.0, num / den * 100)
    return pd.Series(pct, index=numerator.index).round(1)


_DATE_ONLY_PATTERN = re.compile(r'^\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\s*$')


def split_date_time_fallback(raw_series: pd.Series):
    """
    Fallback for when a table's split "_time" column is missing upstream
    (e.g. the pipeline-ordering bug where Table Merge ran before Date
    Scrape - see STC Pipeline Runner.py). The un-split source column may
    still hold a combined value like "16/06/2026 09:25" rather than being
    genuinely date-only - if so, recover the time from it directly instead
    of just leaving it blank.

    Only extracts a time when the raw string actually looks like it has
    one: a plain "16/06/2026" with nothing else genuinely carries no time
    information, and manufacturing "00:00:00" for that would be inventing
    data, not falling back gracefully.
    """
    dates_out = []
    times_out = []
    recovered = 0

    for raw in raw_series.fillna(""):
        raw_str = str(raw).strip()

        if not raw_str:
            dates_out.append("")
            times_out.append("")
            continue

        if _DATE_ONLY_PATTERN.match(raw_str):
            # Genuinely no time component in the source value - not an error
            dates_out.append(raw_str)
            times_out.append("")
            continue

        parsed = pd.to_datetime(raw_str, dayfirst=True, errors="coerce")
        if pd.isna(parsed):
            # Couldn't parse at all - keep the raw text rather than lose it
            dates_out.append(raw_str)
            times_out.append("")
        else:
            dates_out.append(parsed.strftime("%d/%m/%Y"))
            times_out.append(parsed.strftime("%H:%M:%S"))
            recovered += 1

    return (
        pd.Series(dates_out, index=raw_series.index),
        pd.Series(times_out, index=raw_series.index),
        recovered,
    )


def parse_datetime_series_safe(series: pd.Series) -> pd.Series:
    """
    Row-by-row datetime parsing, NOT pandas' vectorized pd.to_datetime(series).
    This matters wherever a column might contain a MIX of date-only and
    date+time strings (exactly what the combined-value fallback above can
    produce) - pandas' bulk parser tries to infer one consistent format for
    the whole column and can silently fail entries that would parse
    correctly on their own when formats are mixed. Slower, but correct.
    """
    def _parse_one(value):
        if pd.isna(value) or str(value).strip() == "":
            return pd.NaT
        return pd.to_datetime(str(value).strip(), dayfirst=True, errors="coerce")

    return series.apply(_parse_one)


# ============================================================================
# SHEET 1: HEADSUP SUMMARY
# ============================================================================

def build_headsup_summary(gld_path: str) -> pd.DataFrame:
    input_file = f"{gld_path}/gld_headsup.csv"

    if not client.exists(input_file):
        print(f"   ⚠️ Input file not found: {input_file}")
        return pd.DataFrame()

    df = client.read_csv(input_file, dtype=str, low_memory=False)
    print(f"   ✅ Loaded gld_headsup.csv: {len(df):,} rows")

    if df.empty:
        return pd.DataFrame()

    # Safety-net dedupe on id - protects this report even if SLV hasn't
    # been rebuilt since the headsup_list dedupe_config entry was added
    # upstream. Keeps the most-recently-ingested copy of each duplicate.
    before = len(df)
    if "_IngestedAt" in df.columns:
        df = df.sort_values("_IngestedAt", ascending=False)
    df = df.drop_duplicates(subset=["id"], keep="first")
    dupes_dropped = before - len(df)
    if dupes_dropped:
        print(f"   🗑️ Dropped {dupes_dropped} duplicate HeadsUp id(s) (safety-net dedupe)")

    out = pd.DataFrame()
    out["HeadsUp ID"] = df["id"]
    out["Title"] = df["title"]
    out["Author"] = df["author_name"]

    if "published_at_time" in df.columns:
        out["Published Date"] = df["published_at"]
        out["Published Time"] = df["published_at_time"]
    else:
        print("   ⚠️ 'published_at_time' column missing from gld_headsup.csv - "
              "did STC Date Scrape.py run before STC Table Merge.py? "
              "Falling back to parsing 'published_at' directly, in case it "
              "still holds a combined date+time value.")
        fallback_dates, fallback_times, recovered = split_date_time_fallback(df["published_at"])
        out["Published Date"] = fallback_dates
        out["Published Time"] = fallback_times
        print(f"      -> recovered a time component for {recovered}/{len(df)} rows")

    view_count = to_numeric(df["viewed_count"])
    ack_count = to_numeric(df["acknowledgement_count"])
    assigned_count = to_numeric(df["assigned_users_count"])

    out["View Count"] = view_count.astype(int)
    out["Acknowledged Count"] = ack_count.astype(int)
    out["Assigned Count"] = assigned_count.astype(int)
    out["Acknowledged %"] = safe_percent(ack_count, assigned_count)
    out["Viewed %"] = safe_percent(view_count, assigned_count)

    return out


# ============================================================================
# SHEET 2: USER TOTALS
# ============================================================================

def build_user_totals(gld_path: str, headsup_summary: pd.DataFrame) -> pd.DataFrame:
    input_file = f"{gld_path}/gld_headsup_users.csv"

    if not client.exists(input_file):
        print(f"   ⚠️ Input file not found: {input_file}")
        return pd.DataFrame()

    df = client.read_csv(input_file, dtype=str, low_memory=False)
    print(f"   ✅ Loaded gld_headsup_users.csv: {len(df):,} rows")

    if df.empty:
        return pd.DataFrame()

    # Same defensive pattern as Sheet 1: if the "_time" column is missing,
    # don't just give up on the time - the date column itself might still
    # hold a combined date+time value (pipeline ordering issue), so parse
    # it directly rather than losing precision unnecessarily.
    def combined_ts(date_col, time_col):
        if date_col not in df.columns:
            return pd.Series([pd.NaT] * len(df), index=df.index)

        if time_col in df.columns:
            date_series = df[date_col].fillna("")
            time_series = df[time_col].fillna("")
            return parse_datetime_series_safe(date_series + " " + time_series)

        print(f"   ⚠️ '{time_col}' column missing - parsing '{date_col}' directly "
              f"in case it still holds a combined date+time value.")
        return parse_datetime_series_safe(df[date_col])

    df["_ack_ts"] = combined_ts("completion_details_acknowledged_at", "completion_details_acknowledged_at_time")
    df["_view_ts"] = combined_ts("completion_details_viewed_at", "completion_details_viewed_at_time")

    df["_acknowledged_bool"] = df["completion_details_acknowledged"].apply(to_bool)
    df["_viewed_bool"] = df["completion_details_viewed"].apply(to_bool)

    # Bring in each row's HeadsUp published timestamp via the _ParentID -> id
    # join (same join validated against Sheet 1's titles below), so we can
    # work out days-to-acknowledge / days-to-view per row.
    published_lookup = {}
    if not headsup_summary.empty:
        pub_ts = parse_datetime_series_safe(
            headsup_summary["Published Date"].fillna("") + " " +
            headsup_summary["Published Time"].fillna("")
        )
        published_lookup = dict(zip(headsup_summary["HeadsUp ID"], pub_ts))

    df["_published_ts"] = df["_ParentID"].map(published_lookup)

    # Row-level elapsed time in days (fractional, not rounded yet - rounding
    # happens once, after averaging, to keep precision through the mean).
    df["_days_to_ack"] = (df["_ack_ts"] - df["_published_ts"]).dt.total_seconds() / 86400
    df["_days_to_view"] = (df["_view_ts"] - df["_published_ts"]).dt.total_seconds() / 86400
    # Only meaningful where the event actually happened
    df.loc[~df["_acknowledged_bool"], "_days_to_ack"] = pd.NA
    df.loc[~df["_viewed_bool"], "_days_to_view"] = pd.NA

    # Group per user. "id" here is the user's own id (from gld_headsup_users),
    # not to be confused with _ParentID (the HeadsUp's id) - grouping on the
    # user's id (not just name) avoids merging two different people who
    # happen to share a first+last name.
    grouped = df.groupby("id", dropna=False)

    rows = []
    for user_id, g in grouped:
        first_name = g["first_name"].iloc[0]
        last_name = g["last_name"].iloc[0]

        total_headsups = g["_ParentID"].nunique()  # used only internally, for %
        total_acknowledged = int(g["_acknowledged_bool"].sum())
        total_viewed = int(g["_viewed_bool"].sum())

        ack_pct = round(total_acknowledged / total_headsups * 100, 1) if total_headsups else 0.0
        view_pct = round(total_viewed / total_headsups * 100, 1) if total_headsups else 0.0

        latest_ack = g.loc[g["_acknowledged_bool"], "_ack_ts"].max()
        latest_view = g.loc[g["_viewed_bool"], "_view_ts"].max()

        avg_days_to_ack = g["_days_to_ack"].dropna()
        avg_days_to_ack = round(avg_days_to_ack.mean(), 1) if not avg_days_to_ack.empty else None

        avg_days_to_view = g["_days_to_view"].dropna()
        avg_days_to_view = round(avg_days_to_view.mean(), 1) if not avg_days_to_view.empty else None

        rows.append({
            "First Name": first_name,
            "Last Name": last_name,
            "Total Acknowledged": total_acknowledged,
            "Total Viewed": total_viewed,
            "Acknowledged %": ack_pct,
            "Viewed %": view_pct,
            "Avg Days to Acknowledge": avg_days_to_ack,
            "Avg Days to View": avg_days_to_view,
            "Latest Acknowledged Date": latest_ack.strftime("%d/%m/%Y") if pd.notna(latest_ack) else "",
            "Latest Viewed Date": latest_view.strftime("%d/%m/%Y") if pd.notna(latest_view) else "",
        })

    result = pd.DataFrame(rows)

    # Enrichment check: confirm the _ParentID -> id join actually resolves
    # against real HeadsUp titles/publish dates, so a broken join fails
    # loudly here (and the days-to-acknowledge columns come out blank)
    # rather than silently producing wrong numbers.
    if not headsup_summary.empty:
        parent_ids_in_users = set(df["_ParentID"].dropna().unique())
        known_ids = set(headsup_summary["HeadsUp ID"].dropna().unique())
        matched = parent_ids_in_users & known_ids
        print(f"   🔗 _ParentID -> HeadsUp id join: {len(matched)}/{len(parent_ids_in_users)} "
              f"unique HeadsUp IDs in the users file matched a real HeadsUp")
        if parent_ids_in_users and not matched:
            print(f"      ⚠️ ZERO matches - _ParentID values don't look like they match "
                  f"gld_headsup's id column. Days-to-acknowledge/view will be blank for "
                  f"everyone until this is fixed.")

    return result.sort_values(["Last Name", "First Name"]).reset_index(drop=True)


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    print("\n⚔️ [BUILDING REPORT]")
    print("=" * 80)

    print("\n📋 Sheet 1: HeadsUp Summary")
    headsup_summary = build_headsup_summary(GLD_PREFIX)

    print("\n📋 Sheet 2: User Totals")
    user_totals = build_user_totals(GLD_PREFIX, headsup_summary)

    if headsup_summary.empty and user_totals.empty:
        print("\n❌ Both sheets are empty - nothing to write. Check the input files exist.")
        return

    print(f"\n💾 Writing to {OUTPUT_FILE}...")
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        headsup_summary.to_excel(writer, sheet_name="HeadsUp Summary", index=False)
        user_totals.to_excel(writer, sheet_name="User Totals", index=False)
    client.write_bytes(buf.getvalue(), OUTPUT_FILE)

    print("\n" + "=" * 80)
    print("🏁 REPORT COMPLETE")
    print("=" * 80)
    print(f"📊 HeadsUp Summary: {len(headsup_summary):,} rows")
    print(f"📊 User Totals: {len(user_totals):,} rows")
    print(f"📅 Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)


if __name__ == "__main__":
    main()