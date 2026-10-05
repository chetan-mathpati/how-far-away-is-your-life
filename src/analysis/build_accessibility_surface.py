from pathlib import Path
import pandas as pd
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]

INPUT = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "spatial_accessibility"
    / "bengaluru_spatial_accessibility.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "accessibility_surface"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    print("=" * 80)
    print("BUILDING ACCESSIBILITY SURFACE")
    print("=" * 80)

    df = pd.read_csv(INPUT)

    print(f"Input rows: {len(df):,}")
    print(f"Origins: {df['origin_id'].nunique():,}")
    print(f"Hours: {sorted(df['hour'].unique())}")
    print(f"Categories: {sorted(df['category'].unique())}")
    print(f"Thresholds: {sorted(df['threshold_minutes'].unique())}")

    # ------------------------------------------------------------------
    # 1. Keep the spatial identity of every origin
    # ------------------------------------------------------------------

    origin_cols = [
        "origin_id",
        "latitude",
        "longitude",
    ]

    origins = (
        df[origin_cols]
        .drop_duplicates("origin_id")
        .sort_values("origin_id")
        .reset_index(drop=True)
    )

    # ------------------------------------------------------------------
    # 2. Helper for extracting a particular accessibility slice
    # ------------------------------------------------------------------

    def get_slice(category, hour, threshold):
        subset = df[
            (df["category"] == category)
            & (df["hour"] == hour)
            & (df["threshold_minutes"] == threshold)
        ][
            [
                "origin_id",
                "accessibility_pct",
                "accessible_count",
            ]
        ].copy()

        subset = subset.rename(
            columns={
                "accessibility_pct": f"{category}_{hour}h_{threshold}min_pct",
                "accessible_count": f"{category}_{hour}h_{threshold}min_count",
            }
        )

        return subset

    # ------------------------------------------------------------------
    # 3. Build the analytical surface
    #
    # The surface contains:
    #   - 15/30 minute accessibility
    #   - midday baseline
    #   - evening peak accessibility
    #   - peak-hour deterioration
    #   - combined health + education accessibility
    # ------------------------------------------------------------------

    surface = origins.copy()

    categories = ["health", "education", "employment"]
    hours = [7, 9, 13, 18, 22]
    thresholds = [15, 30, 45, 60]

    for category in categories:
        for hour in hours:
            for threshold in thresholds:
                piece = get_slice(category, hour, threshold)
                surface = surface.merge(
                    piece,
                    on="origin_id",
                    how="left",
                )

    # ------------------------------------------------------------------
    # 4. Core 30-minute accessibility indicators
    # ------------------------------------------------------------------

    for category in categories:
        surface[f"{category}_30min_midday_pct"] = surface[
            f"{category}_13h_30min_pct"
        ]

        surface[f"{category}_30min_peak_pct"] = surface[
            f"{category}_18h_30min_pct"
        ]

        surface[f"{category}_30min_peak_loss_pp"] = (
            surface[f"{category}_13h_30min_pct"]
            - surface[f"{category}_18h_30min_pct"]
        )

    # ------------------------------------------------------------------
    # 5. Combined health + education access
    #
    # We deliberately do NOT mix employment into this composite because
    # the employment source contains only 16 distinct mapped locations.
    # ------------------------------------------------------------------

    surface["life_access_30min_midday_pct"] = (
        surface["health_30min_midday_pct"]
        + surface["education_30min_midday_pct"]
    ) / 2

    surface["life_access_30min_peak_pct"] = (
        surface["health_30min_peak_pct"]
        + surface["education_30min_peak_pct"]
    ) / 2

    surface["life_access_peak_loss_pp"] = (
        surface["life_access_30min_midday_pct"]
        - surface["life_access_30min_peak_pct"]
    )

    # ------------------------------------------------------------------
    # 6. Accessibility curve AUC
    #
    # AUC across 15/30/45/60 minutes.
    #
    # This measures how quickly opportunity becomes reachable.
    # Higher AUC = better accessibility across the whole travel budget.
    # ------------------------------------------------------------------

    def calculate_auc(row, category, hour):
        x = np.array([15, 30, 45, 60], dtype=float)

        y = np.array(
            [
                row[f"{category}_{hour}h_15min_pct"],
                row[f"{category}_{hour}h_30min_pct"],
                row[f"{category}_{hour}h_45min_pct"],
                row[f"{category}_{hour}h_60min_pct"],
            ],
            dtype=float,
        )

        return np.trapezoid(y, x) / 45.0

    for category in categories:
        for hour in [13, 18]:
            surface[f"{category}_{hour}h_accessibility_auc"] = surface.apply(
                calculate_auc,
                axis=1,
                category=category,
                hour=hour,
            )

    # ------------------------------------------------------------------
    # 7. A combined health + education AUC
    # ------------------------------------------------------------------

    surface["life_access_13h_auc"] = (
        surface["health_13h_accessibility_auc"]
        + surface["education_13h_accessibility_auc"]
    ) / 2

    surface["life_access_18h_auc"] = (
        surface["health_18h_accessibility_auc"]
        + surface["education_18h_accessibility_auc"]
    ) / 2

    surface["life_access_auc_peak_loss"] = (
        surface["life_access_13h_auc"]
        - surface["life_access_18h_auc"]
    )

    # ------------------------------------------------------------------
    # 8. Fragility score
    #
    # High value = good midday access but meaningful peak-hour loss.
    #
    # This is NOT a universal "quality of life" score.
    # It specifically measures temporal fragility.
    # ------------------------------------------------------------------

    surface["temporal_fragility"] = (
        surface["life_access_peak_loss_pp"].clip(lower=0)
    )

    # ------------------------------------------------------------------
    # 9. Rank origins
    # ------------------------------------------------------------------

    surface["midday_access_rank"] = (
        surface["life_access_30min_midday_pct"]
        .rank(method="min", ascending=False)
        .astype(int)
    )

    surface["peak_access_rank"] = (
        surface["life_access_30min_peak_pct"]
        .rank(method="min", ascending=False)
        .astype(int)
    )

    surface["fragility_rank"] = (
        surface["temporal_fragility"]
        .rank(method="min", ascending=False)
        .astype(int)
    )

    # ------------------------------------------------------------------
    # 10. Accessibility classification
    # ------------------------------------------------------------------

    def classify_access(value):
        if pd.isna(value):
            return "unknown"
        if value < 25:
            return "very_low"
        if value < 50:
            return "low"
        if value < 75:
            return "moderate"
        if value < 90:
            return "high"
        return "very_high"

    surface["access_class"] = surface[
        "life_access_30min_midday_pct"
    ].apply(classify_access)

    # ------------------------------------------------------------------
    # 11. Validate
    # ------------------------------------------------------------------

    numeric_cols = [
        "health_30min_midday_pct",
        "education_30min_midday_pct",
        "employment_30min_midday_pct",
        "life_access_30min_midday_pct",
        "life_access_30min_peak_pct",
        "temporal_fragility",
    ]

    for col in numeric_cols:
        if not surface[col].between(-0.001, 100.001).all():
            raise ValueError(f"Invalid accessibility values detected in {col}")

    if surface["origin_id"].duplicated().any():
        raise ValueError("Duplicate origin IDs detected.")

    # ------------------------------------------------------------------
    # 12. Save
    # ------------------------------------------------------------------

    output = OUTPUT_DIR / "bengaluru_accessibility_surface.csv"

    surface.to_csv(output, index=False)

    # Compact map-ready version
    map_columns = [
        "origin_id",
        "latitude",
        "longitude",
        "health_30min_midday_pct",
        "education_30min_midday_pct",
        "employment_30min_midday_pct",
        "life_access_30min_midday_pct",
        "life_access_30min_peak_pct",
        "life_access_peak_loss_pp",
        "life_access_13h_auc",
        "life_access_18h_auc",
        "life_access_auc_peak_loss",
        "temporal_fragility",
        "midday_access_rank",
        "peak_access_rank",
        "fragility_rank",
        "access_class",
    ]

    map_output = OUTPUT_DIR / "bengaluru_accessibility_map.csv"

    surface[map_columns].to_csv(
        map_output,
        index=False,
    )

    # ------------------------------------------------------------------
    # 13. Summary
    # ------------------------------------------------------------------

    summary = pd.DataFrame(
        {
            "metric": [
                "origins",
                "mean_30min_midday_access",
                "median_30min_midday_access",
                "p10_30min_midday_access",
                "p90_30min_midday_access",
                "mean_peak_hour_loss",
                "max_peak_hour_loss",
                "origins_below_25pct_access",
                "origins_above_90pct_access",
            ],
            "value": [
                len(surface),
                surface["life_access_30min_midday_pct"].mean(),
                surface["life_access_30min_midday_pct"].median(),
                surface["life_access_30min_midday_pct"].quantile(0.10),
                surface["life_access_30min_midday_pct"].quantile(0.90),
                surface["life_access_peak_loss_pp"].mean(),
                surface["life_access_peak_loss_pp"].max(),
                (
                    surface["life_access_30min_midday_pct"] < 25
                ).sum(),
                (
                    surface["life_access_30min_midday_pct"] >= 90
                ).sum(),
            ],
        }
    )

    summary.to_csv(
        OUTPUT_DIR / "surface_summary.csv",
        index=False,
    )

    # ------------------------------------------------------------------
    # 14. Print useful research findings
    # ------------------------------------------------------------------

    print()
    print("=" * 80)
    print("ACCESSIBILITY SURFACE RESULTS")
    print("=" * 80)

    print(
        f"Origins: {len(surface):,}"
    )

    print(
        f"Mean 30-min health + education access: "
        f"{surface['life_access_30min_midday_pct'].mean():.2f}%"
    )

    print(
        f"Median 30-min health + education access: "
        f"{surface['life_access_30min_midday_pct'].median():.2f}%"
    )

    print(
        f"P10 access: "
        f"{surface['life_access_30min_midday_pct'].quantile(.10):.2f}%"
    )

    print(
        f"P90 access: "
        f"{surface['life_access_30min_midday_pct'].quantile(.90):.2f}%"
    )

    print(
        f"Mean peak-hour loss: "
        f"{surface['life_access_peak_loss_pp'].mean():.2f} pp"
    )

    print(
        f"Maximum peak-hour loss: "
        f"{surface['life_access_peak_loss_pp'].max():.2f} pp"
    )

    print()
    print("10 LOWEST-ACCESS ORIGINS")
    print("-" * 80)

    print(
        surface[
            [
                "origin_id",
                "latitude",
                "longitude",
                "life_access_30min_midday_pct",
                "life_access_peak_loss_pp",
            ]
        ]
        .sort_values("life_access_30min_midday_pct")
        .head(10)
        .to_string(index=False)
    )

    print()
    print("10 MOST TEMPORALLY FRAGILE ORIGINS")
    print("-" * 80)

    print(
        surface[
            [
                "origin_id",
                "latitude",
                "longitude",
                "life_access_30min_midday_pct",
                "life_access_peak_loss_pp",
            ]
        ]
        .sort_values(
            "life_access_peak_loss_pp",
            ascending=False,
        )
        .head(10)
        .to_string(index=False)
    )

    print()
    print("OUTPUTS")
    print("-" * 80)
    print(output)
    print(map_output)
    print(OUTPUT_DIR / "surface_summary.csv")

    print()
    print("DONE.")


if __name__ == "__main__":
    main()