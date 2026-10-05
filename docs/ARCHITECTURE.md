# Architecture

## The short version

How Far Away Is Your Life? is built as a small analytical pipeline rather than a single notebook.

```text
OpenStreetMap + Adzuna + traffic reference data
                    |
                    v
             Data preparation
                    |
                    v
              Road network
                    |
                    v
        Travel-time calibration
                    |
                    v
          Accessibility engine
                    |
          +---------+---------+
          |         |         |
          v         v         v
       Curves    Inequality  Intervention
          |         |         |
          +---------+---------+
                    |
                    v
              Streamlit app
```

The important idea is that the application is the last layer. The calculations happen before the UI and are saved as processed datasets.

## Main layers

### 1. Data

The project starts with three main sources:

- OpenStreetMap for the Bengaluru road network and health/education locations.
- Adzuna for advertised Bengaluru jobs.
- A Bengaluru traffic reference dataset for time-of-day calibration.

Raw and generated data are kept outside the Git commit where appropriate because some files are large or come from external sources.

### 2. Road network

The OSM road network is converted into a graph.

The final graph contains:

- 155,776 nodes
- 394,403 directed road connections

Each road connection has a baseline travel time.

### 3. Travel-time calibration

The baseline network is adjusted for five scenarios:

- 7 AM
- 9 AM
- 1 PM
- 6 PM
- 10 PM

The spatial calibration uses traffic observations from 20 hotspots and estimates their influence on nearby network segments.

This creates a time-aware network rather than using one city-wide congestion number.

### 4. Opportunity attachment

Health, education and employment locations are attached to nearby road-network nodes.

This allows shortest-path calculations to answer:

> Which opportunities can be reached from this starting location within a given amount of time?

### 5. Accessibility

The accessibility engine calculates reachable opportunities for:

- 15 minutes
- 30 minutes
- 45 minutes
- 60 minutes

The result is stored as both counts and percentages.

### 6. Research analysis

The analysis layer turns those calculations into:

- accessibility curves
- city-wide summaries
- low-access locations
- peak-hour losses
- temporally fragile locations
- intervention experiments
- intervention geometries

### 7. Application

`app/app.py` is the presentation layer.

It reads the processed analytical outputs and lets the user explore the results interactively.

The UI is intentionally separate from the heavy data-processing pipeline.

## Why it is structured this way

The separation makes the project easier to reason about.

If the UI changes, the analytical results do not need to be rebuilt.

If the calibration method changes, the Streamlit application can continue to use the resulting processed data.

It also makes the individual steps easier to test and explain.
