# Methodology

## 1. What accessibility means here

In this project, accessibility means the share of opportunities that can be reached from a starting location within a fixed travel-time budget.

For a given origin:

```text
accessibility (%) =
reachable opportunities / total opportunities Ã— 100
```

The calculation is repeated for 15, 30, 45 and 60 minutes.

This is different from measuring straight-line distance.

## 2. Building the road network

The Bengaluru road network comes from OpenStreetMap.

Where a usable `maxspeed` value is available, it is used as the starting speed.

Where it is not available, a fallback speed is assigned from the road class.

The resulting edge travel time is:

```text
travel time = road length / assumed speed
```

This produces the baseline network.

## 3. Time-of-day calibration

The baseline network represents a simplified travel condition.

To introduce time-of-day variation, the project uses traffic observations from 20 Bengaluru hotspots.

The scenarios are:

- 07:00
- 09:00
- 13:00
- 18:00
- 22:00

The observed hotspot speeds are compared with the local baseline road speeds.

The effect is then spread to nearby road-network segments using inverse-distance weighting.

The resulting multiplier is applied to baseline travel time.

Conceptually:

```text
calibrated travel time
=
baseline travel time / speed multiplier
```

A lower multiplier therefore represents slower travel.

The spatial calibration is an estimate. The traffic reference data does not provide measured travel time for every road segment.

## 4. Opportunity data

### Health

Health opportunities come from OpenStreetMap features tagged as:

- hospital
- clinic
- doctors

### Education

Education opportunities come from:

- school
- college
- university

### Employment

Employment comes from advertised Adzuna job postings.

The employment dataset requires extra caution. There were 305 usable postings after cleaning, but many postings shared coordinates. Only 16 distinct coordinate locations remained.

Therefore employment is treated as a job-opportunity signal rather than a complete workplace map.

## 5. Shortest-path calculation

For each sampled origin, the project calculates travel times through the road network.

Only opportunities reachable within the selected threshold are counted.

This is repeated for the different time-of-day networks, opportunity categories and travel-time budgets.

## 6. Accessibility curves

The accessibility curve is the central analytical object.

It shows:

```text
travel-time budget â†’ accessible opportunity share
```

For example:

```text
15 min â†’ 22%
30 min â†’ 76%
45 min â†’ 99%
60 min â†’ 99%
```

The shape of the curve tells us how quickly accessibility improves as more travel time becomes available.

## 7. Peak-hour comparison

The project compares accessibility between midday and 6 PM.

Peak-hour loss is:

```text
midday accessibility - peak accessibility
```

A larger positive value means that the location loses more accessible opportunity during the modeled peak scenario.

## 8. Finding low-access locations

The combined life-access surface uses health and education accessibility at the 30-minute midday scenario.

Locations are ranked by their combined accessibility.

This identifies places where access to important opportunities is relatively poor even before considering the additional effect of peak-hour congestion.

## 9. Intervention experiment

The intervention analysis is deliberately a counterfactual experiment.

The process is:

1. Select the lowest-access candidate origins.
2. Find nearby health and education destinations.
3. Trace shortest paths from each candidate origin.
4. Count how frequently physical road segments appear across those paths.
5. Select up to 50 high-frequency physical road segments.
6. Model a 20% travel-time improvement on those segments.
7. Recalculate accessibility.
8. Compare the result with the baseline.

The purpose is to ask:

> Under this modeled scenario, which candidate corridor produces the largest accessibility improvement?

It is not a formal transportation optimization model and should not be interpreted as a construction recommendation.

## 10. Validation

The final accessibility calculations were checked for monotonicity.

A location should not lose opportunities when its travel-time budget increases from 15 to 30 to 45 to 60 minutes.

The final spatial accessibility run reported zero monotonicity failures.

The intervention geometry was also checked for connectivity and corridor length.

For the winning candidate, 98% of the selected physical intervention segments formed the largest connected component.

## 11. Important assumptions

The results depend on assumptions about:

- road speeds
- missing OSM speed values
- traffic calibration
- spatial influence of traffic hotspots
- opportunity completeness
- sampled origins
- shortest-path routing
- the 20% intervention improvement

The numbers should therefore be read as modeled estimates, not exact measurements of every person's journey.
