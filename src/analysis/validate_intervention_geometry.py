from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import pandas as pd
from shapely.geometry import shape


ROOT = Path(__file__).resolve().parents[2]

INTERVENTION_DIR = ROOT / "data" / "processed" / "interventions"
GEOMETRY_DIR = INTERVENTION_DIR / "geometries"

WINNING_PATH = GEOMETRY_DIR / "winning_corridor.geojson"
RANKING_PATH = INTERVENTION_DIR / "intervention_ranking.csv"


def haversine_km(lat1, lon1, lat2, lon2):
    """Approximate great-circle distance between two coordinates."""
    from math import radians, sin, cos, sqrt, atan2

    R = 6371.0

    lat1 = radians(lat1)
    lat2 = radians(lat2)
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = (
        sin(dlat / 2) ** 2
        + cos(lat1)
        * cos(lat2)
        * sin(dlon / 2) ** 2
    )

    return 2 * R * atan2(sqrt(a), sqrt(1 - a))


def main():
    print("=" * 80)
    print("INTERVENTION GEOMETRY VALIDATION")
    print("=" * 80)

    # ------------------------------------------------------------------
    # 1. Load winning corridor
    # ------------------------------------------------------------------
    print("\n[1/6] Loading winning corridor...")

    with WINNING_PATH.open("r", encoding="utf-8") as f:
        geojson = json.load(f)

    features = geojson["features"]

    print(f"  Corridor segments: {len(features):,}")

    if len(features) != 50:
        print(
            f"  WARNING: expected 50 physical segments, "
            f"found {len(features)}."
        )

    # ------------------------------------------------------------------
    # 2. Extract physical segment graph
    # ------------------------------------------------------------------
    print("\n[2/6] Building corridor connectivity graph...")

    corridor = nx.Graph()

    rows = []

    for feature in features:
        props = feature["properties"]

        u = str(props["u"])
        v = str(props["v"])

        corridor.add_edge(
            u,
            v,
            path_frequency=float(
                props.get("path_frequency", 0)
            ),
        )

        geometry = shape(feature["geometry"])

        rows.append(
            {
                "u": u,
                "v": v,
                "path_frequency": float(
                    props.get("path_frequency", 0)
                ),
                "geometry": geometry,
            }
        )

    df = pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # 3. Connectivity
    # ------------------------------------------------------------------
    print("\n[3/6] Testing corridor connectivity...")

    components = list(
        nx.connected_components(corridor)
    )

    components = sorted(
        components,
        key=len,
        reverse=True,
    )

    print(
        f"  Connected components: "
        f"{len(components)}"
    )

    print(
        "  Largest component nodes: "
        f"{len(components[0]):,}"
    )

    if len(components) > 1:
        print("\n  Component sizes:")
        for i, component in enumerate(
            components,
            start=1,
        ):
            print(
                f"    Component {i}: "
                f"{len(component):,} nodes"
            )

    # Edge-level component assignment.
    component_lookup = {}

    for component_id, component in enumerate(
        components,
        start=1,
    ):
        for node in component:
            component_lookup[node] = component_id

    df["component"] = df.apply(
        lambda row: component_lookup[row["u"]],
        axis=1,
    )

    component_edge_counts = (
        df["component"]
        .value_counts()
        .sort_values(ascending=False)
    )

    # ------------------------------------------------------------------
    # 4. Segment geometry statistics
    # ------------------------------------------------------------------
    print("\n[4/6] Measuring corridor geometry...")

    lengths = []

    for geometry in df["geometry"]:
        # Geometry is WGS84. Approximate local metric length using
        # latitude/longitude endpoints. For curved LineStrings, sum
        # consecutive point-to-point distances.
        coords = list(geometry.coords)

        total_km = 0.0

        for i in range(len(coords) - 1):
            lon1, lat1 = coords[i]
            lon2, lat2 = coords[i + 1]

            total_km += haversine_km(
                lat1,
                lon1,
                lat2,
                lon2,
            )

        lengths.append(total_km)

    df["length_km"] = lengths

    total_length = df["length_km"].sum()
    median_length = df["length_km"].median()
    max_length = df["length_km"].max()

    print(
        f"  Total modeled corridor length: "
        f"{total_length:.2f} km"
    )

    print(
        f"  Median segment length: "
        f"{median_length:.3f} km"
    )

    print(
        f"  Longest segment: "
        f"{max_length:.3f} km"
    )

    # ------------------------------------------------------------------
    # 5. Path-frequency concentration
    # ------------------------------------------------------------------
    print("\n[5/6] Measuring path-frequency concentration...")

    df = df.sort_values(
        "path_frequency",
        ascending=False,
    ).reset_index(drop=True)

    total_frequency = df["path_frequency"].sum()

    top_5_frequency = df.head(5)[
        "path_frequency"
    ].sum()

    top_10_frequency = df.head(10)[
        "path_frequency"
    ].sum()

    print(
        f"  Total path-frequency score: "
        f"{total_frequency:.0f}"
    )

    if total_frequency > 0:
        print(
            "  Top 5 share: "
            f"{100 * top_5_frequency / total_frequency:.1f}%"
        )

        print(
            "  Top 10 share: "
            f"{100 * top_10_frequency / total_frequency:.1f}%"
        )

    print("\n  Highest-frequency segments:")

    for i, row in df.head(10).iterrows():
        print(
            f"    {i + 1:2d}. "
            f"{row['u']} -> {row['v']} | "
            f"frequency={row['path_frequency']:.0f} | "
            f"length={row['length_km']:.3f} km"
        )

    # ------------------------------------------------------------------
    # 6. Geographic coherence verdict
    # ------------------------------------------------------------------
    print("\n[6/6] Evaluating corridor coherence...")

    largest_component_edges = component_edge_counts.iloc[0]

    if len(features) > 0:
        largest_component_share = (
            largest_component_edges / len(features)
        )
    else:
        largest_component_share = 0.0

    # A corridor is considered geographically coherent when:
    #
    # 1. Most selected physical segments belong to one connected
    #    component.
    #
    # 2. The corridor is not composed of many isolated fragments.
    #
    # 3. Its total length is plausible for a local accessibility
    #    intervention.
    #
    # This is a diagnostic, not a scientific truth criterion.

    if (
        len(components) == 1
        and largest_component_share >= 0.90
    ):
        verdict = "COHERENT"

    elif largest_component_share >= 0.75:
        verdict = "MOSTLY COHERENT"

    else:
        verdict = "FRAGMENTED"

    print("\n" + "-" * 80)
    print("GEOGRAPHIC VALIDATION RESULT")
    print("-" * 80)

    print(
        f"  Verdict: {verdict}"
    )

    print(
        f"  Connected components: "
        f"{len(components)}"
    )

    print(
        f"  Largest component share: "
        f"{100 * largest_component_share:.1f}%"
    )

    print(
        f"  Total corridor length: "
        f"{total_length:.2f} km"
    )

    print(
        f"  Segments evaluated: "
        f"{len(features)}"
    )

    # ------------------------------------------------------------------
    # Compare against ranking metadata
    # ------------------------------------------------------------------
    if RANKING_PATH.exists():
        ranking = pd.read_csv(
            RANKING_PATH
        )

        winner = ranking.sort_values(
            "impact_rank"
        ).iloc[0]

        print("\nWinner metadata:")
        print(
            f"  Candidate: "
            f"{winner['candidate_id']}"
        )

        print(
            f"  Origin: "
            f"{int(winner['origin_id'])}"
        )

        print(
            "  Modeled accessibility gain: "
            f"{winner['total_access_gain_pct_points']:.4f} pp"
        )

        print(
            "  Disadvantaged gain: "
            f"{winner['disadvantaged_total_gain']:.4f} pp"
        )

    # ------------------------------------------------------------------
    # Save validation report
    # ------------------------------------------------------------------
    report = {
        "segments": len(features),
        "connected_components": len(components),
        "largest_component_edges": int(
            largest_component_edges
        ),
        "largest_component_share": float(
            largest_component_share
        ),
        "total_corridor_length_km": float(
            total_length
        ),
        "median_segment_length_km": float(
            median_length
        ),
        "max_segment_length_km": float(
            max_length
        ),
        "total_path_frequency": float(
            total_frequency
        ),
        "top_5_frequency_share": (
            float(
                top_5_frequency
                / total_frequency
            )
            if total_frequency > 0
            else 0.0
        ),
        "top_10_frequency_share": (
            float(
                top_10_frequency
                / total_frequency
            )
            if total_frequency > 0
            else 0.0
        ),
        "verdict": verdict,
    }

    report_path = (
        GEOMETRY_DIR
        / "winning_corridor_validation.json"
    )

    with report_path.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            report,
            f,
            indent=2,
        )

    print(
        f"\n  Validation report written to:"
        f"\n  {report_path.relative_to(ROOT)}"
    )

    print("\n" + "=" * 80)
    print("VALIDATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()