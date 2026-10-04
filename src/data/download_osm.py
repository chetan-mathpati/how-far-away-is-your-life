from pathlib import Path

import osmnx as ox


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = OUTPUT_DIR / "bengaluru_drive.graphml"


def main() -> None:
    print("Downloading Bengaluru road network from OpenStreetMap...")

    ox.settings.use_cache = True
    ox.settings.log_console = True

    graph = ox.graph.graph_from_place(
        "Bengaluru, Karnataka, India",
        network_type="drive",
        simplify=True,
        retain_all=False,
    )

    print(f"Nodes: {len(graph.nodes):,}")
    print(f"Edges: {len(graph.edges):,}")

    ox.io.save_graphml(graph, OUTPUT_FILE)

    print(f"Saved: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()