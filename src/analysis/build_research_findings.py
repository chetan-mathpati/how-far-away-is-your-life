from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

CURVE_DIR = ROOT / "data" / "processed" / "accessibility_curves"
SURFACE_DIR = ROOT / "data" / "processed" / "accessibility_surface"
INTERVENTION_DIR = ROOT / "data" / "processed" / "interventions"
OUTPUT_DIR = ROOT / "data" / "processed" / "research_findings"


def pct(value):
    if value is None or pd.isna(value):
        return None
    return round(float(value), 4)


def require_columns(df, columns, name):
    missing = [c for c in columns if c not in df.columns]

    if missing:
        raise ValueError(
            f"{name} is missing required columns: {missing}\n"
            f"Available columns: {df.columns.tolist()}"
        )


def main():

    print("=" * 80)
    print("BUILD RESEARCH FINDINGS")
    print("=" * 80)

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ==================================================================
    # 1. LOAD DATA
    # ==================================================================

    print("\n[1/7] Loading analytical datasets...")

    curves = pd.read_csv(
        CURVE_DIR / "bengaluru_accessibility_curves.csv"
    )

    origin_curves = pd.read_csv(
        CURVE_DIR / "origin_accessibility_curve_features.csv"
    )

    time_comparison = pd.read_csv(
        CURVE_DIR / "midday_vs_peak_accessibility.csv"
    )

    surface = pd.read_csv(
        SURFACE_DIR / "bengaluru_accessibility_surface.csv"
    )

    ranking = pd.read_csv(
        INTERVENTION_DIR / "intervention_ranking.csv"
    )

    require_columns(
        curves,
        [
            "hour",
            "category",
            "threshold_minutes",
            "mean_accessibility_pct",
            "median_accessibility_pct",
            "p10_accessibility_pct",
            "p25_accessibility_pct",
            "p75_accessibility_pct",
            "p90_accessibility_pct",
            "min_accessibility_pct",
            "max_accessibility_pct",
            "std_accessibility_pct",
            "origins",
        ],
        "bengaluru_accessibility_curves.csv",
    )

    require_columns(
        origin_curves,
        [
            "origin_id",
            "latitude",
            "longitude",
            "hour",
            "category",
            "access_15min_pct",
            "access_30min_pct",
            "access_45min_pct",
            "access_60min_pct",
        ],
        "origin_accessibility_curve_features.csv",
    )

    require_columns(
        time_comparison,
        [
            "origin_id",
            "category",
            "threshold_minutes",
            "midday_access_pct",
            "peak_access_pct",
            "peak_hour_loss_pp",
        ],
        "midday_vs_peak_accessibility.csv",
    )

    # This is the REAL schema produced by build_accessibility_surface.py.
    require_columns(
        surface,
        [
            "origin_id",
            "latitude",
            "longitude",
            "health_30min_midday_pct",
            "education_30min_midday_pct",
            "employment_30min_midday_pct",
            "life_access_30min_midday_pct",
            "life_access_30min_peak_pct",
            "life_access_peak_loss_pp",
            "temporal_fragility",
            "midday_access_rank",
            "peak_access_rank",
            "fragility_rank",
            "access_class",
        ],
        "bengaluru_accessibility_surface.csv",
    )

    require_columns(
        ranking,
        [
            "candidate_id",
            "origin_id",
            "latitude",
            "longitude",
            "baseline_access_pct",
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
            "impact_rank",
        ],
        "intervention_ranking.csv",
    )

    print(
        f"  Curve summary rows: {len(curves):,}"
    )

    print(
        f"  Origin curve rows: {len(origin_curves):,}"
    )

    print(
        f"  Time comparison rows: {len(time_comparison):,}"
    )

    print(
        f"  Surface rows: {len(surface):,}"
    )

    print(
        f"  Intervention candidates: {len(ranking):,}"
    )

    # ==================================================================
    # 2. CATEGORY ACCESSIBILITY
    # ==================================================================

    print(
        "\n[2/7] Computing category accessibility findings..."
    )

    midday_30 = curves[
        (curves["hour"] == 13)
        & (curves["threshold_minutes"] == 30)
    ].copy()

    category_findings = []

    for _, row in midday_30.iterrows():

        category_findings.append(
            {
                "category": row["category"],
                "hour": int(row["hour"]),
                "threshold_minutes": int(
                    row["threshold_minutes"]
                ),
                "mean_accessibility_pct": pct(
                    row["mean_accessibility_pct"]
                ),
                "median_accessibility_pct": pct(
                    row["median_accessibility_pct"]
                ),
                "p10_accessibility_pct": pct(
                    row["p10_accessibility_pct"]
                ),
                "p90_accessibility_pct": pct(
                    row["p90_accessibility_pct"]
                ),
                "accessibility_iqr_pp": pct(
                    row["p75_accessibility_pct"]
                    - row["p25_accessibility_pct"]
                ),
                "min_accessibility_pct": pct(
                    row["min_accessibility_pct"]
                ),
                "max_accessibility_pct": pct(
                    row["max_accessibility_pct"]
                ),
                "std_accessibility_pct": pct(
                    row["std_accessibility_pct"]
                ),
            }
        )

    category_df = pd.DataFrame(
        category_findings
    )

    category_df.to_csv(
        OUTPUT_DIR / "category_accessibility_findings.csv",
        index=False,
    )

    print(
        category_df[
            [
                "category",
                "mean_accessibility_pct",
                "median_accessibility_pct",
                "p10_accessibility_pct",
                "p90_accessibility_pct",
            ]
        ].to_string(index=False)
    )

    # ==================================================================
    # 3. TRAVEL-TIME BUDGET GROWTH
    # ==================================================================

    print(
        "\n[3/7] Measuring the value of additional travel time..."
    )

    growth_summary = (
        curves
        .pivot_table(
            index=[
                "hour",
                "category",
            ],
            columns="threshold_minutes",
            values="mean_accessibility_pct",
            aggfunc="first",
        )
        .reset_index()
    )

    growth_summary.columns.name = None

    rename = {}

    for threshold in [
        15,
        30,
        45,
        60,
    ]:

        if threshold in growth_summary.columns:

            rename[
                threshold
            ] = f"mean_access_{threshold}min_pct"

    growth_summary = growth_summary.rename(
        columns=rename
    )

    if (
        "mean_access_15min_pct"
        in growth_summary.columns
        and
        "mean_access_30min_pct"
        in growth_summary.columns
    ):

        growth_summary[
            "gain_15_to_30_pp"
        ] = (
            growth_summary[
                "mean_access_30min_pct"
            ]
            -
            growth_summary[
                "mean_access_15min_pct"
            ]
        )

    if (
        "mean_access_30min_pct"
        in growth_summary.columns
        and
        "mean_access_45min_pct"
        in growth_summary.columns
    ):

        growth_summary[
            "gain_30_to_45_pp"
        ] = (
            growth_summary[
                "mean_access_45min_pct"
            ]
            -
            growth_summary[
                "mean_access_30min_pct"
            ]
        )

    if (
        "mean_access_45min_pct"
        in growth_summary.columns
        and
        "mean_access_60min_pct"
        in growth_summary.columns
    ):

        growth_summary[
            "gain_45_to_60_pp"
        ] = (
            growth_summary[
                "mean_access_60min_pct"
            ]
            -
            growth_summary[
                "mean_access_45min_pct"
            ]
        )

    growth_summary = growth_summary.sort_values(
        [
            "hour",
            "category",
        ]
    )

    growth_summary.to_csv(
        OUTPUT_DIR / "travel_time_budget_growth.csv",
        index=False,
    )

    print(
        growth_summary[
            [
                "hour",
                "category",
                "mean_access_15min_pct",
                "mean_access_30min_pct",
                "mean_access_45min_pct",
                "mean_access_60min_pct",
                "gain_15_to_30_pp",
            ]
        ].to_string(index=False)
    )

    # ==================================================================
    # 4. PEAK-HOUR EFFECT
    # ==================================================================

    print(
        "\n[4/7] Measuring peak-hour accessibility loss..."
    )

    peak = (
        time_comparison
        .groupby(
            [
                "category",
                "threshold_minutes",
            ],
            as_index=False,
        )
        .agg(
            mean_peak_hour_loss_pp=(
                "peak_hour_loss_pp",
                "mean",
            ),
            median_peak_hour_loss_pp=(
                "peak_hour_loss_pp",
                "median",
            ),
            p90_peak_hour_loss_pp=(
                "peak_hour_loss_pp",
                lambda x: x.quantile(
                    0.90
                ),
            ),
            max_peak_hour_loss_pp=(
                "peak_hour_loss_pp",
                "max",
            ),
            origins=(
                "origin_id",
                "nunique",
            ),
        )
        .sort_values(
            [
                "category",
                "threshold_minutes",
            ]
        )
    )

    peak.to_csv(
        OUTPUT_DIR
        / "peak_hour_accessibility_loss.csv",
        index=False,
    )

    print(
        peak.to_string(
            index=False
        )
    )

    # ==================================================================
    # 5. LOW ACCESSIBILITY
    # ==================================================================

    print(
        "\n[5/7] Identifying locations with lowest accessibility..."
    )

    # The surface already contains the final combined life-access
    # metric for 30-minute midday accessibility.
    #
    # Do NOT reconstruct this metric from scratch.
    # We use the canonical value generated by
    # build_accessibility_surface.py.

    disadvantaged = (
        surface[
            [
                "origin_id",
                "latitude",
                "longitude",
                "life_access_30min_midday_pct",
                "health_30min_midday_pct",
                "education_30min_midday_pct",
                "employment_30min_midday_pct",
                "access_class",
                "midday_access_rank",
            ]
        ]
        .copy()
        .sort_values(
            "life_access_30min_midday_pct"
        )
        .reset_index(drop=True)
    )

    disadvantaged[
        "disadvantage_rank"
    ] = range(
        1,
        len(disadvantaged) + 1,
    )

    disadvantaged.to_csv(
        OUTPUT_DIR
        / "lowest_accessibility_origins.csv",
        index=False,
    )

    print(
        "\n  Lowest-access origins:"
    )

    print(
        disadvantaged.head(
            10
        ).to_string(
            index=False
        )
    )

    # ==================================================================
    # 6. TEMPORAL FRAGILITY
    # ==================================================================

    print(
        "\n[6/7] Identifying temporally fragile locations..."
    )

    temporal = (
        surface[
            [
                "origin_id",
                "latitude",
                "longitude",
                "life_access_30min_midday_pct",
                "life_access_30min_peak_pct",
                "life_access_peak_loss_pp",
                "temporal_fragility",
                "fragility_rank",
            ]
        ]
        .copy()
        .sort_values(
            "life_access_peak_loss_pp",
            ascending=False,
        )
        .reset_index(drop=True)
    )

    temporal[
        "temporal_fragility_rank"
    ] = range(
        1,
        len(temporal) + 1,
    )

    temporal.to_csv(
        OUTPUT_DIR
        / "temporally_fragile_origins.csv",
        index=False,
    )

    print(
        "\n  Most temporally fragile origins:"
    )

    print(
        temporal.head(
            10
        ).to_string(
            index=False
        )
    )

    # ==================================================================
    # 7. HEADLINE FINDINGS
    # ==================================================================

    print(
        "\n[7/7] Building headline research findings..."
    )

    def get_category_row(
        category
    ):

        rows = category_df[
            category_df[
                "category"
            ]
            == category
        ]

        if rows.empty:
            return None

        return rows.iloc[0]

    education = get_category_row(
        "education"
    )

    health = get_category_row(
        "health"
    )

    employment = get_category_row(
        "employment"
    )

    # --------------------------------------------------------------
    # Winner
    # --------------------------------------------------------------

    winner = (
        ranking
        .sort_values(
            "impact_rank"
        )
        .iloc[0]
    )

    # --------------------------------------------------------------
    # Combined life-access distribution
    # --------------------------------------------------------------

    combined_mean = (
        surface[
            "life_access_30min_midday_pct"
        ].mean()
    )

    combined_median = (
        surface[
            "life_access_30min_midday_pct"
        ].median()
    )

    combined_p10 = (
        surface[
            "life_access_30min_midday_pct"
        ].quantile(
            0.10
        )
    )

    combined_p90 = (
        surface[
            "life_access_30min_midday_pct"
        ].quantile(
            0.90
        )
    )

    # --------------------------------------------------------------
    # Peak-hour combined accessibility
    # --------------------------------------------------------------

    peak_loss_mean = (
        surface[
            "life_access_peak_loss_pp"
        ].mean()
    )

    peak_loss_median = (
        surface[
            "life_access_peak_loss_pp"
        ].median()
    )

    peak_loss_p90 = (
        surface[
            "life_access_peak_loss_pp"
        ].quantile(
            0.90
        )
    )

    peak_loss_max = (
        surface[
            "life_access_peak_loss_pp"
        ].max()
    )

    # --------------------------------------------------------------
    # Employment concentration diagnostic
    # --------------------------------------------------------------

    employment_15 = curves[
        (curves["hour"] == 13)
        &
        (curves["category"] == "employment")
        &
        (curves["threshold_minutes"] == 15)
    ]

    employment_30 = curves[
        (curves["hour"] == 13)
        &
        (curves["category"] == "employment")
        &
        (curves["threshold_minutes"] == 30)
    ]

    # --------------------------------------------------------------
    # Research findings object
    # --------------------------------------------------------------

    findings = {

        "project": (
            "How Far Away Is Your Life?"
        ),

        "study_area": (
            "Bengaluru"
        ),

        "core_question": (
            "How unequal is access to opportunity across "
            "Bengaluru when accessibility is measured by "
            "travel time rather than geographic distance?"
        ),

        "dataset": {

            "origins": int(
                origin_curves[
                    "origin_id"
                ].nunique()
            ),

            "hours": sorted(
                origin_curves[
                    "hour"
                ]
                .unique()
                .tolist()
            ),

            "categories": sorted(
                origin_curves[
                    "category"
                ]
                .unique()
                .tolist()
            ),

            "thresholds_minutes": [
                15,
                30,
                45,
                60,
            ],
        },

        "headline_findings": {

            "education_30min_midday_mean_pct":
                pct(
                    education[
                        "mean_accessibility_pct"
                    ]
                )
                if education is not None
                else None,

            "education_30min_midday_median_pct":
                pct(
                    education[
                        "median_accessibility_pct"
                    ]
                )
                if education is not None
                else None,

            "health_30min_midday_mean_pct":
                pct(
                    health[
                        "mean_accessibility_pct"
                    ]
                )
                if health is not None
                else None,

            "health_30min_midday_median_pct":
                pct(
                    health[
                        "median_accessibility_pct"
                    ]
                )
                if health is not None
                else None,

            "employment_30min_midday_mean_pct":
                pct(
                    employment[
                        "mean_accessibility_pct"
                    ]
                )
                if employment is not None
                else None,

            "employment_30min_midday_median_pct":
                pct(
                    employment[
                        "median_accessibility_pct"
                    ]
                )
                if employment is not None
                else None,

            "life_access_30min_midday_mean_pct":
                pct(
                    combined_mean
                ),

            "life_access_30min_midday_median_pct":
                pct(
                    combined_median
                ),

            "life_access_30min_midday_p10_pct":
                pct(
                    combined_p10
                ),

            "life_access_30min_midday_p90_pct":
                pct(
                    combined_p90
                ),

            "life_access_peak_loss_mean_pp":
                pct(
                    peak_loss_mean
                ),

            "life_access_peak_loss_median_pp":
                pct(
                    peak_loss_median
                ),

            "life_access_peak_loss_p90_pp":
                pct(
                    peak_loss_p90
                ),

            "life_access_peak_loss_max_pp":
                pct(
                    peak_loss_max
                ),

            "winning_intervention_origin":
                int(
                    winner["origin_id"]
                ),

            "winning_intervention_gain_pp":
                pct(
                    winner[
                        "total_access_gain_pct_points"
                    ]
                ),

            "winning_intervention_disadvantaged_gain_pp":
                pct(
                    winner[
                        "disadvantaged_total_gain"
                    ]
                ),

            "winning_intervention_affected_origins":
                int(
                    winner[
                        "origins_affected"
                    ]
                ),
        },

        "research_interpretation": {

            "education": (
                "Education has lower average 30-minute "
                "midday accessibility than health under "
                "the modeled network and opportunity distribution."
            ),

            "health": (
                "Health accessibility is somewhat higher "
                "than education at the 30-minute midday "
                "threshold, while remaining spatially unequal."
            ),

            "employment": (
                "Employment accessibility is strongly influenced "
                "by the spatial concentration of available job "
                "posting coordinates and should therefore be "
                "interpreted as job-opportunity intensity rather "
                "than a complete workplace distribution."
            ),

            "travel_time": (
                "The largest accessibility gains generally occur "
                "between 15 and 30 minutes, while accessibility "
                "approaches saturation by 45 to 60 minutes."
            ),

            "peak_hour": (
                "Peak traffic has its clearest system-wide effect "
                "at the 30-minute threshold, where modeled travel "
                "time increases can remove access to opportunities "
                "before longer travel budgets absorb the effect."
            ),

            "intervention": (
                "Origin 394 produces the largest modeled gain "
                "among the tested counterfactual intervention "
                "candidates."
            ),
        },

        "methodology_caveats": [

            (
                "Accessibility is measured as the share of "
                "mapped opportunities reachable within a "
                "travel-time budget."
            ),

            (
                "Travel times are modeled from the road network "
                "and spatial traffic calibration rather than "
                "directly observed GPS trajectories."
            ),

            (
                "The traffic calibration uses hotspot-level "
                "traffic observations and therefore represents "
                "a spatial estimate rather than complete "
                "road-segment telemetry."
            ),

            (
                "Employment coordinates are highly concentrated, "
                "so employment accessibility represents "
                "job-posting opportunity intensity rather than "
                "a complete distribution of workplaces."
            ),

            (
                "The intervention experiment is counterfactual "
                "and does not represent a prediction of a real "
                "infrastructure project or a globally optimal "
                "network intervention."
            ),
        ],
    }

    findings_path = (
        OUTPUT_DIR
        / "headline_research_findings.json"
    )

    with findings_path.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            findings,
            f,
            indent=2,
        )

    print(
        f"  Wrote: "
        f"{findings_path.relative_to(ROOT)}"
    )

    # ==================================================================
    # FINAL SUMMARY
    # ==================================================================

    print("\n" + "=" * 80)
    print("RESEARCH FINDINGS COMPLETE")
    print("=" * 80)

    print("\nHeadline numbers:")

    if education is not None:
        print(
            "  Education, 30 min, midday: "
            f"{education['mean_accessibility_pct']:.2f}%"
        )

    if health is not None:
        print(
            "  Health, 30 min, midday: "
            f"{health['mean_accessibility_pct']:.2f}%"
        )

    if employment is not None:
        print(
            "  Employment, 30 min, midday: "
            f"{employment['mean_accessibility_pct']:.2f}%"
        )

    print(
        "  Life access, 30 min, midday mean: "
        f"{combined_mean:.2f}%"
    )

    print(
        "  Life access, 30 min, midday median: "
        f"{combined_median:.2f}%"
    )

    print(
        "  Life access P10: "
        f"{combined_p10:.2f}%"
    )

    print(
        "  Life access P90: "
        f"{combined_p90:.2f}%"
    )

    print(
        "  Mean peak-hour loss: "
        f"{peak_loss_mean:.2f} pp"
    )

    print(
        "  P90 peak-hour loss: "
        f"{peak_loss_p90:.2f} pp"
    )

    print(
        "  Maximum peak-hour loss: "
        f"{peak_loss_max:.2f} pp"
    )

    print(
        "  Winning intervention origin: "
        f"{int(winner['origin_id'])}"
    )

    print(
        "  Winning intervention gain: "
        f"{winner['total_access_gain_pct_points']:.2f} pp"
    )

    print(
        "  Disadvantaged gain: "
        f"{winner['disadvantaged_total_gain']:.2f} pp"
    )

    print(
        "  Affected origins: "
        f"{int(winner['origins_affected'])}"
    )

    print("\nOutputs:")
    print(
        "  data\\processed\\research_findings\\"
    )

    print(
        "    category_accessibility_findings.csv"
    )

    print(
        "    travel_time_budget_growth.csv"
    )

    print(
        "    peak_hour_accessibility_loss.csv"
    )

    print(
        "    lowest_accessibility_origins.csv"
    )

    print(
        "    temporally_fragile_origins.csv"
    )

    print(
        "    headline_research_findings.json"
    )


if __name__ == "__main__":
    main()