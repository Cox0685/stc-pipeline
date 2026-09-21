import pandas as pd
import os
import sys
import re

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_shared"))
import azure_io

client = azure_io.get_client()

# ==========================================
# 1. DEFINE FILE PATHS
# ==========================================
# ADLS tier prefixes replace what were local GLD/REP paths and the SHEQ
# Portal's local "assets/tables" folder. TABLES is the ADLS equivalent of
# that folder - the pipeline's actual delivery point for the front-end web
# app (see _shared/azure_io.py's module docstring for the full tier list).
raw_paths = {
    "actions": "GLD/gld_actions.csv",
    "issues": "GLD/gld_issues.csv",
    "inspections": "GLD/gld_inspections.csv",
    "incidents": "REP/rp2_incidents.csv",
    "esg": "REP/rp1_esg_report.csv",
    # User / Site / Group mapping sources
    "users": "GLD/gld_users.csv",
    "sites": "TABLES/gld_sites.csv",
    "site_members": "GLD/gld_site_members.csv",
    "groups": "GLD/gld_groups.csv"
}

sites_lookup_path = raw_paths["sites"]
output_dir = "TABLES"

output_paths = {
    "actions": f"{output_dir}/gld_actions.csv",
    "issues": f"{output_dir}/gld_issues.csv",
    "inspections": f"{output_dir}/gld_inspections.csv",
    "incidents": f"{output_dir}/rp2_incidents.csv",
    "esg": f"{output_dir}/rp1_esg_report.csv",
    "user_site_groups": f"{output_dir}/gld_user_site_groups.csv"
}

# ==========================================
# 2. DEFINE LEAN COLUMNS PER SOURCE
# ==========================================
cols_actions = [
    'task_completed_at', 'task_created_at', 'task_creator_firstname', 'task_creator_lastname', 
    'task_due_at', 'task_modified_at', 'task_occurred_at', 'task_site_area', 'task_site_name', 
    'task_title', 'task_unique_id', 'template_name', 'Reporting_Status', 'template_category', 
    'QSET_category', 'GroupName', 'Reporting_Group', 'Reporting_Metric'
]

cols_issues = [
    'category_key', 'location_geo_position_latitude', 'location_geo_position_longitude', 
    'task_completed_at', 'task_created_at', 'task_creator_firstname', 'task_creator_lastname', 
    'task_creator_user_id', 'task_description', 'task_due_at', 'task_modified_at', 'task_occurred_at', 
    'task_site_area', 'task_site_name', 'task_title', 'task_unique_id', 'Reporting_Status', 
    'GroupName', 'Reporting_Group', 'Reporting_Metric'
]

cols_inspections = [
    'author_name', 'client_site', 'conducted_on', 'created_at', 'date_completed', 
    'date_modified', 'date_started', 'id', 'latitude', 'longitude', 'modified_at', 
    'name', 'site_name', 'template_name', 'Reporting_Status', 'template_category', 
    'QSET_category', 'GroupName', 'Reporting_Group', 'Reporting_Metric'
]

cols_incidents = [
    'task_site_name', 'task_status_id', 'task_site_area', 'task_unique_id', 
    'task_created_at', 'task_modified_at', 'task_occurred_at', 'task_creator_firstname', 
    'task_creator_lastname', 'task_creator_user_id', 'category_key', 'Category', 
    'Details', 'Further Information', 'HIPO?', 'Immediate Actions', 'Lost Time', 
    'Please add any other Information of Note?', 'Reporter', 'Site Client', 'Treatment Required',
    'location_geo_position_latitude', 'location_geo_position_longitude'
]

# ==========================================
# 3. HELPER FUNCTIONS, LOOKUPS & MAPS
# ==========================================

