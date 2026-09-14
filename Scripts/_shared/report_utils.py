"""
Shared helpers for the RP2 report scripts (CM Reports, QSET Reports, Site Reports).

These three functions were byte-identical copies living independently inside
each of the three scripts - any fix had to be hand-applied three times, which
is exactly how naming and behaviour drift happens. They're centralised here
instead. Only functions verified to be truly identical across all copies were
moved; a few similarly-named functions turned out to have genuinely different
logic between files (see the pipeline audit notes) and were deliberately left
alone rather than silently merged.
"""

import os
import pandas as pd


def clean_site_name_from_string(name):
    """
    Clean site name by removing everything after the first '/'
    Example: "2336 Orkney Link Cable Route Civils / JB07 / 27 Jul 2026 / Robert Kenny"
    becomes: "2336 Orkney Link Cable Route Civils"
    """
    if pd.isna(name):
        return None

    name_str = str(name).strip()

    # Find the first '/' and take everything before it
    if '/' in name_str:
        cleaned = name_str.split('/')[0].strip()
        return cleaned

    return name_str


def load_site_lookup(gld_input_path):
    """
    Load the site lookup from gld_sites.csv
    Returns a dictionary mapping site_id to site_name
    """
    site_lookup_path = os.path.join(gld_input_path, "gld_sites.csv")

    if not os.path.exists(site_lookup_path):
        print(f"   ⚠️ gld_sites.csv not found at: {site_lookup_path}")
        return {}

    try:
        df_sites = pd.read_csv(site_lookup_path, dtype=str, low_memory=False)
        print(f"   ✅ Loaded gld_sites.csv ({len(df_sites):,} rows)")

        # Find id and name columns
        id_col = None
        name_col = None

        for col in df_sites.columns:
            if col.lower() in ['id', 'site_id', 'uuid']:
                id_col = col
            if col.lower() in ['name', 'site_name']:
                name_col = col

        if id_col is None or name_col is None:
            print(f"   ⚠️ Could not find id/name columns in gld_sites.csv")
            print(f"   📋 Available columns: {list(df_sites.columns)}")
            return {}

        # Create lookup dictionary
        site_lookup = {}
        for _, row in df_sites.iterrows():
            site_id = str(row[id_col]).strip() if pd.notna(row[id_col]) else None
            site_name = str(row[name_col]).strip() if pd.notna(row[name_col]) else None

            if site_id and site_name:
                # Also clean the site name from the lookup
                site_lookup[site_id] = clean_site_name_from_string(site_name)

        print(f"   ✅ Created site lookup with {len(site_lookup):,} entries")
        return site_lookup

    except Exception as e:
        print(f"   ❌ Error loading gld_sites.csv: {e}")
        return {}


def get_site_name(row, site_lookup):
    """
    Get the site name using:
    1. First try: site_id lookup in gld_sites.csv
    2. If blank: use site_name/name column and clean it
    """
    # Try site_id lookup first
    site_id = row.get('site_id', '')
    if site_id and pd.notna(site_id) and str(site_id).strip():
        site_id_str = str(site_id).strip()
        if site_id_str in site_lookup:
            return site_lookup[site_id_str]

    # Fallback: use site_name or name column
    for col in ['site_name', 'name', 'inspection_name']:
        if col in row.index:
            site_name = row.get(col, '')
            if site_name and pd.notna(site_name) and str(site_name).strip():
                return clean_site_name_from_string(site_name)

    return None
