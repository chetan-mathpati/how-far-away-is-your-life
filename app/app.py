from __future__ import annotations

import json
from pathlib import Path

import folium
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from streamlit.components.v1 import html
from streamlit_folium import st_folium


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"

SURFACE = DATA / "accessibility_surface" / "bengaluru_accessibility_surface.csv"
CURVES = DATA / "accessibility_curves" / "origin_accessibility_curve_features.csv"
FINDINGS = DATA / "research_findings" / "headline_research_findings.json"
LOW_ACCESS = DATA / "research_findings" / "lowest_accessibility_origins.csv"
FRAGILE = DATA / "research_findings" / "temporally_fragile_origins.csv"
WINNER_CORRIDOR = DATA / "interventions" / "geometries" / "winning_corridor.geojson"
AFFECTED = DATA / "interventions" / "geometries" / "winning_affected_origins.geojson"


st.set_page_config(
    page_title="How Far Away Is Your Life?",
    page_icon="◌",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ================================================================
# SOFT EDITORIAL DESIGN
# ================================================================

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=Space+Grotesk:wght@400;500;600&display=swap');

:root {
    --paper: #f4f3ee;
    --paper-2: #ebeae4;
    --ink: #1d1e1a;
    --ink-soft: #45473f;
    --muted: #77796f;
    --faint: #a6a79e;
    --line: #d9d8d0;
    --sage: #7e8e58;
    --sage-dark: #647341;
    --sage-pale: #dfe5ce;
    --white: #fbfaf6;
}

html, body, [class*="css"] {
    font-family: "DM Sans", sans-serif;
}

.stApp {
    background: var(--paper);
    color: var(--ink);
}

.block-container {
    max-width: 1380px;
    padding: 0 4.5rem 5rem;
}

header[data-testid="stHeader"] {
    background: transparent;
}

[data-testid="stToolbar"],
#MainMenu,
footer {
    display: none !important;
}

section[data-testid="stSidebar"] {
    display: none;
}

h1, h2, h3, h4 {
    font-family: "Space Grotesk", sans-serif !important;
    color: var(--ink) !important;
    font-weight: 400 !important;
}

p, label, span, div {
    color: inherit;
}

.hero {
    min-height: 720px;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    padding: 5rem 0 4rem;
    border-bottom: 1px solid var(--line);
}

.eyebrow {
    font-size: 11px;
    letter-spacing: .16em;
    text-transform: uppercase;
    color: var(--sage-dark);
    font-weight: 600;
    margin-bottom: 1.6rem;
}

.hero-title {
    font-family: "Space Grotesk", sans-serif;
    font-size: clamp(4.8rem, 9vw, 9.8rem);
    line-height: .84;
    letter-spacing: -.075em;
    font-weight: 400;
    max-width: 1050px;
    margin: 0;
}

.hero-title em {
    font-style: normal;
    color: var(--sage-dark);
}

.hero-subtitle {
    color: var(--ink-soft);
    font-size: 1.08rem;
    line-height: 1.65;
    max-width: 610px;
    margin-top: 2.5rem;
}

.hero-meta {
    margin-top: 4.5rem;
    color: var(--muted);
    font-size: 12px;
    letter-spacing: .02em;
}

.section {
    padding: 8rem 0 2rem;
}

.section-head {
    display: grid;
    grid-template-columns: 110px 1fr;
    gap: 2rem;
    margin-bottom: 3rem;
}

.section-index {
    color: var(--sage-dark);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: .14em;
    text-transform: uppercase;
    padding-top: .55rem;
}

.section-title {
    font-family: "Space Grotesk", sans-serif;
    font-size: clamp(2.5rem, 5vw, 5.3rem);
    line-height: .96;
    letter-spacing: -.06em;
    margin: 0 0 1.2rem;
}

.section-copy {
    color: var(--muted);
    max-width: 650px;
    font-size: 1rem;
    line-height: 1.7;
}

.stat-strip {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    border-top: 1px solid var(--line);
    border-bottom: 1px solid var(--line);
    margin-top: 4rem;
}

.stat {
    padding: 1.5rem 1.2rem 1.7rem 0;
}

.stat + .stat {
    border-left: 1px solid var(--line);
    padding-left: 1.5rem;
}

.stat-value {
    font-family: "Space Grotesk", sans-serif;
    font-size: clamp(2.1rem, 4vw, 3.7rem);
    letter-spacing: -.06em;
    line-height: 1;
}

.stat-label {
    color: var(--muted);
    font-size: 11px;
    line-height: 1.45;
    margin-top: .65rem;
}

.soft-panel {
    background: var(--white);
    border: 1px solid var(--line);
    padding: 1.4rem;
}

.map-shell {
    background: #e8e8e1;
    border: 1px solid var(--line);
    overflow: hidden;
}

.map-caption {
    display: flex;
    justify-content: space-between;
    padding: 12px 14px;
    color: var(--muted);
    font-size: 11px;
    border-top: 1px solid var(--line);
    background: var(--white);
}

.statement {
    font-family: "Space Grotesk", sans-serif;
    font-size: clamp(2.4rem, 5vw, 5.4rem);
    line-height: .98;
    letter-spacing: -.065em;
    max-width: 1050px;
    margin: 4rem 0 5rem;
}

.statement em {
    color: var(--sage-dark);
    font-style: normal;
}

.control-title {
    color: var(--muted);
    font-size: 10px;
    font-weight: 600;
    letter-spacing: .13em;
    text-transform: uppercase;
    margin-bottom: .4rem;
}


/* Native Streamlit controls: quiet, light, and legible */
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div {
    background: #fbfaf6 !important;
    border: 1px solid #d9d8d0 !important;
    color: #1d1e1a !important;
    box-shadow: none !important;
}
div[data-testid="stSelectbox"] div[data-baseweb="select"] span,
div[data-testid="stSelectbox"] div[data-baseweb="select"] input {
    color: #1d1e1a !important;
}
div[data-testid="stSelectbox"] label,
div[data-testid="stSlider"] label {
    color: #77796f !important;
}

div[data-baseweb="select"] > div {
    background: var(--white) !important;
    border: 1px solid var(--line) !important;
    border-radius: 2px !important;
    color: var(--ink) !important;
}

div[data-baseweb="select"] input,
div[data-baseweb="select"] span {
    color: var(--ink) !important;
}

div[data-testid="stSlider"] {
    padding-top: 0;
}

[data-testid="stSlider"] [data-baseweb="slider"] {
    padding-top: 8px;
}

[data-testid="stSlider"] [role="slider"] {
    background: var(--sage-dark) !important;
    border-color: var(--sage-dark) !important;
}

[data-testid="stSlider"] [data-testid="stTickBar"] {
    background: var(--line) !important;
}

[data-testid="stMarkdownContainer"] a {
    color: var(--sage-dark);
}

.chart-frame {
    background: var(--white);
    border: 1px solid var(--line);
    padding: .5rem .5rem .1rem;
}

.quote {
    border-left: 2px solid var(--sage-dark);
    padding-left: 1.2rem;
    color: var(--ink-soft);
    font-size: 1.05rem;
    line-height: 1.65;
    margin: 2rem 0;
}

.method-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    border-top: 1px solid var(--line);
    margin-top: 3rem;
}

