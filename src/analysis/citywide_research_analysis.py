from pathlib import Path
import pandas as pd
import numpy as np


ROOT = Path(__file__).resolve().parents[2]

INPUT = (
    ROOT
    / "data"
    / "processed"
    / "citywide"
    / "bengaluru_citywide_accessibility.csv"
)

ORIGINS = (
    ROOT
    / "data"
    / "processed"
    / "citywide"
    / "citywide_origins.csv"
)

OUT = (
    ROOT
    / "data"
    / "processed"
    / "analysis"
    / "citywide"
)

OUT.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# LOAD
# ============================================================

df = pd.read_csv(INPUT)
origins = pd.read_csv(ORIGINS)

print("\nLoaded citywide accessibility:")
print(f"Rows: {len(df):,}")
print(f"Origins: {origins['origin_id'].nunique():,}")


# ============================================================
# 1. GRID QUALITY CHECK
# ============================================================

print("\n" + "=" * 70)
print("1. GRID QUALITY")
print("=" * 70)

# Check spatial coverage.
print(
    f"Latitude range : "
    f"{origins['latitude'].min():.4f} → "
    f"{origins['latitude'].max():.4f}"
)

print(
    f"Longitude range: "
    f"{origins['longitude'].min():.4f} → "
    f"{origins['longitude'].max():.4f}"
)

# Approximate nearest-neighbor spacing.
coords = origins[
    ["latitude", "longitude"]
].to_numpy()

sample = coords[
    :min(len(coords), 1000)
]

nearest_distances = []

for i in range(len(sample)):

    dlat = (
        sample[:, 0]
        - sample[i, 0]
    )

    dlon = (
        sample[:, 1]
        - sample[i, 1]
    )

    distances = (
        np.sqrt(
            dlat ** 2
            + dlon ** 2
        )
        * 111.0
    )

    distances[i] = np.inf

    nearest_distances.append(
        distances.min()
    )

nearest_distances = np.array(
    nearest_distances
)

print(
    f"Median nearest-origin "
    f"spacing: "
    f"{np.median(nearest_distances):.2f} km"
)

print(
    f"P90 nearest-origin spacing: "
    f"{np.percentile(nearest_distances, 90):.2f} km"
)


# ============================================================
# 2. ACCESSIBILITY CURVES
# ============================================================

print("\n" + "=" * 70)
print("2. ACCESSIBILITY CURVES")
print("=" * 70)

curve_rows = []

for (
    origin_id,
    hour,
    category,
), group in df.groupby(
    [
        "origin_id",
        "hour",
        "category",
    ]
):

    group = group.sort_values(
        "threshold_min"
    )

    x = group[
        "threshold_min"
    ].to_numpy()

    y = group[
        "accessibility_share"
    ].to_numpy()

    auc = np.trapezoid(
        y,
        x
    )

    curve_rows.append(
        {
            "origin_id": origin_id,
            "hour": hour,
            "category": category,
            "auc": auc,
        }
    )

curves = pd.DataFrame(
    curve_rows
)

curves.to_csv(
    OUT
    / "accessibility_curves.csv",
    index=False
)


# ============================================================
# 3. SPATIAL INEQUALITY
# ============================================================

print("\n" + "=" * 70)
print("3. SPATIAL INEQUALITY")
print("=" * 70)

inequality_rows = []

for (
    hour,
    category,
    threshold,
), group in df.groupby(
    [
        "hour",
        "category",
        "threshold_min",
    ]
):

    values = (
        group[
            "accessibility_share"
        ]
        .astype(float)
        .to_numpy()
    )

    mean = values.mean()

    median = np.median(
        values
    )

    p10 = np.percentile(
        values,
        10
    )

    p90 = np.percentile(
        values,
        90
    )

    minimum = values.min()

    maximum = values.max()

    std = values.std()

    cv = (
        std / mean
        if mean > 0
        else np.nan
    )

    inequality_rows.append(
        {
            "hour": hour,
            "category": category,
            "threshold_min": threshold,
            "mean": mean,
            "median": median,
            "p10": p10,
            "p90": p90,
            "p90_minus_p10": (
                p90 - p10
            ),
            "minimum": minimum,
            "maximum": maximum,
            "max_minus_min": (
                maximum - minimum
            ),
            "std": std,
            "cv": cv,
        }
    )

inequality = pd.DataFrame(
    inequality_rows
)

inequality.to_csv(
    OUT
    / "spatial_inequality.csv",
    index=False
)


# ============================================================
# 4. PEAK-HOUR ACCESSIBILITY LOSS
# ============================================================

print("\n" + "=" * 70)
print("4. TIME-OF-DAY ACCESSIBILITY LOSS")
print("=" * 70)

midday = df[
    df["hour"] == 13
][
    [
        "origin_id",
        "category",
        "threshold_min",
        "accessibility_share",
    ]
].rename(
    columns={
        "accessibility_share":
            "midday_access"
    }
)

peak = df[
    df["hour"] == 18
][
    [
        "origin_id",
        "category",
        "threshold_min",
        "accessibility_share",
    ]
].rename(
    columns={
        "accessibility_share":
            "peak_access"
    }
)

loss = midday.merge(
    peak,
    on=[
        "origin_id",
        "category",
        "threshold_min",
    ]
)

loss["absolute_loss"] = (
    loss["midday_access"]
    - loss["peak_access"]
)

