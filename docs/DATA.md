# Data

## Sources

| Source | Used for | Notes |
|---|---|---|
| OpenStreetMap | Road network | Used to build the Bengaluru routing graph |
| OpenStreetMap | Health | Hospitals, clinics and doctors |
| OpenStreetMap | Education | Schools, colleges and universities |
| Adzuna API | Employment | Advertised Bengaluru job opportunities |
| Bengaluru traffic reference dataset | Traffic calibration | 20 traffic hotspots and time-of-day observations |

## Road network

The final Bengaluru road graph contains:

- 155,776 nodes
- 394,403 directed edges

Important road attributes include:

- road class
- length
- one-way status
- lanes where available
- maximum speed where available
- modeled speed
- modeled travel time

## Health

The downloaded health opportunity data contains:

- 2,174 cleaned records
- 1,952 unique network nodes after attachment

The category includes hospitals, clinics and doctors.

## Education

The downloaded education opportunity data contains:

- 2,008 cleaned records
- 1,842 unique network nodes after attachment

The category includes schools, colleges and universities.

## Employment

The final employment file contains:

- 305 unique usable postings
- 16 distinct coordinate locations

The low number of distinct coordinate locations is important.

Multiple advertised jobs can point to the same location, so the employment layer should not be read as a complete map of physical workplaces.

## Traffic reference

The traffic reference dataset contains observations from 20 Bengaluru hotspots.

The project uses these observations to create relative time-of-day adjustments for:

- 7 AM
- 9 AM
- 1 PM
- 6 PM
- 10 PM

The traffic data is used for calibration, not as a claim that every road segment was directly measured.

## Processed accessibility data

The final spatial accessibility table contains:

- origin ID
- latitude
- longitude
- hour
- category
- travel-time threshold
- accessible opportunity count
- total opportunities
- accessibility percentage

The final analysis contains 649 sampled origins across five time scenarios, three opportunity categories and four travel-time thresholds.

## Generated files

Large network files and generated datasets are intentionally excluded from the Git repository.

The source scripts under `src/` show how the main analytical outputs were generated.

This keeps the repository manageable while preserving the logic used to build the analysis.

## Data limitations

No dataset here should be interpreted as a complete census of Bengaluru.

OpenStreetMap coverage can vary.

Job postings represent advertised opportunities rather than every available job.

Traffic observations are concentrated at selected hotspots.

The origin sample represents a set of locations rather than every address in the city.
