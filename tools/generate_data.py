"""
Generate the synthetic input data for the FME store-master-data ETL exercise.

Scenario (fictional): a retail company harmonises store master data from two
countries (Germany, Romania) into one validated dataset. All names, IDs,
postcodes and coordinates are synthetic. No real company data is used.

Outputs (in ../data):
  stores_de.geojson     German store locations, WGS84 lon/lat (RFC 7946 GeoJSON)
  stores_ro.csv         Romanian store locations, x/y in Stereo 70 (EPSG:3844), metres
  store_attributes.csv  Business attributes for both countries

Errors are injected deliberately and listed in ../docs/known_errors.md.
Run:  python generate_data.py
"""
import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

from pyproj import Transformer

random.seed(42)
OUT = Path(__file__).resolve().parent.parent / "data"
OUT.mkdir(exist_ok=True)

# (city, lat, lon, postcode prefix) — approximate city centres
DE_CITIES = [
    ("Hannover", 52.3759, 9.7320, "30"), ("Hamburg", 53.5511, 9.9937, "22"),
    ("Berlin", 52.5200, 13.4050, "10"), ("München", 48.1351, 11.5820, "80"),
    ("Köln", 50.9375, 6.9603, "50"), ("Frankfurt am Main", 50.1109, 8.6821, "60"),
    ("Stuttgart", 48.7758, 9.1829, "70"), ("Düsseldorf", 51.2277, 6.7735, "40"),
    ("Leipzig", 51.3397, 12.3731, "04"), ("Dortmund", 51.5136, 7.4653, "44"),
    ("Bremen", 53.0793, 8.8017, "28"), ("Dresden", 51.0504, 13.7373, "01"),
    ("Nürnberg", 49.4521, 11.0767, "90"), ("Heilbronn", 49.1427, 9.2109, "74"),
    ("Kassel", 51.3127, 9.4797, "34"), ("Münster", 51.9607, 7.6261, "48"),
    ("Freiburg im Breisgau", 47.9990, 7.8421, "79"), ("Rostock", 54.0924, 12.0991, "18"),
    ("Erfurt", 50.9848, 11.0299, "99"), ("Mannheim", 49.4875, 8.4660, "68"),
]
RO_CITIES = [
    ("București", 44.4268, 26.1025, "0"), ("Cluj-Napoca", 46.7712, 23.6236, "40"),
    ("Timișoara", 45.7489, 21.2087, "30"), ("Iași", 47.1585, 27.6014, "70"),
    ("Constanța", 44.1598, 28.6348, "90"), ("Brașov", 45.6427, 25.5887, "50"),
    ("Craiova", 44.3302, 23.7949, "20"), ("Sibiu", 45.7983, 24.1256, "55"),
    ("Oradea", 47.0465, 21.9189, "41"), ("Ploiești", 44.9367, 26.0129, "10"),
]
DISTRICTS = ["Nord", "Süd", "Ost", "West", "Mitte", "Zentrum", "Bahnhof", "Altstadt"]
RO_DISTRICTS = ["Nord", "Sud", "Est", "Vest", "Centru", "Gară"]
FORMATS = ["standard", "compact", "large"]

to_stereo70 = Transformer.from_crs("EPSG:4326", "EPSG:3844", always_xy=True)


def jitter(lat, lon, d=0.03):
    return round(lat + random.uniform(-d, d), 6), round(lon + random.uniform(-d, d), 6)


def postcode(prefix, length):
    return prefix + "".join(random.choice("0123456789") for _ in range(length - len(prefix)))


def random_date(start=date(2005, 1, 1), end=date(2026, 6, 30)):
    return (start + timedelta(days=random.randint(0, (end - start).days))).isoformat()


# ---------------------------------------------------------------- Germany
de_features = []
for i in range(1, 101):
    city, lat, lon, pre = random.choice(DE_CITIES)
    lat, lon = jitter(lat, lon)
    de_features.append({
        "type": "Feature",
        "properties": {
            "filial_nr": f"DE-{i:04d}",
            "filialname": f"Filiale {city} {random.choice(DISTRICTS)}",
            "plz": postcode(pre, 5),
            "ort": city,
        },
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
    })

