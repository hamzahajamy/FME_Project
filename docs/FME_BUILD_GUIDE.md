# FME Build Guide: Store Master Data ETL

Step-by-step instructions for building the workspace in **FME Form (Workbench)** inside the FME Academy lab VM.
Target time: about 2–2.5 hours of building. Check your feature counts against the
**expected counts** after each step (the numbers come from `tools/reference_check.py`).

> **Version note:** transformer names and ports below match the current FME documentation.
> Some parameter labels differ slightly between FME versions. If a label doesn't match,
> look for the closest equivalent and note it in your README.

---

## 0. Lab setup (about 25 min, mostly waiting)

1. Launch the lab VM. Startup takes about 5–10 min, and C:\FMEData takes about 10 more to update.
   While it loads, read this guide again.
2. In the VM browser, open your GitHub repo → **Code → Download ZIP**. Extract it to
   `C:\Users\<you>\Desktop\fme-store-etl\`.
3. Optional (30 min max): do the FME Academy "Getting Started" exercise using C:\FMEData.
4. Open **FME Workbench → New workspace**. Save it right away as
   `workspace\store_master_data_etl.fmw`. **Press Ctrl+S after every step.**
5. Turn on **Feature Caching** (Run menu → Enable Feature Caching). Then you can click
   the green cache icons to inspect data in **Visual Preview** after each step.

---

## 1. Readers (3 sources)

| # | Reader | File | Settings |
|---|---|---|---|
| 1a | **GeoJSON** | `data/stores_de.geojson` | Coordinate system: `LL84` (WGS84 lon/lat). This is the GeoJSON default. |
| 1b | **CSV** | `data/stores_ro.csv` | Encoding **UTF-8** (Romanian diacritics: ș, ț). First row = field names. In *Attribute Definition* choose **Manual** and set `postal_code` to **string/varchar** (Bucharest postcodes start with 0). Set `x` and `y` to **real64**. |
| 1c | **CSV** | `data/store_attributes.csv` | Encoding **UTF-8**. *Attribute Definition* **Manual**: set `store_id`, `status`, `opening_date` and `store_format` to **string**, and `sales_area_m2` to **int32** or **real64**. |

✅ Expected: DE **101** features, RO **60**, attributes **161**.

---

## 2. Harmonise the German locations

**AttributeManager** (name it `AM_DE_Schema`) after the GeoJSON reader:

| Input attribute | Output attribute | Action |
|---|---|---|
| filial_nr | store_id | Rename |
| filialname | store_name | Rename |
| plz | postcode | Rename |
| ort | city | Rename |
| — | source | Set value `stores_de.geojson` |

---

## 3. Harmonise the Romanian locations (geometry + CRS + IDs)

Connect these in a chain after the RO CSV reader:

1. **VertexCreator**: Mode *Replace with Point*; X Value = `x`; Y Value = `y`.
2. **CoordinateSystemSetter**: Coordinate System = `EPSG:3844` (Pulkovo 1942(58) / Stereo 70).
3. **Reprojector**: Destination Coordinate System = `LL84`.
4. **StringPadder**: Attribute `store_code`; Desired String Length `4`; Pad Character `0`; Side *Left*.
5. **AttributeManager** (`AM_RO_Schema`):

| Input attribute | Output attribute | Action / value |
|---|---|---|
| store_code | store_id | Set value: `RO-@Value(store_code)`, then remove `store_code` |
| store_name | store_name | (unchanged) |
| postal_code | postcode | Rename |
| city | city | (unchanged) |
| x, y | — | Remove |
| — | source | Set value `stores_ro.csv` |

✅ Check in Visual Preview: store IDs look like `RO-0001`, and the points lie in Romania
(except **RO-0017**, which lands far outside on purpose).

---

## 4. Standardise the business attributes

After the attributes CSV reader:

1. **AttributeTrimmer**: Attribute `status` (removes the spaces in `" Open "`).
2. **StringCaseChanger**: Attribute `status`; Case Change *lower case* (`"OPEN"` → `"open"`).

This is **standardisation, not rejection**. Four records have messy status spelling and must end up **valid**.

---

## 5. Join locations and business data

**FeatureJoiner**:
- **Left** input: connect *both* `AM_DE_Schema` and `AM_RO_Schema`.
- **Right** input: `StringCaseChanger`.
- Join On: `store_id` = `store_id`; Comparison Mode *String*.
- **Join Mode: Inner**. Unmatched Left features then exit **UnjoinedLeft** and unmatched Right features exit **UnjoinedRight**.

| Port | Expected | Route to |
|---|---|---|
| Joined | **159** | Step 6 |
| UnjoinedLeft | **2** (DE-0097, RO-0058) | Reject **R1** |
| UnjoinedRight | **3** (DE-0101, DE-0102, RO-0061) | Reject **R2** |

---

## 6. Duplicate IDs

**Matcher**:
- Match Geometry: **None**.
- Attribute Matching Strategy: **Match Selected Attributes** → `store_id`.

The Matcher sends **all** features that match another feature to **Matched**, one merged copy per group to **SingleMatched**, and everything else to **NotMatched**.

| Port | Expected | Route to |
|---|---|---|
| Matched | **2** (both DE-0042 records) | Reject **R3** |
| NotMatched | **157** | Step 7 |
| SingleMatched | 1 | **leave unconnected** |

*Design decision to explain in the interview:* when two records share an ID, the workflow can't know which one is correct, so **both** are rejected and the business department decides. A DuplicateFilter would silently keep the first one.

---

## 7. Missing geometry

**GeometryFilter**: Geometry Types to Filter: **Null**, **Point**.

| Port | Expected | Route to |
|---|---|---|
| Null | **1** (DE-0013) | Reject **R4** |
| Point | **156** | Step 8 |

---

## 8. Plausible location (country bounding box)

1. **CoordinateExtractor**: Mode *Specify Coordinate*; Coordinate Index `0`. This creates `_x` (lon) and `_y` (lat).
2. **Tester** (`Test_Country_BBox`), Logic **Composite**:

| # | Left value | Operator | Right value |
|---|---|---|---|
| 1 | country | = | DE |
| 2 | _x | >= | 5.87 |
| 3 | _x | <= | 15.04 |
| 4 | _y | >= | 47.27 |
| 5 | _y | <= | 55.06 |
| 6 | country | = | RO |
| 7 | _x | >= | 20.26 |
| 8 | _x | <= | 29.71 |
| 9 | _y | >= | 43.62 |
| 10 | _y | <= | 48.27 |

Composite expression: `(1 AND 2 AND 3 AND 4 AND 5) OR (6 AND 7 AND 8 AND 9 AND 10)`

| Port | Expected | Route to |
|---|---|---|
| Passed | **152** | Step 9 |
| Failed | **4** (DE-0021 at 0/0, DE-0034 and DE-0055 with lon/lat swapped, RO-0017 in the wrong CRS) | Reject **R5** |

*Known limitation (good to mention when asked):* a bounding box is a rough check. A store
placed in Austria would still pass. The stricter version is a point-in-polygon test against
country boundaries (**PointOnAreaOverlayer**). That's an optional stretch goal.

---

## 9. Mandatory fields

**Tester** (`Test_Mandatory`), Logic **AND**. Use the operator **Attribute Has a Value** for:
`store_name`, `postcode`, `status`, `opening_date`, `sales_area_m2`.

| Port | Expected | Route to |
|---|---|---|
| Passed | **149** | Step 10 |
| Failed | **3** (DE-0008 no name, DE-0066 no postcode, RO-0025 no status) | Reject **R6** |

---

## 10. Value rules (4 checks in a chain)

| Step | Transformer | Configuration | Passes on | Fails → R7 reason |
|---|---|---|---|---|
| 10a | **Tester** `Test_Status_Domain` | `status` **In** `open,closed,planned` (or 3 clauses with `=` and Logic OR) | 148 | 1: DE-0071 `unknown` → *Status nicht im Wertebereich* |
| 10b | **Tester** `Test_SalesArea` | `sales_area_m2` **>** `0` | 147 | 1: DE-0080 → *Verkaufsfläche muss größer als 0 sein* |
| 10c | **DateTimeConverter** | Datetime attribute `opening_date`; Input format `%Y-%m-%d`; Output format `%Y-%m-%d`; **Repair Overflow: No** | 146 (Output) | 1: RO-0033 `2021-02-30` exits **Rejected** → *Eröffnungsdatum ungültig* |
| 10d | **Tester** `Test_Postcode`, Logic Composite | 1: `country` = DE; 2: `postcode` **Contains Regex** `^[0-9]{5}$`; 3: `country` = RO; 4: `postcode` **Contains Regex** `^[0-9]{6}$`. Expression: `(1 AND 2) OR (3 AND 4)` | **144** | 2: DE-0090, RO-0040 → *PLZ-Format falsch* |

⚠️ If **Repair Overflow** is on, FME silently turns 2021-02-30 into 2021-03-02. Turning it off is a deliberate data-quality decision.

---

## 11. Label every reject

After **each** reject port, add an **AttributeCreator** with two attributes:

| Rule | `rule` | `reject_reason` |
|---|---|---|
| UnjoinedLeft | R1 | Standort ohne Geschäftsdaten (keine Zeile in store_attributes.csv) |
| UnjoinedRight | R2 | Geschäftsdaten ohne Standort (keine Geometrie in den Standortdateien) |
| Matched | R3 | Doppelte Filial-ID – Datensatz nicht eindeutig |
| Null geometry | R4 | Geometrie fehlt |
| BBox Failed | R5 | Koordinaten außerhalb des Landes (vertauscht, 0/0 oder falsches Koordinatensystem) |
| Mandatory Failed | R6 | Pflichtfeld fehlt (Name, PLZ, Status, Eröffnungsdatum oder Verkaufsfläche) |
| 10a–10d | R7 | (the reason from the table in step 10) |

Tip: build one AttributeCreator, then copy and paste it and change the values.
Use **Bookmarks** to group each rule, and **Annotations** to document why the rule exists.
Interviewers notice tidy workspaces.

---

## 12. Writers

| Writer | Input | Settings |
|---|---|---|
| **OGC GeoPackage** `output/stores_valid.gpkg`, feature type `stores_valid` | Valid stream after 10d → **AttributeManager**: rename `_x`→`lon`, `_y`→`lat`; remove `source` if you don't want it | Coordinate system `LL84`. Keep `postcode` as **text**, not integer (or Bucharest postcodes lose their leading 0). |
| **CSV** `output/stores_rejected.csv` | All 7 reject AttributeCreators | Attributes: `store_id`, `rule`, `reject_reason`, `source`. Encoding UTF-8. |
| **CSV** `output/quality_summary.csv` | See step 13 | — |

---

## 13. Quality summary

1. Valid stream (after 10d) → also into an **AttributeCreator**: `rule` = `OK`, `reject_reason` = `gültig`.
2. Connect that **plus** all reject AttributeCreators into an **Aggregator**:
   Group By `rule`, `reject_reason`; **Count Attribute** = `count`; mode *Attributes Only* (if your version offers it).
3. Aggregator → CSV writer `quality_summary.csv`.

✅ Expected summary: **OK 144 · R1 2 · R2 3 · R3 2 · R4 1 · R5 4 · R6 3 · R7 5** (1 status, 1 sales area, 1 date, 2 postcodes).
Total **164** records, **87.8 % valid**.

---

## 14. Verify and export (last 20 min, no exceptions)

1. Run the full workspace. Compare the feature counts on every port with this guide.
   If a count is off, use feature caching to see which IDs went where, and compare with
   `docs/known_errors.md`.
2. Open `stores_valid.gpkg` in Visual Preview → take a **map screenshot**.
3. Take a **workspace screenshot** (whole canvas, readable).
4. Save the `.fmw`, the 3 outputs and the 2 screenshots → upload them to GitHub or email them to yourself.
   **The VM is deleted when your lab time ends.**

---

## Optional stretch goals (only if time is left)

- **Published parameters** for input/output paths, so someone else can rerun the workspace on new data.
- **Point-in-polygon country check** (PointOnAreaOverlayer) instead of the bounding box.
- **Writing to PostGIS** instead of, or in addition to, GeoPackage.
- **Collect all failed rules per record** instead of only the first one (e.g. AttributeValidator, which outputs validation messages).
