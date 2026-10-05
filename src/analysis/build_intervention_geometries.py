from __future__ import annotations

import json
from pathlib import Path

import networkx as nx
import pandas as pd
from shapely import wkt
from shapely.geometry import LineString, Point, mapping


ROOT = Path(__file__).resolve().parents[2]

GRAPH_PATH = ROOT / "data" / "processed" / "bengaluru_travel_time.graphml"
INTERVENTION_DIR = ROOT / "data" / "processed" / "interventions"

RANKING_PATH = INTERVENTION_DIR / "intervention_ranking.csv"
EFFECTS_PATH = INTERVENTION_DIR / "intervention_origin_effects.csv"
EDGE_FREQ_PATH = INTERVENTION_DIR / "candidate_corridor_edge_frequency.csv"

OUTPUT_DIR = INTERVENTION_DIR / "geometries"


def safe_float(value, default=0.0):
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def resolve_node(graph_lookup, value):
    """Resolve CSV node IDs against GraphML node IDs."""
    key = str(value)

    if key in graph_lookup:
        return graph_lookup[key]

    # Handle values such as 123.0 coming from CSV parsing.
    try:
        numeric = float(value)
        if numeric.is_integer():
            key = str(int(numeric))
            if key in graph_lookup:
                return graph_lookup[key]
    except (TypeError, ValueError):
        pass

    return None


def edge_geometry(G, u, v):
    """
    Recover geometry for a physical road segment.

    The intervention experiment treats u-v as one physical segment even
    when the underlying network contains both directed representations.
    """

    candidates = []

    for a, b in [(u, v), (v, u)]:
        if not G.has_edge(a, b):
            continue

        data = G.get_edge_data(a, b)

        if not data:
            continue

        for key, attrs in data.items():
            candidates.append((key, attrs))

    # Prefer actual OSM geometry.
    for _, attrs in candidates:
        geometry = attrs.get("geometry")

        if geometry is None:
            continue

        if hasattr(geometry, "geom_type"):
            return geometry

        if isinstance(geometry, str):
            try:
                return wkt.loads(geometry)
            except Exception:
                pass

    # Fallback to straight line between node coordinates.
    if u not in G.nodes or v not in G.nodes:
        return None

    u_data = G.nodes[u]
    v_data = G.nodes[v]

    if "x" not in u_data or "y" not in u_data:
        return None

    if "x" not in v_data or "y" not in v_data:
        return None

    return LineString(
        [
            (float(u_data["x"]), float(u_data["y"])),
            (float(v_data["x"]), float(v_data["y"])),
        ]
    )


def write_geojson(path: Path, features):
    payload = {
        "type": "FeatureCollection",
        "features": features,
    }

    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    print(f"  Wrote: {path.relative_to(ROOT)}")


