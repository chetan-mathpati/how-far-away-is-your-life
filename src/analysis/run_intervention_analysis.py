from pathlib import Path
from collections import Counter

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.sparse.csgraph import dijkstra


PROJECT_ROOT = Path(__file__).resolve().parents[2]

GRAPH_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "bengaluru_travel_time.graphml"
)

CALIBRATION_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "spatial_traffic"
    / "edge_spatial_calibration.csv"
)

SURFACE_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "accessibility_surface"
    / "bengaluru_accessibility_surface.csv"
)

ORIGINS_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "citywide"
    / "citywide_origins.csv"
)

HEALTH_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "bengaluru_health_attached.csv"
)

EDUCATION_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "bengaluru_education_attached.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "interventions"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================================
# EXPERIMENT DESIGN
# ============================================================================

HOUR = 13

THRESHOLD_MINUTES = 30

# Counterfactual:
# selected physical road segments become 20% faster.
IMPROVEMENT = 0.20

# Number of lowest-access origins used to generate candidate corridors.
N_CANDIDATES = 10

# Number of nearest opportunity destinations considered per domain.
DESTINATIONS_PER_CATEGORY = 20

# IMPORTANT:
# This is a PHYSICAL ROAD SEGMENT budget.
#
# If a road exists in both directions:
#
#     A -> B
#     B -> A
#
# it counts as ONE physical segment.
#
# Both directions receive the intervention.
MAX_INTERVENTION_EDGES = 50

# Ignore destinations farther than this from a candidate origin.
MAX_DESTINATION_DISTANCE_MINUTES = 60

# Sparse Dijkstra batch size.
BATCH_SIZE = 20


# ============================================================================
# LOAD NETWORK
# ============================================================================

def load_graph_nodes():

    import networkx as nx

    print("Loading canonical road network...")

    G = nx.read_graphml(
        GRAPH_FILE
    )

    G = nx.relabel_nodes(
        G,
        {
            node: str(node)
            for node in G.nodes
        },
    )

    node_ids = np.array(
        list(G.nodes),
        dtype=str,
    )

    node_index = {
        node_id: i
        for i, node_id in enumerate(node_ids)
    }

    return G, node_ids, node_index


# ============================================================================
# BUILD SPARSE GRAPH
# ============================================================================

def build_sparse_graph(
    calibration,
    node_index,
    improvement_edges=None,
):

    df = calibration[
        calibration["hour"].astype(int) == HOUR
    ].copy()

    u = (
        df["u"]
        .astype(str)
        .map(node_index)
        .to_numpy()
    )

    v = (
        df["v"]
        .astype(str)
        .map(node_index)
        .to_numpy()
    )

    # copy=True is important because pandas may expose
    # a read-only NumPy view.
    weights = (
        df["calibrated_travel_time_s"]
        .astype(float)
        .to_numpy(copy=True)
    )

    if improvement_edges:

        edge_pairs = list(
            zip(
                df["u"].astype(str),
                df["v"].astype(str),
            )
        )

        mask = np.fromiter(
            (
                pair in improvement_edges
                for pair in edge_pairs
            ),
            dtype=bool,
            count=len(edge_pairs),
        )

        weights[mask] *= (
            1.0 - IMPROVEMENT
        )

    graph = sp.csr_matrix(
        (
            weights,
            (u, v),
        ),
        shape=(
            len(node_index),
            len(node_index),
        ),
    )

    return graph


# ============================================================================
# OPPORTUNITY NODES
# ============================================================================

def get_opportunity_nodes(
    path,
    node_index,
):

    df = pd.read_csv(path)

    if "network_node" not in df.columns:
        raise ValueError(
            f"{path.name} does not contain "
            "'network_node'. "
            f"Columns found: {df.columns.tolist()}"
        )

    nodes = (
        df["network_node"]
        .dropna()
        .astype(str)
        .unique()
    )

    valid = [
        node_index[node]
        for node in nodes
        if node in node_index
    ]

    return np.array(
        sorted(set(valid)),
        dtype=np.int64,
    )


# ============================================================================
# SHORTEST-PATH RECONSTRUCTION
# ============================================================================

def reconstruct_path(
    predecessors,
    source_idx,
    target_idx,
):

    path = []

    current = int(
        target_idx
    )

    if current == source_idx:
        return []

    while (
        current != source_idx
        and current >= 0
    ):

        path.append(
            current
        )

        previous = int(
            predecessors[current]
        )

        if previous < 0:
            return []

        current = previous

    path.append(
        source_idx
    )

    path.reverse()

    return path


