from pathlib import Path
import time

import networkx as nx
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra


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
    / "spatial_traffic"
    / "edge_spatial_calibration.csv"
)

ORIGINS_PATH = (
    ROOT
    / "data"
    / "processed"
    / "citywide"
    / "citywide_origins.csv"
)

OPPORTUNITY_FILES = {
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
    / "spatial_accessibility"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

OUTPUT_PATH = (
    OUTPUT_DIR
    / "bengaluru_spatial_accessibility.csv"
)

SUMMARY_PATH = (
    OUTPUT_DIR
    / "spatial_accessibility_summary.csv"
)


# ============================================================
# ANALYSIS CONFIGURATION
# ============================================================

HOURS = [7, 9, 13, 18, 22]

THRESHOLDS = [15, 30, 45, 60]

MAX_TRAVEL_TIME_SECONDS = 60 * 60

# Number of origins sent to SciPy Dijkstra at once.
#
# 25 x 155,776 float64 values ≈ 31 MB.
#
# If your machine has plenty of RAM, 50 can be used later.
BATCH_SIZE = 25


# ============================================================
# HELPERS
# ============================================================

def find_column(df, candidates, required=True):
    """
    Find a dataframe column without caring about capitalization.
    """

    lower_columns = {
        str(column).lower(): column
        for column in df.columns
    }

    for candidate in candidates:

        if candidate.lower() in lower_columns:
            return lower_columns[candidate.lower()]

    if required:

        raise KeyError(
            "\nCould not find any of:\n"
            f"{candidates}\n\n"
            "Available columns:\n"
            f"{list(df.columns)}"
        )

    return None


# ============================================================
# LOAD ROAD NETWORK
# ============================================================

def load_graph():

    print()
    print("=" * 70)
    print("LOADING ROAD NETWORK")
    print("=" * 70)

    G = nx.read_graphml(
        GRAPH_PATH
    )

    print(
        f"Nodes: {G.number_of_nodes():,}"
    )

    print(
        f"Edges: {G.number_of_edges():,}"
    )

    return G


# ============================================================
# NORMALIZE NODE IDs
# ============================================================

def build_node_index(G):

    print()
    print("Building node index...")

    nodes = [
        str(node)
        for node in G.nodes
    ]

    node_to_idx = {
        node: index
        for index, node in enumerate(nodes)
    }

    print(
        f"Indexed nodes: {len(nodes):,}"
    )

    return nodes, node_to_idx


# ============================================================
# BUILD SPARSE GRAPH
# ============================================================

def build_sparse_graph(
    calibration,
    hour,
    node_to_idx,
):
    """
    Build a SciPy sparse directed graph for one time period.

    IMPORTANT:
    We use the calibration file's
    `calibrated_travel_time_s` directly.

    We do NOT recalculate it from speed_multiplier.

    For multiple parallel road edges connecting the same
    directed node pair, the fastest calibrated edge is retained.
    """

    print()
    print(
        f"Building sparse graph for {hour:02d}:00..."
    )

    hour_data = calibration[
        calibration["hour"] == hour
    ].copy()

    if hour_data.empty:

        raise ValueError(
            f"No calibration data found for hour {hour}."
        )

    print(
        f"Calibration rows: "
        f"{len(hour_data):,}"
    )

    # Actual schema from your calibration file:
    #
    # hour
    # u
    # v
    # key
    # speed_multiplier
    # baseline_travel_time_s
    # calibrated_travel_time_s

    required_columns = [
        "u",
        "v",
        "calibrated_travel_time_s",
    ]

    missing = [
        column
        for column in required_columns
        if column not in hour_data.columns
    ]

    if missing:

        raise KeyError(
            "Calibration file is missing required "
            f"columns: {missing}"
        )

    # Normalize IDs.
    hour_data["u"] = (
        hour_data["u"]
        .astype(str)
    )

    hour_data["v"] = (
        hour_data["v"]
        .astype(str)
    )

    # Keep only edges whose nodes exist in the graph.
    hour_data = hour_data[
        hour_data["u"].isin(node_to_idx)
        &
        hour_data["v"].isin(node_to_idx)
    ].copy()

    print(
        f"Valid calibrated edges: "
        f"{len(hour_data):,}"
    )

    # Multiple OSM edges can connect the same u -> v pair.
    #
    # Dijkstra only needs the cheapest directed connection.
    #
    # This also avoids scipy CSR summing duplicate edges.
    hour_data = (
        hour_data
        .groupby(
            ["u", "v"],
            as_index=False,
        )["calibrated_travel_time_s"]
        .min()
    )

    print(
        f"Unique directed connections: "
        f"{len(hour_data):,}"
    )

    rows = (
        hour_data["u"]
        .map(node_to_idx)
        .to_numpy(dtype=np.int64)
    )

    cols = (
        hour_data["v"]
        .map(node_to_idx)
        .to_numpy(dtype=np.int64)
    )

    weights = (
        pd.to_numeric(
            hour_data[
                "calibrated_travel_time_s"
            ],
            errors="coerce",
        )
        .to_numpy(dtype=np.float64)
    )

    valid = (
        np.isfinite(weights)
        &
        (weights > 0)
    )

    rows = rows[valid]
    cols = cols[valid]
    weights = weights[valid]

    n_nodes = len(node_to_idx)

    sparse_graph = csr_matrix(
        (
            weights,
            (rows, cols),
        ),
        shape=(
            n_nodes,
            n_nodes,
        ),
        dtype=np.float64,
    )

    sparse_graph.sum_duplicates()

    print(
        f"Sparse matrix:"
    )

    print(
        f"  nodes       : {n_nodes:,}"
    )

    print(
        f"  connections : {sparse_graph.nnz:,}"
    )

    print(
        f"  memory      : "
        f"{sparse_graph.data.nbytes / 1024 / 1024:.1f} MB"
    )

    return sparse_graph


# ============================================================
# LOAD CITYWIDE ORIGINS
# ============================================================

def load_origins(node_to_idx):

    print()
    print("=" * 70)
    print("LOADING CITYWIDE ORIGINS")
    print("=" * 70)

    origins = pd.read_csv(
        ORIGINS_PATH
    )

    print(
        f"Raw origins: "
        f"{len(origins):,}"
    )

    node_column = find_column(
        origins,
        [
            "network_node",
            "node",
            "origin_node",
            "osmid",
        ],
    )

    origins["_node_id"] = (
        origins[node_column]
        .astype(str)
    )

    origins["_node_idx"] = (
        origins["_node_id"]
        .map(node_to_idx)
    )

    valid = (
        origins["_node_idx"]
        .notna()
    )

    missing = (
        ~valid
    ).sum()

    if missing:

        print(
            f"Warning: {missing} origins "
            "could not be mapped."
        )

    origins = (
        origins.loc[valid]
        .copy()
    )

    origins["_node_idx"] = (
        origins["_node_idx"]
        .astype(int)
    )

    origins = (
        origins
        .reset_index(drop=True)
    )

    print(
        f"Valid origins: "
        f"{len(origins):,}"
    )

    return origins


# ============================================================
# LOAD OPPORTUNITIES
# ============================================================

def load_opportunities(node_to_idx):

    print()
    print("=" * 70)
    print("LOADING OPPORTUNITIES")
    print("=" * 70)

    opportunities = {}

    for category, path in OPPORTUNITY_FILES.items():

        print()
        print(
            f"Loading {category}..."
        )

        df = pd.read_csv(
            path
        )

        print(
            f"  records: "
            f"{len(df):,}"
        )

        node_column = find_column(
            df,
            [
                "network_node",
                "node",
                "origin_node",
                "nearest_node",
            ],
        )

        df["_node_id"] = (
            df[node_column]
            .astype(str)
        )

        df["_node_idx"] = (
            df["_node_id"]
            .map(node_to_idx)
        )

        df = df[
            df["_node_idx"]
            .notna()
        ].copy()

        df["_node_idx"] = (
            df["_node_idx"]
            .astype(int)
        )

        # Number of opportunity records at each road node.
        counts = (
            df
            .groupby("_node_idx")
            .size()
            .astype(float)
        )

        opportunities[category] = counts

        print(
            f"  valid records: "
            f"{len(df):,}"
        )

        print(
            f"  network nodes: "
            f"{len(counts):,}"
        )

        print(
            f"  total weight: "
            f"{counts.sum():,.0f}"
        )

    return opportunities


# ============================================================
# ACCESSIBILITY CALCULATION
# ============================================================

def calculate_accessible_counts(
    distances,
    opportunity_counts,
    threshold_seconds,
):
    """
    Convert shortest-path distances into accessible
    opportunity counts.

    distances:
        shape = origins x network_nodes

    opportunity_counts:
        indexed by network-node integer.

    Returns:
        one accessibility count per origin.
    """

    opportunity_nodes = (
        opportunity_counts
        .index
        .to_numpy(dtype=np.int64)
    )

    opportunity_weights = (
        opportunity_counts
        .to_numpy(dtype=np.float64)
    )

    relevant_distances = (
        distances[
            :,
            opportunity_nodes,
        ]
    )

    accessible = (
        relevant_distances
        <= threshold_seconds
    )

    counts = (
        accessible
        @ opportunity_weights
    )

    return counts


# ============================================================
# MAIN
# ============================================================

def main():

    overall_start = time.time()

    # --------------------------------------------------------
    # 1. LOAD GRAPH
    # --------------------------------------------------------

    G = load_graph()

    nodes, node_to_idx = (
        build_node_index(G)
    )

    del G

    # --------------------------------------------------------
    # 2. LOAD CALIBRATION
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("LOADING SPATIAL TRAFFIC CALIBRATION")
    print("=" * 70)

    calibration = pd.read_csv(
        CALIBRATION_PATH
    )

    print(
        f"Calibration rows: "
        f"{len(calibration):,}"
    )

    print(
        "Columns:"
    )

    print(
        list(calibration.columns)
    )

    # --------------------------------------------------------
    # 3. LOAD ORIGINS
    # --------------------------------------------------------

    origins = load_origins(
        node_to_idx
    )

    # --------------------------------------------------------
    # 4. LOAD OPPORTUNITIES
    # --------------------------------------------------------

    opportunities = (
        load_opportunities(
            node_to_idx
        )
    )

    # --------------------------------------------------------
    # 5. BUILD SPARSE GRAPHS
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("BUILDING TIME-SPECIFIC SPARSE NETWORKS")
    print("=" * 70)

    sparse_graphs = {}

    graph_build_start = time.time()

    for hour in HOURS:

        sparse_graphs[hour] = (
            build_sparse_graph(
                calibration,
                hour,
                node_to_idx,
            )
        )

    print()
    print(
        "Sparse graph construction completed in "
        f"{(time.time() - graph_build_start) / 60:.2f} minutes."
    )

    # --------------------------------------------------------
    # 6. PREPARE ORIGINS
    # --------------------------------------------------------

    origin_indices = (
        origins["_node_idx"]
        .to_numpy(dtype=np.int64)
    )

    total_origins = (
        len(origin_indices)
    )

    total_batches = (
        (
            total_origins
            + BATCH_SIZE
            - 1
        )
        // BATCH_SIZE
    )

    total_expected_rows = (
        total_origins
        * len(HOURS)
        * len(opportunities)
        * len(THRESHOLDS)
    )

    print()
    print("=" * 70)
    print("ACCESSIBILITY COMPUTATION")
    print("=" * 70)

    print(
        f"Origins       : {total_origins:,}"
    )

    print(
        f"Time periods  : {len(HOURS)}"
    )

    print(
        f"Categories    : {len(opportunities)}"
    )

    print(
        f"Thresholds    : {len(THRESHOLDS)}"
    )

    print(
        f"Expected rows : {total_expected_rows:,}"
    )

    print(
        f"Batch size    : {BATCH_SIZE}"
    )

    print()
    print(
        "Starting shortest-path calculations..."
    )

    # --------------------------------------------------------
    # 7. CALCULATE EACH TIME PERIOD
    # --------------------------------------------------------

    results = []

    for hour_index, hour in enumerate(HOURS, start=1):

        print()
        print("=" * 70)

        print(
            f"TIME PERIOD {hour_index}/{len(HOURS)}"
        )

        print(
            f"{hour:02d}:00"
        )

        print("=" * 70)

        sparse_graph = (
            sparse_graphs[hour]
        )

        hour_start = time.time()

        for batch_start in range(
            0,
            total_origins,
            BATCH_SIZE,
        ):

            batch_end = min(
                batch_start + BATCH_SIZE,
                total_origins,
            )

            batch_number = (
                batch_start
                // BATCH_SIZE
            ) + 1

            batch_origin_indices = (
                origin_indices[
                    batch_start:batch_end
                ]
            )

            batch_start_time = (
                time.time()
            )

            print(
                f"  Batch "
                f"{batch_number}/{total_batches} "
                f"| origins "
                f"{batch_start + 1:,}-"
                f"{batch_end:,} "
                f"| running...",
                flush=True,
            )

            # ------------------------------------------------
            # SCIPY DIJKSTRA
            # ------------------------------------------------

            distances = dijkstra(
                csgraph=sparse_graph,
                directed=True,
                indices=batch_origin_indices,
                return_predecessors=False,
                limit=MAX_TRAVEL_TIME_SECONDS,
            )

            # ------------------------------------------------
            # ACCESSIBILITY COUNTS
            # ------------------------------------------------

            for category, counts_by_node in (
                opportunities.items()
            ):

                total_opportunities = (
                    counts_by_node.sum()
                )

                for threshold in THRESHOLDS:

                    accessible_counts = (
                        calculate_accessible_counts(
                            distances,
                            counts_by_node,
                            threshold * 60,
                        )
                    )

                    for local_index, count in enumerate(
                        accessible_counts
                    ):

                        global_index = (
                            batch_start
                            + local_index
                        )

                        origin = (
                            origins.iloc[
                                global_index
                            ]
                        )

                        if "origin_id" in origins.columns:

                            origin_id = (
                                origin["origin_id"]
                            )

                        else:

                            origin_id = (
                                global_index
                            )

                        results.append(
                            {
                                "origin_id": int(
                                    origin_id
                                ),
                                "latitude": float(
                                    origin["latitude"]
                                ),
                                "longitude": float(
                                    origin["longitude"]
                                ),
                                "hour": int(
                                    hour
                                ),
                                "category": category,
                                "threshold_minutes": int(
                                    threshold
                                ),
                                "accessible_count": float(
                                    count
                                ),
                                "total_opportunities": float(
                                    total_opportunities
                                ),
                            }
                        )

            batch_elapsed = (
                time.time()
                - batch_start_time
            )

            completed = (
                batch_end
            )

            percentage = (
                completed
                / total_origins
                * 100
            )

            print(
                f"    completed in "
                f"{batch_elapsed:.1f}s "
                f"| {percentage:.1f}% "
                f"of {hour:02d}:00",
                flush=True,
            )

        hour_elapsed = (
            time.time()
            - hour_start
        )

        print()
        print(
            f"{hour:02d}:00 completed in "
            f"{hour_elapsed / 60:.2f} minutes."
        )

    # --------------------------------------------------------
    # 8. BUILD RESULT DATAFRAME
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("BUILDING FINAL DATASET")
    print("=" * 70)

    result_df = pd.DataFrame(
        results
    )

    result_df["accessibility_pct"] = (
        result_df["accessible_count"]
        /
        result_df["total_opportunities"]
        * 100
    )

    result_df = (
        result_df
        .sort_values(
            [
                "hour",
                "category",
                "threshold_minutes",
                "origin_id",
            ]
        )
        .reset_index(drop=True)
    )

    # --------------------------------------------------------
    # 9. SAVE MAIN DATASET
    # --------------------------------------------------------

    result_df.to_csv(
        OUTPUT_PATH,
        index=False,
    )

    print()
    print(
        f"Saved accessibility dataset:"
    )

    print(
        OUTPUT_PATH
    )

    # --------------------------------------------------------
    # 10. BUILD SUMMARY
    # --------------------------------------------------------

    summary = (
        result_df
        .groupby(
            [
                "hour",
                "category",
                "threshold_minutes",
            ]
        )[
            "accessibility_pct"
        ]
        .agg(
            [
                "mean",
                "median",
                "min",
                "max",
            ]
        )
        .reset_index()
    )

    summary.to_csv(
        SUMMARY_PATH,
        index=False,
    )

    print()
    print(
        "Saved summary:"
    )

    print(
        SUMMARY_PATH
    )

    # --------------------------------------------------------
    # 11. VALIDATION — ROW COUNT
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("VALIDATION")
    print("=" * 70)

    print(
        f"Rows produced : "
        f"{len(result_df):,}"
    )

    print(
        f"Rows expected : "
        f"{total_expected_rows:,}"
    )

    if (
        len(result_df)
        != total_expected_rows
    ):

        raise RuntimeError(
            "Row-count validation failed."
        )

    print(
        "✓ Row count validation passed."
    )

    # --------------------------------------------------------
    # 12. VALIDATION — ACCESSIBILITY MONOTONICITY
    # --------------------------------------------------------

    print()
    print(
        "Checking accessibility monotonicity..."
    )

    monotonic_failures = 0

    grouped = result_df.groupby(
        [
            "origin_id",
            "hour",
            "category",
        ]
    )

    for _, group in grouped:

        values = (
            group
            .sort_values(
                "threshold_minutes"
            )[
                "accessible_count"
            ]
            .to_numpy()
        )

        if np.any(
            np.diff(values)
            < -1e-9
        ):

            monotonic_failures += 1

    print(
        f"Monotonicity failures: "
        f"{monotonic_failures}"
    )

    if monotonic_failures:

        raise RuntimeError(
            "Accessibility should never decrease "
            "when the allowed travel-time threshold "
            "increases."
        )

    print(
        "✓ Monotonicity validation passed."
    )

    # --------------------------------------------------------
    # 13. VALIDATION — ACCESSIBILITY RANGE
    # --------------------------------------------------------

    minimum = (
        result_df[
            "accessibility_pct"
        ].min()
    )

    maximum = (
        result_df[
            "accessibility_pct"
        ].max()
    )

    print()
    print(
        f"Accessibility range: "
        f"{minimum:.2f}% - "
        f"{maximum:.2f}%"
    )

    if minimum < -1e-9:

        raise RuntimeError(
            "Negative accessibility detected."
        )

    if maximum > 100 + 1e-9:

        raise RuntimeError(
            "Accessibility exceeds 100%."
        )

    print(
        "✓ Accessibility range validation passed."
    )

    # --------------------------------------------------------
    # 14. FINAL REPORT
    # --------------------------------------------------------

    total_elapsed = (
        time.time()
        - overall_start
    )

    print()
    print("=" * 70)
    print("COMPLETE")
    print("=" * 70)

    print(
        f"Total runtime: "
        f"{total_elapsed / 60:.2f} minutes"
    )

    print()
    print(
        f"Final rows: "
        f"{len(result_df):,}"
    )

    print()
    print(
        "Output files:"
    )

    print(
        f"  {OUTPUT_PATH}"
    )

    print(
        f"  {SUMMARY_PATH}"
    )

    print()
    print(
        "The spatially calibrated accessibility "
        "dataset is ready for downstream analysis."
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()