.method-item {
    padding: 1.5rem 1.5rem 1.5rem 0;
}

.method-item + .method-item {
    border-left: 1px solid var(--line);
    padding-left: 1.5rem;
}

.method-number {
    font-family: "Space Grotesk", sans-serif;
    font-size: 1.8rem;
}

.method-label {
    color: var(--muted);
    font-size: 11px;
    line-height: 1.5;
    margin-top: .4rem;
}

.note {
    color: var(--muted);
    font-size: 11px;
    line-height: 1.65;
}

.footer {
    border-top: 1px solid var(--line);
    margin-top: 8rem;
    padding-top: 1.5rem;
    color: var(--muted);
    font-size: 11px;
}

@media (max-width: 900px) {
    .block-container {
        padding: 0 1.3rem 3rem;
    }
    .hero {
        min-height: 600px;
    }
    .section-head {
        grid-template-columns: 1fr;
        gap: .4rem;
    }
    .stat-strip {
        grid-template-columns: repeat(2, 1fr);
    }
    .stat:nth-child(3) {
        border-left: 0;
        padding-left: 0;
    }
    .method-grid {
        grid-template-columns: repeat(2, 1fr);
    }
}

/* =========================================================
   V4 — SOFT SPATIAL INTELLIGENCE
   ========================================================= */
.block-container {
    max-width: 1480px;
    padding: 0 3.8rem 6rem;
}

.hero {
    min-height: 820px;
    padding: 5rem 0 3.5rem;
    position: relative;
}

.hero-title {
    font-size: clamp(5rem, 9.5vw, 11rem);
    max-width: 1250px;
    letter-spacing: -.085em;
    line-height: .79;
}

.hero-subtitle {
    max-width: 590px;
    margin-top: 3rem;
}

.hero-meta {
    margin-top: 4rem;
}

.section {
    padding: 9rem 0 1rem;
}

.section-head {
    grid-template-columns: 90px 1fr;
}

.section-title {
    max-width: 950px;
}

.stat-strip {
    display: none;
}

.finding-band {
    display: grid;
    grid-template-columns: 1.25fr .75fr;
    gap: 3rem;
    border-bottom: 1px solid var(--line);
    padding: 2.5rem 0 2.7rem;
}

.finding-kicker {
    display: block;
    color: var(--sage-dark);
    font-size: 10px;
    letter-spacing: .16em;
    font-weight: 600;
    margin-bottom: .8rem;
}

.finding-lead strong {
    display: inline-block;
    font-family: "Space Grotesk";
    font-size: clamp(3.4rem, 6vw, 6.3rem);
    font-weight: 400;
    letter-spacing: -.075em;
    line-height: .9;
    margin-right: 1rem;
}

.finding-lead > span:last-child {
    display: inline-block;
    max-width: 310px;
    color: var(--muted);
    font-size: 13px;
    line-height: 1.55;
}

.finding-detail {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    align-items: end;
}

.finding-detail div {
    padding-left: 1.15rem;
    border-left: 1px solid var(--line);
}

.finding-detail b {
    display: block;
    font-family: "Space Grotesk";
    font-size: 1.55rem;
    font-weight: 400;
    letter-spacing: -.04em;
}

.finding-detail span {
    display: block;
    color: var(--muted);
    font-size: 10px;
    line-height: 1.45;
    margin-top: .3rem;
}

.map-insight {
    background: var(--white);
    border-left: 1px solid var(--line);
    padding: 2.8rem 2.4rem;
    min-height: 560px;
}

.map-insight-number {
    font-family: "Space Grotesk";
    font-size: clamp(4rem, 7vw, 7rem);
    letter-spacing: -.08em;
    line-height: .9;
}

.soft-panel,
.chart-frame {
    background: var(--white);
    border: 1px solid var(--line);
    box-shadow: 0 16px 50px rgba(44,45,39,.035);
}

.quote {
    border-left: 1px solid var(--sage-dark);
}

div[data-baseweb="select"] > div {
    background: var(--white) !important;
    border: 1px solid #c9c8bf !important;
    border-radius: 1px !important;
    box-shadow: none !important;
}

div[data-baseweb="select"] span,
div[data-baseweb="select"] input {
    color: var(--ink) !important;
}

@media (max-width: 900px) {
    .finding-band {
        grid-template-columns: 1fr;
    }
    .finding-detail {
        margin-top: 1.5rem;
    }
}


.place-caption {
    font-family: "Space Grotesk", sans-serif;
    color: var(--ink);
    font-size: 1.05rem;
    letter-spacing: -.02em;
}


.map-insight {
    display:flex;
    flex-direction:column;
    justify-content:center;
}
.map-insight-number {
    margin-top:.25rem;
}
.map-caption {
    letter-spacing:.02em;
}


.map-shell iframe {
    filter: saturate(.92) contrast(1.02);
}