print("\n[0/6] Loading Site Area Reference Map...")
sites_map = {}
if client.exists(sites_lookup_path):
    df_sites = client.read_csv(sites_lookup_path, usecols=['name', 'Site Area'], low_memory=False)
    df_sites = df_sites.dropna(subset=['name', 'Site Area'])
    sites_map = dict(zip(df_sites['name'].astype(str).str.strip(), df_sites['Site Area'].astype(str).str.strip()))
    print(f" -> Successfully mapped {len(sites_map):,} site areas from {sites_lookup_path}")
else:
    print(f" -> WARNING: {sites_lookup_path} not found. Skipping initial fallback enrichment.")

incident_cat_map = {
    'Accident (Personal Injury)': 'Accident',
    'Near Miss / Unplanned Event': 'Near Miss',
    'Environmental Incident': 'Environmental',
    'Security Incident': 'Security',
    'Service Strike': 'Services',
    'Accident': 'Accident',
    'Near Miss': 'Near Miss'
}

def clean_site_name(val):
    if pd.isna(val):
        return 'No Site'
    s = str(val).strip()
    if not s or s.lower() in ['nan', 'none', 'null', '']:
        return 'No Site'
    if re.match(r'^1999\b', s):
        return s
    if re.match(r'^2\d{3,4}\s', s):
        return s
    return 'No Site'

def fill_missing_site_area(row):
    current_area = row.get('site_area')
    if pd.isna(current_area) or str(current_area).strip().lower() in ['', 'nan', 'none', 'null']:
        site_name = str(row.get('site_name')).strip()
        return sites_map.get(site_name, current_area)
    return current_area

def format_creator(df, first_col, last_col):
    if first_col in df.columns and last_col in df.columns:
        df['creator'] = df[first_col].fillna('') + ' ' + df[last_col].fillna('')
        df['creator'] = df['creator'].str.strip()
        df.loc[df['creator'] == '', 'creator'] = None
    elif first_col in df.columns:
        df['creator'] = df[first_col]
    else:
        df['creator'] = None

def reorder_columns(df):
    front_cols = [
        'source_type', 'unique_id', 'site_name', 'site_area', 
        'latitude', 'longitude', 'title', 'status', 'category', 
        'HIPO?', 'Lost Time', 'template_name', 'creator', 
        'created_at', 'occurred_at', 'completed_at', 'due_at'
    ]
    existing_front = [c for c in front_cols if c in df.columns]
    remaining_cols = [c for c in df.columns if c not in existing_front]
    return df[existing_front + remaining_cols]

def update_global_lookups(df):
    """Dynamically updates sites_map with discovered site_name -> site_area pairs."""
    if 'site_name' in df.columns and 'site_area' in df.columns:
        valid_pairs = df[
            (df['site_name'] != 'No Site') & 
            df['site_area'].notna() & 
            (df['site_area'].astype(str).str.strip().str.lower().isin(['', 'nan', 'none', 'null']) == False)
        ][['site_name', 'site_area']].drop_duplicates()
        
        for _, row in valid_pairs.iterrows():
            sites_map.setdefault(str(row['site_name']).strip(), str(row['site_area']).strip())

geo_frames = []

# ==========================================
# 4. PROCESS & EXPORT EACH DATASET
# ==========================================

# --- A. ISSUES / SORS ---
print("\n[1/6] Processing Issues & SORs...")
df_issues = client.read_csv(raw_paths['issues'], usecols=lambda c: c in cols_issues, low_memory=False)
df_issues['source_type'] = 'issue'
format_creator(df_issues, 'task_creator_firstname', 'task_creator_lastname')

