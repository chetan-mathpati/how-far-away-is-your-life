from pathlib import Path
import json
import pandas as pd
import networkx as nx

ROOT = Path(__file__).resolve().parents[2]

TRAFFIC_XLSX = (
    ROOT
    / "data"
    / "external"
    / "bengaluru-traffic-reference"
    / "data"
    / "Bengaluru_Traffic_Condition_Dataset.xlsx"
)

OUT_DIR = ROOT / "data" / "processed" / "time_networks"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_HOURS = [7, 9, 13, 18, 22]

print("Loading traffic reference dataset...")
traffic = pd.read_excel(TRAFFIC_XLSX)

hourly = (
    traffic.groupby("hour")["average_speed_kmh"]
    .mean()
    .reindex(range(8, 23))
    .interpolate()
)

hourly.loc[7] = hourly.loc[8] * 0.98

observed = {
    hour: float(hourly.loc[hour])
    for hour in TARGET_HOURS
}

reference_speed = observed[13]

multipliers = {
    hour: observed[hour] / reference_speed
    for hour in TARGET_HOURS
}

print("\nObserved traffic reference speeds:")

for hour in TARGET_HOURS:
    print(
        f"  {hour:02d}:00 -> "
        f"{observed[hour]:.2f} km/h"
    )

print("\nRelative time-of-day multipliers:")

for hour in TARGET_HOURS:
    print(
        f"  {hour:02d}:00 -> "
        f"{multipliers[hour]:.3f}"
    )

# Save calibration parameters only.
# We intentionally DO NOT duplicate the 155k-node network.
metadata = {
    "method": (
        "Relative time-of-day calibration against "
        "public Bengaluru traffic reference dataset"
    ),
    "reference_hour": 13,
    "target_hours": TARGET_HOURS,
    "observed_target_speeds_kmh": observed,
    "multipliers": multipliers,
    "warning": (
        "These are modeled travel-time adjustments, "
        "not measured road travel times."
    ),
}

metadata_path = OUT_DIR / "calibration_metadata.json"

metadata_path.write_text(
    json.dumps(metadata, indent=2),
    encoding="utf-8",
)

summary = pd.DataFrame(
    [
        {
            "hour": hour,
            "observed_speed_kmh": observed[hour],
            "multiplier": multipliers[hour],
        }
        for hour in TARGET_HOURS
    ]
)

summary_path = OUT_DIR / "calibration_summary.csv"

summary.to_csv(
    summary_path,
    index=False,
)

print("\nCalibration complete.")

print(f"Saved: {metadata_path}")
print(f"Saved: {summary_path}")

print(
    "\nNo GraphML copies created. "
    "The original network will be reused for all time periods."
)