.map-caption span:last-child { color: #898b81; }

/* FINAL PASS — controls and explanatory typography */
[data-testid="stSlider"] [data-testid="stMarkdownContainer"] {
    font-size: 11px;
}
.map-caption {
    font-size: 10px;
    letter-spacing: .04em;
    text-transform: uppercase;
}
.finding-detail span {
    max-width: 170px;
}


/* v11: research-film controls */
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    background:#fbfaf6 !important;
    color:#1d1e1a !important;
    border:1px solid #cfcfc6 !important;
    border-radius:2px !important;
}
div[data-testid="stSelectbox"] div[data-baseweb="select"] span {
    color:#1d1e1a !important;
}

</style>
""",
    unsafe_allow_html=True,
)


# ================================================================
# DATA
# ================================================================

@st.cache_data
def load_data():
    surface = pd.read_csv(SURFACE)
    curves = pd.read_csv(CURVES)

    with open(FINDINGS, "r", encoding="utf-8") as f:
        findings = json.load(f)

    low_access = pd.read_csv(LOW_ACCESS)
    fragile = pd.read_csv(FRAGILE)

    with open(WINNER_CORRIDOR, "r", encoding="utf-8") as f:
        winner_geo = json.load(f)

    with open(AFFECTED, "r", encoding="utf-8") as f:
        affected_geo = json.load(f)

    return surface, curves, findings, low_access, fragile, winner_geo, affected_geo


surface, curves, findings, low_access, fragile, winner_geo, affected_geo = load_data()


# ================================================================
# HELPERS
# ================================================================

ORIGINS = (
    surface[["origin_id", "latitude", "longitude"]]
    .drop_duplicates()
    .sort_values("origin_id")
)

# Keep analytical origin IDs internal. The UI uses human-readable place names.
ORIGIN_LABELS = {
    int(r.origin_id): f"Sampled place · {r.latitude:.3f}°, {r.longitude:.3f}°"
    for r in ORIGINS.itertuples()
}

CATEGORY_LABELS = {
    "life": "Health + education",
    "health": "Health",
    "education": "Education",
    "employment": "Employment",
}

CATEGORY_COLORS = {
    "health": "#75854f",
    "education": "#9a8b67",
    "employment": "#6f827e",
}


@st.cache_data(ttl=60 * 60 * 24 * 30, show_spinner=False)
def reverse_geocode(latitude: float, longitude: float) -> dict:
    """
    Resolve only the selected analytical origin to a human-readable place.
    Nominatim is queried on demand; we do not geocode all 649 origins.
    """
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={
                "lat": latitude,
                "lon": longitude,
                "format": "jsonv2",
                "zoom": 18,
                "addressdetails": 1,
            },
            headers={"User-Agent": "How-Far-Away-Is-Your-Life/1.0"},
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
        address = payload.get("address", {})

        locality = (
            address.get("suburb")
            or address.get("neighbourhood")
            or address.get("quarter")
            or address.get("village")
            or address.get("town")
            or address.get("city_district")
            or address.get("city")
            or "Bengaluru"
        )
        city = (
            address.get("city")
            or address.get("municipality")
            or address.get("town")
            or "Bengaluru"
        )
        state = address.get("state") or "Karnataka"

        return {
            "name": locality,
            "city": city,
            "state": state,
            "display_name": payload.get("display_name", ""),
        }
    except Exception:
        return {
            "name": "Selected place",
            "city": "Bengaluru",
            "state": "Karnataka",
            "display_name": "",
        }


def place_label(origin_id: int) -> dict:
    row = ORIGINS[ORIGINS.origin_id.astype(int) == int(origin_id)]
    if row.empty:
        return {"name": "Selected place", "city": "Bengaluru", "state": "Karnataka"}

    r = row.iloc[0]
    return reverse_geocode(float(r.latitude), float(r.longitude))


def place_short_name(origin_id: int) -> str:
    info = place_label(origin_id)
    return str(info["name"])


def pct(value):
    return f"{float(value):.1f}%"


def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def accessibility_curve(origin_id: int, category: str, hour: int):
    """The curve feature file is intentionally wide: access_15/30/45/60min_pct."""
    frame = curves[
        (curves["origin_id"].astype(int) == int(origin_id))
        & (curves["category"].str.lower() == category.lower())
        & (curves["hour"].astype(int) == int(hour))
    ].copy()

    if frame.empty:
        # Fall back to the closest available hour for the selected origin/category.
        candidate = curves[
            (curves["origin_id"].astype(int) == int(origin_id))
            & (curves["category"].str.lower() == category.lower())
        ].copy()
        if candidate.empty:
            return pd.DataFrame(columns=["threshold_minutes", "accessibility_pct"])
        candidate["hour_distance"] = (candidate["hour"].astype(int) - int(hour)).abs()
        frame = candidate.sort_values("hour_distance").head(1)

    row = frame.iloc[0]
    rows = []
    for minutes in (15, 30, 45, 60):
        column = f"access_{minutes}min_pct"
        if column in frame.columns:
            rows.append(
                {
                    "threshold_minutes": minutes,
                    "accessibility_pct": safe_float(row[column]),
                }
            )
    return pd.DataFrame(rows)


def accessibility_map_frame(category: str, budget: int, hour: int = 13):
    """Build the accessibility field for a selected time scenario and budget."""
    column = f"access_{int(budget)}min_pct"

    base = curves[
        (curves["hour"].astype(int) == int(hour))
        & (curves["category"].str.lower().isin(["health", "education", "employment"]))
    ].copy()

    if column not in base.columns:
        raise KeyError(f"Missing curve column: {column}")

    if category == "life":
        h = base[base["category"].str.lower() == "health"][
            ["origin_id", "latitude", "longitude", column]
        ].rename(columns={column: "health_access"})
        e = base[base["category"].str.lower() == "education"][
            ["origin_id", "latitude", "longitude", column]
        ].rename(columns={column: "education_access"})

        frame = h.merge(e, on=["origin_id", "latitude", "longitude"], how="inner")
        frame["accessibility_pct"] = (
            frame["health_access"] + frame["education_access"]
        ) / 2.0

        if int(hour) == 13 and int(budget) == 30:
            canonical = surface[
                ["origin_id", "life_access_30min_midday_pct"]
            ].copy()
            frame = frame.drop(columns=["accessibility_pct"]).merge(
                canonical, on="origin_id", how="left"
            )
            frame["accessibility_pct"] = frame["life_access_30min_midday_pct"]
    else:
        frame = base[
            base["category"].str.lower() == category.lower()
        ][["origin_id", "latitude", "longitude", column]].copy()
        frame["accessibility_pct"] = frame[column]

    return frame[[
        "origin_id", "latitude", "longitude", "accessibility_pct"
    ]].copy()



def selected_accessibility(origin_id: int, category: str, budget: int, hour: int = 13) -> float:
    frame = accessibility_map_frame(category, budget, hour)
    row = frame[frame["origin_id"].astype(int) == int(origin_id)]
    if row.empty:
        return float("nan")
    return safe_float(row.iloc[0]["accessibility_pct"], float("nan"))



def add_realistic_basemap(m):
    """Esri World Street Map: public street/label tiles, no Carto API key."""
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
        attr="Esri, HERE, Garmin, © OpenStreetMap contributors",
        name="Street map",
        overlay=False,
        control=True,
        max_zoom=19,
    ).add_to(m)
    return m

def make_access_map(origin_id: int, category: str, budget: int, hour: int):
    """
    Map-first renderer.

    The basemap remains visually dominant. Accessibility is communicated
    through a restrained sampled surface rather than a blurred heatmap,
    so street names and neighbourhood geometry remain readable.
    """
    frame = accessibility_map_frame(category, budget, hour)
    center = ORIGINS[ORIGINS.origin_id.astype(int) == int(origin_id)].iloc[0]

    m = folium.Map(
        location=[float(center.latitude), float(center.longitude)],
        zoom_start=11,
        tiles=None,
        control_scale=False,
        zoom_control=True,
        dragging=True,
        scrollWheelZoom=True,
        doubleClickZoom=True,
    )

    # Clean, highly legible public street basemap.
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
        attr="Esri, HERE, Garmin, © OpenStreetMap contributors",
        name="Street map",
        overlay=False,
        control=False,
        max_zoom=19,
    ).add_to(m)

    # Extremely restrained accessibility anchors.
    # No blur: the city remains readable.
    values = pd.to_numeric(frame["accessibility_pct"], errors="coerce").fillna(0).clip(0, 100)

    for row, value in zip(frame.itertuples(), values):
        v = float(value)

        if v >= 85:
            fill = "#71804f"
        elif v >= 70:
            fill = "#8d9970"
        elif v >= 50:
            fill = "#aeb69a"
        elif v >= 30:
            fill = "#c9cdbd"
        else:
            fill = "#dedfd5"

        folium.CircleMarker(
            location=[float(row.latitude), float(row.longitude)],
            radius=2.2,
            color=fill,
            weight=0,
            fill=True,
            fill_color=fill,
            fill_opacity=0.22,
        ).add_to(m)

    place_name = place_short_name(origin_id)

    # Exact selected location.
    folium.CircleMarker(
        location=[float(center.latitude), float(center.longitude)],
        radius=7,
        color="#1d1e1a",
        weight=2,
        fill=True,
        fill_color="#ffffff",
        fill_opacity=1,
        tooltip=place_name,
    ).add_to(m)

    # A visual target ring — deliberately not a geographic radius.
    folium.CircleMarker(
        location=[float(center.latitude), float(center.longitude)],
        radius=15,
        color="#68764b",
        weight=1,
        opacity=0.65,
        fill=False,
    ).add_to(m)

    # Human-readable locality label.
    folium.Marker(
        location=[float(center.latitude), float(center.longitude)],
        icon=folium.DivIcon(
            html=f"""
            <div style="
                transform: translate(13px,-15px);
                white-space:nowrap;
                font-family:DM Sans,Arial,sans-serif;
                font-size:12px;
                font-weight:600;
                letter-spacing:.01em;
                color:#20211c;
                background:rgba(250,249,244,.96);
                border:1px solid rgba(40,41,36,.22);
                padding:6px 9px;
                box-shadow:0 4px 14px rgba(30,31,27,.10);
            ">
                {place_name}
            </div>
            """
        ),
    ).add_to(m)

    # Small explanatory legend; deliberately subordinate to the map.
    legend = """
    <div style="
        position:fixed;
        bottom:18px;
        left:18px;
        z-index:9999;
        background:rgba(250,249,244,.94);
        border:1px solid rgba(40,41,36,.18);
        padding:9px 11px;
        font-family:DM Sans,Arial,sans-serif;
        color:#45473f;
        font-size:9px;
        box-shadow:0 4px 14px rgba(30,31,27,.07);
    ">
        <div style="font-weight:600;letter-spacing:.08em;margin-bottom:5px;">
            REACHABLE OPPORTUNITY
        </div>
        <div style="
            width:105px;height:5px;
            background:linear-gradient(90deg,#dedfd5,#c9cdbd,#aeb69a,#8d9970,#71804f);
        "></div>
        <div style="display:flex;justify-content:space-between;width:105px;margin-top:3px;">
            <span>LOW</span><span>HIGH</span>
        </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend))

    return m


