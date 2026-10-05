# How Far Away Is Your Life?

### A travel-time view of opportunity in Bengaluru

Two places can be only a few kilometres apart and still feel like completely different cities.

I built **How Far Away Is Your Life?** to explore that idea in Bengaluru.

Instead of asking how close a hospital, school or job is in a straight line, the project asks a more useful question:

> **How much opportunity can you actually reach within a given amount of travel time?**

The system models Bengaluru as a road network, adjusts travel times for different parts of the day, and measures how many health, education and job opportunities can be reached from different locations within **15, 30, 45 and 60 minutes**.

The result is an interactive way to explore accessibility, inequality and the places where travel time matters most.

---

## What I wanted to understand

Most maps make distance look simple.

A place is either 5 km away or 10 km away.

But cities don't work like that.

A five-kilometre trip can be easy at one time of day and painful at another. Two neighbourhoods can have similar geographic distances to important services but very different access to them.

So I focused on three questions:

1. **How much of Bengaluru's opportunity can different locations reach within 15, 30, 45 and 60 minutes?**
2. **How much does that accessibility change during the day?**
3. **If we could improve a small set of road segments, where would that improvement have the largest modeled effect?**

The project starts with Bengaluru rather than trying to make a generic global accessibility system.

---

## The core idea

For each sampled location, I calculate how many opportunities can be reached within a travel-time budget.

For example:

```text
Starting place
      ↓
Road network
      ↓
Travel-time calculation
      ↓
15 / 30 / 45 / 60 minute reach
      ↓
Accessible opportunities
      ↓
Accessibility percentage
```

This creates what I call an **Accessibility Curve**.

The curve shows how access grows as a person's travel-time budget increases.

A location might have:

```text
15 min  →  22%
30 min  →  76%
45 min  →  99%
60 min  →  99%
```

That tells a much richer story than simply saying that a hospital is "nearby."

---

## What the project measures

### Health

Hospitals, clinics and doctors mapped from OpenStreetMap.

### Education

Schools, colleges and universities mapped from OpenStreetMap.

### Employment

Job opportunities collected from the Adzuna jobs API.

Employment is treated as a **job-opportunity signal**, not as a complete map of where people actually work.

The employment dataset contains 305 usable postings, but many postings share the same coordinates. After deduplication there are only 16 distinct coordinate locations. Because of this, I treat employment results more cautiously than the health and education results.

---

# The data

The main inputs are:

- **OpenStreetMap** — Bengaluru road network and health/education locations
- **Adzuna API** — Bengaluru job postings
- **Bengaluru traffic reference data** — used to calibrate the travel-time model across different times of day

The road network contains:

- **155,776 nodes**
- **394,403 directed road connections**

The final accessibility analysis uses **649 sampled origins** across Bengaluru.

---

# How the travel-time model works

The first version of the road network used OpenStreetMap speed information where it was available.

For roads without a usable speed value, I assigned a fallback speed based on the road class.

For example, residential roads receive a lower baseline speed than primary or motorway roads.

That gives a baseline travel-time network.

But free-flow travel time alone is not enough for a project about Bengaluru.

So I added a second layer.

## Time-of-day calibration

I used traffic observations from Bengaluru hotspots to estimate how much travel time should change at:

- 7 AM
- 9 AM
- 1 PM
- 6 PM
- 10 PM

The calibration is spatial as well as temporal.

Traffic observations from 20 hotspots are mapped onto the road network using nearby network locations and distance-weighted influence.

The resulting model changes the travel time of individual road segments rather than simply applying one city-wide multiplier.

This produced:

- **1,972,015 calibrated edge rows**
- 20 traffic hotspots
- 5 time-of-day scenarios

The model is an estimate based on hotspot observations. It is **not** GPS-level measured travel time for every road in Bengaluru.

---

# What I found

The numbers below are from the final modeled dataset.

At **1 PM with a 30-minute travel budget**, the average share of opportunities accessible from the sampled locations was:

| Opportunity | Average accessible within 30 min |
|---|---:|
| Education | **76.07%** |
| Health | **79.90%** |
| Employment | **95.46%** |

For health and education together, the average 30-minute accessibility was:

**77.98%**

But the average hides a large amount of variation.

The middle 80% of sampled locations ranged from roughly:

**57.77% → 96.96%**

of health and education opportunities accessible within 30 minutes.

That difference is the reason I built the project.

---

# Travel time changes the picture

At 1 PM, the average accessibility increased substantially when the travel-time budget increased:

| Travel budget | Education | Health |
|---|---:|---:|
| 15 min | 22.51% | 24.63% |
| 30 min | 76.07% | 79.90% |
| 45 min | 98.68% | 99.27% |
| 60 min | 99.39% | 99.60% |

The important part is not simply that accessibility eventually becomes high.

It is **how much time someone needs before that happens**.

For some locations, 30 minutes is enough to reach most of the city's opportunities.

For others, even 30 minutes leaves a large gap.

---

# Peak hours matter

The model also compares midday with the 6 PM scenario.

At the 30-minute budget, the average accessibility loss during the peak scenario was approximately:

- **Education:** 3.59 percentage points
- **Health:** 3.52 percentage points
- **Employment:** 1.68 percentage points

The effect is not uniform across Bengaluru.

Some locations lose much more accessibility than the city-wide average.

The largest modeled health loss at the 30-minute budget was about **13.16 percentage points**.

That makes congestion more than a traffic problem.

It can also become an **access problem**.

---

# Finding places that are difficult to reach

The analysis identifies locations with very low access to health and education within 30 minutes.

Some of the lowest-access sampled locations had combined accessibility of almost zero.

