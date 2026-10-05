# Project Structure

```text
HOW-FAR-AWAY-IS-YOUR-LIFE/
â”‚
â”œâ”€â”€ app/
â”‚   â””â”€â”€ app.py
â”‚
â”œâ”€â”€ data/
â”‚   â”œâ”€â”€ raw/
â”‚   â”œâ”€â”€ processed/
â”‚   â””â”€â”€ external/
â”‚
â”œâ”€â”€ docs/
â”‚   â”œâ”€â”€ ARCHITECTURE.md
â”‚   â”œâ”€â”€ DATA.md
â”‚   â”œâ”€â”€ METHODOLOGY.md
â”‚   â””â”€â”€ PROJECT_STRUCTURE.md
â”‚
â”œâ”€â”€ src/
â”‚   â”œâ”€â”€ accessibility/
â”‚   â”œâ”€â”€ analysis/
â”‚   â””â”€â”€ network/
â”‚
â”œâ”€â”€ inspect_traffic_dataset.py
â”œâ”€â”€ README.md
â”œâ”€â”€ requirements.txt
â””â”€â”€ .gitignore
```

## `app/`

Contains the Streamlit application.

## `data/`

Contains raw, external and generated analytical data.

Large and generated data are ignored by Git.

## `src/accessibility/`

Contains the routing and accessibility calculations.

This is where opportunities are attached to the network and reachable opportunities are calculated.

## `src/network/`

Contains the road-network and travel-time calibration work.

The spatial traffic calibration is here.

## `src/analysis/`

Contains the research layer.

This includes:

- accessibility curves
- accessibility surfaces
- city-wide analysis
- intervention analysis
- geometry generation
- research findings
- validation

## `docs/`

Contains the detailed explanation of how the system works.

## `README.md`

The entry point for someone visiting the repository.

It explains the project in plain language before going into the technical details.
