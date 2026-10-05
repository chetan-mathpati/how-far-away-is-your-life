from pathlib import Path
import json
import warnings

import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
from scipy.spatial import cKDTree

warnings.filterwarnings("ignore")


# ============================================================
# PROJECT PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

GRAPH_PATH = (
    ROOT
    / "data"
    / "processed"
    / "bengaluru_travel_time.graphml"
)

TRAFFIC_PATH = (
    ROOT
    / "data"
    / "external"
    / "bengaluru-traffic-reference"
    / "data"
    / "Bengaluru_Traffic_Condition_Dataset.xlsx"
)

OUT_DIR = (
    ROOT
    / "data"
    / "processed"
    / "spatial_traffic"
)

OUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# CONFIGURATION
# ============================================================

TARGET_HOURS = [7, 9, 13, 18, 22]

# The reference dataset starts at 08:00.
# Therefore 07:00 uses the 08:00 observed condition.
HOUR_PROXY = {
    7: 8,
    9: 9,
    13: 13,
    18: 18,
    22: 22,
}

# Maximum spatial influence radius.
RADIUS_KM = 5.0

# Inverse-distance weighting exponent.
POWER = 2.0

# Traffic should never make the modeled network
# faster than the OSM baseline.
MIN_MULTIPLIER = 0.55
MAX_MULTIPLIER = 1.00


# ============================================================
# VALIDATE INPUT FILES
# ============================================================

if not GRAPH_PATH.exists():
    raise FileNotFoundError(
        f"Road graph not found:\n{GRAPH_PATH}"
    )

if not TRAFFIC_PATH.exists():
    raise FileNotFoundError(
        f"Traffic dataset not found:\n{TRAFFIC_PATH}"
    )


# ============================================================
# LOAD ROAD NETWORK
# ============================================================

print("\nLoading road network...")

G = ox.load_graphml(
    GRAPH_PATH
)

print(
    f"Nodes: {G.number_of_nodes():,}"
)

print(
    f"Edges: {G.number_of_edges():,}"
)


# ============================================================
# NORMALIZE NODE INFORMATION
# ============================================================

node_records = []

for node, data in G.nodes(data=True):

    try:
        x = float(data["x"])
        y = float(data["y"])
    except (
        KeyError,
        TypeError,
        ValueError,
    ):
        continue

    node_records.append(
        {
            "node": str(node),
            "x": x,
            "y": y,
        }
    )

nodes = pd.DataFrame(
    node_records
)

if nodes.empty:
    raise RuntimeError(
        "No valid road-network nodes were found."
    )


# ============================================================
# LOAD TRAFFIC DATA
# ============================================================

print("\nLoading traffic reference...")

traffic = pd.read_excel(
    TRAFFIC_PATH,
    sheet_name="traffic_data"
)

required_columns = [
    "hotspot_id",
    "hotspot_name",
    "latitude",
    "longitude",
    "hour",
    "average_speed_kmh",
    "congestion_score",
    "average_queue_length",
    "average_waiting_time_min",
]

missing = [
    column
    for column in required_columns
    if column not in traffic.columns
]

if missing:
    raise ValueError(
        "Traffic dataset is missing required columns: "
        + ", ".join(missing)
    )

traffic["hour"] = (
    pd.to_numeric(
        traffic["hour"],
        errors="coerce"
    )
)

traffic["latitude"] = (
    pd.to_numeric(
        traffic["latitude"],
        errors="coerce"
    )
)

traffic["longitude"] = (
    pd.to_numeric(
        traffic["longitude"],
        errors="coerce"
    )
)

traffic["average_speed_kmh"] = (
    pd.to_numeric(
        traffic["average_speed_kmh"],
        errors="coerce"
    )
)

traffic["congestion_score"] = (
    pd.to_numeric(
        traffic["congestion_score"],
        errors="coerce"
    )
)

traffic["average_queue_length"] = (
    pd.to_numeric(
        traffic["average_queue_length"],
        errors="coerce"
    )
)

traffic["average_waiting_time_min"] = (
    pd.to_numeric(
        traffic["average_waiting_time_min"],
        errors="coerce"
    )
)