rename_issues = {
    'task_unique_id': 'unique_id', 'task_site_name': 'site_name', 'task_site_area': 'site_area', 
    'task_title': 'title', 'Reporting_Status': 'status', 'category_key': 'category', 
    'task_created_at': 'created_at', 'task_modified_at': 'modified_at', 'task_occurred_at': 'occurred_at', 
    'task_completed_at': 'completed_at', 'task_due_at': 'due_at', 'location_geo_position_latitude': 'latitude', 
    'location_geo_position_longitude': 'longitude', 'GroupName': 'group_name', 'Reporting_Group': 'reporting_group', 
    'Reporting_Metric': 'reporting_metric'
}
df_issues = df_issues.rename(columns=rename_issues)
df_issues.drop(columns=[c for c in ['task_creator_firstname', 'task_creator_lastname', 'task_creator_user_id'] if c in df_issues.columns], inplace=True)
df_issues['site_name'] = df_issues['site_name'].apply(clean_site_name)
df_issues['site_area'] = df_issues.apply(fill_missing_site_area, axis=1)

df_issues['latitude'] = pd.to_numeric(df_issues['latitude'], errors='coerce')
df_issues['longitude'] = pd.to_numeric(df_issues['longitude'], errors='coerce')

valid_geo_issues = df_issues[df_issues['site_name'] != 'No Site'].dropna(subset=['latitude', 'longitude'])[['site_name', 'latitude', 'longitude']]
geo_frames.append(valid_geo_issues)
update_global_lookups(df_issues)

geo_reference = valid_geo_issues.groupby('site_name')[['latitude', 'longitude']].mean()
lat_map = geo_reference['latitude'].to_dict()
lon_map = geo_reference['longitude'].to_dict()

df_issues = reorder_columns(df_issues)
client.write_csv(df_issues, output_paths['issues'], index=False)
print(f" -> Deployed Issues: {len(df_issues):,} rows to {output_paths['issues']}")

# --- B. ACTIONS ---
print("\n[2/6] Processing Actions...")
df_actions = client.read_csv(raw_paths['actions'], usecols=lambda c: c in cols_actions, low_memory=False)
df_actions['source_type'] = 'action'
format_creator(df_actions, 'task_creator_firstname', 'task_creator_lastname')

rename_actions = {
    'task_unique_id': 'unique_id', 'task_site_name': 'site_name', 'task_site_area': 'site_area', 
    'task_title': 'title', 'Reporting_Status': 'status', 'template_category': 'category', 
    'task_created_at': 'created_at', 'task_modified_at': 'modified_at', 'task_occurred_at': 'occurred_at', 
    'task_completed_at': 'completed_at', 'task_due_at': 'due_at', 'GroupName': 'group_name', 
    'Reporting_Group': 'reporting_group', 'Reporting_Metric': 'reporting_metric', 'QSET_category': 'qset_category'
}
df_actions = df_actions.rename(columns=rename_actions)
df_actions.drop(columns=[c for c in ['task_creator_firstname', 'task_creator_lastname'] if c in df_actions.columns], inplace=True)
df_actions['site_name'] = df_actions['site_name'].apply(clean_site_name)
df_actions['site_area'] = df_actions.apply(fill_missing_site_area, axis=1)

df_actions['latitude'] = df_actions['site_name'].map(lat_map)
df_actions['longitude'] = df_actions['site_name'].map(lon_map)
update_global_lookups(df_actions)

df_actions = reorder_columns(df_actions)
client.write_csv(df_actions, output_paths['actions'], index=False)
print(f" -> Deployed Actions: {len(df_actions):,} rows to {output_paths['actions']}")

# --- C. INSPECTIONS ---
print("\n[3/6] Processing Inspections...")
df_inspections = client.read_csv(raw_paths['inspections'], usecols=lambda c: c in cols_inspections, low_memory=False)
df_inspections['source_type'] = 'inspection'
if 'author_name' in df_inspections.columns:
    df_inspections['creator'] = df_inspections['author_name']