def make_intervention_map():
    center = [12.9716, 77.5946]
    m = folium.Map(
        location=center,
        zoom_start=10.7,
        tiles=None,
        control_scale=False,
        zoom_control=False,
        scrollWheelZoom=False,
    )

    add_realistic_basemap(m)

    folium.GeoJson(
        winner_geo,
        name="Modeled intervention corridor",
        style_function=lambda _: {
            "color": "#687746",
            "weight": 5,
            "opacity": 0.72,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["path_frequency", "is_winner"],
            aliases=["Path frequency", "Selected corridor"],
            localize=True,
        ),
    ).add_to(m)

    folium.GeoJson(
        affected_geo,
        name="Affected origins",
        marker=folium.CircleMarker(
            radius=4,
            color="#8f927f",
            fill=True,
            fill_color="#8f927f",
            fill_opacity=0.42,
            weight=1,
        ),
    ).add_to(m)

    return m


def plot_curve(origin_id: int, category: str, hour: int):
    curve = accessibility_curve(origin_id, category, hour)
    fig = go.Figure()

    if curve.empty:
        fig.add_annotation(
            text="No curve is available for this origin.",
            x=.5, y=.5, xref="paper", yref="paper",
            showarrow=False,
            font=dict(size=15, color="#77796f"),
        )
    else:
        fig.add_trace(
            go.Scatter(
                x=curve["threshold_minutes"],
                y=curve["accessibility_pct"],
                mode="lines+markers",
                line=dict(color=CATEGORY_COLORS.get(category, "#7e8e58"), width=3),
                marker=dict(size=9, color="#fbfaf6", line=dict(
                    color=CATEGORY_COLORS.get(category, "#7e8e58"), width=2
                )),
                hovertemplate="%{x} minutes · %{y:.1f}%<extra></extra>",
            )
        )

    fig.update_layout(
        height=390,
        margin=dict(l=10, r=25, t=20, b=35),
        paper_bgcolor="#fbfaf6",
        plot_bgcolor="#fbfaf6",
        font=dict(family="DM Sans", color="#45473f"),
        xaxis=dict(
            title="Travel time budget (minutes)",
            tickvals=[15, 30, 45, 60],
            gridcolor="#e3e2dc",
            zeroline=False,
            linecolor="#d9d8d0",
        ),
        yaxis=dict(
            title="Reachable opportunity (%)",
            ticksuffix="%",
            range=[0, 105],
            gridcolor="#e3e2dc",
            zeroline=False,
            linecolor="#d9d8d0",
        ),
        hoverlabel=dict(bgcolor="#1d1e1a", font_color="#fbfaf6"),
    )
    return fig


