from pathlib import Path
import pandas as pd
import numpy as np


ROOT = Path(__file__).resolve().parents[2]

INPUT = (
    ROOT
    / "data"
    / "processed"
    / "accessibility"
    / "bengaluru_time_accessibility.csv"
)

OUTPUT_DIR = (
    ROOT
    / "data"
    / "processed"
    / "analysis"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# LOAD
# ============================================================

df = pd.read_csv(INPUT)

print("\nLoaded:")
print(f"Rows: {len(df):,}")


# ============================================================
# 1. ACCESSIBILITY CURVE AREA
# ============================================================

curve = (
    df.groupby(
        [
            "origin",
            "hour",
            "category",
        ]
    )
    .apply(
        lambda g: np.trapezoid(
            g["accessibility_share"],
            g["threshold_min"]
        ),
        include_groups=False
    )
    .reset_index(
        name="accessibility_curve_auc"
    )
)

curve.to_csv(
    OUTPUT_DIR
    / "accessibility_curve_auc.csv",
    index=False
)


# ============================================================
# 2. MAIN ACCESSIBILITY METRICS
# ============================================================

pivot = df.pivot_table(
    index=[
        "origin",
        "hour",
        "category",
    ],
    columns="threshold_min",
    values="accessibility_share"
).reset_index()

pivot.columns.name = None

pivot = pivot.rename(
    columns={
        15: "access_15",
        30: "access_30",
        45: "access_45",
        60: "access_60",
    }
)

metrics = pivot.merge(
    curve,
    on=[
        "origin",
        "hour",
        "category",
    ],
    how="left"
)


# ============================================================
# 3. PEAK-HOUR PENALTY
# ============================================================

base = metrics[
    metrics["hour"] == 13
][
    [
        "origin",
        "category",
        "access_15",
        "access_30",
        "access_45",
        "access_60",
    ]
].copy()

base = base.rename(
    columns={
        "access_15": "midday_15",
        "access_30": "midday_30",
        "access_45": "midday_45",
        "access_60": "midday_60",
    }
)

peak = metrics[
    metrics["hour"] == 18
][
    [
        "origin",
        "category",
        "access_15",
        "access_30",
        "access_45",
        "access_60",
    ]
].copy()

peak = peak.rename(
    columns={
        "access_15": "peak_15",
        "access_30": "peak_30",
        "access_45": "peak_45",
        "access_60": "peak_60",
    }
)

peak_penalty = base.merge(
    peak,
    on=[
        "origin",
        "category",
    ]
)

for threshold in [15, 30, 45, 60]:

    peak_penalty[
        f"peak_loss_{threshold}"
    ] = (
        peak_penalty[
            f"midday_{threshold}"
        ]
        - peak_penalty[
            f"peak_{threshold}"
        ]
    )

peak_penalty.to_csv(
    OUTPUT_DIR
    / "peak_hour_penalty.csv",
    index=False
)


# ============================================================
# 4. LOCATION RANKINGS
# ============================================================

rankings = (
    metrics[
        metrics["hour"] == 13
    ]
    .sort_values(
        [
            "category",
            "accessibility_curve_auc",
        ],
        ascending=[
            True,
            False,
        ]
    )
    [
        [
            "origin",
            "category",
            "access_15",
            "access_30",
            "access_45",
            "access_60",
            "accessibility_curve_auc",
        ]
    ]
)

rankings.to_csv(
    OUTPUT_DIR
    / "midday_location_rankings.csv",
    index=False
)


# ============================================================
# 5. CITY-LEVEL INEQUALITY
# ============================================================

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
        .values
    )

    mean = values.mean()

    std = values.std(
        ddof=0
    )

    minimum = values.min()

    maximum = values.max()

    gap = maximum - minimum

    # Coefficient of variation.
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
            "mean_accessibility": mean,
            "std_accessibility": std,
            "min_accessibility": minimum,
            "max_accessibility": maximum,
            "max_minus_min_gap": gap,
            "coefficient_of_variation": cv,
        }
    )

inequality = pd.DataFrame(
    inequality_rows
)

inequality.to_csv(
    OUTPUT_DIR
    / "accessibility_inequality.csv",
    index=False
)


# ============================================================
# 6. PEAK-HOUR CITY IMPACT
# ============================================================

peak_city = (
    df.groupby(
        [
            "hour",
            "category",
            "threshold_min",
        ]
    )[
        "accessibility_share"
    ]
    .agg(
        mean="mean",
        median="median",
        minimum="min",
        maximum="max",
    )
    .reset_index()
)

peak_city.to_csv(
    OUTPUT_DIR
    / "city_accessibility_summary.csv",
    index=False
)


# ============================================================
# 7. PRINT RESEARCH FINDINGS
# ============================================================

print(
    "\n"
    + "=" * 70
)

print(
    "ACCESSIBILITY RESEARCH SUMMARY"
)

print(
    "=" * 70
)


print(
    "\n--- MIDDAY 15-MINUTE ACCESSIBILITY ---"
)

midday = metrics[
    metrics["hour"] == 13
]

for category in [
    "health",
    "education",
    "employment",
]:

    subset = midday[
        midday["category"]
        == category
    ]

    best = subset.loc[
        subset["access_15"].idxmax()
    ]

    worst = subset.loc[
        subset["access_15"].idxmin()
    ]

    print(
        f"\n{category.upper()}"
    )

    print(
        f"Best : "
        f"{best['origin']} "
        f"({best['access_15']:.1%})"
    )

    print(
        f"Worst: "
        f"{worst['origin']} "
        f"({worst['access_15']:.1%})"
    )


print(
    "\n--- 30-MINUTE INEQUALITY ---"
)

for category in [
    "health",
    "education",
    "employment",
]:

    subset = inequality[
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
    ]

    row = subset.iloc[0]

    print(
        f"{category:12s}: "
        f"mean={row['mean_accessibility']:.1%}, "
        f"gap={row['max_minus_min_gap']:.1%}, "
        f"CV={row['coefficient_of_variation']:.3f}"
    )


print(
    "\n--- 1 PM → 6 PM ACCESSIBILITY LOSS ---"
)

for category in [
    "health",
    "education",
    "employment",
]:

    subset = peak_penalty[
        peak_penalty["category"]
        == category
    ]

    print(
        f"\n{category.upper()}"
    )

    print(
        f"15 min mean loss: "
        f"{subset['peak_loss_15'].mean():.1%}"
    )

    print(
        f"30 min mean loss: "
        f"{subset['peak_loss_30'].mean():.1%}"
    )

    print(
        f"45 min mean loss: "
        f"{subset['peak_loss_45'].mean():.1%}"
    )

    print(
        f"60 min mean loss: "
        f"{subset['peak_loss_60'].mean():.1%}"
    )


print(
    "\n--- LOCATION RANKING BY ACCESSIBILITY CURVE ---"
)

for category in [
    "health",
    "education",
    "employment",
]:

    subset = rankings[
        rankings["category"]
        == category
    ]

    print(
        f"\n{category.upper()}"
    )

    print(
        subset[
            [
                "origin",
                "access_15",
                "access_30",
                "accessibility_curve_auc",
            ]
        ]
        .to_string(
            index=False
        )
    )


print(
    "\n"
    + "=" * 70
)

print(
    "ANALYSIS COMPLETE"
)

print(
    "=" * 70
)

print(
    f"\nOutputs saved to:"
    f"\n{OUTPUT_DIR}"
)