# ============================================================================
# PATH -> DIRECTED EDGES
# ============================================================================

def path_to_edges(
    path,
    node_ids,
):

    edges = []

    for u_idx, v_idx in zip(
        path[:-1],
        path[1:],
    ):

        edges.append(
            (
                node_ids[u_idx],
                node_ids[v_idx],
            )
        )

    return edges


# ============================================================================
# ACCESSIBILITY
# ============================================================================

def calculate_accessibility(
    graph,
    origin_indices,
    opportunity_nodes,
    threshold_seconds,
):

    opportunity_nodes = np.asarray(
        opportunity_nodes,
        dtype=np.int64,
    )

    total = len(
        opportunity_nodes
    )

    if total == 0:
        raise ValueError(
            "No opportunity nodes available."
        )

    results = []

    for start in range(
        0,
        len(origin_indices),
        BATCH_SIZE,
    ):

        batch = origin_indices[
            start:start + BATCH_SIZE
        ]

        distances = dijkstra(
            graph,
            directed=True,
            indices=batch,
            limit=threshold_seconds,
        )

        for row in range(
            len(batch)
        ):

            reachable = (
                distances[
                    row,
                    opportunity_nodes,
                ]
                <= threshold_seconds
            )

            count = int(
                np.sum(reachable)
            )

            results.append(
                count
                / total
                * 100.0
            )

    return np.asarray(
        results,
        dtype=float,
    )


# ============================================================================
# BUILD MULTI-DESTINATION CANDIDATE CORRIDOR
# ============================================================================

def build_candidate_corridor(
    origin_row,
    origin_position,
    distances,
    predecessors,
    node_ids,
    health_nodes,
    education_nodes,
    calibration,
):
    """
    Build a candidate intervention corridor from multiple destinations.

    For each disadvantaged origin:

        - up to 20 nearest health opportunities
        - up to 20 nearest education opportunities

    are considered.

    Every shortest path is traced.

    Road segments receive a frequency equal to the number of
    opportunity-access paths that use them.

    The top 50 PHYSICAL road segments are selected.

    A bidirectional road counts as one physical segment.
    If both directions exist in the network, both directions receive
    the 20% travel-time improvement.
    """

    source_idx = int(
        origin_row["node_idx"]
    )

    destination_groups = [
        (
            "health",
            health_nodes,
        ),
        (
            "education",
            education_nodes,
        ),
    ]

    # Directed edge frequency.
    edge_frequency = Counter()

    # Final destination diagnostics.
    destination_records = []

    for category, nodes in destination_groups:

        node_distances = (
            distances[
                origin_position,
                nodes,
            ]
        )

        valid_positions = np.where(
            np.isfinite(
                node_distances
            )
        )[0]

        if len(valid_positions) == 0:
            continue

        max_seconds = (
            MAX_DESTINATION_DISTANCE_MINUTES
            * 60
        )

        valid_positions = [
            position
            for position in valid_positions
            if node_distances[position]
            <= max_seconds
        ]

        valid_positions = sorted(
            valid_positions,
            key=lambda position:
                node_distances[position],
        )

        valid_positions = valid_positions[
            :DESTINATIONS_PER_CATEGORY
        ]

        for position in valid_positions:

            target_idx = int(
                nodes[position]
            )

            distance_seconds = float(
                node_distances[position]
            )

            path = reconstruct_path(
                predecessors[
                    origin_position
                ],
                source_idx,
                target_idx,
            )

            if len(path) < 2:
                continue

            edges = path_to_edges(
                path,
                node_ids,
            )

            for edge in edges:
                edge_frequency[
                    edge
                ] += 1

            destination_records.append(
                {
                    "category": category,
                    "target_node": node_ids[
                        target_idx
                    ],
                    "travel_time_minutes": (
                        distance_seconds
                        / 60.0
                    ),
                    "path_edges": len(
                        edges
                    ),
                }
            )

    # ------------------------------------------------------------------
    # Convert directed edges into PHYSICAL segments.
    #
    # A->B and B->A are the same physical road segment.
    # ------------------------------------------------------------------

    physical_frequency = Counter()

    for (
        (u, v),
        frequency,
    ) in edge_frequency.items():

        physical_key = tuple(
            sorted(
                [u, v]
            )
        )

        physical_frequency[
            physical_key
        ] += frequency

    # ------------------------------------------------------------------
    # Rank physical segments by repeated path usage.
    # ------------------------------------------------------------------

    ranked_physical_segments = sorted(
        physical_frequency.items(),
        key=lambda item: (
            -item[1],
            item[0][0],
            item[0][1],
        ),
    )

    selected_physical_segments = (
        ranked_physical_segments[
            :MAX_INTERVENTION_EDGES
        ]
    )

    # ------------------------------------------------------------------
    # Existing directed network edges.
    # ------------------------------------------------------------------

    existing_directed_edges = set(
        zip(
            calibration["u"].astype(str),
            calibration["v"].astype(str),
        )
    )

    # ------------------------------------------------------------------
    # Expand physical segments into directed edges.
    #
    # A physical segment still counts as ONE intervention even when
    # both directional graph edges exist.
    # ------------------------------------------------------------------

    selected_edges = set()

    selected_frequency_rows = []

    for (
        (u, v),
        frequency,
    ) in selected_physical_segments:

        if (u, v) in existing_directed_edges:

            selected_edges.add(
                (u, v)
            )

        if (v, u) in existing_directed_edges:

            selected_edges.add(
                (v, u)
            )

        selected_frequency_rows.append(
            {
                "u": u,
                "v": v,
                "path_frequency": frequency,
                "selected": True,
            }
        )

    return (
        selected_edges,
        physical_frequency,
        destination_records,
        selected_frequency_rows,
    )


