"""
build_driver_asset_list.py

Combines:
  1. rp2_site_user_data.csv            -> Monthly Staff (First Name, Surname, Job Role, Primary Site)
  2. Tick List Week <N>.xlsx (latest)  -> Ops (names re-jigged, employee no., site from gld_sites.csv)
  3. Asset Responsible person.xlsx     -> Description, Serial Number, Registration Number, Group-Label
     matched on employee number first, then on name as a fallback.

Output: rp2_samsara_user_data.xlsx in the REP folder (sheet rp2_samsara_user_data)
        One row per person per asset (people with no asset get a single row with blank asset columns).

Run:  python "RP2 Samsara User Data.py"
      (ADLS paths - see _shared/azure_io.py for the tier list. Needs
      REP/rp2_site_user_data.csv from RP4 Site and User Data.py to have run
      first, and the Tick List / Asset files uploaded manually - see below.)
"""

import io
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_shared"))
import azure_io

client = azure_io.get_client()

# --------------------------------------------------------------------------------------
# Default paths
# --------------------------------------------------------------------------------------
REP_DIR = "REP"
# Manual uploads (Tick List Week N.xlsx, Asset Responsible person.xlsx) live
# in the same folder they did locally, mirrored into the REP tier.
DRIVER_DIR = f"{REP_DIR}/custom reports/driver data"

SITE_USERS_CSV = f"{REP_DIR}/rp2_site_user_data.csv"
ASSETS_XLSX = f"{DRIVER_DIR}/Asset Responsible person.xlsx"
GLD_SITES_CSV = "GLD/gld_sites.csv"
OUTPUT_NAME = "rp2_samsara_user_data"
OUTPUT_PATH = f"{REP_DIR}/{OUTPUT_NAME}.xlsx"

GROUP_OPS = "Ops"
GROUP_MONTHLY = "Monthly Staff"

ASSET_COLS = ["Description", "Serial Number", "Registration Number", "Group-Label"]
OUTPUT_COLS = (
    ["Employee Number", "First Name", "Surname", "Job Role", "Primary Site", "Group"]
    + ASSET_COLS
    + ["Asset Match"]
)

