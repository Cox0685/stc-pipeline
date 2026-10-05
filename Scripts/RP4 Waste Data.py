"""
rp2 Scope 3 pipeline - rebuilt to line up with the manual Working Data / pivot.

Reads the COINS 'Data' sheet, drops ancillary lines, maps every line to a reporting
category, converts to tonnes (or m3 / litres), applies carbon factors and writes:

    Data             - untouched source
    Working Data     - kept rows, Description = category, Quantity = converted
                       (+ Raw_Description, Original_Quantity, Rule, Review_Flag)
    Dropped Rows     - every excluded row and the reason it was excluded
    Detailed Carbon  - the pivot (Row Labels / Sum of Quantity / kgCO2e)
    Rollup Summary   - the high-level table
    Review Flags     - rows a human should glance at

Run:  python "RP4 Waste Data.py"  -> newest "*Scope 3*.xlsx" in TNS/static source files
      (ADLS paths - see _shared/azure_io.py for the tier list; output goes to REP)
"""
import io
import os
import re
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_shared"))
import azure_io

client = azure_io.get_client()

# =========================================================
# 1. CONFIGURATION
# =========================================================
# Source: the monthly COINS Scope 3 export a human drops into this TNS folder
# (manual upload, same as the monthly staff timesheet - nothing earlier in the
# workflow creates it). Newest upload matching "Scope 3" wins.
SOURCE_DIR = "TNS/static source files"
OUTPUT_DIR = "REP"
OUTPUT_FILENAME = "rp2_waste_data.xlsx"

# --- Waste ---
LOAD_TONNES = 20.0            # tonnes per muck-away load. Written guide says 19, manual uses 20.
SKIP_DEFAULT_TONNES = 2.0     # EA/NO skip lift with no tonnage line on the PO
LOAD_PRICE_CD_ABOVE = 250.0   # £/load above this -> Construction & Demolition
LOAD_PRICE_SOIL_BELOW = 200.0 # £/load below this -> Soil and Stones (£200-£250 flagged)

# --- Bagged cement ---
# "manual": flat 0.02 t per bag, which is what the manual does.
# "stated": use the weight in the description (25KG -> 0.025 t), 20 kg if none stated.
BAG_WEIGHT_MODE = "manual"
DEFAULT_BAG_KG = 20.0

# --- CBS (cement bound sand) mix design, per m3: (sand t, cement t) ---
CBS_MIX = {10: (1.89, 0.17), 14: (1.95, 0.135)}
CBS_DEFAULT_RATIO = 14

# --- Rebar ---
MESH_KG_PER_M2 = {"A142": 2.22, "A193": 3.02, "A252": 3.95, "A393": 6.16, "B1131": 10.90}
MESH_DEFAULT_SHEET_M2 = 2.4 * 4.8
DOWEL_FALLBACK_KG = 1.5

# =========================================================
# 2. CATEGORY NAMES
# =========================================================
AGG = "AGGREGATE"
CEM_LCC = "CEMENT CEM II/B-V FLY ASH SCILICEOUS"
CEM_OPC = "CEMENT OPC"
REBAR = "REBAR"
DIESEL = "DIESEL"
HVO = "HVO"
W_CD = "WASTE CONSTRUCTION AND DEMOLITION WASTE"
W_SOIL = "WASTE SOIL AND STONES"
W_WOOD = "WASTE WOOD"
W_PLASTIC = "WASTE PLASTIC"

CONCRETE_OPC = {
    "GEN0": "CONCRETE OPC GEN 0 (6/8 MPA)",
    "GEN1": "CONCRETE OPC GEN 1 (8/10 MPA)",
    "GEN3": "CONCRETE OPC GEN 3 (16/20 MPA)",
    "RC20/25": "CONCRETE OPC RC 20/25 (20/25 MPA) CEMI",
    "RC28/35": "CONCRETE OPC RC 28/35 (28/35 MPA) CEMI",
    "RC32/40": "CONCRETE OPC RC 32/40 (32/40 MPA) CEMI",
    "RC40/50": "CONCRETE OPC RC 40/50 (40/50 MPA) CEMI",
}
CONCRETE_SLAG = {
    "GEN1": "CONCRETE LCC GEN 1 (8/10 MPA) 50% BLAST FURNACE SLAG",
    "GEN3": "CONCRETE LCC GEN 3 (16/20 MPA) 50% BLAST FURNACE SLAG",
    "RC32/40": "CONCRETE LCC RC 32/40 (32/40 MPA) 50% BLAST FURNACE SLAG",
    "RC40/50": "CONCRETE LCC RC 40/50 (40/50 MPA) 50% BLAST FURNACE SLAG",
}
CONCRETE_FLYASH = {
    "RC32/40": "CONCRETE LCC RC 32/40 (32/40 MPA) 30% FLY ASH",
}