def main():
    print("=" * 80)
    print("BUILD INTERVENTION GEOMETRIES")
    print("=" * 80)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 1. Load intervention results
    # ------------------------------------------------------------------
    print("\n[1/7] Loading intervention results...")

    ranking = pd.read_csv(RANKING_PATH)
    effects = pd.read_csv(EFFECTS_PATH)
    edge_freq = pd.read_csv(EDGE_FREQ_PATH)

    print(f"  Candidates: {len(ranking):,}")
    print(f"  Effect rows: {len(effects):,}")
    print(f"  Corridor edges: {len(edge_freq):,}")

    # ------------------------------------------------------------------
    # 2. Load network
    # ------------------------------------------------------------------
    print("\n[2/7] Loading Bengaluru network...")

    G = nx.read_graphml(GRAPH_PATH)

    print(f"  Nodes: {G.number_of_nodes():,}")
    print(f"  Edges: {G.number_of_edges():,}")

    graph_node_lookup = {
        str(node): node
        for node in G.nodes
    }

    # ------------------------------------------------------------------
    # 3. Identify winner
    # ------------------------------------------------------------------
    print("\n[3/7] Identifying winning intervention...")

    ranking = ranking.sort_values(
        by="impact_rank",
        ascending=True,
    ).reset_index(drop=True)

    winner = ranking.iloc[0]

    winner_candidate_id = str(winner["candidate_id"])
    winner_origin_id = int(winner["origin_id"])

    print(f"  Winning candidate: {winner_candidate_id}")
    print(f"  Winning origin: {winner_origin_id}")
    print(
        "  Total gain: "
        f"{winner['total_access_gain_pct_points']:.4f} pp"
    )
    print(
        "  Disadvantaged gain: "
        f"{winner['disadvantaged_total_gain']:.4f} pp"
    )

    # ------------------------------------------------------------------
    # 4. Build corridor geometries
    # ------------------------------------------------------------------
    print("\n[4/7] Building corridor geometries...")

    corridor_features = []
    winning_features = []

    if "candidate_id" not in edge_freq.columns:
        raise ValueError(
            "candidate_corridor_edge_frequency.csv must contain "
            "'candidate_id'."
        )

    for _, row in edge_freq.iterrows():

        candidate_id = str(row["candidate_id"])

        u = resolve_node(
            graph_node_lookup,
            row["u"],
        )

        v = resolve_node(
            graph_node_lookup,
            row["v"],
        )

        if u is None or v is None:
            continue

        geometry = edge_geometry(
            G,
            u,
            v,
        )

        if geometry is None:
            continue

        path_frequency = safe_float(
            row.get("path_frequency"),
            1.0,
        )

        feature = {
            "type": "Feature",
            "geometry": mapping(geometry),
            "properties": {
                "candidate_id": candidate_id,
                "origin_id": int(row["origin_id"])
                if "origin_id" in row
                else None,
                "u": str(u),
                "v": str(v),
                "path_frequency": path_frequency,
                "is_winner": (
                    candidate_id == winner_candidate_id
                ),
            },
        }

        corridor_features.append(feature)

        if candidate_id == winner_candidate_id:
            winning_features.append(feature)

    print(
        f"  Total corridor features: "
        f"{len(corridor_features):,}"
    )

    print(
        f"  Winning corridor features: "
        f"{len(winning_features):,}"
    )

    write_geojson(
        OUTPUT_DIR / "all_candidate_corridors.geojson",
        corridor_features,
    )

    write_geojson(
        OUTPUT_DIR / "winning_corridor.geojson",
        winning_features,
    )

    # ------------------------------------------------------------------
    # 5. Candidate origins
    # ------------------------------------------------------------------
    print("\n[5/7] Building candidate origin geometry...")

    origin_features = []

    for rank_index, row in ranking.iterrows():

        origin_id = int(row["origin_id"])

        latitude = safe_float(
            row["latitude"],
            None,
        )

        longitude = safe_float(
            row["longitude"],
            None,
        )

        if latitude is None or longitude is None:
            continue

        feature = {
            "type": "Feature",
            "geometry": mapping(
                Point(
                    longitude,
                    latitude,
                )
            ),
            "properties": {
                "candidate_id": str(
                    row["candidate_id"]
                ),
                "origin_id": origin_id,
                "impact_rank": int(
                    row["impact_rank"]
                ),
                "latitude": latitude,
                "longitude": longitude,
                "baseline_access_pct": safe_float(
                    row["baseline_access_pct"]
                ),
                "physical_intervention_segments": int(
                    row["physical_intervention_segments"]
                ),
                "directed_edges_improved": int(
                    row["directed_edges_improved"]
                ),
                "destinations_used": int(
                    row["destinations_used"]
                ),
                "total_access_gain_pct_points": safe_float(
                    row["total_access_gain_pct_points"]
                ),
                "origins_affected": int(
                    row["origins_affected"]
                ),
                "disadvantaged_total_gain": safe_float(
                    row["disadvantaged_total_gain"]
                ),
                "gain_per_physical_segment": safe_float(
                    row["gain_per_physical_segment"]
                ),
                "disadvantaged_gain_per_segment": safe_float(
                    row["disadvantaged_gain_per_segment"]
                ),
                "is_winner": (
                    str(row["candidate_id"])
                    == winner_candidate_id
                ),
            },
        }

        origin_features.append(feature)

    write_geojson(
        OUTPUT_DIR / "candidate_origins.geojson",
        origin_features,
    )

    # ------------------------------------------------------------------
    # 6. Winning intervention affected-origin map
    # ------------------------------------------------------------------
    print("\n[6/7] Building affected-origin geometry...")

    winner_effects = effects.copy()

    # The intervention engine may identify the candidate through
    # candidate_id or origin_id depending on the generated schema.
    if "candidate_id" in winner_effects.columns:
        winner_effects = winner_effects[
            winner_effects["candidate_id"].astype(str)
            == winner_candidate_id
        ]
    elif "origin_id" in winner_effects.columns:
        winner_effects = winner_effects[
            winner_effects["origin_id"].astype(int)
            == winner_origin_id
        ]

    print(
        f"  Winner effect rows: "
        f"{len(winner_effects):,}"
    )

    # Identify the gain column used by the experiment.
    gain_column = None

    for candidate in [
        "access_gain_pct_points",
        "gain_pct_points",
        "combined_gain_pct_points",
        "gain_pp",
        "accessibility_gain_pp",
        "total_gain_pp",
    ]:
        if candidate in winner_effects.columns:
            gain_column = candidate
            break

    # If no obvious gain column exists, infer it from the difference
    # between baseline and post-intervention accessibility.
    if gain_column is None:
        baseline_candidates = [
            "baseline_access_pct",
            "baseline_accessibility_pct",
        ]

        after_candidates = [
            "after_access_pct",
            "post_access_pct",
            "intervention_access_pct",
            "new_access_pct",
        ]

        baseline_column = next(
            (
                c
                for c in baseline_candidates
                if c in winner_effects.columns
            ),
            None,
        )

        after_column = next(
            (
                c
                for c in after_candidates
                if c in winner_effects.columns
            ),
            None,
        )

        if (
            baseline_column is not None
            and after_column is not None
        ):
            winner_effects = winner_effects.copy()

            winner_effects["_derived_gain_pp"] = (
                winner_effects[after_column]
                - winner_effects[baseline_column]
            )

            gain_column = "_derived_gain_pp"

    affected_features = []

    for _, row in winner_effects.iterrows():

        latitude = safe_float(
            row.get("latitude"),
            None,
        )

        longitude = safe_float(
            row.get("longitude"),
            None,
        )

        # Some versions use origin_latitude/origin_longitude.
        if latitude is None:
            latitude = safe_float(
                row.get("origin_latitude"),
                None,
            )

        if longitude is None:
            longitude = safe_float(
                row.get("origin_longitude"),
                None,
            )

        if latitude is None or longitude is None:
            continue

        gain = (
            safe_float(
                row.get(gain_column),
                0,
            )
            if gain_column
            else 0
        )

        if gain <= 0:
            continue

        properties = {
            "gain_pp": gain,
        }

        # Preserve useful experiment fields if present.
        for field in [
            "origin_id",
            "affected_origin_id",
            "baseline_access_pct",
            "after_access_pct",
            "health_gain_pp",
            "education_gain_pp",
            "employment_gain_pp",
            "combined_gain_pct_points",
        ]:
            if field in row.index:
                value = row[field]

                if pd.isna(value):
                    continue

                try:
                    if field in {
                        "origin_id",
                        "affected_origin_id",
                    }:
                        value = int(value)
                    else:
                        value = float(value)
                except (TypeError, ValueError):
                    value = str(value)

                properties[field] = value

        feature = {
            "type": "Feature",
            "geometry": mapping(
                Point(
                    longitude,
                    latitude,
                )
            ),
            "properties": properties,
        }

        affected_features.append(feature)

    write_geojson(
        OUTPUT_DIR / "winning_affected_origins.geojson",
        affected_features,
    )

    # ------------------------------------------------------------------
    # 7. Machine-readable summary
    # ------------------------------------------------------------------
    print("\n[7/7] Writing intervention summary...")

    summary = {
        "project": "How Far Away Is Your Life?",
        "experiment": {
            "hour": 13,
            "threshold_minutes": 30,
            "travel_time_improvement_pct": 20,
            "physical_segment_budget": 50,
            "method": (
                "Counterfactual intervention on the highest-frequency "
                "physical road segments appearing in shortest paths "
                "from candidate low-access origins to nearby health "
                "and education opportunities."
            ),
        },
        "winner": {
            "candidate_id": winner_candidate_id,
            "origin_id": winner_origin_id,
            "impact_rank": int(
                winner["impact_rank"]
            ),
            "latitude": safe_float(
                winner["latitude"]
            ),
            "longitude": safe_float(
                winner["longitude"]
            ),
            "baseline_access_pct": safe_float(
                winner["baseline_access_pct"]
            ),
            "physical_intervention_segments": int(
                winner["physical_intervention_segments"]
            ),
            "directed_edges_improved": int(
                winner["directed_edges_improved"]
            ),
            "destinations_used": int(
                winner["destinations_used"]
            ),
            "total_access_gain_pp": safe_float(
                winner[
                    "total_access_gain_pct_points"
                ]
            ),
            "mean_access_gain_pp": safe_float(
                winner[
                    "mean_access_gain_pct_points"
                ]
            ),
            "max_single_origin_gain_pp": safe_float(
                winner[
                    "max_single_origin_gain_pct_points"
                ]
            ),
            "origins_affected": int(
                winner["origins_affected"]
            ),
            "disadvantaged_total_gain_pp": safe_float(
                winner[
                    "disadvantaged_total_gain"
                ]
            ),
            "disadvantaged_mean_gain_pp": safe_float(
                winner[
                    "disadvantaged_mean_gain"
                ]
            ),
            "gain_per_physical_segment": safe_float(
                winner[
                    "gain_per_physical_segment"
                ]
            ),
            "disadvantaged_gain_per_segment": safe_float(
                winner[
                    "disadvantaged_gain_per_segment"
                ]
            ),
            "corridor_segments_rendered": len(
                winning_features
            ),
            "affected_origins_rendered": len(
                affected_features
            ),
        },
        "outputs": {
            "winning_corridor": (
                "winning_corridor.geojson"
            ),
            "all_candidate_corridors": (
                "all_candidate_corridors.geojson"
            ),
            "candidate_origins": (
                "candidate_origins.geojson"
            ),
            "winning_affected_origins": (
                "winning_affected_origins.geojson"
            ),
        },
        "caveat": (
            "This is a counterfactual experiment, not a "
            "prediction of a real infrastructure project or "
            "a globally optimal network intervention."
        ),
    }

    summary_path = (
        OUTPUT_DIR
        / "winning_intervention_summary.json"
    )

    with summary_path.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            summary,
            f,
            indent=2,
        )

    print(
        "  Wrote: "
        f"{summary_path.relative_to(ROOT)}"
    )

    print("\n" + "=" * 80)
    print("GEOMETRY BUILD COMPLETE")
    print("=" * 80)

    print("\nWinning intervention:")
    print(
        f"  Candidate: {winner_candidate_id}"
    )
    print(
        f"  Origin: {winner_origin_id}"
    )
    print(
        "  Total modeled gain: "
        f"{winner['total_access_gain_pct_points']:.4f} pp"
    )
    print(
        "  Disadvantaged gain: "
        f"{winner['disadvantaged_total_gain']:.4f} pp"
    )
    print(
        "  Physical segments: "
        f"{int(winner['physical_intervention_segments'])}"
    )
    print(
        "  Affected origins: "
        f"{int(winner['origins_affected'])}"
    )
    print(
        "  Corridor features rendered: "
        f"{len(winning_features):,}"
    )
    print(
        "  Affected-origin features rendered: "
        f"{len(affected_features):,}"
    )


if __name__ == "__main__":
    main()