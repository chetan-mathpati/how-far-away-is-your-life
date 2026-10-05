# Project Presentation

## One-line description

**A travel-time accessibility study of Bengaluru that measures how much health, education and job opportunity different locations can reach within 15, 30, 45 and 60 minutes.**

## Short project description

I built How Far Away Is Your Life? to understand how travel time changes access to opportunity across Bengaluru.

Instead of using straight-line distance, the project models the city's road network and estimates how many health, education and job opportunities can be reached within different travel-time budgets.

The analysis also looks at how accessibility changes during the day and runs a counterfactual experiment to see where a small improvement to selected road segments could have the largest modeled effect.

## The problem

A map can tell us that two places are close.

It cannot always tell us whether they are equally accessible.

The project turns that into a measurable question:

> How much opportunity can a person actually reach from where they are within a fixed amount of travel time?

## What makes the project interesting

The project combines:

- geospatial data
- road-network analysis
- shortest-path routing
- travel-time modeling
- time-of-day calibration
- accessibility measurement
- distributional analysis
- counterfactual intervention analysis
- interactive visualization

The main analytical object is the **Accessibility Curve**, which shows how reachable opportunity changes as a person's travel-time budget increases.

## Strongest numbers

- 155,776 road-network nodes
- 394,403 directed road connections
- 649 sampled origins
- 20 traffic hotspots used for spatial calibration
- 1,972,015 calibrated edge rows
- 1,952 health opportunity network nodes
- 1,842 education opportunity network nodes
- 305 usable employment postings
- 15 / 30 / 45 / 60 minute travel-time budgets
- 5 time-of-day scenarios

At 1 PM with a 30-minute budget:

- Education accessibility: **76.07%**
- Health accessibility: **79.90%**
- Employment accessibility: **95.46%**
- Combined health + education accessibility: **77.98%**

The average peak-hour loss for combined health + education accessibility at 30 minutes was about **3.56 percentage points**.

The strongest tested intervention scenario produced a modeled **24.17 percentage-point accessibility gain** under its specific assumptions.

## Resume bullets

### Data Science / Analytics

- Built a geospatial accessibility system for Bengaluru using a **155K-node, 394K-edge road network**, measuring reachable health, education and employment opportunities across **15–60 minute travel budgets**.
- Calibrated road travel times across **5 time-of-day scenarios** using observations from **20 traffic hotspots**, then used shortest-path analysis to quantify spatial and peak-hour accessibility differences across **649 sampled origins**.
- Developed an **Accessibility Curve** and counterfactual road-intervention analysis; the strongest tested scenario produced a **24.17 pp modeled accessibility gain** under a 20% travel-time improvement across up to 50 physical road segments.

### Data Analyst

- Built an interactive Bengaluru accessibility analysis that measures how much health, education and job opportunity can be reached within **15, 30, 45 and 60 minutes** instead of using straight-line distance.
- Processed a **155,776-node road network** and calibrated travel times across five daily scenarios using spatial traffic observations from 20 hotspots.
- Found that average 30-minute midday accessibility was **76.07% for education and 79.90% for health**, while peak-hour accessibility fell by an average of **3.56 percentage points** for combined health and education access.

## Portfolio description

### How Far Away Is Your Life?

What if distance is the wrong way to think about how accessible a city really is?

I built this project around Bengaluru to explore that question.

The system models the city's road network, adjusts travel times for different parts of the day, and measures how many health, education and job opportunities can actually be reached from different locations within 15, 30, 45 and 60 minutes.

The interesting part is not just the map.

The project produces accessibility curves, identifies locations with low or fragile access, compares midday with peak-hour conditions, and runs a counterfactual experiment to ask where a small travel-time improvement could have the largest modeled effect.

## Interview explanation

If someone asks **"Tell me about the project"**:

> I wanted to study urban accessibility from the perspective of travel time rather than geographic distance. I chose Bengaluru and built a road-network model using OpenStreetMap. I attached health, education and job opportunities to the network and calculated which opportunities could be reached from 649 sampled locations within 15, 30, 45 and 60 minutes.
>
> The interesting part was that a static road network wasn't enough, so I calibrated travel times for five times of day using traffic observations from 20 Bengaluru hotspots. That let me compare accessibility under different traffic conditions.
>
> I then built accessibility curves, looked for locations with low or fragile access, and ran a counterfactual experiment where selected road segments received a modeled 20% travel-time improvement.
>
> The project is really about turning a map into a decision-making question: not just "what is nearby?", but "what can I actually reach within the time I have?"

## If they ask "What was technically difficult?"

> The hardest part wasn't the dashboard. It was getting the network model to behave reasonably.
>
> The first free-flow version made 30-minute accessibility almost completely saturated across the city, which was a sign that the assumed speeds were too optimistic for the question I was asking.
>
> I therefore introduced spatial and time-of-day calibration using traffic hotspot observations. I also had to deal with missing road speeds, opportunity-to-network matching, large shortest-path calculations, and making sure accessibility stayed monotonic as the travel-time budget increased.
>
> That debugging process changed the project from a simple map into a more defensible analytical system.

## If they ask "What are the limitations?"

> The travel times are modeled estimates, not GPS measurements for every road. The traffic calibration is based on 20 hotspots, so it cannot represent every road equally well.
>
> The employment data is also incomplete. I had 305 usable job postings, but many shared coordinates, leaving only 16 distinct coordinate locations. So I treat employment as a job-opportunity signal rather than a complete workplace map.
>
> Finally, the intervention experiment is a counterfactual heuristic. It shows what happens under the modeled assumptions; it is not a real infrastructure recommendation.

## Words to avoid

Do not describe this project using:

- cutting-edge AI
- revolutionary
- next-generation
- intelligent city platform
- seamless experience
- powered by advanced AI
- robust AI-driven solution
- leverages state-of-the-art technology

Prefer:

- I built
- I modeled
- I measured
- I compared
- I estimated
- I tested
- I found
- under this scenario
- the model suggests
- one limitation is

## The central story

> **Two places can be geographically close and still be very different in accessibility.**

Everything else in the project supports that idea.

## Final positioning

Present this project as:

**a geospatial accessibility and decision-intelligence study**

rather than:

**a dashboard project**

The dashboard is the interface.

The actual project is the analytical system underneath it.