# Surname particles that should stick to the following word ("van Beek", "de la Cruz")
SURNAME_PARTICLES = {"van", "von", "de", "der", "den", "del", "della", "di", "da", "du",
                     "la", "le", "st", "st.", "ter", "ten", "bin", "al"}


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------
def clean(value) -> str:
    """Trim a cell to a string, turning NaN/None into ''."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def norm(text: str) -> str:
    """Normalise a name for comparison: lowercase, letters/spaces only."""
    text = clean(text).lower().replace("'", "").replace("-", " ")
    return re.sub(r"[^a-z ]", "", re.sub(r"\s+", " ", text)).strip()


def norm_emp(value) -> str:
    """Normalise an employee number: trimmed, upper case, keep leading zeros."""
    v = clean(value).upper()
    if re.fullmatch(r"\d+\.0", v):          # guard against Excel turning 007085 into 7085.0
        v = v[:-2]
    if re.fullmatch(r"\d{1,5}", v):
        v = v.zfill(6)
    return v


def split_surname_first(full_name: str):
    """
    'MacDonald, Roy'            -> ('Roy', 'MacDonald')
    'MacDonald Roy'             -> ('Roy', 'MacDonald')
    'Craddock James John'       -> ('James John', 'Craddock')
    'van Beek Robert'           -> ('Robert', 'van Beek')
    Returns (first_names, surname).
    """
    name = clean(full_name)
    if not name:
        return "", ""
    if "," in name:
        surname, first = name.split(",", 1)
        return clean(first), clean(surname)

    tokens = name.split(" ")
    surname_tokens = [tokens.pop(0)]
    # absorb particles: 'van' + 'Beek', 'de' + 'la' + 'Cruz'
    while surname_tokens[-1].lower() in SURNAME_PARTICLES and tokens:
        surname_tokens.append(tokens.pop(0))
    return " ".join(tokens), " ".join(surname_tokens)


def find_latest_tick_list(folder: str) -> str:
    """Pick the 'Tick List Week N' file with the highest week number (newest upload wins ties)."""
    candidates = []
    for suffix in (".xlsx", ".xls"):
        for path, uploaded in client.list_files_with_dates(folder, suffix=suffix):
            name = os.path.basename(path)
            if name.startswith("Tick List Week") and not name.startswith("~$"):
                candidates.append((path, uploaded))
    if not candidates:
        sys.exit(f"No 'Tick List Week' files found in: {folder}")

    def sort_key(item):
        path, uploaded = item
        m = re.search(r"Week\s*(\d+)", os.path.basename(path), re.IGNORECASE)
        return (int(m.group(1)) if m else -1, uploaded)

    return max(candidates, key=sort_key)[0]


# --------------------------------------------------------------------------------------
# Step 1 - site user data (Monthly Staff)
# --------------------------------------------------------------------------------------
def load_site_users(path: str) -> pd.DataFrame:
    df = client.read_csv(path, dtype=str, encoding="utf-8-sig")
    # The export repeats each user once per GroupName - keep one row per user
    if "User ID" in df.columns:
        df = df.drop_duplicates(subset="User ID")

    out = pd.DataFrame({
        "Employee Number": "",
        "First Name": df["First Name"].map(clean),
        "Surname": df["Surname"].map(clean),
        "Job Role": df["Job Role"].map(clean),
        "Primary Site": df["Primary Site"].map(clean),
    })
    out = out[(out["First Name"] != "") | (out["Surname"] != "")]
    return out.drop_duplicates().reset_index(drop=True)


# --------------------------------------------------------------------------------------
# GLD sites lookup
# --------------------------------------------------------------------------------------
def load_gld_sites(path: str) -> dict:
    """
    Returns {'0130': '0130 North Yard', ...}.
    Uses a site-number column if one exists, otherwise pulls the leading
    4 digits out of the Name column.
    """
    df = client.read_csv(path, dtype=str, encoding="utf-8-sig")
    cols = {c.lower().strip(): c for c in df.columns}
    name_col = cols.get("name")
    if name_col is None:
        sys.exit(f"{path} has no 'Name' column. Columns found: {list(df.columns)}")

    code_col = next(
        (cols[c] for c in ("site number", "contract site number", "site no", "site code",
                           "code", "number", "site_number", "site_code") if c in cols),
        None,
    )

    lookup = {}
    for _, row in df.iterrows():
        name = clean(row[name_col])
        if not name:
            continue
        code = clean(row[code_col]) if code_col else ""
        m = re.search(r"\d{4}", code) or re.match(r"\s*(\d{4})", name)
        if not m:
            continue
        code = m.group(1) if m.lastindex else m.group(0)
        site = name if name.startswith(code) else f"{code} {name}"
        lookup.setdefault(code, site)
    return lookup


# --------------------------------------------------------------------------------------
# Step 2 - tick list (Ops)
# --------------------------------------------------------------------------------------
def load_tick_list(path: str, gld_lookup: dict) -> pd.DataFrame:
    df = pd.read_excel(io.BytesIO(client.read_bytes(path)), dtype=str)
    df = df[df["Name"].map(clean).ne("") & df["Employee"].map(clean).ne("")]

    rows, missing_sites = [], set()
    for _, r in df.iterrows():
        first, surname = split_surname_first(r["Name"])
        location = clean(r.get("Location"))
        m = re.search(r"\d{4}", location)            # 0130, 2398.S1, 0130/2357.BS -> first 4 digits
        code = m.group(0) if m else ""
        site = gld_lookup.get(code, "")
        if code and not site:
            missing_sites.add(code)
            site = code                              # keep the number so nothing is silently lost
        rows.append({
            "Employee Number": norm_emp(r["Employee"]),
            "First Name": first,
            "Surname": surname,
            "Job Role": clean(r.get("Trade")),       # tick list only carries a trade code
            "Primary Site": site,
        })

    if missing_sites:
        print(f"  ! Site numbers not found in gld_sites.csv: {', '.join(sorted(missing_sites))}")
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------
# Step 3 - assets
# --------------------------------------------------------------------------------------
def load_assets(path: str) -> pd.DataFrame:
    df = pd.read_excel(io.BytesIO(client.read_bytes(path)), dtype=str)
    rp = df["Responsible Person"].map(clean)
    df = df[rp != ""].copy()
    rp = df["Responsible Person"].map(clean)
    df["_emp"] = rp.str.extract(r"\[([^\]]+)\]\s*$")[0].map(norm_emp)
    df["_name"] = rp.str.replace(r"\s*\[[^\]]*\]\s*$", "", regex=True).map(norm)
    for c in ASSET_COLS:
        df[c] = df[c].map(clean)
    return df


def name_matches(asset_name: str, first: str, surname: str) -> bool:
    """Asset names are 'Surname Forename(s)'. Match on surname + first forename."""
    sur, fst = norm(surname), norm(first)
    if not sur or not fst or not asset_name:
        return False
    if asset_name in (f"{sur} {fst}", f"{fst} {sur}"):
        return True
    first_token = fst.split(" ")[0]
    if asset_name.startswith(sur + " "):
        rest = asset_name[len(sur) + 1:].split(" ")
        return first_token in rest
    return False


def attach_assets(people: pd.DataFrame, assets: pd.DataFrame) -> pd.DataFrame:
    by_emp = {k: g for k, g in assets[assets["_emp"] != ""].groupby("_emp")}
    # Assets already tied to a known employee number can't be "won" by a name match
    known_emps = set(people["Employee Number"]) - {""}
    name_pool = assets[~assets["_emp"].isin(known_emps)]
    out_rows = []
    counts = {"Employee No": 0, "Name": 0, "None": 0}

    for _, p in people.iterrows():
        matched, method = None, "None"
        emp = p["Employee Number"]

        if emp and emp in by_emp:
            matched, method = by_emp[emp], "Employee No"
        else:
            mask = name_pool["_name"].map(lambda n: name_matches(n, p["First Name"], p["Surname"]))
            if mask.any():
                matched, method = name_pool[mask], "Name"

        counts[method] += 1
        if matched is None:
            out_rows.append({**p.to_dict(), **{c: "" for c in ASSET_COLS}, "Asset Match": method})
        else:
            for _, a in matched.iterrows():
                out_rows.append({**p.to_dict(), **{c: a[c] for c in ASSET_COLS}, "Asset Match": method})

    print(f"  People matched by employee no: {counts['Employee No']}, "
          f"by name: {counts['Name']}, no asset: {counts['None']}")
    return pd.DataFrame(out_rows, columns=OUTPUT_COLS)


# --------------------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------------------
def write_output(df: pd.DataFrame, path: str):
    """Builds the formatted workbook in memory and uploads it to `path`."""
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as xw:
        df.to_excel(xw, index=False, sheet_name=OUTPUT_NAME)
        ws = xw.sheets[OUTPUT_NAME]
        body, head = Font(name="Arial", size=10), Font(name="Arial", size=10, bold=True, color="FFFFFF")
        fill = PatternFill("solid", fgColor="1F3864")
        for row in ws.iter_rows():
            for cell in row:
                cell.font = body
        for cell in ws[1]:
            cell.font, cell.fill = head, fill
        for i, col in enumerate(df.columns, start=1):
            width = max([len(str(col))] + [len(str(v)) for v in df[col].head(2000)])
            ws.column_dimensions[get_column_letter(i)].width = min(width + 2, 60)
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
    client.write_bytes(buffer.getvalue(), path)


# --------------------------------------------------------------------------------------
def main():
    tick_path = find_latest_tick_list(DRIVER_DIR)

    print("Step 1 - site user data")
    staff = load_site_users(SITE_USERS_CSV)
    staff["Group"] = GROUP_MONTHLY
    print(f"  {len(staff)} people")

    print(f"Step 2 - tick list: {os.path.basename(tick_path)}")
    gld = load_gld_sites(GLD_SITES_CSV)
    ops = load_tick_list(tick_path, gld)
    ops["Group"] = GROUP_OPS
    print(f"  {len(ops)} people")

    # Anyone on the tick list is Ops, even if they also appear in the site user data
    ops_keys = set(zip(ops["First Name"].map(norm), ops["Surname"].map(norm)))
    staff = staff[[k not in ops_keys for k in zip(staff["First Name"].map(norm), staff["Surname"].map(norm))]]

    people = pd.concat([ops, staff], ignore_index=True)

    print("Step 3 - assets")
    assets = load_assets(ASSETS_XLSX)
    result = attach_assets(people, assets)
    result = result.sort_values(["Group", "Surname", "First Name"], kind="stable").reset_index(drop=True)

    out = OUTPUT_PATH
    write_output(result, out)

    print(f"Done - {len(result)} rows written to:\n  {out}")


if __name__ == "__main__":
    main()