def life_value_for_origin(origin_id: int, peak=False):
    col = "life_access_30min_peak_pct" if peak else "life_access_30min_midday_pct"
    row = surface[surface.origin_id.astype(int) == int(origin_id)]
    if row.empty:
        return np.nan
    return safe_float(row.iloc[0][col], np.nan)


# ================================================================
# HERO
# ================================================================

st.markdown(
    """
<div class="hero">
    <div class="eyebrow">BENGALURU / ACCESSIBILITY STUDY / 2026</div>
    <div class="hero-title">HOW FAR AWAY<br><em>IS YOUR LIFE?</em></div>
    <div class="hero-subtitle">
        A different way to read a city: not by distance, but by the opportunities
        you can reach before your time runs out.
    </div>
    <div class="hero-meta">
        649 sampled origins &nbsp;·&nbsp; 155k road-network nodes &nbsp;·&nbsp;
        5 network scenarios
    </div>
</div>
""",
    unsafe_allow_html=True,
)

headline = findings.get("headline", findings)

life_mean = safe_float(headline.get("life_access_mean_30min_midday_pct", 77.98))
life_p10 = safe_float(headline.get("life_access_p10_30min_midday_pct", 57.77))
life_p90 = safe_float(headline.get("life_access_p90_30min_midday_pct", 96.96))
peak_loss = safe_float(headline.get("mean_peak_hour_loss_pp", 3.56))