def de(i):
    return de_features[i - 1]

# --- injected errors (Germany) ---
dup = json.loads(json.dumps(de(42)))                       # E03 duplicate ID
dup["properties"]["filialname"] = "Filiale Hannover Messe"
dup["geometry"]["coordinates"] = [9.8102, 52.3218]
de_features.append(dup)
de(13)["geometry"] = None                                  # E04 missing geometry
de(21)["geometry"]["coordinates"] = [0.0, 0.0]             # E05 (0,0)
for i in (34, 55):                                         # E06/E07 lon/lat swapped
    c = de(i)["geometry"]["coordinates"]
    de(i)["geometry"]["coordinates"] = [c[1], c[0]]
de(8)["properties"]["filialname"] = ""                     # E09 name missing
de(66)["properties"]["plz"] = ""                           # E10 postcode missing
de(90)["properties"]["plz"] = de(90)["properties"]["plz"][:4]  # E16 4-digit postcode

with open(OUT / "stores_de.geojson", "w", encoding="utf-8") as f:
    json.dump({"type": "FeatureCollection", "features": de_features}, f,
              ensure_ascii=False, indent=1)

# ---------------------------------------------------------------- Romania
ro_rows = []
for i in range(1, 61):
    city, lat, lon, pre = random.choice(RO_CITIES)
    lat, lon = jitter(lat, lon)
    x, y = to_stereo70.transform(lon, lat)
    ro_rows.append({
        "store_code": i,
        "store_name": f"Magazin {city} {random.choice(RO_DISTRICTS)}",
        "postal_code": postcode(pre, 6),
        "city": city,
        "x": round(x, 2),
        "y": round(y, 2),
    })

def ro(i):
    return ro_rows[i - 1]

# E08 wrong CRS: lon/lat degrees written into the Stereo 70 columns
ro(17)["x"], ro(17)["y"] = 26.0874, 44.4391
# E17 5-digit postcode (Romania needs 6)
ro(40)["postal_code"] = ro(40)["postal_code"][:5]

with open(OUT / "stores_ro.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(ro_rows[0].keys()))
    w.writeheader()
    w.writerows(ro_rows)

# ---------------------------------------------------------------- Attributes
attr = []
def attr_row(store_id, country):
    status = random.choices(["open", "planned", "closed"], weights=[85, 8, 7])[0]
    opening = (random_date(date(2026, 12, 1), date(2027, 9, 30)) if status == "planned"
               else random_date())
    return {"store_id": store_id, "country": country, "status": status,
            "opening_date": opening,
            "sales_area_m2": random.choice(range(600, 2401, 10)),
            "store_format": random.choice(FORMATS)}

for i in range(1, 101):
    if i != 97:                                            # E01 location without attributes
        attr.append(attr_row(f"DE-{i:04d}", "DE"))
for i in range(1, 61):
    if i != 58:                                            # E02 location without attributes
        attr.append(attr_row(f"RO-{i:04d}", "RO"))
# E11-E13 attribute rows without a location
attr += [attr_row("DE-0101", "DE"), attr_row("DE-0102", "DE"), attr_row("RO-0061", "RO")]

def a(sid):
    return next(r for r in attr if r["store_id"] == sid)

a("RO-0025")["status"] = ""                                # E14 status missing
a("DE-0071")["status"] = "unknown"                         # E15 status not in domain
a("DE-0080")["sales_area_m2"] = 0                          # E18 sales area not > 0
a("RO-0033")["opening_date"] = "2021-02-30"                # E19 impossible date
# Standardisation cases (must NOT be rejected): messy status spelling
for sid, val in [("DE-0003", "OPEN"), ("DE-0019", " Open "), ("RO-0005", "Open"),
                 ("RO-0012", "CLOSED ")]:
    a(sid)["status"] = val

random.shuffle(attr)
with open(OUT / "store_attributes.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(attr[0].keys()))
    w.writeheader()
    w.writerows(attr)

print(f"DE locations: {len(de_features)} | RO locations: {len(ro_rows)} | attribute rows: {len(attr)}")