traffic = traffic.dropna(
    subset=[
        "hotspot_id",
        "latitude",
        "longitude",
        "hour",
        "average_speed_kmh",
    ]
).copy()

traffic["hour"] = (
    traffic["hour"]
    .astype(int)
)

print(
    f"Traffic observations: "
    f"{len(traffic):,}"
)

print(
    f"Hotspots: "
    f"{traffic['hotspot_id'].nunique()}"
)

print(
    "Observed hours:",
    sorted(
        traffic["hour"]
        .unique()
        .tolist()
    )
)


# ============================================================
# APPROXIMATE KM COORDINATES
# ============================================================

LAT0 = nodes["y"].mean()

KM_PER_DEG_LAT = 111.32

KM_PER_DEG_LON = (
    111.32
    * np.cos(
        np.radians(LAT0)
    )
)

node_xy = np.column_stack(
    [
        nodes["x"].to_numpy()
        * KM_PER_DEG_LON,

        nodes["y"].to_numpy()
        * KM_PER_DEG_LAT,
    ]
)

node_tree = cKDTree(
    node_xy
)


# ============================================================
# MAP TRAFFIC HOTSPOTS TO ROAD NETWORK
# ============================================================

print(
    "\nMapping traffic hotspots "
    "to road network..."
)

hotspots = (
    traffic[
        [
            "hotspot_id",
            "hotspot_name",
            "latitude",
            "longitude",
        ]
    ]
    .drop_duplicates(
        "hotspot_id"
    )
    .copy()
)

hotspot_xy = np.column_stack(
    [
        hotspots["longitude"].to_numpy()
        * KM_PER_DEG_LON,

        hotspots["latitude"].to_numpy()
        * KM_PER_DEG_LAT,
    ]
)

distances, indices = (
    node_tree.query(
        hotspot_xy,
        k=1
    )
)

hotspots["nearest_node"] = [
    nodes.iloc[index]["node"]
    for index in indices
]

hotspots["network_snap_distance_km"] = (
    distances
)

print(
    "Maximum hotspot snap distance:",
    f"{distances.max():.3f} km"
)

print(
    "Median hotspot snap distance:",
    f"{np.median(distances):.3f} km"
)


# ============================================================
# ESTIMATE LOCAL OSM BASELINE SPEED
# ============================================================

print(
    "\nEstimating local OSM baseline speeds..."
)

node_speed_samples = {}

for u, v, key, data in G.edges(
    keys=True,
    data=True
):

    try:
        speed = float(
            data["speed_kmh"]
        )
    except (
        KeyError,
        TypeError,
        ValueError,
    ):
        continue

    u = str(u)
    v = str(v)

    node_speed_samples.setdefault(
        u,
        []
    ).append(speed)

    node_speed_samples.setdefault(
        v,
        []
    ).append(speed)


all_speed_values = [
    speed
    for values in node_speed_samples.values()
    for speed in values
]

if not all_speed_values:
    raise RuntimeError(
        "No speed_kmh values were found "
        "in the road network."
    )

global_network_speed = float(
    np.median(
        all_speed_values
    )
)

hotspot_baselines = []

for _, row in hotspots.iterrows():

    node = row["nearest_node"]

    local_speeds = (
        node_speed_samples.get(
            node,
            []
        )
    )

    if local_speeds:

        baseline_speed = float(
            np.median(
                local_speeds
            )
        )

    else:

        baseline_speed = (
            global_network_speed
        )

    hotspot_baselines.append(
        baseline_speed
    )

hotspots["baseline_speed_kmh"] = (
    hotspot_baselines
)


# ============================================================
# ATTACH BASELINE SPEED TO TRAFFIC OBSERVATIONS
# ============================================================

traffic = traffic.merge(
    hotspots[
        [
            "hotspot_id",
            "nearest_node",
            "network_snap_distance_km",
            "baseline_speed_kmh",
        ]
    ],
    on="hotspot_id",
    how="left"
)


# ============================================================
# CALCULATE OBSERVED / BASELINE SPEED RATIO
# ============================================================