# =========================================================
# 3. CARBON FACTORS (kgCO2e per t, m3 or litre)
# ---------------------------------------------------------
# !! These are BACK-SOLVED from the manual pivots (kgCO2e / quantity), mostly
# !! August 2026, HVO from July, fly-ash concrete from June. They reproduce the
# !! manual; they are not a published factor set. Swap in your real library.
# =========================================================
CARBON_FACTORS = {
    AGG: 406815 / 54242.158727,
    CEM_LCC: 456280 / 748.38,
    CEM_OPC: 45360 / 54.0,
    CONCRETE_SLAG["GEN1"]: 122.4,
    CONCRETE_SLAG["GEN3"]: 4176 / 29,
    CONCRETE_SLAG["RC32/40"]: 202164 / 991,
    CONCRETE_SLAG["RC40/50"]: 1881 / 8,
    CONCRETE_FLYASH["RC32/40"]: 78230 / 281,
    CONCRETE_OPC["GEN0"]: 3628 / 23.93,
    CONCRETE_OPC["GEN1"]: 25056 / 119.5,
    CONCRETE_OPC["GEN3"]: 90900 / 374.5,
    CONCRETE_OPC["RC20/25"]: 13440 / 49.5,
    CONCRETE_OPC["RC28/35"]: 5443 / 18,
    CONCRETE_OPC["RC32/40"]: 28152 / 84.5,
    CONCRETE_OPC["RC40/50"]: 144626 / 379,
    DIESEL: 1626051.5 / 509008.1,
    HVO: 833 / 1389,
    REBAR: 767120 / 446.293,
    W_CD: 9.63 / 19.31,
    W_PLASTIC: 13.96 / 2.82,
    W_SOIL: 283.91 / 280,
    W_WOOD: 32.58 / 7.14,
}

# =========================================================
# 4. DROP RULES
# =========================================================
DROP_KEYWORDS = [
    "WAITING TIME", "WAIT TIME", "WAITI TIME", "PART LOAD", "MINIMUM LOAD",
    "EXCEPTIONAL COST CHARGE", "EXCEPTION COST CHARGE", "ENERGY SURCHARGE",
    "EXT RAD", "LAND DRAIN",          # Wolseley "AGG 125/150 MM 6 M BN3 EXT RAD" = drain pipe, not aggregate
    "FUEL REPLENISHMENT", "ADMIN FEE", "WASTED JOURNEY", "TRANSPORT", "DELIVERY",
    "CARRIAGE", "FREIGHT", "HAULAGE",
    "CONTAINER DEPOSIT", "IBC DEPOSIT", "RETURNABLE DEPSOITS", "DEPOSIT IBC",
    "ADBLUE", "AD BLUE", "FLEETBLUE", "ANTI-BUG ADDITIVE", "PD5 FUEL", "GRAVITY HOSE",
    "EXPANDING FOAM", "FOAM FIX", "SILICONE", "WATER STOP", "WATERSTOP",
    "TOKSTRIP", "ADOMAST", "ADOSTRIKE", "ADO STRIKE", "ADOTARD", "ADOCURE", "ADO CURE",
    "DENSO TAPE", "SAFETY CAPS", "MUSHROOM CAPS", "DOWEL BAR CAPS", "REBAR CAPS",
    "SPACERS", "DOUBLE COVER", "TYING WIRE", "WIRECHAIR", "HY-CHAIRS", "PANEL CLIPS",
    "HERAS", "DIVIBAR", "DIVI BAR", "DIVI SLEEVES", "RUBBER BLOCK", "ANGLED COUPLER",
    "ANGLE SUPPORT", "WEIGHTS", "ROUND TOP PANELS", "ROAD PINS", "STEEL BANDIN",
    "SPTT", "MPTT", "SIGNAL LORA", "CONCRETE NOT TAKEN", "SEPTIC TANK",
    "CONCRETE LINTEL", "STANDARD BLOCK", "FLAT TOP", "RING CLUTCH",
    "PAINT LINEMARK", "TENSAR", "GEOGRID", "CELLCORE", "FIBRE FILLERBOARD",
    "RESIN", "ROYALTIES", "SKIP @", "UNLOADED", "SEPA NOTE",
    "IN ERROR", "CREDIT RECEIVED",
]
# Rows containing these survive the keyword drop (still subject to the £0 rule)
KEEP_OVERRIDES = ["DELIVERY OF WHITE DIESEL", "MATERIAL DELIVERY"]

