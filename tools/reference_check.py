"""
Python reference implementation of the store-master-data ETL.

Purpose:
  1. Compute the EXPECTED results, so the FME workspace output can be verified.
  2. Serve as the Python/GeoPandas fallback if FME is not available.

Rules are applied in a fixed order; a record is rejected with the FIRST rule it
fails (same behaviour as a linear FME workspace).

Run:  python reference_check.py      (writes to ../output_reference)
"""
import re
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

BASE = Path(__file__).resolve().parent.parent
DATA, OUT = BASE / "data", BASE / "output_reference"
OUT.mkdir(exist_ok=True)

TARGET_CRS = "EPSG:4326"
BBOX = {"DE": (5.87, 47.27, 15.04, 55.06),   # lon_min, lat_min, lon_max, lat_max
        "RO": (20.26, 43.62, 29.71, 48.27)}
POSTCODE = {"DE": r"^[0-9]{5}$", "RO": r"^[0-9]{6}$"}
STATUS_DOMAIN = {"open", "closed", "planned"}
MANDATORY = ["store_name", "postcode", "status", "opening_date", "sales_area_m2"]

# ---------------------------------------------------------------- 1 Read
de = gpd.read_file(DATA / "stores_de.geojson")                       # WGS84
ro_raw = pd.read_csv(DATA / "stores_ro.csv", dtype=str)               # keep leading zeros
attr = pd.read_csv(DATA / "store_attributes.csv", dtype=str, keep_default_na=False)

# ---------------------------------------------------------------- 2 Harmonise schema + CRS
de = de.rename(columns={"filial_nr": "store_id", "filialname": "store_name",
                        "plz": "postcode", "ort": "city"})
ro = gpd.GeoDataFrame(
    ro_raw.assign(store_id="RO-" + ro_raw["store_code"].str.zfill(4))
          .rename(columns={"store_name": "store_name", "postal_code": "postcode"}),
    geometry=[Point(float(x), float(y)) for x, y in zip(ro_raw["x"], ro_raw["y"])],
    crs="EPSG:3844").to_crs(TARGET_CRS)
cols = ["store_id", "store_name", "postcode", "city", "geometry"]
loc = pd.concat([de[cols], ro[cols]], ignore_index=True)
loc = gpd.GeoDataFrame(loc, geometry="geometry", crs=TARGET_CRS)
loc[["store_name", "postcode", "city"]] = loc[["store_name", "postcode", "city"]].fillna("")

# Standardise status (trim + lower case) — standardisation, not rejection
attr["status"] = attr["status"].str.strip().str.lower()

rejects = []
def reject(df, rule, reason):
    if len(df):
        r = pd.DataFrame({"store_id": df["store_id"].values,
                          "rule": rule, "reject_reason": reason})
        rejects.append(r)

# ---------------------------------------------------------------- 3 Join
m = loc.merge(attr, on="store_id", how="outer", indicator=True)
reject(m[m["_merge"] == "left_only"], "R1", "Standort ohne Geschäftsdaten (keine Zeile in store_attributes.csv)")
reject(m[m["_merge"] == "right_only"], "R2", "Geschäftsdaten ohne Standort (keine Geometrie in den Standortdateien)")
d = gpd.GeoDataFrame(m[m["_merge"] == "both"].drop(columns="_merge"), geometry="geometry", crs=TARGET_CRS)

# ---------------------------------------------------------------- 4 Duplicate IDs (reject ALL members)
dupmask = d["store_id"].duplicated(keep=False)
reject(d[dupmask], "R3", "Doppelte Filial-ID – Datensatz nicht eindeutig")
d = d[~dupmask]

# ---------------------------------------------------------------- 5 Missing geometry
nogeom = d.geometry.isna() | d.geometry.is_empty
reject(d[nogeom], "R4", "Geometrie fehlt")
d = d[~nogeom]

# ---------------------------------------------------------------- 6 Plausible location (country bbox)
def inside(row):
    x0, y0, x1, y1 = BBOX[row["country"]]
    return x0 <= row.geometry.x <= x1 and y0 <= row.geometry.y <= y1
ok = d.apply(inside, axis=1)
reject(d[~ok], "R5", "Koordinaten außerhalb des Landes (vertauscht, 0/0 oder falsches Koordinatensystem)")
d = d[ok]

# ---------------------------------------------------------------- 7 Mandatory fields
miss = d[MANDATORY].apply(lambda c: c.astype(str).str.strip() == "").any(axis=1)
reject(d[miss], "R6", "Pflichtfeld fehlt (Name, PLZ, Status, Eröffnungsdatum oder Verkaufsfläche)")
d = d[~miss]

# ---------------------------------------------------------------- 8 Value rules
value_rules = [
    (lambda t: ~t["status"].isin(STATUS_DOMAIN),
     "Status nicht im Wertebereich (open, closed, planned)"),
    (lambda t: pd.to_numeric(t["sales_area_m2"], errors="coerce").fillna(0) <= 0,
     "Verkaufsfläche muss größer als 0 sein"),
    (lambda t: pd.to_datetime(t["opening_date"], format="%Y-%m-%d", errors="coerce").isna(),
     "Eröffnungsdatum ungültig"),
    (lambda t: ~t.apply(lambda r: bool(re.match(POSTCODE[r["country"]], r["postcode"])), axis=1),
     "PLZ-Format falsch (DE: 5 Ziffern, RO: 6 Ziffern)"),
]
for rule_fn, reason in value_rules:
    mask = rule_fn(d)
    reject(d[mask], "R7", reason)
    d = d[~mask]

# ---------------------------------------------------------------- 9 Write
valid = d.copy()
valid["lon"], valid["lat"] = valid.geometry.x.round(6), valid.geometry.y.round(6)
valid = valid[["store_id", "country", "store_name", "postcode", "city", "status",
               "opening_date", "sales_area_m2", "store_format", "lon", "lat", "geometry"]]
valid.to_file(OUT / "stores_valid.gpkg", layer="stores_valid", driver="GPKG")
rej = pd.concat(rejects, ignore_index=True).sort_values(["rule", "store_id"])
rej.to_csv(OUT / "stores_rejected.csv", index=False, encoding="utf-8")

total = len(valid) + len(rej)
summary = (rej.groupby(["rule", "reject_reason"]).size().rename("count").reset_index())
summary.to_csv(OUT / "quality_summary.csv", index=False, encoding="utf-8")
print(f"Records total: {total} | valid: {len(valid)} | rejected: {len(rej)} "
      f"| valid share: {len(valid)/total:.1%}")
print(summary.to_string(index=False))
print("\nRejected IDs:")
print(rej.to_string(index=False))