rename_inspections = {
    'id': 'unique_id', 'site_name': 'site_name', 'client_site': 'site_area', 'name': 'title', 
    'Reporting_Status': 'status', 'template_category': 'category', 'created_at': 'created_at', 
    'modified_at': 'modified_at', 'conducted_on': 'occurred_at', 'date_completed': 'completed_at', 
    'GroupName': 'group_name', 'Reporting_Group': 'reporting_group', 'Reporting_Metric': 'reporting_metric', 
    'QSET_category': 'qset_category', 'latitude': 'latitude', 'longitude': 'longitude'
}
df_inspections = df_inspections.rename(columns=rename_inspections)
df_inspections.drop(columns=[c for c in ['author_name'] if c in df_inspections.columns], inplace=True)
df_inspections['site_name'] = df_inspections['site_name'].apply(clean_site_name)
df_inspections['site_area'] = df_inspections.apply(fill_missing_site_area, axis=1)

df_inspections['latitude'] = pd.to_numeric(df_inspections['latitude'], errors='coerce').combine_first(df_inspections['site_name'].map(lat_map))
df_inspections['longitude'] = pd.to_numeric(df_inspections['longitude'], errors='coerce').combine_first(df_inspections['site_name'].map(lon_map))

valid_geo_inspections = df_inspections[df_inspections['site_name'] != 'No Site'].dropna(subset=['latitude', 'longitude'])[['site_name', 'latitude', 'longitude']]
geo_frames.append(valid_geo_inspections)
update_global_lookups(df_inspections)

df_inspections = reorder_columns(df_inspections)
client.write_csv(df_inspections, output_paths['inspections'], index=False)
print(f" -> Deployed Inspections: {len(df_inspections):,} rows to {output_paths['inspections']}")

# --- D. INCIDENTS ---
print("\n[4/6] Processing Incidents...")
df_incidents = client.read_csv(raw_paths['incidents'], usecols=lambda c: c in cols_incidents, low_memory=False)
df_incidents['source_type'] = 'incident'
format_creator(df_incidents, 'task_creator_firstname', 'task_creator_lastname')

rename_incidents = {
    'task_unique_id': 'unique_id', 
    'task_site_name': 'site_name', 
    'task_site_area': 'site_area', 
    'task_status_id': 'status', 
    'Category': 'category',
    'task_created_at': 'created_at', 
    'task_modified_at': 'modified_at', 
    'task_occurred_at': 'occurred_at',
    'location_geo_position_latitude': 'latitude',
    'location_geo_position_longitude': 'longitude'
}
df_incidents = df_incidents.rename(columns=rename_incidents)

if 'category' in df_incidents.columns:
    df_incidents['category'] = df_incidents['category'].replace(incident_cat_map)

df_incidents.drop(columns=[c for c in ['task_creator_firstname', 'task_creator_lastname', 'task_creator_user_id'] if c in df_incidents.columns], inplace=True)
df_incidents['site_name'] = df_incidents['site_name'].apply(clean_site_name)
df_incidents['site_area'] = df_incidents.apply(fill_missing_site_area, axis=1)

df_incidents['latitude'] = pd.to_numeric(df_incidents.get('latitude'), errors='coerce').combine_first(df_incidents['site_name'].map(lat_map))
df_incidents['longitude'] = pd.to_numeric(df_incidents.get('longitude'), errors='coerce').combine_first(df_incidents['site_name'].map(lon_map))

valid_geo_incidents = df_incidents[df_incidents['site_name'] != 'No Site'].dropna(subset=['latitude', 'longitude'])[['site_name', 'latitude', 'longitude']]
geo_frames.append(valid_geo_incidents)
update_global_lookups(df_incidents)

df_incidents = reorder_columns(df_incidents)
client.write_csv(df_incidents, output_paths['incidents'], index=False)
print(f" -> Deployed Incidents: {len(df_incidents):,} rows to {output_paths['incidents']}")

# Recompute master aggregate latitude & longitude maps across all datasets
all_geo_df = pd.concat(geo_frames, ignore_index=True)
master_geo = all_geo_df.groupby('site_name')[['latitude', 'longitude']].mean()
lat_map = master_geo['latitude'].to_dict()
lon_map = master_geo['longitude'].to_dict()
print(f" -> Master Reference compiled: {len(sites_map):,} site areas & {len(master_geo):,} site coordinates available.")