SURCHARGE_RE = re.compile(r"SURCHAR")                      # catches the "surchare" typo too
INC_SURCHARGE_RE = re.compile(r"INC(?:L|LUDING)?\.?\s+SURCHARGE")

AGGREGATE_PREFIXES = ["M110", "M115", "M120", "M125", "M130", "M135", "M140", "M145",
                      "M150", "M155", "M160", "M165", "M170", "M175", "M180", "M190"]
CONCRETE_PREFIXES = ["M21", "M22", "M23", "M24", "M25"]

CEMENT_OPC_KEYWORDS = [
    "POSTCRETE", "POST CRETE", "POSTCTRETE", "POSTFIX", "POST FIX", "POSFIX", "POSTMIX",
    "MASTERCRETE", "MULTICEM", "MULTI CEM", "QUICKCEM", "MASTERGRADE",
    "SIKAGROUT", "SIKA GROUT", "SIKA 111", "CONBEXTRA", "CEMENT",
]
CBS_RE = re.compile(r"\bCBS\b|CEMENT BOUND SAND|CEMENT BASED SAND")


def drop_reason(desc: str, code: str, qty: float, gbp: float):
    """Returns why a row is excluded, or None to keep it."""
    d = desc.upper()
    override = any(k in d for k in KEEP_OVERRIDES)
    if not override:
        for kw in DROP_KEYWORDS:
            if kw in d:
                return f"keyword: {kw}"
        if SURCHARGE_RE.search(d) and not INC_SURCHARGE_RE.search(d):
            return "surcharge line"
    if gbp == 0:
        # £0 invoice lines are summaries/duplicates, except the Breedon-style
        # "INV nnn - SUPPLY OF ..." aggregate lines that carry the real tonnage.
        is_agg = any(code.startswith(p) for p in AGGREGATE_PREFIXES)
        if not (is_agg and d.startswith("INV") and qty > 1):
            return "£0 line"
    return None


# =========================================================
# 5. WASTE (PO-level rules)
# =========================================================
WASTE_EXTRA_RE = re.compile(r"PER LOAD|INERT MATERIAL TO TIP|CART AWAY|DISPOSAL OF UNUSED CBS|DISPOSAL - CONCRETE")
RENTAL_RE = re.compile(r"HIRE|RENTAL|PER DAY")
LOAD_RE = re.compile(r"PER LOAD|INERT MATERIAL TO TIP|CART AWAY")
FEE_RE = re.compile(r"EXCHANGE|UPLIFT|TIP & RETURN")
SKIPSIZE_RE = re.compile(r"SKIP|SKP|\bBIN\b|YARD|YRD|\d\s?YD\b|\d\s?CY\b|CUYD")
MIXED_RE = re.compile(r"GENERAL|MIXED|MUNICIPAL|DMR|CONSTRUCTION|RUBBISH")


def waste_material(d: str):
    if "WOOD" in d or "TIMBER" in d:
        return W_WOOD
    if "PLASTIC" in d:
        return W_PLASTIC
    if re.search(r"SOIL|INERT|MUCK|STONE", d):
        return W_SOIL
    if re.search(r"CONCRETE|CBS|RUBBLE|HARDCORE|TYRE", d):
        return W_CD
    return None


def is_waste_row(code: str, d: str) -> bool:
    return code.startswith("P5") or bool(WASTE_EXTRA_RE.search(d))


