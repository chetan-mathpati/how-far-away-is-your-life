from pathlib import Path
import json
import pandas as pd
import networkx as nx
import osmnx as ox


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

CALIBRATION_PATH = (
    ROOT
    / "data"
    / "processed"
    / "time_networks"
    / "calibration_metadata.json"
)

OUTPUT_DIR = (
    ROOT
    / "data"
    / "processed"
    / "accessibility"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# ORIGINS
# ============================================================

ORIGINS = {
    "Central Bengaluru": (12.9716, 77.5946),
    "Whitefield": (12.9698, 77.7500),
    "Electronic City": (12.8452, 77.6602),
    "Yelahanka": (13.1007, 77.5963),
    "Kengeri": (12.9141, 77.4828),
    "Hebbal": (13.0358, 77.5970),
    "JP Nagar": (12.9063, 77.5857),
    "Indiranagar": (12.9784, 77.6408),
    "Rajajinagar": (12.9910, 77.5530),
    "Marathahalli": (12.9591, 77.6974),
}


# ============================================================
# OPPORTUNITY DATA
# ============================================================

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


# ============================================================
# ACCESSIBILITY THRESHOLDS
# ============================================================

THRESHOLDS = [15, 30, 45, 60]


# ============================================================
# LOAD GRAPH
# ============================================================

def load_graph():

    print("\nLoading canonical travel-time network...")

    G = nx.read_graphml(GRAPH_PATH)

    print(
        f"Raw nodes: {G.number_of_nodes():,}"
    )

    print(
        f"Raw edges: {G.number_of_edges():,}"
    )

    # --------------------------------------------------------
    # CRITICAL:
    # GraphML commonly loads node IDs as strings.
    # Normalize every node ID explicitly.
    # --------------------------------------------------------

    mapping = {
        node: str(node)
        for node in G.nodes
    }

    G = nx.relabel_nodes(
        G,
        mapping
    )

    # --------------------------------------------------------
    # Convert GraphML attributes from strings to numbers.
    # --------------------------------------------------------

    for node, data in G.nodes(data=True):

        if "x" in data:
            data["x"] = float(data["x"])

        if "y" in data:
            data["y"] = float(data["y"])

    for _, _, data in G.edges(data=True):

        data["travel_time"] = float(
            data["travel_time"]
        )

        data["speed_kmh"] = float(
            data["speed_kmh"]
        )

        data["length"] = float(
            data["length"]
        )

    print(
        "Graph attributes normalized."
    )

    return G


# ============================================================
# LOAD OPPORTUNITIES
# ============================================================

def load_opportunities():

    print(
        "\nLoading opportunity datasets..."
    )

    opportunities = {}

    for category, path in OPPORTUNITIES.items():

        df = pd.read_csv(path)

        # Normalize network node IDs.
        df["network_node"] = (
            df["network_node"]
            .astype(str)
        )

        # Multiple records can occupy the same
        # network node. Employment especially needs
        # multiplicity preserved.
        grouped = (
            df.groupby(
                "network_node"
            )
            .size()
            .reset_index(
                name="opportunity_count"
            )
        )

        opportunities[category] = grouped

        print(
            f"{category:12s}: "
            f"{len(df):,} records -> "
            f"{len(grouped):,} network nodes"
        )

    return opportunities


# ============================================================
# MAP ORIGINS TO ROAD NETWORK
# ============================================================

def map_origins(G):

    print(
        "\nMapping origins to road network..."
    )

    origin_nodes = {}

    for name, (lat, lon) in ORIGINS.items():

        node = ox.distance.nearest_nodes(
            G,
            X=float(lon),
            Y=float(lat),
        )

        # CRITICAL:
        # Network node IDs are normalized to strings.
        node = str(node)

        origin_nodes[name] = node

        print(
            f"{name:20s} -> {node}"
        )

    return origin_nodes


# ============================================================
# LOAD TIME CALIBRATION
# ============================================================

def load_calibration():

    print(
        "\nLoading time-of-day calibration..."
    )

    metadata = json.loads(
        CALIBRATION_PATH.read_text(
            encoding="utf-8"
        )
    )

    multipliers = {
        int(hour): float(multiplier)
        for hour, multiplier
        in metadata["multipliers"].items()
    }

    for hour in sorted(multipliers):

        print(
            f"{hour:02d}:00 -> "
            f"{multipliers[hour]:.3f}"
        )

    return multipliers


# ============================================================
# MAIN ACCESSIBILITY CALCULATION
# ============================================================

def calculate():

    G = load_graph()

    opportunities = (
        load_opportunities()
    )

    origin_nodes = (
        map_origins(G)
    )

    multipliers = (
        load_calibration()
    )

    # --------------------------------------------------------
    # Total opportunity counts
    # --------------------------------------------------------

    totals = {
        category: int(
            df["opportunity_count"].sum()
        )
        for category, df
        in opportunities.items()
    }

    print(
        "\nTotal opportunities:"
    )

    for category, total in totals.items():

        print(
            f"{category:12s}: "
            f"{total:,}"
        )

    # --------------------------------------------------------
    # Results container
    # --------------------------------------------------------

    results = []

    # ========================================================
    # TIME PERIOD LOOP
    # ========================================================

    for hour in sorted(multipliers):

        multiplier = (
            multipliers[hour]
        )

        print(
            "\n"
            + "=" * 65
        )

        print(
            f"TIME PERIOD: {hour:02d}:00"
        )

        print(
            f"Travel-time multiplier: "
            f"{multiplier:.3f}"
        )

        print(
            "=" * 65
        )

        # ----------------------------------------------------
        # Apply scenario travel time.
        #
        # If multiplier = 0.874:
        #
        # scenario_time =
        # baseline_time / 0.874
        #
        # Therefore roads become slower.
        # ----------------------------------------------------

        for _, _, data in G.edges(
            data=True
        ):

            data["scenario_time"] = (
                data["travel_time"]
                / multiplier
            )

        # ====================================================
        # ORIGIN LOOP
        # ====================================================

        for origin_name, origin_node in (
            origin_nodes.items()
        ):

            print(
                f"Processing "
                f"{origin_name}..."
            )

            # ------------------------------------------------
            # One Dijkstra search per origin/time period.
            # ------------------------------------------------

            distances = (
                nx.single_source_dijkstra_path_length(
                    G,
                    origin_node,
                    cutoff=60 * 60,
                    weight="scenario_time",
                )
            )

            # Convert seconds -> minutes.
            distance_minutes = {
                str(node): seconds / 60.0
                for node, seconds
                in distances.items()
            }

            # =================================================
            # OPPORTUNITY CATEGORY LOOP
            # =================================================

            for category, opp_df in (
                opportunities.items()
            ):

                # ---------------------------------------------
                # Keep only opportunities reachable within
                # the 60-minute analysis horizon.
                # ---------------------------------------------

                reachable = []

                for _, row in (
                    opp_df.iterrows()
                ):

                    node = str(
                        row[
                            "network_node"
                        ]
                    )

                    if node in distance_minutes:

                        reachable.append(
                            (
                                distance_minutes[
                                    node
                                ],

                                int(
                                    row[
                                        "opportunity_count"
                                    ]
                                )
                            )
                        )

                # =================================================
                # THRESHOLD LOOP
                # =================================================

                for threshold in THRESHOLDS:

                    accessible_count = sum(
                        weight
                        for travel_time, weight
                        in reachable
                        if travel_time <= threshold
                    )

                    total = totals[
                        category
                    ]

                    accessibility_share = (
                        accessible_count / total
                        if total > 0
                        else 0.0
                    )

                    results.append(
                        {
                            "origin": (
                                origin_name
                            ),

                            "latitude": (
                                ORIGINS[
                                    origin_name
                                ][0]
                            ),

                            "longitude": (
                                ORIGINS[
                                    origin_name
                                ][1]
                            ),

                            "hour": hour,

                            "category": (
                                category
                            ),

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
                                accessibility_share
                            ),

                            "multiplier": (
                                multiplier
                            ),
                        }
                    )

    # ========================================================
    # SAVE RESULTS
    # ========================================================

    df = pd.DataFrame(
        results
    )

    output_path = (
        OUTPUT_DIR
        / "bengaluru_time_accessibility.csv"
    )

    df.to_csv(
        output_path,
        index=False
    )

    # ========================================================
    # SUMMARY
    # ========================================================

    print(
        "\n"
        + "=" * 65
    )

    print(
        "ACCESSIBILITY CALCULATION COMPLETE"
    )

    print(
        "=" * 65
    )

    print(
        f"Rows generated: {len(df):,}"
    )

    print(
        "Expected rows: 600"
    )

    print(
        f"Saved: {output_path}"
    )

    print(
        "\nRows by time:"
    )

    print(
        df.groupby("hour")
        .size()
        .to_string()
    )

    print(
        "\nRows by category:"
    )

    print(
        df.groupby("category")
        .size()
        .to_string()
    )

    print(
        "\nSample:"
    )

    print(
        df.head(20)
        .to_string(index=False)
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    calculate()