# ============================================================================
# MAIN
# ============================================================================

def main():

    print("=" * 80)
    print(
        "MULTI-DESTINATION COUNTERFACTUAL "
        "INTERVENTION ANALYSIS"
    )
    print("=" * 80)

    print()
    print("Experiment design:")
    print(
        f"  Evaluation time: {HOUR}:00"
    )
    print(
        f"  Accessibility threshold: "
        f"{THRESHOLD_MINUTES} minutes"
    )
    print(
        f"  Counterfactual improvement: "
        f"{IMPROVEMENT * 100:.0f}%"
    )
    print(
        f"  Candidate origins: "
        f"{N_CANDIDATES}"
    )
    print(
        f"  Destinations/category: "
        f"{DESTINATIONS_PER_CATEGORY}"
    )
    print(
        f"  Physical road-segment budget: "
        f"{MAX_INTERVENTION_EDGES}"
    )

    # ==================================================================
    # NETWORK
    # ==================================================================

    G, node_ids, node_index = (
        load_graph_nodes()
    )

    print(
        f"Network nodes: "
        f"{len(node_ids):,}"
    )

    # ==================================================================
    # CALIBRATION
    # ==================================================================

    calibration = pd.read_csv(
        CALIBRATION_FILE
    )

    calibration["hour"] = (
        calibration["hour"]
        .astype(int)
    )

    print(
        f"Calibration rows: "
        f"{len(calibration):,}"
    )

    # ==================================================================
    # BASELINE GRAPH
    # ==================================================================

    baseline_graph = build_sparse_graph(
        calibration,
        node_index,
    )

    print(
        f"Baseline graph connections: "
        f"{baseline_graph.nnz:,}"
    )

    # ==================================================================
    # ORIGINS
    # ==================================================================

    origins = pd.read_csv(
        ORIGINS_FILE
    )

    origins["node"] = (
        origins["node"]
        .astype(str)
    )

    origins = origins[
        origins["node"].isin(
            node_index
        )
    ].copy()

    origins["node_idx"] = (
        origins["node"]
        .map(node_index)
        .astype(int)
    )

    origins = (
        origins
        .sort_values(
            "origin_id"
        )
        .reset_index(
            drop=True
        )
    )

    # ==================================================================
    # OPPORTUNITIES
    # ==================================================================

    health_nodes = (
        get_opportunity_nodes(
            HEALTH_FILE,
            node_index,
        )
    )

    education_nodes = (
        get_opportunity_nodes(
            EDUCATION_FILE,
            node_index,
        )
    )

    print()
    print(
        f"Health opportunity nodes: "
        f"{len(health_nodes):,}"
    )

    print(
        f"Education opportunity nodes: "
        f"{len(education_nodes):,}"
    )

    # ==================================================================
    # LOW-ACCESS ORIGINS
    # ==================================================================

    surface = pd.read_csv(
        SURFACE_FILE
    )

    candidates = (
        surface
        .sort_values(
            "life_access_30min_midday_pct"
        )
        .head(
            N_CANDIDATES
        )
        .copy()
    )

    candidates = candidates.merge(
        origins[
            [
                "origin_id",
                "node",
                "node_idx",
            ]
        ],
        on="origin_id",
        how="left",
    )

    candidates = candidates.dropna(
        subset=["node_idx"]
    )

    candidates["node_idx"] = (
        candidates["node_idx"]
        .astype(int)
    )

    print()
    print(
        f"Candidate origins: "
        f"{len(candidates)}"
    )

    print(
        candidates[
            [
                "origin_id",
                "latitude",
                "longitude",
                "life_access_30min_midday_pct",
            ]
        ].to_string(
            index=False
        )
    )

    # ==================================================================
    # SHORTEST-PATH TREES
    # ==================================================================

    candidate_origin_indices = (
        candidates[
            "node_idx"
        ].to_numpy(
            dtype=np.int64
        )
    )

    print()
    print(
        "Computing shortest-path trees "
        "for disadvantaged origins..."
    )

    (
        candidate_distances,
        candidate_predecessors,
    ) = dijkstra(
        baseline_graph,
        directed=True,
        indices=candidate_origin_indices,
        return_predecessors=True,
    )

    # ==================================================================
    # CANDIDATE CORRIDORS
    # ==================================================================

    candidate_results = []

    corridor_frequency_rows = []

    destination_rows = []

    print()
    print(
        "Constructing multi-destination "
        "candidate corridors..."
    )

    for position, (_, origin) in enumerate(
        candidates.iterrows()
    ):

        (
            selected_edges,
            physical_frequency,
            destination_records,
            selected_frequency_rows,
        ) = build_candidate_corridor(
            origin,
            position,
            candidate_distances,
            candidate_predecessors,
            node_ids,
            health_nodes,
            education_nodes,
            calibration,
        )

        candidate_id = (
            f"ORIGIN_{int(origin['origin_id'])}"
        )

        # Number of physical segments is the actual budget.
        selected_physical_count = len(
            selected_frequency_rows
        )

        candidate_results.append(
            {
                "candidate_id": candidate_id,
                "origin_id": int(
                    origin["origin_id"]
                ),
                "latitude": float(
                    origin["latitude"]
                ),
                "longitude": float(
                    origin["longitude"]
                ),
                "baseline_access_pct": float(
                    origin[
                        "life_access_30min_midday_pct"
                    ]
                ),
                "corridor_edges": (
                    selected_edges
                ),
                "physical_segment_count": (
                    selected_physical_count
                ),
                "destination_count": len(
                    destination_records
                ),
            }
        )

        for row in selected_frequency_rows:

            corridor_frequency_rows.append(
                {
                    "candidate_id": (
                        candidate_id
                    ),
                    "u": row["u"],
                    "v": row["v"],
                    "path_frequency": row[
                        "path_frequency"
                    ],
                    "selected": True,
                }
            )

        for record in destination_records:

            destination_rows.append(
                {
                    "candidate_id": (
                        candidate_id
                    ),
                    **record,
                }
            )

        print(
            f"{candidate_id}: "
            f"{len(destination_records)} destinations, "
            f"{selected_physical_count} physical segments, "
            f"{len(selected_edges)} directed edges"
        )

    # ==================================================================
    # BASELINE ACCESSIBILITY
    # ==================================================================

    all_origin_indices = (
        origins[
            "node_idx"
        ].to_numpy(
            dtype=np.int64
        )
    )

    threshold_seconds = (
        THRESHOLD_MINUTES * 60
    )

    print()
    print(
        "Calculating baseline accessibility "
        "for all origins..."
    )

    baseline_health = (
        calculate_accessibility(
            baseline_graph,
            all_origin_indices,
            health_nodes,
            threshold_seconds,
        )
    )

    baseline_education = (
        calculate_accessibility(
            baseline_graph,
            all_origin_indices,
            education_nodes,
            threshold_seconds,
        )
    )

    baseline_life = (
        baseline_health
        + baseline_education
    ) / 2.0

    # ==================================================================
    # INTERVENTION EXPERIMENTS
    # ==================================================================

    summary_rows = []

    origin_effect_rows = []

    for number, candidate in enumerate(
        candidate_results,
        start=1,
    ):

        candidate_id = (
            candidate["candidate_id"]
        )

        print()
        print("=" * 80)
        print(
            f"INTERVENTION "
            f"{number}/{len(candidate_results)}: "
            f"{candidate_id}"
        )
        print("=" * 80)

        print(
            f"Physical intervention segments: "
            f"{candidate['physical_segment_count']}"
        )

        print(
            f"Directed graph edges improved: "
            f"{len(candidate['corridor_edges'])}"
        )

        improvement_graph = (
            build_sparse_graph(
                calibration,
                node_index,
                improvement_edges=(
                    candidate[
                        "corridor_edges"
                    ]
                ),
            )
        )

        health_after = (
            calculate_accessibility(
                improvement_graph,
                all_origin_indices,
                health_nodes,
                threshold_seconds,
            )
        )

        education_after = (
            calculate_accessibility(
                improvement_graph,
                all_origin_indices,
                education_nodes,
                threshold_seconds,
            )
        )

        life_after = (
            health_after
            + education_after
        ) / 2.0

        health_gain = (
            health_after
            - baseline_health
        )

        education_gain = (
            education_after
            - baseline_education
        )

        life_gain = (
            life_after
            - baseline_life
        )

        positive_gain = np.maximum(
            life_gain,
            0,
        )

        affected = (
            life_gain > 0.01
        )

        total_gain = float(
            positive_gain.sum()
        )

        mean_gain = float(
            positive_gain.mean()
        )

        max_gain = float(
            positive_gain.max()
        )

        affected_count = int(
            affected.sum()
        )

        # --------------------------------------------------------------
        # DISADVANTAGED ORIGINS
        # --------------------------------------------------------------

        disadvantaged_mask = (
            baseline_life <= 50
        )

        disadvantaged_gain = (
            np.maximum(
                life_gain[
                    disadvantaged_mask
                ],
                0,
            )
        )

        disadvantaged_total_gain = float(
            disadvantaged_gain.sum()
        )

        disadvantaged_mean_gain = (
            float(
                disadvantaged_gain.mean()
            )
            if len(
                disadvantaged_gain
            )
            else 0.0
        )

        # --------------------------------------------------------------
        # IMPACT PER INTERVENTION SEGMENT
        # --------------------------------------------------------------

        physical_segments = max(
            candidate[
                "physical_segment_count"
            ],
            1,
        )

        gain_per_segment = (
            total_gain
            / physical_segments
        )

        disadvantaged_gain_per_segment = (
            disadvantaged_total_gain
            / physical_segments
        )

        summary_rows.append(
            {
                "candidate_id": (
                    candidate_id
                ),
                "origin_id": (
                    candidate["origin_id"]
                ),
                "latitude": (
                    candidate["latitude"]
                ),
                "longitude": (
                    candidate["longitude"]
                ),
                "baseline_access_pct": (
                    candidate[
                        "baseline_access_pct"
                    ]
                ),
                "physical_intervention_segments": (
                    candidate[
                        "physical_segment_count"
                    ]
                ),
                "directed_edges_improved": (
                    len(
                        candidate[
                            "corridor_edges"
                        ]
                    )
                ),
                "destinations_used": (
                    candidate[
                        "destination_count"
                    ]
                ),
                "total_access_gain_pct_points": (
                    total_gain
                ),
                "mean_access_gain_pct_points": (
                    mean_gain
                ),
                "max_single_origin_gain_pct_points": (
                    max_gain
                ),
                "origins_affected": (
                    affected_count
                ),
                "disadvantaged_total_gain": (
                    disadvantaged_total_gain
                ),
                "disadvantaged_mean_gain": (
                    disadvantaged_mean_gain
                ),
                "gain_per_physical_segment": (
                    gain_per_segment
                ),
                "disadvantaged_gain_per_segment": (
                    disadvantaged_gain_per_segment
                ),
            }
        )

        # --------------------------------------------------------------
        # ORIGIN-LEVEL EFFECTS
        # --------------------------------------------------------------

        for i, origin_id in enumerate(
            origins["origin_id"]
        ):

            origin_effect_rows.append(
                {
                    "candidate_id": (
                        candidate_id
                    ),
                    "origin_id": (
                        origin_id
                    ),
                    "latitude": (
                        origins.iloc[i][
                            "latitude"
                        ]
                    ),
                    "longitude": (
                        origins.iloc[i][
                            "longitude"
                        ]
                    ),
                    "baseline_life_access_pct": (
                        baseline_life[i]
                    ),
                    "after_life_access_pct": (
                        life_after[i]
                    ),
                    "gain_pct_points": (
                        life_gain[i]
                    ),
                    "health_gain_pct_points": (
                        health_gain[i]
                    ),
                    "education_gain_pct_points": (
                        education_gain[i]
                    ),
                }
            )

        print(
            f"Total positive gain: "
            f"{total_gain:.2f} pp"
        )

        print(
            f"Mean gain/origin: "
            f"{mean_gain:.4f} pp"
        )

        print(
            f"Maximum single-origin gain: "
            f"{max_gain:.2f} pp"
        )

        print(
            f"Origins affected: "
            f"{affected_count}/"
            f"{len(origins)}"
        )

        print(
            f"Disadvantaged-origin gain: "
            f"{disadvantaged_total_gain:.2f} pp"
        )

        print(
            f"Gain per physical segment: "
            f"{gain_per_segment:.4f} pp"
        )

    # ==================================================================
    # FINAL RANKING
    # ==================================================================

    ranking = pd.DataFrame(
        summary_rows
    )

    # Primary ranking:
    # impact among disadvantaged origins.
    #
    # Secondary:
    # total citywide gain.
    ranking = (
        ranking
        .sort_values(
            [
                "disadvantaged_total_gain",
                "total_access_gain_pct_points",
            ],
            ascending=False,
        )
        .reset_index(
            drop=True
        )
    )

    ranking["impact_rank"] = (
        np.arange(
            1,
            len(ranking) + 1,
        )
    )

    ranking.to_csv(
        OUTPUT_DIR
        / "intervention_ranking.csv",
        index=False,
    )

    # ==================================================================
    # ORIGIN EFFECTS
    # ==================================================================

    pd.DataFrame(
        origin_effect_rows
    ).to_csv(
        OUTPUT_DIR
        / "intervention_origin_effects.csv",
        index=False,
    )

    # ==================================================================
    # CORRIDOR FREQUENCY
    # ==================================================================

    pd.DataFrame(
        corridor_frequency_rows
    ).to_csv(
        OUTPUT_DIR
        / "candidate_corridor_edge_frequency.csv",
        index=False,
    )

    # ==================================================================
    # DESTINATION RECORDS
    # ==================================================================

    pd.DataFrame(
        destination_rows
    ).to_csv(
        OUTPUT_DIR
        / "candidate_corridor_destinations.csv",
        index=False,
    )

    # ==================================================================
    # FINAL REPORT
    # ==================================================================

    print()
    print("=" * 80)
    print("FINAL INTERVENTION RANKING")
    print("=" * 80)

    print(
        ranking[
            [
                "impact_rank",
                "candidate_id",
                "origin_id",
                "physical_intervention_segments",
                "directed_edges_improved",
                "destinations_used",
                "total_access_gain_pct_points",
                "mean_access_gain_pct_points",
                "max_single_origin_gain_pct_points",
                "origins_affected",
                "disadvantaged_total_gain",
                "disadvantaged_mean_gain",
                "gain_per_physical_segment",
                "disadvantaged_gain_per_segment",
            ]
        ].to_string(
            index=False
        )
    )

    # ==================================================================
    # VALIDATION
    # ==================================================================

    print()
    print("=" * 80)
    print("VALIDATION")
    print("=" * 80)

    physical_counts = (
        ranking[
            "physical_intervention_segments"
        ]
    )

    print(
        "Physical intervention segment counts:"
    )

    print(
        physical_counts.to_list()
    )

    if (
        physical_counts
        .drop_duplicates()
        .isin(
            [MAX_INTERVENTION_EDGES]
        )
        .all()
    ):
        print(
            "PASS: candidate intervention "
            "budgets are standardized."
        )
    else:
        print(
            "NOTE: some candidates have fewer "
            "than the maximum available physical "
            "segments."
        )

    # ==================================================================
    # OUTPUTS
    # ==================================================================

    print()
    print("=" * 80)
    print("OUTPUTS")
    print("=" * 80)

    print(
        OUTPUT_DIR
        / "intervention_ranking.csv"
    )

    print(
        OUTPUT_DIR
        / "intervention_origin_effects.csv"
    )

    print(
        OUTPUT_DIR
        / "candidate_corridor_edge_frequency.csv"
    )

    print(
        OUTPUT_DIR
        / "candidate_corridor_destinations.csv"
    )

    print()
    print(
        "IMPORTANT:"
    )

    print(
        "These are counterfactual network experiments, "
        "not predictions of real infrastructure projects."
    )

    print()
    print("DONE.")


if __name__ == "__main__":
    main()