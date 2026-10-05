from pathlib import Path

import networkx as nx
import osmnx as ox
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

GRAPH_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "bengaluru_travel_time.graphml"
)

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

THRESHOLDS = {
    "15": 15 * 60,
    "30": 30 * 60,
    "45": 45 * 60,
    "60": 60 * 60,
}


def load_graph():
    print("Loading travel-time network...")

    graph = ox.load_graphml(GRAPH_PATH)

    for _, _, data in graph.edges(data=True):
        data["travel_time"] = float(data["travel_time"])

    print(f"Nodes: {len(graph.nodes):,}")
    print(f"Edges: {len(graph.edges):,}")

    return graph


def load_opportunities():
    datasets = {
        "health": PROCESSED_DIR / "bengaluru_health_attached.csv",
        "education": PROCESSED_DIR / "bengaluru_education_attached.csv",
        "employment": PROCESSED_DIR / "bengaluru_employment_attached.csv",
    }

    opportunities = {}

    for category, path in datasets.items():
        df = pd.read_csv(path)

        # Employment may contain multiple listings at the same node.
        # Preserve that multiplicity as opportunity weight.
        grouped = (
            df.groupby("network_node")
            .size()
            .rename("opportunity_count")
            .reset_index()
        )

        opportunities[category] = grouped

        print(
            f"{category.capitalize():12s}: "
            f"{len(df):,} records → "
            f"{len(grouped):,} network nodes"
        )

    return opportunities


def calculate_origin_accessibility(
    graph,
    opportunities,
    latitude: float,
    longitude: float,
):
    origin = ox.distance.nearest_nodes(
        graph,
        X=longitude,
        Y=latitude,
    )

    # One Dijkstra search up to the largest threshold.
    distances = nx.single_source_dijkstra_path_length(
        graph,
        origin,
        cutoff=THRESHOLDS["60"],
        weight="travel_time",
    )

    results = {
        "latitude": latitude,
        "longitude": longitude,
        "network_node": origin,
    }

    for threshold_name, threshold_seconds in THRESHOLDS.items():

        reachable_nodes = {
            node
            for node, seconds in distances.items()
            if seconds <= threshold_seconds
        }

        for category, opportunities_df in opportunities.items():

            reachable = opportunities_df[
                opportunities_df["network_node"].isin(reachable_nodes)
            ]

            count = int(reachable["opportunity_count"].sum())

            results[
                f"{category}_{threshold_name}min"
            ] = count

    return results


def main():
    graph = load_graph()
    opportunities = load_opportunities()

    # Initial analytical origins.
    # These are deliberately spread across Bengaluru rather than
    # testing only the city centre.
    origins = [
        ("Central Bengaluru", 12.9716, 77.5946),
        ("Whitefield", 12.9698, 77.7500),
        ("Electronic City", 12.8452, 77.6602),
        ("Yelahanka", 13.1007, 77.5963),
        ("Kengeri", 12.9141, 77.4828),
        ("Hebbal", 13.0358, 77.5970),
        ("JP Nagar", 12.9063, 77.5857),
        ("Indiranagar", 12.9784, 77.6408),
        ("Rajajinagar", 12.9910, 77.5530),
        ("Marathahalli", 12.9591, 77.6974),
    ]

    rows = []

    print("\nCalculating accessibility...\n")

    for name, latitude, longitude in origins:
        print(f"Processing {name}...")

        result = calculate_origin_accessibility(
            graph,
            opportunities,
            latitude,
            longitude,
        )

        result["origin"] = name
        rows.append(result)

    result_df = pd.DataFrame(rows)

    columns = [
        "origin",
        "latitude",
        "longitude",
        "network_node",
        "health_15min",
        "health_30min",
        "health_45min",
        "health_60min",
        "education_15min",
        "education_30min",
        "education_45min",
        "education_60min",
        "employment_15min",
        "employment_30min",
        "employment_45min",
        "employment_60min",
    ]

    result_df = result_df[columns]

    output = PROCESSED_DIR / "bengaluru_accessibility_sample.csv"
    result_df.to_csv(output, index=False)

    print("\nAccessibility calculation complete.")
    print(f"Origins analysed: {len(result_df)}")
    print(f"Saved: {output}")

    print("\nResults:")
    print(result_df.to_string(index=False))


if __name__ == "__main__":
    main()