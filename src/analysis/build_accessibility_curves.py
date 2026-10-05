from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

INPUT_PATH = (
    ROOT
    / "data"
    / "processed"
    / "spatial_accessibility"
    / "bengaluru_spatial_accessibility.csv"
)

OUTPUT_DIR = (
    ROOT
    / "data"
    / "processed"
    / "accessibility_curves"
)


def main():
    print("=" * 80)
    print("BUILD ACCESSIBILITY CURVES")
    print("=" * 80)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ------------------------------------------------------------------
    # 1. Load accessibility dataset
    # ------------------------------------------------------------------
    print("\n[1/6] Loading accessibility data...")

    df = pd.read_csv(INPUT_PATH)

    print(f"  Rows: {len(df):,}")
    print(f"  Origins: {df['origin_id'].nunique():,}")
    print(
        f"  Hours: "
        f"{sorted(df['hour'].unique().tolist())}"
    )
    print(
        f"  Categories: "
        f"{sorted(df['category'].unique().tolist())}"
    )
    print(
        f"  Thresholds: "
        f"{sorted(df['threshold_minutes'].unique().tolist())}"
    )

    # ------------------------------------------------------------------
    # 2. Validate monotonicity
    # ------------------------------------------------------------------
    print("\n[2/6] Validating accessibility curves...")

    violations = []

    group_columns = [
        "origin_id",
        "hour",
        "category",
    ]

    for keys, group in df.groupby(group_columns):

        ordered = group.sort_values(
            "threshold_minutes"
        )

        values = ordered[
            "accessibility_pct"
        ].tolist()

        for i in range(1, len(values)):
            if values[i] + 1e-9 < values[i - 1]:
                violations.append(
                    {
                        "origin_id": keys[0],
                        "hour": keys[1],
                        "category": keys[2],
                        "previous": values[i - 1],
                        "current": values[i],
                    }
                )

    print(
        f"  Monotonicity violations: "
        f"{len(violations):,}"
    )

    if violations:
        raise ValueError(
            "Accessibility curve monotonicity failed."
        )

    # ------------------------------------------------------------------
    # 3. Build Bengaluru-wide curve statistics
    # ------------------------------------------------------------------
    print("\n[3/6] Building population-level curves...")

    curve_summary = (
        df.groupby(
            [
                "hour",
                "category",
                "threshold_minutes",
            ],
            as_index=False,
        )
        .agg(
            mean_accessibility_pct=(
                "accessibility_pct",
                "mean",
            ),
            median_accessibility_pct=(
                "accessibility_pct",
                "median",
            ),
            p10_accessibility_pct=(
                "accessibility_pct",
                lambda x: x.quantile(0.10),
            ),
            p25_accessibility_pct=(
                "accessibility_pct",
                lambda x: x.quantile(0.25),
            ),
            p75_accessibility_pct=(
                "accessibility_pct",
                lambda x: x.quantile(0.75),
            ),
            p90_accessibility_pct=(
                "accessibility_pct",
                lambda x: x.quantile(0.90),
            ),
            min_accessibility_pct=(
                "accessibility_pct",
                "min",
            ),
            max_accessibility_pct=(
                "accessibility_pct",
                "max",
            ),
            std_accessibility_pct=(
                "accessibility_pct",
                "std",
            ),
            origins=(
                "origin_id",
                "nunique",
            ),
        )
        .sort_values(
            [
                "hour",
                "category",
                "threshold_minutes",
            ]
        )
    )

    curve_summary_path = (
        OUTPUT_DIR
        / "bengaluru_accessibility_curves.csv"
    )

    curve_summary.to_csv(
        curve_summary_path,
        index=False,
    )

    print(
        f"  Wrote: "
        f"{curve_summary_path.relative_to(ROOT)}"
    )

    # ------------------------------------------------------------------
    # 4. Build origin-level curve dataset
    # ------------------------------------------------------------------
    print("\n[4/6] Building origin-level curves...")

    origin_curves = (
        df[
            [
                "origin_id",
                "latitude",
                "longitude",
                "hour",
                "category",
                "threshold_minutes",
                "accessible_count",
                "total_opportunities",
                "accessibility_pct",
            ]
        ]
        .sort_values(
            [
                "origin_id",
                "hour",
                "category",
                "threshold_minutes",
            ]
        )
        .reset_index(drop=True)
    )

    origin_curves_path = (
        OUTPUT_DIR
        / "origin_accessibility_curves.csv"
    )

    origin_curves.to_csv(
        origin_curves_path,
        index=False,
    )

    print(
        f"  Wrote: "
        f"{origin_curves_path.relative_to(ROOT)}"
    )

    # ------------------------------------------------------------------
    # 5. Calculate curve growth
    # ------------------------------------------------------------------
    print("\n[5/6] Calculating accessibility gains...")

    pivot = (
        df.pivot_table(
            index=[
                "origin_id",
                "latitude",
                "longitude",
                "hour",
                "category",
            ],
            columns="threshold_minutes",
            values="accessibility_pct",
            aggfunc="first",
        )
        .reset_index()
    )

    pivot.columns.name = None

    rename_map = {}

    for threshold in [15, 30, 45, 60]:
        if threshold in pivot.columns:
            rename_map[
                threshold
            ] = f"access_{threshold}min_pct"

    pivot = pivot.rename(
        columns=rename_map
    )

    if (
        "access_15min_pct" in pivot.columns
        and "access_30min_pct" in pivot.columns
    ):
        pivot["gain_15_to_30_pp"] = (
            pivot["access_30min_pct"]
            - pivot["access_15min_pct"]
        )

    if (
        "access_30min_pct" in pivot.columns
        and "access_45min_pct" in pivot.columns
    ):
        pivot["gain_30_to_45_pp"] = (
            pivot["access_45min_pct"]
            - pivot["access_30min_pct"]
        )

    if (
        "access_45min_pct" in pivot.columns
        and "access_60min_pct" in pivot.columns
    ):
        pivot["gain_45_to_60_pp"] = (
            pivot["access_60min_pct"]
            - pivot["access_45min_pct"]
        )

    pivot_path = (
        OUTPUT_DIR
        / "origin_accessibility_curve_features.csv"
    )

    pivot.to_csv(
        pivot_path,
        index=False,
    )

    print(
        f"  Wrote: "
        f"{pivot_path.relative_to(ROOT)}"
    )

    # ------------------------------------------------------------------
    # 6. Build cross-time comparison
    # ------------------------------------------------------------------
    print("\n[6/6] Building time-of-day comparison...")

    midday = df[
        df["hour"] == 13
    ][
        [
            "origin_id",
            "category",
            "threshold_minutes",
            "accessibility_pct",
        ]
    ].rename(
        columns={
            "accessibility_pct": "midday_access_pct"
        }
    )

    peak = df[
        df["hour"] == 18
    ][
        [
            "origin_id",
            "category",
            "threshold_minutes",
            "accessibility_pct",
        ]
    ].rename(
        columns={
            "accessibility_pct": "peak_access_pct"
        }
    )

    time_comparison = midday.merge(
        peak,
        on=[
            "origin_id",
            "category",
            "threshold_minutes",
        ],
        how="inner",
    )

    time_comparison[
        "peak_hour_loss_pp"
    ] = (
        time_comparison[
            "midday_access_pct"
        ]
        - time_comparison[
            "peak_access_pct"
        ]
    )

    time_comparison_path = (
        OUTPUT_DIR
        / "midday_vs_peak_accessibility.csv"
    )

    time_comparison.to_csv(
        time_comparison_path,
        index=False,
    )

    print(
        f"  Wrote: "
        f"{time_comparison_path.relative_to(ROOT)}"
    )

    # ------------------------------------------------------------------
    # Final diagnostics
    # ------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("ACCESSIBILITY CURVES COMPLETE")
    print("=" * 80)

    print(
        f"\nCurve rows: "
        f"{len(curve_summary):,}"
    )

    print(
        f"Origin-level rows: "
        f"{len(origin_curves):,}"
    )

    print(
        f"Curve feature rows: "
        f"{len(pivot):,}"
    )

    print(
        f"Time comparison rows: "
        f"{len(time_comparison):,}"
    )

    print("\nSample Bengaluru-wide curves:")

    sample = curve_summary[
        (
            curve_summary["hour"] == 13
        )
        & (
            curve_summary["threshold_minutes"].isin(
                [15, 30, 45, 60]
            )
        )
    ]

    print(
        sample[
            [
                "category",
                "threshold_minutes",
                "mean_accessibility_pct",
                "median_accessibility_pct",
                "p10_accessibility_pct",
                "p90_accessibility_pct",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()