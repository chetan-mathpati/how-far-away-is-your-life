from pathlib import Path

import osmnx as ox
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def extract_features(tags: dict, category: str) -> pd.DataFrame:
    print(f"\nDownloading {category}...")

    gdf = ox.features_from_place(
        "Bengaluru, Karnataka, India",
        tags=tags,
    )

    print(f"Raw features: {len(gdf):,}")

    # Keep only point-like facilities for clean network attachment.
    gdf = gdf[gdf.geometry.notna()].copy()

    # Convert polygons/buildings to representative points.
    gdf["geometry"] = gdf.geometry.representative_point()

    gdf = gdf.to_crs("EPSG:4326")

    gdf["latitude"] = gdf.geometry.y
    gdf["longitude"] = gdf.geometry.x

    name = (
        gdf.get("name", pd.Series(index=gdf.index, dtype="object"))
        .fillna("Unnamed")
        .astype(str)
    )

    result = pd.DataFrame(
        {
            "id": [f"{category}_{i:06d}" for i in range(len(gdf))],
            "name": name.values,
            "category": category,
            "latitude": gdf["latitude"].values,
            "longitude": gdf["longitude"].values,
        }
    )

    # Remove impossible coordinates.
    result = result[
        result["latitude"].between(12.7, 13.3)
        & result["longitude"].between(77.2, 77.9)
    ]

    result = result.drop_duplicates(
        subset=["name", "latitude", "longitude"]
    ).reset_index(drop=True)

    output = OUTPUT_DIR / f"bengaluru_{category}.csv"
    result.to_csv(output, index=False)

    print(f"Clean facilities: {len(result):,}")
    print(f"Saved: {output}")

    return result


def main() -> None:
    hospitals = extract_features(
        {
            "amenity": [
                "hospital",
                "clinic",
                "doctors",
            ]
        },
        "health",
    )

    education = extract_features(
        {
            "amenity": [
                "school",
                "college",
                "university",
            ]
        },
        "education",
    )

    print("\nOpportunity acquisition complete.")
    print(f"Health:     {len(hospitals):,}")
    print(f"Education:  {len(education):,}")


if __name__ == "__main__":
    main()