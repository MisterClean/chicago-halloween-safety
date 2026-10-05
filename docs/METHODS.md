# How the analysis works

The study was prepared on October 5, 2026. It keeps the 2018–2025 comparison period fixed when you rebuild it; download receipts identify the records actually used in your run.

## What is counted

Crashes are distinct `CRASH_RECORD_ID` records. Overall injury and death totals come from the Crashes table. The People table identifies outcomes for pedestrians, children walking and people bicycling. People are grouped by crash ID before being joined, avoiding repeated crash totals when several people are involved.

An injured person includes the source classifications fatal, incapacitating, non-incapacitating, and reported but not evident. “Serious” means the police classification of incapacitating injury. Fatalities count people reported killed, not crashes involving a death. These are police-reported outcomes rather than independent medical follow-up.

Children have recorded ages 0–17. Missing or implausible pedestrian ages are audited, and a sensitivity calculation considers unclassified ages. Missing ages are not silently assigned to children. Unmatched people and crashes without People records are also reported in the audit. Person-specific counts should be read with those coverage limitations in mind.

Dates are Chicago local civil dates. The evening view covers 4 p.m. through 9:59 p.m. Counts describe reported harm, not risk per trip or pedestrian: those exposure denominators are unavailable.

## Coverage and calendar comparisons

The portal describes citywide CPD coverage from September 2017. The principal study uses complete 2018–2025 years, so every plotted calendar date has the same coverage. The calendar plot excludes February 29. Its ranks count how many dates have a larger total and report ties.

Halloween 2017 is a supplemental comparison. Earlier records are displayed separately because incomplete coverage prevents a citywide interpretation. Ongoing 2026 outcomes are excluded. Some highways, ramps and boundary roads handled by other agencies may be absent.

For each Halloween, the comparison dates are the same weekday ±7, 14, 21 and 28 days. Thanksgiving is excluded. Thursday-Halloween years therefore have seven comparison dates; other years have eight. The overall ratio divides the sum of Halloween counts by the sum of the annual matched-day averages. Each year contributes one Halloween and one average day.

The hourly chart sums the eight Halloweens rather than comparing them with hourly control counts.

## Variation across years

The calculation resamples paired years 20,000 times for a percentile interval around the count ratio. Each Halloween stays paired with its own comparison average. Intervals are suppressed when either total is below five. Sparse death counts cannot be taken as proof of no risk.

Sensitivity calculations exclude 2020, use a three-week comparison window, and omit one year at a time. A 50,000-draw calendar-placebo calculation assigns one event date within each year's Halloween-and-controls block. This assumes exchangeability among nearby calendar dates for a diagnostic test; it is not a randomized experiment. Measures are exploratory and no multiple-comparison adjustment is applied.

The random seed is fixed at `20261005`. The same input files and dependency versions produce the same resampling draws.

## Ward boundaries and permit eligibility

Original city geometry is used for spatial assignment; the displayed geometry is simplified afterward. Boundary generations switch on May 18, 2015 and May 15, 2023. The 2003 file's non-ward “OUT” polygons are excluded. A point shared by multiple numbered wards goes to the lowest numbered ward. Ward numbers do not describe constant geography across a remap.

Crash coordinates and permit address-range start points are assigned by spatial containment. Missing, invalid or outside points stay in city totals but do not contribute to ward results. An address range is not a measured street-closure segment; one application with locations in multiple wards can contribute to each ward.

Current permit records take precedence when a location key also appears in the modern parent archive. Eligible full-closure permits must be BlockParty applications, have an issue date and Complete milestone, specify Full street closure, have a start date in 2013–2026, and last less than three days with a nonnegative duration. Issue dates must be no later than the event's first calendar day. Distinct applications are counted once per ward and calendar date.

Legacy and modern permit archives overlap in converted 2013–2015 records. Their archive summaries stay separate; the legacy source does not enter the 2018–2025 permit model. The 2026 planning view shows applications overlapping October 30–November 1, including approval status. The map and historical exposure use eligible full closures rather than treating every application as an approved event.

## The block party comparison

The reproducible calculation includes all 50 wards and all May–October dates in 2018–2025, including zero-event dates. A linear count model estimates the association per additional eligible permit in a ward-day. It absorbs ward-era × year × weekday effects and exact-date effects using alternating projections. Date effects account for factors shared across the city on that date; ward patterns do not remove event-specific neighborhood selection.

Uncertainty uses a two-way cluster covariance by ward number and date. Correlation in the same numbered ward is allowed across the remap. Absorbed fixed-effect rank uses a conservative upper bound; the t reference uses the smaller cluster count minus one degrees of freedom.

A supplemental Halloween-only calculation compares Halloween-minus-matched-day means for injuries and permits across 400 ward-year observations. It includes ward-era and year effects, ward/year clustering, and a t reference with seven degrees of freedom.

Checks include a seven-day future-permit lead, one-day lag, exclusion of 2020 and separate boundary-era estimates. A future-permit association can indicate selection or remaining structure. A null result does not prove that selection has been resolved. A lag check cannot establish where traffic was displaced.

These are observational associations. There is no random or plausibly external assignment of street closures, reliable attendance measure, traffic/walking exposure measure, or verified counterfactual. Benefits on one block and displacement on neighboring streets can disappear inside a ward-wide total. Neither model identifies a causal effect or a Halloween-specific benefit on the closed street. Their estimates remain in the downloadable results for inspection; the page withholds the model section.

## Checks you can rerun

`pipeline.py check` verifies downloaded fingerprints and independently reads the source CSVs to reconcile Halloween crash totals and child pedestrian injuries. It also checks complete day/ward coverage, duplicate keys, geographic/subset totals, all 400 ward comparisons, holiday exclusions, correct boundary eras, future-map reconciliation and permitted public output fields.

For a bounded real panel slice, it compares the absorbed fixed-effect estimate with an independently fitted explicit-dummy model. This checks the implementation, not the causal assumptions. Checks fail rather than silently accepting amended or corrupted cached files.

The raw downloads may contain personal or contact fields. They stay in the ignored local cache and are not copied into the web export. Only the selected public application location fields and aggregated crash outcomes are published by the build.
