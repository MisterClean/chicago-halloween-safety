# Chicago Halloween traffic safety

What happens on Chicago’s streets on Halloween? This project looks at reported crashes, injuries and block party permits, with a page you can explore and scripts you can run yourself.

**[Explore the published analysis](https://michaelmclean.me/chicago-halloween-safety)** · [How the comparisons work](docs/METHODS.md) · [Where the data comes from](docs/SOURCES.md)

## What you can explore

- **Halloween in context.** Compare October 31 with every other calendar date and with nearby days that fall on the same weekday.
- **Eight years, one at a time.** See crashes, injuries, serious injuries, deaths and harm to people walking, including children.
- **Your ward.** Explore a map, sort the tables and follow each measure’s yearly bar chart. Ward assignments use the boundaries in place at the time.
- **Car-free celebrations.** See full-closure block party permits alongside reported harm, including a separate planning view for Halloween 2026.
- **The evidence behind the page.** Rebuild the tables, download the results and inspect the checks that keep the counts honest.

## Run it yourself

Install [Git](https://git-scm.com/downloads) and [uv](https://docs.astral.sh/uv/getting-started/installation/), then run:

```bash
git clone https://github.com/MisterClean/chicago-halloween-safety.git
cd chicago-halloween-safety
uv run --locked python pipeline.py
uv run --locked python pipeline.py serve
```

Open **http://127.0.0.1:8766/** when the last command is running.

The first command downloads the city’s records, builds the analysis, checks the results and prepares the page. `uv` supplies Python 3.12 and the project’s fixed set of dependencies. You also need `curl`, which is included with recent macOS and Windows versions and is available through Linux package managers.

The crash and people downloads together are about **1.4 GB**. Allow several GB of free disk space for the downloads, working database and results. The first run takes longer than later ones. A small DuckDB map extension is downloaded on the first build; no Chicago data account or API key is required.

Street tiles are optional. The charts, tables and ward outlines work without a map key. To add a street basemap, copy `apps/web/public/config.example.js` to `config.local.js` in the same folder and add your own [Protomaps key](https://protomaps.com/api). Your local configuration is ignored by Git. Map keys used in a browser are visible to visitors; restrict yours to the domains you use.

## Why compare nearby weekdays?

A Friday in late October is a different kind of day from a Tuesday in January. Comparing Halloween with an average of every day in the year can mix the holiday with season and weekday patterns.

For each year, this project compares Halloween with the same weekday one, two, three and four weeks before and after it. Thanksgiving is left out. The calendar chart answers a different question: how much reported harm appears on each date across the same eight years?

The main study covers **2018–2025**, the complete years of citywide reporting available when the analysis was prepared. Earlier coverage is shown separately. The 2026 permit view is a planning snapshot; it is not a comparison with 2026 Halloween crash outcomes.

## What can we conclude?

The published October 5, 2026 analysis found 18 reported injuries to children walking across eight Halloweens, compared with 11.4 when the nearby weekday averages are added together. Halloween was higher in five of the eight years. That pattern is worth examining, but eight days provide limited evidence: the uncertainty range includes no increase.

These are reported counts. We do not know how many people were walking or driving, so the results cannot tell us how much an individual’s risk changed. Deaths are too rare in this sample to call Halloween Chicago’s deadliest day.

Block party permits let us look for a relationship between street closures and harm. They do not tell us whether a closure happened as planned, how many people attended, or what would have happened without it. A whole ward is also much larger than a closed block. The analysis code retains these comparisons for inspection; the page does not present them as a proven safety effect. See [the methods](docs/METHODS.md) for the assumptions and checks.

## How the rebuild works

1. **Get the public records.** Fetch the entire Crashes and People CSVs, historical and current block party permits, and three generations of ward boundaries from Chicago’s Data Portal.
2. **Put the records together carefully.** Match people to crashes, count injuries once, and locate crashes and permits in the ward boundaries valid on their dates.
3. **Make the comparisons.** Build city and ward tables, yearly Halloween comparisons, and the calendar and hourly charts.
4. **Check and show the results.** Check source file fingerprints, source totals, coverage, ward assignments and the statistical calculations, then prepare the interactive page.

Downloads and generated results stay on your computer. This repository contains the instructions and code; it does not contain source records or prepared data files. The local page uses your rebuilt results and does not depend on the published site’s data host.

Chicago can revise its records. Fetching today’s exports recreates the methods and study period, but may not reproduce the published numbers exactly. Every download gets a dated receipt and file fingerprint, and those receipts travel with your results. The changing current-permit view is particularly sensitive to the retrieval date.

## Useful commands

| What you want to do | Command |
| --- | --- |
| Get fresh city exports | `uv run --locked python pipeline.py fetch --refresh` |
| Rebuild from your existing downloads | `uv run --locked python pipeline.py build` |
| Recalculate using the prepared database | `uv run --locked python pipeline.py build --reuse` |
| Check the results again | `uv run --locked python pipeline.py check` |
| Prepare a folder for your own web host | `uv run --locked python pipeline.py export` |

Rebuilding from downloads still needs an installed Python environment and DuckDB map extension. Use `--reuse` only when the downloaded sources and preparation code have not changed. Fresh downloads should be followed by a full `build`.

Results are written to `packages/data/processed/`: the daily CSV, ward-day CSV, chart results, permit archive summary, three ward maps and the 2026 permit map. The local page lives in `apps/web/public/`; the export command creates `apps/web/dist/`. Both contain only aggregated crash results and selected public permit locations, never the raw People or contact records.

## Explore the project

- [`packages/data/scripts/`](packages/data/scripts/) — fetching, calculations, checks and the SQL that assigns wards.
- [`apps/web/public/`](apps/web/public/) — the interactive page and its styling.
- [`docs/METHODS.md`](docs/METHODS.md) — definitions, comparisons and limits.
- [`docs/SOURCES.md`](docs/SOURCES.md) — public source links and download details.
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — making a change and checking it.

## Credits and license

City records come from the [Chicago Data Portal](https://data.cityofchicago.org/). The project uses [DuckDB](https://duckdb.org/), Python’s scientific libraries, [MapLibre](https://maplibre.org/) and [Protomaps](https://protomaps.com/). Basemap contributors are credited in the map.

The layout follows the [Smart Streets pilot project](https://github.com/MisterClean/chicago-smart-streets-pilot), and the rebuild approach follows the [Divvy station analysis](https://github.com/MisterClean/divvy-station-analysis). The national child-pedestrian chart supplied as a visual reference informed the calendar layout; its estimates are not used in this Chicago study.

Code is available under the [MIT license](LICENSE). City data and basemap data have their own [terms and attribution requirements](DATA_LICENSE.md).
