# Known (deliberately injected) data errors

Answer key for verifying the workspace output. All errors were injected by
`tools/generate_data.py`. Each record is rejected with the **first** rule it fails,
in pipeline order R1 → R7.

| ID | Store | Source | Injected error | Expected rule |
|---|---|---|---|---|
| E01 | DE-0097 | store_attributes.csv | Attribute row removed: location has no business data | R1 |
| E02 | RO-0058 | store_attributes.csv | Attribute row removed: location has no business data | R1 |
| E11 | DE-0101 | store_attributes.csv | Attribute row with no location | R2 |
| E12 | DE-0102 | store_attributes.csv | Attribute row with no location | R2 |
| E13 | RO-0061 | store_attributes.csv | Attribute row with no location | R2 |
| E03 | DE-0042 (×2) | stores_de.geojson | Second location with the same ID ("Filiale Hannover Messe"). Both records are rejected. | R3 |
| E04 | DE-0013 | stores_de.geojson | `geometry: null` | R4 |
| E05 | DE-0021 | stores_de.geojson | Coordinates (0, 0) | R5 |
| E06 | DE-0034 | stores_de.geojson | Lon/lat swapped | R5 |
| E07 | DE-0055 | stores_de.geojson | Lon/lat swapped | R5 |
| E08 | RO-0017 | stores_ro.csv | Wrong CRS: lon/lat degrees written into the Stereo 70 x/y columns | R5 |
| E09 | DE-0008 | stores_de.geojson | Store name empty | R6 |
| E10 | DE-0066 | stores_de.geojson | Postcode empty | R6 |
| E14 | RO-0025 | store_attributes.csv | Status empty | R6 |
| E15 | DE-0071 | store_attributes.csv | Status `unknown` (not in domain) | R7 |
| E18 | DE-0080 | store_attributes.csv | Sales area `0` | R7 |
| E19 | RO-0033 | store_attributes.csv | Opening date `2021-02-30` (impossible date) | R7 |
| E16 | DE-0090 | stores_de.geojson | 4-digit postcode | R7 |
| E17 | RO-0040 | stores_ro.csv | 5-digit postcode (Romania needs 6) | R7 |

## Standardisation cases (must end up VALID)

| Store | Raw status | After AttributeTrimmer + StringCaseChanger |
|---|---|---|
| DE-0003 | `OPEN` | `open` |
| DE-0019 | `␣Open␣` | `open` |
| RO-0005 | `Open` | `open` |
| RO-0012 | `CLOSED␣` | `closed` |

Also check: Bucharest postcodes (starting with `0`) and Leipzig/Dresden postcodes
(`04…`, `01…`) must keep their leading zero.

## Expected totals

| | Count |
|---|---|
| Records in total (161 locations + 3 attribute-only rows) | 164 |
| Valid | **144** (87.8 %) |
| Rejected | **20** |