def process_waste(w: pd.DataFrame) -> pd.DataFrame:
    """w = waste rows only. Returns rows with Category/Quantity/Rule/Flag, or Drop_Reason."""
    w = w.copy()
    d = w["_D"]
    unit = w["_U"]
    po = w["Contract"].astype(str) + "|" + w["PO Number"].astype(str)

    is_rental = d.str.contains(RENTAL_RE)
    is_load = d.str.contains(LOAD_RE) | (unit == "LD")
    is_fee = d.str.contains(FEE_RE)
    is_skip = d.str.contains(SKIPSIZE_RE)
    is_tyre_count = d.str.contains("TYRE") & unit.isin(["EA", "NO"])

    tonnage = (~is_rental & ~is_load & ~is_fee) & (
        (unit == "TN") | (unit.isin(["EA", "NO"]) & ~is_skip & ~is_tyre_count)
    )
    lift = ~is_rental & ~is_load & ~tonnage & ~is_tyre_count
    pos_with_tonnage = set(po[tonnage])

    po_material = {}
    for k, desc in zip(po[lift], d[lift]):
        m = waste_material(desc)
        if m:
            po_material.setdefault(k, set()).add(m)

    cats, qtys, rules, flags, drops = [], [], [], [], []
    for i in range(len(w)):
        desc, u, q, g, k = d.iat[i], unit.iat[i], w["_Q"].iat[i], w["_G"].iat[i], po.iat[i]
        mat = waste_material(desc)
        cat, t, rule, flag, drop = None, 0.0, "", "", None

        if is_tyre_count.iat[i]:
            drop = "waste: tyres counted by the unit, no tonnage"
        elif is_rental.iat[i]:
            drop = "waste: skip hire / rental"
        elif is_load.iat[i]:
            t = q * LOAD_TONNES
            per_load = g / q if q else 0.0
            if re.search(r"INERT|SOIL", desc):
                cat = W_SOIL
            elif per_load > LOAD_PRICE_CD_ABOVE:
                cat = W_CD
            elif per_load < LOAD_PRICE_SOIL_BELOW:
                cat = W_SOIL
            else:
                cat = W_CD
                flag = f"£{per_load:,.0f}/load is in the undefined £200-£250 band - booked as C&D"
            rule = f"{q:g} load(s) x {LOAD_TONNES:g} t"
        elif tonnage.iat[i]:
            t = q
            if mat:
                cat = mat
            elif MIXED_RE.search(desc):
                cat = W_CD
            else:
                sib = po_material.get(k, set())
                cat = next(iter(sib)) if len(sib) == 1 else W_CD
            rule = "tonnage as invoiced"
            if u != "TN":
                rule = f"tonnage line invoiced as {u} - qty read as tonnes"
                if float(q).is_integer():
                    flag = f"whole-number {u} on a disposal line - check it really is tonnes"
        elif lift.iat[i]:
            if k in pos_with_tonnage:
                drop = "waste: lift/exchange fee, PO already has a tonnage line"
            else:
                t = q * SKIP_DEFAULT_TONNES
                cat = mat or W_CD
                rule = f"{q:g} lift(s) x {SKIP_DEFAULT_TONNES:g} t (no tonnage on PO)"
        else:
            t = q
            cat = mat or W_CD
            flag = f"unhandled waste unit '{u}'"
            rule = "qty used as-is"

        cats.append(cat); qtys.append(t); rules.append(rule); flags.append(flag); drops.append(drop)

    w["Category"] = cats
    w["New_Quantity"] = qtys
    w["Rule"] = rules
    w["Review_Flag"] = flags
    w["Drop_Reason"] = drops
    return w


# =========================================================
# 6. CBS (split into sand -> AGGREGATE and cement -> CEMENT OPC)
# =========================================================
def process_cbs(row) -> list:
    d, u, q = row["_D"], row["_U"], row["_Q"]
    m = re.search(r"(\d{1,2})\s?:\s?1", d)
    ratio = int(m.group(1)) if m else CBS_DEFAULT_RATIO
    sand_t, cem_t = CBS_MIX.get(ratio, CBS_MIX[CBS_DEFAULT_RATIO])
    flag = "" if ratio in CBS_MIX else f"{ratio}:1 CBS has no mix design - used {CBS_DEFAULT_RATIO}:1"
    if not m:
        flag = f"no ratio in description - assumed {CBS_DEFAULT_RATIO}:1"

    # Sand bought separately (e.g. "CBS SAND COLLECTED FROM ...") - plain aggregate
    if "CBS SAND" in d:
        return [(AGG, q, "CBS sand bought separately - aggregate as invoiced", "")]

    if u == "TN":
        flag = (flag + "; " if flag else "") + "CBS in TN treated as m3 (matches manual) - check the unit"
    m3 = q
    parts = []
    if "BATCH" in d:
        # Batching only: the sand is on a separate line, so only the cement is new
        parts.append((CEM_OPC, m3 * cem_t, f"CBS batching {m3:g} m3 x {cem_t} t cement ({ratio}:1)", flag))
    else:
        parts.append((AGG, m3 * sand_t, f"CBS {m3:g} m3 x {sand_t} t sand ({ratio}:1)", flag))
        parts.append((CEM_OPC, m3 * cem_t, f"CBS {m3:g} m3 x {cem_t} t cement ({ratio}:1)", ""))
    return parts


