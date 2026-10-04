from pathlib import Path
import math
import re

import networkx as nx
import osmnx as ox


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GRAPH_PATH = PROJECT_ROOT / "data" / "raw" / "bengaluru_drive.graphml"
OUTPUT_PATH = PROJECT_ROOT / "data" / "processed" / "bengaluru_travel_time.graphml"

# Conservative free-flow estimates for Bengaluru.
# Used only when an OSM maxspeed value is unavailable.
ROAD_SPEEDS_KMH = {
    "motorway": 80,
    "motorway_link": 50,
    "trunk": 70,
    "trunk_link": 45,
    "primary": 50,
    "primary_link": 40,
    "secondary": 40,
    "secondary_link": 35,
    "tertiary": 35,
    "tertiary_link": 30,
    "residential": 25,
    "living_street": 15,
    "unclassified": 25,
    "road": 25,
    "busway": 30,
}


def parse_speed(value) -> float | None:
    """Extract a km/h speed from an OSM maxspeed value."""
    if value is None:
        return None

    if isinstance(value, list):
        values = [parse_speed(v) for v in value]
        values = [v for v in values if v is not None]
        return sum(values) / len(values) if values else None

    text = str(value).strip().lower()

    # Extract the first numeric value.
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return None

    speed = float(match.group())

    # Convert mph if explicitly specified.
    if "mph" in text:
        speed *= 1.60934

    # Reject obviously invalid values.
    if speed <= 0 or speed > 150:
        return None

    return speed


def road_class(value) -> str:
    """Normalize OSM highway classification."""
    if isinstance(value, list):
        return str(value[0]) if value else "unclassified"
    return str(value)


def main() -> None:
    print("Loading Bengaluru road graph...")
    graph = ox.load_graphml(GRAPH_PATH)

    explicit_speed = 0
    fallback_speed = 0

    for _, _, data in graph.edges(data=True):
        highway = road_class(data.get("highway"))
        speed_kmh = parse_speed(data.get("maxspeed"))

        if speed_kmh is not None:
            explicit_speed += 1
        else:
            speed_kmh = ROAD_SPEEDS_KMH.get(
                highway,
                ROAD_SPEEDS_KMH["unclassified"],
            )
            fallback_speed += 1

        data["speed_kmh"] = float(speed_kmh)

        length_m = float(data["length"])
        speed_mps = speed_kmh / 3.6

        # Travel time in seconds.
        data["travel_time"] = length_m / speed_mps

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ox.save_graphml(graph, OUTPUT_PATH)

    print()
    print("Travel-time network built successfully.")
    print(f"Nodes: {len(graph.nodes):,}")
    print(f"Edges: {len(graph.edges):,}")
    print(f"OSM maxspeed used: {explicit_speed:,}")
    print(f"Fallback road-class speed: {fallback_speed:,}")
    print(f"Saved: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()