traffic["speed_multiplier_raw"] = (
    traffic["average_speed_kmh"]
    /
    traffic["baseline_speed_kmh"]
)

# Important modeling rule:
#
# multiplier < 1
#     → observed traffic is slower than baseline
#
# multiplier = 1
#     → no slowdown applied
#
# multiplier > 1
#     → observed speed exceeds our baseline
#       and is treated as baseline-model mismatch,
#       NOT as evidence that roads should become faster.
#
traffic["speed_multiplier"] = (
    traffic["speed_multiplier_raw"]
    .clip(
        lower=MIN_MULTIPLIER,
        upper=MAX_MULTIPLIER,
    )
)


# ============================================================
# GLOBAL FALLBACK MULTIPLIER
# ============================================================

global_multiplier = {}

for observed_hour in sorted(
    traffic["hour"].unique()
):

    subset = traffic[
        traffic["hour"]
        == observed_hour
    ]

    value = float(
        subset[
            "speed_multiplier"
        ].median()
    )

    global_multiplier[
        observed_hour
    ] = value


print(
    "\nGlobal fallback multipliers:"
)

for hour in sorted(
    global_multiplier
):

    print(
        f"  {hour:02d}:00 → "
        f"{global_multiplier[hour]:.3f}"
    )


# ============================================================
# BUILD SPATIAL TRAFFIC FIELDS
# ============================================================

print(
    "\nBuilding spatial traffic fields..."
)

node_results = []

for target_hour in TARGET_HOURS:

    observed_hour = HOUR_PROXY[
        target_hour
    ]

    hour_data = traffic[
        traffic["hour"]
        == observed_hour
    ].copy()

    if hour_data.empty:
        raise RuntimeError(
            f"No traffic observations for "
            f"reference hour {observed_hour}."
        )

    hotspot_points = np.column_stack(
        [
            hour_data[
                "longitude"
            ].to_numpy()
            * KM_PER_DEG_LON,

            hour_data[
                "latitude"
            ].to_numpy()
            * KM_PER_DEG_LAT,
        ]
    )

    hotspot_tree = cKDTree(
        hotspot_points
    )

    hotspot_multipliers = (
        hour_data[
            "speed_multiplier"
        ].to_numpy()
    )

    neighbor_lists = (
        hotspot_tree.query_ball_point(
            node_xy,
            r=RADIUS_KM
        )
    )

    fallback = global_multiplier[
        observed_hour
    ]

    multipliers = np.full(
        len(nodes),
        fallback,
        dtype=float
    )

    for i, neighbors in enumerate(
        neighbor_lists
    ):

        if not neighbors:
            continue

        local_points = (
            hotspot_points[
                neighbors
            ]
        )

        dx = (
            local_points[:, 0]
            - node_xy[i, 0]
        )

        dy = (
            local_points[:, 1]
            - node_xy[i, 1]
        )

        distances_km = np.sqrt(
            dx ** 2
            + dy ** 2
        )

        # Avoid zero-distance division.
        distances_km = np.maximum(
            distances_km,
            0.05
        )

        weights = (
            1.0
            /
            distances_km ** POWER
        )

        local_values = (
            hotspot_multipliers[
                neighbors
            ]
        )

        weighted_value = (
            np.sum(
                weights
                * local_values
            )
            /
            np.sum(
                weights
            )
        )

        multipliers[i] = (
            weighted_value
        )

    multipliers = np.clip(
        multipliers,
        MIN_MULTIPLIER,
        MAX_MULTIPLIER
    )

    hour_frame = pd.DataFrame(
        {
            "node": nodes["node"],
            "hour": target_hour,
            "observed_reference_hour":
                observed_hour,
            "spatial_speed_multiplier":
                multipliers,
        }
    )

    node_results.append(
        hour_frame
    )


node_calibration = pd.concat(
    node_results,
    ignore_index=True
)


# ============================================================
# BUILD NODE MULTIPLIER LOOKUP
# ============================================================

node_multiplier_lookup = {}

for hour in TARGET_HOURS:

    subset = node_calibration[
        node_calibration["hour"]
        == hour
    ]

    node_multiplier_lookup[
        hour
    ] = dict(
        zip(
            subset["node"],
            subset[
                "spatial_speed_multiplier"
            ]
        )
    )