# =========================================================
# 7. CONCRETE GRADE / BINDER
# =========================================================
PAIR_RE = re.compile(r"(?<![A-Z0-9])R?C\s?(\d{1,2})\s?/\s?(\d{1,2})")
SINGLE_RE = re.compile(r"(?<![A-Z0-9/])C\s?(\d{1,2})(?![0-9/])")
GEN_RE = re.compile(r"\bGEN\s?(\d)")
ST_RE = re.compile(r"\bST\s?(\d)\b")
SLAG_RE = re.compile(r"CIIIA|CIII\b|CEM\s?III|CEM\s?111|SLAG|GGBS|CIIA\b|CIIB-S")
FLYASH_RE = re.compile(r"CEM\s?II\s?/?\s?B-?V|CIIB-?V|FLY\s?ASH|PFA|\bBV\b")

SINGLE_MAP = {8: "GEN1", 10: "GEN1", 15: "GEN3", 16: "GEN3", 20: "RC20/25", 25: "RC20/25",
              30: "RC32/40", 35: "RC28/35", 40: "RC32/40", 45: "RC40/50", 50: "RC40/50"}
ST_MAP = {1: "GEN0", 2: "GEN1", 3: "GEN3", 4: "GEN3", 5: "RC20/25"}
GEN_MAP = {0: "GEN0", 1: "GEN1", 2: "GEN1", 3: "GEN3"}


def concrete_grade(d: str):
    """Returns (grade_key, note) or (None, reason)."""
    m = PAIR_RE.search(d)
    if m:
        cyl = int(m.group(1))
        if cyl <= 6:   return "GEN0", ""
        if cyl <= 10:  return "GEN1", ""
        if cyl <= 16:  return "GEN3", ("C12/15 has no category - booked as GEN 3" if cyl < 16 else "")
        if cyl <= 20:  return "RC20/25", ""
        if cyl <= 25:  return "RC32/40", ""   # manual books C25/30 as RC 32/40
        if cyl <= 28:  return "RC28/35", ""
        if cyl <= 32:  return "RC32/40", ""
        return "RC40/50", ""
    m = GEN_RE.search(d)
    if m:
        g = int(m.group(1))
        return GEN_MAP.get(g, "GEN3"), ("" if g in (0, 1, 3) else f"GEN {g} has no category")
    m = ST_RE.search(d)
    if m:
        return ST_MAP.get(int(m.group(1)), "GEN3"), ""
    if "SCREED" in d:
        return "GEN0", ""
    if "SEMI-DRY" in d:
        return "GEN3", ""
    m = SINGLE_RE.search(d)
    if m:
        v = int(m.group(1))
        if v in SINGLE_MAP:
            return SINGLE_MAP[v], ""
    return None, "concrete code but no strength class found"


def concrete_category(d: str):
    grade, note = concrete_grade(d)
    if grade is None:
        return None, note
    if SLAG_RE.search(d):
        if grade in CONCRETE_SLAG:
            return CONCRETE_SLAG[grade], note
        return CONCRETE_OPC[grade], "slag binder but no LCC category for this grade - booked as OPC"
    if FLYASH_RE.search(d):
        if grade in CONCRETE_FLYASH:
            return CONCRETE_FLYASH[grade], note
        return CONCRETE_OPC[grade], "fly-ash binder but no LCC category for this grade - booked as OPC"
    return CONCRETE_OPC[grade], note


def has_concrete_grade(d: str) -> bool:
    return bool(PAIR_RE.search(d) or GEN_RE.search(d) or ST_RE.search(d))


