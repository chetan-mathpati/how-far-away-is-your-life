from pathlib import Path
import json
import math
import pandas as pd
import numpy as np
import networkx as nx


# ============================================================
# PATHS
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

GRAPH_PATH = (
    ROOT
    / "data"
    / "processed"
    / "bengaluru_travel_time.graphml"
)

CALIBRATION_PATH = (
    ROOT
    / "data"
    / "processed"
    / "time_networks"
    / "calibration_metadata.json"
)

OPPORTUNITIES = {
    "health": (
        ROOT
        / "data"
        / "processed"
        / "bengaluru_health_attached.csv"
    ),
    "education": (
        ROOT
        / "data"
        / "processed"
        / "bengaluru_education_attached.csv"
    ),
    "employment": (
        ROOT
        / "data"
        / "processed"
        / "bengaluru_employment_attached.csv"
    ),
}

OUTPUT_DIR = (
    ROOT
    / "data"
    / "processed"
    / "citywide"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

THRESHOLDS = [15, 30, 45, 60]

# Approximately 1 km spatial grid.
# 0.01 degrees latitude is ~1.11 km.
GRID_SIZE = 0.01

# Maximum number of representative origins.
# The script naturally produces fewer if the road network
# contains fewer occupied grid cells.
MAX_ORIGINS = 1500


# ============================================================
# LOAD GRAPH
# ============================================================

def load_graph():

    print("\nLoading Bengaluru network...")

    G = nx.read_graphml(
        GRAPH_PATH
    )

    # Normalize node IDs.
    G = nx.relabel_nodes(
        G,
        {
            node: str(node)
            for node in G.nodes
        }
    )

    # Normalize node coordinates.
    for node, data in G.nodes(data=True):

        data["x"] = float(data["x"])
        data["y"] = float(data["y"])

    # Normalize edge travel time.
    for _, _, data in G.edges(data=True):

        data["travel_time"] = float(
            data["travel_time"]
        )

    print(
        f"Nodes: {G.number_of_nodes():,}"
    )

    print(
        f"Edges: {G.number_of_edges():,}"
    )

    return G


# ============================================================
# LOAD OPPORTUNITIES
# ============================================================

def load_opportunities():

    print("\nLoading opportunities...")

    opportunities = {}

    for category, path in OPPORTUNITIES.items():

        df = pd.read_csv(path)

        df["network_node"] = (
            df["network_node"]
            .astype(str)
        )

        grouped = (
            df.groupby("network_node")
            .size()
            .reset_index(
                name="opportunity_count"
            )
        )

        grouped["network_node"] = (
            grouped["network_node"]
            .astype(str)
        )

        opportunities[category] = grouped

        print(
            f"{category:12s}: "
            f"{len(df):,} records -> "
            f"{len(grouped):,} network nodes"
        )

    return opportunities


# ============================================================
# BUILD REPRESENTATIVE CITYWIDE ORIGINS
# ============================================================

def build_origins(G):

    print(
        "\nBuilding approximately 1 km "
        "road-network origin grid..."
    )

    cells = {}

    for node, data in G.nodes(data=True):

        lat = float(data["y"])
        lon = float(data["x"])

        # Spatial grid cell.
        cell_x = math.floor(
            lon / GRID_SIZE
        )

        cell_y = math.floor(
            lat / GRID_SIZE
        )

        key = (
            cell_x,
            cell_y
        )

        # Keep the first road node in each cell.
        if key not in cells:

            cells[key] = {
                "node": node,
                "latitude": lat,
                "longitude": lon,
            }

    origins = list(
        cells.values()
    )

    # Deterministic ordering.
    origins.sort(
        key=lambda x: (
            x["latitude"],
            x["longitude"],
        )
    )

    # Safety cap.
    if len(origins) > MAX_ORIGINS:

        print(
            f"Grid produced "
            f"{len(origins):,} cells."
        )

        print(
            f"Sampling down to "
            f"{MAX_ORIGINS:,} origins."
        )

        step = (
            len(origins)
            / MAX_ORIGINS
        )

        origins = [
            origins[
                int(i * step)
            ]
            for i in range(
                MAX_ORIGINS
            )
        ]

    print(
        f"Representative origins: "
        f"{len(origins):,}"
    )

    return origins


# ============================================================
# LOAD CALIBRATION
# ============================================================

def load_calibration():

    metadata = json.loads(
        CALIBRATION_PATH.read_text(
            encoding="utf-8"
        )
    )

    multipliers = {
        int(hour): float(value)
        for hour, value
        in metadata[
            "multipliers"
        ].items()
    }

    print(
        "\nTime-of-day calibration:"
    )

    for hour in sorted(
        multipliers
    ):

        print(
            f"{hour:02d}:00 -> "
            f"{multipliers[hour]:.3f}"
        )

    return multipliers


# ============================================================
# ACCESSIBILITY CALCULATION
# ============================================================

def calculate():

    G = load_graph()

    opportunities = (
        load_opportunities()
    )

    origins = build_origins(G)

    multipliers = (
        load_calibration()
    )

    # --------------------------------------------------------
    # Opportunity lookup:
    #
    # category -> network node -> count
    # --------------------------------------------------------

    opportunity_maps = {}

    totals = {}

    for category, df in (
        opportunities.items()
    ):

        opportunity_maps[category] = {
            str(row["network_node"]):
                int(row["opportunity_count"])
            for _, row in df.iterrows()
        }

        totals[category] = int(
            df["opportunity_count"].sum()
        )

    # --------------------------------------------------------
    # Important optimization:
    #
    # We only need ONE Dijkstra per origin.
    #
    # The time-of-day model is:
    #
    # scenario_time = baseline_time / multiplier
    #
    # Therefore:
    #
    # scenario_time <= T
    #
    # becomes:
    #
    # baseline_time <= T * multiplier
    #
    # So we can reuse the baseline shortest-path tree.
    # --------------------------------------------------------

    maximum_baseline_cutoff = (
        max(THRESHOLDS)
        * 60
        * max(multipliers.values())
    )

    print(
        "\nMaximum baseline search cutoff:"
    )

    print(
        f"{maximum_baseline_cutoff / 60:.2f} minutes"
    )

    results = []

    total_origins = len(
        origins
    )

    # ========================================================
    # ORIGIN LOOP
    # ========================================================

    for index, origin in enumerate(
        origins,
        start=1
    ):

        origin_node = origin[
            "node"
        ]

        # ----------------------------------------------------
        # Progress indicator.
        # ----------------------------------------------------

        if (
            index == 1
            or index % 25 == 0
            or index == total_origins
        ):

            print(
                f"Processing origin "
                f"{index:,}/{total_origins:,}"
            )

        # ----------------------------------------------------
        # ONE baseline Dijkstra.
        # ----------------------------------------------------

        distances = (
            nx.single_source_dijkstra_path_length(
                G,
                origin_node,
                cutoff=maximum_baseline_cutoff,
                weight="travel_time",
            )
        )

        # Convert to minutes.
        distances_minutes = {
            str(node): (
                seconds / 60.0
            )
            for node, seconds
            in distances.items()
        }

        # ====================================================
        # TIME PERIOD
        # ====================================================

        for hour, multiplier in sorted(
            multipliers.items()
        ):

            # =================================================
            # CATEGORY
            # =================================================

            for category, node_counts in (
                opportunity_maps.items()
            ):

                total = totals[
                    category
                ]

                # ------------------------------------------------
                # For every threshold, convert the scenario
                # threshold into an equivalent baseline threshold.
                #
                # Example:
                #
                # 18:00 multiplier = 0.874
                #
                # 30-minute scenario threshold:
                #
                # baseline <= 30 * 0.874
                # = 26.22 minutes
                # ------------------------------------------------

                for threshold in THRESHOLDS:

                    baseline_limit = (
                        threshold
                        * multiplier
                    )

                    accessible_count = 0

                    for node, count in (
                        node_counts.items()
                    ):

                        travel_time = (
                            distances_minutes
                            .get(node)
                        )

                        if (
                            travel_time
                            is not None
                            and travel_time
                            <= baseline_limit
                        ):

                            accessible_count += count

                    share = (
                        accessible_count
                        / total
                        if total > 0
                        else 0.0
                    )

                    results.append(
                        {
                            "origin_id": index,
                            "latitude": origin[
                                "latitude"
                            ],
                            "longitude": origin[
                                "longitude"
                            ],
                            "network_node": (
                                origin_node
                            ),
                            "hour": hour,
                            "category": category,
                            "threshold_min": (
                                threshold
                            ),
                            "accessible_count": (
                                accessible_count
                            ),
                            "total_opportunities": (
                                total
                            ),
                            "accessibility_share": (
                                share
                            ),
                            "multiplier": (
                                multiplier
                            ),
                        }
                    )

    # ========================================================
    # SAVE
    # ========================================================

    df = pd.DataFrame(
        results
    )

    output = (
        OUTPUT_DIR
        / "bengaluru_citywide_accessibility.csv"
    )

    df.to_csv(
        output,
        index=False
    )

    # Save origin coordinates separately.
    origins_df = pd.DataFrame(
        origins
    )

    origins_df.insert(
        0,
        "origin_id",
        range(
            1,
            len(origins_df) + 1
        )
    )

    origins_df.to_csv(
        OUTPUT_DIR
        / "citywide_origins.csv",
        index=False
    )

    # ========================================================
    # SUMMARY
    # ========================================================

    print(
        "\n"
        + "=" * 70
    )

    print(
        "CITYWIDE ACCESSIBILITY COMPLETE"
    )

    print(
        "=" * 70
    )

    print(
        f"Origins: {len(origins):,}"
    )

    print(
        f"Rows: {len(df):,}"
    )

    expected = (
        len(origins)
        * len(multipliers)
        * len(OPPORTUNITIES)
        * len(THRESHOLDS)
    )

    print(
        f"Expected rows: {expected:,}"
    )

    print(
        f"\nSaved:\n{output}"
    )

    print(
        f"\nSaved:\n"
        f"{OUTPUT_DIR / 'citywide_origins.csv'}"
    )

    print(
        "\nAccessibility range:"
    )

    summary = (
        df.groupby(
            [
                "hour",
                "category",
                "threshold_min",
            ]
        )[
            "accessibility_share"
        ]
        .agg(
            mean="mean",
            median="median",
            minimum="min",
            maximum="max",
        )
        .reset_index()
    )

    print(
        summary.round(3)
        .to_string(index=False)
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    calculate()