# ============================================================
# BUILD EDGE-LEVEL CALIBRATION
# ============================================================

print(
    "\nBuilding calibrated edge travel times..."
)

edge_records = []

for target_hour in TARGET_HOURS:

    multiplier_map = (
        node_multiplier_lookup[
            target_hour
        ]
    )

    for u, v, key, data in G.edges(
        keys=True,
        data=True
    ):

        u_str = str(u)
        v_str = str(v)

        u_multiplier = (
            multiplier_map.get(
                u_str,
                1.0
            )
        )

        v_multiplier = (
            multiplier_map.get(
                v_str,
                1.0
            )
        )

        edge_multiplier = (
            u_multiplier
            + v_multiplier
        ) / 2.0

        # Final safety guard.
        edge_multiplier = float(
            np.clip(
                edge_multiplier,
                MIN_MULTIPLIER,
                MAX_MULTIPLIER
            )
        )

        baseline_time = float(
            data["travel_time"]
        )

        calibrated_time = (
            baseline_time
            /
            edge_multiplier
        )

        edge_records.append(
            {
                "hour": target_hour,
                "u": u_str,
                "v": v_str,
                "key": key,
                "speed_multiplier":
                    edge_multiplier,
                "baseline_travel_time_s":
                    baseline_time,
                "calibrated_travel_time_s":
                    calibrated_time,
            }
        )


edge_calibration = pd.DataFrame(
    edge_records
)


# ============================================================
# SAVE NODE CALIBRATION
# ============================================================

node_calibration.to_csv(
    OUT_DIR
    / "node_spatial_calibration.csv",
    index=False
)


# ============================================================
# SAVE EDGE CALIBRATION
# ============================================================

edge_calibration.to_csv(
    OUT_DIR
    / "edge_spatial_calibration.csv",
    index=False
)


# ============================================================
# SAVE HOTSPOT NETWORK MAPPING
# ============================================================

hotspots[
    [
        "hotspot_id",
        "hotspot_name",
        "latitude",
        "longitude",
        "nearest_node",
        "network_snap_distance_km",
        "baseline_speed_kmh",
    ]
].to_csv(
    OUT_DIR
    / "hotspot_network_mapping.csv",
    index=False
)


# ============================================================
# SAVE HOTSPOT CALIBRATION
# ============================================================

traffic[
    [
        "hotspot_id",
        "hotspot_name",
        "hour",
        "average_speed_kmh",
        "baseline_speed_kmh",
        "speed_multiplier_raw",
        "speed_multiplier",
        "congestion_score",
        "average_queue_length",
        "average_waiting_time_min",
    ]
].to_csv(
    OUT_DIR
    / "hotspot_speed_calibration.csv",
    index=False
)


# ============================================================
# SUMMARY
# ============================================================

summary_rows = []

for target_hour in TARGET_HOURS:

    subset = edge_calibration[
        edge_calibration["hour"]
        == target_hour
    ]

    multipliers = (
        subset[
            "speed_multiplier"
        ]
        .astype(float)
    )

    travel_time_increase = (
        1.0
        /
        multipliers
        - 1.0
    )

    summary_rows.append(
        {
            "hour": target_hour,

            "mean_multiplier":
                float(
                    multipliers.mean()
                ),

            "median_multiplier":
                float(
                    multipliers.median()
                ),

            "p10_multiplier":
                float(
                    multipliers.quantile(
                        0.10
                    )
                ),

            "p90_multiplier":
                float(
                    multipliers.quantile(
                        0.90
                    )
                ),

            "mean_travel_time_increase":
                float(
                    travel_time_increase.mean()
                ),

            "median_travel_time_increase":
                float(
                    travel_time_increase.median()
                ),

            "p90_travel_time_increase":
                float(
                    travel_time_increase.quantile(
                        0.90
                    )
                ),
        }
    )


summary = pd.DataFrame(
    summary_rows
)


summary.to_csv(
    OUT_DIR
    / "spatial_traffic_summary.csv",
    index=False
)


