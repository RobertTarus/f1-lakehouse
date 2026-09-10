import argparse
import io
import json
import os
import re
from pathlib import Path

import boto3
import fastf1
import pandas as pd
from botocore.config import Config
from dotenv import load_dotenv


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

load_dotenv()

S3_ENDPOINT = os.getenv(
    "SEAWEED_S3_ENDPOINT",
    "http://localhost:8333",
)

S3_BUCKET = os.getenv(
    "SEAWEED_S3_BUCKET",
    "f1-raw",
)

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")

CACHE_DIR = Path("data/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

fastf1.Cache.enable_cache(str(CACHE_DIR))


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name="us-east-1",
        config=Config(
            s3={"addressing_style": "path"}
        ),
    )


def dataframe_to_parquet_bytes(df: pd.DataFrame) -> io.BytesIO:
    buffer = io.BytesIO()

    df.to_parquet(
        buffer,
        engine="pyarrow",
        index=False,
        compression="snappy",
    )

    buffer.seek(0)

    return buffer


def upload_dataframe(
    s3,
    df: pd.DataFrame,
    bucket: str,
    object_key: str,
):
    buffer = dataframe_to_parquet_bytes(df)

    s3.upload_fileobj(
        buffer,
        bucket,
        object_key,
    )

    print(
        f"Uploaded {object_key} "
        f"({len(df):,} rows)"
    )


def upload_json(
    s3,
    data: dict,
    bucket: str,
    object_key: str,
):
    payload = json.dumps(
        data,
        indent=2,
        default=str,
    )

    s3.put_object(
        Bucket=bucket,
        Key=object_key,
        Body=payload.encode("utf-8"),
        ContentType="application/json",
    )

    print(f"Uploaded {object_key}")


# ---------------------------------------------------------
# FastF1 extraction
# ---------------------------------------------------------

def load_session(
    year: int,
    event: str,
    session_type: str,
):
    print()
    print("=" * 60)
    print("FASTF1 EXTRACTION")
    print("=" * 60)

    print(f"Season : {year}")
    print(f"Event  : {event}")
    print(f"Session: {session_type}")

    session = fastf1.get_session(
        year,
        event,
        session_type,
    )

    # Telemetry is intentionally disabled for milestone 1.
    # We will build telemetry ingestion separately.
    session.load(
        telemetry=False,
        weather=True,
        messages=False,
    )

    return session


# ---------------------------------------------------------
# Main ingestion pipeline
# ---------------------------------------------------------

def ingest(
    year: int,
    event: str,
    session_type: str,
):
    session = load_session(
        year,
        event,
        session_type,
    )

    event_name = session.event["EventName"]

    event_slug = slugify(event_name)

    prefix = (
        f"season={year}/"
        f"event={event_slug}/"
        f"session={session_type}"
    )

    print()
    print("=" * 60)
    print("DATASETS")
    print("=" * 60)

    laps = session.laps.copy()
    results = session.results.copy()
    weather = session.weather_data.copy()

    print(f"Laps    : {len(laps):,}")
    print(f"Results : {len(results):,}")
    print(f"Weather : {len(weather):,}")

    s3 = get_s3_client()

    print()
    print("=" * 60)
    print("SEAWEEDFS UPLOAD")
    print("=" * 60)

    upload_dataframe(
        s3,
        laps,
        S3_BUCKET,
        f"{prefix}/laps.parquet",
    )

    upload_dataframe(
        s3,
        results,
        S3_BUCKET,
        f"{prefix}/results.parquet",
    )

    upload_dataframe(
        s3,
        weather,
        S3_BUCKET,
        f"{prefix}/weather.parquet",
    )

    metadata = {
        "season": year,
        "event_name": event_name,
        "session_type": session_type,
        "session_name": session.name,
        "country": session.event.get("Country"),
        "location": session.event.get("Location"),
        "event_date": session.event.get("EventDate"),
        "data_source": "FastF1",
        "storage_format": "Parquet",
        "storage_layer": "raw",
    }

    upload_json(
        s3,
        metadata,
        S3_BUCKET,
        f"{prefix}/metadata.json",
    )

    print()
    print("=" * 60)
    print("INGESTION COMPLETE")
    print("=" * 60)

    print(
        f"s3://{S3_BUCKET}/{prefix}/"
    )


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Ingest FastF1 session data into SeaweedFS."
    )

    parser.add_argument(
        "--year",
        type=int,
        required=True,
    )

    parser.add_argument(
        "--event",
        type=str,
        required=True,
    )

    parser.add_argument(
        "--session",
        type=str,
        default="R",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    ingest(
        year=args.year,
        event=args.event,
        session_type=args.session,
    )