# --- E. ESG CARDS & HOURS ---
print("\n[5/6] Processing ESG Cards Hours...")
df_esg = client.read_csv(raw_paths['esg'], low_memory=False)

site_candidates = ['client_site', 'task_site_name', 'site_name', 'Site Client', 'site']
matched_site_col = next((c for c in site_candidates if c in df_esg.columns), None)

if matched_site_col:
    print(f" -> Mapping ESG site data using source column: '{matched_site_col}'")
    cleaned_sites = df_esg[matched_site_col].apply(clean_site_name)
    raw_sites = df_esg[matched_site_col].astype(str).str.strip()

    mapped_area = cleaned_sites.map(sites_map).combine_first(raw_sites.map(sites_map))
    if 'task_site_area' in df_esg.columns:
        df_esg['task_site_area'] = df_esg['task_site_area'].combine_first(mapped_area)
    elif 'site_area' in df_esg.columns:
        df_esg['site_area'] = df_esg['site_area'].combine_first(mapped_area)
    else:
        df_esg['task_site_area'] = mapped_area

    mapped_lat = cleaned_sites.map(lat_map).combine_first(raw_sites.map(lat_map))
    mapped_lon = cleaned_sites.map(lon_map).combine_first(raw_sites.map(lon_map))

    if 'latitude' in df_esg.columns:
        df_esg['latitude'] = pd.to_numeric(df_esg['latitude'], errors='coerce').combine_first(mapped_lat)
    else:
        df_esg['latitude'] = mapped_lat

    if 'longitude' in df_esg.columns:
        df_esg['longitude'] = pd.to_numeric(df_esg['longitude'], errors='coerce').combine_first(mapped_lon)
    else:
        df_esg['longitude'] = mapped_lon
else:
    print(" -> WARNING: No matching site column found in ESG Cards dataset. Exporting as-is.")

client.write_csv(df_esg, output_paths['esg'], index=False)
print(f" -> Deployed ESG Cards Hours: {len(df_esg):,} rows to {output_paths['esg']}")


# ==============================================================================
# 5. USER - SITE - GROUP MASTER JUNCTION (USING GLD_SITES.CSV AS SOURCE OF TRUTH)
# ==============================================================================
PAUSE_STEP_6 = True  # <-- Set to False when you are ready to re-enable Step 6

if PAUSE_STEP_6:
    print("\n[6/6] Generating Master User-Site-Group Table: PAUSED (Skipped).")
