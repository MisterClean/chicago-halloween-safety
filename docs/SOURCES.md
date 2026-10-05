# The public records

Every source is downloaded directly from the City of Chicago Data Portal. You do not need credentials.

| Source | What is fetched | Why it is needed |
| --- | --- | --- |
| [Traffic Crashes — Crashes](https://data.cityofchicago.org/Transportation/Traffic-Crashes-Crashes/85ca-t3if/about) | Entire unfiltered CSV | Crash dates, locations and overall injury totals |
| [Traffic Crashes — People](https://data.cityofchicago.org/Transportation/Traffic-Crashes-People/u6pd-qa9d/about) | Entire unfiltered CSV | Pedestrian, child and bicycle outcomes |
| [Modern transportation permits](https://data.cityofchicago.org/Transportation/Transportation-Department-Permits/pubx-yq2d/about) | All `worktype='BlockParty'` rows | Historical and future applications |
| [Current/future block party permits](https://data.cityofchicago.org/Transportation/Transportation-Department-Permits-Block-Party-Curr/9zhy-9n5f/about) | Entire CSV | Current records take precedence over parent-archive duplicates |
| [Legacy transportation permits](https://data.cityofchicago.org/Transportation/Transportation-Department-Permits/hwmb-iu8j/about) | All `permit_type_code='BLKPARTY'` rows | Separate 2011–2015 archive summary |
| [2003 ward boundaries](https://data.cityofchicago.org/Facilities-Geographic-Boundaries/Boundaries-Wards-2003-2015/awaf-s7ux/about) | GeoJSON | Historical permit geography |
| [2015 ward boundaries](https://data.cityofchicago.org/Facilities-Geographic-Boundaries/Boundaries-Wards-2015-2023/k9yb-bpqx/about) | GeoJSON | Geography before the 2023 remap |
| [2023 ward boundaries](https://data.cityofchicago.org/Facilities-Geographic-Boundaries/Boundaries-Wards-2023-/p293-wvbd/about) | GeoJSON | Geography after the 2023 remap |

Boundary effective dates follow [CMAP's ward history](https://cmap-repos.github.io/cmapgeo/reference/ward_sf.html). The spatial join uses the official polygons rather than the portal's automatically assigned geographic-region IDs.

## What is saved locally

`fetch.py` writes sources under `.cache/halloween/`. Each has a receipt with its dataset ID, retrieval URL, UTC retrieval time, byte count and SHA-256 fingerprint. The source's metadata response includes the column definitions and table description. `sources.json` combines the receipts.

The two large crash exports use the portal's full CSV download endpoint. Block party archive queries allow up to 1,000,000 rows; the fetcher verifies that the result matches an independent source count rather than accepting a capped export. Ward requests allow 100 features, enough for the 50 numbered wards and the 2003 file's extra non-ward polygons. The analysis verifies 50 numbered wards in every generation.

Cached downloads are fingerprint-checked before reuse. To accept newer upstream records, run `pipeline.py fetch --refresh`, then a full `pipeline.py build`. A failed or interrupted fetch does not replace a previously complete data file. The city may update records during a download, so this is a collection of dated exports rather than a transactional database snapshot.

## Reading the generated files

| File | Contents |
| --- | --- |
| `analysis.json` | Chart counts, annual comparisons, estimates, audit and source receipts |
| `daily.csv` | One row per city day in 2018–2025 |
| `ward-day.csv` | One row per ward and day, including permit exposure and boundary era |
| `permit-archive.json` | Legacy and modern application/location counts, separately labeled |
| `wards-2003.geojson`, `wards-2015.geojson`, `wards-2023.geojson` | Simplified ward maps for display |
| `permits-2026.geojson` | Selected public locations for the Halloween-weekend planning view |
| `audit.json` | Source and matching checks for your run |

These files are created by your build and ignored by Git. No source records, prepared data files, production map keys or hosting credentials are distributed in this repository.
