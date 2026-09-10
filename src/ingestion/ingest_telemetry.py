import argparse
import io
import os
import re
from pathlib import Path

import boto3
import fastf1
import pandas as pd

from botocore.config import Config
from dotenv import load_dotenv


load_dotenv()


BUCKET = os.getenv("SEAWEED_S3_BUCKET", "f1-raw")
S3_ENDPOINT = os.getenv(
    "SEAWEED_S3_ENDPOINT",
    "http://localhost:8333",
)

ACCESS_KEY = os.getenv("AWS_ACCESS_KEY_ID")
SECRET_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

CACHE_DIR = Path("data/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

fastf1.Cache.enable_cache(str(CACHE_DIR))


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def get_s3():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=ACCESS_KEY,
        aws_secret_access_key=SECRET_KEY,
        region_name="us-east-1",
        config=Config(
            s3={"addressing_style": "path"}
        ),
    )


def upload_dataframe(
    s3,
    df: pd.DataFrame,
    key: str,
):
    buffer = io.BytesIO()

    df.to_parquet(
        buffer,
        engine="pyarrow",
        compression="zstd",
        index=False,
    )

    size_mb = (
        buffer.getbuffer().nbytes
        / 1024
        / 1024
    )

    buffer.seek(0)

    s3.upload_fileobj(
        buffer,
        BUCKET,
        key,
    )

    return size_mb


def extract_driver(
    session,
    year: int,
    event: str,
    session_type: str,
    driver: str,
):
    driver_laps = session.laps.pick_drivers(driver)

    if driver_laps.empty:
        print(f"{driver}: no laps found")
        return None

    frames = []

    for _, lap in driver_laps.iterlaps():

        lap_number = lap.get("LapNumber")

        if pd.isna(lap_number):
            continue

        telemetry = lap.get_telemetry()

        if telemetry.empty:
            continue

        telemetry = telemetry.copy()

        telemetry["Season"] = year
        telemetry["EventName"] = event
        telemetry["EventSlug"] = slugify(event)
        telemetry["SessionType"] = session_type

        telemetry["Driver"] = driver

        telemetry["DriverNumber"] = str(
            lap.get("DriverNumber", "")
        )

        telemetry["Team"] = str(
            lap.get("Team", "")
        )

        telemetry["LapNumber"] = int(
            lap_number
        )

        frames.append(telemetry)

    if not frames:
        return None

    return pd.concat(
        frames,
        ignore_index=True,
    )


def ingest_race(
    year: int,
    event: str,
    session_type: str,
    selected_driver: str | None = None,
):

    print()
    print("=" * 75)
    print("FASTF1 FULL-RACE TELEMETRY INGESTION")
    print("=" * 75)

    print(f"Season : {year}")
    print(f"Event  : {event}")
    print(f"Session: {session_type}")

    print()
    print("Loading FastF1 session once...")

    session = fastf1.get_session(
        year,
        event,
        session_type,
    )

    session.load(
        telemetry=True,
        weather=False,
        messages=False,
    )

    print("Session loaded.")

    # Determine drivers from session results
    drivers = (
        session.results["Abbreviation"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    if selected_driver:
        selected_driver = selected_driver.upper()

        if selected_driver not in drivers:
            raise ValueError(
                f"Driver '{selected_driver}' "
                f"not found. Available: {drivers}"
            )

        drivers = [selected_driver]

    print()
    print(
        f"Drivers to process: {len(drivers)}"
    )

    print(
        ", ".join(drivers)
    )

    s3 = get_s3()

    event_slug = slugify(event)

    total_rows = 0
    total_size = 0.0
    successful = 0

    summary = []

    for position, driver in enumerate(
        drivers,
        start=1,
    ):

        print()
        print("-" * 75)

        print(
            f"[{position}/{len(drivers)}] "
            f"Processing {driver}"
        )

        try:

            df = extract_driver(
                session=session,
                year=year,
                event=event,
                session_type=session_type,
                driver=driver,
            )

            if df is None or df.empty:

                print(
                    f"{driver}: "
                    "no telemetry available"
                )

                continue

            key = (
                f"season={year}/"
                f"event={event_slug}/"
                f"session={session_type}/"
                f"telemetry/"
                f"driver={driver}/"
                f"telemetry.parquet"
            )

            size_mb = upload_dataframe(
                s3=s3,
                df=df,
                key=key,
            )

            rows = len(df)

            print(
                f"{driver}: "
                f"{rows:,} rows | "
                f"{size_mb:.2f} MB"
            )

            print(
                f"s3://{BUCKET}/{key}"
            )

            total_rows += rows
            total_size += size_mb
            successful += 1

            summary.append({
                "driver": driver,
                "rows": rows,
                "size_mb": round(
                    size_mb,
                    2,
                ),
                "object_key": key,
            })

        except Exception as exc:

            print(
                f"{driver}: FAILED"
            )

            print(
                f"Reason: {exc}"
            )

    # -----------------------------------------------------
    # Write ingestion manifest
    # -----------------------------------------------------

    if summary:

        manifest = pd.DataFrame(summary)

        manifest_key = (
            f"season={year}/"
            f"event={event_slug}/"
            f"session={session_type}/"
            f"telemetry/"
            f"_manifest.parquet"
        )

        upload_dataframe(
            s3,
            manifest,
            manifest_key,
        )

        print()
        print(
            f"Manifest: "
            f"s3://{BUCKET}/{manifest_key}"
        )

    print()
    print("=" * 75)
    print("INGESTION SUMMARY")
    print("=" * 75)

    print(
        f"Drivers processed : "
        f"{successful}/{len(drivers)}"
    )

    print(
        f"Telemetry rows    : "
        f"{total_rows:,}"
    )

    print(
        f"Stored data       : "
        f"{total_size:.2f} MB"
    )

    print()
    print(
        "FULL-RACE TELEMETRY "
        "INGESTION COMPLETE"
    )


def main():

    parser = argparse.ArgumentParser(
        description=(
            "Ingest FastF1 telemetry "
            "into SeaweedFS."
        )
    )

    parser.add_argument(
        "--year",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--event",
        required=True,
    )

    parser.add_argument(
        "--session",
        default="R",
    )

    parser.add_argument(
        "--driver",
        required=False,
        help=(
            "Optional driver abbreviation. "
            "Omit to process all drivers."
        ),
    )

    args = parser.parse_args()

    ingest_race(
        year=args.year,
        event=args.event,
        session_type=args.session,
        selected_driver=args.driver,
    )


if __name__ == "__main__":
    main()