st.markdown(
    f"""
<div class="finding-band">
    <div class="finding-lead">
        <span class="finding-kicker">THE CITY AT 30 MINUTES</span>
        <strong>{life_mean:.1f}%</strong>
        <span>of mapped health + education opportunity is reachable from the average sampled origin.</span>
    </div>
    <div class="finding-detail">
        <div><b>{life_p10:.1f}%</b><span>10th percentile<br>1 in 10 sampled places is at or below this</span></div>
        <div><b>{life_p90:.1f}%</b><span>90th percentile<br>9 in 10 sampled places are at or below this</span></div>
        <div><b>{peak_loss:.1f} points</b><span>average accessibility change<br>from 1 PM to 6 PM</span></div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)


# ================================================================
# 01 — EXPLORE
# ================================================================

st.markdown('<div class="section">', unsafe_allow_html=True)
st.markdown(
    """
<div class="section-head">
    <div class="section-index">01 / Explore</div>
    <div>
        <div class="section-title">What can you reach?</div>
        <div class="section-copy">
            Pick a place, a travel budget, and a time of day. The map shows the share
            of Bengaluru's mapped opportunity landscape reachable under that scenario.
        </div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

c1, c2, c3, c4 = st.columns([1.25, 0.9, 0.9, 1.0])

with c1:
    st.markdown('<div class="control-title">Starting place</div>', unsafe_allow_html=True)
    origin_ids = list(ORIGIN_LABELS.keys())
    if "explore_origin_id" not in st.session_state:
        st.session_state.explore_origin_id = origin_ids[0]

    current_origin = int(st.session_state.explore_origin_id)
    current_index = origin_ids.index(current_origin) if current_origin in origin_ids else 0

    selected_label = st.selectbox(
        "Starting place",
        list(ORIGIN_LABELS.values()),
        index=current_index,
        label_visibility="collapsed",
    )
    selected_origin = next(k for k, v in ORIGIN_LABELS.items() if v == selected_label)
    st.session_state.explore_origin_id = selected_origin
    selected_place = place_label(selected_origin)

with c2:
    st.markdown('<div class="control-title">Travel time</div>', unsafe_allow_html=True)
    budget = st.select_slider(
        "Travel time",
        options=[15, 30, 45, 60],
        value=30,
        format_func=lambda x: f"{x} min",
        label_visibility="collapsed",
    )

with c3:
    st.markdown('<div class="control-title">Time of day</div>', unsafe_allow_html=True)
    hour = st.select_slider(
        "Time of day",
        options=[7, 9, 13, 18, 22],
        value=13,
        format_func=lambda x: f"{x:02d}:00",
        label_visibility="collapsed",
    )

with c4:
    st.markdown('<div class="control-title">Life dimension</div>', unsafe_allow_html=True)
    dimension = st.selectbox(
        "Life dimension",
        ["life", "health", "education", "employment"],
        format_func=lambda x: CATEGORY_LABELS[x],
        index=0,
        label_visibility="collapsed",
    )

st.markdown(
    f"""
    <div style="margin:.35rem 0 1rem;color:#77796f;font-size:11px;">
        Reading <strong>{selected_place["name"]}</strong> at
        <strong>{budget} minutes</strong> · <strong>{hour:02d}:00</strong> ·
        <strong>{CATEGORY_LABELS[dimension]}</strong>
    </div>
    """,
    unsafe_allow_html=True,
)

map_col, copy_col = st.columns([2.55, 0.85], gap="large")

with map_col:
    access_map = make_access_map(selected_origin, dimension, budget, hour)
    map_state = st_folium(
        access_map,
        height=560,
        width=None,
        returned_objects=["last_clicked"],
        key="explore_accessibility_map",
    )

    # Clicking anywhere on the map selects the nearest sampled origin.
    # Panning and zooming remain normal Leaflet interactions.
    clicked = map_state.get("last_clicked") if map_state else None
    if clicked and clicked.get("lat") is not None and clicked.get("lng") is not None:
        click_lat = float(clicked["lat"])
        click_lon = float(clicked["lng"])
        distances = (
            (ORIGINS["latitude"].astype(float) - click_lat) ** 2
            + (ORIGINS["longitude"].astype(float) - click_lon) ** 2
        )
        nearest_idx = distances.idxmin()
        nearest_origin = int(ORIGINS.loc[nearest_idx, "origin_id"])
        if nearest_origin != int(selected_origin):
            st.session_state.explore_origin_id = nearest_origin
            st.rerun()

    st.markdown(
        f"""
        <div class="map-caption">
            <span>{CATEGORY_LABELS[dimension].upper()} · {budget}-MINUTE ACCESSIBILITY</span>
            <span>{hour:02d}:00 NETWORK SCENARIO · 649 SAMPLED PLACES</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

with copy_col:
    selected_row = surface[surface.origin_id.astype(int) == int(selected_origin)].iloc[0]
    selected_value = selected_accessibility(selected_origin, dimension, budget, hour)

    st.markdown(
        f"""
        <div class="map-insight">
            <div class="control-title">STARTING PLACE</div>
            <div style="font-family:'Space Grotesk';font-size:2.1rem;letter-spacing:-.055em;margin-bottom:1.2rem;">{selected_place["name"]}</div>
            <div class="note" style="margin-bottom:1.4rem;">{selected_place["city"]} · {selected_place["state"]}<br>{float(selected_row["latitude"]):.5f}°, {float(selected_row["longitude"]):.5f}°</div>
            <div class="map-insight-number">{selected_value:.1f}%</div>
            <div class="note" style="margin-top:1rem;">
                of mapped {CATEGORY_LABELS[dimension].lower()} opportunity
                is reachable within a {budget}-minute modeled road journey.
            </div>
            <div class="quote" style="margin-top:3rem;">
                The map stays geographically honest.<br><br>
                The small points show the sampled accessibility surface for this travel budget and time of day. The ring marks the selected place; it is not a travel-time boundary.
            </div>
            <div class="note" style="margin-top:2rem;">
                Darker points indicate a larger share of mapped opportunity reachable within the selected time.
                The outlined point is your starting location.
                Scenario: <strong>{hour:02d}:00</strong>. Travel times are calibrated estimates, not live navigation.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

selected_life = selected_accessibility(selected_origin, 'life', budget, hour)
st.markdown(
    f"""
    <div class="statement">
        From <em>{selected_place["name"]}</em>, <em>{selected_life:.1f}%</em> of the mapped
        health + education opportunity is within the <em>{budget}-minute network</em>.
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("</div>", unsafe_allow_html=True)


# ================================================================
# 02 — CURVE
# ================================================================

st.markdown('<div class="section">', unsafe_allow_html=True)
st.markdown(
    """
<div class="section-head">
    <div class="section-index">02 / The curve</div>
    <div>
        <div class="section-title">Time is the currency of accessibility.</div>
        <div class="section-copy">
            There is no single boundary around a place. Every extra minute
            opens another layer of the city's opportunity landscape.
        </div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

curve_c1, curve_c2 = st.columns([1, 1])
with curve_c1:
    st.markdown('<div class="control-title">Opportunity dimension</div>', unsafe_allow_html=True)
    curve_category = st.selectbox(
        "Opportunity dimension",
        ["health", "education", "employment"],
        format_func=lambda x: CATEGORY_LABELS[x],
        key="curve_category",
        label_visibility="collapsed",
    )
with curve_c2:
    st.markdown('<div class="control-title">Network scenario</div>', unsafe_allow_html=True)
    curve_hour = st.selectbox(
        "Network scenario",
        [7, 9, 13, 18, 22],
        index=2,
        format_func=lambda x: f"{x:02d}:00",
        key="curve_hour",
        label_visibility="collapsed",
    )

curve = accessibility_curve(selected_origin, curve_category, curve_hour)
curve_fig = plot_curve(selected_origin, curve_category, curve_hour)

# Highlight the selected 30-minute point.
if not curve.empty:
    curve_fig.add_trace(
        go.Scatter(
            x=[30],
            y=[float(curve.loc[curve.threshold_minutes == 30, "accessibility_pct"].iloc[0])],
            mode="markers",
            marker=dict(size=12, color="#68764b", line=dict(width=3, color="#fbfaf6")),
            name="30 minutes",
            hovertemplate="%{y:.1f}% reachable<extra>30 minutes</extra>",
        )
    )
    curve_fig.update_layout(
        showlegend=False,
        xaxis=dict(
            title="Travel time budget (minutes)",
            tickmode="array",
            tickvals=[15, 30, 45, 60],
        ),
        yaxis=dict(
            title="Share of mapped opportunity reachable",
            ticksuffix="%",
            range=[0, 105],
        ),
    )

st.markdown('<div class="chart-frame">', unsafe_allow_html=True)
st.plotly_chart(curve_fig, use_container_width=True, config={"displayModeBar": False})
st.markdown("</div>", unsafe_allow_html=True)

if not curve.empty:
    at15 = safe_float(curve.loc[curve.threshold_minutes == 15, "accessibility_pct"].iloc[0])
    at30 = safe_float(curve.loc[curve.threshold_minutes == 30, "accessibility_pct"].iloc[0])
    at45 = safe_float(curve.loc[curve.threshold_minutes == 45, "accessibility_pct"].iloc[0])
    at60 = safe_float(curve.loc[curve.threshold_minutes == 60, "accessibility_pct"].iloc[0])

    st.markdown(
        f"""
        <div class="finding-band" style="margin-top:1.2rem;">
            <div class="finding-lead">
                <span class="finding-kicker">FROM {selected_place["name"].upper()} · {curve_hour:02d}:00</span>
                <strong>{at30:.1f}%</strong>
                <span>of mapped {CATEGORY_LABELS[curve_category].lower()} opportunity is reachable within 30 minutes.</span>
            </div>
            <div class="finding-detail">
                <div><b>{at15:.1f}%</b><span>15 minutes</span></div>
                <div><b>{at45:.1f}%</b><span>45 minutes</span></div>
                <div><b>{at60:.1f}%</b><span>60 minutes</span></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("</div>", unsafe_allow_html=True)


# ================================================================
# 03 — TIME
# ================================================================

st.markdown('<div class="section">', unsafe_allow_html=True)
st.markdown(
    """
<div class="section-head">
    <div class="section-index">03 / Time</div>
    <div>
        <div class="section-title">The same city. A different reachable world.</div>
        <div class="section-copy">
            Hold the travel budget at 30 minutes and move the clock.
            Peak-hour friction does not affect every place equally.
        </div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

# Build a city-wide life-access summary directly from the canonical curve data.
life_time_rows = []
for h in [7, 9, 13, 18, 22]:
    hh = curves[
        (curves["hour"].astype(int) == h)
        & (curves["category"].str.lower() == "health")
    ][["origin_id", "access_30min_pct"]].rename(columns={"access_30min_pct": "health"})
    ee = curves[
        (curves["hour"].astype(int) == h)
        & (curves["category"].str.lower() == "education")
    ][["origin_id", "access_30min_pct"]].rename(columns={"access_30min_pct": "education"})
    joined = hh.merge(ee, on="origin_id", how="inner")
    life = ((joined["health"] + joined["education"]) / 2.0).astype(float)
    life_time_rows.append(
        {
            "hour": h,
            "mean": life.mean(),
            "median": life.median(),
            "p10": life.quantile(.10),
            "p90": life.quantile(.90),
        }
    )

time_df = pd.DataFrame(life_time_rows)

fig_time = go.Figure()
fig_time.add_trace(
    go.Scatter(
        x=time_df["hour"],
        y=time_df["mean"],
        mode="lines+markers",
        line=dict(color="#68764b", width=3),
        marker=dict(size=8),
        name="Average",
        hovertemplate="%{x}:00 · %{y:.1f}% average<extra></extra>",
    )
)
fig_time.add_trace(
    go.Scatter(
        x=time_df["hour"],
        y=time_df["p90"],
        mode="lines",
        line=dict(color="#b8b9b0", width=1, dash="dot"),
        name="Higher-access locations",
        hovertemplate="%{x}:00 · %{y:.1f}%<extra>90th percentile</extra>",
    )
)
fig_time.add_trace(
    go.Scatter(
        x=time_df["hour"],
        y=time_df["p10"],
        mode="lines",
        line=dict(color="#b8b9b0", width=1, dash="dot"),
        name="Lower-access locations",
        hovertemplate="%{x}:00 · %{y:.1f}%<extra>10th percentile</extra>",
    )
)
fig_time.update_layout(
    height=420,
    margin=dict(l=10, r=25, t=25, b=45),
    paper_bgcolor="#fbfaf6",
    plot_bgcolor="#fbfaf6",
    font=dict(family="DM Sans", color="#45473f"),
    xaxis=dict(
        title="Network scenario",
        tickmode="array",
        tickvals=[7, 9, 13, 18, 22],
        ticktext=["7 AM", "9 AM", "1 PM", "6 PM", "10 PM"],
        gridcolor="#e3e2dc",
    ),
    yaxis=dict(
        title="Share of mapped health + education reachable",
        ticksuffix="%",
        gridcolor="#e3e2dc",
        range=[0, 105],
    ),
    legend=dict(orientation="h", y=1.08, x=0),
    hoverlabel=dict(bgcolor="#1d1e1a", font_color="#fbfaf6"),
)

st.markdown('<div class="chart-frame">', unsafe_allow_html=True)
st.plotly_chart(fig_time, use_container_width=True, config={"displayModeBar": False})
st.markdown("</div>", unsafe_allow_html=True)

at1 = time_df.loc[time_df.hour == 13, "mean"].iloc[0]
at6 = time_df.loc[time_df.hour == 18, "mean"].iloc[0]
delta = at1 - at6

st.markdown(
    f"""
    <div class="statement">
        At 30 minutes, the modeled city-wide average moves from
        <em>{at1:.1f}% at 1 PM</em> to <em>{at6:.1f}% at 6 PM</em> —
        a change of <em>{delta:.1f} percentage points</em>.
        But the lines also show why the average is not the whole story:
        some places barely move while others lose much more.
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("</div>", unsafe_allow_html=True)


# ================================================================
# 04 — INEQUALITY
# ================================================================

st.markdown('<div class="section">', unsafe_allow_html=True)
st.markdown(
    """
<div class="section-head">
    <div class="section-index">04 / Inequality</div>
    <div>
        <div class="section-title">Averages can hide two very different cities.</div>
        <div class="section-copy">
            We compare the lower and higher ends of the sampled accessibility
            distribution instead of treating the city as one number.
        </div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

gap = life_p90 - life_p10

# Keep this block as one continuous HTML block. Streamlit's Markdown parser
# can treat indented lines after blank lines as code, which breaks the visual.
inequality_html = f"""
<div class="soft-panel" style="padding:2.6rem 2.8rem;">
<div class="control-title">30-MINUTE LIFE ACCESSIBILITY</div>
<div style="font-family:'Space Grotesk';font-size:4.4rem;line-height:1;letter-spacing:-.075em;margin-top:.35rem;">{gap:.1f}<span style="font-size:1.5rem;letter-spacing:-.02em;margin-left:.45rem;">point gap</span></div>
<div class="note" style="max-width:650px;margin-top:.7rem;">The difference between places near the lower-access end and places near the higher-access end of the sampled city.</div>
<div style="margin-top:2.8rem;">
<div style="height:9px;border-radius:99px;background:linear-gradient(90deg,#d8dacd 0%,#aeb69a 55%,#68764b 100%);position:relative;">
<div style="position:absolute;left:{life_p10}%;top:-6px;width:3px;height:21px;border-radius:2px;background:#1d1e1a;"></div>
<div style="position:absolute;left:{life_p90}%;top:-6px;width:3px;height:21px;border-radius:2px;background:#1d1e1a;"></div>
</div>
<div style="display:flex;justify-content:space-between;gap:2rem;margin-top:1.15rem;">
<div><div style="font-family:'Space Grotesk';font-size:2rem;letter-spacing:-.05em;">{life_p10:.1f}%</div><div class="note">lower-access end</div></div>
<div style="text-align:right;"><div style="font-family:'Space Grotesk';font-size:2rem;letter-spacing:-.05em;">{life_p90:.1f}%</div><div class="note">higher-access end</div></div>
</div>
</div>
<div class="quote" style="margin-top:2.4rem;">In plain English: <strong>one in ten sampled places is at or below {life_p10:.1f}% reachable opportunity</strong>. At the other end, nine in ten are at or below {life_p90:.1f}%.</div>
</div>
"""
st.markdown(inequality_html, unsafe_allow_html=True)

lowest = low_access.head(3)
rows = ""
for r in lowest.itertuples():
    p = place_label(int(r.origin_id))
    rows += (
        f"<div style='padding:.8rem 0;border-bottom:1px solid #d9d8d0;'>"
        f"<strong>{p['name']}</strong>"
        f"<span style='float:right;color:#77796f;'>{float(r.life_access_30min_midday_pct):.1f}%</span>"
        f"<div style='font-size:10px;color:#a0a197;margin-top:.2rem;'>"
        f"lower-access sampled place</div></div>"
    )

st.markdown(
    f"""
    <div class="soft-panel" style="margin-top:1.2rem;padding:1.8rem 2.2rem;">
        <div class="control-title">Examples at the lower-access end</div>
        {rows}
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("</div>", unsafe_allow_html=True)


# ================================================================
# 05 — INTERVENTION
# ================================================================

st.markdown('<div class="section">', unsafe_allow_html=True)
st.markdown(
    """
<div class="section-head">
    <div class="section-index">05 / What could change?</div>
    <div>
        <div class="section-title">If time is the constraint, where would a small intervention matter most?</div>
        <div class="section-copy">
            We tested a counterfactual: improve 50 high-leverage physical
            road segments associated with opportunity-access paths from
            the lowest-access candidate origins.
        </div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

winner = headline.get("winning_intervention", {})
winner_gain = safe_float(
    winner.get("total_gain_pp", headline.get("winning_intervention_gain_pp", 24.17))
)
winner_disadvantaged = safe_float(
    winner.get("disadvantaged_gain_pp", headline.get("winning_disadvantaged_gain_pp", 18.56))
)

im = make_intervention_map()
html(im.get_root().render(), height=560)

st.markdown(
    f"""
    <div class="finding-band" style="margin-top:1rem;">
        <div class="finding-lead">
            <span class="finding-kicker">COUNTERFACTUAL RESULT · {place_short_name(394).upper()}</span>
            <strong>+{winner_gain:.1f}</strong>
            <span>percentage points of modeled accessibility gain across the tested network.</span>
        </div>
        <div class="finding-detail">
            <div><b>+{winner_disadvantaged:.1f}</b><span>points among<br>disadvantaged candidates</span></div>
            <div><b>50</b><span>physical road<br>segments</span></div>
            <div><b>20%</b><span>modeled travel-time<br>improvement</span></div>
        </div>
    </div>

    <div class="note" style="margin-top:1.2rem;max-width:850px;">
        This is an experiment, not a prediction of a real infrastructure project.
        The corridor is generated from repeated shortest-path use and tested under
        one scenario: 13:00, 30 minutes, and a 20% reduction in travel time on the
        selected physical segments.
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("</div>", unsafe_allow_html=True)

# ================================================================
# 06 — METHOD
# ================================================================

st.markdown('<div class="section">', unsafe_allow_html=True)
st.markdown(
    """
<div class="section-head">
    <div class="section-index">06 / Method</div>
    <div>
        <div class="section-title">A map on top. A model underneath.</div>
        <div class="section-copy">
            This project treats accessibility as a network property rather
            than a simple geographic radius.
        </div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="method-grid">
    <div class="method-item">
        <div class="method-number">649</div>
        <div class="method-label">sampled origins across Bengaluru</div>
    </div>
    <div class="method-item">
        <div class="method-number">155k</div>
        <div class="method-label">road-network nodes in the modeled graph</div>
    </div>
    <div class="method-item">
        <div class="method-number">5</div>
        <div class="method-label">time-of-day traffic scenarios</div>
    </div>
    <div class="method-item">
        <div class="method-number">3</div>
        <div class="method-label">opportunity dimensions: health, education, employment</div>
    </div>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div style="margin-top:3rem;max-width:760px;">
    <div class="quote">
        The central unit of analysis is not kilometres.
        It is <strong>opportunity reachable per unit of time</strong>.
    </div>
    <div class="note">
        Road travel times are estimated from OpenStreetMap network structure,
        OSM speed data where available, road-class fallback speeds, and a
        spatial traffic calibration built from Bengaluru traffic observations.
        Opportunity locations come from mapped health and education facilities
        and sampled job postings. Employment is therefore interpreted as a
        job-opportunity signal rather than a complete workplace census.
    </div>
</div>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="footer">
    HOW FAR AWAY IS YOUR LIFE? &nbsp;·&nbsp; Bengaluru &nbsp;·&nbsp; Accessibility intelligence
    <br><br>
    Analytical estimates for exploration and research. Not live navigation or infrastructure advice.
</div>
""",
    unsafe_allow_html=True,
)

st.markdown("</div>", unsafe_allow_html=True)
