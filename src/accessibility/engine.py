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


def load_network():
    print("Loading travel-time network...")
    graph = ox.load_graphml(GRAPH_PATH)

    # Convert travel_time back to float because GraphML
    # serialization can store numeric attributes as strings.
    for _, _, data in graph.edges(data=True):
        data["travel_time"] = float(data["travel_time"])

    print(f"Nodes: {len(graph.nodes):,}")
    print(f"Edges: {len(graph.edges):,}")

    return graph


def nearest_node(graph, latitude: float, longitude: float):
    return ox.distance.nearest_nodes(
        graph,
        X=longitude,
        Y=latitude,
    )


def reachable_nodes(
    graph,
    latitude: float,
    longitude: float,
    max_minutes: int = 30,
):
    origin = nearest_node(graph, latitude, longitude)

    max_seconds = max_minutes * 60

    distances = nx.single_source_dijkstra_path_length(
        graph,
        origin,
        cutoff=max_seconds,
        weight="travel_time",
    )

    return origin, distances


def main():
    graph = load_network()

    # Bengaluru city-centre test origin.
    # This is only an engine sanity check.
    latitude = 12.9716
    longitude = 77.5946

    origin, distances = reachable_nodes(
        graph,
        latitude,
        longitude,
        max_minutes=30,
    )

    print()
    print("Accessibility engine test")
    print(f"Origin node: {origin}")
    print(f"Reachable nodes within 30 min: {len(distances):,}")

    if distances:
        max_time = max(distances.values())
        print(f"Farthest reached travel time: {max_time / 60:.2f} min")


if __name__ == "__main__":
    main()