loss["relative_loss"] = np.where(
    loss["midday_access"] > 0,
    (
        loss["absolute_loss"]
        / loss["midday_access"]
    ),
    np.nan
)

loss.to_csv(
    OUT
    / "peak_hour_accessibility_loss.csv",
    index=False
)


# ============================================================
# 5. LOW-ACCESSIBILITY HOTSPOTS
# ============================================================

print("\n" + "=" * 70)
print("5. LOW-ACCESSIBILITY HOTSPOTS")
print("=" * 70)

# Focus on the most meaningful 30-minute threshold.
low_access = df[
    (
        df["threshold_min"]
        == 30
    )
    &
    (
        df["hour"]
        == 18
    )
].copy()

# Rank separately for each category.
hotspot_rows = []

for category in [
    "health",
    "education",
    "employment",
]:

    subset = low_access[
        low_access["category"]
        == category
    ].copy()

    subset = subset.sort_values(
        "accessibility_share"
    )

    bottom_n = subset.head(
        min(25, len(subset))
    )

    for rank, (_, row) in enumerate(
        bottom_n.iterrows(),
        start=1
    ):

        hotspot_rows.append(
            {
                "category": category,
                "rank": rank,
                "origin_id": (
                    row["origin_id"]
                ),
                "latitude": (
                    row["latitude"]
                ),
                "longitude": (
                    row["longitude"]
                ),
                "accessibility_share": (
                    row[
                        "accessibility_share"
                    ]
                ),
            }
        )

hotspots = pd.DataFrame(
    hotspot_rows
)

hotspots.to_csv(
    OUT
    / "low_accessibility_hotspots.csv",
    index=False
)


# ============================================================
# 6. CROSS-DOMAIN DISADVANTAGE
# ============================================================

print("\n" + "=" * 70)
print("6. CROSS-DOMAIN ACCESSIBILITY")
print("=" * 70)

cross = df[
    (
        df["hour"] == 18
    )
    &
    (
        df["threshold_min"] == 30
    )
    &
    (
        df["category"].isin(
            [
                "health",
                "education",
            ]
        )
    )
]

cross = cross.pivot_table(
    index=[
        "origin_id",
        "latitude",
        "longitude",
    ],
    columns="category",
    values="accessibility_share"
).reset_index()

cross.columns.name = None

cross["combined_access"] = (
    cross["health"]
    + cross["education"]
) / 2

cross["cross_domain_gap"] = (
    cross[
        [
            "health",
            "education",
        ]
    ].max(axis=1)
    -
    cross[
        [
            "health",
            "education",
        ]
    ].min(axis=1)
)

cross = cross.sort_values(
    "combined_access"
)

cross.to_csv(
    OUT
    / "cross_domain_accessibility.csv",
    index=False
)


# ============================================================
# 7. PRINT KEY FINDINGS
# ============================================================

print("\n" + "=" * 70)
print("KEY RESEARCH FINDINGS")
print("=" * 70)


# ------------------------------------------------------------
# 30-minute midday
# ------------------------------------------------------------

print(
    "\n--- 30-MINUTE MIDDAY ACCESS ---"
)

for category in [
    "health",
    "education",
    "employment",
]:

    row = inequality[
        (
            inequality["hour"]
            == 13
        )
        &
        (
            inequality["category"]
            == category
        )
        &
        (
            inequality["threshold_min"]
            == 30
        )
    ].iloc[0]

    print(
        f"{category:12s}: "
        f"mean={row['mean']:.1%} | "
        f"median={row['median']:.1%} | "
        f"P10={row['p10']:.1%} | "
        f"P90={row['p90']:.1%} | "
        f"gap={row['p90_minus_p10']:.1%}"
    )


# ------------------------------------------------------------
# 18:00 penalty
# ------------------------------------------------------------

print(
    "\n--- 1 PM → 6 PM LOSS ---"
)

for category in [
    "health",
    "education",
    "employment",
]:

    subset = loss[
        loss["category"]
        == category
    ]

    for threshold in [
        15,
        30,
    ]:

        row = subset[
            subset["threshold_min"]
            == threshold
        ]

        print(
            f"{category:12s} "
            f"{threshold:2d} min: "
            f"mean absolute loss="
            f"{row['absolute_loss'].mean():.1%}"
        )


# ------------------------------------------------------------
# Lowest accessibility
# ------------------------------------------------------------

print(
    "\n--- LOWEST 30-MIN ACCESSIBILITY "
    "AT 6 PM ---"
)

for category in [
    "health",
    "education",
    "employment",
]:

    subset = hotspots[
        hotspots["category"]
        == category
    ]

    print(
        f"\n{category.upper()}"
    )

    print(
        subset[
            [
                "rank",
                "origin_id",
                "latitude",
                "longitude",
                "accessibility_share",
            ]
        ]
        .head(10)
        .to_string(
            index=False
        )
    )


# ------------------------------------------------------------
# Cross-domain
# ------------------------------------------------------------

print(
    "\n--- CROSS-DOMAIN LOW ACCESS ---"
)

print(
    cross.head(10)[
        [
            "origin_id",
            "latitude",
            "longitude",
            "health",
            "education",
            "combined_access",
        ]
    ]
    .to_string(
        index=False
    )
)


# ============================================================
# DONE
# ============================================================

print(
    "\n"
    + "=" * 70
)

print(
    "CITYWIDE RESEARCH ANALYSIS COMPLETE"
)

print(
    "=" * 70
)

print(
    f"\nOutputs saved to:\n{OUT}"
)