# =========================================================
# 8. REBAR MASS
# =========================================================
def rebar_tonnes(d: str, u: str, q: float):
    """Returns (tonnes, rule, flag). tonnes=0 with a flag when the mass is unknowable."""
    if u in ("TN", "T"):
        return q, "tonnes as invoiced", ""
    if u == "KG":
        return q / 1000, "kg / 1000", ""

    mesh = re.search(r"\b(A142|A193|A252|A393|B1131)\b", d)
    if mesh:
        kg_m2 = MESH_KG_PER_M2[mesh.group(1)]
        size = re.search(r"(\d(?:\.\d+)?)\s?M?\s?X\s?(\d(?:\.\d+)?)\s?M\b", d)
        area = float(size.group(1)) * float(size.group(2)) if size else MESH_DEFAULT_SHEET_M2
        t = q * kg_m2 * area / 1000
        return t, f"{q:g} sheet(s) x {kg_m2} kg/m2 x {area:.2f} m2", ""

    if "DOWEL" in d:
        dia = re.search(r"\bR(\d{2})\b|DB-?(\d{2})|\bT(\d{2})\b|(\d{2})\s?MM\s?DIA", d)
        dia = next((int(x) for x in dia.groups() if x), None) if dia else None
        lengths = [int(x) for x in re.findall(r"(?<!\d)(\d{3,4})(?!\d)", d) if 150 <= int(x) <= 3000]
        if dia and lengths:
            kg = 0.00617 * dia ** 2 * lengths[0] / 1000
            return q * kg / 1000, f"{q:g} dowel(s) x {kg:.3f} kg (d{dia} x {lengths[0]}mm)", ""
        return q * DOWEL_FALLBACK_KG / 1000, f"{q:g} dowel(s) x {DOWEL_FALLBACK_KG} kg", "dowel size not parsed - fallback mass used"

    return 0.0, "no mass", f"rebar in '{u}' with no size - excluded from tonnage, check the invoice"


# =========================================================
# 9. MAIN ROW CLASSIFIER (everything except waste and CBS)
# =========================================================
REBAR_WORDS = ["REBAR", "REINFORCEMENT", "FABRIC", "MESH", "CUT & BEND", "CUT AND BENT",
               "A142", "A193", "A252", "A393", "B1131", "DOWEL"]


def classify_row(row):
    """Returns (category or None, quantity, rule, flag)."""
    code, d, u, q, g = row["_C"], row["_D"], row["_U"], row["_Q"], row["_G"]

    # Fuel
    if code.startswith("P810"):
        cat = HVO if "HVO" in d else DIESEL
        flag = ""
        if u == "L" and q <= 1 and g > 10:
            flag = f"{q:g} L for £{g:,.2f} - quantity looks like a lump sum, not litres"
        return cat, q, "litres as invoiced", flag

    # Rebar
    if code.startswith("M7") and any(k in d for k in REBAR_WORDS):
        t, rule, flag = rebar_tonnes(d, u, q)
        return REBAR, t, rule, flag

    # Fly-ash cement (bulk)
    if "PHOENIX" in d and u == "TN":
        return CEM_LCC, q, "tonnes as invoiced", ""

    # Bagged / bulk OPC cement (anything saying CEMENT that isn't a graded concrete)
    if any(k in d for k in CEMENT_OPC_KEYWORDS) and not has_concrete_grade(d) and not code.startswith(("P", "M7")):
        if u in ("TN", "T"):
            return CEM_OPC, q, "tonnes as invoiced", ""
        if u == "KG":
            return CEM_OPC, q / 1000, "kg / 1000", ""
        stated = re.search(r"(\d{2})\s?KG", d)
        if BAG_WEIGHT_MODE == "stated":
            kg = float(stated.group(1)) if stated else DEFAULT_BAG_KG
        else:
            kg = 20.0
        flag = "" if u in ("EA", "BAG", "NO", "M3") else f"cement in unit '{u}' treated as bags"
        return CEM_OPC, q * kg / 1000, f"{q:g} bag(s) x {kg:g} kg", flag

    # Ready-mix concrete
    if any(code.startswith(p) for p in CONCRETE_PREFIXES):
        cat, note = concrete_category(d)
        if cat is None:
            return None, q, "", note
        flag = note
        if u != "M3":
            flag = (flag + "; " if flag else "") + f"concrete invoiced in '{u}' not m3 - qty used as-is"
        return cat, q, "m3 as invoiced", flag

    # Aggregate
    if any(code.startswith(p) for p in AGGREGATE_PREFIXES):
        if u in ("NO", "EA") and q <= 5 and g > 500:
            return AGG, g / 22.0, f"lump-sum invoice £{g:,.2f} / £22 per t", "lump-sum aggregate converted from value"
        bag = re.search(r"(\d{2})\s?KG", d)
        if bag and u in ("BAG", "EA", "NO"):
            kg = float(bag.group(1))
            return AGG, q * kg / 1000, f"{q:g} bag(s) x {kg:g} kg", ""
        # EA/NO/BAG aggregate lines are loads or bulk bags already in tonnes - only odd units get flagged
        flag = "" if u in ("TN", "T", "EA", "NO", "BAG", "LD") else f"aggregate in '{u}' - qty used as-is"
        return AGG, q, "tonnes as invoiced", flag

    return None, q, "", ""


