from pathlib import Path

import osmnx as ox
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]

GRAPH_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "bengaluru_travel_time.graphml"
)

RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

DATASETS = {
    "health": RAW_DIR / "bengaluru_health.csv",
    "education": RAW_DIR / "bengaluru_education.csv",
    "employment": RAW_DIR / "bengaluru_employment.csv",
}


def attach_dataset(graph, path: Path, category: str) -> pd.DataFrame:
    print(f"\nAttaching {category}...")

    df = pd.read_csv(path)

    # Validate required coordinates.
    df = df.dropna(subset=["latitude", "longitude"]).copy()

    # Find nearest road-network node for every opportunity.
    nodes = ox.distance.nearest_nodes(
        graph,
        X=df["longitude"].to_numpy(),
        Y=df["latitude"].to_numpy(),
    )

    df["network_node"] = nodes.astype("int64")
    df["opportunity_category"] = category

    # Distance from opportunity to its attached road node.
    node_x = pd.Series(
        {node: float(data["x"]) for node, data in graph.nodes(data=True)}
    )
    node_y = pd.Series(
        {node: float(data["y"]) for node, data in graph.nodes(data=True)}
    )

    df["node_longitude"] = df["network_node"].map(node_x)
    df["node_latitude"] = df["network_node"].map(node_y)

    output = PROCESSED_DIR / f"bengaluru_{category}_attached.csv"
    df.to_csv(output, index=False)

    print(f"Opportunities: {len(df):,}")
    print(f"Unique network nodes: {df['network_node'].nunique():,}")
    print(f"Saved: {output}")

    return df


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading Bengaluru travel-time network...")
    graph = ox.load_graphml(GRAPH_PATH)

    print(f"Network nodes: {len(graph.nodes):,}")

    for category, path in DATASETS.items():
        attach_dataset(graph, path, category)

    print("\nOpportunity attachment complete.")


if __name__ == "__main__":
    main()