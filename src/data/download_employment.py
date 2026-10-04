from pathlib import Path
import os
import time

import pandas as pd
import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "data" / "raw"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(PROJECT_ROOT / ".env")

APP_ID = os.getenv("ADZUNA_APP_ID")
APP_KEY = os.getenv("ADZUNA_APP_KEY")

BASE_URL = "https://api.adzuna.com/v1/api/jobs/in/search"

RESULTS_PER_PAGE = 50
MAX_PAGES = 20


def fetch_page(page: int) -> dict:
    url = f"{BASE_URL}/{page}"

    params = {
        "app_id": APP_ID,
        "app_key": APP_KEY,
        "where": "Bengaluru",
        "results_per_page": RESULTS_PER_PAGE,
        "content-type": "application/json",
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    return response.json()


def main() -> None:
    if not APP_ID or not APP_KEY:
        raise RuntimeError(
            "ADZUNA_APP_ID and ADZUNA_APP_KEY are missing from .env"
        )

    jobs = []

    print("Collecting Bengaluru employment opportunities...")

    for page in range(1, MAX_PAGES + 1):
        print(f"Fetching page {page}/{MAX_PAGES}...")

        data = fetch_page(page)
        results = data.get("results", [])

        if not results:
            print("No more results.")
            break

        jobs.extend(results)

        print(f"  Retrieved: {len(results):,}")
        print(f"  Total collected: {len(jobs):,}")

        if not data.get("results"):
            break

        time.sleep(0.5)

    rows = []

    for job in jobs:
        location = job.get("location") or {}
        company = job.get("company") or {}
        category = job.get("category") or {}

        latitude = job.get("latitude")
        longitude = job.get("longitude")

        # Spatial analysis requires coordinates.
        if latitude is None or longitude is None:
            continue

        try:
            latitude = float(latitude)
            longitude = float(longitude)
        except (TypeError, ValueError):
            continue

        # Bengaluru bounding box sanity check.
        if not (12.7 <= latitude <= 13.3):
            continue

        if not (77.2 <= longitude <= 77.9):
            continue

        salary = job.get("salary_min")
        salary_max = job.get("salary_max")

        rows.append(
            {
                "job_id": str(job.get("id", "")),
                "title": job.get("title"),
                "company": company.get("display_name"),
                "category": category.get("label"),
                "latitude": latitude,
                "longitude": longitude,
                "created": job.get("created"),
                "contract_time": job.get("contract_time"),
                "contract_type": job.get("contract_type"),
                "salary_min": salary,
                "salary_max": salary_max,
                "salary_currency": "INR",
                "location": location.get("display_name"),
                "source": "Adzuna",
            }
        )

    df = pd.DataFrame(rows)

    if df.empty:
        raise RuntimeError(
            "No geographically valid Bengaluru jobs were collected."
        )

    before = len(df)

    df = df.drop_duplicates(subset=["job_id"])
    df = df.drop_duplicates(
        subset=["title", "company", "latitude", "longitude"]
    )

    df = df.sort_values("created", ascending=False)

    output = OUTPUT_DIR / "bengaluru_employment.csv"
    df.to_csv(output, index=False)

    print()
    print("Employment dataset created.")
    print(f"Raw jobs collected: {len(jobs):,}")
    print(f"Geocoded jobs retained: {before:,}")
    print(f"Unique jobs after deduplication: {len(df):,}")
    print(f"Saved: {output}")


if __name__ == "__main__":
    main()