# =========================================================
# 10. ROLLUP GROUPS
# =========================================================
def high_level_group(cat):
    if not cat:
        return None
    c = str(cat).upper()
    if c == AGG: return "Aggregate"
    if c == CEM_LCC: return "Cement LCC"
    if c == CEM_OPC: return "Cement OPC"
    if c.startswith("CONCRETE LCC"): return "Concrete LCC"
    if c.startswith("CONCRETE OPC"): return "Concrete OPC"
    if c == REBAR: return "Rebar"
    if c == DIESEL: return "Diesel"
    if c == HVO: return "HVO"
    if c.startswith("WASTE"): return "Waste"
    return None


ROLLUP_ORDER = ["Aggregate", "Cement LCC", "Cement OPC", "Concrete LCC", "Concrete OPC",
                "Rebar", "Diesel", "HVO", "Waste"]


# =========================================================
# 11. PIPELINE
# =========================================================
def get_latest_scope3_file(directory: str) -> str:
    latest = client.find_latest_file(directory, suffix=".xlsx", name_contains="Scope 3")
    if not latest or os.path.basename(latest).startswith("~$"):
        raise FileNotFoundError(f"No Scope 3 Excel files found in: {directory}")
    return latest


def to_number(s: pd.Series) -> pd.Series:
    return pd.to_numeric(
        s.astype(str).str.replace("£", "", regex=False).str.replace(",", "", regex=False).str.strip(),
        errors="coerce",
    ).fillna(0.0)


