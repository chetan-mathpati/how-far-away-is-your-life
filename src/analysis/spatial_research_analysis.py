from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[2]

INPUT = (
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
    / "spatial_analysis"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


def main():

    df = pd.read_csv(INPUT)

    print("=" * 80)
    print("HOW FAR AWAY IS YOUR LIFE?")
    print("SPATIAL ACCESSIBILITY RESEARCH ANALYSIS")
    print("=" * 80)

    print()
    print(f"Rows: {len(df):,}")
    print(f"Origins: {df.origin_id.nunique():,}")
    print(f"Hours: {sorted(df.hour.unique())}")
    print(f"Categories: {sorted(df.category.unique())}")
    print(f"Thresholds: {sorted(df.threshold_minutes.unique())}")

    # ---------------------------------------------------------
    # 1. CITYWIDE SUMMARY
    # ---------------------------------------------------------

    citywide = (
        df.groupby(
            ["hour", "category", "threshold_minutes"]
        )["accessibility_pct"]
        .agg(
            mean="mean",
            median="median",
            p10=lambda x: x.quantile(0.10),
            p25=lambda x: x.quantile(0.25),
            p75=lambda x: x.quantile(0.75),
            p90=lambda x: x.quantile(0.90),
            minimum="min",
            maximum="max",
            std="std",
        )
        .reset_index()
    )

    citywide.to_csv(
        OUTPUT_DIR / "citywide_summary.csv",
        index=False,
    )

    print()
    print("=" * 80)
    print("CITYWIDE SUMMARY")
    print("=" * 80)

    print(
        citywide.to_string(
            index=False,
            float_format=lambda x: f"{x:.2f}",
        )
    )

    # ---------------------------------------------------------
    # 2. ACCESSIBILITY CURVE / AUC
    # ---------------------------------------------------------

    auc_rows = []

    for (origin, hour, category), group in df.groupby(
        ["origin_id", "hour", "category"]
    ):

        group = group.sort_values(
            "threshold_minutes"
        )

        x = group["threshold_minutes"].to_numpy()
        y = group["accessibility_pct"].to_numpy()

        auc = np.trapezoid(
            y,
            x,
        )

        auc_rows.append(
            {
                "origin_id": origin,
                "hour": hour,
                "category": category,
                "accessibility_auc": auc,
            }
        )

    auc_df = pd.DataFrame(
        auc_rows
    )

    auc_df.to_csv(
        OUTPUT_DIR / "accessibility_auc.csv",
        index=False,
    )

    # ---------------------------------------------------------
    # 3. MIDDAY RANKINGS
    # ---------------------------------------------------------

    midday = (
        auc_df[
            auc_df["hour"] == 13
        ]
        .sort_values(
            [
                "category",
                "accessibility_auc",
            ],
            ascending=[
                True,
                False,
            ],
        )
    )

    print()
    print("=" * 80)
    print("MIDDAY ACCESSIBILITY RANKINGS")
    print("=" * 80)

    for category in sorted(
        midday.category.unique()
    ):

        print()
        print(category.upper())

        subset = midday[
            midday.category == category
        ].copy()

        print(
            subset[
                [
                    "origin_id",
                    "accessibility_auc",
                ]
            ]
            .head(10)
            .to_string(index=False)
        )

    # ---------------------------------------------------------
    # 4. PEAK-HOUR PENALTY
    # ---------------------------------------------------------

    pivot = df.pivot_table(
        index=[
            "origin_id",
            "category",
            "threshold_minutes",
        ],
        columns="hour",
        values="accessibility_pct",
    ).reset_index()

    if 13 in pivot.columns and 18 in pivot.columns:

        pivot["peak_hour_loss_pp"] = (
            pivot[13]
            - pivot[18]
        )

        pivot["peak_hour_loss_relative_pct"] = (
            (
                pivot[13]
                - pivot[18]
            )
            /
            pivot[13].replace(0, np.nan)
            * 100
        )

        peak_summary = (
            pivot.groupby(
                [
                    "category",
                    "threshold_minutes",
                ]
            )[
                "peak_hour_loss_pp"
            ]
            .agg(
                mean="mean",
                median="median",
                p10=lambda x: x.quantile(0.10),
                p90=lambda x: x.quantile(0.90),
                maximum="max",
            )
            .reset_index()
        )

        peak_summary.to_csv(
            OUTPUT_DIR / "peak_hour_penalty.csv",
            index=False,
        )

        print()
        print("=" * 80)
        print("1 PM → 6 PM ACCESSIBILITY LOSS")
        print("=" * 80)

        print(
            peak_summary.to_string(
                index=False,
                float_format=lambda x: f"{x:.2f}",
            )
        )

    # ---------------------------------------------------------
    # 5. SPATIAL INEQUALITY
    # ---------------------------------------------------------

    inequality = (
        df.groupby(
            [
                "hour",
                "category",
                "threshold_minutes",
            ]
        )["accessibility_pct"]
        .agg(
            mean="mean",
            std="std",
            minimum="min",
            maximum="max",
        )
        .reset_index()
    )

    inequality["gap_pp"] = (
        inequality["maximum"]
        - inequality["minimum"]
    )

    inequality["cv"] = (
        inequality["std"]
        /
        inequality["mean"].replace(0, np.nan)
    )

    inequality.to_csv(
        OUTPUT_DIR / "spatial_inequality.csv",
        index=False,
    )

    # ---------------------------------------------------------
    # 6. WORST-ACCESS AREAS
    # ---------------------------------------------------------

    for hour in [7, 13, 18, 22]:

        for category in sorted(
            df.category.unique()
        ):

            subset = df[
                (df.hour == hour)
                &
                (df.category == category)
                &
                (df.threshold_minutes == 30)
            ].copy()

            subset = subset.sort_values(
                "accessibility_pct"
            )

            output = subset[
                [
                    "origin_id",
                    "latitude",
                    "longitude",
                    "accessibility_pct",
                ]
            ].head(20)

            output.to_csv(
                OUTPUT_DIR
                / f"worst_{category}_{hour}h_30min.csv",
                index=False,
            )

    # ---------------------------------------------------------
    # 7. BEST / WORST DIFFERENCE
    # ---------------------------------------------------------

    gap_rows = []

    for (hour, category, threshold), group in df.groupby(
        [
            "hour",
            "category",
            "threshold_minutes",
        ]
    ):

        best = group.loc[
            group.accessibility_pct.idxmax()
        ]

        worst = group.loc[
            group.accessibility_pct.idxmin()
        ]

        gap_rows.append(
            {
                "hour": hour,
                "category": category,
                "threshold_minutes": threshold,
                "best_origin": best.origin_id,
                "best_accessibility_pct": best.accessibility_pct,
                "best_latitude": best.latitude,
                "best_longitude": best.longitude,
                "worst_origin": worst.origin_id,
                "worst_accessibility_pct": worst.accessibility_pct,
                "worst_latitude": worst.latitude,
                "worst_longitude": worst.longitude,
                "gap_pp": (
                    best.accessibility_pct
                    - worst.accessibility_pct
                ),
            }
        )

    gaps = pd.DataFrame(
        gap_rows
    )

    gaps.to_csv(
        OUTPUT_DIR / "best_worst_gaps.csv",
        index=False,
    )

    # ---------------------------------------------------------
    # 8. 30-MINUTE CROSS-DOMAIN ACCESS
    # ---------------------------------------------------------

    cross = df[
        df.threshold_minutes == 30
    ].pivot_table(
        index=[
            "origin_id",
            "latitude",
            "longitude",
            "hour",
        ],
        columns="category",
        values="accessibility_pct",
    ).reset_index()

    for column in [
        "health",
        "education",
        "employment",
    ]:

        if column not in cross.columns:
            cross[column] = np.nan

    cross["life_accessibility_index"] = (
        cross[
            [
                "health",
                "education",
                "employment",
            ]
        ]
        .mean(axis=1)
    )

    cross["health_education_index"] = (
        cross[
            [
                "health",
                "education",
            ]
        ]
        .mean(axis=1)
    )

    cross.to_csv(
        OUTPUT_DIR / "cross_domain_accessibility.csv",
        index=False,
    )

    # ---------------------------------------------------------
    # 9. CROSS-DOMAIN WORST AREAS
    # ---------------------------------------------------------

    midday_cross = cross[
        cross.hour == 13
    ].sort_values(
        "health_education_index"
    )

    print()
    print("=" * 80)
    print("LOWEST HEALTH + EDUCATION ACCESSIBILITY")
    print("MIDDAY / 30 MINUTES")
    print("=" * 80)

    print(
        midday_cross[
            [
                "origin_id",
                "latitude",
                "longitude",
                "health",
                "education",
                "employment",
                "health_education_index",
            ]
        ]
        .head(15)
        .to_string(
            index=False,
            float_format=lambda x: f"{x:.2f}",
        )
    )

    # ---------------------------------------------------------
    # 10. PEAK-HOUR MOST AFFECTED AREAS
    # ---------------------------------------------------------

    if 13 in cross.hour.unique() and 18 in cross.hour.unique():

        noon = cross[
            cross.hour == 13
        ][
            [
                "origin_id",
                "health",
                "education",
                "employment",
            ]
        ].set_index("origin_id")

        evening = cross[
            cross.hour == 18
        ][
            [
                "origin_id",
                "health",
                "education",
                "employment",
            ]
        ].set_index("origin_id")

        joined = noon.join(
            evening,
            lsuffix="_13",
            rsuffix="_18",
        )

        for category in [
            "health",
            "education",
            "employment",
        ]:

            joined[
                f"{category}_loss"
            ] = (
                joined[f"{category}_13"]
                -
                joined[f"{category}_18"]
            )

        joined["combined_loss"] = (
            joined["health_loss"]
            +
            joined["education_loss"]
        ) / 2

        joined = (
            joined
            .sort_values(
                "combined_loss",
                ascending=False,
            )
            .reset_index()
        )

        joined.to_csv(
            OUTPUT_DIR
            / "peak_hour_affected_origins.csv",
            index=False,
        )

        print()
        print("=" * 80)
        print("MOST PEAK-HOUR AFFECTED AREAS")
        print("30-MINUTE ACCESSIBILITY")
        print("=" * 80)

        print(
            joined.head(20).to_string(
                index=False,
                float_format=lambda x: f"{x:.2f}",
            )
        )

    # ---------------------------------------------------------
    # DONE
    # ---------------------------------------------------------

    print()
    print("=" * 80)
    print("RESEARCH ANALYSIS COMPLETE")
    print("=" * 80)

    print()
    print(
        "Files written to:"
    )

    print(
        OUTPUT_DIR
    )


if __name__ == "__main__":
    main()