# ============================================================
# METADATA
# ============================================================

metadata = {
    "traffic_source":
        str(TRAFFIC_PATH),

    "graph_source":
        str(GRAPH_PATH),

    "target_hours":
        TARGET_HOURS,

    "hour_proxy":
        HOUR_PROXY,

    "radius_km":
        RADIUS_KM,

    "distance_weight_power":
        POWER,

    "minimum_multiplier":
        MIN_MULTIPLIER,

    "maximum_multiplier":
        MAX_MULTIPLIER,

    "method":
        (
            "Observed hotspot speed divided by "
            "local OSM-derived baseline speed. "
            "Hotspot ratios are spatially interpolated "
            "to road-network nodes using inverse-distance "
            "weighting and then averaged across edge "
            "endpoints."
        ),

    "speed_cap_rule":
        (
            "Multipliers above 1.0 are clipped to 1.0. "
            "Observed speeds above the OSM-derived "
            "baseline are treated as baseline-model "
            "mismatch rather than evidence of faster "
            "travel."
        ),

    "important_limitation":
        (
            "Traffic observations are hotspot-level "
            "reference observations, not complete "
            "road-segment travel-time measurements. "
            "The resulting travel times are modeled "
            "estimates rather than observed trips."
        ),
}


with open(
    OUT_DIR
    / "calibration_metadata.json",
    "w",
    encoding="utf-8",
) as f:

    json.dump(
        metadata,
        f,
        indent=2
    )


# ============================================================
# VALIDATION CHECKS
# ============================================================

print(
    "\n"
    + "=" * 70
)

print(
    "VALIDATION CHECKS"
)

print(
    "=" * 70
)

print(
    "\nMultiplier bounds:"
)

print(
    f"Minimum: "
    f"{edge_calibration['speed_multiplier'].min():.4f}"
)

print(
    f"Maximum: "
    f"{edge_calibration['speed_multiplier'].max():.4f}"
)

if (
    edge_calibration[
        "speed_multiplier"
    ]
    > 1.0
).any():

    raise RuntimeError(
        "Validation failed: "
        "some multipliers exceed 1.0."
    )

if (
    edge_calibration[
        "speed_multiplier"
    ]
    < MIN_MULTIPLIER
).any():

    raise RuntimeError(
        "Validation failed: "
        "some multipliers are below "
        "the configured minimum."
    )

print(
    "All multiplier bounds passed."
)


expected_rows = (
    len(TARGET_HOURS)
    * G.number_of_edges()
)

actual_rows = len(
    edge_calibration
)

print(
    "\nExpected edge rows:",
    f"{expected_rows:,}"
)

print(
    "Actual edge rows:",
    f"{actual_rows:,}"
)

if actual_rows != expected_rows:

    raise RuntimeError(
        "Validation failed: "
        "unexpected edge calibration row count."
    )

print(
    "Edge row count passed."
)


# ============================================================
# FINAL REPORT
# ============================================================

print(
    "\n"
    + "=" * 70
)

print(
    "SPATIAL TRAFFIC CALIBRATION COMPLETE"
)

print(
    "=" * 70
)

print(
    f"\nOutput directory:\n{OUT_DIR}"
)

print(
    "\nFiles:"
)

for file in sorted(
    OUT_DIR.iterdir()
):

    print(
        f"  {file.name}"
    )


print(
    "\n"
    + "=" * 70
)

print(
    "CALIBRATION SUMMARY"
)

print(
    "=" * 70
)

print(
    summary.to_string(
        index=False,
        float_format=lambda x:
            f"{x:.4f}"
    )
)


print(
    "\n"
    + "=" * 70
)

print(
    "HOTSPOT NETWORK MAPPING"
)

print(
    "=" * 70
)

print(
    hotspots[
        [
            "hotspot_id",
            "hotspot_name",
            "network_snap_distance_km",
            "baseline_speed_kmh",
        ]
    ].to_string(
        index=False
    )
)


print(
    "\nNOTE:"
)

print(
    "These are modeled travel-time adjustments "
    "using hotspot observations."
)

print(
    "They should NOT be described as GPS-observed "
    "travel times."
)