def run(source_file: str):
    print(f"Source: {source_file}")
    df_raw = pd.read_excel(io.BytesIO(client.read_bytes(source_file)), sheet_name="Data", header=6)
    df_raw.columns = [str(c).strip() for c in df_raw.columns]
    for col in ["Code", "Description", "Quantity", "GBP Value", "Contract", "PO Number"]:
        if col not in df_raw.columns:
            raise KeyError(f"Expected column '{col}' not found.")
    df_raw = df_raw[df_raw["Code"].notna()].copy()   # drop blank / total rows

    unit_col = "tpgl_unitdel" if "tpgl_unitdel" in df_raw.columns else "UN"
    df = df_raw.copy()
    df["_C"] = df["Code"].astype(str).str.upper().str.strip()
    df["_D"] = df["Description"].astype(str).str.upper().str.strip()
    df["_U"] = df[unit_col].astype(str).str.upper().str.strip()
    df["_Q"] = to_number(df["Quantity"])
    df["_G"] = to_number(df["GBP Value"])

    # --- Drops ---
    df["Drop_Reason"] = [drop_reason(d, c, q, g) for d, c, q, g in zip(df["_D"], df["_C"], df["_Q"], df["_G"])]
    dropped = [df[df["Drop_Reason"].notna()]]
    df = df[df["Drop_Reason"].isna()].copy()

    out_rows = []

    # --- Waste ---
    waste_mask = np.array([is_waste_row(c, d) for c, d in zip(df["_C"], df["_D"])])
    w = process_waste(df[waste_mask])
    dropped.append(w[w["Drop_Reason"].notna()])
    for _, r in w[w["Drop_Reason"].isna()].iterrows():
        out_rows.append((r, r["Category"], r["New_Quantity"], r["Rule"], r["Review_Flag"], r["_G"]))
    df = df[~waste_mask]

    # --- CBS ---
    cbs_mask = df["_D"].str.contains(CBS_RE) & ~df["_C"].str.startswith("P")
    for _, r in df[cbs_mask].iterrows():
        for n, (cat, t, rule, flag) in enumerate(process_cbs(r)):
            out_rows.append((r, cat, t, rule, flag, r["_G"] if n == 0 else 0.0))
    df = df[~cbs_mask]

    # --- Everything else ---
    for _, r in df.iterrows():
        cat, t, rule, flag = classify_row(r)
        out_rows.append((r, cat, t, rule, flag, r["_G"]))

    # --- Assemble Working Data ---
    recs = []
    for r, cat, t, rule, flag, gbp in out_rows:
        rec = {c: r[c] for c in df_raw.columns}
        rec["Raw_Description"] = r["Description"]
        rec["Original_Quantity"] = r["Quantity"]
        rec["Description"] = cat if cat else r["Description"]
        rec["Quantity"] = t
        rec["GBP Value"] = gbp
        rec["Rule"] = rule if cat else "unmapped - not reported"
        rec["Review_Flag"] = flag
        recs.append(rec)
    work = pd.DataFrame(recs)
    work["High_Level_Group"] = work["Description"].apply(high_level_group)
    work["Factor"] = work["Description"].map(CARBON_FACTORS)
    work["kgCO2e"] = work["Quantity"] * work["Factor"].fillna(0.0)

    missing = work[work["High_Level_Group"].notna() & work["Factor"].isna()]
    for cat in missing["Description"].unique():
        print(f"WARNING: no carbon factor for '{cat}' - its kgCO2e is 0")
    work.loc[missing.index, "Review_Flag"] = (
        work.loc[missing.index, "Review_Flag"].fillna("") + " | no carbon factor for this category"
    ).str.strip(" |")

    # Keep original column order, helpers on the end
    extra = ["Raw_Description", "Original_Quantity", "Rule", "Review_Flag", "Factor", "kgCO2e", "High_Level_Group"]
    work = work[[c for c in df_raw.columns] + extra]

    dropped_df = pd.concat(dropped)[list(df_raw.columns) + ["Drop_Reason"]]

    # --- Detailed Carbon (the pivot) ---
    rep = work[work["High_Level_Group"].notna()]
    detailed = (
        rep.groupby("Description", as_index=False)
        .agg(**{"Sum of Quantity": ("Quantity", "sum"), "kgCO2e": ("kgCO2e", "sum")})
        .rename(columns={"Description": "Row Labels"})
        .sort_values("Row Labels")
    )
    detailed = pd.concat([detailed, pd.DataFrame([{
        "Row Labels": "Grand Total",
        "Sum of Quantity": detailed["Sum of Quantity"].sum(),
        "kgCO2e": detailed["kgCO2e"].sum(),
    }])], ignore_index=True)

    # --- Rollup Summary ---
    rows = []
    for grp in ROLLUP_ORDER:
        sub = rep[rep["High_Level_Group"] == grp]
        cost_label, cost = "", ""
        if grp in ("Diesel", "HVO", "Waste"):
            cost_label = f"{grp} cost"
            cost = round(sub["GBP Value"].sum(), 2)
        rows.append({"": grp, "QUANT": round(sub["Quantity"].sum(), 2),
                     "tCO2e": round(sub["kgCO2e"].sum() / 1000, 3),
                     "Cost Description": cost_label, "Cost": cost})
    rollup = pd.DataFrame(rows)

    flags = work[work["Review_Flag"].fillna("") != ""]
    return df_raw, work, dropped_df, detailed, rollup, flags


def main():
    source = get_latest_scope3_file(SOURCE_DIR)
    df_raw, work, dropped, detailed, rollup, flags = run(source)

    out_path = f"{OUTPUT_DIR}/{OUTPUT_FILENAME}"
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as xw:
        df_raw.to_excel(xw, sheet_name="Data", index=False)
        work.to_excel(xw, sheet_name="Working Data", index=False)
        dropped.to_excel(xw, sheet_name="Dropped Rows", index=False)
        detailed.to_excel(xw, sheet_name="Detailed Carbon", index=False)
        rollup.to_excel(xw, sheet_name="Rollup Summary", index=False)
        flags.to_excel(xw, sheet_name="Review Flags", index=False)
    client.write_bytes(buffer.getvalue(), out_path)

    print(rollup.to_string(index=False))
    print(f"\n{len(flags)} row(s) flagged for review. Written to:\n{out_path}")


if __name__ == "__main__":
    main()