Other locations had considerably higher access but were especially sensitive to peak-hour travel.

This creates two different kinds of problems:

### Low accessibility

A location starts with poor access even when traffic conditions are relatively good.

### Fragile accessibility

A location has reasonable access normally, but loses a large amount of it when travel times increase.

Those are not necessarily the same places.

---

# The intervention experiment

I also wanted to move beyond:

> "Here is a problem."

and ask:

> **"Where could a small intervention make the biggest difference?"**

For the 10 lowest-access candidate origins, I traced routes toward nearby health and education opportunities.

I then ranked physical road segments by how often they appeared across those routes.

For each candidate, I modeled a counterfactual where up to **50 physical road segments** received a **20% travel-time improvement**.

The strongest candidate in the experiment was **Origin 394**.

Under that particular modeled scenario:

- Total accessibility gain: **24.17 percentage points**
- Gain for the disadvantaged candidate group: **18.56 percentage points**
- Other sampled origins affected: **88**
- Intervention budget: **50 physical road segments**
- Travel-time improvement: **20%**
- Scenario: **1 PM, 30-minute budget**

This is a **counterfactual experiment**, not a claim that these exact roads should actually be rebuilt.

The intervention is a heuristic based on repeated shortest-path usage. It is useful for asking "what if?" but it is not a formal transportation infrastructure optimization model.

---

# The interactive experience

The application is designed more like an interactive research piece than a conventional dashboard.

You can:

- Move around the Bengaluru map
- Zoom into an area
- Click a location to investigate it
- Change the travel-time budget
- Change the time of day
- Explore health, education and employment
- Follow the accessibility curve
- Compare different parts of Bengaluru
- Explore the intervention experiment
- Read the methodology and limitations

The main interaction is intentionally simple:

> **Drag to explore. Click to choose.**

---

# Project structure

```text
HOW-FAR-AWAY-IS-YOUR-LIFE/
│
├── app/
│   └── app.py
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── external/
│
├── src/
│   ├── accessibility/
│   │   ├── attach_opportunities.py
│   │   ├── calculate_accessibility.py
│   │   ├── calculate_spatial_accessibility.py
│   │   ├── calculate_time_accessibility.py
│   │   └── engine.py
│   │
│   ├── analysis/
│   │   ├── analyze_accessibility.py
│   │   ├── build_accessibility_curves.py
│   │   ├── build_accessibility_surface.py
│   │   ├── build_citywide_accessibility.py
│   │   ├── build_intervention_geometries.py
│   │   ├── build_research_findings.py
│   │   ├── citywide_research_analysis.py
│   │   ├── run_intervention_analysis.py
│   │   ├── spatial_research_analysis.py
│   │   └── validate_intervention_geometry.py
│   │
│   └── network/
│       ├── build_spatial_traffic_calibration.py
│       └── build_time_calibration.py
│
├── inspect_traffic_dataset.py
├── requirements.txt
└── README.md
```

The generated datasets and large network files are intentionally excluded from Git.

---

# Running the project locally

## 1. Clone the repository

```bash
git clone <your-repository-url>
cd HOW-FAR-AWAY-IS-YOUR-LIFE
```

## 2. Create the virtual environment

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

## 3. Install dependencies

```bash
pip install -r requirements.txt
```

## 4. Start the application

```bash
python -m streamlit run app\app.py
```

The application will normally be available at:

```text
http://localhost:8501
```

Some of the raw data used to generate the final results are not stored in the repository because of their size and/or external-source requirements. The data pipeline scripts in `src/` document how the analysis was built.

---

# Limitations

This project is a model of accessibility, not a perfect representation of real travel.

A few limitations matter:

### Travel times are estimated

The road network starts with OpenStreetMap speeds and is calibrated using traffic observations from selected hotspots. It does not contain real-time GPS travel times for every road.

### Traffic observations are sparse

The traffic reference data covers 20 hotspots rather than every road in Bengaluru. Spatial calibration therefore estimates how congestion may influence nearby roads.

### Employment data is incomplete

The job-posting dataset is a sample of advertised opportunities, not a census of all jobs in Bengaluru. Many postings also share the same coordinates.

### The origin sample is not every possible address

The analysis uses 649 sampled locations rather than every building or resident.

### The intervention is counterfactual

The road-segment experiment asks what would happen under a modeled travel-time improvement. It does not prove that a real construction project would produce the same result.

These limitations are part of the project rather than something to hide. The goal is to build a useful analytical model while being clear about where that model stops.

---

# What I learned

The biggest lesson from this project was that **distance is a poor substitute for accessibility**.

A map can make two places look close.

A travel-time network can show that they are not equally close in practice.

Building this also forced me to deal with problems that don't appear in a clean dataset:

- incomplete speed information
- disconnected or duplicated opportunity data
- spatial matching
- calibration
- computationally expensive shortest-path calculations
- choosing reasonable assumptions
- validating monotonicity
- interpreting uncertainty
- separating measured data from modeled results
- designing an interface that makes the analysis understandable

That was the part of the project I found most valuable.

---

# Future work

If I continue this project, I would like to explore:

- Public-transit accessibility
- Walking and cycling accessibility
- Population-weighted accessibility
- More detailed traffic observations
- Better employment coverage
- Multiple intervention budgets
- Formal network optimization
- Accessibility changes over longer time periods
- More detailed demographic and socioeconomic analysis

The current version intentionally focuses on getting the core travel-time accessibility model right before expanding into those areas.

---

## A note on the project

This project is a personal exploration of how travel time changes our understanding of a city.

It is not intended to be an official transportation study of Bengaluru.

The goal is simpler:

**to make accessibility visible.**