else:
    print("\n[6/6] Generating Master User-Site-Group Table from gld_sites.csv Truth...")

    # 1. Load users & create normalized user lookup table
    df_u = client.read_csv(raw_paths['users'], low_memory=False)

    def clean_user_full_name(row):
        fn = str(row.get('firstname', '')).strip() if pd.notna(row.get('firstname')) else ''
        ln = str(row.get('lastname', '')).strip() if pd.notna(row.get('lastname')) else ''
        if fn and ln:
            if fn.lower() == ln.lower():
                return fn
            return f"{fn} {ln}".strip()
        return fn or ln or 'Unknown'

    df_u['user_name'] = df_u.apply(clean_user_full_name, axis=1)
    df_u['user_name_lookup'] = df_u['user_name'].str.lower().str.strip()

    user_cols = ['id', 'user_name', 'user_name_lookup', 'firstname', 'lastname', 'email', 'active', 'seat_type']
    df_u = df_u[[c for c in user_cols if c in df_u.columns]].copy()
    df_u.rename(columns={'id': 'user_id', 'active': 'user_active', 'seat_type': 'user_seat_type'}, inplace=True)

    # 2. Load sites (Source of Truth) and explode the 'Members' column
    df_sites_truth = client.read_csv(raw_paths['sites'], low_memory=False)
    df_sites_truth = df_sites_truth.rename(columns={'id': 'site_id', 'name': 'site_name', 'Site Area': 'site_area'})

    # Extract and expand members
    site_member_rows = []
    for _, row in df_sites_truth.iterrows():
        s_id = str(row.get('site_id', '')).strip()
        s_name = str(row.get('site_name', '')).strip()
        s_area = str(row.get('site_area', '')).strip()
        raw_members = str(row.get('Members', ''))
        
        if pd.isna(raw_members) or raw_members.strip().lower() in ['0', '#n/a', 'nan', 'none', 'null', '']:
            continue
        
        for member in raw_members.split(','):
            m_name = member.strip()
            if m_name and m_name.lower() not in ['0', '#n/a', 'nan', 'none', 'null']:
                site_member_rows.append({
                    'site_id': s_id,
                    'site_name': s_name,
                    'site_area': s_area,
                    'user_name_lookup': m_name.lower()
                })

    df_site_members_expanded = pd.DataFrame(site_member_rows, columns=['site_id', 'site_name', 'site_area', 'user_name_lookup']).drop_duplicates()

    # 3. Match exploded site members against User directory
    df_site_user_matched = pd.merge(
        df_site_members_expanded,
        df_u,
        on='user_name_lookup',
        how='inner'
    )

    # 4. Fallback check: Also include any links from gld_site_members.csv by ID in case of name typos
    if client.exists(raw_paths['site_members']):
        df_sm_raw = client.read_csv(raw_paths['site_members'], low_memory=False)
        id_col = 'member_id' if 'member_id' in df_sm_raw.columns else ('user_id' if 'user_id' in df_sm_raw.columns else None)
        
        if id_col and 'site_id' in df_sm_raw.columns:
            df_sm_raw = df_sm_raw[[id_col, 'site_id']].dropna().drop_duplicates()
            df_sm_raw.rename(columns={id_col: 'user_id'}, inplace=True)
            
            df_sm_id_merged = pd.merge(df_sm_raw, df_sites_truth[['site_id', 'site_name', 'site_area']], on='site_id', how='inner')
            df_sm_id_merged = pd.merge(df_sm_id_merged, df_u, on='user_id', how='inner')
            
            df_site_user_matched = pd.concat([df_site_user_matched, df_sm_id_merged], ignore_index=True).drop_duplicates(subset=['site_id', 'user_id'])

    # 5. Load Groups
    df_g = client.read_csv(raw_paths['groups'], low_memory=False)
    df_g = df_g[['user_id', 'GroupName', 'Reporting_Group', 'status']].dropna(subset=['user_id']).drop_duplicates()
    df_g.rename(columns={
        'GroupName': 'group_name',
        'Reporting_Group': 'reporting_group',
        'status': 'group_member_status'
    }, inplace=True)

    # 6. Build Unified Table: Join Sites+Users with Groups
    df_master_usg = pd.merge(
        df_site_user_matched,
        df_g,
        on='user_id',
        how='left'
    )

    df_master_usg['group_name'] = df_master_usg['group_name'].fillna('No Group')
    df_master_usg['reporting_group'] = df_master_usg['reporting_group'].fillna('No Reporting Group')
    df_master_usg['group_member_status'] = df_master_usg['group_member_status'].fillna('unknown')

    # 7. Final Reordering and Output
    final_cols = [
        'site_id', 'site_name', 'site_area', 
        'user_id', 'user_name', 'firstname', 'lastname', 'email', 'user_active', 'user_seat_type',
        'group_name', 'reporting_group', 'group_member_status'
    ]

    df_master_usg = df_master_usg[[c for c in final_cols if c in df_master_usg.columns]].drop_duplicates()
    df_master_usg.sort_values(by=['site_name', 'user_name', 'group_name'], inplace=True)

    # Export to single CSV table
    client.write_csv(df_master_usg, output_paths['user_site_groups'], index=False)
    print(f" -> Deployed Master User-Site-Group Table: {len(df_master_usg):,} rows to {output_paths['user_site_groups']}")

print("\nAll pipeline tasks completed successfully!")